"""
MODULE: test_uxp_700a_2
GOAL: Pin UXP-700a-2 -- a record whose artifact places exist but whose store
    index is absent is made whole by the generator alone: it writes an index
    declaring zero artifacts with every derived lookup present and empty, a
    second run writes nothing, and the checker then reaches a verdict.
BUSINESS CONTEXT: The build scaffolds index.json on install, but an index can
    still go missing afterwards -- deleted by hand, lost in a merge, never
    committed. The generator is the store's single writer, so it is the one
    thing that must be able to rebuild the index from the sources. Before this
    AC it crashed outright with FileNotFoundError, leaving the record
    unrecoverable without a person hand-authoring JSON.
ARCHITECTURE: Import-based tests drive the REAL generate_product_truth.generate()
    against a tempdir store and read back what it actually wrote. The
    reachability test runs the REAL generator CLI and then the REAL checker CLI
    as subprocesses, from a store laid out the way an install lays it out
    (scripts/ and schemas/ copied whole, index.json absent).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PT_SRC / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402

_DERIVED_LOOKUPS = ("by_component", "by_entity", "by_flow", "by_ac")


def _empty_record(root: Path) -> tuple[Path, Path]:
    """Artifact places present and empty, no index.json, an empty AC store."""
    store = root / "docs" / "product-truth"
    ac_root = root / "docs" / "acceptance-criteria"
    for place in ("flows", "mock-data", "mockups"):
        (store / place).mkdir(parents=True)
    ac_root.mkdir(parents=True)
    return store, ac_root


def _run_generate(store: Path, ac_root: Path) -> bool:
    original_store, original_ac_store = gpt.STORE, gpt.AC_STORE
    gpt.STORE, gpt.AC_STORE = store, ac_root
    try:
        return gpt.generate(check=False, run_date="2026-01-01")
    finally:
        gpt.STORE, gpt.AC_STORE = original_store, original_ac_store


class TestGeneratorCreatesIndexFromZeroArtifacts(unittest.TestCase):
    def test_generator_creates_index_from_zero_artifacts(self) -> None:
        # covers: UXP-700a-2
        # angle: real_artifact
        with tempfile.TemporaryDirectory() as tmp_name:
            store, ac_root = _empty_record(Path(tmp_name))
            self.assertFalse((store / "index.json").exists(), "precondition: the index is absent")

            changed = _run_generate(store, ac_root)

            index_path = store / "index.json"
            self.assertTrue(index_path.is_file(), "the generator must write the missing index itself")
            index = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertTrue(changed, "writing a missing index is a change and must be reported as one")
        self.assertEqual(index.get("artifacts"), [], "the index must declare zero artifacts")
        for lookup in _DERIVED_LOOKUPS:
            self.assertIn(lookup, index, f"derived lookup {lookup!r} must be present, not left unwritten")
            self.assertEqual(index[lookup], {}, f"derived lookup {lookup!r} must be empty, got {index[lookup]!r}")


class TestSecondGeneratorRunOnEmptyStoreWritesNothing(unittest.TestCase):
    def test_second_generator_run_on_empty_store_writes_nothing(self) -> None:
        # covers: UXP-700a-2
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp_name:
            store, ac_root = _empty_record(Path(tmp_name))
            _run_generate(store, ac_root)
            index_path = store / "index.json"
            bytes_after_first = index_path.read_bytes()
            mtime_after_first = index_path.stat().st_mtime_ns

            changed_second = _run_generate(store, ac_root)

            bytes_after_second = index_path.read_bytes()
            mtime_after_second = index_path.stat().st_mtime_ns

        self.assertFalse(changed_second, "a second run with no artifact added must report no change")
        self.assertEqual(bytes_after_first, bytes_after_second, "the index bytes must not change on the second run")
        self.assertEqual(mtime_after_first, mtime_after_second, "the second run must not rewrite the index at all")


class TestUxp700a2ReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700a_2_reachable_from_entry_point(self) -> None:
        # covers: UXP-700a-2
        # angle: reachability
        # Entry points: the generator's own CLI, then the checker's own CLI, both run
        # as subprocesses from a store laid out the way an install lays it out.
        with tempfile.TemporaryDirectory() as tmp_name:
            store, _ac_root = _empty_record(Path(tmp_name))
            shutil.copytree(_SCRIPTS_DIR, store / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(_PT_SRC / "schemas", store / "schemas")

            generated = subprocess.run(
                [sys.executable, str(store / "scripts" / "generate_product_truth.py")],
                capture_output=True, text=True, timeout=60,
            )
            index_written = (store / "index.json").is_file()
            checked = subprocess.run(
                [sys.executable, str(store / "scripts" / "validate_product_truth.py")],
                capture_output=True, text=True, timeout=60,
            )

        self.assertEqual(
            generated.returncode, 0,
            f"the generator CLI must rebuild a missing index, not crash; stderr={generated.stderr!r}",
        )
        self.assertTrue(index_written, "the generator CLI must leave an index on disk")
        self.assertNotIn(
            "Traceback", checked.stderr,
            f"the checker must reach a verdict against the generated index, not crash; stderr={checked.stderr!r}",
        )
        last_line = checked.stdout.strip().splitlines()[-1] if checked.stdout.strip() else ""
        verdict = json.loads(last_line)
        self.assertIn("outcome", verdict, f"the checker must state its verdict; stdout={checked.stdout!r}")


if __name__ == "__main__":
    unittest.main()
