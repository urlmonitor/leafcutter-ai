"""
MODULE: unit_tests/commit_guardian/test_ge_122d_1_no_stage_disagreement.py
GOAL: Cover GE-122d-1's ``test_no_stage_reports_clean_while_another_reports_contested``
    descriptor: across a matrix of fixture collections spanning clean,
    contested, and unresolvable-namespace shapes, the commit-time and
    authoring-time stages must never disagree on ``passed``.
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
BUSINESS CONTEXT: This is a data-driven regression lock, not a
    single-scenario check -- GE-122d-1's coverage note forbids a test that
    only proves agreement on ONE case ("A test asserting that three
    registrations point at the same script name does not cover it"). Each
    fixture below is real, on-disk, and built the same way this AC's other
    tests build one (see test_ge_122d_1.py / test_ge_122d_6.py precedent),
    never a hand-typed verdict literal.
ARCHITECTURE: Parameterised over four real fixture shapes: (1) fully clean
    and resolved, (2) AC-namespace collision, (3) diagrams-namespace
    collision, (4) work-items namespace unresolvable (missing
    ticket_lifecycle.json -- the exact shape PR #635 Finding 2 fixed). Both
    stages are loaded fresh per fixture (via a fresh scratch deploy copy) and
    invoked against it; the test asserts ``commit_verdict.passed ==
    authoring_payload["passed"]`` for every one.

DOC_LINKS:
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/hooks/check_identifier_uniqueness_authoring.py
  - unit_tests/commit_guardian/test_ge_122d_6.py (Finding 2 fix this locks in)

DECISION HISTORY:
  - 2026-09-01 [test-writer/GE-122d-1]: Created.
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


def _load_module(path: Path, name: str):
    spec = _ilu.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not resolve a module spec/loader for {path}.")
    module = _ilu.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _fixture_clean(root: Path) -> None:
    (root / "docs" / "acceptance-criteria").mkdir(parents=True)
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True)
    (root / "tickets").mkdir(parents=True)
    (root / "tickets" / "ticket_lifecycle.json").write_text(json.dumps({"folders": []}), encoding="utf-8")


def _fixture_ac_collision(root: Path) -> None:
    import yaml

    _fixture_clean(root)
    ac_dir = root / "docs" / "acceptance-criteria" / "fixture-component"
    ac_dir.mkdir(parents=True)
    for suffix in ("a", "b"):
        (ac_dir / f"MATRIX-1{suffix}.yaml").write_text(
            yaml.safe_dump({"id": "MATRIX-1", "title": f"claimant {suffix}"}),
            encoding="utf-8",
        )


def _fixture_diagram_collision(root: Path) -> None:
    _fixture_clean(root)
    diagrams = root / "docs" / "architecture" / "diagrams"
    (diagrams / "c1-001-alpha.md").write_text("# alpha\n", encoding="utf-8")
    (diagrams / "c1-001-beta.md").write_text("# beta\n", encoding="utf-8")


def _fixture_work_items_unresolvable(root: Path) -> None:
    (root / "docs" / "acceptance-criteria").mkdir(parents=True)
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True)
    (root / "tickets").mkdir(parents=True)
    # Deliberately no ticket_lifecycle.json.


_FIXTURES = {
    "clean": _fixture_clean,
    "ac_collision": _fixture_ac_collision,
    "diagram_collision": _fixture_diagram_collision,
    "work_items_unresolvable": _fixture_work_items_unresolvable,
}


class TestNoStageDisagreesAcrossFixtureMatrix(unittest.TestCase):
    def setUp(self) -> None:
        self._scratch_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._scratch_tmp.cleanup)
        scratch_root = Path(self._scratch_tmp.name)

        scripts_dir = scratch_root / "scripts" / "commit_guardian"
        scripts_dir.mkdir(parents=True)
        for src in _SHARED_SRC_DIR.glob("*.py"):
            shutil.copy2(src, scripts_dir / src.name)
        self.deployed_commit = scripts_dir / _COMMIT_STAGE_SRC.name

        hooks_dir = scratch_root / "hooks"
        hooks_dir.mkdir(parents=True)
        self.deployed_authoring = hooks_dir / _AUTHORING_SRC.name
        shutil.copy2(_AUTHORING_SRC, self.deployed_authoring)

    def test_no_stage_reports_clean_while_another_reports_contested(self) -> None:
        # covers: GE-122d-1
        # angle: boundary
        disagreements = []
        for label, builder in _FIXTURES.items():
            with tempfile.TemporaryDirectory() as fixture_tmp:
                fixture_root = Path(fixture_tmp)
                builder(fixture_root)

                commit_module = _load_module(self.deployed_commit, f"matrix_commit_{label}")
                commit_verdict = commit_module.run_uniqueness_pass(fixture_root)

                authoring_module = _load_module(self.deployed_authoring, f"matrix_authoring_{label}")
                payload = json.loads(authoring_module.evaluate_identifier_uniqueness(str(fixture_root)))

                if commit_verdict.passed != payload["passed"]:
                    disagreements.append(
                        {
                            "fixture": label,
                            "commit_passed": commit_verdict.passed,
                            "authoring_passed": payload["passed"],
                        }
                    )

        self.assertEqual(
            [],
            disagreements,
            "One or more fixtures produced a clean verdict at one stage and a "
            f"contested verdict at another (GE-122d-1 forbids this): {disagreements}",
        )


if __name__ == "__main__":
    unittest.main()
