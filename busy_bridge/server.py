"""FastAPI server for Busy Bridge API.

Exposes REST endpoints that OpenClaw agents can call,
then bridges to Busy38's internal systems.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import Config
from .client import Busy38Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory stores (replace with proper storage)
missions_db: Dict[str, Dict] = {}
notes_db: Dict[str, List[Dict]] = {}
tools_db: Dict[str, Dict] = {}

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


# Dependency to get Busy38 client
async def get_busy_client():
    """Get Busy38 client."""
    config = Config.load()
    return Busy38Client(config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    logger.info("Starting Busy Bridge API server")
    yield
    logger.info("Shutting down Busy Bridge API server")


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


# Health endpoint
@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Tool endpoints
@app.get("/tools")
async def list_tools():
    """List available tools."""
    # TODO: Load from Busy38's tool registry
    tools = list(tools_db.values()) or [
        {
            "name": "read_file",
            "description": "Read content from a file",
            "category": "file",
        },
        {
            "name": "write_file", 
            "description": "Write content to a file",
            "category": "file",
        },
        {
            "name": "search_web",
            "description": "Search the web for information",
            "category": "web",
        },
        {
            "name": "shell",
            "description": "Execute shell commands",
            "category": "system",
        },
    ]
    return {"tools": tools}


@app.get("/tools/{name}")
async def lookup_tool(name: str):
    """Get tool details."""
    # TODO: Load from Busy38's tool registry
    if name in tools_db:
        return tools_db[name]
    
    # Return mock data for now
    return {
        "name": name,
        "description": f"Tool: {name}",
        "parameters": {},
        "examples": [],
    }


@app.post("/tools/use")
async def use_tool(request: ToolUseRequest):
    """Execute a tool via plain English."""
    logger.info(f"Tool use request: {request.description}")
    
    # TODO: Integrate with Busy38's orchestrator
    # For now, return a mock response
    return {
        "success": True,
        "result": f"Executed: {request.description}",
        "tool_used": "mock_tool",
    }


@app.post("/tools/make")
async def make_tool(request: ToolMakeRequest):
    """Create a new tool via mission."""
    logger.info(f"Tool make request: {request.description}")
    
    # Create a mission for tool creation
    mission_id = f"mission_{uuid4().hex[:10]}"
    mission = {
        "mission_id": mission_id,
        "objective": f"Create tool: {request.description}",
        "role": "tool_builder_agent",
        "state": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "steps": [],
    }
    missions_db[mission_id] = mission
    notes_db[mission_id] = []
    
    # Start mission in background
    asyncio.create_task(run_tool_creation_mission(mission_id, request.description))
    
    return {
        "success": True,
        "mission_id": mission_id,
        "message": "Tool creation mission started",
    }


async def run_tool_creation_mission(mission_id: str, description: str):
    """Run tool creation mission in background."""
    mission = missions_db[mission_id]
    mission["state"] = "running"
    
    # Step 1: Planning
    mission["steps"].append({
        "index": 0,
        "description": "Planning tool structure",
        "status": "completed",
    })
    
    # Step 2: Create YAML spec
    mission["steps"].append({
        "index": 1,
        "description": "Creating YAML specification",
        "status": "completed",
    })
    
    # Step 3: Implement handler
    mission["steps"].append({
        "index": 2,
        "description": "Implementing Python handler",
        "status": "completed",
    })
    
    # Step 4: QA Review
    mission["steps"].append({
        "index": 3,
        "description": "QA review",
        "status": "completed",
    })
    
    mission["state"] = "approved"
    mission["final_output"] = f"Tool created successfully: {description}"
    
    # Register the tool
    tool_name = description.split()[0].lower()
    tools_db[tool_name] = {
        "name": tool_name,
        "description": description,
        "category": "custom",
    }


# Mission endpoints
@app.get("/missions")
async def list_missions():
    """List all missions."""
    return {"missions": list(missions_db.values())}


@app.post("/missions")
async def create_mission(request: MissionCreateRequest):
    """Create a new mission."""
    mission_id = f"mission_{uuid4().hex[:10]}"
    
    mission = {
        "mission_id": mission_id,
        "objective": request.objective,
        "role": request.role,
        "state": "pending",
        "acceptance_criteria": request.acceptance_criteria,
        "allowed_namespaces": request.allowed_namespaces,
        "max_steps": request.max_steps,
        "created_at": datetime.utcnow().isoformat(),
        "steps": [],
    }
    
    missions_db[mission_id] = mission
    notes_db[mission_id] = []
    
    # Start mission in background
    asyncio.create_task(run_mission(mission_id, request))
    
    return {
        "success": True,
        "mission_id": mission_id,
        "state": "pending",
    }


async def run_mission(mission_id: str, request: MissionCreateRequest):
    """Run a mission in background."""
    mission = missions_db[mission_id]
    mission["state"] = "running"
    mission["started_at"] = datetime.utcnow().isoformat()
    
    # Simulate mission execution
    for i in range(min(request.max_steps, 3)):
        mission["steps"].append({
            "index": i,
            "description": f"Step {i+1}: Processing",
            "status": "completed",
        })
        await asyncio.sleep(1)  # Simulate work
    
    mission["state"] = "approved"
    mission["final_output"] = f"Mission completed: {request.objective}"
    mission["completed_at"] = datetime.utcnow().isoformat()


@app.get("/missions/{mission_id}")
async def get_mission(mission_id: str):
    """Get mission details."""
    if mission_id not in missions_db:
        raise HTTPException(status_code=404, detail="Mission not found")
    return missions_db[mission_id]


@app.get("/missions/{mission_id}/notes")
async def get_mission_notes(mission_id: str):
    """Get notes for a mission."""
    if mission_id not in missions_db:
        raise HTTPException(status_code=404, detail="Mission not found")
    return {"notes": notes_db.get(mission_id, [])}


@app.post("/missions/{mission_id}/cancel")
async def cancel_mission(mission_id: str, request: MissionCancelRequest):
    """Cancel a mission."""
    if mission_id not in missions_db:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    mission = missions_db[mission_id]
    mission["state"] = "cancelled"
    mission["cancel_reason"] = request.reason
    
    # Add cancellation note
    notes_db[mission_id].append({
        "category": "mission_cancel_request",
        "title": f"Mission cancelled: {mission_id}",
        "author_id": "user",
        "payload": {"reason": request.reason},
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    return {"success": True, "message": "Mission cancelled"}


@app.post("/missions/{mission_id}/respond")
async def respond_to_mission(mission_id: str, request: MissionRespondRequest):
    """Respond to a mission query."""
    if mission_id not in missions_db:
        raise HTTPException(status_code=404, detail="Mission not found")
    
    # Add response note
    notes_db[mission_id].append({
        "category": "orchestrator_response",
        "title": f"Response to mission query",
        "author_id": "user",
        "payload": {"response": request.response},
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    return {"success": True, "message": "Response recorded"}


# Cheatcode endpoints
@app.post("/cheatcodes/execute")
async def execute_cheatcode(request: CheatcodeExecuteRequest):
    """Execute a cheatcode."""
    logger.info(f"Cheatcode: {request.namespace}:{request.action}")
    
    # TODO: Integrate with Busy38's cheatcode registry
    # For now, return mock responses for rw4 namespace
    if request.namespace == "rw4":
        if request.action == "read_file":
            return {
                "success": True,
                "content": f"Mock content for {request.attributes.get('path', 'unknown')}",
            }
        elif request.action == "write_file":
            return {
                "success": True,
                "message": f"Wrote to {request.attributes.get('path', 'unknown')}",
            }
        elif request.action == "shell":
            return {
                "success": True,
                "output": f"Executed: {request.attributes.get('cmd', 'unknown')}",
            }
        elif request.action == "git_status":
            return {
                "success": True,
                "status": "On branch main\nnothing to commit, working tree clean",
            }
    
    return {
        "success": False,
        "error": f"Unknown cheatcode: {request.namespace}:{request.action}",
    }


def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
