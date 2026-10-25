"""
Underworld engine - World simulation logic.
"""

import random
import threading
from typing import Any

from engine.models import Agent, Position, Tile

GRID_SIZE = 20
TRAIL_THRESHOLD = 3
TRAIL_DISPLAY_THRESHOLD = 3
HISTORY_MAX_LENGTH = 10

ENERGY_MOVE_COST = 1
ENERGY_CHAT_COST = 2
ENERGY_COLLECT_REWARD = 40

DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}


class WorldEngine:
    """
    Persistent 2D world with environment memory.
    Thread-safe for concurrent agent access.
    """

    def __init__(self, width: int = GRID_SIZE, height: int = GRID_SIZE) -> None:
        self.width = width
        self.height = height
        self._lock = threading.RLock()
        self.grid: list[list[Tile]] = [
            [Tile(terrain=".") for _ in range(width)] for _ in range(height)
        ]
        self.agents: dict[str, Agent] = {}
        self.resources: set[tuple[int, int]] = set()
        self.event_log: list[str] = []
        self._max_event_log = 50

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _append_event(self, msg: str) -> None:
        self.event_log.append(msg)
        if len(self.event_log) > self._max_event_log:
            self.event_log = self.event_log[-self._max_event_log :]

    def add_event_to_tile(self, pos: Position | tuple[int, int], event_msg: str) -> None:
        """Add an event message to a tile's history for environmental context."""
        x, y = pos.as_tuple() if isinstance(pos, Position) else pos
        with self._lock:
            if not self._in_bounds(x, y):
                return
            tile = self.grid[y][x]
            tile.history.append(event_msg)
            if len(tile.history) > HISTORY_MAX_LENGTH:
                tile.history = tile.history[-HISTORY_MAX_LENGTH:]
            self._append_event(f"[{x},{y}] {event_msg}")

    def spawn_agent(
        self,
        agent_id: str,
        x: int,
        y: int,
        personality: str = "",
    ) -> bool:
        """Place or revive an agent at (x, y). Returns False if cell occupied or out of bounds."""
        with self._lock:
            if not self._in_bounds(x, y):
                return False
            pos_tuple = (x, y)
            if any(a.position.as_tuple() == pos_tuple and a.id != agent_id for a in self.agents.values()):
                return False
            agent = Agent(
                id=agent_id,
                position=Position(x=x, y=y),
                personality=personality,
                energy=100,
                max_energy=100,
                is_active=True,
            )
            self.agents[agent_id] = agent
            self.add_event_to_tile(pos_tuple, f"Agent {agent_id} arrived")
            self._append_event(f"⚡ {agent_id} spawned at ({x},{y})")
            return True

    def add_resource(self, x: int, y: int) -> bool:
        """Add a resource at (x, y)."""
        with self._lock:
            if not self._in_bounds(x, y):
                return False
            self.resources.add((x, y))
            self.add_event_to_tile((x, y), "Resource appeared")
            return True

    def spawn_resource(self) -> bool:
        """Randomly place '!' on the map if fewer than 5 resources. Returns True if placed."""
        with self._lock:
            if len(self.resources) >= 5:
                return False
            agent_positions = {a.position.as_tuple() for a in self.agents.values()}
            candidates = [
                (x, y)
                for x in range(self.width)
                for y in range(self.height)
                if (x, y) not in self.resources and (x, y) not in agent_positions
            ]
            if not candidates:
                return False
            x, y = random.choice(candidates)
            self.resources.add((x, y))
            self.add_event_to_tile((x, y), "Resource appeared")
            self._append_event(f"✨ Resource spawned at ({x},{y})")
            return True

    def decay_trails(self) -> None:
        """Gradually decay walk_count and evaporate old trails."""
        with self._lock:
            for y in range(self.height):
                for x in range(self.width):
                    tile = self.grid[y][x]
                    if tile.walk_count > 0:
                        tile.walk_count -= 1
                        if tile.walk_count < TRAIL_THRESHOLD and tile.terrain == "+":
                            tile.terrain = "."

    def move_agent(self, agent_id: str, direction: str) -> tuple[bool, str]:
        """
        Move agent one cell in the given direction.
        Consumes energy, increments walk_count, and adds 'trace' to tile history.
        Returns (success, message).
        """
        direction = direction.lower().strip()
        if direction not in DIRECTIONS:
            return False, f"Invalid direction: {direction}"
        dx, dy = DIRECTIONS[direction]
        with self._lock:
            agent = self.agents.get(agent_id)
            if agent is None:
                return False, "Agent not found"
            if not agent.is_active or agent.energy <= 0:
                return False, "Agent is exhausted (0 energy)"

            ox, oy = agent.position.x, agent.position.y
            nx, ny = ox + dx, oy + dy
            if not self._in_bounds(nx, ny):
                return False, "Out of bounds"
            pos_tuple = (nx, ny)
            if any(
                a.id != agent_id and a.position.as_tuple() == pos_tuple
                for a in self.agents.values()
            ):
                return False, "Cell occupied"

            # Deduct energy for movement
            agent.energy = max(0, agent.energy - ENERGY_MOVE_COST)

            # Leave old tile
            self.add_event_to_tile((ox, oy), f"{agent_id} left")

            # Enter new tile
            tile = self.grid[ny][nx]
            tile.walk_count += 1
            tile.history.append("trace")
            if len(tile.history) > HISTORY_MAX_LENGTH:
                tile.history = tile.history[-HISTORY_MAX_LENGTH:]
            if tile.walk_count >= TRAIL_THRESHOLD and tile.terrain == ".":
                tile.terrain = "+"
            tile.history.append(f"{agent_id} moved here")
            if len(tile.history) > HISTORY_MAX_LENGTH:
                tile.history = tile.history[-HISTORY_MAX_LENGTH:]
            agent.position = Position(x=nx, y=ny)

            if agent.energy == 0:
                agent.is_active = False
                self._append_event(f"💀 {agent_id} exhausted all energy and collapsed at ({nx},{ny})")
                return True, "Moved, but collapsed from exhaustion (0 energy)"

            self._append_event(f"{agent_id} moved ({ox},{oy}) -> ({nx},{ny}) [E: {agent.energy}]")
            return True, "Moved"

    def collect(self, agent_id: str) -> tuple[bool, str]:
        """Collect resource at agent's current cell, restoring energy and adding to inventory."""
        with self._lock:
            agent = self.agents.get(agent_id)
            if agent is None:
                return False, "Agent not found"
            pos = agent.position.as_tuple()
            if pos not in self.resources:
                return False, "No resource here"

            self.resources.discard(pos)
            agent.inventory.append("energy_crystal")
            gained = min(agent.max_energy - agent.energy, ENERGY_COLLECT_REWARD)
            agent.energy = min(agent.max_energy, agent.energy + ENERGY_COLLECT_REWARD)
            agent.is_active = True

            self.add_event_to_tile(pos, f"{agent_id} collected resource (+{gained} energy)")
            self._append_event(
                f"💎 {agent_id} collected resource (+{gained} energy -> {agent.energy}, items: {len(agent.inventory)})"
            )
            return True, f"Collected resource (+{gained} energy)"

    def chat(self, agent_id: str, message: str) -> tuple[bool, str]:
        """Record agent speech in nearby tiles, consuming 2 energy."""
        with self._lock:
            agent = self.agents.get(agent_id)
            if agent is None:
                return False, "Agent not found"
            if not agent.is_active or agent.energy <= 0:
                return False, "Agent is exhausted (0 energy)"

            agent.energy = max(0, agent.energy - ENERGY_CHAT_COST)
            if agent.energy == 0:
                agent.is_active = False

            x, y = agent.position.x, agent.position.y
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    nx, ny = x + dx, y + dy
                    if self._in_bounds(nx, ny):
                        self.add_event_to_tile((nx, ny), f"{agent_id}: {message}")
            self._append_event(f"💬 {agent_id}: \"{message}\" [E: {agent.energy}]")
            return True, "Spoke"

    def get_perception(self, agent_id: str, radius: int = 3) -> dict[str, Any] | None:
        """Return a (2*radius+1)x(2*radius+1) view with tile history and agent stats."""
        with self._lock:
            agent = self.agents.get(agent_id)
            if agent is None:
                return None
            ax, ay = agent.position.x, agent.position.y
            cells: list[list[dict]] = []
            for dy in range(-radius, radius + 1):
                row: list[dict] = []
                for dx in range(-radius, radius + 1):
                    nx, ny = ax + dx, ay + dy
                    if not self._in_bounds(nx, ny):
                        row.append({"terrain": "#", "walk_count": 0, "history": []})
                        continue
                    tile = self.grid[ny][nx]
                    if (nx, ny) in [
                        a.position.as_tuple() for a in self.agents.values()
                    ]:
                        disp = "@"
                    elif (nx, ny) in self.resources:
                        disp = "!"
                    else:
                        disp = tile.terrain
                    row.append({
                        "terrain": disp,
                        "walk_count": tile.walk_count,
                        "history": tile.history.copy(),
                    })
                cells.append(row)
            return {
                "agent_id": agent_id,
                "center": [ax, ay],
                "radius": radius,
                "energy": agent.energy,
                "max_energy": agent.max_energy,
                "inventory_count": len(agent.inventory),
                "is_active": agent.is_active,
                "cells": cells,
            }

    def get_full_state(self) -> dict[str, Any]:
        """Return full world state for the visualizer and dashboard."""
        with self._lock:
            rows: list[list[str]] = []
            for y in range(self.height):
                row: list[str] = []
                for x in range(self.width):
                    if (x, y) in [a.position.as_tuple() for a in self.agents.values()]:
                        row.append("@")
                    elif (x, y) in self.resources:
                        row.append("!")
                    else:
                        tile = self.grid[y][x]
                        row.append("+" if tile.walk_count >= TRAIL_DISPLAY_THRESHOLD else ".")
                    rows.append(row)
            agents_dict = {
                aid: [a.position.x, a.position.y] for aid, a in self.agents.items()
            }
            agent_details = {
                aid: {
                    "energy": a.energy,
                    "max_energy": a.max_energy,
                    "inventory_count": len(a.inventory),
                    "personality": a.personality,
                    "is_active": a.is_active,
                    "x": a.position.x,
                    "y": a.position.y,
                }
                for aid, a in self.agents.items()
            }
            return {
                "grid": rows,
                "agents": agents_dict,
                "agent_details": agent_details,
                "event_log": self.event_log.copy(),
            }
