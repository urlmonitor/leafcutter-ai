"""
MODULE: unit_tests/commit_guardian/test_ge_127d_1.py
COVERS: GE-127d-1 -- "The published rule and the enforced rule are checked
    against each other, and no fact the standard accepts about a change is
    left without effect on its verdict"

GOAL: RED test-first stubs for all eight of GE-127d-1's test_spec
    descriptors, driving the (not-yet-authored) reconciliation gate
    ``check_file_size_rule_parity.py``. See ``_ge_127d_1_fixture.py``'s own
    module docstring for the fixture conventions (script-directory-relative
    ``published_rule_surfaces``, the ``DISAGREEMENT`` / ``Compared N
    surface(s)`` vocabulary this file pins, and why the kinds axis is the one
    exercised for bidirectionality).

RED TODAY, FOR TWO DIFFERENT REASONS:
    - Descriptors 1-5 and 7-8 depend on ``check_file_size_rule_parity.py``,
      which does not exist yet -- ``copy_production_modules`` raises
      ``FileNotFoundError`` in ``setUp``, a valid RED state.
    - Descriptor 6 (the inert ``is_new`` flag) is red against the REAL
      production verdict path, ``_classify_file(filepath, is_new,
      previous_lengths)`` -- the function ``main()`` calls at commit time.
      Its verdict comes from ``lines``/``limit``/``previous`` only; ``is_new``
      is never read. (Not the dead, callerless ``check_file()`` -- see the
      test class docstring below.)

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127d-1.yaml and its parent GE-127d.yaml.

DECISION HISTORY
- 2026-09-15 [GE-127d-1/test-writer]: Initial authoring of all eight RED
    test stubs per GE-127d-1's test_spec.
- 2026-09-21 [GE-127d-1/test-writer]: Repointed descriptor 6 (H-1) to
    `_classify_file()`. H-2's new facts live in the sibling file
    `test_ge_127d_1_scope_extension.py` -- this file is at ratchet capacity.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_1_fixture as fx  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_CHECK_FILE_SIZE = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_file_size.py"


class _FixtureTestCase(unittest.TestCase):
    """Shared scaffolding: a fresh temp fixture root."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


class TestPublishedStatementDisagreeingWithEnforcedScopeRefusesCommit(_FixtureTestCase):
    def test_ge_127d_1_a_published_statement_disagreeing_with_the_enforced_scope_refuses_the_commit(self):
        # covers: GE-127d-1
        # angle: criterion
        """NAMED MUTATION 1, DOCUMENTATION SIDE (BA's injection 1). An
        agreeing baseline (both surfaces state exactly the enforced kind)
        must complete cleanly; changing ONE published surface (README.md)
        alone to claim an extra covered kind the enforced scope does not
        have must refuse, naming the disagreement and the surface.
        """
        dest = fx.build_fixture_tree(
            self.root,
            checked_extensions=[".py"],
            readme_extensions=[".py"],
            comment_extensions=[".py"],
        )
        baseline = fx.run_direct(self.root)
        self.assertEqual(
            0, baseline.returncode, msg=f"agreeing baseline must pass. Got: {baseline.stdout!r}{baseline.stderr!r}"
        )

        # NAMED MUTATION 1: README alone now claims .sql too.
        (dest / "README.md").write_text(fx.surface_text([".py", ".sql"]), encoding="utf-8")

        result = fx.run_direct(self.root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"a disagreeing surface must refuse. Got: {combined!r}")
        self.assertIn(fx.DISAGREEMENT_TOKEN, combined, msg=f"the outcome must name the disagreement. Got: {combined!r}")
        self.assertIn("README.md", combined, msg=f"the outcome must name the offending surface. Got: {combined!r}")


class TestChangeToEnforcedScopeAloneAlsoRefusesCommit(_FixtureTestCase):
    def test_ge_127d_1_a_change_to_the_enforced_scope_alone_also_refuses_the_commit(self):
        # covers: GE-127d-1
        # angle: criterion
        """NAMED MUTATION 2, BEHAVIOUR SIDE (BA's injection 2). From an
        agreeing baseline, change the ENFORCED scope alone (add ".sql" to
        checked_extensions) without touching either surface's wording. The
        commit must be refused again -- a check catching only the
        documentation direction is insufficient.
        """
        dest = fx.build_fixture_tree(
            self.root,
            checked_extensions=[".py"],
            readme_extensions=[".py"],
            comment_extensions=[".py"],
        )
        baseline = fx.run_direct(self.root)
        self.assertEqual(0, baseline.returncode, msg=f"agreeing baseline must pass. Got: {baseline.stdout!r}{baseline.stderr!r}")

        # NAMED MUTATION 2: the ENFORCED scope alone widens; no wording changes.
        config_path = dest / "commit_guardian.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["file_size"]["checked_extensions"] = [".py", ".sql"]
        config["file_size"]["line_limits"][".sql"] = 5
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        result = fx.run_direct(self.root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0, result.returncode, msg=f"an enforced-side-only scope change must also refuse. Got: {combined!r}"
        )
        self.assertIn(fx.DISAGREEMENT_TOKEN, combined, msg=f"the outcome must name the disagreement. Got: {combined!r}")
        self.assertIn(".sql", combined, msg=f"the outcome must name the newly-enforced, unstated kind. Got: {combined!r}")


