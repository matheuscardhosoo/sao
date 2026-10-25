"""
Underworld ASCII - World Engine
State & Logic for the persistent 2D simulation environment.
"""

from dataclasses import dataclass, field
from typing import Optional
import threading

TRAIL_THRESHOLD = 3
HISTORY_MAX_LENGTH = 5
GRID_SIZE = 20


@dataclass
class Tile:
    """A single cell in the world grid with environment memory."""

    char: str = "."
    walk_count: int = 0
    history: list[str] = field(default_factory=list)

    def record_event(self, event: str) -> None:
        """Append event to history, trim if exceeds max length."""
        self.history.append(event)
        if len(self.history) > HISTORY_MAX_LENGTH:
            self.history = self.history[-HISTORY_MAX_LENGTH:]

    def step_on(self) -> None:
        """Increment walk count and potentially form a trail."""
        self.walk_count += 1
        if self.walk_count >= TRAIL_THRESHOLD and self.char == ".":
            self.char = "+"

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "char": self.char,
            "walk_count": self.walk_count,
            "history": self.history.copy(),
        }


class World:
    """
    The persistent 2D world with Environment Memory.
    Thread-safe for concurrent agent access.
    """

    def __init__(self, width: int = GRID_SIZE, height: int = GRID_SIZE) -> None:
        self.width = width
        self.height = height
        self._lock = threading.RLock()
        self.grid: list[list[Tile]] = [
            [Tile() for _ in range(width)] for _ in range(height)
        ]
        self.agents: dict[str, tuple[int, int]] = {}
        self.resources: set[tuple[int, int]] = set()
        self.global_event_log: list[str] = []
        self._max_event_log = 50

    def _log_event(self, msg: str) -> None:
        """Append to global event log."""
        with self._lock:
            self.global_event_log.append(msg)
            if len(self.global_event_log) > self._max_event_log:
                self.global_event_log = self.global_event_log[-self._max_event_log:]

    def spawn_agent(self, agent_id: str, x: int, y: int) -> bool:
        """Place an agent at (x, y). Returns False if cell occupied."""
        with self._lock:
            if not self._in_bounds(x, y):
                return False
            if (x, y) in self.agents.values():
                return False
            self.agents[agent_id] = (x, y)
            tile = self.grid[y][x]
            tile.record_event(f"Agent {agent_id} arrived")
            self._log_event(f"{agent_id} spawned at ({x},{y})")
            return True

    def add_resource(self, x: int, y: int) -> bool:
        """Add a resource marker at (x, y)."""
        with self._lock:
            if not self._in_bounds(x, y):
                return False
            self.resources.add((x, y))
            self.grid[y][x].record_event("Resource appeared")
            self._log_event(f"Resource added at ({x},{y})")
            return True

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get_agent_position(self, agent_id: str) -> Optional[tuple[int, int]]:
        """Return (x, y) or None if agent not found."""
        return self.agents.get(agent_id)

    def get_perception(self, agent_id: str, radius: int = 2) -> Optional[dict]:
        """
        Return a (2*radius+1)x(2*radius+1) view centered on the agent.
        Includes tile history for environmental context.
        """
        with self._lock:
            pos = self.agents.get(agent_id)
            if pos is None:
                return None
            ax, ay = pos
            cells: list[list[dict]] = []
            for dy in range(-radius, radius + 1):
                row: list[dict] = []
                for dx in range(-radius, radius + 1):
                    nx, ny = ax + dx, ay + dy
                    if not self._in_bounds(nx, ny):
                        row.append({"char": "#", "walk_count": 0, "history": []})
                        continue
                    tile = self.grid[ny][nx]
                    # Determine displayed char: agent, resource, trail, or base
                    if (nx, ny) in self.agents.values():
                        other_id = next(k for k, v in self.agents.items() if v == (nx, ny))
                        disp_char = "@" if other_id == agent_id else "@"
                        # Could differentiate self vs other; for now both @
                    elif (nx, ny) in self.resources:
                        disp_char = "!"
                    else:
                        disp_char = tile.char
                    row.append({
                        "char": disp_char,
                        "walk_count": tile.walk_count,
                        "history": tile.history.copy(),
                    })
                cells.append(row)
            return {
                "agent_id": agent_id,
                "center": [ax, ay],
                "radius": radius,
                "cells": cells,
            }

    def move(self, agent_id: str, dx: int, dy: int) -> tuple[bool, str]:
        """
        Move agent by (dx, dy). Returns (success, message).
        Updates tile walk_count and history (Environment Memory).
        """
        with self._lock:
            pos = self.agents.get(agent_id)
            if pos is None:
                return False, "Agent not found"
            ox, oy = pos
            nx, ny = ox + dx, oy + dy
            if not self._in_bounds(nx, ny):
                return False, "Out of bounds"
            if (nx, ny) in [(x, y) for aid, (x, y) in self.agents.items() if aid != agent_id]:
                return False, "Cell occupied by another agent"
            # Leave old cell
            old_tile = self.grid[oy][ox]
            old_tile.record_event(f"{agent_id} left")
            # Enter new cell
            new_tile = self.grid[ny][nx]
            new_tile.step_on()
            new_tile.record_event(f"{agent_id} moved here")
            self.agents[agent_id] = (nx, ny)
            self._log_event(f"{agent_id} moved ({ox},{oy}) -> ({nx},{ny})")
            return True, "Moved"

    def talk(self, agent_id: str, message: str) -> tuple[bool, str]:
        """Record agent speech in nearby tiles (Environment Memory)."""
        with self._lock:
            pos = self.agents.get(agent_id)
            if pos is None:
                return False, "Agent not found"
            x, y = pos
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    nx, ny = x + dx, y + dy
                    if self._in_bounds(nx, ny):
                        self.grid[ny][nx].record_event(f"{agent_id}: {message}")
            self._log_event(f"{agent_id} said: {message}")
            return True, "Spoke"

    def collect(self, agent_id: str) -> tuple[bool, str]:
        """Agent collects resource at current cell."""
        with self._lock:
            pos = self.agents.get(agent_id)
            if pos is None:
                return False, "Agent not found"
            x, y = pos
            if (x, y) not in self.resources:
                return False, "No resource here"
            self.resources.discard((x, y))
            self.grid[y][x].record_event(f"{agent_id} collected resource")
            self._log_event(f"{agent_id} collected resource at ({x},{y})")
            return True, "Collected"

    def get_full_state(self) -> dict:
        """Return full world state for visualizer."""
        with self._lock:
            rows: list[list[str]] = []
            for y in range(self.height):
                row: list[str] = []
                for x in range(self.width):
                    if (x, y) in self.agents.values():
                        row.append("@")
                    elif (x, y) in self.resources:
                        row.append("!")
                    else:
                        row.append(self.grid[y][x].char)
                rows.append(row)
            return {
                "grid": rows,
                "agents": {k: list(v) for k, v in self.agents.items()},
                "event_log": self.global_event_log.copy(),
            }
