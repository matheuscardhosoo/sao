"""
API Integration tests using FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_dashboard(client):
    r = client.get("/api/info")
    assert r.status_code == 200
    assert r.json()["name"] == "Underworld ASCII API"

    r_dash = client.get("/dashboard")
    assert r_dash.status_code == 200
    assert "Underworld" in r_dash.text


def test_world_state(client):
    r = client.get("/world/state")
    assert r.status_code == 200
    data = r.json()
    assert "grid" in data
    assert "agents" in data
    assert "agent_details" in data
    assert "event_log" in data


def test_spawn_and_action_flow(client):
    # 1. Spawn agent
    r_spawn = client.post("/spawn", json={"agent_id": "api_bot", "x": 8, "y": 8, "personality": "API Tester"})
    assert r_spawn.status_code == 200
    assert r_spawn.json()["agent_id"] == "api_bot"

    # 2. Perceive
    r_perc = client.get("/agent/perceive/api_bot?radius=2")
    assert r_perc.status_code == 200
    assert r_perc.json()["agent_id"] == "api_bot"
    assert r_perc.json()["energy"] == 100

    # 3. Move action
    r_move = client.post("/agent/action", json={
        "agent_id": "api_bot",
        "action": "move",
        "metadata": {"direction": "north"},
    })
    assert r_move.status_code == 200
    assert r_move.json()["success"] is True

    # 4. Chat action (testing both "chat" and "talk" alias)
    r_talk = client.post("/agent/action", json={
        "agent_id": "api_bot",
        "action": "talk",
        "metadata": {"message": "Talking test"},
    })
    assert r_talk.status_code == 200
    assert r_talk.json()["action"] == "chat"
    assert r_talk.json()["success"] is True

    # 5. Add resource and collect
    r_res = client.post("/add_resource", json={"x": 8, "y": 7})
    assert r_res.status_code == 200

    r_col = client.post("/agent/action", json={
        "agent_id": "api_bot",
        "action": "collect",
        "metadata": {},
    })
    assert r_col.status_code == 200
    assert r_col.json()["success"] is True
