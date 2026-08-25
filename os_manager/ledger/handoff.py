"""Cross-Agent Context Handoff Protocol and Lifecycle Manager."""

from dataclasses import dataclass
import json
import time
from typing import Any, Dict, List, Optional

from .db import LedgerDB


@dataclass
class HandoffEnvelope:
    handoff_id: str
    timestamp: float
    source_agent_id: str
    target_agent_id: str
    task_summary: str
    worktree_branch: Optional[str]
    context_payload: Dict[str, Any]
    status: str = "pending"  # pending | in_progress | completed | rejected


class HandoffManager:
    """Manages creation, claiming, and completion of agent task handovers."""

    def __init__(self, db: Optional[LedgerDB] = None):
        self.db = db or LedgerDB()

    def create_handoff(self, handoff: HandoffEnvelope) -> None:
        """Record a new pending handoff envelope in the ledger."""
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO handoffs (
                    handoff_id, timestamp, source_agent_id, target_agent_id,
                    task_summary, worktree_branch, context_payload, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handoff.handoff_id,
                    handoff.timestamp,
                    handoff.source_agent_id,
                    handoff.target_agent_id,
                    handoff.task_summary,
                    handoff.worktree_branch,
                    json.dumps(handoff.context_payload),
                    handoff.status,
                ),
            )
            conn.commit()

    def list_pending_handoffs(
        self, target_agent_id: Optional[str] = None
    ) -> List[HandoffEnvelope]:
        """List uncompleted handoffs awaiting claim."""
        query = "SELECT handoff_id, timestamp, source_agent_id, target_agent_id, task_summary, worktree_branch, context_payload, status FROM handoffs WHERE status = 'pending'"
        params: List[Any] = []

        if target_agent_id:
            query += " AND (target_agent_id = ? OR target_agent_id = 'all')"
            params.append(target_agent_id)

        query += " ORDER BY timestamp ASC"

        results: List[HandoffEnvelope] = []
        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            for row in cur.fetchall():
                results.append(
                    HandoffEnvelope(
                        handoff_id=row[0],
                        timestamp=row[1],
                        source_agent_id=row[2],
                        target_agent_id=row[3],
                        task_summary=row[4],
                        worktree_branch=row[5],
                        context_payload=json.loads(row[6]),
                        status=row[7],
                    )
                )
        return results

    def claim_handoff(self, handoff_id: str, agent_id: str) -> bool:
        """Mark a pending handoff as in_progress by an agent."""
        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE handoffs SET status = 'in_progress' WHERE handoff_id = ? AND status = 'pending'",
                (handoff_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def complete_handoff(self, handoff_id: str) -> bool:
        """Mark a handoff as completed."""
        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE handoffs SET status = 'completed' WHERE handoff_id = ?",
                (handoff_id,),
            )
            conn.commit()
            return cur.rowcount > 0
