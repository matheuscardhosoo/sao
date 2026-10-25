"""
Underworld ASCII - Telemetry & Analytics
Logs every interaction for later analysis.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import threading

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "simulation_telemetry.jsonl"
_lock = threading.Lock()


def _ensure_log_dir() -> None:
    """Create logs directory if it doesn't exist."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_event(
    agent_id: str,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    """
    Append an event to simulation_telemetry.jsonl.
    Each line is a JSON object with timestamp, agent_id, event_type, description, metadata.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "event_type": event_type,
        "description": description,
        "metadata": metadata or {},
    }
    line = json.dumps(record) + "\n"
    with _lock:
        _ensure_log_dir()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
