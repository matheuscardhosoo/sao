"""
Underworld ASCII - Simple Autonomous Agent
Perceive -> Decide -> Act loop with configurable Vibe.
"""

import argparse
import random
import sys
import time
from typing import Literal

import requests

VIBES: tuple[str, ...] = ("explorer", "aggressive", "social")
BASE_URL = "http://127.0.0.1:8000"


def perceive(agent_id: str, radius: int = 2) -> dict | None:
    """Fetch 5x5 (radius=2) perception from server."""
    try:
        r = requests.get(f"{BASE_URL}/perceive/{agent_id}", params={"radius": radius}, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def act(agent_id: str, action: Literal["move", "talk", "collect"], metadata: dict) -> bool:
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


def decide(
    agent_id: str,
    perception: dict,
    vibe: str,
) -> tuple[Literal["move", "talk", "collect"], dict]:
    """
    Simple heuristic decision logic based on Vibe.
    Returns (action, metadata).
    """
    cells = perception.get("cells", [])
    center = perception.get("center", [0, 0])
    cx, cy = center[0], center[1]
    radius = perception.get("radius", 2)

    # Find nearest resource (!) and nearest other agent (@)
    nearest_resource: tuple[int, int, int] | None = None  # (dx, dy, dist)
    nearest_agent: tuple[int, int, int] | None = None

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            row = cells[dy + radius] if dy + radius < len(cells) else []
            cell = row[dx + radius] if dx + radius < len(row) else {}
            char = cell.get("char", ".")
            dist = abs(dx) + abs(dy)
            if char == "!":
                if nearest_resource is None or dist < nearest_resource[2]:
                    nearest_resource = (dx, dy, dist)
            if char == "@":
                # Could be self at center - we check neighbors, so this is another agent
                if nearest_agent is None or dist < nearest_agent[2]:
                    nearest_agent = (dx, dy, dist)

    # TODO: Integrate LLM API here
    # Replace heuristic logic with: prompt = build_prompt(perception, vibe); response = llm(prompt); action = parse(response)

    if vibe == "explorer":
        if nearest_resource is not None:
            dx, dy, _ = nearest_resource
            # Move one step toward resource
            sdx = 1 if dx > 0 else (-1 if dx < 0 else 0)
            sdy = 1 if dy > 0 else (-1 if dy < 0 else 0)
            return "move", {"dx": sdx, "dy": sdy}
        # Random exploration
        moves = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        dx, dy = random.choice(moves)
        return "move", {"dx": dx, "dy": dy}

    if vibe == "aggressive":
        if nearest_resource is not None:
            dx, dy, _ = nearest_resource
            sdx = 1 if dx > 0 else (-1 if dx < 0 else 0)
            sdy = 1 if dy > 0 else (-1 if dy < 0 else 0)
            return "move", {"dx": sdx, "dy": sdy}
        if nearest_agent is not None and random.random() < 0.5:
            dx, dy, _ = nearest_agent
            sdx = 1 if dx > 0 else (-1 if dx < 0 else 0)
            sdy = 1 if dy > 0 else (-1 if dy < 0 else 0)
            return "move", {"dx": sdx, "dy": sdy}
        moves = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        dx, dy = random.choice(moves)
        return "move", {"dx": dx, "dy": dy}

    if vibe == "social":
        if nearest_agent is not None and random.random() < 0.6:
            messages = [
                "Hey there!",
                "Found anything interesting?",
                "I sense a presence nearby.",
                "Hello, traveler.",
                "Care to chat?",
            ]
            return "talk", {"message": random.choice(messages)}
        if nearest_resource is not None:
            dx, dy, _ = nearest_resource
            if nearest_resource[2] == 1:
                return "collect", {}
            sdx = 1 if dx > 0 else (-1 if dx < 0 else 0)
            sdy = 1 if dy > 0 else (-1 if dy < 0 else 0)
            return "move", {"dx": sdx, "dy": sdy}
        moves = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        dx, dy = random.choice(moves)
        return "move", {"dx": dx, "dy": dy}

    # Default: explorer-like
    moves = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    dx, dy = random.choice(moves)
    return "move", {"dx": dx, "dy": dy}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-id", required=True, help="Unique agent identifier")
    parser.add_argument("--vibe", choices=VIBES, default="explorer", help="Agent personality")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between act cycles")
    args = parser.parse_args()

    agent_id = args.agent_id
    vibe: str = args.vibe
    interval = args.interval

    while True:
        perception = perceive(agent_id)
        if perception is None:
            time.sleep(interval)
            continue

        action, metadata = decide(agent_id, perception, vibe)
        act(agent_id, action, metadata)
        time.sleep(interval)


if __name__ == "__main__":
    main()
