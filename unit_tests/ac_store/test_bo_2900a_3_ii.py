"""
MODULE: unit_tests/ac_store/test_bo_2900a_3_ii.py
COVERS: BO-2900a-3

GOAL: Rework-round RED tests for the two findings pr-reviewer (2026-09-25
    19:15) and ac-validator (2026-09-25 19:40) raised against
    test_bo_2900a_3.py's original four tests, per ticket-supervisor's
    2026-09-27 20:49 handoff comment:

    1. AC-2 -- "no automation runs that unit as a program" is the THIRD of
       the three enumerated conditions this AC's own it_requirements
       constraint #1 requires ALL to hold before refusing a unit with
       refusal_cause 'no_entry_point_reaches_code'. Today
       ``_apply_reachability_gate`` (scripts/ac_store/done_proof.py) never
       consults the automation-invocation seam at all -- it evaluates only
       conditions (1) and (2) (no main() of its own; not genuinely imported
       elsewhere). A unit that IS run as a program by a real automation
       script must therefore NOT be refused with this cause; the same unit
       with no automation invocation at all must still be refused (the
       paired negative). The automation seam this condition depends on is
       BO-2900b-1/BO-2900b-3's ``collected_invocations(script_paths)``,
       re-exported from ``scripts/commit_guardian/_reachability_inventory``
       (implemented in the sibling module
       ``_reachability_invocation_collector.py``) -- now present on this
       branch (PR #918 / BO-2900b-1 merged to main and merged into this
       ticket's branch, per the handoff comment). This test file uses the
       REAL, unmocked ``collected_invocations()`` twice: once as a
       self-check that the fixture automation script is shaped the way the
       real collector recognises (an AST-based scan of a real on-disk
       script, never a hand-typed invocation list), and implicitly again
       inside ``verify_done_eligible`` once python-coder wires condition (3)
       to this seam.

    2. clearing_actions -- BO-2900a-3.yaml's own
       ``config_schema_fragment.no_way_in_verdict`` and this ticket's
       "Delivers To" Agent Contract both specify the refusal verdict shape
       as carrying ``clearing_actions: ["give the unit an entry point",
       "record an exemption"]`` (consumed by
       ``scripts/commit_guardian/check_done_proof.py`` and by BO-2900e-1's
       second message). ``_apply_reachability_gate``'s return dict
       (done_proof.py:~2098-2109) does not include this key today.

=== Red baseline (this round) ===

    Both new tests below call the REAL, unmodified ``verify_done_eligible``.

    - ``test_automation_invocation_of_the_unit_clears_the_refusal_but_its_absence_does_not``
      is RED today: condition (3) is never evaluated, so the automation-
      reached unit is refused with ``no_entry_point_reaches_code`` exactly
      like the unreached one -- the ``assertNotEqual`` on the "with
      automation" verdict fails.
    - ``test_refusal_verdict_carries_the_two_named_clearing_actions`` is RED
      today: the refusal dict has no ``clearing_actions`` key at all, so
      ``verdict.get("clearing_actions")`` is ``None``, not the two-item list
      the AC's schema fragment requires.

    Shared fixture helpers (write_ac, write_fixture_file,
    init_git_fixture_project) come from
    unit_tests/ac_store/_bo_2900a_1_fixtures.py, the same seam
    test_bo_2900a_3.py and test_bo_2900a_1*.py already use. This file's own
    fixture unit omits the docstring-decoy file test_bo_2900a_3.py's
    fixtures use -- that decoy targeted a since-fixed regex-text-scan bug in
    ``_is_imported_elsewhere`` unrelated to the automation condition or
    clearing_actions this file tests.

=== Rework round two (pr-reviewer 2026-09-27 21:57 blocker) ===

    ``unit_is_invoked_by_automation`` (scripts/ac_store/_done_proof_automation_gate.py)
    compares ``invocation.surface`` against ``unit_absolute`` -- an ABSOLUTE,
    OS-native-separator string -- via bare ``==``. ``invocation.surface`` is
    returned VERBATIM from whatever literal the automation script author
    wrote (see ``_reachability_invocation_collector.py::_invocation_from_call``),
    with no normalisation applied unless the literal happens to use the one
    recognised ``Path(__file__).resolve().parent / "x.py"`` idiom. A
    realistic, project-root-relative, forward-slash literal -- e.g.
    ``subprocess.run([sys.executable, "scripts/the_unit.py", "run"])`` with
    the project root as cwd, the exact style ``scripts/commit_guardian/
    run_hook.py``-style automation in this repo actually uses -- therefore
    NEVER matches, and the unit is wrongly refused despite real automation
    running it.

    Two new tests below (both call the REAL, unmodified ``verify_done_eligible``
    and the REAL, unmocked ``collected_invocations``, with a real on-disk
    automation-script fixture -- no hand-typed invocation list):

    1. ``test_automation_invocation_via_project_relative_forward_slash_literal_clears_the_refusal``
       -- a project-root-relative, forward-slash literal naming the REAL unit
       must clear the refusal. RED today (the exact gap pr-reviewer flagged):
       the literal ``surface`` never equals the absolute, native-separator
       ``unit_absolute`` the current comparison builds.
    2. ``test_relative_literal_naming_a_different_same_basename_file_does_not_clear_the_refusal``
       -- a guard against over-matching: a relative literal naming a
       DIFFERENT file that merely shares the real unit's basename, in
       another folder, must NOT clear the refusal. This may already be
       GREEN today (the current comparison never matches any relative
       literal at all, correct-by-accident for this negative case) -- kept
       as a guard so a future "match by basename" fix cannot silently pass.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900a_1_fixtures import (  # noqa: E402
    init_git_fixture_project,
    write_ac,
    write_fixture_file,
)

from done_proof import verify_done_eligible  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

from _reachability_inventory import collected_invocations  # noqa: E402


def _write_unit_and_test(root: Path, ac_id: str) -> tuple[Path, Path, Path]:
    """Build a fixture unit with no way in of its own (no ``main()``, not
    genuinely imported by any other project file) and a covers-tagged test
    that imports it directly and passes.

    Returns (ac_root, test_root, unit_path).
    """
    ac_root = root / "acs"
    test_root = root / "tests"
    src_dir = root / "src"
    write_ac(ac_root, ac_id)
    unit_path = write_fixture_file(
        src_dir,
        "no_entry_unit.py",
        "def do_thing():\n    return 42\n",
    )
    write_fixture_file(
        test_root,
        "test_direct_import.py",
        "import sys\n"
        f"sys.path.insert(0, {str(src_dir)!r})\n"
        "from no_entry_unit import do_thing\n\n\n"
        "def test_fixture_unit_via_direct_import():\n"
        f"    # covers: {ac_id}\n"
        "    assert do_thing() == 42\n",
    )
    return ac_root, test_root, unit_path


def _write_automation_script_invoking_unit(
    automation_dir: Path, unit_path: Path, capability: str = "run"
) -> Path:
    """Write a REAL, on-disk automation script that runs *unit_path* as a
    program via ``subprocess.run([sys.executable, <unit path>,
    <capability>], ...)`` -- the exact shape
    ``_reachability_invocation_collector.collected_invocations()``
    recognises: a literal argv list passed to a ``subprocess.run``/``call``/
    ``check_call``/``check_output``/``Popen`` Call node whose first
    ``.py``-suffixed resolved token is the "surface" and whose very next
    resolved, non-flag token is the "capability" (see that module's
    ``_is_subprocess_run_call`` / ``_invocation_from_call``). The unit path
    is bound to a module-level constant (``UNIT_PATH``) rather than inlined
    as a bare literal in the call, mirroring
    ``_module_level_string_bindings``'s own documented resolution shape.

    Returns the automation script's own path.
    """
    automation_dir.mkdir(parents=True, exist_ok=True)
    script_path = automation_dir / "run_the_unit.py"
    script_path.write_text(
        "import subprocess\n"
        "import sys\n\n"
        f"UNIT_PATH = {str(unit_path)!r}\n\n\n"
        "def main() -> int:\n"
        f"    subprocess.run([sys.executable, UNIT_PATH, {capability!r}], check=False)\n"
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n'
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    return script_path


def _write_automation_script_with_literal_relative_surface(
    automation_dir: Path, relative_posix_surface: str, capability: str = "run"
) -> Path:
    """Write a REAL, on-disk automation script whose argv names its surface
    with a BARE STRING LITERAL -- e.g. ``"scripts/the_unit.py"`` -- rather
    than the ``UNIT_PATH`` module-level-binding-of-an-absolute-path idiom
    :func:`_write_automation_script_invoking_unit` uses. This is the exact,
    realistic shape pr-reviewer's 2026-09-27 21:57 finding names: a
    project-root-relative, forward-slash literal, the style this codebase's
    own automation (e.g. ``scripts/commit_guardian/run_hook.py``-style
    scripts) actually favours. The literal is inlined directly in the
    ``subprocess.run([...])`` call -- a plain ``ast.Constant`` string, so
    ``_argv_literal_tokens`` resolves it with no binding lookup at all.

    Args:
        automation_dir: Directory to write the script into (must be inside
            *project_root* but outside both *ac_root* and *test_root* for
            the caller's fixture shape).
        relative_posix_surface: The literal surface string to embed verbatim
            in the script's argv list (already forward-slash, project-root-
            relative -- this function does not transform it further).
        capability: The capability token to embed after the surface.

    Returns:
        The automation script's own path.
    """
    automation_dir.mkdir(parents=True, exist_ok=True)
    script_path = automation_dir / "run_the_unit_relative_literal.py"
    script_path.write_text(
        "import subprocess\n"
        "import sys\n\n\n"
        "def main() -> int:\n"
        f"    subprocess.run([sys.executable, {relative_posix_surface!r}, "
        f"{capability!r}], check=False)\n"
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n'
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    return script_path


class TestAutomationInvocationClearsTheNoEntryPointRefusal(unittest.TestCase):
    """AC-2 (BO-2900a-3): condition (3) -- 'no automation runs that unit as
    a program' -- is one of three conditions that must ALL hold before the
    'no_entry_point_reaches_code' refusal fires. A unit with no main() of
    its own (condition 1) and imported by nothing else (condition 2), but
    run as a program by a real, on-disk automation script, must NOT be
    refused with this cause. The paired negative: the same unit shape with
    no automation invocation anywhere must still be refused."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_automation_invocation_of_the_unit_clears_the_refusal_but_its_absence_does_not(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: criterion
        # --- (1) WITH a real automation script invoking the unit ---
        ac_id_with = "BO-TEST-2900A3-AUTOMATION-YES"
        ac_root_with, test_root_with, unit_path_with = _write_unit_and_test(
            self.root / "with-automation", ac_id_with
        )
        automation_script = _write_automation_script_invoking_unit(
            self.root / "with-automation" / "automation", unit_path_with
        )

        # Sanity-check the fixture's OWN shape against the REAL, unmocked
        # collector before asserting anything about verify_done_eligible --
        # if this assertion ever fails, the fixture (not done_proof.py)
        # needs fixing, because it would mean the automation script is not
        # shaped the way BO-2900b-1/BO-2900b-3's own collector recognises a
        # real invocation.
        invocations = collected_invocations([automation_script])
        self.assertTrue(
            any(inv.surface == str(unit_path_with) for inv in invocations),
            f"fixture automation script must be recognised by the real "
            f"collected_invocations() as invoking {unit_path_with}, got: "
            f"{invocations}",
        )

        verdict_with_automation = verify_done_eligible(
            ac_id_with, ac_root=ac_root_with, test_root=test_root_with
        )
        self.assertNotEqual(
            verdict_with_automation.get("refusal_cause"),
            "no_entry_point_reaches_code",
            f"a unit with no main() of its own and imported by nothing "
            f"else, but run as a program by a real automation script, must "
            f"NOT be refused as no_entry_point_reaches_code (condition 3 -- "
            f"'no automation runs that unit as a program' -- does not "
            f"hold), got: {verdict_with_automation}",
        )
        self.assertTrue(
            verdict_with_automation.get("eligible"),
            f"expected the automation-reached unit to be eligible, got: "
            f"{verdict_with_automation}",
        )

        # --- (2) paired negative: the SAME unit shape, but no automation
        # invocation anywhere -- must still be refused ---
        ac_id_without = "BO-TEST-2900A3-AUTOMATION-NO"
        ac_root_without, test_root_without, _unit_path_without = _write_unit_and_test(
            self.root / "without-automation", ac_id_without
        )
        verdict_without_automation = verify_done_eligible(
            ac_id_without, ac_root=ac_root_without, test_root=test_root_without
        )
        self.assertFalse(
            verdict_without_automation.get("eligible"),
            f"expected the unreached unit (no automation invocation at "
            f"all) to be refused, got: {verdict_without_automation}",
        )
        self.assertEqual(
            verdict_without_automation.get("refusal_cause"),
            "no_entry_point_reaches_code",
            f"expected the BO-2900a-3 refusal_cause for the unreached "
            f"unit, got: {verdict_without_automation}",
        )


