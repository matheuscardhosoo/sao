# Underworld (SAO) - Implementation Plan

**Goal:** Transform Underworld into a robust, extensible multi-agent environment with clean modular architecture, full offline/online agent execution, rich survival & economic gameplay mechanics, and a real-time web visualization dashboard.

---

## Phase A: Codebase Cleanup, Standardization & Offline Agent Loop

### 1. Remove Legacy Root Duplications
- **Archive/Remove Stale Root Files:**
  - `server.py` (superseded by `src/api/main.py`)
  - `world_engine.py` (superseded by `src/engine/logic.py` and `src/engine/models.py`)
  - `visualizer.py` (superseded by `src/visualizer.py`)
  - `analytics.py` (superseded by `src/utils/telemetry.py`)
  - `agent_llm.py` (superseded by `src/agents/agent_llm.py`)
- Clean up root imports and make `src/` the single source of truth.

### 2. Standardize Action Schema (`talk` vs `chat`)
- In `src/agents/agent_llm.py`:
  - Align system prompt to use `"action": "move|chat|collect"`.
  - Accept both `"chat"` and legacy `"talk"` gracefully, mapping `"talk"` to `"chat"`.
- In `src/api/main.py`:
  - Support both `chat` and `talk` in the request validator or alias them cleanly for backwards compatibility.

### 3. Modernize & Relocate Simple Heuristic Agent (`src/agents/agent_simple.py`)
- Move and refactor `agent_simple.py` to `src/agents/agent_simple.py`:
  - Target configurable API URLs (`UNDERWORLD_API_URL`, default `http://127.0.0.1:7788`).
  - Use `/agent/perceive/{agent_id}` and `/agent/action`.
  - Send directional moves (`{"direction": "north" | "south" | "east" | "west"}`).
  - Read `cell.get("terrain")` instead of deprecated `cell.get("char")`.
  - Support multiple vibes: `explorer`, `aggressive`, `social`, `scavenger`, `guardian`.

### 4. Upgrade Master Orchestrator (`main.py`)
- Add CLI arguments:
  - `--mode`: `simple` (default, 100% offline heuristic agents), `llm` (Ollama/OpenAI), or `mixed` (mix of heuristic and LLM agents).
  - `--no-visualizer`: Run headless server + agents.
  - `--backend`: `ollama` or `openai` (for LLM mode).
  - `--port`: Configurable port (default 7788).
  - `--web`: Launch Web dashboard.
- Graceful shutdown handling for all child agent processes and server.

---

## Phase B: Core Gameplay & Simulation Mechanics

### 1. Energy Consumption & Exhaustion
- **Initial State:** Agents start with `energy = 100` (max 100).
- **Consumption:**
  - `move`: -1 energy.
  - `chat`: -2 energy.
  - `idle`: -0 energy.
- **Exhaustion / Dormancy:**
  - When `energy <= 0`, agent cannot move until revived or re-energized.
  - Status is reflected in `WorldState` and tile history (`"Agent <id> exhausted"`).

### 2. Resource Collection & Inventory Accumulation
- **Collection (`collect` action):**
  - Verify agent position matches a resource (`!`).
  - Consume resource tile.
  - Increment agent `inventory` (e.g. `inventory: ["crystal"]` or resource count).
  - Restore agent `energy = min(max_energy, energy + 40)`.
  - Record telemetry event and log to tile history.

### 3. Trail Evaporation / Decay
- Background or step-based decay:
  - Tiles with `+` trail decay if not stepped on after $N$ ticks/seconds.
  - Prevents the entire grid from permanently saturating with `+`.

### 4. Agent Inspection & State API
- Enhance `GET /world/state` and `GET /agent/perceive/{agent_id}`:
  - Return agent metadata (`energy`, `inventory_count`, `vibe`/`personality`, `status`).

---

## Phase D: Real-Time Web Dashboard & Streaming

### 1. WebSocket Streaming Endpoint (`/ws/world`)
- Add WebSocket route in `src/api/main.py`:
  - Broadcasts `WorldState` updates at 2–4 Hz (or on state change) to all connected clients.
  - Reduces HTTP polling overhead.

### 2. Web Visualizer Dashboard
- Serve a clean HTML5/CSS/JavaScript dashboard directly from FastAPI at `/dashboard`:
  - **Live 2D Grid Canvas:** Interactive grid displaying `@` agents (with IDs/colors), `!` resources, `+` trails, and terrain.
  - **Agent Inspector Panel:** Live energy bars, inventory, current coordinates, and thought bubbles.
  - **Global Event Log & Chat Feed:** Real-time stream of agent announcements, movements, and speech.
  - **Controls:** Spawn manual resources, trigger agent actions, adjust simulation speed.

---

## Verification & Testing
- Unit tests in `tests/test_engine.py` for grid movement, collision, energy, collection, and perception.
- Integration tests in `tests/test_api.py` for all endpoints.
- End-to-end execution test of `main.py --mode simple` and `--web`.
