"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3_iii.py
GOAL: BP-100k-3-iii — on a worked-in (not freshly cloned) built workspace, four
    files that no build run can ever produce deterministic content for must be
    declared exemptions with distinct, non-blank grounds in the REAL
    commit_guardian.json (not a test-only override), and two stale artifacts
    left behind by a deprecated skill and a deleted script must remain
    reported as coverage gaps — never silently folded into the same
    exemption — because an orphan with no template able to produce it is the
    "candidate for manual deletion" class _drift_exemptions.py's own
    governing comment already warns against exempting.
BUSINESS CONTEXT: Measured on the reporting machine 2026-09-14, immediately
    after a successful full build.py run, check-output-drift reported six
    gaps and blocked every commit. Four of the six are never-build-determined
    and belong in the exemption registry BP-100k-3 already built. The other
    two are stale deploy artifacts of a deprecated skill and a deleted script
    respectively — real gaps correctly found, not exemption candidates. See
    docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100k-3-iii.yaml.
ARCHITECTURE / EXERCISE STRATEGY: fixture plumbing lives in the sibling
    harness module _bp_100k_3_iii_harness.py (mirroring the
    unit_tests/product_truth/_bounds_harness.py precedent) so this file stays
    a list of behavioural assertions. The exemption-half tests EXECUTE the
    real, unmodified deployed check_output_drift.py as a subprocess against a
    synthesized tree, reading the REAL, colocated commit_guardian.json (no
    HOOK_TEST_CONFIG override). The classification-evidence tests load the
    real _drift_exemptions and build_phases modules directly.

RED BASELINE (expected, captured before the registry entries are added):
    every EXEMPT-side assertion below is RED — the four never-build-determined
    paths are reported as UNCOMPARABLE: GAP (not EXEMPT) because no exemption
    registry entry yet exists for them.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from . import _bp_100k_3_iii_harness as h


def _require_result_line(combined: str) -> re.Match[str]:
    """Return the gate's RESULT-line match, failing loudly if it is absent.

    A missing RESULT line means the gate did not run to completion, which is a
    different outcome from a gate that ran and disagreed — so it gets its own
    error rather than an AttributeError on None further down.

    Args:
        combined: Captured stdout+stderr from a gate run.

    Returns:
        The RESULT-line match object.

    Raises:
        AssertionError: If the output carries no RESULT line.
    """
    match = h.RESULT_LINE_RE.search(combined)
    if match is None:
        raise AssertionError(f"No RESULT line found. Output:\n{combined}")
    return match


class TestExemptionHalf(unittest.TestCase):
    """The four never-build-determined files are exempt with distinct
    grounds, and the real registry that grounds them loads and validates."""

    def test_bp_100k_3_iii_the_four_never_build_determined_files_are_exempt_with_distinct_grounds(
        self,
    ) -> None:
        # covers: BP-100k-3-iii
        with tempfile.TemporaryDirectory() as td:
            hook = h.build_gate_workspace(
                Path(td),
                registered={".claude/settings.json": b"# tracked output\nmatches the manifest\n"},
                unregistered=h.FOUR_EXEMPT_PATHS,
            )
            result = h.run_gate_with_real_registry(hook, Path(td))
        combined = result.stdout + result.stderr

        grounds: dict[str, str] = {}
        for rel_path in h.FOUR_EXEMPT_PATHS:
            ground = h.extract_exempt_ground(combined, rel_path)
            if not ground:
                self.fail(
                    f"{rel_path} not reported as exempt with a non-blank ground. "
                    f"Output:\n{combined}"
                )
            grounds[rel_path] = ground

        self.assertEqual(
            len(set(grounds.values())),
            len(grounds),
            msg=f"The four grounds are not pairwise distinct: {grounds}",
        )

        match = _require_result_line(combined)
        self.assertEqual(0, int(match.group(4)), msg=f"Expected zero gaps. Output:\n{combined}")
        self.assertEqual(0, result.returncode, msg=f"Expected a clean exit. Output:\n{combined}")

    def test_bp_100k_3_iii_the_real_registry_entries_load_and_validate_with_non_blank_grounds(
        self,
    ) -> None:
        # covers: BP-100k-3-iii
        with h.real_drift_exemptions_module() as module:
            valid = module.validate_exemption_registry(
                module.load_exemption_registry("check-output-drift")
            )

        grounds = {}
        for rel_path in h.FOUR_EXEMPT_PATHS:
            self.assertIn(rel_path, valid, msg=f"{rel_path} is not a grounded real entry.")
            self.assertTrue(valid[rel_path].strip(), msg=f"{rel_path}'s real ground is blank.")
            grounds[rel_path] = valid[rel_path]
        self.assertEqual(
            len(set(grounds.values())),
            len(grounds),
            msg=f"The four real registry grounds are not pairwise distinct: {grounds}",
        )

        for rel_path in h.ORPHAN_PATHS:
            self.assertNotIn(
                rel_path,
                valid,
                msg=f"{rel_path} must never appear as a declared exemption — it is a "
                "stale artifact with no template, not a hand-maintained file the "
                "build deliberately leaves alone.",
            )


