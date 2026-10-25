"""
Underworld - Agent Performance Benchmark
Benchmarks Random vs Heuristic vs Trained Q-Agent in controlled simulation episodes.
Zero LLM tokens required.
"""

import argparse
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from engine.logic import WorldEngine
from scripts.train import DEFAULT_SAVE_PATH, discretize_state


def run_benchmark_trial(agent_type: str, policy_path: Path, max_steps: int = 300) -> dict:
    world = WorldEngine(width=20, height=20)
    for _ in range(5):
        world.spawn_resource()

    agent_id = f"bench_{agent_type}"
    sx, sy = random.randint(2, 17), random.randint(2, 17)
    world.spawn_agent(agent_id, sx, sy)

    visited = {(sx, sy)}
    crystals = 0
    steps_survived = 0

    # If trained, load policy
    q_table = {}
    if agent_type == "trained" and policy_path.exists():
        import json
        with open(policy_path, encoding="utf-8") as f:
            q_table = json.load(f).get("q_table", {})

    for step in range(max_steps):
        agent_obj = world.agents[agent_id]
        if not agent_obj.is_active or agent_obj.energy <= 0:
            break

        steps_survived += 1
        pos = agent_obj.position.as_tuple()
        visited.add(pos)

        p = world.get_perception(agent_id, radius=2)

        # Decide action based on type
        if agent_type == "random":
            action = random.choice(["north", "south", "east", "west", "collect"])

        elif agent_type == "heuristic":
            # Scavenger heuristic
            if pos in world.resources:
                action = "collect"
            else:
                cells = p.get("cells", [])
                radius = 2
                found_res = None
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        r_idx, c_idx = dy + radius, dx + radius
                        if 0 <= r_idx < len(cells) and 0 <= c_idx < len(cells[r_idx]):
                            if cells[r_idx][c_idx].get("terrain") == "!":
                                found_res = (dx, dy)
                                break
                    if found_res:
                        break
                if found_res:
                    dx, dy = found_res
                    if abs(dy) >= abs(dx):
                        action = "north" if dy < 0 else "south"
                    else:
                        action = "east" if dx > 0 else "west"
                else:
                    action = random.choice(["north", "south", "east", "west"])

        elif agent_type == "trained":
            state_key = discretize_state(p, agent_id)
            vals = q_table.get(state_key)
            if pos in world.resources:
                action = "collect"
            elif vals:
                from scripts.train import ACTIONS
                action = ACTIONS[vals.index(max(vals))]
                if action == "collect" and pos not in world.resources:
                    action = random.choice(["north", "south", "east", "west"])
            else:
                action = random.choice(["north", "south", "east", "west"])

        # Execute
        if action == "collect":
            success, _ = world.collect(agent_id)
            if success:
                crystals += 1
        else:
            world.move_agent(agent_id, action)

        # Periodic resource spawning
        if step % 15 == 0 and len(world.resources) < 5:
            world.spawn_resource()

    return {
        "steps_survived": steps_survived,
        "crystals": crystals,
        "tiles_explored": len(visited),
        "exploration_pct": round((len(visited) / 400) * 100, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark agent architectures")
    parser.add_argument("--trials", type=int, default=30, help="Number of trials per agent")
    parser.add_argument("--max-steps", type=int, default=300, help="Max steps per trial")
    parser.add_argument("--policy", default=str(DEFAULT_SAVE_PATH), help="Path to trained policy JSON")
    args = parser.parse_args()

    policy_path = Path(args.policy)
    agent_types = ["random", "heuristic", "trained"]

    print("=" * 68)
    print(f"📊 BENCHMARKING AGENT POLICIES ({args.trials} trials, max {args.max_steps} steps)")
    print("=" * 68)

    results = {}

    for atype in agent_types:
        print(f"Testing {atype.upper()} agent...", end="", flush=True)
        t0 = time.time()
        trial_metrics = [run_benchmark_trial(atype, policy_path, args.max_steps) for _ in range(args.trials)]
        elapsed = time.time() - t0

        avg_steps = sum(m["steps_survived"] for m in trial_metrics) / args.trials
        avg_crystals = sum(m["crystals"] for m in trial_metrics) / args.trials
        avg_explored = sum(m["tiles_explored"] for m in trial_metrics) / args.trials
        avg_pct = sum(m["exploration_pct"] for m in trial_metrics) / args.trials

        results[atype] = {
            "avg_steps": avg_steps,
            "avg_crystals": avg_crystals,
            "avg_explored": avg_explored,
            "avg_pct": avg_pct,
            "time": elapsed,
        }
        print(f" done ({elapsed:0.2f}s)")

    print("\n" + "=" * 68)
    print(f"{'Agent Type':<16} | {'Avg Steps':<11} | {'Avg Crystals':<13} | {'Map Explored':<12}")
    print("-" * 68)
    for atype, data in results.items():
        print(f"{atype.capitalize():<16} | {data['avg_steps']:<11.1f} | {data['avg_crystals']:<13.2f} | {data['avg_pct']:<5.1f}% ({data['avg_explored']:0.0f} tiles)")
    print("=" * 68)


if __name__ == "__main__":
    main()
