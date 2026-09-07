"""
MODULE: unit_tests/commit_guardian/test_ge_122d_6.py
GOAL: Regression coverage for the three empirical findings PR #635's review
    raised against templates/hooks/check_identifier_uniqueness_authoring.py.
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
BUSINESS CONTEXT: An empirical (code-run) review of PR #635 found the
    authoring-time stage of GE-122's numbering rule (1) crashed with
    ModuleNotFoundError when deployed to the Antigravity/Gemini hook
    directory, (2) reported a CLEAN verdict on a root where the commit-time
    stage's own disposition fail-closes -- the exact two-stages-disagree
    defect GE-122d-1 exists to forbid -- and (3) could strand a
    half-initialised module in sys.modules on a failed shared-module load.
    Every test below is behavioral: it loads and calls the REAL module
    (never a hand-authored stand-in, never a grep of the source), per this
    repository's documented "Gate / Workflow ACs — Verify Behaviorally, Not
    by Grep" convention.

DECISION HISTORY:
  - 2026-08-31 [python-coder/GE-122d-6]: Created alongside the three fixes
    in templates/hooks/check_identifier_uniqueness_authoring.py. The
    Finding 2 test
    (TestFinding2AuthoringAgreesWithCommitTimeOnUnresolvableNamespace) was
    confirmed RED against the pre-fix code before the fix was applied:
    ``self.assertFalse(payload["passed"], ...)`` failed with
    ``KeyError: 'passed'`` (the pre-fix payload had no such key at all) --
    see the sign-off comment for the exact failure output.
"""
from __future__ import annotations

import importlib.util as ilu
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AUTHORING_SRC = _REPO_ROOT / "templates" / "hooks" / "check_identifier_uniqueness_authoring.py"
_COMMIT_STAGE_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"
_SHARED_SRC_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"


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
    spec = ilu.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not resolve a module spec/loader for {path}.")
    module = ilu.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _build_clean_fixture_collection(root: Path) -> None:
    """A real, fully-resolved collection with zero contested numbers."""
    (root / "docs" / "acceptance-criteria").mkdir(parents=True)
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True)
    (root / "tickets").mkdir(parents=True)
    (root / "tickets" / "ticket_lifecycle.json").write_text('{"folders": []}', encoding="utf-8")


def _build_unresolvable_work_items_fixture(root: Path) -> None:
    """Real, resolved (empty) AC/decisions/diagrams namespaces plus a
    ``tickets/`` directory with NO ``ticket_lifecycle.json`` -- the
    work-items namespace's own documented "root/config could not be
    resolved at all" contract (GE-122e-3), reported as ``passed=False``
    with an EMPTY ``findings`` list. This is the exact root shape PR #635's
    Finding 2 review used to show the two stages disagreeing.
    """
    (root / "docs" / "acceptance-criteria").mkdir(parents=True)
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True)
    (root / "tickets").mkdir(parents=True)
    # Deliberately no ticket_lifecycle.json -- the misconfiguration under test.


