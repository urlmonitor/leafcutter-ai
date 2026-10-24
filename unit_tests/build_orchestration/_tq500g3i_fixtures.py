"""
MODULE: unit_tests/build_orchestration/_tq500g3i_fixtures.py
GOAL: Shared REAL sandbox and CLI drivers for the TQ-500g-3-i tests (the sweep list check:
    scripts/build_orchestration/consumer_sweep.py record / check, and wrong_version_gate.py finish).
BUSINESS CONTEXT: "Existed before the work began" is a git fact, so every fixture is a real git repo
    whose base commit holds test_refresh.py, test_retry.py, test_export.py and a conftest.py with
    the fixture retry_state; the work is an UNCOMMITTED edit on top of it (the routes pass
    --base-ref HEAD). Lists go through the real record step (so the fingerprint is the check's
    own); nothing the CLIs print is typed by hand.
ARCHITECTURE: Not a test file (leading underscore). Today consumer_sweep.py does not exist, so a
    run prints no JSON and ``parse_one_json`` raises an AssertionError: every test is red on an
    assertion, never on an ImportError or a fixture error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix

SCRIPTS = ix.REPO_ROOT / "scripts" / "build_orchestration"
SWEEP = SCRIPTS / "consumer_sweep.py"
GATE = SCRIPTS / "wrong_version_gate.py"
CHECK_KEYS = {"passed", "applicable", "reason", "unlisted", "weakened", "loosened", "removed", "inconclusive", "error"}
REFRESH, RETRY, EXPORT, CONFTEST = "tests/test_refresh.py", "tests/test_retry.py", "tests/test_export.py", "tests/conftest.py"
GATE_FILE = "tests/test_refresh_gate.py"
FIXTURE = "retry_state"
W1_KEY, W2_KEY = "work-w1", "work-w2"

_BASE = {
    REFRESH: "def test_refresh_on():\n    assert 1 + 1 == 2\n\n\ndef test_refresh_off():\n    assert 2 + 2 == 4\n",
    RETRY: "def test_retry_limit():\n    assert 3 == 3\n\n\ndef test_retry_none():\n    assert 0 == 0\n",
    EXPORT: ("def test_export_csv():\n    assert 'a,b' == 'a,b'\n\n\ndef test_export_json():\n"
             "    assert 'jj' == 'jj'\n\n\ndef test_export_empty():\n    assert '' == ''\n"),
    CONFTEST: ("import pytest\n\n\n@pytest.fixture\ndef retry_state():\n    return {'n': 0}\n\n\n"
               "@pytest.fixture\ndef other_state():\n    return {'m': 0}\n"),
}
_EDITS = {  # the work's edits: (path, old, new)
    "refresh": (REFRESH, "assert 1 + 1 == 2", "assert 1 + 1 == 2\n    assert 2 * 1 == 2"),
    "retry": (RETRY, "assert 3 == 3", "assert 3 == 3\n    assert 4 - 1 == 3"),
    "export_csv": (EXPORT, "assert 'a,b' == 'a,b'", "assert 'a,b' == 'a,b'\n    assert 'x' != 'y'"),
    "export_json": (EXPORT, "assert 'jj' == 'jj'", "assert 'jj' == 'jj'\n    assert 'kk' != 'jj'"),
    "fixture": (CONFTEST, "return {'n': 0}", "return {'n': 0, 'limit': 3}"),
}
NEW_TEST = "def test_refresh_gate_blocks():\n    assert True is not False\n"
ALL_EDITS = ("refresh", "retry", "export_csv", "export_json", "fixture")


@dataclass
class Repo:
    """A scratch git repo: base commit in HEAD, the work uncommitted in the tree."""

    root: Path
    ac_root: Path

    def path(self, rel: str) -> Path:
        return self.root / rel

    def git_dir(self) -> Path:
        return Path(gitfx.run_git(["rev-parse", "--absolute-git-dir"], cwd=self.root).strip())


def write(path: Path, text: str) -> None:
    """Write *text* as UTF-8 bytes (LF), creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def edit(repo: Repo, key: str) -> None:
    """Apply one of the work's named edits to the working tree."""
    rel, old, new = _EDITS[key]
    text = read(repo.path(rel))
    assert old in text, f"{old!r} is not in {rel}"
    write(repo.path(rel), text.replace(old, new, 1))


