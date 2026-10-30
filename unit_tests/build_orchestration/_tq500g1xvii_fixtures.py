"""
MODULE: unit_tests/build_orchestration/_tq500g1xvii_fixtures.py
GOAL: Shared REAL sandbox and drivers for the TQ-500g-1-xvii test family (a requirement may declare the exact
    replacement for a named wrong version; declared > pinned > prepared, and a declaration is checked the
    same way as a pin).
BUSINESS CONTEXT: The work 07_TICKET-refresh-gate guards TQ-9101, whose test T1 owes "propagation that reaches
    only one level deep" (PROP) and "drop the _lc_obs_installed guard" (GUARD). The AC names the code file
    observer.py; the sandbox reuses the TQ-500g-1-xiii refresh_config.py sandbox, so PROP's declared
    replacement edits refresh_config.py in the same way (a condition inside the one function T1 calls). The
    work holds pins for both names; PROP's pin differs from its declaration. Every fixture is built for real: a
    git sandbox, real pytest tests, an AC store written with yaml.safe_dump, pin files written with json.dumps
    in the pin store's own shape (the xiii fixture writer). The writer (list) and the gate (finish) are only
    driven through their CLIs.
ARCHITECTURE: Not a test file (leading underscore). It builds on the xiii / xi / ix fixtures; identity and pin
    bytes are read back from disk and recomputed there, never through the module under test.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.build_orchestration._tq500g1xi_fixtures as f
import unit_tests.build_orchestration._tq500g1xiii_fixtures as w

PROP = "propagation that reaches only one level deep"
GUARD = "drop the _lc_obs_installed guard"
WK, AC_ID, ENTRY = w.WK, ix.AC_ID, w.T1
REFRESH, TEST_REL, SETTINGS_PY = w.REFRESH, w.TEST_REL, w.SETTINGS_PY
OLD_BLOCK = f"    {w.COND}:\n        {w.RETURN_REFRESH}\n"
NEW_BLOCK = f"    if refresh_due or retry_due:\n        {w.RETURN_REFRESH}\n"
DECLARED = (REFRESH, OLD_BLOCK, NEW_BLOCK)  # the declared replacement of PROP
PIN_PROP = (REFRESH, w.RETURN_REFRESH, 'return "skip"')  # PROP's earlier pin: a different replacement
PIN_GUARD = (REFRESH, 'return "skip"', 'return "refresh"')  # GUARD's pin
GUESS = (REFRESH, 'return "skip"', 'return "refresh"')  # a preparer's answer for PROP: neither the pin nor the declaration
DECLARED_BY = [{"ac_id": AC_ID, "entry": ENTRY}]
PREFIX = f"declared on {AC_ID}, entry {ENTRY}: "


def decl(*repls: tuple[str, str, str], name: str = PROP) -> dict:
    """A ``declared_replacements`` object: ``{name: [{path, old, new}]}``."""
    return {name: f.repl_dicts(*repls)}


def spec(names: list[str], declared: dict | None) -> list[dict]:
    """T1's entry owes *names*; with *declared* it also carries ``declared_replacements``. T2's entry names nothing."""
    t1 = {"name": ENTRY, "must_catch": list(names), "in_scope_files": [REFRESH]}
    if declared is not None:
        t1["declared_replacements"] = declared
    return [t1, {"name": w.T2}]


def set_ac(sb: x.XSandbox, names: list[str], declared: dict | None) -> None:
    """(Re)write the AC store file of TQ-9101 with yaml.safe_dump."""
    gitfx.write_ac_yaml(sb.ac_root, AC_ID, spec(names, declared))


def build(root: Path, names: list[str], declared: dict | None, pins: dict | None = None) -> x.XSandbox:
    """The xiii sandbox, with T1's entry as given and (optionally) the work's pin file written."""
    sb = w.build(root, names=names)
    set_ac(sb, names, declared)
    if pins:
        w.write_pins(sb, pins)
    return sb


def rows_of(out: dict, name: str) -> list[dict]:
    """The verdict rows of *name* (an AssertionError when there are none)."""
    rows = [r for r in out["verdict"]["results"] if r["wrong_version"] == name]
    assert rows, f"no row for {name!r}: {out['verdict']['results']}"
    return rows


def plan(sb: x.XSandbox) -> tuple[list[str], list[tuple[str, str]]]:
    """Run the writer's list step; return ``(names to prepare, [(name, source)])``."""
    proc, listed = f.run_list(sb, WK)
    assert proc.returncode == 0 and listed["error"] is None, (proc.returncode, listed, proc.stderr[-300:])
    return [i["name"] for i in listed["to_prepare"]], w.decisions(listed)