class TestFinding1ThreeDeployedLocationsResolveSharedModule(unittest.TestCase):
    """PR #635 Finding 1: the fixed ``parent.parent`` hop resolved the
    source tree and the Claude Code deployment correctly but raised
    ``ModuleNotFoundError`` from the Antigravity/Gemini deployment, which
    sits one directory deeper relative to the shared module. Synthesizes
    all three real deploy depths from the REAL, unmodified template files
    (copied byte-for-byte, following this repo's own
    test_bp_100k_3.py._deploy_commit_guardian_dir precedent) and invokes
    each copy directly -- never a stand-in, never a mock.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)

    def _copy_shared_module_to(self, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src in _SHARED_SRC_DIR.glob("*.py"):
            shutil.copy2(src, dest_dir / src.name)

    def _assert_hook_evaluates_clean(self, hook_path: Path, module_name: str) -> None:
        with tempfile.TemporaryDirectory() as fixture_tmp:
            fixture_root = Path(fixture_tmp)
            _build_clean_fixture_collection(fixture_root)
            module = _load_module(hook_path, module_name)
            payload = json.loads(module.evaluate_identifier_uniqueness(str(fixture_root)))
            self.assertEqual(payload["contested_numbers"], [])
            self.assertTrue(payload["passed"])

    def test_source_tree_layout_resolves(self) -> None:
        # covers: GE-122d-6 Finding 1 (source-tree control case)
        self._assert_hook_evaluates_clean(_AUTHORING_SRC, "f1_source_tree")

    def test_claude_deployed_layout_resolves(self) -> None:
        # covers: GE-122d-6 Finding 1 (one-level-sibling deployed case)
        hooks_dir = self.workspace / ".leafcutter" / "hooks"
        hooks_dir.mkdir(parents=True)
        deployed_hook = hooks_dir / _AUTHORING_SRC.name
        shutil.copy2(_AUTHORING_SRC, deployed_hook)
        self._copy_shared_module_to(self.workspace / ".leafcutter" / "scripts" / "commit_guardian")

        self._assert_hook_evaluates_clean(deployed_hook, "f1_claude_deployed")

    def test_antigravity_deployed_layout_resolves(self) -> None:
        # covers: GE-122d-6 Finding 1 (the actually-broken two-level case)
        hooks_dir = self.workspace / ".leafcutter" / "gemini" / "hooks"
        hooks_dir.mkdir(parents=True)
        deployed_hook = hooks_dir / _AUTHORING_SRC.name
        shutil.copy2(_AUTHORING_SRC, deployed_hook)
        self._copy_shared_module_to(self.workspace / ".leafcutter" / "scripts" / "commit_guardian")

        self._assert_hook_evaluates_clean(deployed_hook, "f1_antigravity_deployed")


class TestFinding2AuthoringAgreesWithCommitTimeOnUnresolvableNamespace(unittest.TestCase):
    """PR #635 Finding 2 (THE SERIOUS ONE): the authoring stage discarded
    ``namespace_verdict.passed`` entirely, so it reported clean
    (``contested_numbers: []``) on a root where the commit-time stage's own
    ``compute_commit_disposition`` fail-closes (``.blocking is True``)
    because of an unresolvable namespace. Constructs that exact
    disagreeing root and asserts the two stages now agree.
    """

    def test_authoring_does_not_report_clean_when_commit_stage_would_block(self) -> None:
        # covers: GE-122d-6 Finding 2
        commit_module = _load_module(_COMMIT_STAGE_SRC, "f2_commit_stage")
        authoring_module = _load_module(_AUTHORING_SRC, "f2_authoring_stage")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_unresolvable_work_items_fixture(root)

            verdict = commit_module.run_uniqueness_pass(root)
            disposition = commit_module.compute_commit_disposition(verdict, [])
            self.assertTrue(
                disposition.blocking,
                "Fixture must reproduce the commit-time stage's fail-closed "
                "outcome (an unresolvable namespace) for this test to be "
                "meaningful.",
            )

            payload = json.loads(authoring_module.evaluate_identifier_uniqueness(str(root)))

            # The unresolvable namespace never produces a Finding (there is
            # nothing to name), so contested_numbers alone stays empty --
            # this is the exact shape that used to be misread as "clean".
            self.assertEqual(payload["contested_numbers"], [])

            # The fix: a caller checking `passed` (or `unresolvable_namespaces`)
            # can never disagree with the commit-time stage's own disposition.
            self.assertFalse(
                payload["passed"],
                "Authoring stage reported passed=True (clean) on a root "
                "where the commit-time stage's own compute_commit_disposition "
                "blocks the commit -- this is the exact two-stages-disagree "
                "defect GE-122d-1 exists to forbid.",
            )
            self.assertIn("work-items", payload["unresolvable_namespaces"])


class TestFinding9FailedLoadDoesNotStrandModuleInSysModules(unittest.TestCase):
    """PR #635 Finding 9: ``sys.modules.setdefault(spec.name, module)`` ran
    BEFORE ``exec_module``, so a failed exec left a half-initialised module
    registered under the shared module's name. Forces a real
    ``exec_module`` failure (a stand-in file that raises at module-execution
    time) and asserts sys.modules is left clean afterward.
    """

    def test_failed_shared_module_load_leaves_no_stranded_sys_modules_entry(self) -> None:
        # covers: GE-122d-6 Finding 9
        authoring_module = _load_module(_AUTHORING_SRC, "f9_authoring_stage")
        shared_name = authoring_module._SHARED_MODULE_NAME

        with tempfile.TemporaryDirectory() as tmp:
            broken_module_path = Path(tmp) / "check_identifier_uniqueness.py"
            broken_module_path.write_text(
                "raise RuntimeError('simulated exec_module failure')\n",
                encoding="utf-8",
            )
            authoring_module._find_shared_module_path = lambda: broken_module_path

            sys.modules.pop(shared_name, None)
            with self.assertRaises(RuntimeError):
                authoring_module._load_shared_uniqueness_module()

            self.assertNotIn(
                shared_name,
                sys.modules,
                "A failed shared-module load left a half-initialised module "
                "registered in sys.modules -- FINDING 9 regression.",
            )


if __name__ == "__main__":
    unittest.main()
