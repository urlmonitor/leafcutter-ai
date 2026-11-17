"""
MODULE: unit_tests/build_orchestration/_tq500g1_fixtures.py
GOAL: Shared REAL sandbox for the TQ-500g-1-i / -ii / -iii test families (the
    shared wrong-version runner, scripts/build_orchestration/wrong_version_runner.py).
BUSINESS CONTEXT: Every fixture is built for real -- a git repo whose
    refresh_config.py goes from "if refresh_due:" (base) to
    "if refresh_due and retry_due:" (the committed fix), real test files, a real
    AC store (yaml.safe_dump) and an alterations manifest (json.dump) in the
    TQ-500g-1-iv delivers_to shape. No pytest output is ever hand-typed.
    The runner is only ever driven through its CLI (subprocess), never imported.
ARCHITECTURE: Not a test file (leading underscore). Fixture tests report to
    files OUTSIDE the work tree: a run log (which test ran against which
    refresh_config.py bytes) and a probe (git stash list, git status, where the
    as-written copy sits) written while a wrong version is on disk. Cut-short
    hooks (sleep / os._exit(3) / block on a marker / replace the target with a
    directory) fire only when the file carries the marker "altered".
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx

REPO_ROOT = gitfx.REPO_ROOT
RUNNER = REPO_ROOT / "scripts" / "build_orchestration" / "wrong_version_runner.py"
FAST_LANE = REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"
TIMEOUT_ENV = "LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS"

AC_ID = "TQ-9101"
WV_DROP = "drop the retry_due condition"
WV_UNDONE = "the fix undone"
WV_ALIAS = "revert the fix"
WV_GATE = "the gate always allows"
WV_ONCE = "retry only once"
T1, T2, T3, T4 = (
    "test_t1_retry_gate_blocks_refresh", "test_t2_nothing_due_skips",
    "test_t3_undeclared_gate_check", "test_t4_discrimination_only",
)
SEAM_ABS, SEAM_ASSERT = "test_seam_absence", "test_seam_assertion"
NOTE = "\n# local note kept uncommitted\n"
MARK = "\n# altered: seam fixture marker\n"

_BASE = 'def refresh_config(refresh_due, retry_due):\n    if refresh_due:\n        return "refresh"\n    return "skip"\n'
_FIX = _BASE.replace("if refresh_due:", "if refresh_due and retry_due:")

_HEADER = '''\
import hashlib, json, os, subprocess, sys, time
from pathlib import Path
WORK, GITDIR, RUNLOG, PROBE, MARKER = @CONSTS@
ASWRITTEN_SHA = @SHA@
sys.path.insert(0, WORK)
import refresh_config as _rc_mod
from refresh_config import refresh_config
_SRC = Path(_rc_mod.__file__)
_ALTERED = b"altered" in _SRC.read_bytes()


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _log(name):
    with open(RUNLOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"test": name, "sha": _sha(_SRC), "altered": _ALTERED}) + "\\n")


def _probe():
    git = lambda *a: subprocess.run(["git", *a], cwd=WORK, capture_output=True, text=True).stdout
    runs = Path(GITDIR) / "leafcutter" / "wrong-version-runs"
    copies = [p.relative_to(GITDIR).as_posix() for p in runs.rglob("*")
              if p.is_file() and _sha(p) == ASWRITTEN_SHA] if runs.exists() else []
    tree = [p.name for p in Path(WORK).rglob("*") if p.is_file() and ".git" not in p.parts
            and "__pycache__" not in p.parts and p.name != "refresh_config.py"
            and _sha(p) == ASWRITTEN_SHA]
    rec = {"stash": git("stash", "list"), "status": git("status", "--porcelain"),
           "copies": copies, "tree_copies": tree}
    with open(PROBE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\\n")
'''

_HOOKS = {
    None: "",
    "sleep": "    if _ALTERED:\n        time.sleep(300)\n",
    "exit3": "    if _ALTERED:\n        os._exit(3)\n",
    "block": ("    if _ALTERED:\n        _end = time.time() + 150\n"
              "        while not os.path.exists(MARKER) and time.time() < _end:\n"
              "            time.sleep(0.1)\n"),
    "sabotage": "    if _ALTERED:\n        os.remove(_SRC)\n        os.mkdir(_SRC)\n",
}


def _t1(hook, weak):
    call = "(False, True)" if weak else "(True, False)"
    return (f"def {T1}():\n    # covers: {AC_ID}\n    _log({T1!r})\n    result = refresh_config{call}\n"
            f'    if result == "refresh":\n        _probe()\n{_HOOKS[hook]}    assert result == "skip"\n')


_BODIES = {
    "T2": f'def {T2}():\n    # covers: {AC_ID}\n    _log({T2!r})\n    assert refresh_config(False, False) == "skip"\n',
    "T3": f'def {T3}():\n    # covers: {AC_ID}\n    _log({T3!r})\n    assert refresh_config(True, False) == "skip"\n',
    "T4": (f'def {T4}():\n    # covers: {AC_ID}\n    _log({T4!r})\n'
           f'    assert refresh_config(True, False) == "skip" or _ALTERED\n'),
}
_SEAM = {
    "SEAM_ABS": ("test_seam_abs.py", f'def {SEAM_ABS}():\n    # covers: {AC_ID}\n    _log({SEAM_ABS!r})\n'
                 f'    if _ALTERED:\n        from nonexistent_gate_mod import gate\n'
                 f'    assert refresh_config(False, False) == "skip"\n'),
    "SEAM_ASSERT": ("test_seam_assert.py", f'def {SEAM_ASSERT}():\n    # covers: {AC_ID}\n    _log({SEAM_ASSERT!r})\n'
                    f'    assert not _ALTERED, "refresh_config.py carries an alteration"\n'),
}
_NAMES = {"T1": T1, "T2": T2, "T3": T3, "T4": T4, "SEAM_ABS": SEAM_ABS, "SEAM_ASSERT": SEAM_ASSERT}


@dataclass
class Sandbox:
    root: Path
    work: Path
    test_root: Path
    ac_root: Path
    base_sha: str
    manifest: Path
    as_written: bytes
    base_bytes: bytes | None
    probe: Path
    runlog: Path
    marker: Path
    altered: dict = field(default_factory=dict)

    @property
    def target(self) -> Path:
        return self.work / "refresh_config.py"

    @property
    def git_dir(self) -> Path:
        return Path(gitfx.run_git(["rev-parse", "--absolute-git-dir"], cwd=self.work).strip())

    @property
    def gate_dir(self) -> Path:
        return self.git_dir / "leafcutter" / "wrong-version-runs"

    def copies_of_as_written(self) -> list[Path]:
        if not self.gate_dir.exists():
            return []
        return [p for p in self.gate_dir.rglob("*") if p.is_file() and p.read_bytes() == self.as_written]


def _wb(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _spec(keys, t1_must_catch):
    spec = []
    for key in keys:
        if key == "T1":
            spec.append({"name": T1, "must_catch": list(t1_must_catch)})
        elif key == "T3":
            spec.append({"name": T3})
        elif key == "T4":
            spec.append({"name": T4, "angle": "discrimination"})
        else:
            spec.append({"name": _NAMES[key], "must_catch": [WV_DROP]})
    return spec


def build_sandbox(root: Path, *, tests=("T1", "T2", "T3", "T4"), t1_must_catch=(WV_ALIAS, WV_DROP),
                  weak_t1=False, hook=None, entries=("drop",), new_file_only=False,
                  uncommitted_note=False, marked=False, claims=False) -> Sandbox:
    """Build the sandbox repo, AC store, altered copies and manifest under *root*."""
    work, base_sha = gitfx.make_worktree(
        root, {".gitignore": "__pycache__/\n.pytest_cache/\n", "README.md": "sandbox\n"})
    if not new_file_only:
        _wb(work / "refresh_config.py", _BASE)
        base_sha = gitfx.commit_all(work, "base refresh_config")
    fix = _FIX + (MARK if marked else "")
    final = fix + (NOTE if uncommitted_note else "")
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    probe, runlog, marker = state / "probe.jsonl", state / "runlog.jsonl", state / "release.marker"
    digest = hashlib.sha256(final.encode("utf-8")).hexdigest()
    consts = repr((str(work), str(work / ".git"), str(runlog), str(probe), str(marker)))
    header = _HEADER.replace("@CONSTS@", consts).replace("@SHA@", repr(digest))
    fx = work / "fx_tests"
    body = [header]
    for key in tests:
        if key == "T1":
            body.append(_t1(hook, weak_t1))
        elif key in _BODIES:
            body.append(_BODIES[key])
    if len(body) > 1:
        _wb(fx / "test_refresh.py", "\n\n".join(body))
    for key in tests:
        if key in _SEAM:
            _wb(fx / _SEAM[key][0], header + "\n\n" + _SEAM[key][1])
    _wb(work / "refresh_config.py", fix)
    gitfx.commit_all(work, "the fix and its tests")
    if uncommitted_note:
        _wb(work / "refresh_config.py", final)
    ac_root = root / "ac_store"
    gitfx.write_ac_yaml(ac_root, AC_ID, _spec(tests, t1_must_catch))
    sb = Sandbox(root, work, fx, ac_root, base_sha, state / "alterations.json", final.encode("utf-8"),
                 None if new_file_only else _BASE.encode("utf-8"), probe, runlog, marker)
    _write_manifest(sb, entries, claims)
    return sb


def _write_manifest(sb: Sandbox, entries, claims: bool) -> None:
    text = sb.as_written.decode("utf-8")
    variants = {
        "drop": (WV_DROP, text.replace("if refresh_due and retry_due:", "if refresh_due:  # altered: retry_due dropped")),
        "gate": (WV_GATE, text.replace("if refresh_due and retry_due:", "if refresh_due and :")),
        "once": (WV_ONCE, text),
    }
    out = []
    for key in entries:
        name, altered = variants[key]
        copy = sb.root / "altered" / f"{key}_refresh_config.py"
        _wb(copy, altered)
        sb.altered[key] = copy
        diff = "".join(difflib.unified_diff(text.splitlines(True), altered.splitlines(True),
                                            "a/refresh_config.py", "b/refresh_config.py"))
        entry: dict[str, object] = {"name": name, "status": "prepared", "reason": None, "diff": diff,
                 "files": [{"path": "refresh_config.py", "altered_copy": str(copy)}]}
        if claims:
            entry.update({"caught": True, "caught_by": [T2], "outcome": "caught"})
        out.append(entry)
    sb.manifest.write_text(json.dumps({"work_key": "tq-9101-fx", "entries": out}), encoding="utf-8")


def runner_cmd(sb: Sandbox, sub: str = "run", ac_ids: str = AC_ID) -> list[str]:
    if sub != "run":
        return [sys.executable, str(RUNNER), sub]
    return [sys.executable, str(RUNNER), "run", "--ac-ids", ac_ids, "--test-root", str(sb.test_root),
            "--ac-root", str(sb.ac_root), "--base-ref", sb.base_sha, "--alterations", str(sb.manifest)]


def _env(timeout: str | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != TIMEOUT_ENV}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if timeout:
        env[TIMEOUT_ENV] = timeout
    return env


def run_runner(sb: Sandbox, *, timeout_env: str | None = None, ac_ids: str = AC_ID):
    """Run the runner CLI; return (CompletedProcess, parsed verdict dict)."""
    proc = subprocess.run(runner_cmd(sb, "run", ac_ids), cwd=sb.work, capture_output=True, text=True,
                          timeout=420, env=_env(timeout_env))
    return proc, parse_json(proc)


def run_recover(sb: Sandbox):
    proc = subprocess.run(runner_cmd(sb, "recover"), cwd=sb.work, capture_output=True, text=True,
                          timeout=120, env=_env())
    return proc, parse_json(proc)


def parse_json(proc) -> dict:
    try:
        parsed = json.loads(proc.stdout.strip())
    except ValueError as exc:
        msg = (f"runner printed no single JSON object (rc={proc.returncode}): "
               f"stdout={proc.stdout[-400:]!r} stderr={proc.stderr[-400:]!r}")
        raise AssertionError(msg) from exc
    assert isinstance(parsed, dict), f"runner JSON is not an object: {parsed!r}"
    return parsed


def rows(verdict: dict, test: str | None = None, wv: str | None = None) -> list[dict]:
    return [r for r in verdict.get("results", [])
            if (test is None or str(r.get("test", "")).endswith("::" + test))
            and (wv is None or r.get("wrong_version") == wv)]


def survivor_pairs(verdict: dict) -> list[tuple[str, str]]:
    return sorted((str(s["test"]).rsplit("::", 1)[-1], s["wrong_version"]) for s in verdict.get("survivors", []))


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_digest(work: Path) -> dict[str, str]:
    out = {}
    for p in sorted(work.rglob("*")):
        rel = p.relative_to(work)
        if ".git" in rel.parts or "__pycache__" in rel.parts or ".pytest_cache" in rel.parts:
            continue
        out[rel.as_posix()] = sha(p.read_bytes()) if p.is_file() else "<dir>"
    return out


def git_state(work: Path) -> dict[str, str]:
    return {"stash": gitfx.run_git(["stash", "list"], cwd=work),
            "status": gitfx.run_git(["status", "--porcelain"], cwd=work)}


def walk_strings(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in walk_strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in walk_strings(v)]
    return []


def norm(text: str) -> str:
    return text.replace("\\", "/").lower()


def run_red_baseline(sb: Sandbox) -> dict:
    proc = subprocess.run(
        [sys.executable, str(FAST_LANE), "verify_red_baseline", "--ac-ids", AC_ID, "--test-root",
         str(sb.test_root), "--base-ref", sb.base_sha, "--ac-root", str(sb.ac_root)],
        cwd=sb.work, capture_output=True, text=True, timeout=180, env=_env())
    return parse_json(proc)


def kill_tree(proc: subprocess.Popen) -> None:
    """Hard-kill *proc* and every child (no cleanup code in the runner can run)."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=60)
    else:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    proc.wait(timeout=60)


def start_runner_until_altered(sb: Sandbox, limit: float = 150.0) -> subprocess.Popen:
    """Start ``run`` in the background; return once refresh_config.py differs from as-written."""
    log = (sb.root / "state" / "runner.log").open("w")
    proc = subprocess.Popen(runner_cmd(sb), cwd=sb.work, stdout=log, stderr=log, env=_env(),
                            start_new_session=sys.platform != "win32")
    end = time.time() + limit
    while time.time() < end:
        if proc.poll() is not None:
            msg = f"runner exited ({proc.returncode}) before the file was ever altered"
            raise AssertionError(msg)
        try:
            if sb.target.read_bytes() != sb.as_written:
                return proc
        except OSError:
            pass
        time.sleep(0.05)
    kill_tree(proc)
    msg = "refresh_config.py was never altered while the runner ran"
    raise AssertionError(msg)
