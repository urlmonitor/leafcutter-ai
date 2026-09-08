"""
MODULE: unit_tests/commit_guardian/test_ge_122d_1.py
GOAL: Minimal RED test-first stub for AC GE-122d-1 — "One rule, evaluated at
    three stages, cannot give three different answers".
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml

Asserts the load-bearing test_spec descriptor
(``test_three_stages_agree_on_the_same_contested_collection``): given a real
on-disk fixture collection holding exactly one contested number, all THREE
stage entry points — authoring-time, commit-time, and shared-build — are
actually invoked against it, and all three name the same contested number.

Per this AC's coverage note: "A test asserting that three registrations
point at the same script name does not cover it" — this test therefore
EXECUTES all three stages rather than inspecting a manifest.

STAGE ENTRY POINTS UNDER TEST:
  - Commit-time: templates/scripts/commit_guardian/check_identifier_uniqueness.py
    (EXISTS — built for GE-122a-1 — invoked here via run_uniqueness_pass()).
  - Authoring-time: an equivalent PostToolUse hook under templates/hooks/
    that evaluates the SAME rule at Edit|Write time. Confirmed via a
    directory listing of templates/hooks/ (2026-08-31) that no such hook
    exists yet — there is no authoring-time entry point for identifier
    uniqueness at all today, only a per-file ticket_frontmatter_guard.py.
  - Shared-build: the "AC store valid" CI job running the commit-time hook
    THROUGH pre-commit (per this AC's it_requirements). Not separately
    invoked by this minimal stub; the missing authoring-time stage alone is
    sufficient to make this test RED.

RED AT AUTHORING TIME: there is no authoring-time hook module for identifier
uniqueness anywhere under templates/hooks/, so importing one fails with
ModuleNotFoundError / ImportError before any comparison can be made.
"""
from __future__ import annotations

import importlib.util as _ilu
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_TIME_MODULE = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"
_AUTHORING_TIME_MODULE = _REPO_ROOT / "templates" / "hooks" / "check_identifier_uniqueness_authoring.py"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"


def _load_module(path: Path, name: str):
    """Load a module fresh from an explicit file path (never from sys.path).

    Args:
        path: Absolute path to the .py file to load.
        name: The name to register it under in sys.modules.

    Returns:
        The executed module object.

    Raises:
        ImportError: If no spec (or no loader on the spec) could be resolved
            for ``path`` -- a None spec/loader means the module could not be
            found at all, which should fail loudly here rather than surface
            later as an obscure AttributeError on None.
    """
    spec = _ilu.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not resolve a module spec/loader for {path}.")
    module = _ilu.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _build_contested_fixture_collection(root: Path) -> None:
    """One AC namespace fixture holding exactly one contested number (two
    files both claiming 'GE-999')."""
    ac_dir = root / "docs" / "acceptance-criteria" / "fixture-component"
    ac_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    for suffix in ("a", "b"):
        (ac_dir / f"GE-999{suffix}.yaml").write_text(
            yaml.safe_dump({"id": "GE-999", "title": f"Contested claimant {suffix}"}),
            encoding="utf-8",
        )
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
    (root / "tickets").mkdir(parents=True, exist_ok=True)


class TestGe122d1ThreeStagesAgree(unittest.TestCase):
    def test_three_stages_agree_on_the_same_contested_collection(self) -> None:
        # covers: GE-122d-1
        # angle: reachability
        """The commit-time stage and the authoring-time stage, invoked
        against the SAME fixture collection holding exactly one contested
        number, must name the same contested number.
        """
        self.assertTrue(
            _COMMIT_TIME_MODULE.exists(),
            msg=f"Commit-time stage module missing at {_COMMIT_TIME_MODULE}.",
        )
        commit_mod = _load_module(_COMMIT_TIME_MODULE, "ge122d1_commit_stage")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_contested_fixture_collection(root)

            commit_verdict = commit_mod.run_uniqueness_pass(root)
            self.assertFalse(commit_verdict.passed, "Fixture must be contested at the commit-time stage.")

            # The authoring-time stage must exist and evaluate the SAME rule.
            self.assertTrue(
                _AUTHORING_TIME_MODULE.exists(),
                msg=(
                    f"No authoring-time hook module found at {_AUTHORING_TIME_MODULE}. "
                    "GE-122d-1 requires the SAME rule to be evaluated at authoring time, "
                    "commit time, and shared-build time — verified 2026-08-31 that no "
                    "such module exists under templates/hooks/ today, so the "
                    "authoring-time stage cannot even be invoked, let alone agree with "
                    "the commit-time stage."
                ),
            )
            authoring_mod = _load_module(_AUTHORING_TIME_MODULE, "ge122d1_authoring_stage")
            authoring_payload = json.loads(
                authoring_mod.evaluate_identifier_uniqueness(str(root))
            )
            self.assertIn(
                "GE-999",
                authoring_payload.get("contested_numbers", []),
                msg="Authoring-time stage must name the same contested number as the commit-time stage.",
            )


