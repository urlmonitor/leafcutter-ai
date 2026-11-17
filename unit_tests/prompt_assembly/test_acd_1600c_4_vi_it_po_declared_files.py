"""ACD-1600c-4-vi: the IT product owner's enrichment output includes declared_files.

The it-po template's output contract and worked example must teach the
`declared_files` field. The worked example's "After enrichment" record is
parsed with the real YAML parser and run through the real validator
(scripts/ac_store/declared_files.py), so the test asserts the record the agent
is shown how to emit is one the pipeline accepts and the test designer can read.
"""

import re
import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ac_store"))
sys.path.insert(0, str(REPO_ROOT))

from scripts.ac_store import declared_files as df  # noqa: E402

TEMPLATE = REPO_ROOT / "templates" / "agents" / "it-po.md"


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _frontmatter() -> dict:
    match = re.match(r"---\n(.*?)\n---\n", _template_text(), re.DOTALL)
    assert match, "it-po.md has no frontmatter"
    return yaml.safe_load(match.group(1))


def _example_records() -> tuple[dict, dict]:
    """Return (before, after) records parsed from the Few-Shot Example."""
    body = _template_text().split("## Few-Shot Example", 1)[1]
    blocks = re.findall(r"```yaml\n(.*?)\n```", body, re.DOTALL)
    assert len(blocks) >= 2, "expected before/after YAML blocks in the example"
    return yaml.safe_load(blocks[0]), yaml.safe_load(blocks[1])


class TestItPoDeclaredFiles(unittest.TestCase):
    def test_ac_worked_example_record_carries_valid_declared_files(self):
        # covers: ACD-1600c-4-vi
        # angle: criterion
        """The enriched worked-example record has a valid declared_files list."""
        _, after = _example_records()
        found = df.get_declared_files(after)
        self.assertNotIsInstance(found, df.NoDeclaredFiles)
        self.assertGreaterEqual(len(found), 1)
        self.assertEqual(
            df.declared_files_shape_errors(after["id"], after["declared_files"]), []
        )
        for entry in found:
            self.assertNotIn("\\", entry["path"])
            self.assertFalse(entry["path"].startswith("/"))

    def test_ac_declared_files_placed_before_it_requirements(self):
        # covers: ACD-1600c-4-vi
        # angle: criterion
        """declared_files is a top-level key placed before it_requirements."""
        _, after = _example_records()
        keys = list(after)
        self.assertIn("declared_files", keys)
        self.assertLess(keys.index("declared_files"), keys.index("it_requirements"))

    def test_ac_output_contract_names_declared_files(self):
        # covers: ACD-1600c-4-vi
        # angle: criterion
        """The requirement_records output description lists declared_files."""
        outputs = {o["name"]: o for o in _frontmatter()["outputs"]}
        self.assertIn("declared_files", outputs["requirement_records"]["description"])
        self.assertIn("declared_files", _frontmatter()["description"])

    def test_negative_control_before_record_has_none(self):
        # covers: ACD-1600c-4-vi
        # angle: boundary
        """The BA's un-enriched record carries no declared_files (control)."""
        before, _ = _example_records()
        self.assertIsInstance(df.get_declared_files(before), df.NoDeclaredFiles)

    def test_negative_control_validator_refuses_bad_shapes(self):
        # covers: ACD-1600c-4-vi
        # angle: failure
        """The validator refuses an empty list and an unknown state (control)."""
        self.assertTrue(df.declared_files_shape_errors("X-1", []))
        self.assertTrue(
            df.declared_files_shape_errors("X-1", [{"path": "a.py", "state": "maybe"}])
        )
        self.assertEqual(
            df.declared_files_shape_errors(
                "X-1", [{"path": "a.py", "state": "to_be_created"}]
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
