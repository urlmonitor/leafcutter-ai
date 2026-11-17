"""
MODULE: unit_tests/commit_guardian/_tq500g1viii_fixtures.py
GOAL: Shared sandbox for the TQ-500g-1-viii hook tests: a real git repo with a real index, the real marker
    written by the record module's own CLI, and gate records in the shapes the AC pins.
BUSINESS CONTEXT: The hook templates/scripts/commit_guardian/check_build_epic_gate_verdicts.py is only ever
    driven as a subprocess (cwd = the sandbox repo), never imported, so today (the file is missing) a run prints
    nothing useful and every test fails on an assertion about its exit code or message, never on an import.
    Verdicts are NOT hand-typed: the wrong-version ones come from the runner's own ``assemble`` / ``row`` (the
    builders the workflow tests use); the red-baseline ones are what the real ``heavy_lane_gate`` CLI prints.
    Records are written with json.dumps in the shape TQ-500g-1-viii's expects_from states.
PINNED BEYOND THE AC (the coder must conform; one place to read them): ``code_digest`` is the sha256 of
    ``json.dumps(paths, sort_keys=True)``; the hook is expected NOT to re-derive it (staleness is per path).
ARCHITECTURE: Not a test file (leading underscore).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BO = REPO_ROOT / "scripts" / "build_orchestration"
HOOK = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_build_epic_gate_verdicts.py"
RECORDS = BO / "gate_verdict_records.py"
FAST_LANE = BO / "fast_lane.py"
if str(BO) not in sys.path:
    sys.path.insert(0, str(BO))
from _wvr_verdict import NO_SOURCE_OUTCOME, assemble, row  # noqa: E402

KEY = "07_wv_ticket"
EPIC_DIR = "tickets/00_inbox/epics/EPIC-WvViii"
CODE = "scripts/stub_impl.py"
KNOWLEDGE = "docs/knowledge/note.md"
TEST_NAME, WRONG = "test_gate_blocks_refresh_without_retry", "drop the retry_due condition"
CODE_V0, CODE_V1, CODE_V2 = ("def refresh(due, retry):\n    return 'v%d'\n" % n for n in (0, 1, 2))
TICKET_V0 = "---\nstatus: todo\n---\n# ticket\n"
TICKET_V1 = ("---\nstatus: in_progress\nred_baseline_gate: passed\n---\n# ticket\n\n## Comments\n"
             "### 2026-10-22 10:00 — ticket-supervisor (status: ok)\nBoth gates passed, ready for commit.\n")
RB_NA_OUTCOME = "red-baseline reader not applicable: no source requirement"


def git(args: list[str], cwd: Path, *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60, env=env)
    assert not check or proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc


def write_bytes(path: Path, text: str) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return data


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_repo(root: Path, key: str = KEY) -> Path:
    """A real repo with one base commit: a code file, a ticket file and a knowledge note (all at version 0)."""
    work = root / "work"
    work.mkdir(parents=True)
    git(["init", "-b", "main", "-q"], work)
    for k, v in (("user.email", "tw@example.com"), ("user.name", "Test Writer"), ("core.autocrlf", "false")):
        git(["config", k, v], work)
    write_bytes(work / ".gitignore", "__pycache__/\n")
    write_bytes(work / CODE, CODE_V0)
    write_bytes(work / ticket_rel(key), TICKET_V0)
    write_bytes(work / KNOWLEDGE, "note v0\n")
    git(["add", "-A"], work)
    git(["commit", "-q", "-m", "base"], work)
    return work


def ticket_rel(key: str = KEY) -> str:
    return f"{EPIC_DIR}/{key}.md"


def stage(work: Path, *rels: str) -> None:
    git(["add", "--", *rels], work)


def git_dir(work: Path) -> Path:
    return Path(git(["rev-parse", "--absolute-git-dir"], work).stdout.strip())


def verdict_dir(work: Path, key: str = KEY) -> Path:
    return git_dir(work) / "leafcutter" / "gate-verdicts" / key


def env(*, source_tree: bool = True, trace: Path | None = None) -> dict:
    out = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    if source_tree:  # the template hook sits outside the deployed layout; let it find the shared module
        out["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "scripts"), str(BO)])
    if trace is not None:
        out["GIT_TRACE2_EVENT"] = str(trace)
    return out


def run_py(script: Path, args: list[str], cwd: Path, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], cwd=cwd, capture_output=True, text=True,
                          timeout=300, env=env(**kw))


def open_marker(work: Path, key: str = KEY, *, records: Path = RECORDS, **kw) -> dict:
    """Open the marker with the record module's own CLI (the producer the workflow uses) and require success."""
    proc = run_py(records, ["open", "--worktree", str(work), "--ticket-key", key, "--ticket-path", ticket_rel(key)], work, **kw)
    out = json.loads(proc.stdout.strip() or "{}") if proc.stdout.strip().startswith("{") else {}
    assert proc.returncode == 0 and out.get("opened") is True, (
        f"the record module's open step did not open a marker: rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr[-300:]!r}")
    assert (verdict_dir(work, key) / "open.json").is_file(), "open reported success but wrote no open.json"
    return out


