"""
MODULE: tests.kernel.capabilities.test_dk_400c_1
GOAL: Prove the decompose_goal packet gives the host no repository access (AC DK-400c-1).
BUSINESS CONTEXT: ADR-052 and ADR-053: the host only proposes parts. Its packet allows reading
    the supplied artifact and proposing a split, forbids the standard operations, and its input
    artifact holds only the subject and the proposal rules.
ARCHITECTURE: The packet is the one the real service hands the host when a turned-away bundled
    goal parks on host.decompose_goal; the input artifact is read back from disk. RED until the
    operation allows exactly read_supplied_artifacts and propose_split.
"""

from __future__ import annotations

import json
from pathlib import Path

from kernel.interaction.packets import FORBIDDEN_HOST_OPERATIONS
from tests.kernel.helpers import narrow
from tests.kernel.split.support_400c import GOAL, ProposalCase


class TestDecomposePacket(ProposalCase):
    """The compiled host packet of decompose_goal."""

    async def test_decompose_packet_has_no_repository_access(self) -> None:
        # covers: DK-400c-1
        # angle: failure
        """Only read_supplied_artifacts and propose_split are allowed; the artifact is bare."""
        self.arrange()
        waiting = await self.service().start_run(self.goal_task())
        packet = narrow(waiting.pending_interaction)
        self.assertEqual(packet.operation, "decompose_goal")
        self.assertEqual(packet.allowed_operations, ["read_supplied_artifacts", "propose_split"])
        self.assertEqual(packet.forbidden_operations, list(FORBIDDEN_HOST_OPERATIONS))
        self.assertEqual(set(packet.allowed_operations) & set(packet.forbidden_operations), set())
        self.assertEqual(packet.input_evidence_ids, [])  # no repository evidence is cited
        (ref,) = packet.input_artifact_refs
        body = json.loads(Path(ref).read_text(encoding="utf-8"))
        self.assertEqual(body["evidence"], [])
        for leak in ("entity_context", "context_enrichment", "clarifications"):
            self.assertNotIn(leak, body)
        self.assertEqual(set(body["request"]), {"split_id", "subject_kind", "subject_text",
                                                "allowed_capabilities", "min_parts", "max_parts"})
        self.assertEqual(body["request"]["subject_text"], " ".join(GOAL.split()))
        self.assertEqual(body["request"]["min_parts"], 2)
        self.assertEqual(body["request"]["max_parts"], self.config.split.max_parts)
        self.assertEqual(body["request"]["allowed_capabilities"], ["decision", "research"])
