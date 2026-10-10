"""TQ-600a-2-i: private-copy staging directories must not leak into /tmp.

Behavioural tests: a tiny child pytest session (subprocess) requests the
``shared_reference_layout`` fixture as undeclared / mutator / reader. The
expensive copy + build.py subprocess are stubbed inside the child (no real
build.py runs), and TMPDIR is pointed at a scratch directory so every
``leafcutter-unshared-layout-*`` staging directory is observable.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_PREFIX = "leafcutter-unshared-layout-"

_STUB_PLUGIN = '''
import os
import shutil
import subprocess
from pathlib import Path

import scripts.suite_performance.pytest_shared_reference_layout as plugin

MODE = os.environ.get("STUB_MODE", "ok")


def _copytree(src, dst, *a, **kw):
    if MODE == "copy_fail":
        Path(dst).mkdir(parents=True)  # partial copy, then fail
        raise OSError("stub copy failure")
    (Path(dst) / "scripts").mkdir(parents=True)


def _run(cmd, *a, **kw):
    staging = Path(kw["cwd"])
    if MODE == "deploy_fail":
        return subprocess.CompletedProcess(cmd, 1, "", "boom")
    if MODE != "no_manifest":
        (staging / ".build_manifest.json").write_text("{}")
    return subprocess.CompletedProcess(cmd, 0, "", "")


shutil.copytree = _copytree
plugin.subprocess.run = _run
plugin.get_or_produce_shared_layout = lambda: Path(os.environ["STUB_SHARED_ROOT"])
'''

_TEST_FILE = '''
import os
import pytest
from pathlib import Path


def _record(path):
    with open(os.environ["RECORD"], "a") as fh:
        fh.write(f"{path}|{Path(path).exists()}\\n")


def test_undeclared(shared_reference_layout):
    _record(shared_reference_layout.parent)


@pytest.mark.shared_layout_mutator
def test_mutator(shared_reference_layout):
    _record(shared_reference_layout.parent)


@pytest.mark.shared_layout_mutator
def test_mutator_body_fails(shared_reference_layout):
    _record(shared_reference_layout.parent)
    assert False, "deliberate failure"


@pytest.mark.shared_layout_reader
def test_reader(shared_reference_layout):
    _record(shared_reference_layout)
'''


class TestPrivateCopyCleanup(unittest.TestCase):
    def _run_child(self, mode: str, select: str | None = None):
        tmp = Path(tempfile.mkdtemp(prefix="tq600a2i-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        scratch = tmp / "scratch"
        scratch.mkdir()
        shared = tmp / "shared_root"
        shared.mkdir()
        proj = tmp / "proj"
        proj.mkdir()
        (proj / "stub_plugin.py").write_text(_STUB_PLUGIN)
        (proj / "test_child.py").write_text(_TEST_FILE)
        (proj / "pytest.ini").write_text(
            "[pytest]\nmarkers =\n    shared_layout_reader\n    shared_layout_mutator\n"
        )
        record = tmp / "record.txt"
        env = dict(os.environ)
        env.update(
            TMPDIR=str(scratch),
            RECORD=str(record),
            STUB_MODE=mode,
            STUB_SHARED_ROOT=str(shared),
            PYTHONPATH=os.pathsep.join([str(_WORKTREE_ROOT), str(proj)]),
            PYTEST_ADDOPTS="",
        )
        cmd = [
            sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
            "-p", "scripts.suite_performance.pytest_shared_reference_layout",
            "-p", "stub_plugin", "-q",
            "--rootdir", str(proj), "-c", str(proj / "pytest.ini"),
            str(proj / "test_child.py"),
        ]
        if select:
            cmd += ["-k", select]
        res = subprocess.run(
            cmd, cwd=str(proj), env=env, capture_output=True, text=True, timeout=120
        )
        lines = record.read_text().splitlines() if record.exists() else []
        leftovers = [p for p in scratch.iterdir() if p.name.startswith(_PREFIX)]
        return res, lines, leftovers, shared

    def test_undeclared_staging_removed_after_test(self):
        # covers: TQ-600a-2-i
        # angle: criterion
        res, lines, leftovers, _ = self._run_child("ok", "test_undeclared")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].endswith("|True"), "staging must exist during test")
        self.assertEqual(leftovers, [], "undeclared private copy leaked")

    def test_mutator_staging_removed_after_test(self):
        # covers: TQ-600a-2-i
        # angle: criterion
        res, lines, leftovers, _ = self._run_child("ok", "test_mutator and not fails")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].endswith("|True"))
        self.assertEqual(leftovers, [], "mutator private copy leaked")

    def test_staging_removed_when_test_body_fails(self):
        # covers: TQ-600a-2-i
        # angle: failure
        res, lines, leftovers, _ = self._run_child("ok", "test_mutator_body_fails")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].endswith("|True"))
        self.assertEqual(leftovers, [], "private copy leaked after failing test")

    def test_failed_deploy_leaves_no_staging(self):
        # covers: TQ-600a-2-i
        # angle: failure
        for mode in ("deploy_fail", "no_manifest", "copy_fail"):
            with self.subTest(mode=mode):
                res, lines, leftovers, _ = self._run_child(mode, "test_undeclared")
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(lines, [], "test body must not run on setup failure")
                self.assertIn("SharedReferenceLayoutError", res.stdout + res.stderr)
                self.assertEqual(leftovers, [], f"{mode} leaked staging dir")

    def test_reader_shared_root_is_not_removed(self):
        # covers: TQ-600a-2-i
        # angle: discrimination
        # Negative control: only private copies are cleaned, never the shared root.
        res, lines, leftovers, shared = self._run_child("ok", "test_reader")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].endswith("|True"))
        self.assertTrue(shared.exists(), "shared reader root must survive")
        self.assertEqual(leftovers, [], "reader route must not create staging dirs")


if __name__ == "__main__":
    unittest.main()
