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
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_TIME_MODULE = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"
_AUTHORING_TIME_MODULE = _REPO_ROOT / "templates" / "hooks" / "check_identifier_uniqueness_authoring.py"


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
# ====================================================================
