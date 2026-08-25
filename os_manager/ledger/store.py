"""Multi-Agent Event Logging and Query Interface."""

from dataclasses import asdict, dataclass
import json
import time
from typing import Any, Dict, List, Optional

from .db import LedgerDB


@dataclass
class AgentEvent:
    event_id: str
    timestamp: float
    agent_id: str
    topic: str
    payload: Dict[str, Any]


class EventStore:
    """Appends and queries structured multi-agent events."""

    def __init__(self, db: Optional[LedgerDB] = None):
        self.db = db or LedgerDB()

    def append_event(self, event: AgentEvent) -> None:
        """Persist an agent event to the SQLite WAL database."""
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO events (event_id, timestamp, agent_id, topic, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.timestamp,
                    event.agent_id,
                    event.topic,
                    json.dumps(event.payload),
                ),
            )
            conn.commit()

    def query_events(
        self, topic: Optional[str] = None, limit: int = 50
    ) -> List[AgentEvent]:
        """Query recent events with optional topic filter."""
        events: List[AgentEvent] = []
        query = "SELECT event_id, timestamp, agent_id, topic, payload FROM events"
        params: List[Any] = []

        if topic:
            query += " WHERE topic = ?"
            params.append(topic)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            for row in cur.fetchall():
                events.append(
                    AgentEvent(
                        event_id=row[0],
                        timestamp=row[1],
                        agent_id=row[2],
                        topic=row[3],
                        payload=json.loads(row[4]),
                    )
                )
        return events