class TestRefusalCarriesClearingActions(unittest.TestCase):
    """config_schema_fragment.no_way_in_verdict (BO-2900a-3.yaml) and this
    ticket's 'Delivers To' Agent Contract both specify that the
    no_entry_point_reaches_code refusal verdict carries
    clearing_actions == ['give the unit an entry point', 'record an
    exemption'] -- consumed by check_done_proof.py and by BO-2900e-1's
    second message. pr-reviewer (2026-09-25 19:15) and ac-validator
    (2026-09-25 19:40) both flagged this field as missing."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)
        self.ac_id = "BO-TEST-2900A3-CLEARING"
        self.ac_root, self.test_root, self.unit_path = _write_unit_and_test(
            self.root, self.ac_id
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_refusal_verdict_carries_the_two_named_clearing_actions(self) -> None:
        # covers: BO-2900a-3
        # angle: criterion
        verdict = verify_done_eligible(
            self.ac_id, ac_root=self.ac_root, test_root=self.test_root
        )
        self.assertFalse(
            verdict.get("eligible"),
            f"expected the unreached unit to be refused, got: {verdict}",
        )
        self.assertEqual(
            verdict.get("refusal_cause"),
            "no_entry_point_reaches_code",
            f"expected the BO-2900a-3 refusal_cause, got: {verdict}",
        )
        self.assertEqual(
            verdict.get("clearing_actions"),
            ["give the unit an entry point", "record an exemption"],
            f"the no_entry_point_reaches_code refusal must carry the two "
            f"clearing_actions named in BO-2900a-3.yaml's "
            f"config_schema_fragment.no_way_in_verdict and this ticket's "
            f"Delivers-To contract, got: {verdict}",
        )


class TestRelativeForwardSlashSurfaceLiteralMatching(unittest.TestCase):
    """pr-reviewer (2026-09-27 21:57 blocker): ``unit_is_invoked_by_automation``
    compares ``invocation.surface`` (the VERBATIM literal an automation
    script author wrote) against ``unit_absolute`` -- an absolute,
    OS-native-separator string -- via bare ``==``. A realistic,
    project-root-relative, forward-slash literal (e.g.
    ``subprocess.run([sys.executable, "scripts/the_unit.py", "run"])``, the
    style this repo's own ``run_hook.py``-style automation favours) never
    equals that absolute, native-separator form, so the unit is wrongly
    refused despite real automation running it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_automation_invocation_via_project_relative_forward_slash_literal_clears_the_refusal(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: discrimination
        project_root = self.root / "relative-literal-clears"
        ac_id = "BO-TEST-2900A3-RELATIVE-LITERAL-YES"
        ac_root, test_root, unit_path = _write_unit_and_test(project_root, ac_id)

        # The unit's path, as it would be authored by a real automation
        # script naming its target relative to the project root, with
        # portable forward slashes -- exactly the literal shape pr-reviewer's
        # finding names, and exactly what _find_no_entry_point_unit computes
        # internally via project_root-relative resolution.
        relative_posix_surface = unit_path.relative_to(project_root).as_posix()
        self.assertIn(
            "/",
            relative_posix_surface,
            "fixture setup: the unit must live below a subdirectory of "
            "project_root so the relative literal is genuinely multi-segment "
            "(not merely a bare filename), matching a realistic automation "
            f"literal -- got: {relative_posix_surface}",
        )

        automation_script = _write_automation_script_with_literal_relative_surface(
            project_root / "automation", relative_posix_surface
        )

        # Sanity-check the fixture's OWN shape against the REAL, unmocked
        # collector before asserting anything about verify_done_eligible --
        # confirms collected_invocations() reports the surface VERBATIM as
        # authored (relative, forward-slash), never silently resolved to an
        # absolute path by the collector itself.
        invocations = collected_invocations([automation_script])
        self.assertTrue(
            any(inv.surface == relative_posix_surface for inv in invocations),
            f"fixture automation script must be recognised by the real "
            f"collected_invocations() as invoking {relative_posix_surface!r} "
            f"verbatim, got: {invocations}",
        )

        verdict = verify_done_eligible(ac_id, ac_root=ac_root, test_root=test_root)
        self.assertNotEqual(
            verdict.get("refusal_cause"),
            "no_entry_point_reaches_code",
            f"a unit run as a program by a real automation script via a "
            f"project-root-relative, forward-slash literal ({relative_posix_surface!r}) "
            f"must NOT be refused as no_entry_point_reaches_code -- condition "
            f"(3) does not hold, got: {verdict}",
        )
        self.assertTrue(
            verdict.get("eligible"),
            f"expected the automation-reached unit to be eligible, got: {verdict}",
        )

    def test_relative_literal_naming_a_different_same_basename_file_does_not_clear_the_refusal(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: discrimination
        # Guard against over-matching: a plausible WRONG fix would match by
        # basename (or by any looser criterion than the full resolved path),
        # which would wrongly clear the refusal for a unit that automation
        # never actually reaches. This test may already be green today (the
        # current comparison never matches ANY relative literal, correct by
        # accident for this negative case) -- kept so a future fix cannot
        # silently regress into basename-only matching.
        project_root = self.root / "relative-literal-decoy"
        ac_id = "BO-TEST-2900A3-RELATIVE-LITERAL-DECOY"
        ac_root, test_root, unit_path = _write_unit_and_test(project_root, ac_id)
        real_relative_surface = unit_path.relative_to(project_root).as_posix()

        # A DIFFERENT file, sharing the real unit's basename, in another
        # folder -- never the file the covers-tagged test actually imports.
        decoy_path = write_fixture_file(
            project_root / "other",
            unit_path.name,
            "def do_thing():\n    return 999\n",
        )
        decoy_relative_surface = decoy_path.relative_to(project_root).as_posix()
        self.assertNotEqual(
            real_relative_surface,
            decoy_relative_surface,
            "fixture setup: the decoy must live at a genuinely different "
            "relative path from the real unit despite sharing its basename",
        )

        automation_script = _write_automation_script_with_literal_relative_surface(
            project_root / "automation", decoy_relative_surface
        )

        invocations = collected_invocations([automation_script])
        self.assertTrue(
            any(inv.surface == decoy_relative_surface for inv in invocations),
            f"fixture automation script must be recognised by the real "
            f"collected_invocations() as invoking the DECOY "
            f"{decoy_relative_surface!r}, got: {invocations}",
        )
        self.assertFalse(
            any(inv.surface == real_relative_surface for inv in invocations),
            "fixture setup: no invocation should name the real unit's own "
            "relative path in this decoy-only scenario",
        )

        verdict = verify_done_eligible(ac_id, ac_root=ac_root, test_root=test_root)
        self.assertFalse(
            verdict.get("eligible"),
            f"automation invoking a DIFFERENT, same-basename file must NOT "
            f"clear the refusal for the real, unreached unit, got: {verdict}",
        )
        self.assertEqual(
            verdict.get("refusal_cause"),
            "no_entry_point_reaches_code",
            f"expected the BO-2900a-3 refusal_cause for the unit that no "
            f"automation actually reaches, got: {verdict}",
        )


if __name__ == "__main__":
    unittest.main()
