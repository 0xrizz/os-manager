"""Unit tests for cross-agent context handoff envelope protocol."""

from pathlib import Path
import tempfile
import unittest

from os_manager.ledger.db import LedgerDB
from os_manager.ledger.handoff import HandoffEnvelope, HandoffManager


class TestHandoffProtocol(unittest.TestCase):
    """Verify task handover creation, claiming, and context preservation."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test_handoff.db"
        self.db = LedgerDB(self.db_path)
        self.manager = HandoffManager(self.db)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_create_and_claim_handoff(self) -> None:
        handoff = HandoffEnvelope(
            handoff_id="hnd_101",
            timestamp=1700000000.0,
            source_agent_id="planner-agent",
            target_agent_id="coder-agent",
            task_summary="Implement AST security guard",
            worktree_branch="feat/ast-guard",
            context_payload={"files_to_touch": ["os_manager/security/ast_guard.py"]},
            status="pending",
        )
        self.manager.create_handoff(handoff)

        pending = self.manager.list_pending_handoffs(target_agent_id="coder-agent")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].handoff_id, "hnd_101")
        self.assertEqual(pending[0].worktree_branch, "feat/ast-guard")

        # Claim handoff
        claimed = self.manager.claim_handoff("hnd_101", agent_id="coder-agent")
        self.assertTrue(claimed)
        self.assertEqual(len(self.manager.list_pending_handoffs("coder-agent")), 0)


if __name__ == "__main__":
    unittest.main()
