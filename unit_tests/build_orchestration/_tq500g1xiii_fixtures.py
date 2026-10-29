"""
MODULE: unit_tests/build_orchestration/_tq500g1xiii_fixtures.py
GOAL: Shared REAL sandbox and CLI drivers for the TQ-500g-1-xiii test family (every run re-checks each
    pinned replacement against the current code before any wrong version is run; a pin that fails a check
    is neither used nor dropped but prepared again).
BUSINESS CONTEXT: The work 07_TICKET-refresh-gate holds pinned replacements for six names of test T1's
    entry (P1 to P6). The code has changed since they were pinned, so each pin fails (or passes) exactly one
    check: P1 passes all; P2 old text now twice; P3 new text calls a renamed module-level function; P4 new
    text equals the current text; P5 changes a line in a function T1 does not call (T2, whose entry names
    nothing, does); P6 alters settings.py, which left the entry's in_scope_files. Every fixture is built for
    real: a git sandbox (the fix committed on top of a base commit), real pytest tests, an AC store written
    with yaml.safe_dump, pin files written with json.dumps in the pin store's own shape, replies written
    with json.dumps. The writer (list) and the gate (finish) are only driven through their CLIs.
ARCHITECTURE: Not a test file (leading underscore). It reuses the xi family's drivers (``run_list``,
    ``finish``, pin readers) so the pin shape and location are read back from disk and recomputed here, never
    through the module under test. T1 appends one line to a log file outside the repository each time it
    runs, so the number of pytest runs the list step made is observable.
"""

from __future__ import annotations

import json
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.build_orchestration._tq500g1xi_fixtures as f

REFRESH, SETTINGS_PY, TEST_REL = "refresh_config.py", "settings.py", "tests/test_refresh_gate.py"
WK = "07_TICKET-refresh-gate"
T1, T2 = "test_t1_refresh_gate_holds", "test_t2_idle_state_is_idle"
P1, P2, P3 = "always skip the refresh", "drop the retry_due condition", "cap the retries at a looked-up limit"
P4, P5, P6 = "keep the flag on", "mark the idle state busy", "lower the retry limit"
SIX = [P1, P2, P3, P4, P5, P6]
RT, FRESH = "refresh through the old helper", "refresh without the retry check"
COND = "if refresh_due and retry_due"
FLAG, MAX_TRIES, IDLE = 'FLAG = "on"', "MAX_TRIES = 3", 'return "idle"'
RETURN_REFRESH = 'return "refresh"'
NOT_IN_SCOPE, TWICE = "re-prepared: not in scope", "re-prepared: old text found 2 times"
DID_NOT_LOAD, NOTHING = "re-prepared: did not load", "re-prepared: changes nothing"
NO_LINE = "re-prepared: changes no line the tests naming it run"
REASONS = {P2: TWICE, P3: DID_NOT_LOAD, P4: NOTHING, P5: NO_LINE, P6: NOT_IN_SCOPE}

# The code as it NOW stands: the coder renamed old_limit_value to limit_value and added audit_gate, which
# holds a second copy of the gate condition.
# It also holds a dataclass under postponed annotations, which only executes when the module is registered
# in sys.modules first, as a real import does (the load check once missed that and read every such file
# as "did not load").
CURRENT_SRC = (
    '"""Refresh gate."""\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass\n\n'
    "from settings import RETRY_LIMIT\n\n" + FLAG + "\n" + MAX_TRIES + "\n\n\n"
    "@dataclass\nclass GateState:\n    due: bool\n\n\n"
    "def limit_value():\n    return RETRY_LIMIT\n\n\n"
    f"def refresh_config(refresh_due, retry_due):\n    {COND}:\n        {RETURN_REFRESH}\n"
    '    return "skip"\n\n\n'
    f"def audit_gate(refresh_due, retry_due):\n    {COND}:\n        return True\n    return False\n\n\n"
    f"def idle_state():\n    {IDLE}\n"
)
BASE_SRC = CURRENT_SRC.replace(f"    {COND}:\n        {RETURN_REFRESH}", f"    if refresh_due:\n        {RETURN_REFRESH}")
SETTINGS = "RETRY_LIMIT = 3\nTIMEOUT = 5\n"


def _tests_py(log: Path, work: Path) -> str:
    """The two real tests: T1 (names the six) logs each run and checks the gate; T2 runs idle_state."""
    return (
        f"import sys\n\nsys.path.insert(0, {str(work)!r})\n"
        "from refresh_config import idle_state, limit_value, refresh_config\n\n\n"
        f"def {T1}():\n    # covers: {ix.AC_ID}\n    with open({str(log)!r}, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('t1 ran\\n')\n"
        '    assert refresh_config(True, False) == "skip"\n    assert refresh_config(True, True) == "refresh"\n'
        "    assert limit_value() == 3\n\n\n"
        f'def {T2}():\n    # covers: {ix.AC_ID}\n    assert idle_state() == "idle"\n'
    )


