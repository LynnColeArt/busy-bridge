"""HTTP client for Busy38 API."""

import json
from typing import Any, Dict, List, Optional

import httpx

from .config import Config


class Busy38Error(Exception):
    """Error from Busy38 API."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class Busy38Client:
    """Client for Busy38 orchestrator API."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        self.client = httpx.Client(
            base_url=self.config.url,
            timeout=self.config.timeout,
            headers=self._headers(),
        )
    
    def _headers(self) -> Dict[str, str]:
        """Build request headers with auth."""
        headers = {
            "Content-Type": "application/json",
            "X-Agent-ID": self.config.agent_id,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request."""
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            try:
                details = e.response.json()
            except json.JSONDecodeError:
                details = {}
            raise Busy38Error(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                details=details,
            )
        except httpx.RequestError as e:
            raise Busy38Error(f"Request failed: {e}")
    
    # Health
    def health(self) -> Dict[str, Any]:
        """Check API health."""
        return self._request("GET", "/health")
    
    # Tools
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        response = self._request("GET", "/tools")
        return response.get("tools", [])
    
    def lookup_tool(self, name: str) -> Dict[str, Any]:
        """Get full documentation for a tool."""
        return self._request("GET", f"/tools/{name}")
    
    def use_tool(self, description: str) -> Dict[str, Any]:
        """Execute a tool via plain English description."""
        return self._request("POST", "/tools/use", json={"description": description})
    
    # Missions
    def start_mission(
        self,
        objective: str,
        role: str = "mission_agent",
        acceptance_criteria: Optional[List[str]] = None,
        allowed_namespaces: Optional[List[str]] = None,
        max_steps: int = 6,
    ) -> Dict[str, Any]:
        """Start a new mission."""
        payload = {
            "objective": objective,
            "role": role,
            "acceptance_criteria": acceptance_criteria or [],
            "allowed_namespaces": allowed_namespaces or [],
            "max_steps": max_steps,
        }
        return self._request("POST", "/missions", json=payload)
    
    def list_missions(self) -> List[Dict[str, Any]]:
        """List all missions."""
        response = self._request("GET", "/missions")
        return response.get("missions", [])
    
    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        """Get mission details."""
        return self._request("GET", f"/missions/{mission_id}")
    
    def get_mission_notes(self, mission_id: str) -> List[Dict[str, Any]]:
        """Get notes for a mission."""
        response = self._request("GET", f"/missions/{mission_id}/notes")
        return response.get("notes", [])
    
    def cancel_mission(self, mission_id: str, reason: str) -> Dict[str, Any]:
        """Cancel a running mission."""
        return self._request(
            "POST",
            f"/missions/{mission_id}/cancel",
            json={"reason": reason},
        )
    
    def respond_to_mission(self, mission_id: str, response: str) -> Dict[str, Any]:
        """Respond to a mission query."""
        return self._request(
            "POST",
            f"/missions/{mission_id}/respond",
            json={"response": response},
        )
    
    # Tool Creation (specialized mission)
    def make_tool(self, description: str) -> Dict[str, Any]:
        """Create a new tool via mission."""
        return self._request("POST", "/tools/make", json={"description": description})
    
    # Cheatcodes
    def use_cheatcode(self, namespace: str, action: str, **attributes) -> Dict[str, Any]:
        """Execute a cheatcode."""
        return self._request(
            "POST",
            "/cheatcodes/execute",
            json={
                "namespace": namespace,
                "action": action,
                "attributes": attributes,
            },
        )
    
    # Streaming for real-time updates
    def stream_mission(self, mission_id: str):
        """Stream mission updates (requires WebSocket or SSE support)."""
        # TODO: Implement WebSocket streaming
        raise NotImplementedError("Streaming not yet implemented")