def build(tmp: Path, *, edits: tuple[str, ...] = ALL_EDITS, add_new_file: bool = True) -> Repo:
    """A repo whose base commit holds the existing tests; the work edits them and adds test_refresh_gate.py."""
    repo = tmp / "repo"
    gitfx.init_repo(repo)
    write(repo / ".gitignore", "__pycache__/\n")
    for rel, text in _BASE.items():
        write(repo / rel, text)
    gitfx.commit_all(repo, "base")
    sb = Repo(repo, tmp / "ac_store")
    sb.ac_root.mkdir(parents=True, exist_ok=True)
    for key in edits:
        edit(sb, key)
    if add_new_file:
        write(repo / GATE_FILE, NEW_TEST)
        gitfx.run_git(["add", GATE_FILE], cwd=repo)
    return sb


def entry(file: str, test: str, status: str = "strengthened", note: str = "added an assertion", **extra) -> dict:
    return {"file": file, "test": test, "status": status, "note": note, **extra}


W1_LIST = [entry(REFRESH, "test_refresh_on"), entry(RETRY, "test_retry_limit")]
W2_LIST = [*W1_LIST, entry(EXPORT, "test_export_csv"), entry(EXPORT, "test_export_json"), entry(CONFTEST, FIXTURE)]


def _run(cmd: list[str], repo: Repo, stdin: str, who: str, timeout: int = 600):
    raw = subprocess.run(cmd, cwd=repo.root, input=stdin.encode("utf-8"), capture_output=True, timeout=timeout,
                         env=ix._env())  # noqa: SLF001 -- the one shared env builder
    proc = subprocess.CompletedProcess(raw.args, raw.returncode, raw.stdout.decode("utf-8", "replace"),
                                       raw.stderr.decode("utf-8", "replace"))
    return proc, ix.parse_one_json(proc, who)


def record(repo: Repo, entries: list[dict], key: str = W1_KEY):
    """Run ``consumer_sweep.py record`` with the list as stdin JSON; return ``(proc, JSON)``."""
    cmd = [sys.executable, str(SWEEP), "record", "--work-key", key, "--test-root", str(repo.root), "--base-ref", "HEAD"]
    return _run(cmd, repo, json.dumps({"entries": entries}), "record")


def check(repo: Repo):
    """Run ``consumer_sweep.py check``; return ``(proc, JSON)``."""
    cmd = [sys.executable, str(SWEEP), "check", "--test-root", str(repo.root), "--base-ref", "HEAD"]
    return _run(cmd, repo, "", "check")


def recorded(repo: Repo, entries: list[dict], key: str = W1_KEY) -> None:
    """Record *entries* and require that the record step accepted them."""
    proc, out = record(repo, entries, key)
    assert proc.returncode == 0 and out.get("recorded") is True, (proc.returncode, out, proc.stderr[-300:])


def assert_check_shape(proc, out: dict) -> None:
    assert CHECK_KEYS <= set(out), f"check JSON keys are {sorted(out)}, missing {sorted(CHECK_KEYS - set(out))}"
    assert isinstance(out["passed"], bool), out["passed"]
    assert (proc.returncode == 0) == out["passed"], (proc.returncode, out["passed"])


def pairs(items: list[dict]) -> set[tuple[str, str]]:
    return {(i["file"], i["test"]) for i in items}


def finish(repo: Repo, key: str = W1_KEY):
    """Run ``wrong_version_gate.py finish`` with NO --ac-ids and an empty reply; return ``(proc, JSON)``."""
    cmd = [sys.executable, str(GATE), "finish", "--work-key", key, "--reply", "-", "--ac-root", str(repo.ac_root),
           "--test-root", str(repo.root), "--base-ref", "HEAD"]
    return _run(cmd, repo, "", "gate")


def manifest_path(repo: Repo, key: str) -> Path:
    return repo.git_dir() / "leafcutter" / "work" / key / "alterations.json"
