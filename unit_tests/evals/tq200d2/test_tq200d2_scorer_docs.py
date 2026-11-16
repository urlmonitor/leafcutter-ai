"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_scorer_docs
GOAL: RED tests for the documentation half of TQ-200d-2-i and TQ-200d-2-ii: the produced-tests lines of
    scripts/evals/README.md and the known-issue register (the sql-test-writer known issue moves to resolved
    when both of its parts are fixed).
Target: scripts/evals/README.md, docs/known-issues/testing-quality.md,
    docs/known-issues/testing-quality/resolved/
Documentation is part of each AC; these read the REAL README and register.
"""

from __future__ import annotations

import unit_tests.evals.tq200d1ii._helpers as ref
import unit_tests.evals.tq200d2._helpers as h
import unit_tests.evals.tq200d2._probes as p

SQL_PAGE = ref.FAMILY_PAGE["sql-test-writer"]
KI_STEM = "ki-tq-20261025-sql-test-writer-eval-rejects-valid-live-outputs"


def test_readme_states_the_to_run_later_rule_in_one_linked_line():
    # covers: TQ-200d-2-i
    # angle: real_artifact
    # must_catch: README line missing, or naming the rule without linking the kind's entry
    p.check_readme_line(h.K_TO_RUN_LATER, SQL_PAGE, "test id", "non-empty")


def test_readme_states_the_count_rule_in_one_linked_line():
    # covers: TQ-200d-2-ii
    # angle: real_artifact
    # must_catch: README line missing, or naming the rule without linking the kind's entry
    p.check_readme_line(h.K_COUNTS, SQL_PAGE, "fetched", ">= 0", "at least one row")


def test_both_parts_fixed_so_the_known_issue_is_resolved():
    # covers: TQ-200d-2-ii
    # angle: real_artifact
    # must_catch: the known issue left open or its register row left under Open
    p.ki_resolved(KI_STEM, "TQ-200d-2-i", "TQ-200d-2-ii")
