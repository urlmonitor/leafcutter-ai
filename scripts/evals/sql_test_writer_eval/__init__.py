"""
MODULE: scripts/evals/sql_test_writer_eval/__init__.py
GOAL: The assertion kinds of the sql-test-writer eval set (TQ-200d-2), as one ``KINDS`` registry.
BUSINESS CONTEXT: scripts/evals/ is at its folder file limit, so the kinds that only this agent's
    set uses live in this sub-package instead of in a sibling module.
ARCHITECTURE: ``report_kinds`` reads the hand-off prose (trap and run lines); ``label_kinds`` reads its labels; ``evidence_kinds``
    reads the machine evidence (the to-run-later file in the sandbox's git dir) and the SQL of the
    produced test. ``KINDS`` is spread into produced_tests_scoring.KINDS.
"""

from __future__ import annotations

from sql_test_writer_eval import evidence_kinds, label_kinds, report_kinds

KINDS = {**report_kinds.KINDS, **label_kinds.KINDS, **evidence_kinds.KINDS}
