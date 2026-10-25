# Underworld (SAO) - Autonomous Multi-Agent Simulation

A persistent 2D simulation environment with **Environmental Memory**, energy dynamics, and real-time visualization for autonomous AI entities.

```
       ┌────────────────────────────────────────────────────────┐
       │                WorldEngine (20x20 Grid)                │
       │  - Tile Memory (walk count, history, trails '+')       │
       │  - Entities: Agents ('@') & Resources ('!')            │
       └───────────────────────────┬────────────────────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   FastAPI Server (src/api)                 Telemetry Logger
   - GET  /world/state                      - logs/underworld.jsonl
   - GET  /agent/perceive/{agent_id}
   - POST /agent/action (move, chat, collect)
   - WebSocket /ws/world & Web Dashboard
              │
    ┌─────────┴──────────────────────┐
    ▼                                ▼
Web / Curses Dashboard         Autonomous Agents
- Live 2D ASCII Grid           - Heuristic Agent (5 Vibes)
- Global Event Log & Audio     - LLM Brain (Ollama/OpenAI)
```

---

## One-Command Operations (`manage.py` & `make`)

Use `manage.py` or `Makefile` shortcuts to perform all repetitive tasks with **zero LLM token costs**:

```bash
# 1. Check live simulation status (agents, energy, crystals, positions):
python manage.py status       # Or: make status

# 2. Train an autonomous RL policy locally in ~3 seconds (0 tokens!):
python manage.py train        # Or: make train

# 3. Benchmark agent policies (Random vs Heuristic vs Trained):
python manage.py benchmark    # Or: make benchmark

# 4. Spawn a trained RL agent into the simulation:
python manage.py spawn trained_oracle --type trained   # Or: make spawn-trained

# 5. Spawn an entire balanced ecosystem of 5 diverse agents:
python manage.py spawn-team   # Or: make spawn-team

# 6. Spawn a custom heuristic vibe agent:
python manage.py spawn scout_1 --type heuristic --vibe explorer

# 7. Add an energy crystal manually at (x, y):
python manage.py add-resource --x 10 --y 10

# 8. Stop all background agent processes:
python manage.py kill-all     # Or: make kill-all
```

---

## Quickstart with Docker (Live Hot-Reloading)

The container keeps the simulation running in the background and mounts `./src` as a live volume, allowing you to edit code or spawn agents on the fly with instant updates.

### 1. Start the Container
```bash
make docker-up
```
Or with Docker Compose:
```bash
docker compose up -d underworld
```

### 2. Open Live Web Dashboard
Navigate to **[http://localhost:7788/dashboard](http://localhost:7788/dashboard)** in your browser.
- **2D ASCII Matrix**: Live rendering of `@` agents, `!` crystals, `+` trails, and terrain.
- **Live WebSocket Stream**: Real-time updates delivered at 2 Hz.
- **Entity Inspector**: Watch agent energy levels, crystal inventories, coordinates, and status.

### 3. On-The-Fly Manipulations
Because `./src` is mounted into the container with Uvicorn `--reload`, any change you make to:
- [`src/engine/logic.py`](src/engine/logic.py)
- [`src/engine/models.py`](src/engine/models.py)
- [`src/api/main.py`](src/api/main.py)
- [`src/api/dashboard.html`](src/api/dashboard.html)

is immediately picked up live inside the running container without rebuilding.

#### Spawn a Custom Agent On the Fly:
```bash
# 1. Register spawn position
curl -X POST http://localhost:7788/spawn \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "live_scout", "x": 10, "y": 10, "personality": "Live explorer"}'

# 2. Run agent loop inside the container
docker compose exec -d underworld python src/agents/agent_simple.py \
  --agent-id live_scout \
  --vibe scavenger
```

#### Tail Live Container Logs:
```bash
make docker-logs
```

#### Stop the Container:
```bash
make docker-down
```

---

## Running Locally (Without Docker)

```bash
# 1. Create and activate venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Run simulation with 4 autonomous agents + open web dashboard:
python main.py --web

# Or run headless server + web dashboard:
python main.py --no-visualizer --web
```

---

## Agent Configuration & Behavioral Archetypes

See [**`docs/definitions/custom_agents_guide.md`**](docs/definitions/custom_agents_guide.md) for full tuning and training guides.

### Heuristic Vibes:
- `scavenger`: B-lines toward `!` energy crystals and hoards resources.
- `explorer`: Charts unexplored ground (`.`) and follows fresh trails (`+`).
- `social`: Seeks other agents (`@`) and initiates conversation via tile memory.
- `guardian`: Establishes a perimeter around its spawn post and issues warnings.
- `aggressive`: Confronts and tracks nearest agents.

### LLM Agents:
```bash
# Ollama:
python src/agents/agent_llm.py --name hermit --personality "Cynical hermit" --backend ollama

# OpenAI:
OPENAI_API_KEY="sk-..." python src/agents/agent_llm.py --name merchant --personality "Trader" --backend openai
```

---

## API Reference

- `GET /world/state` — Full grid, active entities, energy levels, and event log.
- `GET /agent/perceive/{agent_id}?radius=2` — Local perception view with tile history.
- `POST /agent/action` — `{agent_id, action: "move"|"chat"|"collect", metadata}`.
- `POST /spawn` — Spawn or revive agent at `(x, y)`.
- `POST /add_resource` — Place energy crystal at `(x, y)`.
- `WS /ws/world` — Real-time WebSocket stream of simulation state.
- `GET /dashboard` — Interactive HTML5 dashboard.

---

## Tests & Linting

```bash
make test    # Runs pytest suite (10/10 passing)
make lint    # Runs ruff
```
