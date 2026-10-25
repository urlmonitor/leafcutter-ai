"""
MODULE: unit_tests/build_orchestration/_tq500g1ix_fixtures.py
GOAL: Shared REAL sandbox for the TQ-500g-1-ix test family (the wrong-version
    writer, scripts/build_orchestration/wrong_version_writer.py: its ``list`` and
    ``write`` steps).
BUSINESS CONTEXT: Every fixture is built for real -- a git repo holding
    refresh_config.py ("if refresh_due and retry_due" once, "retry_due" three
    times), settings.py and tests/test_refresh_config.py; an AC store written with
    yaml.safe_dump; replies written with json.dump in the TQ-500g-1-iv reply
    contract shape. No tool output is ever hand-typed.
ARCHITECTURE: Not a test file (leading underscore). The writer is only ever
    driven through its CLI (subprocess, sys.executable + script path), never
    imported: today the CLI does not exist, so a run prints no JSON and the
    parse helper raises an AssertionError -- every test goes red on an
    assertion, never on an ImportError.
"""

from __future__ import annotations

import difflib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1_fixtures as fx

REPO_ROOT = gitfx.REPO_ROOT
WRITER = REPO_ROOT / "scripts" / "build_orchestration" / "wrong_version_writer.py"
RUNNER = fx.RUNNER
AC_ID, AC_ID_2 = "TQ-9101", "TQ-9102"
IDS = f"{AC_ID},{AC_ID_2}"
WORK_KEY = "tq-9101-work"

N1, N2, N3 = "drop the retry_due condition", "ignore retry_due", "retry only once"
N4, N5 = "skip the refresh when the cache is warm", "refresh on every call"
N6, N7, N8 = "refresh without a due check", "retry on a timeout", "refresh twice"
N9 = "refresh from the settings file"
OWED = [N1, N2, N3, N4, N5, N6, N7, N8, N9]
ALIAS, UNDONE, UNOWED = "revert the fix", "the fix undone", "invert refresh_due"
SPELLED_ALIAS = "REVERT THE FIX "
CLAIM_TEST = "test_refresh_gate_requires_retry"
TEST_FILE = "tests/test_refresh_config.py"
WRONG_DIFF = "--- a/wrong.py\n+++ b/wrong.py\n@@ -1 +1 @@\n-WRONGDIFFMARK\n+WRONGDIFFMARK2\n"
ANOMALY = "preparer saw ANOMALYMARK in the file"
COND, COND_ALT = "if refresh_due and retry_due", "if refresh_due"
COMMENT_LINE = "    # retry_due must also hold before a refresh runs\n"

REFRESH_LF = (
    '"""Refresh gate."""\n\n\ndef refresh_config(refresh_due, retry_due):\n' + COMMENT_LINE
    + '    if refresh_due and retry_due:\n        return "refresh"\n    return "skip"\n'
)
SETTINGS = "RETRY_LIMIT = 3\nTIMEOUT = 5\n"
TESTS_PY = (
    "import sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n"
    "from refresh_config import refresh_config\n\n\n"
    f'def {CLAIM_TEST}():\n    # covers: {AC_ID}\n    assert refresh_config(True, False) == "skip"\n\n\n'
    f'def test_refresh_retries_on_timeout():\n    # covers: {AC_ID}\n    assert refresh_config(True, True) == "refresh"\n\n\n'
    f'def test_refresh_second_guard():\n    # covers: {AC_ID}\n    assert refresh_config(False, True) == "skip"\n\n\n'
    f'def test_other_requirement():\n    # covers: {AC_ID_2}\n    assert refresh_config(False, False) == "skip"\n'
)
EXPECTED_KEYS = ["written", "manifest_path", "error", "entries", "ignored_reply_names", "preparer_anomalies"]
LIST_KEYS = ["owed", "to_prepare", "decisions", "error"]  # TQ-500g-1-xi: the list step's fixed key order