def spec(names: list[str], scope: list[str] | None = None) -> list[dict]:
    """T1's entry owes *names* (scope: refresh_config.py only); T2's entry names nothing."""
    return [{"name": T1, "must_catch": list(names), "in_scope_files": [REFRESH] if scope is None else scope}, {"name": T2}]


def run_log(sb: x.XSandbox) -> Path:
    """The file T1 appends a line to on each run (outside the repository)."""
    return sb.root / "t1_runs.log"


def log_lines(sb: x.XSandbox) -> int:
    """How many times T1 has run so far (the log is absent before the first run)."""
    path = run_log(sb)
    return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0


def build(root: Path, names: list[str] | None = None) -> x.XSandbox:
    """The sandbox: base commit, the fix committed on top, an uncommitted note; T1 owes *names* (default the six)."""
    work, _ = gitfx.make_worktree(root, {"README.md": "sandbox\n"})
    x._wb(work / ".gitignore", "__pycache__/\n.pytest_cache/\n")  # noqa: SLF001 -- the one shared file writer
    x._wb(work / REFRESH, BASE_SRC)  # noqa: SLF001
    x._wb(work / SETTINGS_PY, SETTINGS)  # noqa: SLF001
    x._wb(work / TEST_REL, _tests_py(run_log(x.XSandbox(root, work, root, False)), work))  # noqa: SLF001
    base_sha = gitfx.commit_all(work, "base")
    x._wb(work / REFRESH, CURRENT_SRC)  # noqa: SLF001
    gitfx.commit_all(work, "the fix")
    x._wb(work / "scratch_note.txt", "uncommitted note\n")  # noqa: SLF001
    ac_root = root / "ac_store"
    gitfx.write_ac_yaml(ac_root, ix.AC_ID, spec(SIX if names is None else names))
    return x.XSandbox(root, work, ac_root, False, base_sha)


def write_pins(sb: x.XSandbox, pins: dict[str, list[tuple[str, str, str]]], work_key: str = WK) -> None:
    """Write the work's pin file (json.dumps, the pin store's own shape): ``{name: [(path, old, new)]}``."""
    body = {}
    for name, repls in pins.items():
        dicts = f.repl_dicts(*repls)
        body[f.key_of(name)] = dict(zip(f.PIN_KEYS, (name, dicts, f.alteration_id(dicts), None, False, None), strict=True))
    path = f.pin_path(sb, work_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps({"work_key": work_key, "pins": body}, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def six_pins() -> dict[str, list[tuple[str, str, str]]]:
    """The six pinned replacements, as they were prepared against the code before it changed."""
    return {
        P1: [(REFRESH, RETURN_REFRESH, 'return "skip"')],
        P2: [(REFRESH, COND, "if refresh_due or retry_due")],
        P3: [(REFRESH, MAX_TRIES, "MAX_TRIES = old_limit_value()")],
        P4: [(REFRESH, FLAG, FLAG)],
        P5: [(REFRESH, IDLE, 'return "busy"')],
        P6: [(SETTINGS_PY, "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")],
    }


def fresh_p2() -> dict:
    """The preparer's fresh answer for P2: old text once (it includes the line only refresh_config has), a line T1 runs."""
    old = f"    {COND}:\n        {RETURN_REFRESH}\n"
    return ix.prep(P2, (REFRESH, old, f"    if refresh_due or retry_due:\n        {RETURN_REFRESH}\n"))


def decisions(listed: dict) -> list[tuple[str, str]]:
    """``(name, source)`` of every decision a list payload prints."""
    return [(d["name"], d["source"]) for d in listed["decisions"]]


def pins_or_empty(sb: x.XSandbox, work_key: str) -> dict:
    """The ``pins`` object of the work's pin file; ``{}`` when no pin file exists."""
    return f.pins(sb, work_key) if f.pin_path(sb, work_key).is_file() else {}


def unfinished(out: dict, name: str) -> list[dict]:
    """The verdict's unfinished entries for *name*."""
    return [u for u in out["verdict"]["unfinished"] if u["wrong_version"] == name]


def result_words(out: dict, name: str) -> set[str]:
    """Every result word of the verdict rows of *name*."""
    return {r["result"] for r in out["verdict"]["results"] if r["wrong_version"] == name}


def survivor_names(out: dict) -> set[str]:
    """The wrong versions in the verdict's survivors."""
    return {s["wrong_version"] for s in out["verdict"]["survivors"]}
