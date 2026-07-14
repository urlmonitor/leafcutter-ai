"""
MODULE: test_check_component_vocab
GOAL: Unit tests for the CI style guard scripts/check_component_vocab.py, which
      fails when any `components` LIST value is not a canonical docs/components.json
      id (the merge-vector guard).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import check_component_vocab as ccv  # noqa: E402

_REGISTRY = {"components": {"knowledge_system": {}, "ac_store": {}, "build_orchestration": {}}}


def _make_repo(tmp: Path) -> Path:
    (tmp / "docs").mkdir(parents=True)
    (tmp / "docs" / "components.json").write_text(json.dumps(_REGISTRY), encoding="utf-8")
    (tmp / "docs" / "acceptance-criteria").mkdir(parents=True)
    (tmp / "tickets").mkdir(parents=True)
    return tmp


class TestCheckComponentVocab(unittest.TestCase):
    def test_clean_store_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = _make_repo(Path(d))
            (root / "docs" / "acceptance-criteria" / "a.yaml").write_text(
                "id: X\ncomponent: ac-store\ncomponents:\n  - ac_store\n", encoding="utf-8")
            self.assertEqual(ccv.main(["--repo-root", str(root)]), 0)

    def test_kebab_ac_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = _make_repo(Path(d))
            (root / "docs" / "acceptance-criteria" / "a.yaml").write_text(
                "id: X\ncomponents:\n  - build-orchestration\n", encoding="utf-8")
            self.assertEqual(ccv.main(["--repo-root", str(root)]), 1)

    def test_kebab_ticket_frontmatter_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = _make_repo(Path(d))
            (root / "tickets" / "t.md").write_text(
                "---\nid: T\ncomponents:\n- ac-store\n---\nbody\n", encoding="utf-8")
            self.assertEqual(ccv.main(["--repo-root", str(root)]), 1)

    def test_scalar_component_ignored(self):
        # scalar `component` may stay kebab; only the LIST is checked.
        with tempfile.TemporaryDirectory() as d:
            root = _make_repo(Path(d))
            (root / "docs" / "acceptance-criteria" / "a.yaml").write_text(
                "id: X\ncomponent: ac-store\ncomponents:\n  - ac_store\n", encoding="utf-8")
            self.assertEqual(ccv.main(["--repo-root", str(root)]), 0)

    def test_missing_components_is_not_a_violation(self):
        # PRESENCE is not enforced by this style guard.
        with tempfile.TemporaryDirectory() as d:
            root = _make_repo(Path(d))
            (root / "docs" / "acceptance-criteria" / "a.yaml").write_text(
                "id: X\ncomponent: ac-store\n", encoding="utf-8")
            self.assertEqual(ccv.main(["--repo-root", str(root)]), 0)

    def test_missing_registry_returns_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)  # no docs/components.json
            self.assertEqual(ccv.main(["--repo-root", str(root)]), 2)

    def test_scan_reports_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root = _make_repo(Path(d))
            (root / "docs" / "acceptance-criteria" / "a.yaml").write_text(
                "id: X\ncomponents:\n  - bogus-kebab\n", encoding="utf-8")
            registry = ccv.load_registry_ids(root)
            violations = ccv.scan(root, registry)
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0][1], "bogus-kebab")


if __name__ == "__main__":
    unittest.main()