@dataclass
class Sandbox:
    """A real git repo plus a real AC store; ``work`` is the working-tree root."""

    root: Path
    work: Path
    ac_root: Path
    crlf: bool

    @property
    def git_dir(self) -> Path:
        return Path(gitfx.run_git(["rev-parse", "--absolute-git-dir"], cwd=self.work).strip())

    @property
    def work_dir(self) -> Path:
        return self.git_dir / "leafcutter" / "work" / WORK_KEY

    @property
    def manifest_path(self) -> Path:
        return self.work_dir / "alterations.json"

    @property
    def copies_dir(self) -> Path:
        return self.work_dir / "copies"

    def as_written(self, rel: str) -> bytes:
        return (self.work / rel).read_bytes()


def _wb(path: Path, text: str, crlf: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def ac_test_spec() -> list[dict]:
    """The TQ-9101 test entries: nine owed names, two aliases, scope per entry."""
    return [
        {"name": CLAIM_TEST, "must_catch": [ALIAS, N1, N2, N3, N4, N5, N6, N8, N9],
         "in_scope_files": ["refresh_config.py", TEST_FILE]},
        {"name": "test_refresh_retries_on_timeout", "must_catch": [N7, UNDONE],
         "in_scope_files": ["refresh_config.py", "settings.py", TEST_FILE]},
        {"name": "test_refresh_second_guard", "must_catch": [N1, SPELLED_ALIAS],
         "in_scope_files": ["refresh_config.py", TEST_FILE]},
    ]


def build_sandbox(root: Path, *, crlf: bool = False, untracked: bool = True) -> Sandbox:
    """Build the sandbox repo (committed) and the AC store under *root*."""
    work, _ = gitfx.make_worktree(root, {"README.md": "sandbox\n"})
    _wb(work / ".gitignore", "__pycache__/\n.pytest_cache/\n")
    _wb(work / "refresh_config.py", REFRESH_LF, crlf)
    _wb(work / "settings.py", SETTINGS)
    _wb(work / TEST_FILE, TESTS_PY)
    gitfx.commit_all(work, "refresh gate")
    _wb(root / "shared" / "refresh_config.py", REFRESH_LF)
    _wb(work / ".git" / "hooks" / "pre-commit", "#!/bin/sh\nexit 0\n")
    if untracked:
        _wb(work / "scratch_note.txt", "untracked note\n")
    ac_root = root / "ac_store"
    gitfx.write_ac_yaml(ac_root, AC_ID, ac_test_spec())
    gitfx.write_ac_yaml(ac_root, AC_ID_2, [{"name": "test_other_requirement"}])
    return Sandbox(root, work, ac_root, crlf)


def prep(name: str, *repls: tuple[str, str, str], **extra) -> dict:
    """A prepared reply entry: replacements are ``(path, old, new)``."""
    entry = {"name": name, "status": "prepared", "reason": None,
             "replacements": [{"path": p, "old": o, "new": n} for p, o, n in repls]}
    entry.update(extra)
    return entry


def cnp(name: str, reason: str) -> dict:
    """A could_not_prepare reply entry."""
    return {"name": name, "status": "could_not_prepare", "reason": reason, "replacements": []}


def default_entries() -> list[dict]:
    """The reply of the AC's first scenario: R1..R7, R9, plus an alias and an unowed name."""
    r1 = prep(N1, ("refresh_config.py", COND, COND_ALT), diff=WRONG_DIFF,
              caught_by=[CLAIM_TEST], would_catch=True, outcome="caught")
    return [
        r1,
        prep(N2, ("refresh_config.py", "retry_due", "True")),
        prep(N3, ("refresh_config.py", "max_retries = 3", "max_retries = 1")),
        prep(N4, ("refresh_config.py", 'return "skip"', 'return "refresh"'),
             (TEST_FILE, "def test_refresh_second_guard", "def test_refresh_second_guard_x")),
        prep(N5, ("../shared/refresh_config.py", COND, COND_ALT)),
        prep(N6, (".git/hooks/pre-commit", "exit 0", "exit 1")),
        cnp(N7, "refresh_config.py has no timeout handling"),
        prep(N9, ("refresh_config.py", 'return "refresh"', 'return "skip"'),
             ("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")),
        prep(ALIAS, ("refresh_config.py", COND, COND_ALT)),
        prep(UNOWED, ("refresh_config.py", COND, "if not refresh_due")),
    ]


def reply_obj(entries: list[dict], anomalies=(), work_key: str = WORK_KEY, **extra) -> dict:
    """A reply in the TQ-500g-1-iv success shape."""
    obj = {"work_key": work_key, "entries": list(entries), "anomalies": list(anomalies)}
    obj.update(extra)
    return obj


def write_reply(sb: Sandbox, content, name: str = "reply.json") -> Path:
    """Write *content* (a dict, via json.dump, or raw text) to a reply file; return its path."""
    path = sb.root / name
    if isinstance(content, str):
        path.write_bytes(content.encode("utf-8"))
    else:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(content, fh)
    return path


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if k != fx.TIMEOUT_ENV}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def parse_one_json(proc: subprocess.CompletedProcess, who: str = "writer") -> dict:
    """Parse the single JSON object *who* printed; an AssertionError when it printed none."""
    try:
        parsed = json.loads(proc.stdout.strip())
    except ValueError as exc:
        msg = (f"{who} printed no single JSON object (rc={proc.returncode}): "
               f"stdout={proc.stdout[-300:]!r} stderr={proc.stderr[-300:]!r}")
        raise AssertionError(msg) from exc
    assert isinstance(parsed, dict), f"{who} JSON is not an object: {parsed!r}"
    return parsed


