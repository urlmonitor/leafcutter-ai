"""Tests for GE-124a-1: a component-level declaration block names the criteria a file serves.

MODULE: test_ge_124a_1.py
GOAL: Pin the contract of the shared frontend declaration reader
      (templates/scripts/commit_guardian/_frontend_declaration_reader.py).
      The reader must expose:
        read_declaration(path, text) -> record dict (pure text scan)
        read_staged_declarations(repo_root, paths) -> list of records, read from
            the git INDEX (staged blob), never the working tree
        main(argv) / CLI: `_frontend_declaration_reader.py --staged <path>...`
            run with cwd at the repo root prints a JSON list of records on stdout.
      Record shape: {path, framework, role, declaration_block, declares, verdict}.
BUSINESS CONTEXT: Both the commit-tier check (GE-124c) and the CI gate (GE-124e)
    consume this one reader; a reader that sorts ids, accepts one separator form,
    or reads the working tree teaches authors that the guardrail is wrong.
ARCHITECTURE: Not needed.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_READER_PATH = _COMMIT_GUARDIAN / "_frontend_declaration_reader.py"

_RECORD_KEYS = {"path", "framework", "role", "declaration_block", "declares", "verdict"}


def _comment(ac_line):
    """Build a leading doc comment carrying the given @ac line."""
    return "/**\n * Realization badge - labels a flow node.\n * " + ac_line + "\n */"


def _component_source(ac_line):
    """Build a .tsx component source whose leading comment carries ac_line."""
    return _comment(ac_line) + "\nexport function Badge() {\n  return <span>hi</span>;\n}\n"


def _load_reader():
    """Import the reader from the templates source tree."""
    sys.path.insert(0, str(_COMMIT_GUARDIAN))
    try:
        import _frontend_declaration_reader as reader  # type: ignore[import]
    finally:
        sys.path.remove(str(_COMMIT_GUARDIAN))
    return reader


def _git(repo, *args):
    """Run git in repo and return the completed process."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )


def _make_repo(tmp):
    """Create a temp git repo and return its path."""
    repo = Path(tmp) / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    return repo


