"""
Unit tests for Q-Learning training loop and trained agent decision making.
"""

from pathlib import Path
from engine.logic import WorldEngine
from scripts.train import discretize_state, train
from agents.agent_trained import TrainedAgent


def test_discretize_state():
    world = WorldEngine(width=20, height=20)
    world.spawn_agent("bot", 5, 5)
    world.add_resource(5, 4)  # Resource 1 step north
    p = world.get_perception("bot", radius=2)

    key = discretize_state(p, "bot")
    assert key.startswith("E3_R1")  # Full energy (E3), Resource North (R1)


def test_quick_training_run(tmp_path: Path):
    policy_file = tmp_path / "test_policy.json"
    result = train(episodes=50, max_steps=30, save_path=policy_file)
    assert policy_file.exists()
    assert "q_table" in result
    assert result["metadata"]["episodes_trained"] == 50


def test_trained_agent_decision(tmp_path: Path):
    policy_file = tmp_path / "test_policy.json"
    train(episodes=20, max_steps=20, save_path=policy_file)

    agent = TrainedAgent(agent_id="test_oracle", policy_path=policy_file)
    assert len(agent.q_table) > 0

    mock_perception = {
        "center": [5, 5],
        "energy": 90,
        "radius": 2,
        "cells": [
            [{"terrain": "."} for _ in range(5)] for _ in range(5)
        ]
    }
    action, metadata, thought = agent.decide(mock_perception)
    assert action in ("move", "chat", "collect")
    assert isinstance(thought, str)
