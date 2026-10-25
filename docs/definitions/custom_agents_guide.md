# Custom Agents: Configuration, Tuning & Training Guide

This guide explains how to define, configure, tune, and train autonomous agents to inhabit the **Underworld** simulation.

---

## 1. Agent Anatomy in Underworld

Every agent in Underworld operates on an autonomous **Perceive $\to$ Contextualize $\to$ Think $\to$ Act** loop:

```
         ┌────────────────────────────────────────────────────────┐
         │              1. PERCEIVE (Local Vision)                │
         │  GET /agent/perceive/{agent_id}?radius=2               │
         │  Reads 5x5 grid: tiles, terrain, agents, tile history  │
         └───────────────────────────┬────────────────────────────┘
                                     │
         ┌───────────────────────────▼────────────────────────────┐
         │            2. CONTEXTUALIZE / MEMORY                   │
         │  - Converts grid into narrative or vector state        │
         │  - Parses past footprints and tile message history     │
         └───────────────────────────┬────────────────────────────┘
                                     │
         ┌───────────────────────────▼────────────────────────────┐
         │             3. THINK / DECIDE (The Brain)              │
         │  - Heuristic Policy (Rule-based vibe) OR               │
         │  - LLM Decision Engine (Prompt + Persona + Examples)   │
         └───────────────────────────┬────────────────────────────┘
                                     │
         ┌───────────────────────────▼────────────────────────────┐
         │                 4. ACT (API Execution)                 │
         │  POST /agent/action:                                   │
         │  - "move"    {"direction": "north"|"south"|...}        │
         │  - "collect" {}                                        │
         │  - "chat"    {"message": "..."}                        │
         └────────────────────────────────────────────────────────┘
```

---

## 2. Agent Types: Heuristic vs. LLM-Powered

| Capability | Heuristic Agent (`agent_simple.py`) | LLM Agent (`agent_llm.py`) |
| :--- | :--- | :--- |
| **Speed** | Instantaneous (<10ms) | Model-dependent (0.2s - 2s) |
| **Requirements** | Zero external dependencies (100% offline) | Needs Ollama, OpenAI, or API key |
| **Cost** | Free ($0) | Local compute or API tokens |
| **Emergent Behavior** | Rule-bound (e.g., greedy scavenger) | Nuanced conversation, deception, alliances |

---

## 3. Configuring Heuristic Agents ("Vibes")

Heuristic agents use behavioral archetypes ("vibes") that dictate priority order:

1. **`scavenger` / `explorer`**:
   - Prioritizes searching for `!` resources.
   - Follows `+` trails to discover resource hubs.
   - Collects immediately when on a resource tile.
2. **`social` / `philosopher`**:
   - Searches for other `@` agents within perception.
   - Emits speech when another agent is within 2 tiles.
   - Reads tile speech history and replies.
3. **`guardian` / `territorial`**:
   - Chooses a designated patrol zone (e.g. $(x_1, y_1)$ to $(x_2, y_2)$).
   - Warns trespassers via `chat` and blocks movement.
4. **`nomad`**:
   - Avoids existing trails (`+`) to chart unexplored territory (`.`).

---

## 4. Configuring & Tuning LLM Agents

LLM agents use a system prompt, personality string, and perception narrative.

### Personality Injection
In `src/agents/agent_llm.py`, the `--personality` flag alters how the model reasons:

```bash
# Example 1: The Greedy Merchant
python -m src.agents.agent_llm --name merchant \
  --personality "You are a shrewd trader. You hoard resources (!) and ask high prices in chat."

# Example 2: The Silent Hermit
python -m src.agents.agent_llm --name hermit \
  --personality "You distrust others. Avoid agents (@), seek secluded corners, speak only in riddles."

# Example 3: The Cartographer
python -m src.agents.agent_llm --name mapper \
  --personality "You want to map the world. Always move toward unvisited '.' cells and follow trails '+'."
```

---

## 5. "Training" & Refining Agents

To improve your agents' performance, you can tune them across 4 layers:

### Layer 1: Prompt & Few-Shot Tuning (In-Context Learning)
Inject high-reward decision examples directly into the prompt:

```json
[
  {
    "perception": "To your North, you see a resource (!). Your energy is 25.",
    "thought": "My energy is dangerously low and a resource is right above me. Moving North.",
    "action": "move",
    "direction": "north"
  },
  {
    "perception": "In your current tile, you see a resource (!).",
    "thought": "I am standing on top of a resource. I must collect it now.",
    "action": "collect"
  }
]
```

### Layer 2: Memory Buffer / Mental Map
Out of the box, agents have no persistent memory across turns. You can add a rolling memory buffer:
- **Visited Coordinates Tracker:** Keep a set `self.visited_tiles = set()` so the agent avoids pacing back and forth.
- **Social Graph:** Remember agents met by name and their last known messages.

### Layer 3: Policy Optimization via Telemetry
Underworld logs every action to [`logs/underworld.jsonl`](file:///Users/matheus/Code/side-projects/sao/logs/underworld.jsonl):
- Monitor **Survival Rate** (actions survived before hitting 0 energy).
- Monitor **Collection Efficiency** (resources gathered per 100 turns).
- Inspect thoughts to identify failure modes (e.g. running into walls `#` or missing nearby resources).

---

## 6. Declarative Agent Configurations (`configs/agents/`)

You can create declarative agent definitions in `configs/agents/`:

```json
{
  "agent_id": "scout_alpha",
  "type": "heuristic",
  "vibe": "explorer",
  "spawn_position": [5, 5],
  "action_delay": 1.0
}
```
Or for an LLM agent:
```json
{
  "agent_id": "oracle_gemini",
  "type": "llm",
  "backend": "ollama",
  "model": "llama3.2",
  "personality": "Mystic observer who reads tile histories and whispers prophecies.",
  "spawn_position": [10, 10],
  "action_delay": 2.0
}
```
