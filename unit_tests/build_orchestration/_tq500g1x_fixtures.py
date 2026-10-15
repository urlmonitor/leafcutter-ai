"""
MODULE: unit_tests/build_orchestration/_tq500g1x_fixtures.py
GOAL: Shared REAL sandbox for the TQ-500g-1-x test family (the derived scope of the
    wrong-version writer's ``list`` / ``write`` steps and the runner's scope check).
BUSINESS CONTEXT: Every fixture is built for real -- a git repo whose base commit holds
    refresh_config.py, settings.py, legacy_refresh.py, helpers.py, old_name.py and
    tests/test_refresh_config.py; then the work: a COMMITTED change to refresh_config.py
    (the gate now reads "if refresh_due and retry_due"), and UNCOMMITTED a changed test
    file, the deletion of legacy_refresh.py and a never-staged retry_policy.py. The AC
    store is written with yaml.safe_dump, replies with json.dump, files as bytes (LF).
ARCHITECTURE: Not a test file (leading underscore). The writer and the runner are only
    driven through their CLIs (subprocess). Git invocations are counted from git's own
    trace2 event log (GIT_TRACE2_EVENT), so the code under test is never mocked.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix

AC_ID = ix.AC_ID
N1, N2, N3, N9 = ix.N1, ix.N2, ix.N3, ix.N9
OWED = [N1, N3, N2, N9]
TEST_FILE = ix.TEST_FILE
E1, E2, E3 = "test_gate_blocks_refresh_without_retry", "test_retry_limit_stays_three", "test_gate_and_limit_both_hold"
COND, COND_ALT = ix.COND, ix.COND_ALT
NO_FLAG = object()  # pass no --base-ref flag at all
NO_REF = "no-such-ref"
SHARED_REL = "../shared/refresh_config.py"
HOOK_REL = ".git/hooks/pre-commit"

FIX_SRC = (
    '"""Refresh gate."""\nfrom settings import RETRY_LIMIT\n\n\ndef refresh_config(refresh_due, retry_due):\n'
    '    if refresh_due and retry_due:\n        return "refresh"\n    return "skip"\n\n\n'
    "def retry_limit():\n    return RETRY_LIMIT\n"
)
BASE_SRC = FIX_SRC.replace(COND + ":", "if refresh_due:")
SETTINGS = "RETRY_LIMIT = 3\nTIMEOUT = 5\n"
LEGACY = "def legacy_refresh():\n    return 'legacy'\n"
RETRY_POLICY = "RETRY_ATTEMPTS = 3\n"
HELPERS, OLD_NAME = "def helper():\n    return 1\n", "def old_name():\n    return 2\n"
TEST_NOTE = "\n# local test note kept uncommitted\n"
_HEAD = "import sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n"
TESTS_PY = (
    _HEAD + "from refresh_config import refresh_config, retry_limit\n\n\n"
    f'def {E1}():\n    # covers: {AC_ID}\n    assert refresh_config(True, False) == "skip"\n\n\n'
    f"def {E2}():\n    # covers: {AC_ID}\n    assert retry_limit() == 3\n\n\n"
    f'def {E3}():\n    # covers: {AC_ID}\n    assert refresh_config(True, False) == "skip"\n'
    '    assert refresh_config(True, True) == "refresh"\n    assert retry_limit() == 3\n'
)
SETTINGS_FILES = ["settings.py", "refresh_config.py"]


@dataclass
class XSandbox(ix.Sandbox):
    """The ix sandbox plus the base commit the work began from."""

    base_sha: str = ""


def _wb(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def test_spec(declared_only: bool = False) -> list[dict]:
    """The TQ-9101 test entries: N1 and one N3 entry declare scope, the rest declare none."""
    spec = [
        {"name": E1, "must_catch": [N1], "in_scope_files": list(SETTINGS_FILES)},
        {"name": E2, "must_catch": [N3], "in_scope_files": ["settings.py"]},
    ]
    return spec if declared_only else [*spec, {"name": E3, "must_catch": [N3, N2, N9]}]


def _base_files(work: Path, shape: str) -> None:
    _wb(work / ".gitignore", "__pycache__/\n.pytest_cache/\n*.ignored\n")
    _wb(work / "refresh_config.py", FIX_SRC if shape == "test_only" else BASE_SRC)
    _wb(work / "settings.py", SETTINGS)
    _wb(work / "legacy_refresh.py", LEGACY)
    _wb(work / "helpers.py", HELPERS)
    _wb(work / "old_name.py", OLD_NAME)
    _wb(work / TEST_FILE, TESTS_PY)


def build(root: Path, *, shape: str = "full", ac_inside: bool = False, declared_only: bool = False) -> XSandbox:
    """Build the sandbox. *shape*: ``full`` (the criteria's work) or ``test_only`` (only the test file changed)."""
    work, _ = gitfx.make_worktree(root, {"README.md": "sandbox\n"})
    ac_root = (work if ac_inside else root) / "ac_store"
    _base_files(work, shape)
    if ac_inside:
        gitfx.write_ac_yaml(ac_root, AC_ID, test_spec(declared_only))
    base_sha = gitfx.commit_all(work, "base")
    _wb(root / "shared" / "refresh_config.py", FIX_SRC)
    _wb(work / HOOK_REL, "#!/bin/sh\nexit 0\n")
    if shape == "full":
        _wb(work / "refresh_config.py", FIX_SRC)
        gitfx.commit_all(work, "the fix")
        (work / "legacy_refresh.py").unlink()
        _wb(work / "retry_policy.py", RETRY_POLICY)
    _wb(work / TEST_FILE, TESTS_PY + TEST_NOTE)
    if not ac_inside:
        gitfx.write_ac_yaml(ac_root, AC_ID, test_spec(declared_only))
    return XSandbox(root, work, ac_root, False, base_sha)


def build_all_new(root: Path) -> XSandbox:
    """A work that only ADDS non-test files (staged), so the fix undone does not apply."""
    work, _ = gitfx.make_worktree(root, {"README.md": "sandbox\n"})
    _wb(work / ".gitignore", "__pycache__/\n.pytest_cache/\n")
    base_sha = gitfx.commit_all(work, "base")
    _wb(work / "refresh_config.py", FIX_SRC)
    _wb(work / "settings.py", SETTINGS)
    gitfx.run_git(["add", "refresh_config.py", "settings.py"], cwd=work)
    ac_root = root / "ac_store"
    gitfx.write_ac_yaml(ac_root, AC_ID, test_spec())
    return XSandbox(root, work, ac_root, False, base_sha)


def amend_ac_store(sb: XSandbox) -> None:
    """Change one committed AC file and add a new one inside the repo (the work edits the AC store)."""
    with (sb.ac_root / f"{AC_ID}.yaml").open("ab") as fh:
        fh.write(b"# amended by the work\n")
    other = sb.ac_root / "TQ-9199.yaml"
    other.write_bytes(yaml.safe_dump({"id": "TQ-9199", "test_spec": []}).encode("utf-8"))


def env(trace: Path | None = None) -> dict:
    out = ix._env()  # noqa: SLF001 -- the one shared env builder (no runner timeout, no bytecode)
    if trace is not None:
        out["GIT_TRACE2_EVENT"] = str(trace)
    return out


def _base_args(sb: XSandbox, base_ref) -> list[str]:
    ref = sb.base_sha if base_ref is None else base_ref
    return [] if ref is NO_FLAG else ["--base-ref", ref]


def run_list(sb: XSandbox, *, base_ref=None, ac_ids: str = AC_ID, trace: Path | None = None):
    """Run ``list`` (``--base-ref`` defaults to the base commit; ``NO_FLAG`` omits it); return ``(proc, JSON)``."""
    cmd = [sys.executable, str(ix.WRITER), "list", "--ac-ids", ac_ids, "--ac-root", str(sb.ac_root),
           "--test-root", str(sb.work), *_base_args(sb, base_ref)]
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=120, env=env(trace))
    return proc, ix.parse_one_json(proc)


