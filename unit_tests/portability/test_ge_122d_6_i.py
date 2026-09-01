"""
MODULE: unit_tests/portability/test_ge_122d_6_i.py
GOAL: Minimal RED test-first stub for AC GE-122d-6-i — "A pass states what
    it inspected, so a pass is distinguishable from a hook that never ran".
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-6-i.yaml

Asserts the primary (angle: criterion) test_spec descriptor
(``test_ge122d6i_clean_commit_reports_one_inspected_count_per_namespace``):
in a built working copy with the check registered as GE-122d-6 requires, an
ordinary commit of a change claiming NO contested number completes, and the
captured commit output carries a per-namespace inspected-count line.

Per this AC's coverage note: "covered only by executing all three runs
against a real built working copy and comparing their outputs" — this
minimal stub asserts the first (registered, clean) run only; the
constant-defeating (added-artifact) and deregistered comparison runs are
this AC's other two test_spec descriptors, deferred here to keep this a
minimal stub.

RED AT AUTHORING TIME: as GE-122d-6-i depends directly on GE-122d-6
("Given a built working copy in which the numbering check is registered as
GE-122d-6 requires"), and GE-122d-6 is itself not yet satisfied (confirmed
by test_ge_122d_6.py in this same directory — the check is registered
nowhere in the deployed pre-commit registry), this test's precondition
cannot be met: no commit output carries any per-namespace inspected count
line, because the check never runs at all.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge122_build_commit_helpers import (  # noqa: E402
    build_and_wire_ordinary_commit_path,
    attempt_ordinary_commit,
    stage_paths,
)

# Per ADR-037 (referenced by this AC's doc_links), the pass is responsible
# for four namespaces. A clean commit's output must carry one inspected
# count line per namespace it is responsible for.
_EXPECTED_NAMESPACES = ["acceptance-criteria", "decisions", "diagrams", "work-items"]
_INSPECTED_COUNT_PATTERN = re.compile(r"(\d+)\s+inspected", re.IGNORECASE)


class TestGe122d6iCleanCommitReportsInspectedCounts(unittest.TestCase):
    def test_ge122d6i_clean_commit_reports_one_inspected_count_per_namespace(self) -> None:
        # covers: GE-122d-6-i
        # angle: criterion
        """An ordinary commit of a change claiming no contested number
        completes, and the captured commit output carries one inspected
        count per namespace the pass is responsible for.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "built_copy"
            build_result = build_and_wire_ordinary_commit_path(target_dir)
            self.assertEqual(
                0,
                build_result.returncode,
                msg=(
                    "Precondition failed: build.py must succeed before a clean commit's "
                    f"output can be inspected.\nstdout:\n{build_result.stdout}"
                    f"\nstderr:\n{build_result.stderr}"
                ),
            )

            uncontested_file = target_dir / "skills_config.json"
            uncontested_file.write_text('{"_comment": "adopter change"}\n', encoding="utf-8")
            stage_paths(target_dir, ["skills_config.json"])

            commit_result = attempt_ordinary_commit(
                target_dir, "test: ordinary uncontested change (GE-122d-6-i fixture)"
            )
            self.assertEqual(
                0,
                commit_result.returncode,
                msg=(
                    "Precondition failed: an uncontested commit must itself complete.\n"
                    f"stdout:\n{commit_result.stdout}\nstderr:\n{commit_result.stderr}"
                ),
            )

            combined_output = commit_result.stdout + commit_result.stderr
            inspected_lines = _INSPECTED_COUNT_PATTERN.findall(combined_output)

            self.assertGreaterEqual(
                len(inspected_lines),
                len(_EXPECTED_NAMESPACES),
                msg=(
                    "Expected at least one 'N inspected' count per namespace "
                    f"({_EXPECTED_NAMESPACES}) in the captured commit output — found "
                    f"{len(inspected_lines)} such line(s). Today the numbering check is not "
                    "registered at all (see test_ge_122d_6.py), so the commit's output "
                    "carries no inspected-count line whatsoever — a clean commit and a "
                    "commit where nothing was wired are indistinguishable, which is exactly "
                    f"what this AC exists to prevent.\nFull output:\n{combined_output}"
                ),
            )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/GE-122d-6 fast-lane build set]: Initial minimal
#   RED stub. Expected to fail because the commit output carries zero
#   'N inspected' lines (the check is not registered at all, per
#   test_ge_122d_6.py's confirmed baseline), never mind one per namespace.
# ====================================================================
