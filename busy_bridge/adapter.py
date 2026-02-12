"""Adapter layer for Busy38 integration.

This module wraps Busy38 internals behind a stable interface for
busy-bridge server endpoints.
"""

from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


class Busy38Adapter:
    """Adapter that wraps Busy38 internals."""

    def __init__(self):
        self.orchestrator: Optional[Any] = None
        self.tool_manager: Optional[Any] = None
        self._busy_src_path: Optional[Path] = None

        self._Busy38Orchestrator: Optional[Type[Any]] = None
        self._OrchestratorConfig: Optional[Type[Any]] = None
        self._MissionSpec: Optional[Type[Any]] = None
        self._ToolManager: Optional[Type[Any]] = None
        self._cheatcode_registry: Optional[Any] = None

        self._initialized = False

    def _resolve_busy_source_path(self) -> Optional[Path]:
        candidates: List[Path] = []

        raw_env = os.getenv("BUSY38_SOURCE_PATH", "").strip()
        if raw_env:
            candidates.append(Path(raw_env))

        here = Path(__file__).resolve()
        project_root = here.parent.parent
        workspace = project_root.parent
        candidates.extend(
            [
                Path.cwd(),
                project_root,
                workspace / "busy-38-ongoing",
                workspace / "Busy38",
                workspace / "Busy",
                workspace / "busy-src",
            ]
        )

        seen = set()
        for candidate in candidates:
            p = candidate.expanduser().resolve()
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            if (p / "core" / "orchestration" / "integration.py").exists():
                return p
        return None

    def _ensure_busy_imports(self) -> None:
        if self._Busy38Orchestrator is not None:
            return

        src = self._resolve_busy_source_path()
        if src is None:
            raise RuntimeError(
                "Could not locate Busy source path. Set BUSY38_SOURCE_PATH to your Busy checkout."
            )
        self._busy_src_path = src
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

        integration_mod = importlib.import_module("core.orchestration.integration")
        registry_mod = importlib.import_module("core.cheatcodes.registry")
        mission_mod = importlib.import_module("core.mission")
        tools_mod = importlib.import_module("core.tools.manager")

        self._Busy38Orchestrator = getattr(integration_mod, "Busy38Orchestrator")
        self._OrchestratorConfig = getattr(integration_mod, "OrchestratorConfig")
        self._cheatcode_registry = getattr(registry_mod, "cheatcode_registry")
        self._MissionSpec = getattr(mission_mod, "MissionSpec")
        self._ToolManager = getattr(tools_mod, "ToolManager")

    async def initialize(self):
        """Initialize Busy38 components."""
        if self._initialized:
            return

        self._ensure_busy_imports()

        config = self._OrchestratorConfig()
        self.orchestrator = self._Busy38Orchestrator(config)
        await self.orchestrator.start()

        tools_dir = None
        if self._busy_src_path is not None:
            tools_dir = self._busy_src_path / "capabilities" / "tools"
        self.tool_manager = self._ToolManager(tools_dir=str(tools_dir) if tools_dir else "capabilities/tools")
        self.tool_manager.load_all()

        self._initialized = True

    async def shutdown(self):
        """Cleanup Busy38 components."""
        if self.orchestrator:
            await self.orchestrator.stop()
        self._initialized = False

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        await self.initialize()
        tools = []
        for _, spec in self.tool_manager._tools.items():
            tools.append(
                {
                    "name": spec.get("name", ""),
                    "description": spec.get("description", ""),
                    "category": "general",
                }
            )
        return tools

    async def lookup_tool(self, name: str) -> Dict[str, Any]:
        """Get tool details."""
        await self.initialize()
        spec = self.tool_manager._tools.get(name)
        if not spec:
            raise ValueError(f"Tool not found: {name}")
        return spec

    async def use_tool(self, description: str) -> Dict[str, Any]:
        """Execute a tool via plain English description."""
        await self.initialize()
        result = await self.orchestrator.run_agent_loop(f"Use a tool to: {description}")
        return {
            "success": True,
            "result": result,
            "tool_used": "inferred_from_description",
        }

    async def make_tool(self, description: str) -> str:
        """Create a new tool via mission and return mission id."""
        await self.initialize()
        spec = self._MissionSpec(
            objective=f"Create a tool that: {description}",
            role="tool_builder_agent",
            acceptance_criteria=[
                "YAML spec created in capabilities/tools/",
                "Handler class implements Tool base",
                "Includes example usage",
                "Passes security scan",
            ],
        )
        run = self.orchestrator.missions.start_mission(spec)
        return run.spec.mission_id

    async def list_missions(self) -> List[Dict[str, Any]]:
        """List all missions."""
        await self.initialize()
        runs = self.orchestrator.missions.list_runs()
        return [self._serialize_mission_run(run) for run in runs]

    async def get_mission(self, mission_id: str) -> Dict[str, Any]:
        """Get mission details."""
        await self.initialize()
        run = self.orchestrator.missions.get_run(mission_id)
        if not run:
            raise ValueError(f"Mission not found: {mission_id}")
        return self._serialize_mission_run(run)

    async def start_mission(
        self,
        objective: str,
        role: str = "mission_agent",
        acceptance_criteria: Optional[List[str]] = None,
        allowed_namespaces: Optional[List[str]] = None,
        max_steps: int = 6,
    ) -> str:
        """Start a new mission and return mission id."""
        await self.initialize()
        spec = self._MissionSpec(
            objective=objective,
            role=role,
            acceptance_criteria=acceptance_criteria or [],
            allowed_namespaces=allowed_namespaces or [],
            max_steps=max_steps,
        )
        run = self.orchestrator.missions.start_mission(spec)
        return run.spec.mission_id

    async def cancel_mission(self, mission_id: str, reason: str) -> bool:
        """Cancel a mission."""
        await self.initialize()
        return self.orchestrator.missions.cancel_mission(
            mission_id, reason=reason, cancelled_by="busy-bridge"
        )

    async def respond_to_mission(self, mission_id: str, response: str) -> bool:
        """Respond to a mission query via Busy notes API."""
        await self.initialize()
        run = self.orchestrator.missions.get_run(mission_id)
        if not run:
            raise ValueError(f"Mission not found: {mission_id}")

        notes = self.orchestrator.missions.notes
        if hasattr(notes, "post_structured_note"):
            notes.post_structured_note(
                recipient_id=mission_id,
                author_id="busy-bridge",
                author_role="bridge_orchestrator",
                title="Response to mission query",
                category="orchestrator_response",
                payload={"response": response},
                related_mission_id=mission_id,
            )
            return True

        raise RuntimeError("Busy notes API does not support structured mission responses")

    async def get_mission_notes(self, mission_id: str) -> List[Dict[str, Any]]:
        """Get notes for a mission."""
        await self.initialize()
        notes_mgr = self.orchestrator.missions.notes
        if hasattr(notes_mgr, "get_mission_notes"):
            notes = notes_mgr.get_mission_notes(mission_id)
        elif hasattr(notes_mgr, "get_notes_for_context"):
            notes = notes_mgr.get_notes_for_context(mission_id)
        else:
            notes = []

        out: List[Dict[str, Any]] = []
        for note in notes:
            payload = (getattr(note, "metadata", {}) or {}).get("payload", {})
            ts = (
                note.created_at.isoformat()
                if hasattr(note, "created_at") and note.created_at is not None
                else datetime.utcnow().isoformat()
            )
            out.append(
                {
                    "category": getattr(note, "category", "unknown"),
                    "title": getattr(note, "title", ""),
                    "author_id": getattr(note, "author_id", ""),
                    "payload": payload,
                    "timestamp": ts,
                }
            )
        return out

    async def execute_cheatcode(
        self, namespace: str, action: str, attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a cheatcode."""
        await self.initialize()
        try:
            result = self._cheatcode_registry.execute(namespace, action, attributes)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _serialize_mission_run(self, run) -> Dict[str, Any]:
        """Convert MissionRunRecord to dict."""
        return {
            "mission_id": run.spec.mission_id,
            "objective": run.spec.objective,
            "role": run.spec.role,
            "state": run.state.value if hasattr(run.state, "value") else str(run.state),
            "acceptance_criteria": run.spec.acceptance_criteria,
            "allowed_namespaces": run.spec.allowed_namespaces,
            "max_steps": run.spec.max_steps,
            "created_at": run.created_at.isoformat()
            if hasattr(run.created_at, "isoformat")
            else str(run.created_at),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "final_output": run.final_output,
            "error": run.error,
            "steps": [
                {
                    "index": step.index,
                    "description": step.description,
                    "status": step.status,
                    "output": step.output,
                }
                for step in run.steps
            ],
            "cancel_reason": run.cancel_reason,
            "cancelled_by": run.cancelled_by,
        }


# Global adapter instance
_adapter: Optional[Busy38Adapter] = None


async def get_adapter() -> Busy38Adapter:
    """Get or create the global adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = Busy38Adapter()
        await _adapter.initialize()
    return _adapter


async def shutdown_adapter():
    """Shutdown the global adapter."""
    global _adapter
    if _adapter:
        await _adapter.shutdown()
        _adapter = None