class TestCorrectingOnePublishedSurfaceAndLeavingOtherStaleStillRefuses(_FixtureTestCase):
    def test_ge_127d_1_correcting_one_published_surface_and_leaving_the_other_stale_still_refuses(self):
        # covers: GE-127d-1
        # angle: seam
        """NAMED MUTATION 3, SECOND SURFACE (BA's injection 3). With the
        enforced scope widened to {.py, .sql} and BOTH surfaces initially
        stale (only .py), bring README.md alone into agreement and leave
        commit_guardian.json's `_comment` stale. The commit must still be
        refused, naming the STALE surface only -- proving every published
        place is compared, not just whichever one an implementer happened
        to read.
        """
        dest = fx.build_fixture_tree(
            self.root,
            checked_extensions=[".py", ".sql"],
            readme_extensions=[".py"],
            comment_extensions=[".py"],
        )

        # Correct README ONLY; commit_guardian.json's _comment stays stale.
        (dest / "README.md").write_text(fx.surface_text([".py", ".sql"]), encoding="utf-8")

        result = fx.run_direct(self.root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"the stale second surface must still refuse. Got: {combined!r}")

        lines = fx.disagreement_lines(combined)
        self.assertEqual(
            1,
            len(lines),
            msg=f"exactly the one still-stale surface must be reported disagreeing. Got lines: {lines!r}; full: {combined!r}",
        )
        self.assertIn(
            "commit_guardian.json",
            lines[0],
            msg=f"the reported disagreement must name the STALE surface (commit_guardian.json), not the corrected one. Got: {lines[0]!r}",
        )
        self.assertNotIn(
            "README.md",
            lines[0],
            msg=f"the corrected surface (README.md) must not be reported as disagreeing. Got: {lines[0]!r}",
        )


class TestNewlyAddedPublishedSurfaceIsComparedWithoutChangingCheck(_FixtureTestCase):
    def test_ge_127d_1_a_newly_added_published_surface_is_compared_without_changing_the_check(self):
        # covers: GE-127d-1
        # angle: real_artifact
        """THE ANTI-HARD-CODED-SURFACE-LIST DESCRIPTOR. Adding ONE new
        surface to the CONFIGURED `published_rule_surfaces` list -- with
        disagreeing content -- and changing nothing in the check itself must
        be caught, and the gate's OWN stated surfaces-compared count must
        move by exactly one. No implementation carrying a surface list
        written into itself can pass this.
        """
        dest = fx.build_fixture_tree(
            self.root,
            checked_extensions=[".py"],
            readme_extensions=[".py"],
            comment_extensions=[".py"],
        )
        before = fx.run_direct(self.root)
        before_combined = before.stdout + before.stderr
        self.assertEqual(0, before.returncode, msg=f"agreeing baseline must pass. Got: {before_combined!r}")
        count_before = fx.parse_compared_count(before_combined)
        self.assertIsNotNone(count_before, msg=f"the gate must state how many surfaces it compared. Got: {before_combined!r}")

        extra_name = "extra_surface.md"
        (dest / extra_name).write_text(fx.surface_text([".py", ".sql"]), encoding="utf-8")
        config_path = dest / "commit_guardian.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["file_size"]["published_rule_surfaces"].append(extra_name)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        after = fx.run_direct(self.root)
        after_combined = after.stdout + after.stderr
        self.assertNotEqual(0, after.returncode, msg=f"the newly-added disagreeing surface must refuse. Got: {after_combined!r}")
        self.assertIn(extra_name, after_combined, msg=f"the new surface must be named. Got: {after_combined!r}")

        count_after = fx.parse_compared_count(after_combined)
        self.assertIsNotNone(count_after, msg=f"the gate must state its new surfaces-compared count. Got: {after_combined!r}")
        self.assertEqual(
            count_before + 1,
            count_after,
            msg=(
                "adding exactly one surface to configuration must move the stated "
                f"compared count by exactly one. Before={count_before} After={count_after}"
            ),
        )


