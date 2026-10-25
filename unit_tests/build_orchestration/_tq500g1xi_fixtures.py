"""
MODULE: unit_tests/build_orchestration/_tq500g1xi_fixtures.py
GOAL: Shared REAL sandbox and CLI drivers for the TQ-500g-1-xi test family (a named wrong version, once
    prepared and passed, is pinned for the work and replayed on the current code by every later run).
BUSINESS CONTEXT: The work 07_TICKET-refresh-gate guards TQ-9101, whose test T1 names two wrong versions.
    Every fixture is built for real: the TQ-500g-1-x git sandbox (refresh_config.py committed as the fix, a
    base commit before it), an AC store written with yaml.safe_dump, replies written with json.dumps in the
    TQ-500g-1-iv reply contract shape, verdicts built with the runner's own ``assemble`` / ``row``. The
    writer (list, write, pin) and the gate (finish) are only ever driven through their CLIs (subprocess).
ARCHITECTURE: Not a test file (leading underscore). The pin store location, the pin shape and the
    alteration identity are read back from disk and recomputed here independently (never through the
    module under test), so a test cannot pass on the code agreeing with itself.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g
import unit_tests.build_orchestration._tq500g1x_fixtures as x

sys.path.insert(0, str(ix.REPO_ROOT / "scripts" / "build_orchestration"))
from _wvr_scope import norm_name  # noqa: E402
from _wvr_verdict import assemble, row  # noqa: E402

WK1, WK2, WK3 = "07_TICKET-refresh-gate", "08_TICKET-refresh-retry", "09_TICKET-fresh-key"
N1, ALWAYS = "drop the retry_due condition", "the gate always allows"
REFRESH = "refresh_config.py"
COND, COND_ALT = x.COND, x.COND_ALT
LOG_OLD, LOG_NEW = "log.info('refresh')", "log.info('refresh starting')"
PIN_KEYS = ["name", "replacements", "alteration_id", "failed_check", "reset", "cleared_alteration_id"]
NOT_PINNED, PINNED = "prepared: not pinned", "pinned"


def spec(*, with_alias: bool = False) -> list[dict]:
    """The TQ-9101 test entries: T1 owes N1 and ALWAYS (and, with_alias, the "revert the fix" alias too)."""
    names = [ix.ALIAS, N1] if with_alias else [N1, ALWAYS]
    return [{"name": x.E1, "must_catch": names, "in_scope_files": list(x.SETTINGS_FILES)}]


def build(root: Path, *, with_alias: bool = False) -> x.XSandbox:
    """The TQ-500g-1-x sandbox, T1 as above, refresh_config.py carrying a log line (an uncommitted edit)."""
    sb = x.build(root)
    gitfx.write_ac_yaml(sb.ac_root, ix.AC_ID, spec(with_alias=with_alias))
    src = x.FIX_SRC.replace("from settings import RETRY_LIMIT\n", "import logging\nfrom settings import RETRY_LIMIT\n\nlog = logging.getLogger(__name__)\n")
    src = src.replace('        return "refresh"', f'        {LOG_OLD}\n        return "refresh"')
    assert LOG_OLD in src and "logging" in src, "the fixture source lost its log line"
    (sb.work / REFRESH).write_bytes(src.encode("utf-8"))
    return sb


def edit_source(sb: x.XSandbox, old: str, new: str) -> None:
    """Edit refresh_config.py in the working tree (a coder changing the code between two runs)."""
    path = sb.work / REFRESH
    text = path.read_bytes().decode("utf-8")
    assert text.count(old) == 1, f"{old!r} is not exactly once in {REFRESH}"
    path.write_bytes(text.replace(old, new).encode("utf-8"))


def repl(new: str, old: str = COND) -> tuple[str, str, str]:
    """One ``(path, old, new)`` replacement in refresh_config.py."""
    return (REFRESH, old, new)


def first_entries(n1: str = COND_ALT, always: str = "if True") -> list[dict]:
    """The preparer's reply entries; they carry extras (a diff, caught_by) that must never reach a pin."""
    return [ix.prep(N1, repl(n1), diff=ix.WRONG_DIFF, caught_by=[x.E1], would_catch=True, outcome="caught"),
            ix.prep(ALWAYS, repl(always), diff=ix.WRONG_DIFF, caught_by=[x.E1])]


def reply_text(entries: list[dict], work_key: str) -> str:
    """The test-breaker reply text for *entries* (json.dumps), for the writer of *work_key*."""
    return json.dumps(ix.reply_obj(entries, work_key=work_key))