def run_hook(work: Path, *, hook: Path = HOOK, trace: Path | None = None, source_tree: bool = True) -> tuple[subprocess.CompletedProcess, str]:
    proc = run_py(hook, [], work, source_tree=source_tree, trace=trace)
    return proc, proc.stdout + proc.stderr


def git_commands(trace: Path) -> list[str]:
    """Every git command name git's own trace2 log saw (the hook's git calls), in order."""
    if not trace.exists():
        return []
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e["name"] for e in events if e.get("event") == "cmd_name"]


# --- verdicts ----------------------------------------------------------------------------------
def wv_pass() -> dict:
    return assemble([row(TEST_NAME, WRONG, "caught", "failed under it by an assertion")])


def wv_stop() -> dict:
    return assemble([row(TEST_NAME, WRONG, "survived", f"passed under '{WRONG}': the test did not notice it")])


def wv_na() -> dict:
    return assemble([], applicable=False, outcome=NO_SOURCE_OUTCOME)


def _heavy(work: Path, ac_root: Path, ac_id: str | None) -> dict:
    args = ["heavy_lane_gate", "--test-root", str(work), "--ac-root", str(ac_root)] + (["--source-ac", ac_id] if ac_id else [])
    proc = subprocess.run([sys.executable, str(FAST_LANE), *args], cwd=work, capture_output=True, text=True, timeout=300)
    assert proc.stdout.strip().startswith("{"), f"heavy_lane_gate printed no JSON: {proc.stdout!r} {proc.stderr[-300:]!r}"
    return json.loads(proc.stdout)


def _force_remove(func, path, _exc) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


@functools.lru_cache(maxsize=1)
def real_red_baseline_verdicts() -> tuple[str, dict, dict]:
    """``(ac id, passing verdict, not-applicable verdict)`` as the real heavy_lane_gate CLI prints them."""
    import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx

    tmp = Path(tempfile.mkdtemp(prefix="tq500g1viii_rb_"))
    try:
        work, _ = gitfx.make_worktree(tmp)
        ac_root, ac_id = work / "docs" / "acceptance-criteria", "TQ-FIX-8-RB"
        gitfx.write_ac_yaml(ac_root, ac_id, gitfx.t1_t2_t3_test_spec())
        gitfx.write_t1_t2_t3_test_files(work / "tests", ac_id, include={gitfx.T2_NAME, gitfx.T3_NAME})
        passed, na = _heavy(work, ac_root, ac_id), _heavy(work, ac_root, None)
    finally:
        shutil.rmtree(tmp, onerror=_force_remove)  # git object files are read-only on Windows
    assert passed["gate_passed"] is True and passed["applicable"] is True and na["applicable"] is False, (passed, na)
    return ac_id, passed, na


# --- records -----------------------------------------------------------------------------------
def paths_of(work: Path, rels: list[str]) -> dict:
    """``{rel: sha256 of the working-tree bytes}`` -- the shape of the wrong-version record's ``paths``."""
    return {r: hashlib.sha256((work / r).read_bytes()).hexdigest() for r in rels}


def record_body(key: str, gate: str, verdict: dict, *, ids=(), paths: dict | None = None) -> dict:
    body = {"gate": gate, "ticket_key": key, "ids": list(ids),
            "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "verdict": verdict}
    if gate == "wrong_version":
        paths = paths or {}
        body.update(base_ref="HEAD", paths=paths, code_digest=hashlib.sha256(json.dumps(paths, sort_keys=True).encode()).hexdigest())
    return body


def write_record(work: Path, key: str, gate: str, verdict: dict, *, ids=(), paths: dict | None = None, cut: bool = False) -> Path:
    """Write ``<git-dir>/leafcutter/gate-verdicts/<key>/<gate>.json``; ``cut`` keeps only the first half of its text."""
    text = json.dumps(record_body(key, gate, verdict, ids=ids, paths=paths))
    target = verdict_dir(work, key) / f"{gate}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text[: len(text) // 2] if cut else text, encoding="utf-8")
    return target


def stage_work(work: Path, key: str = KEY, code: str = CODE_V1) -> dict:
    """Stage the ticket file (carrying the supervisor's own 'ready' summary) and *code*; return the code path's sha map."""
    write_bytes(work / ticket_rel(key), TICKET_V1)
    write_bytes(work / CODE, code)
    stage(work, ticket_rel(key), CODE)
    return {CODE: sha(code)}


def names_reason(text: str, *words: str) -> bool:
    return all(re.search(w, text, re.IGNORECASE) for w in words)