class TestUnreadablePublishedSurfaceIsNamedAndNeverReportedAsAgreement(_FixtureTestCase):
    def test_ge_127d_1_an_unreadable_published_surface_is_named_and_never_reported_as_agreement(self):
        # covers: GE-127d-1
        # angle: failure
        """A listed published surface that is GENUINELY missing at run time
        (never written to disk, though configured) must produce the pinned
        INDETERMINATE outcome naming the surface and the reason, exit 2, and
        must never report agreement -- guarding against the four-times-
        shipped shape (KI-CG-034, KI-CG-012, KI-CG-018) where a skipped
        input became a clean verdict.
        """
        fx.build_fixture_tree(
            self.root,
            checked_extensions=[".py"],
            readme_extensions=[".py"],
            comment_extensions=[".py"],
            surfaces=["README.md", "commit_guardian.json", "missing_surface.md"],
        )

        result = fx.run_direct(self.root)
        combined = result.stdout + result.stderr

        self.assertEqual(
            2, result.returncode, msg=f"an unreadable surface must INDETERMINATE (exit 2), never a clean/refused verdict. Got: {combined!r}"
        )
        lines = fx.indeterminate_lines(combined)
        self.assertTrue(lines, msg=f"the pinned INDETERMINATE vocabulary must be emitted. Got: {combined!r}")
        self.assertTrue(
            any("missing_surface.md" in line for line in lines),
            msg=f"the INDETERMINATE line must name the unreadable surface. Got: {lines!r}",
        )


class TestFactAcceptedIntoVerdictThatChangesNothingIsReported(unittest.TestCase):
    """H-1: repointed 2026-09-21 from the dead `check_file()` (zero callers)
    to `_classify_file`, the function `main()` calls at commit time. DIRECT
    CALL, NOT THE CLI: `main()` derives `is_new` from git status, coupling
    it to whether `previous_lengths` has an entry -- a CLI run cannot
    toggle one without disturbing the other. A direct call with an
    IDENTICAL `previous_lengths` dict isolates `is_new` alone.
    """

    def test_ge_127d_1_a_fact_accepted_into_the_verdict_that_changes_nothing_is_reported(self):
        # covers: GE-127d-1
        # angle: criterion
        """`_classify_file(filepath, is_new, previous_lengths)` must NOT
        both accept `is_new` AND let it change nothing. Same file, same
        length, SAME `previous_lengths`, twice: `is_new` True then False.
        RED BASELINE: today it accepts `is_new` and never reads it.
        """
        self.assertTrue(
            _REAL_CHECK_FILE_SIZE.exists(), msg=f"expected the real check_file_size.py at {_REAL_CHECK_FILE_SIZE}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.py"
            probe.write_text("x = 1\ny = 2\n", encoding="utf-8")

            driver = Path(tmp) / "_driver.py"
            driver.write_text(
                "import sys, inspect\n"
                f"sys.path.insert(0, {str(_REAL_CHECK_FILE_SIZE.parent)!r})\n"
                "from check_file_size import _classify_file\n"
                "sig = inspect.signature(_classify_file)\n"
                "params = list(sig.parameters)\n"
                f"path = {str(probe)!r}\n"
                # presence-only: false positive — `params` is
                # list(inspect.signature(_classify_file).parameters) on the LIVE
                # imported function, not the text of check_file_size.py. This is a
                # branch condition selecting which behavioural probe to run, not an
                # assertion: the real assertion below calls _classify_file twice with
                # is_new toggled and asserts the verdicts differ. A source-text check
                # is precisely what this descriptor exists to avoid, since the first
                # version of this fix was green against the callerless check_file().
                "if 'is_new' in params:\n"
                "    r_new = _classify_file(path, True, {})\n"
                "    r_mod = _classify_file(path, False, {})\n"
                "    print('PARAM_PRESENT')\n"
                "    print(r_new == r_mod)\n"
                "else:\n"
                "    r = _classify_file(path, {})\n"
                "    print('PARAM_ABSENT')\n"
                "    print(r)\n",
                encoding="utf-8",
            )
            result = fx.run([fx.PYTHON, str(driver)], Path(tmp))

        self.assertEqual(0, result.returncode, msg=f"the driver itself must run cleanly. stdout={result.stdout!r} stderr={result.stderr!r}")
        lines = result.stdout.strip().splitlines()
        self.assertGreaterEqual(len(lines), 2, msg=f"expected two output lines. Got: {result.stdout!r}")
        mode = lines[0].strip()
        if mode == "PARAM_PRESENT":
            verdicts_equal = lines[1].strip() == "True"
            self.assertFalse(
                verdicts_equal,
                msg=(
                    "_classify_file still accepts is_new as a verdict input AND produces "
                    "the identical verdict regardless of its value -- an accepted-but-inert "
                    "input in the REAL production path main() calls."
                ),
            )
        elif mode == "PARAM_ABSENT":
            pass  # the parameter was removed from the verdict signature -- satisfies the clause.
        else:
            self.fail(f"unexpected driver output: {result.stdout!r}")


class TestReconciliationVerdictEmittedThroughRegisteredHookEntryPoint(_FixtureTestCase):
    def test_ge_127d_1_the_reconciliation_verdict_is_emitted_through_its_registered_hook_entry_point(self):
        # covers: GE-127d-1
        # angle: reachability
        """PRODUCTION ENTRY POINT, PROVED BY CONTRAST. Reachability entry
        point resolved per this ticket's own test_spec[6].surface_invoked
        (copied verbatim, source-of-truth already named it): ``python
        .leafcutter/scripts/commit_guardian/run_hook.py
        .leafcutter/scripts/commit_guardian/check_file_size_rule_parity.py``
        -- mirrored here via the fixture's own minimal single-hook
        `.pre-commit-config.yaml` + a REAL ordinary `git commit`, exactly as
        GE-127a-1's own reachability descriptor does for its sibling gate.
        A disagreement only a direct script call can see is inert -- the
        defect this whole record exists to close.
        """
        fx.build_fixture_tree(
            self.root,
            checked_extensions=[".py"],
            readme_extensions=[".py", ".sql"],  # disagreement baked in from the start
            comment_extensions=[".py"],
        )
        fx.init_repo(self.root)
        fx.write_precommit_config(self.root)
        fx.install_precommit(self.root)

        direct = fx.run_direct(self.root)
        self.assertNotEqual(
            0, direct.returncode, msg=f"fixture sanity: direct invocation must already refuse. Got: {direct.stdout!r}{direct.stderr!r}"
        )

        fx.stage_all(self.root)
        result = fx.commit(self.root, "attempt commit with a disagreement present")
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"the SAME disagreement must ALSO be refused by a REAL ordinary commit through the registered hook path. Output: {combined!r}",
        )
        self.assertIn(fx.DISAGREEMENT_TOKEN, combined, msg=f"the registered hook path's own output must name the disagreement. Got: {combined!r}")
        self.assertIsNotNone(
            fx.parse_compared_count(combined),
            msg=f"the registered hook path's own output must state the surfaces-compared count. Got: {combined!r}",
        )