def run_write(sb: XSandbox, entries: list[dict], *, base_ref=None):
    """Write a reply for *entries* and run ``write``; return ``(proc, JSON)``."""
    reply = ix.write_reply(sb, ix.reply_obj(entries))
    cmd = [sys.executable, str(ix.WRITER), "write", "--work-key", ix.WORK_KEY, "--reply", str(reply),
           "--ac-ids", AC_ID, "--ac-root", str(sb.ac_root), "--test-root", str(sb.work), *_base_args(sb, base_ref)]
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=120, env=env())
    return proc, ix.parse_one_json(proc)


def listed(sb: XSandbox, **kw) -> dict[str, dict]:
    """Run ``list`` and require success; return ``{name: item}``."""
    proc, out = run_list(sb, **kw)
    assert proc.returncode == 0 and out["error"] is None, (proc.returncode, out, proc.stderr[-300:])
    return {o["name"]: o for o in out["owed"]}


def hand_manifest(sb: XSandbox, entries: dict[str, list[tuple[str, str, str]]], name: str = "hand.json") -> Path:
    """A hand-made alterations manifest: ``{wrong version: [(path, old, new)]}`` applied to the as-written files."""
    out = []
    for i, (wv, repls) in enumerate(entries.items()):
        files = []
        for path, old, new in repls:
            text = (sb.work / path).read_bytes().decode("utf-8")
            assert old in text, f"{old!r} is not in {path}"
            copy = sb.root / "altered" / str(i) / path
            _wb(copy, text.replace(old, new, 1))
            files.append({"path": path, "altered_copy": str(copy)})
        out.append({"name": wv, "status": "prepared", "reason": None, "diff": "", "files": files})
    path = sb.root / name
    path.write_text(json.dumps({"work_key": ix.WORK_KEY, "entries": out}), encoding="utf-8")
    return path


def full_manifest(sb: XSandbox) -> Path:
    """A complete in-scope manifest: every owed wrong version is one the covering tests catch."""
    return hand_manifest(sb, {
        N1: [("refresh_config.py", COND, COND_ALT)],
        N3: [("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")],
        N2: [("refresh_config.py", COND, "if refresh_due and True")],
        N9: [("refresh_config.py", 'return "refresh"', 'return "skip"')],
    })


def run_runner(sb: XSandbox, manifest: Path, *, trace: Path | None = None, base_ref: str | None = None):
    """Run the runner CLI against *manifest*; return ``(proc, verdict)``."""
    cmd = [sys.executable, str(ix.RUNNER), "run", "--ac-ids", AC_ID, "--test-root", str(sb.work),
           "--ac-root", str(sb.ac_root), "--base-ref", base_ref or sb.base_sha, "--alterations", str(manifest)]
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=420, env=env(trace))
    return proc, ix.parse_one_json(proc, "runner")


def git_commands(trace: Path) -> list[str]:
    """Every git command name (``diff``, ``rev-parse``, ...) git's own trace2 log saw, in order."""
    if not trace.exists():
        return []
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e["name"] for e in events if e.get("event") == "cmd_name"]


def snapshot(sb: XSandbox) -> dict:
    """Everything listing must leave alone: status, index, stash and the tree's bytes."""
    git = lambda *a: gitfx.run_git(list(a), cwd=sb.work)  # noqa: E731
    return {"status": git("status", "--porcelain"), "index": git("ls-files", "--stage"),
            "stash": git("stash", "list"), "tree": fx.tree_digest(sb.work)}

