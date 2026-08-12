"""
MODULE: unit_tests/commit_guardian/test_done_proof_excludes_fixtures.py
GOAL: The done-proof gate's changed/staged AC discovery must NOT evaluate
      bundled fixture/demo AC copies (e.g. under
      leafcutter-web/fixtures/docs/acceptance-criteria/**). Those are canned
      data for the Atlas to render in mock mode, not real store entries, so
      marking them work_status: done must never trip the proof-of-done gate.

CONTEXT: PR #410 (Atlas mock mode) bundled fixture AC YAMLs whose path contains
    an `acceptance-criteria` segment; the diff-scoped discovery matched them and
    the gate demanded test proof. The discovery predicate now excludes any path
    with a `fixtures` segment. This test exercises that predicate directly.

Same import wiring as test_done_proof_ci_changed_scope.py (deployed
scripts/commit_guardian/check_done_proof.py, created by build.py install_shims).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

from check_done_proof import _is_gated_ac_yaml  # noqa: E402


class TestDoneProofExcludesFixtures(unittest.TestCase):
    def test_real_store_ac_is_gated(self):
        # covers: a genuine repo-root AC YAML is evaluated by the gate.
        rel = Path("docs/acceptance-criteria/ux-prototyping/UXP-596-x/UXP-597.yaml")
        self.assertTrue(_is_gated_ac_yaml(rel))

    def test_fixture_ac_is_excluded(self):
        # covers: a bundled fixture AC copy is NOT evaluated by the gate.
        rel = Path(
            "leafcutter-web/fixtures/docs/acceptance-criteria/"
            "ux-prototyping/UXP-550-atlas-mock-mode/UXP-550.yaml"
        )
        self.assertFalse(_is_gated_ac_yaml(rel))

    def test_any_fixtures_segment_is_excluded(self):
        # covers: the exclusion keys on a `fixtures` path segment anywhere.
        rel = Path("some/pkg/fixtures/docs/acceptance-criteria/AC-1.yaml")
        self.assertFalse(_is_gated_ac_yaml(rel))

    def test_non_yaml_is_excluded(self):
        rel = Path("docs/acceptance-criteria/ux-prototyping/UXP-597.md")
        self.assertFalse(_is_gated_ac_yaml(rel))

    def test_non_ac_yaml_is_excluded(self):
        rel = Path("config/skills_config.default.json.yaml")
        self.assertFalse(_is_gated_ac_yaml(rel))


if __name__ == "__main__":
    unittest.main()