def run_list(sb: x.XSandbox, work_key: str | None):
    """Run the writer's list step (``--work-key`` omitted when None); return ``(proc, JSON)``."""
    cmd = [sys.executable, str(ix.WRITER), "list"]
    if work_key is not None:
        cmd += ["--work-key", work_key]
    cmd += ["--ac-ids", ix.AC_ID, "--ac-root", str(sb.ac_root), "--test-root", str(sb.work), "--base-ref", sb.base_sha]
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=120, env=x.env())
    return proc, ix.parse_one_json(proc)


def run_pin(sb: x.XSandbox, work_key: str, manifest: Path, verdict: dict):
    """Run the writer's pin step with *verdict* (the runner's run JSON) on stdin; return ``(proc, JSON)``."""
    cmd = [sys.executable, str(ix.WRITER), "pin", "--work-key", work_key, "--manifest", str(manifest),
           "--test-root", str(sb.work)]
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=120, env=x.env(),
                          input=json.dumps(verdict))
    return proc, ix.parse_one_json(proc, "pin step")


def finish(sb: x.XSandbox, entries: list[dict] | None, work_key: str):
    """Run the gate's finish for *work_key* with a reply of *entries* (None: an empty reply)."""
    text = "" if entries is None else reply_text(entries, work_key)
    proc, out = g.run_finish(sb, text, work_key=work_key)
    g.assert_shape(proc, out)
    return proc, out


def pin_path(sb: x.XSandbox, work_key: str) -> Path:
    """Where the pins of *work_key* must be: outside the work folder the write step clears."""
    return sb.git_dir / "leafcutter" / "pins" / f"{work_key}.json"


def pin_bytes(sb: x.XSandbox, work_key: str) -> bytes:
    """The pin file's bytes; an AssertionError when it is not on disk."""
    path = pin_path(sb, work_key)
    assert path.is_file(), f"no pin file at {path}"
    return path.read_bytes()


def pins(sb: x.XSandbox, work_key: str) -> dict:
    """The pin file's ``pins`` object, after checking the top-level shape."""
    data = json.loads(pin_bytes(sb, work_key).decode("utf-8"))
    assert list(data) == ["work_key", "pins"] and data["work_key"] == work_key, list(data)
    return data["pins"]


def manifest(sb: x.XSandbox, work_key: str) -> dict:
    """The alterations manifest the write step left for *work_key*."""
    path = sb.git_dir / "leafcutter" / "work" / work_key / "alterations.json"
    assert path.is_file(), f"no manifest at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def copy_text(entry: dict) -> str:
    """The text of the one altered copy of a manifest *entry*."""
    assert len(entry["files"]) == 1, entry["files"]
    return Path(entry["files"][0]["altered_copy"]).read_text(encoding="utf-8")


def alteration_id(replacements: list[dict]) -> str:
    """The identity of an ordered replacement list, computed here from the spec, not from the code under test."""
    canon = json.dumps(replacements, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()[:16]


def repl_dicts(*repls: tuple[str, str, str]) -> list[dict]:
    """``[{path, old, new}]`` for *repls*."""
    return [{"path": p, "old": o, "new": n} for p, o, n in repls]


def git_files(sb: x.XSandbox) -> set[str]:
    """Every file under the git directory (relative, POSIX; git's own ``index`` left out)."""
    root = sb.git_dir
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name not in {"index"}}


def key_of(name: str) -> str:
    """The pin key of *name*: the shared normaliser, never a second one."""
    return norm_name(name)


def hand_manifest(sb: x.XSandbox, work_key: str, entries: list[dict], name: str = "pin_manifest.json") -> Path:
    """A manifest file for the pin step (json.dumps; entries carry name, status, source, replacements, alteration_id)."""
    full = [{"reason": None, "files": [], "diff": "", **e} for e in entries]
    path = sb.root / name
    path.write_text(json.dumps({"work_key": work_key, "entries": full}), encoding="utf-8")
    return path


def prepared_entry(name: str, source: str, *repls: tuple[str, str, str]) -> dict:
    """A manifest entry of a prepared name with its replacements and their identity."""
    dicts = repl_dicts(*repls)
    return {"name": name, "status": "prepared", "source": source, "replacements": dicts, "alteration_id": alteration_id(dicts)}


def verdict_of(*rows: tuple[str, str, str]) -> dict:
    """The runner's run JSON for ``(test, wrong_version, result)`` rows, built with the runner's own assemble/row."""
    return assemble([row(t, wv, res, "detail of the run") for t, wv, res in rows])
