"""FastAPI server for Busy Bridge API.

Exposes REST endpoints that OpenClaw agents can call,
then bridges to Busy38's internal systems via the adapter.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .adapter import get_adapter, shutdown_adapter, Busy38Adapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class ToolUseRequest(BaseModel):
    description: str


class ToolMakeRequest(BaseModel):
    description: str


class MissionCreateRequest(BaseModel):
    objective: str
    role: str = "mission_agent"
    acceptance_criteria: List[str] = Field(default_factory=list)
    allowed_namespaces: List[str] = Field(default_factory=list)
    max_steps: int = 6
    qa_max_retries: int = 2


class MissionCancelRequest(BaseModel):
    reason: str


class MissionRespondRequest(BaseModel):
    response: str


class CheatcodeExecuteRequest(BaseModel):
    namespace: str
    action: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    logger.info("Starting Busy Bridge API server")
    # Initialize adapter (connects to Busy38)
    await get_adapter()
    yield
    # Cleanup
    logger.info("Shutting down Busy Bridge API server")
    await shutdown_adapter()


app = FastAPI(
    title="Busy Bridge API",
    description="Bridge between OpenClaw and Busy38",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_busy_adapter() -> Busy38Adapter:
    """Get the Busy38 adapter."""
    return await get_adapter()


# Health endpoint
@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "timestamp": datetime.utcnow().isoformat(),
        "busy38_connected": True,
    }


# Tool endpoints
@app.get("/tools")
async def list_tools():
    """List available tools."""
    try:
        adapter = await get_busy_adapter()
        tools = await adapter.list_tools()
        return {"tools": tools}
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools/{name}")
async def lookup_tool(name: str):
    """Get tool details."""
    try:
        adapter = await get_busy_adapter()
        tool = await adapter.lookup_tool(name)
        return tool
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to lookup tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/use")
async def use_tool(request: ToolUseRequest):
    """Execute a tool via plain English."""
    logger.info(f"Tool use request: {request.description}")
    try:
        adapter = await get_busy_adapter()
        result = await adapter.use_tool(request.description)
        return result
    except Exception as e:
        logger.error(f"Failed to use tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/make")
async def make_tool(request: ToolMakeRequest):
    """Create a new tool via mission."""
    logger.info(f"Tool make request: {request.description}")
    try:
        adapter = await get_busy_adapter()
        mission_id = await adapter.make_tool(request.description)
        return {
            "success": True,
            "mission_id": mission_id,
            "message": "Tool creation mission started",
        }
    except Exception as e:
        logger.error(f"Failed to start tool creation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mission endpoints
@app.get("/missions")
async def list_missions():
    """List all missions."""
    try:
        adapter = await get_busy_adapter()
        missions = await adapter.list_missions()
        return {"missions": missions}
    except Exception as e:
        logger.error(f"Failed to list missions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/missions")
async def create_mission(request: MissionCreateRequest):
    """Create a new mission."""
    try:
        adapter = await get_busy_adapter()
        mission_id = await adapter.start_mission(
            objective=request.objective,
            role=request.role,
            acceptance_criteria=request.acceptance_criteria,
            allowed_namespaces=request.allowed_namespaces,
            max_steps=request.max_steps,
        )
        return {
            "success": True,
            "mission_id": mission_id,
            "state": "pending",
        }
    except Exception as e:
        logger.error(f"Failed to create mission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/missions/{mission_id}")
async def get_mission(mission_id: str):
    """Get mission details."""
    try:
        adapter = await get_busy_adapter()
        mission = await adapter.get_mission(mission_id)
        return mission
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get mission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/missions/{mission_id}/notes")
async def get_mission_notes(mission_id: str):
    """Get notes for a mission."""
    try:
        adapter = await get_busy_adapter()
        notes = await adapter.get_mission_notes(mission_id)
        return {"notes": notes}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get mission notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/missions/{mission_id}/cancel")
async def cancel_mission(mission_id: str, request: MissionCancelRequest):
    """Cancel a mission."""
    try:
        adapter = await get_busy_adapter()
        success = await adapter.cancel_mission(mission_id, request.reason)
        if success:
            return {"success": True, "message": "Mission cancelled"}
        else:
            raise HTTPException(status_code=400, detail="Failed to cancel mission")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel mission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/missions/{mission_id}/respond")
async def respond_to_mission(mission_id: str, request: MissionRespondRequest):
    """Respond to a mission query."""
    try:
        adapter = await get_busy_adapter()
        success = await adapter.respond_to_mission(mission_id, request.response)
        if success:
            return {"success": True, "message": "Response recorded"}
        else:
            raise HTTPException(status_code=400, detail="Failed to record response")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to respond to mission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cheatcode endpoints
@app.post("/cheatcodes/execute")
async def execute_cheatcode(request: CheatcodeExecuteRequest):
    """Execute a cheatcode."""
    logger.info(f"Cheatcode: {request.namespace}:{request.action}")
    try:
        adapter = await get_busy_adapter()
        result = await adapter.execute_cheatcode(
            request.namespace, request.action, request.attributes
        )
        return result
    except Exception as e:
        logger.error(f"Failed to execute cheatcode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