class TestDeployedCopyReconcilesRealPublishedSurfacesAndComesBackClean(_FixtureTestCase):
    def setUp(self) -> None:
        super().setUp()
        fx.build_deployed_fixture_repo(self.root)

    def test_ge_127d_1_the_deployed_copy_reconciles_the_real_published_surfaces_and_comes_back_clean(self):
        # covers: GE-127d-1
        # angle: deployed
        """After a REAL `build.py` deploy, the DEPLOYED reconciliation gate
        -- over THIS repository's REAL, corrected README.md and
        commit_guardian.json -- must report zero disagreements, a
        surfaces-compared count greater than zero, and exit 0. A helper
        outside templates/scripts/commit_guardian/ with no
        scripts/build_phases.py deploy-map entry surfaces here as
        ModuleNotFoundError rather than passing.

        RED TODAY (per this AC's own test_spec): the gate does not exist yet
        (build.py will not have deployed it), and even once it does, the
        real README.md / commit_guardian.json still carry the stale
        new-files-only claim until the documentation correction lands as
        part of this same ticket.
        """
        deployed_script = fx.deployed_script_path(self.root)
        self.assertTrue(deployed_script.exists(), msg=f"{deployed_script} was not deployed by build.py.")

        result = fx.run([fx.PYTHON, str(deployed_script)], self.root)
        combined = result.stdout + result.stderr

        self.assertNotIn(
            "ModuleNotFoundError", combined, msg=f"the deployed gate crashed importing a dependency. Got: {combined!r}"
        )
        self.assertEqual(
            0, result.returncode, msg=f"over the real, corrected surfaces the deployed gate must exit 0. Got: {combined!r}"
        )
        self.assertNotIn(
            fx.DISAGREEMENT_TOKEN, combined, msg=f"the real, corrected surfaces must report zero disagreements. Got: {combined!r}"
        )
        count = fx.parse_compared_count(combined)
        self.assertIsNotNone(count, msg=f"the gate must state its surfaces-compared count. Got: {combined!r}")
        self.assertGreater(count, 0, msg=f"the stated surfaces-compared count must be greater than zero. Got: {count}")


if __name__ == "__main__":
    unittest.main()