class TestOrphanHalf(unittest.TestCase):
    """The two stale deploy artifacts remain coverage gaps, never silently
    exempted, and executable evidence explains why each has no template."""

    def test_bp_100k_3_iii_the_orphaned_pair_are_reported_as_gaps_never_silently_exempted(
        self,
    ) -> None:
        # covers: BP-100k-3-iii
        tracked_content = b"# tracked output\nmatches the manifest\n"
        with tempfile.TemporaryDirectory() as td:
            hook = h.build_gate_workspace(
                Path(td),
                registered={
                    ".claude/settings.json": tracked_content,
                    ".gemini/instructions.md": tracked_content,
                    "scripts/commit_guardian/commit_guardian.json": tracked_content,
                },
                unregistered=h.ORPHAN_PATHS,
            )
            result = h.run_gate_with_real_registry(hook, Path(td))
        combined = result.stdout + result.stderr

        for rel_path in h.ORPHAN_PATHS:
            self.assertIn(
                f"UNCOMPARABLE: GAP {rel_path} action=run build.py to register it",
                combined,
                msg=f"{rel_path} was not reported as a gap. Output:\n{combined}",
            )
            self.assertNotIn(
                f"UNCOMPARABLE: EXEMPT {rel_path}",
                combined,
                msg=f"{rel_path} was silently exempted. Output:\n{combined}",
            )

        match = _require_result_line(combined)
        self.assertEqual(2, int(match.group(4)), msg=f"Output:\n{combined}")
        self.assertEqual(2, result.returncode, msg=f"Output:\n{combined}")

    def test_bp_100k_3_iii_frontend_design_is_deprecated_so_no_template_can_produce_its_gemini_output(
        self,
    ) -> None:
        # covers: BP-100k-3-iii
        frontend_design_dir = h.TEMPLATES_DIR / "skills" / "frontend-design"
        self.assertTrue(frontend_design_dir.is_dir(), msg=f"Expected {frontend_design_dir}.")
        with h.real_build_phases_module() as build_phases:
            self.assertTrue(
                build_phases._skill_is_deprecated(frontend_design_dir),
                msg="templates/skills/frontend-design is no longer deprecated — if this "
                "changes, .gemini/skills/frontend-design/SKILL.md becomes a real "
                "registration gap and BP-100k-3-iii's exemption decision needs revisiting.",
            )

    def test_bp_100k_3_iii_known_failing_tests_template_does_not_exist(self) -> None:
        # covers: BP-100k-3-iii
        known_failing_tests_template = h.CG_TEMPLATES_SRC / "known_failing_tests.py"
        self.assertFalse(
            known_failing_tests_template.exists(),
            msg=f"{known_failing_tests_template} exists — if a template has been "
            "(re)created at this path, scripts/commit_guardian/known_failing_tests.py "
            "is a real gap, not an orphan, and BP-100k-3-iii's decision needs revisiting.",
        )


class TestEndToEnd(unittest.TestCase):
    """After the four exemptions exist and the two orphans are absent from
    disk, a single gate run reports a fully clean RESULT line."""

    def test_bp_100k_3_iii_end_to_end_after_the_fix_the_gate_reports_gaps_zero_and_exits_zero(
        self,
    ) -> None:
        # covers: BP-100k-3-iii
        with tempfile.TemporaryDirectory() as td:
            hook = h.build_gate_workspace(
                Path(td),
                registered={".claude/settings.json": b"# tracked output\nmatches the manifest\n"},
                unregistered=h.FOUR_EXEMPT_PATHS,
            )
            result = h.run_gate_with_real_registry(hook, Path(td))
        combined = result.stdout + result.stderr

        match = _require_result_line(combined)
        verified, uncomparable, exempt, gaps, drifted, missing, unreadable = (
            int(g) for g in match.groups()
        )
        self.assertEqual(0, gaps, msg=f"Output:\n{combined}")
        self.assertEqual(0, drifted, msg=f"Output:\n{combined}")
        self.assertEqual(0, missing, msg=f"Output:\n{combined}")
        self.assertEqual(0, unreadable, msg=f"Output:\n{combined}")
        self.assertEqual(4, exempt, msg=f"Output:\n{combined}")
        self.assertEqual(0, result.returncode, msg=f"Expected a clean exit. Output:\n{combined}")


if __name__ == "__main__":
    unittest.main()
