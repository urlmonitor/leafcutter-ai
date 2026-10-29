"""
MODULE: unit_tests/build_orchestration/_tq500g1xii_fixtures.py
GOAL: Shared REAL sandbox and CLI drivers for the TQ-500g-1-xii test family (only a name that is new to the
    work, whose pinned old text no longer matches, or whose wording changed goes to the preparer).
BUSINESS CONTEXT: The work 07_TICKET-refresh-gate holds pinned replacements, from an earlier run, for names
    of test T1's entry. The entry then names a different set (a respelled name, a reworded name, a new
    name) and the code is changed between runs. Every fixture is built for real: the TQ-500g-1-xi git
    sandbox (refresh_config.py with a log line), an AC store written with yaml.safe_dump, pin files written
    with json.dumps in the pin store's own shape (through the xiii family's ``write_pins``), replies written
    with json.dumps. The writer (list) and the gate (finish) are only driven through their CLIs.
ARCHITECTURE: Not a test file (leading underscore). Reuses the xi and xiii drivers; the pin shape and the
    alteration identity are read back from disk and recomputed there, never through the module under test.
    The "return" line of refresh_config.py is the line of N2's pin; the gate condition is the line of the
    others, so a coder rewriting the one leaves the others' pins matching.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.build_orchestration._tq500g1xi_fixtures as f
import unit_tests.build_orchestration._tq500g1xiii_fixtures as w

WK = f.WK1
N1, N2, N5 = "drop the retry_due condition", "the gate always allows", "refresh on every call"
N3_PIN, N3_NOW = "retry only once", "Retry only once "
WARM, COLD = "skip the refresh when the cache is warm", "skip the refresh when the cache is cold"
SKIP_OLD, SKIP_REWRITTEN = 'return "skip"', "return 'skip'"
STALE_NEW = 'return "STALEPIN"'
WARM_NEW = "if refresh_due or True"
# What each pin replaces, and what a fresh preparation of the same name replaces it with.
PIN_REPLS = {
    N1: (f.REFRESH, f.COND, f.COND_ALT),
    N2: (f.REFRESH, SKIP_OLD, STALE_NEW),
    N3_PIN: (f.REFRESH, f.COND, "if True"),
    WARM: (f.REFRESH, f.COND, WARM_NEW),
}
FRESH_REPLS = {
    N2: (f.REFRESH, SKIP_REWRITTEN, "return 'refresh'"),
    COLD: (f.REFRESH, f.COND, "if not retry_due"),
    N5: (f.REFRESH, f.COND, "if refresh_due or retry_due"),
}


def spec(owed: list[str]) -> list[dict]:
    """T1's entry owes *owed* in that order, with refresh_config.py and settings.py in scope."""
    return [{"name": x.E1, "must_catch": list(owed), "in_scope_files": list(x.SETTINGS_FILES)}]


def build(root: Path, owed: list[str]) -> x.XSandbox:
    """The xi sandbox with T1 owing *owed*."""
    sb = f.build(root)
    set_owed(sb, owed)
    return sb


def set_owed(sb: x.XSandbox, owed: list[str]) -> None:
    """Rewrite the AC store so T1's entry now names *owed* (the entry changed between two runs)."""
    gitfx.write_ac_yaml(sb.ac_root, ix.AC_ID, spec(owed))


def pin(sb: x.XSandbox, *names: str) -> None:
    """Write the work's pin file holding the pinned replacement of each of *names* (see PIN_REPLS)."""
    w.write_pins(sb, {n: [PIN_REPLS[n]] for n in names}, WK)


def rewrite_return_line(sb: x.XSandbox) -> None:
    """The coder rewrites N2's pinned line (quote style only); the gate condition line stays as it was."""
    f.edit_source(sb, SKIP_OLD, SKIP_REWRITTEN)


def fresh_entries(*names: str) -> list[dict]:
    """The preparer's reply entries for *names* (see FRESH_REPLS), each caught by T1."""
    return [ix.prep(n, FRESH_REPLS[n], caught_by=[x.E1], would_catch=True, outcome="caught") for n in names]


def by_name(items: list[dict], name: str) -> dict:
    """The one item of *items* (owed, to_prepare or decisions) named exactly *name*."""
    hits = [i for i in items if i["name"] == name]
    assert len(hits) == 1, f"{name!r} is in {[i['name'] for i in items]!r}, expected exactly once"
    return hits[0]


def verdict_names(out: dict) -> list[str]:
    """The wrong_version spelling of every verdict row the gate printed."""
    return [r["wrong_version"] for r in out["verdict"]["results"]]
