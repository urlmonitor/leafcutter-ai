"""
MODULE: unit_tests/commit_guardian/test_ge_122d_1_authoring_reachability.py
GOAL: Cover GE-122d-1's ``test_shared_module_imports_from_both_deployed_layouts``
    descriptor AND the reachability gap this AC's own amended_by history
    records as the reason a prior ``work_status: done`` flip was reverted.
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
BUSINESS CONTEXT: GE-122d-1.yaml's own 2026-08-31 "manual" amendment record
    states plainly: "check_identifier_uniqueness_authoring.py appears ZERO
    times in the ten hooks wired in .leafcutter/settings.json. Nothing
    invokes the authoring stage... presence of an artifact is not the same
    as an entry point reaching it, and only the second one is what this
    criterion asks for." It further states the evidence a future done-flip
    needs is "(a) the hook registered where the authoring path actually
    reads it, demonstrated by invoking that path". This test is that
    evidence requirement expressed as a failing assertion: it is not enough
    for the shared module to IMPORT cleanly from a deployed hook file (that
    part already works, see TestSharedModuleAgreesFromDeployedCopies below,
    and unit_tests/commit_guardian/test_ge_122d_6.py's Finding 1 coverage) —
    the authoring stage's PostToolUse registration must also actually exist
    in the deployed hook config, or the module's correctness is unreachable
    from any real Claude Code Edit/Write event.
ARCHITECTURE: Two independent checks:
    1. Deployed-copy agreement (the test_spec descriptor, taken literally):
       copies templates/scripts/commit_guardian/*.py and
       templates/hooks/check_identifier_uniqueness_authoring.py into a
       scratch directory shaped like the real Claude Code deploy depth (a
       "hooks/" sibling of "scripts/commit_guardian/" — see
       check_identifier_uniqueness_authoring.py's own ARCHITECTURE note),
       and confirms the authoring-stage entry point evaluates a REAL
       contested fixture identically to the commit-time module.
    2. Reachability (the manual amendment's actual done-flip bar): reads
       templates/settings.json — the tracked, canonical source ``build_hooks``
       / ``build_claude_settings`` deploys verbatim (confirmed empirically
       2026-09-01: a fresh ``build.py --target-dir`` run's
       ``.claude/settings.json`` and ``.leafcutter/settings.json`` both
       contain zero occurrences of "check_identifier_uniqueness_authoring",
       matching the untouched template) — for a PostToolUse hook entry on
       the ``Edit|Write`` matcher whose command references
       ``check_identifier_uniqueness_authoring.py``. This is the check that
       is RED today.

DOC_LINKS:
  - templates/hooks/check_identifier_uniqueness_authoring.py
  - templates/settings.json
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml

DECISION HISTORY:
  - 2026-09-01 [test-writer/GE-122d-1]: Created. Confirmed RED empirically:
    ``grep -c check_identifier_uniqueness_authoring templates/settings.json``
    returns 0, and a fresh ``build.py --target-dir <tmp>`` run's deployed
    ``.claude/settings.json`` / ``.leafcutter/settings.json`` also both
    return 0 — the hook is registered nowhere in any deployed layout.
"""
from __future__ import annotations

import importlib.util as _ilu
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
_SETTINGS_SRC = _REPO_ROOT / "templates" / "settings.json"

_HOOK_MODULE_BASENAME = "check_identifier_uniqueness_authoring.py"


def _load_module(path: Path, name: str):
    """Load a module fresh from an explicit file path (never from sys.path)."""
    spec = _ilu.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not resolve a module spec/loader for {path}.")
    module = _ilu.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _build_contested_fixture_collection(root: Path) -> None:
    """A real on-disk collection with exactly one AC namespace collision."""
    import yaml

    ac_dir = root / "docs" / "acceptance-criteria" / "fixture-component"
    ac_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("a", "b"):
        (ac_dir / f"CONTESTED-1{suffix}.yaml").write_text(
            yaml.safe_dump({"id": "CONTESTED-1", "title": f"claimant {suffix}"}),
            encoding="utf-8",
        )
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
    tickets_dir = root / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    (tickets_dir / "ticket_lifecycle.json").write_text(json.dumps({"folders": []}), encoding="utf-8")


