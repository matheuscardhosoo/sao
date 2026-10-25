"""
Unit tests for WorldEngine core simulation logic.
"""

import pytest

from engine.logic import (
    ENERGY_CHAT_COST,
    ENERGY_COLLECT_REWARD,
    ENERGY_MOVE_COST,
    TRAIL_THRESHOLD,
    WorldEngine,
)


@pytest.fixture
def engine():
    return WorldEngine(width=10, height=10)


def test_spawn_agent(engine):
    assert engine.spawn_agent("bot1", 5, 5, personality="Tester")
    assert "bot1" in engine.agents
    agent = engine.agents["bot1"]
    assert agent.position.x == 5
    assert agent.position.y == 5
    assert agent.energy == 100
    assert agent.is_active is True

    # Cannot spawn out of bounds
    assert not engine.spawn_agent("bot_oob", 10, 10)
    # Cannot spawn on occupied tile
    assert not engine.spawn_agent("bot2", 5, 5)


def test_move_agent_and_energy(engine):
    engine.spawn_agent("bot", 5, 5)
    agent = engine.agents["bot"]

    success, msg = engine.move_agent("bot", "north")
    assert success
    assert (agent.position.x, agent.position.y) == (5, 4)
    assert agent.energy == 100 - ENERGY_MOVE_COST

    # Check tile history on old and new tile
    old_tile = engine.grid[5][5]
    assert "bot left" in old_tile.history[-1]
    new_tile = engine.grid[4][5]
    assert "bot moved here" in new_tile.history[-1]
    assert new_tile.walk_count == 1


def test_trail_formation_and_decay(engine):
    engine.spawn_agent("bot", 2, 2)
    # Move back and forth to build walk count on (2, 3)
    tile_target = engine.grid[3][2]

    for _ in range(TRAIL_THRESHOLD + 1):
        engine.move_agent("bot", "south")
        engine.move_agent("bot", "north")

    assert tile_target.walk_count >= TRAIL_THRESHOLD
    assert tile_target.terrain == "+"

    # Test trail decay
    for _ in range(tile_target.walk_count + 1):
        engine.decay_trails()

    assert tile_target.walk_count == 0
    assert tile_target.terrain == "."


def test_agent_exhaustion(engine):
    engine.spawn_agent("bot", 1, 1)
    agent = engine.agents["bot"]
    agent.energy = 1  # 1 step left

    success, msg = engine.move_agent("bot", "east")
    assert success
    assert agent.energy == 0
    assert agent.is_active is False

    # Further move should fail due to exhaustion
    fail, fail_msg = engine.move_agent("bot", "east")
    assert not fail
    assert "exhausted" in fail_msg.lower()


def test_collect_resource(engine):
    engine.spawn_agent("bot", 4, 4)
    agent = engine.agents["bot"]
    agent.energy = 50

    # Place resource at (4, 4)
    engine.add_resource(4, 4)
    assert (4, 4) in engine.resources

    success, msg = engine.collect("bot")
    assert success
    assert (4, 4) not in engine.resources
    assert "energy_crystal" in agent.inventory
    assert agent.energy == min(100, 50 + ENERGY_COLLECT_REWARD)


def test_chat_and_tile_memory(engine):
    engine.spawn_agent("speaker", 5, 5)
    agent = engine.agents["speaker"]
    start_energy = agent.energy

    success, msg = engine.chat("speaker", "Hello Underworld!")
    assert success
    assert agent.energy == start_energy - ENERGY_CHAT_COST

    # Surrounding 3x3 tiles should remember the speech
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            tile = engine.grid[5 + dy][5 + dx]
            assert any("speaker: Hello Underworld!" in h for h in tile.history)


def test_get_perception(engine):
    engine.spawn_agent("scout", 3, 3)
    engine.add_resource(4, 3)

    p = engine.get_perception("scout", radius=2)
    assert p is not None
    assert p["agent_id"] == "scout"
    assert p["center"] == [3, 3]
    assert p["energy"] == 100
    assert p["is_active"] is True

    # Resource at (4,3) is dx=+1, dy=0 from (3,3)
    # Center in cells is index [radius][radius] = [2][2]
    # Resource cell is [2][3]
    cells = p["cells"]
    assert cells[2][3]["terrain"] == "!"
