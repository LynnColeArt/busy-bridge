"""Adapter layer for Busy38 integration.

This module wraps Busy38's core internals, providing a clean interface
for the busy-bridge server. When you want to switch to HTTP API later,
just swap this adapter for an HTTP client.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4

# Add busy-src to path
BUSY_SRC_PATH = Path(__file__).parent.parent.parent / "busy-src"
if str(BUSY_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(BUSY_SRC_PATH))

# Import Busy38 core
from core.orchestration.integration import Busy38Orchestrator, OrchestratorConfig
from core.cheatcodes.registry import cheatcode_registry
from core.mission import MissionSpec, MissionRuntime
from core.tools.manager import ToolManager


class Busy38Adapter:
    """Adapter that wraps Busy38's internals.
    
    This provides a clean interface for busy-bridge server to use.
    When switching to HTTP API, replace this class with HTTP calls.
    """
    
    def __init__(self):
        self.orchestrator: Optional[Busy38Orchestrator] = None
        self.tool_manager: Optional[ToolManager] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Busy38 components."""
        if self._initialized:
            return
        
        # Initialize orchestrator
        config = OrchestratorConfig()
        self.orchestrator = Busy38Orchestrator(config)
        await self.orchestrator.start()
        
        # Initialize tool manager
        self.tool_manager = ToolManager()
        self.tool_manager.load_all()
        
        self._initialized = True
    
    async def shutdown(self):
        """Cleanup Busy38 components."""
        if self.orchestrator:
            await self.orchestrator.stop()
        self._initialized = False
    
    # Tool operations
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        await self.initialize()
        catalog = self.tool_manager.get_catalog()
        # Parse catalog string or get from internal _tools
        tools = []
        for name, spec in self.tool_manager._tools.items():
            tools.append({
                "name": spec["name"],
                "description": spec["description"],
                "category": "general",  # Could extract from spec
            })
        return tools
    
    async def lookup_tool(self, name: str) -> Dict[str, Any]:
        """Get tool details."""
        await self.initialize()
        spec = self.tool_manager._tools.get(name)
        if not spec:
            raise ValueError(f"Tool not found: {name}")
        return spec
    
    async def use_tool(self, description: str) -> Dict[str, Any]:
        """Execute a tool via plain English description.
        
        This uses the orchestrator to interpret the description
        and invoke the appropriate tool.
        """
        await self.initialize()
        
        # Use orchestrator to run the tool request
        result = await self.orchestrator.run_agent_loop(
            f"Use a tool to: {description}"
        )
        
        return {
            "success": True,
            "result": result,
            "tool_used": "inferred_from_description",
        }
    
    async def make_tool(self, description: str) -> str:
        """Create a new tool via mission.
        
        Returns mission_id for tracking.
        """
        await self.initialize()
        
        # Create a mission spec for tool creation
        spec = MissionSpec(
            objective=f"Create a tool that: {description}",
            role="tool_builder_agent",
            acceptance_criteria=[
                "YAML spec created in capabilities/tools/",
                "Handler class implements Tool base",
                "Includes example usage",
                "Passes security scan",
            ],
        )
        
        # Start the mission via orchestrator's mission runtime
        run = self.orchestrator.missions.start_mission(spec)
        return run.spec.mission_id
    
    # Mission operations
    async def list_missions(self) -> List[Dict[str, Any]]:
        """List all missions."""
        await self.initialize()
        
        runs = self.orchestrator.missions.list_runs()
        missions = []
        for run in runs:
            missions.append(self._serialize_mission_run(run))
        return missions
    
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
        """Start a new mission. Returns mission_id."""
        await self.initialize()
        
        spec = MissionSpec(
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
        """Respond to a mission query."""
        await self.initialize()
        
        # Add a note to the mission
        run = self.orchestrator.missions.get_run(mission_id)
        if not run:
            raise ValueError(f"Mission not found: {mission_id}")
        
        # TODO: Implement proper response mechanism
        # For now, add as a note
        self.orchestrator.missions.notes.add_note(
            recipient_id=mission_id,
            category="orchestrator_response",
            title="Response to mission query",
            payload={"response": response},
            author_id="busy-bridge",
        )
        return True
    
    async def get_mission_notes(self, mission_id: str) -> List[Dict[str, Any]]:
        """Get notes for a mission."""
        await self.initialize()
        
        # Get notes from the notes manager
        notes = self.orchestrator.missions.notes.get_notes_for_context(mission_id)
        return [
            {
                "category": note.category,
                "title": note.title,
                "author_id": note.author_id,
                "payload": note.payload,
                "timestamp": note.timestamp.isoformat() if hasattr(note, 'timestamp') else datetime.utcnow().isoformat(),
            }
            for note in notes
        ]
    
    # Cheatcode operations
    async def execute_cheatcode(
        self, namespace: str, action: str, attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a cheatcode."""
        await self.initialize()
        
        try:
            result = cheatcode_registry.execute(namespace, action, attributes)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Helper methods
    def _serialize_mission_run(self, run) -> Dict[str, Any]:
        """Convert MissionRunRecord to dict."""
        return {
            "mission_id": run.spec.mission_id,
            "objective": run.spec.objective,
            "role": run.spec.role,
            "state": run.state.value if hasattr(run.state, 'value') else str(run.state),
            "acceptance_criteria": run.spec.acceptance_criteria,
            "allowed_namespaces": run.spec.allowed_namespaces,
            "max_steps": run.spec.max_steps,
            "created_at": run.created_at.isoformat() if hasattr(run.created_at, 'isoformat') else str(run.created_at),
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
