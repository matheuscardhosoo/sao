"""
Underworld utilities - Simulation telemetry logging.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "underworld.jsonl"
_sink_added = False


def _telemetry_filter(record: dict) -> bool:
    """Only pass records from the telemetry logger."""
    return record.get("extra", {}).get("telemetry") is True


class SimulationLogger:
    """
    Writes every action into logs/underworld.jsonl using loguru.
    Each line is a JSON object for later analysis.
    """

    def __init__(self, log_path: Path | None = None) -> None:
        global _sink_added
        self.log_path = log_path or LOG_FILE
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not _sink_added:
            logger.add(
                str(self.log_path),
                format="{message}",
                level="DEBUG",
                mode="a",
                filter=_telemetry_filter,
            )
            _sink_added = True
        self._tel = logger.bind(telemetry=True)

    def log(
        self,
        agent_id: str,
        action: str,
        description: str,
        metadata: dict | None = None,
    ) -> None:
        """Append a structured event to the telemetry log."""
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": agent_id,
            "action": action,
            "description": description,
            "metadata": metadata or {},
        }
        self._tel.debug(json.dumps(record))
