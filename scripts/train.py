"""
Underworld - Offline Reinforcement Learning (Q-Learning) Trainer
Trains an agent policy with ZERO external API calls or LLM token costs.
Saves the learned Q-table to configs/policies/trained_q_agent.json.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

# Add src to pythonpath
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from engine.logic import WorldEngine

ACTIONS = ["north", "south", "east", "west", "collect", "chat"]
DEFAULT_SAVE_PATH = ROOT / "configs" / "policies" / "trained_q_agent.json"


def discretize_state(perception: dict, agent_id: str) -> str:
    """
    Convert raw local perception into a compact discrete state key.
    State components:
    - energy_bucket: 0 (<=25), 1 (26-50), 2 (51-75), 3 (>75)
    - res_dir: 0 (none), 1 (N), 2 (S), 3 (E), 4 (W), 5 (HERE)
    - agent_near: 0 (no), 1 (yes)
    - wall_n, wall_s, wall_e, wall_w: 0/1 (is out-of-bounds or impassable)
    """
    energy = perception.get("energy", 100)
    if energy <= 25:
        energy_b = 0
    elif energy <= 50:
        energy_b = 1
    elif energy <= 75:
        energy_b = 2
    else:
        energy_b = 3

    cells = perception.get("cells", [])
    radius = perception.get("radius", 2)
    center_cell = cells[radius][radius] if (0 <= radius < len(cells) and 0 <= radius < len(cells[radius])) else {}

    # Check if standing on resource
    if center_cell.get("terrain") == "!":
        res_dir = 5
    else:
        # Search for closest resource in radius
        closest_res = None
        closest_dist = 999
        agent_near = 0

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                r_idx = dy + radius
                c_idx = dx + radius
                if 0 <= r_idx < len(cells) and 0 <= c_idx < len(cells[r_idx]):
                    cell = cells[r_idx][c_idx]
                    t = cell.get("terrain", ".")
                    dist = abs(dx) + abs(dy)
                    if t == "!":
                        if dist < closest_dist:
                            closest_dist = dist
                            closest_res = (dx, dy)
                    elif t == "@" and dist <= 1:
                        agent_near = 1

        if closest_res is None:
            res_dir = 0
        else:
            dx, dy = closest_res
            # Cardinal bias
            if abs(dy) >= abs(dx):
                res_dir = 1 if dy < 0 else 2  # North or South
            else:
                res_dir = 3 if dx > 0 else 4  # East or West

    # Check wall bounds
    cx, cy = perception.get("center", [0, 0])
    wall_n = 1 if cy <= 0 else 0
    wall_s = 1 if cy >= 19 else 0
    wall_w = 1 if cx <= 0 else 0
    wall_e = 1 if cx >= 19 else 0

    return f"E{energy_b}_R{res_dir}_A{agent_near}_W{wall_n}{wall_s}{wall_e}{wall_w}"


class QLearningAgent:
    def __init__(self, alpha: float = 0.2, gamma: float = 0.95, epsilon: float = 1.0, epsilon_decay: float = 0.9992, epsilon_min: float = 0.05):
        self.q_table: dict[str, list[float]] = {}
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

    def get_q_values(self, state: str) -> list[float]:
        if state not in self.q_table:
            # Initialize with slight optimistic prior for collect (action index 4)
            self.q_table[state] = [0.0, 0.0, 0.0, 0.0, 5.0, 0.0]
        return self.q_table[state]

    def choose_action(self, state: str) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, len(ACTIONS) - 1)
        q_vals = self.get_q_values(state)
        max_q = max(q_vals)
        best_actions = [i for i, q in enumerate(q_vals) if q == max_q]
        return random.choice(best_actions)

    def learn(self, state: str, action: int, reward: float, next_state: str, done: bool):
        q_vals = self.get_q_values(state)
        current_q = q_vals[action]
        if done:
            target = reward
        else:
            next_max_q = max(self.get_q_values(next_state))
            target = reward + self.gamma * next_max_q
        self.q_table[state][action] = current_q + self.alpha * (target - current_q)

    def decay_epsilon(self):
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay


def train(episodes: int = 3000, max_steps: int = 250, save_path: Path = DEFAULT_SAVE_PATH) -> dict:
    agent = QLearningAgent()
    print(f"🧠 Training Q-Learning Policy for {episodes} episodes (max {max_steps} steps/ep)...")
    start_time = time.time()

    crystals_collected_total = 0
    episodes_survived_full = 0

    history_window = []

    for ep in range(1, episodes + 1):
        # Create fresh isolated world instance
        world = WorldEngine(width=20, height=20)
        # Spawn initial resources
        for _ in range(6):
            world.spawn_resource()

        agent_id = "trainee"
        sx, sy = random.randint(2, 17), random.randint(2, 17)
        world.spawn_agent(agent_id, sx, sy)

        visited = {(sx, sy)}
        ep_reward = 0
        ep_crystals = 0

        p = world.get_perception(agent_id, radius=2)
        state = discretize_state(p, agent_id)

        for step in range(max_steps):
            action_idx = agent.choose_action(state)
            action_name = ACTIONS[action_idx]

            reward = 0.0
            done = False

            if action_name == "collect":
                success, _ = world.collect(agent_id)
                if success:
                    reward = 120.0
                    ep_crystals += 1
                    crystals_collected_total += 1
                else:
                    reward = -12.0  # Wasted step trying to collect empty tile

            elif action_name == "chat":
                success, _ = world.chat(agent_id, "Training...")
                reward = -2.0

            else:  # move action
                success, _ = world.move_agent(agent_id, action_name)
                if not success:
                    reward = -15.0  # Invalid move / bumped into wall or edge
                else:
                    new_pos = world.agents[agent_id].position.as_tuple()
                    if new_pos not in visited:
                        visited.add(new_pos)
                        reward = 4.0  # Reward exploration
                    else:
                        reward = -0.5  # Slight penalty for repeating visited tiles

            # Check agent status
            agent_obj = world.agents[agent_id]
            if not agent_obj.is_active or agent_obj.energy <= 0:
                reward = -80.0
                done = True

            # Respawn resources periodically
            if step % 15 == 0 and len(world.resources) < 5:
                world.spawn_resource()

            next_p = world.get_perception(agent_id, radius=2) if not done else None
            next_state = discretize_state(next_p, agent_id) if not done else state

            agent.learn(state, action_idx, reward, next_state, done)
            state = next_state
            ep_reward += reward

            if done:
                break

        if not done:
            episodes_survived_full += 1

        agent.decay_epsilon()
        history_window.append((ep_crystals, ep_reward, step + 1))

        if ep % 500 == 0 or ep == episodes:
            recent = history_window[-200:]
            avg_crystals = sum(c for c, _, _ in recent) / len(recent)
            avg_steps = sum(s for _, _, s in recent) / len(recent)
            print(f"  Episode {ep:4d}/{episodes} | Avg Surv Steps: {avg_steps:5.1f} | Avg Crystals/Ep: {avg_crystals:4.2f} | Epsilon: {agent.epsilon:0.3f}")

    elapsed = time.time() - start_time
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Save policy
    policy_data = {
        "metadata": {
            "algorithm": "Q-Learning",
            "episodes_trained": episodes,
            "max_steps": max_steps,
            "total_crystals": crystals_collected_total,
            "training_time_sec": round(elapsed, 2),
            "state_space_size": len(agent.q_table),
            "actions": ACTIONS,
        },
        "q_table": agent.q_table,
    }

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(policy_data, f, indent=2)

    print(f"\n✅ Training complete in {elapsed:0.2f}s!")
    print(f"💾 Policy saved to: {save_path} ({len(agent.q_table)} states learned)")
    return policy_data


def main():
    parser = argparse.ArgumentParser(description="Train autonomous Q-Learning agent offline")
    parser.add_argument("--episodes", type=int, default=3000, help="Number of training episodes")
    parser.add_argument("--max-steps", type=int, default=200, help="Max steps per episode")
    parser.add_argument("--save-path", type=str, default=str(DEFAULT_SAVE_PATH), help="Path to save learned policy JSON")
    args = parser.parse_args()

    train(episodes=args.episodes, max_steps=args.max_steps, save_path=Path(args.save_path))


if __name__ == "__main__":
    main()
