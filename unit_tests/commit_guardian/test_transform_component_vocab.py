"""
MODULE: test_transform_component_vocab
GOAL: Unit tests for the transform-component-vocab pre-stage guard that
      auto-normalises stray `components` LIST values to the canonical
      docs/components.json vocabulary before validators run.
BUSINESS CONTEXT: Merges of pre-migration branches keep reintroducing kebab
      component ids; this transformer heals them non-disruptively. These tests
      pin the rewrite behaviour against both YAML block-list indent styles and
      confirm the scalar `component`, other list fields, and already-valid ids
      are never touched.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CG_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
sys.path.insert(0, str(_CG_DIR))

import transform_component_vocab as tcv  # noqa: E402

# A registry where knowledge_management is valid (mirrors post-#274 state).
_REG = {
    "build_orchestration", "ac_store", "commit_guardian", "knowledge_management",
    "build_pipeline", "testing_quality", "precommit_hooks", "documentation_system",
}


def _write(d: Path, name: str, body: str) -> Path:
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


class TestRewriteBlock(unittest.TestCase):
    def test_column0_kebab_normalised(self):  # ticket style
        text = "id: T-1\ncomponents:\n- build-orchestration\n- ac-store\n"
        new, changed = tcv.rewrite_components_block(text, _REG)
        self.assertEqual(changed, 2)
        self.assertIn("- build_orchestration", new)
        self.assertIn("- ac_store", new)
        self.assertNotIn("build-orchestration", new)

    def test_indented_kebab_normalised(self):  # AC style
        text = "id: X\ncomponents:\n  - ac-store\n  - guardrail-engine\n"
        new, changed = tcv.rewrite_components_block(text, _REG)
        self.assertEqual(changed, 2)
        self.assertIn("  - ac_store", new)
        self.assertIn("  - commit_guardian", new)  # guardrail-engine -> commit_guardian

    def test_valid_value_untouched(self):
        text = "components:\n- knowledge_management\n"
        new, changed = tcv.rewrite_components_block(text, _REG)
        self.assertEqual(changed, 0)
        self.assertIn("- knowledge_management", new)

    def test_scalar_component_untouched(self):
        text = "component: ac-store\ncomponents:\n  - ac-store\n"
        new, changed = tcv.rewrite_components_block(text, _REG)
        self.assertEqual(changed, 1)
        self.assertIn("component: ac-store", new)  # scalar kebab preserved
        self.assertIn("  - ac_store", new)

    def test_unmapped_value_left_alone(self):
        text = "components:\n- totally_unknown\n"
        new, changed = tcv.rewrite_components_block(text, _REG)
        self.assertEqual(changed, 0)
        self.assertIn("- totally_unknown", new)

    def test_dedup_after_remap(self):
        # ac-store and ac_store collapse to a single ac_store entry.
        text = "components:\n- ac-store\n- ac_store\n"
        new, _ = tcv.rewrite_components_block(text, _REG)
        self.assertEqual(new.count("- ac_store"), 1)


class TestTransformFile(unittest.TestCase):
    def test_md_frontmatter_only(self):
        with tempfile.TemporaryDirectory() as d:
            body = (
                "---\nid: T\ncomponents:\n- build-orchestration\n"
                "files_touched:\n- scripts/x.py\n---\n"
                "prose mentioning build-orchestration should be untouched\n"
            )
            p = _write(Path(d), "t.md", body)
            changed = tcv.transform_file(p, _REG)
            self.assertEqual(changed, 1)
            out = p.read_text()
            self.assertIn("- build_orchestration", out)
            self.assertIn("- scripts/x.py", out)  # other list untouched
            self.assertIn("prose mentioning build-orchestration", out)  # body untouched

    def test_yaml_ac(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), "a.yaml", "id: X\ncomponent: ac-store\ncomponents:\n  - ac-store\n")
            changed = tcv.transform_file(p, _REG)
            self.assertEqual(changed, 1)
            self.assertIn("  - ac_store", p.read_text())

    def test_empty_registry_noop(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), "a.yaml", "components:\n  - ac-store\n")
            # rewrite treats empty registry: nothing is "in registry", but REMAP
            # still applies — guard against empty-registry is in main(), not here.
            changed = tcv.transform_file(p, set())
            # ac-store is not in empty registry but is in REMAP -> still normalised
            self.assertEqual(changed, 1)


if __name__ == "__main__":
    unittest.main()