class TestGe122d1SharedModuleImportsFromBothDeployedLayouts(unittest.TestCase):
    """Covers the ``test_shared_module_imports_from_both_deployed_layouts``
    descriptor by running the REAL ``scripts/build_phases.py`` deploy-phase
    functions -- ``build_hooks`` and ``build_commit_guardian`` -- into a
    fresh temporary target directory, never a hand-shaped scratch copy.

    ``scripts/build_phases.py`` is this ticket's ONLY declared
    ``files_touched`` entry. A source-tree read of
    ``templates/hooks/...`` / ``templates/scripts/commit_guardian/...`` is
    structurally blind to a gap in that file's deploy manifest -- the exact
    failure mode this AC's Implementation Notes name as "THE HARD PART":
    "the authoring stage silently emitting nothing while the other two
    work... invisible to source-tree unit tests." Running the actual
    deploy-phase functions (rather than ``shutil.copy2``-ing files by hand,
    as ``TestSharedModuleAgreesFromDeployedCopies`` in
    test_ge_122d_1_authoring_reachability.py does) is what makes a
    deploy-manifest regression in ``scripts/build_phases.py`` visible to
    this test.
    """

    def setUp(self) -> None:
        if str(_SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS_DIR))
        import build_phases

        self._build_phases = build_phases
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.deploy_root = Path(self._tmp.name)

    def test_shared_module_imports_from_both_deployed_layouts(self) -> None:
        # covers: GE-122d-1
        # angle: deployed
        written_hooks = self._build_phases.build_hooks(self.deploy_root, {}, dry_run=False, force=True)
        written_cg = self._build_phases.build_commit_guardian(self.deploy_root, {}, dry_run=False, force=True)

        self.assertGreater(
            written_hooks,
            0,
            "build_hooks() wrote nothing -- templates/hooks/ deploy manifest is broken.",
        )
        self.assertGreater(
            written_cg,
            0,
            "build_commit_guardian() wrote nothing -- templates/scripts/commit_guardian/ deploy manifest is broken.",
        )

        deployed_authoring = self.deploy_root / "hooks" / "check_identifier_uniqueness_authoring.py"
        deployed_shared = self.deploy_root / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"

        self.assertTrue(
            deployed_authoring.exists(),
            f"build_hooks() did not deploy the authoring-time stage to {deployed_authoring} "
            "-- it would be silently absent from the real .claude/hooks/ / "
            ".leafcutter/hooks/ layout.",
        )
        self.assertTrue(
            deployed_shared.exists(),
            f"build_commit_guardian() did not deploy the shared evaluation module to "
            f"{deployed_shared} -- the commit-time and shared-build stages would be "
            "silently absent from .leafcutter/scripts/commit_guardian/.",
        )

        with tempfile.TemporaryDirectory() as fixture_tmp:
            fixture_root = Path(fixture_tmp)
            _build_contested_fixture_collection(fixture_root)

            deployed_shared_module = _load_module(deployed_shared, "deployed_ge122d1_commit_stage")
            commit_verdict = deployed_shared_module.run_uniqueness_pass(fixture_root)
            self.assertFalse(
                commit_verdict.passed,
                "Fixture must be contested at the DEPLOYED commit-time stage.",
            )

            deployed_authoring_module = _load_module(deployed_authoring, "deployed_ge122d1_authoring_stage")
            payload = json.loads(deployed_authoring_module.evaluate_identifier_uniqueness(str(fixture_root)))

            self.assertEqual(
                payload["passed"],
                commit_verdict.passed,
                "The authoring-time stage, imported from build_hooks()'s ACTUAL deployed "
                "location, must agree with the commit-time stage imported from "
                "build_commit_guardian()'s ACTUAL deployed location -- a deploy-manifest "
                "gap here is invisible to any source-tree-only test.",
            )
            self.assertIn("GE-999", payload.get("contested_numbers", []))


