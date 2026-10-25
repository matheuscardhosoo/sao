"""
Underworld - Advanced LLM Brain
Perceive -> Contextualize -> Think & Act loop with personality injection.
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Any

import requests

# Direction mapping for narrative: (dx, dy) -> cardinal name
DIRECTION_NAMES: dict[tuple[int, int], str] = {
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

# ANSI color for thought output (cyan/bright blue)
THOUGHT_COLOR = "\033[96m"  # Bright cyan
RESET_COLOR = "\033[0m"

SYSTEM_PROMPT = (
    "You are a sentient digital entity in the Underworld. You are represented by the symbol @. "
    "Rules:\n"
    "1. You need resources (!) to gain energy.\n"
    "2. You can see traces (+) of other entities.\n"
    "3. You can read the 'History' of the tiles you step on. This is your only way to know the past.\n"
    "4. You can leave messages for others.\n\n"
    "Your personality: {personality}.\n\n"
    'Format your response as valid JSON: {{ "thought": "your reasoning", '
    '"action": "move|chat|collect", "direction": "up|down|left|right|none", "message": "your text" }}'
)

# Map LLM direction format to API format
DIRECTION_MAP = {"up": "north", "down": "south", "left": "west", "right": "east"}


def perceive(base_url: str, name: str, radius: int = 2) -> dict | None:
    """Fetch 5x5 perception from GET /agent/perceive/{name}."""
    try:
        r = requests.get(
            f"{base_url}/agent/perceive/{name}",
            params={"radius": radius},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def act(base_url: str, name: str, action: str, metadata: dict[str, Any]) -> dict | None:
    """Send action to POST /agent/action. Returns response or None."""
    try:
        r = requests.post(
            f"{base_url}/agent/action",
            json={"agent_id": name, "action": action, "metadata": metadata},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def contextualize(perception: dict) -> str:
    """
    Convert JSON perception into a narrative string.
    E.g., 'To your North, there is a trail (+). To your South, you see a resource (!)...'
    """
    cells = perception.get("cells", [])
    radius = perception.get("radius", 2)

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
            terrain = cell.get("terrain", ".")
            history = cell.get("history", [])

            dir_name = DIRECTION_NAMES.get((dx, dy), f"({dx},{dy})")

            if terrain == "#":
                parts.append(f"To your {dir_name}, there is a wall.")
            elif terrain == "@":
                parts.append(f"To your {dir_name}, another agent is standing.")
            elif terrain == "!":
                parts.append(f"To your {dir_name}, you see a resource (!).")
            elif terrain == "+":
                parts.append(f"To your {dir_name}, there is a trail (+).")
            elif terrain == ".":
                if history:
                    hist_str = "; ".join(history[-2:])
                    parts.append(f"To your {dir_name}, empty ground. History: \"{hist_str}\".")
                else:
                    parts.append(f"To your {dir_name}, empty ground.")
            else:
                parts.append(f"To your {dir_name}, you see '{terrain}'.")

    # Current tile (center) history
    if cells and radius < len(cells):
        center_row = cells[radius]
        if radius < len(center_row):
            center_cell = center_row[radius]
            hist = center_cell.get("history", [])
            if hist:
                parts.insert(0, f"In your current tile, the history says: \"{'; '.join(hist[-3:])}\".")

    return " ".join(parts) if parts else "You see nothing around you."


def call_llm(
    narrative: str,
    personality: str,
    api_key: str | None,
    backend: str = "ollama",
    model: str = "llama3.2",
) -> str | None:
    """Send narrative + personality to LLM. Returns raw response text."""
    system = SYSTEM_PROMPT.format(personality=personality or "Neutral.")
    user_content = f"Your perception:\n{narrative}\n\nChoose your action (JSON only):"

    if backend == "ollama":
        url = "http://127.0.0.1:11434/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        headers = {"Content-Type": "application/json"}
    else:
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system},
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
    """Extract JSON from LLM response."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        raw = match.group(1).strip()
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        raw = match.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def print_thought(name: str, thought: str) -> None:
    """Print agent's thought in distinct color."""
    print(f"{THOUGHT_COLOR}[{name}] 💭 {thought}{RESET_COLOR}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Underworld LLM-powered agent")
    parser.add_argument("--name", required=True, help="Agent name (must be spawned first)")
    parser.add_argument(
        "--personality",
        default="",
        help="Personality injected into system prompt (e.g. 'A cynical hermit')",
    )
    parser.add_argument(
        "--api_key",
        default="",
        help="OpenAI API key (or set OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--api_url",
        default=os.environ.get("UNDERWORLD_API_URL", "http://127.0.0.1:7788"),
        help="Underworld API base URL",
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
        help="Model name (llama3.2 for Ollama, gpt-4o-mini for OpenAI)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between turns (default 1.5)",
    )
    args = parser.parse_args()

    name = args.name
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    model = args.model or ("llama3.2" if args.backend == "ollama" else "gpt-4o-mini")
    base_url = args.api_url.rstrip("/")

    while True:
        perception = perceive(base_url, name, radius=2)
        if perception is None:
            time.sleep(args.delay)
            continue

        narrative = contextualize(perception)

        raw = call_llm(
            narrative=narrative,
            personality=args.personality,
            api_key=api_key or None,
            backend=args.backend,
            model=model,
        )

        if not raw:
            time.sleep(args.delay)
            continue

        parsed = parse_llm_response(raw)
        if not parsed:
            print(f"[{name}] Failed to parse LLM response", file=sys.stderr)
            time.sleep(args.delay)
            continue

        thought = parsed.get("thought", "")
        action = parsed.get("action", "move")
        direction = parsed.get("direction")
        message = parsed.get("message")

        print_thought(name, thought)

        if action == "move":
            raw_dir = (direction or "none").lower()
            api_dir = DIRECTION_MAP.get(
                raw_dir,
                raw_dir if raw_dir in ("north", "south", "east", "west") else "north",
            )
            if raw_dir != "none":
                act(base_url, name, "move", {"direction": api_dir})
        elif action in ("talk", "chat"):
            act(base_url, name, "chat", {"message": message or "..."})
        elif action == "collect":
            act(base_url, name, "collect", {})

        time.sleep(args.delay)

    return 0


if __name__ == "__main__":
    sys.exit(main())
