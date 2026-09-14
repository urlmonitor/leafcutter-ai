"""
MODULE: test_uxp_700b_3_i
GOAL: Pin the population-of-one boundary for the generic "every record of a kind must
    satisfy a rule" checker introduced by the UXP-700b-3 family.
BUSINESS CONTEXT: UXP-700b-3 establishes that a check phrased as a universal rule
    ("every X must satisfy P") must report "not_exercised" — not a clean pass — when it
    examined zero records of that kind (the vacuous-truth trap: "errors if ANY X differs"
    is true by default on an empty set). UXP-700b-3-i is the paired negative control: a
    checker that refuses to ever report anything BUT not_exercised (a guard that examines
    nothing and a guard that examines everything but never says so look identical from the
    outside) would trivially satisfy UXP-700b-3 while being useless. This record proves the
    boundary is pinned at population=1 in BOTH directions — a single satisfying record must
    yield a real "holds" verdict with examined=1, and a single violating record must yield a
    real, name-bearing violation — and neither case is allowed to fall back to
    "not_exercised".
ARCHITECTURE: Targets a new, not-yet-implemented module
    docs/product-truth/scripts/universal_rule_check.py (added to sys.path the same way
    unit_tests/test_generate_product_truth_idempotency.py already reaches into
    docs/product-truth/scripts for generate_product_truth). The module does not exist yet —
    this file is expected to fail on import (ImportError / ModuleNotFoundError) until
    python-coder creates it. Its expected contract:

      check_universal_rule(records, predicate, kind, name_of=...) -> RuleCheckResult
        - RuleCheckResult has .outcome in {"not_exercised", "holds", "violated"},
          .examined (int), .kind (str), .violations (list[str]).
        - 0 records            -> outcome "not_exercised" (this boundary is UXP-700b-3's,
                                   not re-tested here).
        - >=1 record, all pass -> outcome "holds", examined == len(records).
        - >=1 record, any fail -> outcome "violated", violations names each failing record.

      main(argv) / CLI (`python universal_rule_check.py --records <path.json> --rule
      <name> --kind <name>`) — the module's own production entry point. Reads a JSON list
      of record objects from --records, applies a canned rule selected by --rule, prints
      the verdict as JSON to stdout, and exits 0 for "holds"/"not_exercised" and 1 for
      "violated" — i.e. the outcome is consumed in control flow via the exit code, not just
      printed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The scripts directory is not on the default path; add it so we can import, mirroring
# unit_tests/test_generate_product_truth_idempotency.py's convention for this same
# docs/product-truth/scripts location.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_CLI_PATH = _SCRIPTS_DIR / "universal_rule_check.py"


class TestSingleRecordBoundary(unittest.TestCase):
    """Population-of-one boundary for the universal every-record rule checker."""

    def test_single_satisfying_record_reports_the_rule_holds_and_one_examined(self):
        # covers: UXP-700b-3-i
        # angle: boundary
        # A population of exactly one record that SATISFIES the rule must yield a real
        # "holds" verdict with examined == 1 — and must NOT collapse to "not_exercised",
        # which is the verdict reserved for a population of zero (UXP-700b-3).
        import universal_rule_check as urc  # noqa: E402  (import must fail until implemented)

        records = [{"id": "widget-1", "value": 5}]
        result = urc.check_universal_rule(
            records,
            predicate=lambda r: r["value"] > 0,
            kind="widget",
        )

        self.assertEqual(result.outcome, "holds")
        self.assertEqual(result.examined, 1)
        self.assertNotEqual(
            result.outcome,
            "not_exercised",
            "a populated, satisfying run must not be reported as unexercised",
        )
        self.assertEqual(result.violations, [])

    def test_single_violating_record_reports_the_violation_by_name(self):
        # covers: UXP-700b-3-i
        # angle: failure
        # A population of exactly one record that VIOLATES the rule must yield a named
        # violation — not a not-exercised report, and not a silent pass.
        import universal_rule_check as urc  # noqa: E402  (import must fail until implemented)

        records = [{"id": "widget-bad-1", "value": -3}]
        result = urc.check_universal_rule(
            records,
            predicate=lambda r: r["value"] > 0,
            kind="widget",
        )

        self.assertEqual(result.outcome, "violated")
        self.assertEqual(result.examined, 1)
        self.assertEqual(result.violations, ["widget-bad-1"])
        self.assertNotEqual(
            result.outcome,
            "not_exercised",
            "a populated, violating run must not be reported as unexercised",
        )


class TestReachability(unittest.TestCase):
    """Reachability: the checker must be provable through its real CLI entry point, not
    merely through a direct import of check_universal_rule()."""

    def _run_cli(self, records: list) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            records_path = Path(tmp) / "records.json"
            records_path.write_text(json.dumps(records), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(_CLI_PATH),
                    "--records",
                    str(records_path),
                    "--rule",
                    "positive",
                    "--kind",
                    "widget",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

    def test_uxp_700b_3_i_reachable_from_entry_point(self):
        # covers: UXP-700b-3-i
        # angle: reachability
        # REQUIRED: invoke the module's real production entry point — its CLI — as a
        # subprocess, for both arms of the boundary, and assert the outcome is consumed in
        # control flow via the process exit code (not merely printed to stdout).
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python docs/product-truth/scripts/universal_rule_check.py \
        #     --records <file> --rule positive --kind widget (CLI via subprocess, main()
        #     guarded by if __name__ == '__main__':)"
        # This module has no existing caller (UXP-700b/700b-1/700b-2/700b-3 — its own
        # prerequisites in the AC store — are all still work_status: todo in this repo, so
        # there is no pre-commit hook, slash command, or workflow step to attach to yet).
        # Category 1 of the resolution order (CLI script with a main() guarded by
        # `if __name__ == "__main__":`) is the one this ticket's own contract requires
        # python-coder to build, so the CLI IS the entry point being pinned here, not an
        # inner helper reached by import.

        holds_result = self._run_cli([{"id": "widget-1", "value": 5}])
        self.assertEqual(
            holds_result.returncode,
            0,
            f"a single satisfying record must exit 0; stderr={holds_result.stderr!r}",
        )
        holds_payload = json.loads(holds_result.stdout)
        self.assertEqual(holds_payload["outcome"], "holds")
        self.assertEqual(holds_payload["examined"], 1)
        self.assertNotEqual(holds_payload["outcome"], "not_exercised")

        violated_result = self._run_cli([{"id": "widget-bad-1", "value": -3}])
        self.assertEqual(
            violated_result.returncode,
            1,
            f"a single violating record must exit non-zero (its result must be consumed "
            f"in control flow, not merely printed); stderr={violated_result.stderr!r}",
        )
        violated_payload = json.loads(violated_result.stdout)
        self.assertEqual(violated_payload["outcome"], "violated")
        self.assertEqual(violated_payload["examined"], 1)
        self.assertEqual(violated_payload["violations"], ["widget-bad-1"])
        self.assertNotEqual(violated_payload["outcome"], "not_exercised")


if __name__ == "__main__":
    unittest.main()
