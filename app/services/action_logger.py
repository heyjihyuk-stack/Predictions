from __future__ import annotations

"""Structured action logger with full audit trail for agent decisions."""

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    THOUGHT = "THOUGHT"
    TOOL_CALL = "TOOL_CALL"
    OBSERVATION = "OBSERVATION"
    PREDICTION = "PREDICTION"
    CHANGE = "CHANGE"


@dataclass
class ActionEntry:
    timestamp: str
    agent_name: str
    action_type: str
    asset_id: str
    details: dict[str, Any]
    result: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActionLogger:
    """Singleton action logger that tracks every agent decision with full audit trail.

    Thread-safe via a reentrant lock so nested calls from the same thread
    do not deadlock.
    """

    _instance: ActionLogger | None = None
    _init_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> ActionLogger:
        if cls._instance is None:
            with cls._init_lock:
                # Double-checked locking
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._entries: list[ActionEntry] = []
                    instance._lock = threading.RLock()
                    cls._instance = instance
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_action(
        self,
        agent_name: str,
        action_type: str | ActionType,
        details: dict[str, Any],
        result: str,
        asset_id: str = "",
    ) -> ActionEntry:
        """Record a single action and return the created entry."""
        if isinstance(action_type, ActionType):
            action_type = action_type.value

        entry = ActionEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_name=agent_name,
            action_type=action_type,
            asset_id=asset_id,
            details=details,
            result=result,
        )
        with self._lock:
            self._entries.append(entry)
        logger.debug(
            "ActionLogger: [%s] %s/%s -> %s",
            entry.timestamp,
            agent_name,
            action_type,
            result[:120] if result else "",
        )
        return entry

    def get_audit_trail(self, asset_id: str) -> list[ActionEntry]:
        """Return all action entries related to *asset_id*, ordered chronologically."""
        with self._lock:
            return [e for e in self._entries if e.asset_id == asset_id]

    def get_prediction_history(self, asset_id: str) -> list[dict[str, Any]]:
        """Return prediction changes over time with reasons for *asset_id*.

        Only entries of type PREDICTION or CHANGE are included so the caller
        gets a concise view of how the forecast evolved.
        """
        target_types = {ActionType.PREDICTION.value, ActionType.CHANGE.value}
        with self._lock:
            matching = [
                e for e in self._entries
                if e.asset_id == asset_id and e.action_type in target_types
            ]
        return [
            {
                "timestamp": e.timestamp,
                "agent_name": e.agent_name,
                "action_type": e.action_type,
                "details": e.details,
                "result": e.result,
            }
            for e in matching
        ]

    def export_trail(self, asset_id: str) -> list[dict[str, Any]]:
        """Return a JSON-serializable list of all actions for *asset_id*."""
        trail = self.get_audit_trail(asset_id)
        return [entry.to_dict() for entry in trail]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all stored entries (useful for testing)."""
        with self._lock:
            self._entries.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def __repr__(self) -> str:
        return f"<ActionLogger entries={self.size}>"
