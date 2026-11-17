"""UXP-512: generator writes the product_truth back-ref onto each AC.

Each case runs the real generator CLI in a fresh process against a private copy
of the real store whose AC corpus contains real AC files (never an empty
acceptance-criteria directory, which would leave the write path unexercised).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from unit_tests.product_truth._uxp_300_store import ac_path, copy_bounded_store, replace_backlinks

_TARGET = "UXP-512"
_UNREFERENCED = "UXP-590"
_TIMEOUT = 180
_BLOCK = re.compile(r"^product_truth:.*\Z", re.MULTILINE | re.DOTALL)


def _generate(store: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(store / "scripts" / "generate_product_truth.py"), "--now", "2026-10-14"],
        capture_output=True, text=True, timeout=_TIMEOUT,
    )


def _by_ac(store: Path) -> dict:
    return json.loads((store / "index.json").read_text(encoding="utf-8"))["by_ac"]


def _truth(store: Path, ac_id: str):
    return yaml.safe_load(ac_path(store, ac_id).read_text(encoding="utf-8")).get("product_truth")


def _no_asof(entries):
    return [{k: v for k, v in e.items() if k != "asof"} for e in entries]


class TestUxp512(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        docs = Path(self._tmp.name) / "docs"
        docs.mkdir()
        self.store = copy_bounded_store(docs, extra_ac_ids=(_TARGET, _UNREFERENCED))

    def _strip_block(self, ac_id: str) -> str:
        path = ac_path(self.store, ac_id)
        text = path.read_text(encoding="utf-8")
        stripped = _BLOCK.sub("", text)
        path.write_text(stripped, encoding="utf-8")
        return stripped

    def test_product_truth_block_is_written_onto_a_referenced_ac_file(self):
        # covers: UXP-512
        # angle: real_artifact
        """A real AC file without a block gains one equal to its by_ac entry."""
        self._strip_block(_TARGET)
        self.assertIsNone(_truth(self.store, _TARGET))
        proc = _generate(self.store)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        expected = _by_ac(self.store)[_TARGET]
        self.assertGreaterEqual(len(expected), 1)
        self.assertEqual(_no_asof(_truth(self.store, _TARGET)), _no_asof(expected))

    def test_product_truth_block_is_overwritten_wholesale_not_merged(self):
        # covers: UXP-512
        # angle: criterion
        """A stale list ends as exactly the current inversion, no leftovers."""
        stale = [{"flow": "stale/flow", "node": "gone", "node_kind": "step", "flow_kind": "data",
                  "screen": None, "mock_data": None, "entities": [], "source": "real", "asof": "2020-01-01"}]
        replace_backlinks(self.store, _TARGET, stale)
        self.assertEqual(_generate(self.store).returncode, 0)
        result = _truth(self.store, _TARGET)
        self.assertEqual(_no_asof(result), _no_asof(_by_ac(self.store)[_TARGET]))
        self.assertNotIn("stale/flow", [e["flow"] for e in result])
        self.assertNotIn("stale/flow", ac_path(self.store, _TARGET).read_text(encoding="utf-8"))

    def test_key_is_omitted_entirely_when_no_flow_references_the_ac(self):
        # covers: UXP-512
        # angle: boundary
        """An unreferenced AC with a stale block loses the key altogether."""
        self.assertNotIn(_UNREFERENCED, _by_ac(self.store), "precondition: AC must be unreferenced")
        stale = [{"flow": "stale/flow", "node": "gone", "node_kind": "step", "flow_kind": "data",
                  "screen": None, "mock_data": None, "entities": [], "source": "real", "asof": "2020-01-01"}]
        replace_backlinks(self.store, _UNREFERENCED, stale)
        self.assertEqual(_generate(self.store).returncode, 0)
        text = ac_path(self.store, _UNREFERENCED).read_text(encoding="utf-8")
        self.assertNotIn("product_truth", yaml.safe_load(text))
        self.assertNotIn("product_truth:", text)

    def test_surrounding_yaml_lines_are_byte_identical_after_the_edit(self):
        # covers: UXP-512
        # angle: real_artifact
        """Every byte outside the product_truth block survives the rewrite."""
        path = ac_path(self.store, _TARGET)
        original = path.read_bytes().decode("utf-8")
        match = re.search(r"^product_truth:", original, re.MULTILINE)
        self.assertIsNotNone(match)
        prefix = original[: match.start()]
        # Make the block stale (text-only edit, leaving the rest of the file untouched).
        path.write_bytes(original.replace("source: real", "source: stale-value").encode("utf-8"))
        self.assertEqual(_generate(self.store).returncode, 0)
        after = path.read_bytes().decode("utf-8")
        self.assertTrue(after.startswith(prefix), "bytes before the product_truth block changed")
        self.assertNotIn("stale-value", after)
        self.assertEqual(_no_asof(_truth(self.store, _TARGET)), _no_asof(_by_ac(self.store)[_TARGET]))


if __name__ == "__main__":
    unittest.main()