class TestSharedModuleAgreesFromDeployedCopies(unittest.TestCase):
    """The test_spec descriptor taken literally: the shared module imports
    successfully, and agrees with the commit-time stage, from a deployed
    (Claude Code depth) hook/scripts layout."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.deploy_root = Path(self._tmp.name)

    def test_authoring_stage_agrees_with_commit_stage_from_deployed_layout(self) -> None:
        # covers: GE-122d-1
        # angle: deployed
        scripts_dir = self.deploy_root / "scripts" / "commit_guardian"
        scripts_dir.mkdir(parents=True)
        for src in _SHARED_SRC_DIR.glob("*.py"):
            shutil.copy2(src, scripts_dir / src.name)

        hooks_dir = self.deploy_root / "hooks"
        hooks_dir.mkdir(parents=True)
        deployed_authoring = hooks_dir / _AUTHORING_SRC.name
        shutil.copy2(_AUTHORING_SRC, deployed_authoring)

        with tempfile.TemporaryDirectory() as fixture_tmp:
            fixture_root = Path(fixture_tmp)
            _build_contested_fixture_collection(fixture_root)

            commit_module = _load_module(scripts_dir / _COMMIT_STAGE_SRC.name, "reachability_commit_stage")
            commit_verdict = commit_module.run_uniqueness_pass(fixture_root)
            self.assertFalse(commit_verdict.passed, "Fixture must be contested at the commit-time stage.")

            authoring_module = _load_module(deployed_authoring, "reachability_authoring_stage")
            payload = json.loads(authoring_module.evaluate_identifier_uniqueness(str(fixture_root)))
            self.assertEqual(
                payload["passed"],
                commit_verdict.passed,
                "Authoring stage's `passed` must never disagree with the commit-time "
                "stage's `verdict.passed` on the same collection (GE-122d-1).",
            )
            self.assertIn("CONTESTED-1", payload.get("contested_numbers", []))


class TestAuthoringHookIsRegisteredWhereTheAuthoringPathReadsIt(unittest.TestCase):
    """The reachability half GE-122d-1's own amended_by history demands: the
    module behaving correctly WHEN CALLED is not evidence anything calls
    it. Nothing does, today."""

    def test_authoring_hook_is_wired_into_a_posttooluse_edit_write_hook(self) -> None:
        # covers: GE-122d-1
        # angle: reachability
        settings = json.loads(_SETTINGS_SRC.read_text(encoding="utf-8"))
        post_tool_use = settings.get("hooks", {}).get("PostToolUse", [])

        matching_commands: list[str] = []
        for entry in post_tool_use:
            matcher = entry.get("matcher", "")
            if "Edit" not in matcher and "Write" not in matcher:
                continue
            for hook in entry.get("hooks", []):
                command = hook.get("command", "")
                if _HOOK_MODULE_BASENAME in command:
                    matching_commands.append(command)

        self.assertTrue(
            matching_commands,
            f"{_HOOK_MODULE_BASENAME} is not referenced by any PostToolUse "
            "Edit|Write hook entry in templates/settings.json. GE-122d-1's own "
            "amended_by history (2026-08-31, 'manual') records this as the exact "
            "reason a prior done-flip was reverted: 'Nothing invokes the "
            "authoring stage... presence of an artifact is not the same as an "
            "entry point reaching it'. Wire the authoring hook into a "
            "PostToolUse Edit|Write entry (following the existing "
            "check_exception_handling_hook.py registration as a template) "
            "before this AC can be considered done.",
        )


if __name__ == "__main__":
    unittest.main()
