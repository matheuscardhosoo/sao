"""
Underworld ASCII - Advanced LLM Brain
Perceive -> Think (LLM) -> Act loop with personality injection.
"""

import argparse
import json
import re
import sys
import time
from typing import Any

import requests

BASE_URL = "http://127.0.0.1:8000"

# LLM backends: OpenAI-compatible or Ollama
OPENAI_BASE = "https://api.openai.com/v1"
OLLAMA_BASE = "http://127.0.0.1:11434"

# Cardinal directions: (dx, dy) -> name
DIRECTIONS = {
    (0, -1): "North",
    (0, 1): "South",
    (1, 0): "East",
    (-1, 0): "West",
    (1, -1): "North-East",
    (-1, -1): "North-West",
    (1, 1): "South-East",
    (-1, 1): "South-West",
    (0, -2): "Far North",
    (0, 2): "Far South",
    (2, 0): "Far East",
    (-2, 0): "Far West",
    (-2, -1): "North-West (far)",
    (2, -1): "North-East (far)",
    (-2, 1): "South-West (far)",
    (2, 1): "South-East (far)",
    (-1, -2): "North-West (far)",
    (1, -2): "North-East (far)",
    (-1, 2): "South-West (far)",
    (1, 2): "South-East (far)",
    (-2, -2): "Far North-West",
    (2, -2): "Far North-East",
    (-2, 2): "Far South-West",
    (2, 2): "Far South-East",
}

SYSTEM_PROMPT = """You are an autonomous agent in a 2D ASCII world. You perceive your surroundings and choose one action per turn.

ACTIONS (respond with exactly one):
1. move - Move one cell. Provide "direction": "north" | "south" | "east" | "west"
2. talk - Speak to nearby agents. Provide "message": "<your speech>"
3. collect - Pick up a resource on your current cell. No extra fields.

RESPOND in valid JSON only, no other text:
{"thought": "<brief reasoning>", "action": "move"|"talk"|"collect", "direction": "<for move>"|null, "message": "<for talk>"|null}

Examples:
- Moving north: {"thought": "I'll explore north.", "action": "move", "direction": "north", "message": null}
- Speaking: {"thought": "I'll greet them.", "action": "talk", "direction": null, "message": "Hello!"}
- Collecting: {"thought": "I'll take this resource.", "action": "collect", "direction": null, "message": null}"""


def perceive(agent_id: str, radius: int = 2) -> dict | None:
    """Fetch perception from server."""
    try:
        r = requests.get(
            f"{BASE_URL}/perceive/{agent_id}",
            params={"radius": radius},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def act(
    agent_id: str,
    action: str,
    metadata: dict[str, Any],
) -> bool:
    """Send action to server. Returns True if request succeeded."""
    try:
        r = requests.post(
            f"{BASE_URL}/act",
            json={"agent_id": agent_id, "action": action, "metadata": metadata},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("success", False)
    except requests.RequestException:
        return False


def format_perception(perception: dict) -> str:
    """
    Format grid, history, and tiles into human-readable environmental description.
    Example: 'At your North, there is a trail of movement. At your East, another agent @ is standing.'
    """
    cells = perception.get("cells", [])
    radius = perception.get("radius", 2)
    agent_id = perception.get("agent_id", "you")

    parts: list[str] = []

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            row_idx = dy + radius
            col_idx = dx + radius
            if row_idx < 0 or row_idx >= len(cells):
                continue
            row = cells[row_idx]
            if col_idx < 0 or col_idx >= len(row):
                continue
            cell = row[col_idx]
            char = cell.get("char", ".")
            walk_count = cell.get("walk_count", 0)
            history = cell.get("history", [])

            dir_name = DIRECTIONS.get((dx, dy), f"({dx},{dy})")

            if char == "#":
                parts.append(f"At your {dir_name}, there is a wall.")
            elif char == "@":
                parts.append(f"At your {dir_name}, another agent @ is standing.")
            elif char == "!":
                parts.append(f"At your {dir_name}, there is a resource !")
            elif char == "+":
                parts.append(f"At your {dir_name}, there is a trail of movement.")
            elif char == ".":
                if walk_count > 0 or history:
                    trail_hint = " (traces of movement)" if walk_count > 0 else ""
                    hist_hint = f" Recent: {'; '.join(history[-2:])}." if history else ""
                    parts.append(f"At your {dir_name}, empty ground{trail_hint}.{hist_hint}")
                else:
                    parts.append(f"At your {dir_name}, empty ground.")
            else:
                parts.append(f"At your {dir_name}, there is '{char}'.")

    if not parts:
        return "You see nothing around you."
    return " ".join(parts)


def call_llm(
    system_prompt: str,
    user_content: str,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    backend: str = "openai",
) -> str | None:
    """Call LLM API. Supports OpenAI and Ollama."""
    if backend == "ollama":
        url = f"{OLLAMA_BASE}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        headers = {"Content-Type": "application/json"}
    else:
        url = f"{OPENAI_BASE}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or ''}",
        }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        if backend == "ollama":
            return data.get("message", {}).get("content", "")
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except requests.RequestException as e:
        print(f"[LLM Error] {e}", file=sys.stderr)
        return None


def parse_llm_response(raw: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response. Handles markdown code blocks."""
    raw = raw.strip()
    # Try to find JSON in code blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        raw = match.group(1).strip()
    # Or find {...}
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        raw = match.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def direction_to_dxdy(direction: str) -> tuple[int, int]:
    """Map direction string to (dx, dy)."""
    d = direction.lower().strip()
    m = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
    return m.get(d, (0, 0))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LLM-powered agent for Underworld ASCII"
    )
    parser.add_argument("--agent-id", required=True, help="Unique agent identifier")
    parser.add_argument(
        "--personality",
        default="",
        help="Personality prepended to system prompt (e.g. 'A cynical hermit')",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Seconds between turns",
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "ollama"],
        default="ollama",
        help="LLM backend",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Model name (e.g. llama3.2 for Ollama, gpt-4o-mini for OpenAI)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="OpenAI API key (or set OPENAI_API_KEY env)",
    )
    args = parser.parse_args()

    import os
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")

    # Build system prompt with personality
    system = SYSTEM_PROMPT
    if args.personality:
        system = f"{args.personality}. {system}"

    model = args.model or (
        "llama3.2" if args.backend == "ollama" else "gpt-4o-mini"
    )

    agent_id = args.agent_id

    while True:
        perception = perceive(agent_id)
        if perception is None:
            time.sleep(args.interval)
            continue

        env_text = format_perception(perception)
        user_content = f"Current perception:\n{env_text}\n\nChoose your action (JSON only):"

        raw = call_llm(
            system_prompt=system,
            user_content=user_content,
            api_key=api_key or None,
            model=model,
            backend=args.backend,
        )

        if not raw:
            time.sleep(args.interval)
            continue

        parsed = parse_llm_response(raw)
        if not parsed:
            print(f"[{agent_id}] Failed to parse LLM response", file=sys.stderr)
            time.sleep(args.interval)
            continue

        thought = parsed.get("thought", "")
        action = parsed.get("action", "move")
        if action not in ("move", "talk", "collect"):
            action = "move"
        direction = parsed.get("direction")
        message = parsed.get("message")

        # Print thought to local console
        print(f"[{agent_id}] 💭 {thought}")

        metadata: dict[str, Any] = {}
        if action == "move":
            dx, dy = direction_to_dxdy(direction or "north")
            metadata = {"dx": dx, "dy": dy}
        elif action == "talk":
            metadata = {"message": message or "..."}

        act(agent_id, action, metadata)
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    sys.exit(main())