def _run_reader_cli(repo, *paths):
    """Run the reader's real CLI over staged paths and return parsed JSON records."""
    proc = subprocess.run(
        [sys.executable, str(_READER_PATH), "--staged", *paths],
        cwd=str(repo), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f"reader CLI exited {proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return json.loads(proc.stdout)


class TestGe124a1(unittest.TestCase):
    """Contract tests for the shared frontend declaration reader."""

    def test_ge_124a_1_declaration_block_parses_to_ordered_id_list(self):
        """AC-1/AC-2/AC-3: '@ac UXP-607, UXP-607-1' -> ordered list, 'declared', literal block."""
        # covers: GE-124a-1
        # angle: criterion
        reader = _load_reader()
        block = _comment("@ac UXP-607, UXP-607-1")
        record = reader.read_declaration("components/badge.tsx", _component_source("@ac UXP-607, UXP-607-1"))
        self.assertEqual(record["declares"], ["UXP-607", "UXP-607-1"])
        self.assertEqual(record["verdict"], "declared")
        self.assertEqual(record["declaration_block"], block)
        self.assertEqual(record["path"], "components/badge.tsx")
        # Wrong version caught: a sorted list ('UXP-607-1' < 'UXP-607' is False, so also
        # exercise a reversed-order declaration where sorting would reorder).
        reversed_record = reader.read_declaration(
            "components/b.tsx", _component_source("@ac UXP-609-3, KM-200f")
        )
        self.assertEqual(reversed_record["declares"], ["UXP-609-3", "KM-200f"])
        # Wrong version caught: de-dup / set semantics lose a repeated-prefix distinct id.
        self.assertIsInstance(record["declares"], list)
        self.assertEqual(len(record["declares"]), 2)

    def test_ge_124a_1_all_three_separator_forms_yield_the_identical_list(self):
        """AC-4/AC-5/AC-6: three separator forms agree; one id yields a one-item list."""
        # covers: GE-124a-1
        # angle: boundary
        reader = _load_reader()
        expected = ["UXP-607", "UXP-607-1"]
        for line in (
            "@ac UXP-607, UXP-607-1",
            "@ac UXP-607 UXP-607-1",
            "@ac UXP-607,UXP-607-1",
        ):
            with self.subTest(line=line):
                record = reader.read_declaration("a/b.tsx", _component_source(line))
                self.assertEqual(record["declares"], expected)
                self.assertEqual(record["verdict"], "declared")
        single = reader.read_declaration("a/c.tsx", _component_source("@ac UXP-100d-2"))
        self.assertEqual(single["declares"], ["UXP-100d-2"])
        self.assertIsInstance(single["declares"], list)
        self.assertEqual(single["verdict"], "declared")
        # Control: a file with no @ac line must NOT come back 'declared' (the grammar is
        # permissive about separators, not about presence).
        none = reader.read_declaration("a/d.tsx", "export function X() { return <i/>; }\n")
        self.assertEqual(none["declares"], [])
        self.assertNotEqual(none["verdict"], "declared")

    def test_ge_124a_1_reader_is_reached_from_the_hook_entry_point_over_real_staged_files(self):
        """Reachability: the reader's real CLI reads the STAGED blob, not the working tree."""
        # covers: GE-124a-1
        # angle: reachability
        # Entry point (no commit-tier hook exists until GE-124c-1): the reader's own CLI,
        # run as a subprocess with real argv inside a real git repo.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            rel = "components/badge.tsx"
            target = repo / rel
            target.parent.mkdir()
            staged_text = _component_source("@ac UXP-607, UXP-607-1")
            target.write_text(staged_text, encoding="utf-8")
            _git(repo, "add", rel)
            records = _run_reader_cli(repo, rel)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["path"], rel)
            self.assertEqual(records[0]["declares"], ["UXP-607", "UXP-607-1"])
            self.assertEqual(records[0]["declaration_block"], _comment("@ac UXP-607, UXP-607-1"))
            self.assertEqual(records[0]["verdict"], "declared")
            # Overwrite the working tree WITHOUT staging: the record must still reflect
            # the staged version.
            target.write_text(_component_source("@ac UXP-999"), encoding="utf-8")
            after = _run_reader_cli(repo, rel)
            self.assertEqual(len(after), 1)
            self.assertEqual(after[0]["declares"], ["UXP-607", "UXP-607-1"])
            self.assertNotIn("UXP-999", json.dumps(after))

    def test_ge_124a_1_declaration_record_shape_is_consumed_by_its_real_downstream(self):
        """Seam: the record the real reader emits survives JSON hand-off with the contract shape."""
        # covers: GE-124a-1
        # angle: seam
        # No real consumer exists yet (GE-124c-1 creates check_frontend_ac_declaration.py).
        # The seam pinned here is the real producer's CLI output crossing the process
        # boundary as JSON, which is how every downstream tier receives it: the exact key
        # set, list-typed declares, and verdict vocabulary the consumers read.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            files = {
                "components/declared.tsx": _component_source("@ac UXP-607, UXP-607-1"),
                "components/single.tsx": _component_source("@ac UXP-100d-2"),
            }
            for rel, text in files.items():
                path = repo / rel
                path.parent.mkdir(exist_ok=True)
                path.write_text(text, encoding="utf-8")
                _git(repo, "add", rel)
            records = _run_reader_cli(repo, *files)
            self.assertEqual(len(records), 2)
            by_path = {r["path"]: r for r in records}
            self.assertEqual(set(by_path), set(files))
            for record in records:
                self.assertEqual(set(record), _RECORD_KEYS)
                self.assertIsInstance(record["declares"], list)
                self.assertTrue(all(isinstance(i, str) for i in record["declares"]))
                self.assertIsInstance(record["declaration_block"], str)
                self.assertEqual(record["framework"], "react-tsx")
                self.assertEqual(record["verdict"], "declared")
            self.assertEqual(by_path["components/single.tsx"]["declares"], ["UXP-100d-2"])
            self.assertEqual(
                by_path["components/declared.tsx"]["declares"], ["UXP-607", "UXP-607-1"]
            )


if __name__ == "__main__":
    unittest.main()
