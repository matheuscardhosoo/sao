"""
Underworld engine - Pydantic schemas for world state.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    """2D coordinates in the world grid."""

    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)

    def as_tuple(self) -> tuple[int, int]:
        """Return (x, y) tuple for indexing."""
        return (self.x, self.y)


class Tile(BaseModel):
    """Schema for a single cell in the world grid with environment memory."""

    model_config = ConfigDict(extra="forbid")

    terrain: str = Field(default=".", description="Terrain: ., +, !, @")
    walk_count: int = Field(default=0, ge=0)
    history: list[str] = Field(default_factory=list)


class Agent(BaseModel):
    """Schema for an agent in the world."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    position: Position = Field(...)
    energy: int = Field(default=100, ge=0)
    max_energy: int = Field(default=100, ge=1)
    personality: str = Field(default="")
    inventory: list[Any] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class AgentState(BaseModel):
    """Schema for an agent's state in API responses."""

    agent_id: str = Field(..., min_length=1)
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    energy: int = Field(default=100, ge=0)
    is_active: bool = Field(default=True)


class WorldState(BaseModel):
    """Schema for the full world state for the visualizer and dashboard."""

    grid: list[list[str]] = Field(default_factory=list)
    agents: dict[str, list[int]] = Field(default_factory=dict)
    agent_details: dict[str, dict[str, Any]] = Field(default_factory=dict)
    event_log: list[str] = Field(default_factory=list)
