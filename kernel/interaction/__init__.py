"""
MODULE: kernel.interaction
GOAL: Public surface of the interaction protocol: packets handed to a client, submissions coming
    back, the stable rejection codes and the ledgered `submit_interaction` entry point.
BUSINESS CONTEXT: Host work and human questions are how a run asks outside parties for help; the
    service, CLI and skill (P7) and the host operations (P8) all speak exactly this protocol.
ARCHITECTURE: No scheduler imports here, so the scheduler package can import this one. The
    `nodes_interaction` graph nodes call `packets`, `submissions` and `results`; clients call
    `ledger.submit_interaction`.
"""

from __future__ import annotations

from kernel.interaction.ledger import (
    SubmissionRejected,
    SubmitResult,
    SubmitStatus,
    submit_interaction,
)
from kernel.interaction.packets import FORBIDDEN_HOST_OPERATIONS, redact_packet
from kernel.interaction.submissions import (
    RejectionCode,
    Verdict,
    check_submission,
    pending_packet,
    submission_hash,
)

__all__ = ["FORBIDDEN_HOST_OPERATIONS", "RejectionCode", "SubmissionRejected", "SubmitResult",
           "SubmitStatus", "Verdict", "check_submission", "pending_packet", "redact_packet",
           "submission_hash", "submit_interaction"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: Split into packets, submissions, results and ledger so every
#   file stays well under the size cap and only `ledger` touches the graph and the run store.
#   (#KernelBootstrapV0/P6)
# ====================================================================