class TestGe122d1ReachableFromEntryPoint(unittest.TestCase):
    """AC GE-122d-1's REQUIRED ``reachability`` angle test
    (``test_ge_122d_1_reachable_from_entry_point``): invoke the REAL
    production entry point -- ``templates/hooks/check_identifier_uniqueness_authoring.py``'s
    ``main()``, the module registered in ``templates/settings.json``'s
    PostToolUse ``Edit|Write`` hook list -- as a subprocess, exactly the way
    Claude Code's own PostToolUse mechanism invokes it: a JSON payload on
    stdin, and an exit code that is the result actually consumed (2 = block,
    with the message fed back to Claude via stderr).

    Entry-point resolution (this file's dispatch contract, "Reachability
    Entry-Point Resolution", Step 1 #2 -- hook via its own runner): this
    hook's "own runner" IS Claude Code invoking ``python <hook path>`` with
    a PostToolUse payload on stdin. Importing
    ``evaluate_identifier_uniqueness`` and calling it directly (as
    ``TestGe122d1ThreeStagesAgree`` above legitimately does, to compare
    verdicts across stages) does NOT satisfy this angle -- it proves the
    function behaves correctly when called, never that Claude Code's own
    invocation shape ever reaches it. This AC's own amended_by history
    records exactly that gap once already: a correctly-behaving module that
    nothing calls is not a working stage.

    completion_manifest.reachability_entry_point_answer:
      result: resolved
      entry_point: "python templates/hooks/check_identifier_uniqueness_authoring.py < <PostToolUse JSON on stdin> (hook via its own runner: Claude Code's PostToolUse mechanism, registered in templates/settings.json)"
    """

    def test_ge_122d_1_reachable_from_entry_point(self) -> None:
        # covers: GE-122d-1
        # angle: reachability
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_contested_fixture_collection(root)

            subprocess.run(["git", "init", "-q"], cwd=root, check=True, timeout=15)
            claimant_a = root / "docs" / "acceptance-criteria" / "fixture-component" / "GE-999a.yaml"
            subprocess.run(
                ["git", "add", str(claimant_a.relative_to(root))],
                cwd=root,
                check=True,
                timeout=15,
            )

            payload = json.dumps({"tool_input": {"file_path": str(claimant_a)}})
            result = subprocess.run(
                [sys.executable, str(_AUTHORING_TIME_MODULE)],
                input=payload,
                capture_output=True,
                text=True,
                cwd=root,
                timeout=15,
            )

            self.assertEqual(
                result.returncode,
                2,
                msg=(
                    "The authoring-time PostToolUse hook, run as a real subprocess "
                    "exactly as Claude Code invokes it (stdin JSON in, exit code as "
                    "the consumed result), must exit 2 (blocking) when a STAGED edit "
                    "is part of a contested numbering collision -- got exit "
                    f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
                ),
            )
            self.assertIn(
                "GE-999",
                result.stderr,
                msg=(
                    "The block message on stderr (what PostToolUse feeds back to "
                    "Claude) must name the contested number."
                ),
            )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/GE-122d-6 fast-lane build set]: Initial minimal
#   RED stub. Confirmed via `ls templates/hooks/` that no authoring-time
#   identifier-uniqueness hook exists; expected to fail on the
#   assertTrue(_AUTHORING_TIME_MODULE.exists()) assertion.
# - 2026-09-01 [python-coder/PR #635 CI fix]: `_load_module` narrowed the
#   `ModuleSpec | None` / `Loader | None` returns from
#   `spec_from_file_location` with an explicit `ImportError` raise instead of
#   the implicit None-attribute access mypy flagged (arg-type / union-attr on
#   spec.loader / module_from_spec). Same defect as test_ge_122d_6.py's
#   `_load_module`, fixed identically.
# - 2026-09-07 [test-writer/GE-122d-1 re-verification pass]: Added
#   TestGe122d1SharedModuleImportsFromBothDeployedLayouts (runs the REAL
#   build_hooks()/build_commit_guardian() deploy-phase functions from
#   scripts/build_phases.py -- this ticket's sole files_touched entry --
#   into a fresh tmp target, replacing the hand-copied scratch-directory
#   proof with one that is actually blind to a regression in that file) and
#   TestGe122d1ReachableFromEntryPoint (the ticket's REQUIRED
#   `angle: reachability` descriptor, previously absent: invokes the
#   authoring-time hook as a real subprocess against a real git repo with a
#   staged contested collision, asserting exit code 2 and the contested
#   number on stderr). BOTH RAN GREEN IMMEDIATELY, not red -- confirmed by
#   architect-review's independent inspection (this AC's evaluation-module
#   reuse, deploy-path ancestor-walk fix, and two rounds of adversarial bug
#   fixes are already on this branch per git history: PR#614, PR#635,
#   f20f4e201, PR#682) and by this test-writer pass itself: no assertion in
#   either test could be weakened to find a real gap. This is a TDD-order
#   exception, not a violation to paper over -- see the sign-off comment's
#   explicit note per this repo's "TDD Order" CLAUDE.md convention. Both
#   tests are retained as real regression coverage tied directly to
#   scripts/build_phases.py (this ticket's sole files_touched entry): a
#   future glob/filter regression in that file's build_hooks() or
#   build_commit_guardian() would turn TestGe122d1SharedModuleImportsFromBothDeployedLayouts
#   red, and a future de-registration of the authoring hook from
#   templates/settings.json's PostToolUse list would turn
#   TestGe122d1ReachableFromEntryPoint red.
# ====================================================================
