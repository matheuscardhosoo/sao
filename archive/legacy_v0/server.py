"""
Underworld ASCII - API / MCP Bridge
Exposes world state and actions via REST endpoints.
"""

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from world_engine import World, GRID_SIZE
from analytics import log_event

app = FastAPI(title="Underworld ASCII API", version="1.0.0")
world = World(width=GRID_SIZE, height=GRID_SIZE)


class ActRequest(BaseModel):
    """Request body for POST /act."""

    agent_id: str = Field(..., min_length=1)
    action: Literal["move", "talk", "collect"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpawnRequest(BaseModel):
    """Request body for POST /spawn."""

    agent_id: str = Field(..., min_length=1)
    x: int = Field(..., ge=0, lt=GRID_SIZE)
    y: int = Field(..., ge=0, lt=GRID_SIZE)


class ResourceRequest(BaseModel):
    """Request body for POST /add_resource."""

    x: int = Field(..., ge=0, lt=GRID_SIZE)
    y: int = Field(..., ge=0, lt=GRID_SIZE)


@app.get("/perceive/{agent_id}")
def perceive(agent_id: str, radius: int = 2) -> dict:
    """
    Returns a (2*radius+1)x(2*radius+1) area around the agent,
    including tile history for environmental context.
    """
    if radius < 1 or radius > 5:
        raise HTTPException(status_code=400, detail="radius must be 1-5")
    result = world.get_perception(agent_id, radius=radius)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@app.post("/act")
def act(req: ActRequest) -> dict:
    """
    Execute an action: move, talk, or collect.
    Updates world state and records telemetry.
    """
    agent_id = req.agent_id
    action = req.action
    metadata = req.metadata

    if world.get_agent_position(agent_id) is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    success = False
    message = ""
    event_type = action

    if action == "move":
        dx = metadata.get("dx", 0)
        dy = metadata.get("dy", 0)
        if not isinstance(dx, int) or not isinstance(dy, int):
            raise HTTPException(status_code=400, detail="dx and dy must be integers")
        if abs(dx) > 1 or abs(dy) > 1:
            raise HTTPException(status_code=400, detail="Move limited to 1 cell per step")
        success, message = world.move(agent_id, dx, dy)
        log_event(agent_id, "move", message, {"dx": dx, "dy": dy})

    elif action == "talk":
        msg = metadata.get("message", "")
        if not isinstance(msg, str):
            msg = str(msg)
        success, message = world.talk(agent_id, msg)
        log_event(agent_id, "talk", msg, {"message": msg})

    elif action == "collect":
        success, message = world.collect(agent_id)
        log_event(agent_id, "collect", message, {})

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    return {"success": success, "message": message, "action": action}


@app.get("/world")
def get_world() -> dict:
    """Return full world state for visualizer."""
    return world.get_full_state()


@app.post("/spawn")
def spawn(req: SpawnRequest) -> dict:
    """Spawn an agent at (x, y). Used by bootstrapper."""
    ok = world.spawn_agent(req.agent_id, req.x, req.y)
    if not ok:
        raise HTTPException(status_code=400, detail="Spawn failed (cell occupied or invalid)")
    log_event(req.agent_id, "spawn", f"Spawned at ({req.x},{req.y})", {"x": req.x, "y": req.y})
    return {"success": True, "agent_id": req.agent_id, "x": req.x, "y": req.y}


@app.post("/add_resource")
def add_resource(req: ResourceRequest) -> dict:
    """Add a resource at (x, y)."""
    ok = world.add_resource(req.x, req.y)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to add resource")
    return {"success": True, "x": req.x, "y": req.y}


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the server (for programmatic use)."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
