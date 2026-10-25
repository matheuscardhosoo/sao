"""
Underworld API - FastAPI entry point for the simulation.
Includes WebSocket streaming and Web Dashboard.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel, Field

from engine.logic import WorldEngine
from engine.models import WorldState
from utils.telemetry import SimulationLogger

sim_logger = SimulationLogger()
engine: WorldEngine | None = None
DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"


async def _spawn_resource_loop(world: WorldEngine) -> None:
    """Background task: spawn resources every 10 seconds."""
    while True:
        try:
            await asyncio.sleep(10)
            world.spawn_resource()
        except asyncio.CancelledError:
            break


async def _decay_trail_loop(world: WorldEngine) -> None:
    """Background task: decay trails every 15 seconds."""
    while True:
        try:
            await asyncio.sleep(15)
            world.decay_trails()
        except asyncio.CancelledError:
            break


async def _dummy_agent_loop(world: WorldEngine) -> None:
    """Background task: dummy agents act randomly every 3 seconds."""
    import random
    directions = ["north", "south", "east", "west"]
    while True:
        try:
            await asyncio.sleep(3)
            dummy_ids = [aid for aid in world.agents if aid.startswith("dummy_")]
            if dummy_ids:
                aid = random.choice(dummy_ids)
                agent = world.agents.get(aid)
                if agent and agent.is_active:
                    # Check if on resource
                    if agent.position.as_tuple() in world.resources:
                        world.collect(aid)
                    else:
                        world.move_agent(aid, random.choice(directions))
        except asyncio.CancelledError:
            break


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle. WorldEngine singleton + seed data + background tasks."""
    global engine
    logger.info("Underworld API starting")
    engine = WorldEngine(width=20, height=20)
    app.state.engine = engine

    # Seed 2–3 dummy agents at random positions
    import random
    positions: list[tuple[int, int]] = []
    for _ in range(3):
        for _ in range(50):
            x, y = random.randint(0, 19), random.randint(0, 19)
            if (x, y) not in positions:
                positions.append((x, y))
                engine.spawn_agent(f"dummy_{len(positions) - 1}", x, y)
                break

    # Initial resources
    for _ in range(4):
        engine.spawn_resource()

    spawn_task = asyncio.create_task(_spawn_resource_loop(engine))
    decay_task = asyncio.create_task(_decay_trail_loop(engine))
    dummy_task = asyncio.create_task(_dummy_agent_loop(engine))
    logger.info("Dummy agents, resources, and trail decay background loops seeded")

    yield

    spawn_task.cancel()
    decay_task.cancel()
    dummy_task.cancel()
    for t in (spawn_task, decay_task, dummy_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    logger.info("Underworld API shutting down")


app = FastAPI(
    title="Underworld ASCII API",
    version="1.0.0",
    description="Persistent, decentralized environment for autonomous AI agents",
    lifespan=lifespan,
)


def _get_engine() -> WorldEngine:
    if engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return engine


class ActionRequest(BaseModel):
    """Request body for POST /agent/action."""

    agent_id: str = Field(..., min_length=1)
    action: Literal["move", "chat", "talk", "collect"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpawnRequest(BaseModel):
    """Request body for spawning an agent."""

    agent_id: str = Field(..., min_length=1)
    x: int = Field(..., ge=0, lt=20)
    y: int = Field(..., ge=0, lt=20)
    personality: str = Field(default="")


class ResourceRequest(BaseModel):
    """Request body for adding a resource."""

    x: int = Field(..., ge=0, lt=20)
    y: int = Field(..., ge=0, lt=20)


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    """Serve the Web Dashboard at root."""
    if DASHBOARD_PATH.exists():
        return HTMLResponse(content=DASHBOARD_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Underworld API Running</h1><p>Visit /docs for Swagger.</p>")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Serve the Web Dashboard."""
    if DASHBOARD_PATH.exists():
        return HTMLResponse(content=DASHBOARD_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Underworld API Running</h1><p>Dashboard template missing.</p>")


@app.get("/api/info")
def api_info() -> dict:
    """Health check and API info."""
    return {
        "name": "Underworld ASCII API",
        "version": "1.0.0",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "ws_stream": "/ws/world",
    }


def _get_world_state() -> WorldState:
    """Return the full grid, agents, details, and event log for visualizer/dashboard."""
    world = _get_engine()
    data = world.get_full_state()
    return WorldState(
        grid=data["grid"],
        agents=data["agents"],
        agent_details=data["agent_details"],
        event_log=data["event_log"],
    )


@app.get("/world/state", response_model=WorldState)
def get_world_state() -> WorldState:
    """Return the full grid and agents for the visualizer."""
    return _get_world_state()


@app.get("/world", response_model=WorldState)
def get_world() -> WorldState:
    """Alias for /world/state for backward compatibility."""
    return _get_world_state()


@app.get("/agent/perceive/{agent_id}")
def agent_perceive(agent_id: str, radius: int = 3) -> dict:
    """Return the local view, stats, and tile history around the agent."""
    world = _get_engine()
    if radius < 1 or radius > 5:
        raise HTTPException(status_code=400, detail="radius must be 1-5")
    result = world.get_perception(agent_id, radius=radius)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@app.post("/agent/action")
def agent_action(req: ActionRequest) -> dict:
    """Validate and execute agent moves, speech, or collection."""
    world = _get_engine()
    if world.agents.get(req.agent_id) is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    action_type = "chat" if req.action == "talk" else req.action
    success = False
    message = ""
    perception = None

    if action_type == "move":
        direction = req.metadata.get("direction", "north")
        if not isinstance(direction, str):
            raise HTTPException(status_code=400, detail="direction must be a string")
        success, message = world.move_agent(req.agent_id, direction)
        sim_logger.log(req.agent_id, "move", message, {"direction": direction})
        perception = world.get_perception(req.agent_id, radius=3)

    elif action_type == "chat":
        msg = req.metadata.get("message", "")
        if not isinstance(msg, str):
            msg = str(msg)
        success, message = world.chat(req.agent_id, msg)
        sim_logger.log(req.agent_id, "chat", msg, {"message": msg})
        perception = world.get_perception(req.agent_id, radius=3)

    elif action_type == "collect":
        success, message = world.collect(req.agent_id)
        sim_logger.log(req.agent_id, "collect", message, {})
        perception = world.get_perception(req.agent_id, radius=3)

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    return {
        "success": success,
        "message": message,
        "action": action_type,
        "perception": perception,
    }


@app.post("/spawn")
def spawn(req: SpawnRequest) -> dict:
    """Spawn or revive an agent at (x, y)."""
    world = _get_engine()
    ok = world.spawn_agent(req.agent_id, req.x, req.y, req.personality)
    if not ok:
        raise HTTPException(status_code=400, detail="Spawn failed (cell occupied or invalid)")
    sim_logger.log(req.agent_id, "spawn", f"Spawned at ({req.x},{req.y})", {"x": req.x, "y": req.y})
    return {"success": True, "agent_id": req.agent_id, "x": req.x, "y": req.y}


@app.post("/add_resource")
def add_resource(req: ResourceRequest) -> dict:
    """Add a resource at (x, y)."""
    world = _get_engine()
    ok = world.add_resource(req.x, req.y)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to add resource")
    return {"success": True, "x": req.x, "y": req.y}


@app.websocket("/ws/world")
async def websocket_world(websocket: WebSocket) -> None:
    """WebSocket stream sending WorldState updates to connected browsers at 2Hz."""
    await websocket.accept()
    try:
        while True:
            state = _get_world_state()
            await websocket.send_json(state.model_dump())
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, Exception):
        pass
