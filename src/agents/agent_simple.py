"""
Underworld - Simple Autonomous Heuristic Agent
Perceive -> Decide -> Act loop with configurable Vibe.
Zero external dependencies required (100% offline).
"""

import argparse
import os
import random
import time
from typing import Any, Literal

import requests

VIBES = ("explorer", "scavenger", "aggressive", "social", "guardian")
DEFAULT_API_URL = os.environ.get("UNDERWORLD_API_URL", "http://127.0.0.1:7788")

# Direction vectors to cardinal names
DELTA_TO_DIRECTION: dict[tuple[int, int], str] = {
    (0, -1): "north",
    (0, 1): "south",
    (1, 0): "east",
    (-1, 0): "west",
}

# ANSI colors for agent actions
COLOR_MAP = {
    "explorer": "\033[94m",    # Blue
    "scavenger": "\033[93m",   # Yellow
    "social": "\033[92m",      # Green
    "aggressive": "\033[91m",  # Red
    "guardian": "\033[95m",    # Magenta
}
RESET_COLOR = "\033[0m"


def perceive(base_url: str, agent_id: str, radius: int = 2) -> dict[str, Any] | None:
    """Fetch perception from /agent/perceive/{agent_id}."""
    try:
        r = requests.get(
            f"{base_url}/agent/perceive/{agent_id}",
            params={"radius": radius},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def act(
    base_url: str,
    agent_id: str,
    action: Literal["move", "chat", "collect"],
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    """Send action to /agent/action."""
    try:
        r = requests.post(
            f"{base_url}/agent/action",
            json={"agent_id": agent_id, "action": action, "metadata": metadata},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def decide(
    agent_id: str,
    perception: dict[str, Any],
    vibe: str,
    spawn_pos: tuple[int, int] | None = None,
) -> tuple[Literal["move", "chat", "collect"], dict[str, Any], str]:
    """
    Decide action based on perception and vibe.
    Returns (action, metadata, thought_summary).
    """
    cells = perception.get("cells", [])
    center = perception.get("center", [0, 0])
    cx, cy = center[0], center[1]
    radius = perception.get("radius", 2)

    # Check if currently standing on a resource
    if 0 <= radius < len(cells) and 0 <= radius < len(cells[radius]):
        center_cell = cells[radius][radius]
        if center_cell.get("terrain") == "!":
            return "collect", {}, "Standing directly on a resource! Collecting."

    # Scan perception grid for nearest resource (!) and other agent (@)
    nearest_resource: tuple[int, int, int] | None = None  # (dx, dy, manhattan_dist)
    nearest_agent: tuple[int, int, int] | None = None
    open_trails: list[tuple[int, int]] = []

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            row_idx = dy + radius
            col_idx = dx + radius
            if not (0 <= row_idx < len(cells) and 0 <= col_idx < len(cells[row_idx])):
                continue
            cell = cells[row_idx][col_idx]
            terrain = cell.get("terrain", ".")
            dist = abs(dx) + abs(dy)

            if terrain == "!":
                if nearest_resource is None or dist < nearest_resource[2]:
                    nearest_resource = (dx, dy, dist)
            elif terrain == "@":
                if nearest_agent is None or dist < nearest_agent[2]:
                    nearest_agent = (dx, dy, dist)
            elif terrain == "+":
                open_trails.append((dx, dy))

    # Helper for 1-step move in cardinal directions
    def step_towards(target_dx: int, target_dy: int) -> str:
        candidates = []
        if target_dx > 0:
            candidates.append("east")
        elif target_dx < 0:
            candidates.append("west")
        if target_dy > 0:
            candidates.append("south")
        elif target_dy < 0:
            candidates.append("north")
        return random.choice(candidates) if candidates else random.choice(["north", "south", "east", "west"])

    # 1. SCAVENGER / EXPLORER VIBE
    if vibe in ("scavenger", "explorer"):
        if nearest_resource is not None:
            dx, dy, dist = nearest_resource
            direction = step_towards(dx, dy)
            return "move", {"direction": direction}, f"Spotted resource {dist} steps away, moving {direction}."
        if open_trails and random.random() < 0.6:
            tdx, tdy = random.choice(open_trails)
            direction = step_towards(tdx, tdy)
            return "move", {"direction": direction}, f"Following fresh trail toward {direction}."
        direction = random.choice(["north", "south", "east", "west"])
        return "move", {"direction": direction}, f"Scouting area toward {direction}."

    # 2. SOCIAL VIBE
    if vibe == "social":
        if nearest_agent is not None:
            dx, dy, dist = nearest_agent
            if dist <= 2:
                phrases = [
                    "Greetings fellow wanderer!",
                    "Did you discover any resources nearby?",
                    "Peace be with you in the Underworld.",
                    "The trails are bustling today.",
                ]
                msg = random.choice(phrases)
                return "chat", {"message": msg}, f"Greeting nearby agent: '{msg}'"
            direction = step_towards(dx, dy)
            return "move", {"direction": direction}, f"Approaching agent {dist} steps away."
        if nearest_resource is not None:
            direction = step_towards(nearest_resource[0], nearest_resource[1])
            return "move", {"direction": direction}, f"Moving toward resource at {direction}."
        direction = random.choice(["north", "south", "east", "west"])
        return "move", {"direction": direction}, f"Wandering socially toward {direction}."

    # 3. AGGRESSIVE VIBE
    if vibe == "aggressive":
        if nearest_agent is not None and random.random() < 0.7:
            dx, dy, dist = nearest_agent
            if dist <= 1:
                return "chat", {"message": "Stand down! This territory belongs to me."}, "Warning agent to step back."
            direction = step_towards(dx, dy)
            return "move", {"direction": direction}, f"Hunting nearby agent at {direction}."
        if nearest_resource is not None:
            direction = step_towards(nearest_resource[0], nearest_resource[1])
            return "move", {"direction": direction}, f"Seizing resource at {direction}."
        direction = random.choice(["north", "south", "east", "west"])
        return "move", {"direction": direction}, f"Patrolling aggressively toward {direction}."

    # 4. GUARDIAN VIBE
    if vibe == "guardian":
        if nearest_agent is not None:
            dx, dy, dist = nearest_agent
            if dist <= 2:
                return "chat", {"message": "You are approaching a restricted zone. Turn back!"}, "Issuing security warning."
        # If far from spawn position, head back
        if spawn_pos is not None:
            sx, sy = spawn_pos
            pdist = abs(cx - sx) + abs(cy - sy)
            if pdist > 3:
                direction = step_towards(sx - cx, sy - cy)
                return "move", {"direction": direction}, f"Returning to guard post ({sx},{sy})."
        direction = random.choice(["north", "south", "east", "west"])
        return "move", {"direction": direction}, f"Patrolling perimeter toward {direction}."

    # Default move
    direction = random.choice(["north", "south", "east", "west"])
    return "move", {"direction": direction}, f"Moving {direction}."


def run_agent(
    agent_id: str,
    vibe: str = "explorer",
    api_url: str = DEFAULT_API_URL,
    interval: float = 1.0,
) -> None:
    """Main execution loop for heuristic agent."""
    base_url = api_url.rstrip("/")
    color = COLOR_MAP.get(vibe, "\033[97m")
    print(f"{color}[{agent_id}] Initialized with vibe: {vibe} (API: {base_url}){RESET_COLOR}")

    spawn_pos: tuple[int, int] | None = None

    while True:
        perception = perceive(base_url, agent_id, radius=2)
        if perception is None:
            time.sleep(interval)
            continue

        if spawn_pos is None and "center" in perception:
            c = perception["center"]
            spawn_pos = (c[0], c[1])

        action, metadata, thought = decide(agent_id, perception, vibe, spawn_pos)
        print(f"{color}[{agent_id}] 🧠 {thought}{RESET_COLOR}")

        act(base_url, agent_id, action, metadata)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Underworld Heuristic Autonomous Agent")
    parser.add_argument("--agent-id", required=True, help="Unique agent identifier")
    parser.add_argument("--vibe", choices=VIBES, default="explorer", help="Behavioral archetype")
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Underworld API base URL (default: http://127.0.0.1:7788)",
    )
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between act cycles")
    args = parser.parse_args()

    try:
        run_agent(
            agent_id=args.agent_id,
            vibe=args.vibe,
            api_url=args.api_url,
            interval=args.interval,
        )
    except KeyboardInterrupt:
        print(f"\n[{args.agent_id}] Stopped.")


if __name__ == "__main__":
    main()
