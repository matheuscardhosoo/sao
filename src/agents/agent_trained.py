"""
Underworld - Trained Policy Autonomous Agent
Executes learned Q-learning policy with spatial memory and frontier exploration.
Requires ZERO LLM tokens; executes instantly with microsecond latency.
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Literal

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.train import ACTIONS, DEFAULT_SAVE_PATH, discretize_state

DEFAULT_API_URL = os.environ.get("UNDERWORLD_API_URL", "http://127.0.0.1:7788")

COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
RESET_COLOR = "\033[0m"


class TrainedAgent:
    def __init__(self, agent_id: str, policy_path: Path = DEFAULT_SAVE_PATH, api_url: str = DEFAULT_API_URL):
        self.agent_id = agent_id
        self.api_url = api_url.rstrip("/")
        self.policy_path = policy_path
        self.q_table: dict[str, list[float]] = {}
        self.visited_tiles: set[tuple[int, int]] = set()
        self.load_policy()

    def load_policy(self) -> None:
        if self.policy_path.exists():
            try:
                with open(self.policy_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.q_table = data.get("q_table", {})
                print(f"{COLOR_GREEN}[{self.agent_id}] Loaded trained policy from {self.policy_path.name} ({len(self.q_table)} states){RESET_COLOR}")
            except Exception as e:
                print(f"{COLOR_YELLOW}[{self.agent_id}] Warning loading policy: {e}. Falling back to dynamic policy.{RESET_COLOR}")
        else:
            print(f"{COLOR_YELLOW}[{self.agent_id}] Policy {self.policy_path} not found. Running with baseline heuristic fallback.{RESET_COLOR}")

    def perceive(self, radius: int = 2) -> dict[str, Any] | None:
        try:
            r = requests.get(
                f"{self.api_url}/agent/perceive/{self.agent_id}",
                params={"radius": radius},
                timeout=4,
            )
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        return None

    def act(self, action: Literal["move", "chat", "collect"], metadata: dict[str, Any]) -> dict[str, Any] | None:
        try:
            r = requests.post(
                f"{self.api_url}/agent/action",
                json={"agent_id": self.agent_id, "action": action, "metadata": metadata},
                timeout=4,
            )
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        return None

    def decide(self, perception: dict[str, Any]) -> tuple[Literal["move", "chat", "collect"], dict[str, Any], str]:
        cx, cy = perception.get("center", [0, 0])
        self.visited_tiles.add((cx, cy))
        energy = perception.get("energy", 100)

        # 1. State lookup in learned Q-table
        state_key = discretize_state(perception, self.agent_id)
        learned_vals = self.q_table.get(state_key)

        # 2. Priority check: Standing on crystal -> Collect immediately!
        cells = perception.get("cells", [])
        radius = perception.get("radius", 2)
        if 0 <= radius < len(cells) and 0 <= radius < len(cells[radius]):
            center_cell = cells[radius][radius]
            if center_cell.get("terrain") == "!":
                return "collect", {}, "Standing directly on energy crystal! Harvesting +40 energy."

        action_name = None
        thought = ""

        if learned_vals:
            max_q = max(learned_vals)
            best_idx = learned_vals.index(max_q)
            candidate_action = ACTIONS[best_idx]
            if max_q > 0.5:
                action_name = candidate_action
                thought = f"State {state_key} matched policy -> Chose '{action_name}' (Q-value: {max_q:0.2f})"

        # 3. Hybrid fallback if state is novel or learned action is ambiguous
        if not action_name or action_name == "collect":
            # Search perception for visible crystal
            closest_res = None
            closest_dist = 999
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    r_idx, c_idx = dy + radius, dx + radius
                    if 0 <= r_idx < len(cells) and 0 <= c_idx < len(cells[r_idx]):
                        if cells[r_idx][c_idx].get("terrain") == "!":
                            d = abs(dx) + abs(dy)
                            if d < closest_dist:
                                closest_dist = d
                                closest_res = (dx, dy)

            if closest_res:
                dx, dy = closest_res
                if abs(dy) >= abs(dx):
                    action_name = "north" if dy < 0 else "south"
                else:
                    action_name = "east" if dx > 0 else "west"
                thought = f"Visual override: Detected crystal {closest_dist} steps away -> Advancing {action_name}."
            else:
                # Frontier exploration: pick move toward unvisited coordinate
                candidates = []
                for cardinal, (dx, dy) in [("north", (0, -1)), ("south", (0, 1)), ("east", (1, 0)), ("west", (-1, 0))]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < 20 and 0 <= ny < 20:
                        score = 10 if (nx, ny) not in self.visited_tiles else 1
                        candidates.append((score, cardinal))
                candidates.sort(key=lambda c: c[0] + random.random(), reverse=True)
                action_name = candidates[0][1] if candidates else "north"
                thought = f"Frontier exploration -> Scouting unvisited frontier {action_name}."

        # Map to action dispatch
        if action_name in ("north", "south", "east", "west"):
            return "move", {"direction": action_name}, thought
        elif action_name == "collect":
            return "collect", {}, thought
        elif action_name == "chat":
            return "chat", {"message": f"Energy status: {energy}% | Mapping Underworld."}, thought
        return "move", {"direction": "north"}, thought

    def step(self) -> bool:
        perception = self.perceive(radius=2)
        if not perception:
            return False

        energy = perception.get("energy", 100)
        is_active = perception.get("is_active", True)
        if not is_active or energy <= 0:
            print(f"{COLOR_RED}[{self.agent_id}] 💀 Agent has exhausted energy.{RESET_COLOR}")
            return False

        action, metadata, thought = self.decide(perception)
        color = COLOR_CYAN if "Visual" in thought or "Harvesting" in thought else COLOR_GREEN
        print(f"{color}[{self.agent_id}] ⚡ [E: {energy:3d}] {thought}{RESET_COLOR}")

        self.act(action, metadata)
        return True

    def run(self, interval: float = 0.8) -> None:
        print(f"{COLOR_CYAN}🚀 [{self.agent_id}] Initialized trained agent loop (Interval: {interval}s)...{RESET_COLOR}")
        while True:
            alive = self.step()
            if not alive:
                time.sleep(2.0)
                continue
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Run trained reinforcement learning agent")
    parser.add_argument("--agent-id", default="trained_oracle", help="Agent identifier")
    parser.add_argument("--policy", default=str(DEFAULT_SAVE_PATH), help="Path to policy JSON")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Underworld API URL")
    parser.add_argument("--interval", type=float, default=0.8, help="Step interval in seconds")
    args = parser.parse_args()

    agent = TrainedAgent(agent_id=args.agent_id, policy_path=Path(args.policy), api_url=args.api_url)
    try:
        agent.run(interval=args.interval)
    except KeyboardInterrupt:
        print(f"\n[{args.agent_id}] Stopped.")


if __name__ == "__main__":
    main()