def run_writer(sb: Sandbox, step: str, *, reply: Path | None = None, stdin: str | None = None,
               ac_ids: str = IDS, ac_root: Path | None = None, work_key: str = WORK_KEY):
    """Run the writer CLI; return ``(CompletedProcess, parsed stdout JSON)``."""
    cmd = [sys.executable, str(WRITER), step]
    if step == "write":
        cmd += ["--work-key", work_key, "--reply", "-" if stdin is not None else str(reply)]
    cmd += ["--ac-ids", ac_ids, "--ac-root", str(ac_root or sb.ac_root), "--test-root", str(sb.work)]
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=120, env=_env(),
                          input=stdin)
    return proc, parse_one_json(proc)


def write_default(sb: Sandbox, entries: list[dict] | None = None, **kw):
    """Write a reply (default: the first scenario's) and run the write step on it."""
    path = write_reply(sb, reply_obj(default_entries() if entries is None else entries, **kw))
    return run_writer(sb, "write", reply=path)


def load_manifest(sb: Sandbox) -> dict:
    """Read the manifest the writer left; an AssertionError when it is not on disk."""
    assert sb.manifest_path.is_file(), f"no manifest at {sb.manifest_path}"
    return json.loads(sb.manifest_path.read_text(encoding="utf-8"))


def entry(manifest: dict, name: str) -> dict:
    """The one manifest entry for *name*; an AssertionError unless there is exactly one."""
    found = [e for e in manifest["entries"] if e["name"] == name]
    assert len(found) == 1, f"{name!r} appears {len(found)} times in the manifest"
    return found[0]


def copy_files(sb: Sandbox) -> list[Path]:
    """Every file under the work folder's copies/ (sorted)."""
    if not sb.copies_dir.exists():
        return []
    return sorted(p for p in sb.copies_dir.rglob("*") if p.is_file())


def expected_diff(rel: str, before: bytes, after: bytes) -> str:
    """The unified diff of the LF forms of *before* and *after*, 3 lines of context."""
    a = before.decode("utf-8").replace("\r\n", "\n")
    b = after.decode("utf-8").replace("\r\n", "\n")
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{rel}", f"b/{rel}", n=3))


def assert_refused(m: dict, name: str, reason: str) -> None:
    """*name* is could_not_prepare with exactly *reason*, no files and no diff."""
    e = entry(m, name)
    assert e["status"] == "could_not_prepare", f"{name!r}: {e}"
    assert e["reason"] == reason, f"{name!r}: reason {e['reason']!r} != {reason!r}"
    assert e["files"] == [] and e["diff"] == "", f"{name!r} kept files or a diff: {e}"


def list_names(payload: dict) -> list[str]:
    """The owed names a list payload prints, in order."""
    return [o["name"] for o in payload["owed"]]
