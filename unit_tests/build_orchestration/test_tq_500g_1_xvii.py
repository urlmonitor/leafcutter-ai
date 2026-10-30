"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_xvii.py
GOAL: RED tests for TQ-500g-1-xvii: a requirement may declare the exact replacement for a named wrong version
    (``declared_replacements`` on a test_spec entry); declared > pinned > prepared, the declaration is held to the
    same checks as a pin and the same refusals as a prepared replacement, a failing declaration is unfinished
    (never prepared, never the pin), and the pin is left alone while the declaration exists.
BUSINESS CONTEXT: Every test drives the real writer (list) and gate (finish) CLIs in fresh subprocesses on a
    real git sandbox with real pytest tests, an AC store written with yaml.safe_dump and pin files written in the
    pin store's own shape (see _tq500g1xvii_fixtures.py). Today ``declared_replacements`` is an unknown key that is
    ignored by the runner side, so the pin is applied (or the name is prepared) and each test fails on an assertion
    about the JSON the CLIs print or the files they leave, never on an import.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1xi_fixtures as f
import unit_tests.build_orchestration._tq500g1xiii_fixtures as w
import unit_tests.build_orchestration._tq500g1xvii_fixtures as d

DECLARED_DICTS = f.repl_dicts(d.DECLARED)


def _two_pins() -> dict:
    return {d.PROP: [d.PIN_PROP], d.GUARD: [d.PIN_GUARD]}


def test_declared_replacement_wins_over_pin_and_preparer():
    # covers: TQ-500g-1-xvii
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = d.build(Path(tmp), [d.PROP, d.GUARD], d.decl(d.DECLARED), _two_pins())
        before = f.pin_bytes(sb, d.WK)
        to_prepare, decisions = d.plan(sb)
        assert to_prepare == [], f"a declared or pinned name was sent to the preparer: {to_prepare}"
        assert decisions == [(d.PROP, "declared"), (d.GUARD, f.PINNED)], decisions
        # The preparer's answer for PROP (here a stray one) is never used: the name was not asked.
        done, out = f.finish(sb, [ix.prep(d.PROP, d.GUESS)], d.WK)
        assert out["stopped_at"] is None and out["gate_passed"] is True, out
        entry = ix.entry(f.manifest(sb, d.WK), d.PROP)
        assert entry["status"] == "prepared" and entry["source"] == "declared", entry
        assert entry["replacements"] == DECLARED_DICTS, f"the pin or the guess was applied: {entry['replacements']}"
        assert entry["alteration_id"] == f.alteration_id(DECLARED_DICTS), entry["alteration_id"]
        assert entry["declared_by"] == d.DECLARED_BY, entry
        expected = (sb.work / d.REFRESH).read_text(encoding="utf-8").replace(d.OLD_BLOCK, d.NEW_BLOCK, 1)
        assert f.copy_text(entry) == expected, "the declared replacement was not applied to the file as it now stands"
        rows = d.rows_of(out, d.PROP)
        assert {r["source"] for r in rows} == {"declared"} and {r["result"] for r in rows} == {"caught"}, rows
        assert all(r["declared_by"] == d.DECLARED_BY and r["replacements"] == DECLARED_DICTS for r in rows), rows
        control = d.rows_of(out, d.GUARD)  # the undeclared name keeps its pin and carries no declaration
        assert {r["source"] for r in control} == {f.PINNED}, control
        assert all("declared_by" not in r for r in control), control
        assert f.pin_bytes(sb, d.WK) == before, "the pin file changed: the declaration was written to it, or the pin was touched"
    # A declared name the work holds NO pin for: the passing declaration must still never become a pin
    # (above, PROP's existing pin alone would keep a declaration out of the store).
    with tempfile.TemporaryDirectory() as tmp:
        sb = d.build(Path(tmp), [d.PROP], d.decl(d.DECLARED))
        d.plan(sb)
        done, out = f.finish(sb, None, d.WK)
        assert out["gate_passed"] is True and {r["source"] for r in d.rows_of(out, d.PROP)} == {"declared"}, out
        assert out["pins"]["pinned"] == [], f"a passing declaration was written into the pin store: {out['pins']}"
        assert f.key_of(d.PROP) not in w.pins_or_empty(sb, d.WK), "the declaration is in the pin file"


def _failing_case(root: Path, repl: tuple[str, str, str], *, stale: bool = False):
    """PROP declares *repl*; a valid pin for PROP exists; the preparer's answer for PROP is a valid replacement."""
    sb = d.build(root, [d.PROP], d.decl(repl), {d.PROP: [d.PIN_PROP]})
    if stale:  # the declared old text is edited away; the pin's old text is untouched
        f.edit_source(sb, d.OLD_BLOCK, f"    if retry_due and refresh_due:\n        {w.RETURN_REFRESH}\n")
    before = f.pin_bytes(sb, d.WK)
    to_prepare, _ = d.plan(sb)
    assert to_prepare == [], f"a failing declaration was sent to the preparer: {to_prepare}"
    done, out = f.finish(sb, [ix.prep(d.PROP, d.GUESS)], d.WK)
    entry = ix.entry(f.manifest(sb, d.WK), d.PROP)
    assert entry["status"] == "could_not_prepare" and entry["files"] == [], f"a fallback was applied: {entry}"
    assert entry["reason"].startswith(d.PREFIX), entry["reason"]
    assert out["gate_passed"] is False and out["verdict"]["reason"] == "unfinished", out["verdict"]["reason"]
    rows = w.unfinished(out, d.PROP)
    assert len(rows) == 1 and entry["reason"] in rows[0]["detail"], out["verdict"]["unfinished"]
    assert w.result_words(out, d.PROP) <= {"invalid", "not_applied", "not_run"}, w.result_words(out, d.PROP)
    assert d.PROP not in w.survivor_names(out)
    assert f.pin_bytes(sb, d.WK) == before, "the pin was changed or cleared"
    return sb, entry


def test_failing_declaration_is_unfinished_never_prepared_never_the_pin():
    # covers: TQ-500g-1-xvii
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        _, entry = _failing_case(Path(tmp) / "stale", d.DECLARED, stale=True)
        assert entry["reason"] == f"{d.PREFIX}target changed", entry["reason"]
    refusals = [
        ("test file", (d.TEST_REL, "t1 ran", "t1 ran again"), "is a test file"),
        ("not in scope", (d.SETTINGS_PY, "RETRY_LIMIT = 3", "RETRY_LIMIT = 1"), "is not in scope for"),
        ("outside", ("../outside.py", "x", "y"), "outside the repository"),
        ("vcs folder", (".git/HEAD", "ref", "rof"), "inside the version-control folder"),
    ]
    for label, repl, fragment in refusals:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / label.replace(" ", "_")
            sb, entry = _failing_case(root, repl)
            assert fragment in entry["reason"], f"{label}: {entry['reason']}"
            if label == "test file":
                assert "t1 ran again" not in (sb.work / d.TEST_REL).read_text(encoding="utf-8"), "a declaration altered a test file"


def test_undeclared_name_still_comes_from_pin_or_preparer():
    # covers: TQ-500g-1-xvii
    # angle: boundary
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for label in ("with", "without"):
            (base / label).mkdir()
        # Pinned: GUARD has a pin that matches, with and without a declaration on PROP.
        declared = d.build(base / "with", [d.PROP, d.GUARD], d.decl(d.DECLARED), {d.GUARD: [d.PIN_GUARD]})
        plain = d.build(base / "without", [d.PROP, d.GUARD], None, {d.GUARD: [d.PIN_GUARD]})
        prep_d, dec_d = d.plan(declared)
        prep_p, dec_p = d.plan(plain)
        assert dict(dec_d)[d.GUARD] == dict(dec_p)[d.GUARD] == f.PINNED, (dec_d, dec_p)
        assert dict(dec_d)[d.PROP] == "declared" and dict(dec_p)[d.PROP] == f.NOT_PINNED, (dec_d, dec_p)
        assert prep_d == [] and prep_p == [d.PROP], (prep_d, prep_p)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for label in ("with", "without"):
            (base / label).mkdir()
        # Prepared: no pin at all; GUARD goes to the preparer exactly as without the declaration.
        declared = d.build(base / "with", [d.PROP, d.GUARD], d.decl(d.DECLARED))
        plain = d.build(base / "without", [d.PROP, d.GUARD], None)
        prep_d, dec_d = d.plan(declared)
        prep_p, dec_p = d.plan(plain)
        assert dict(dec_d)[d.GUARD] == dict(dec_p)[d.GUARD] == f.NOT_PINNED, (dec_d, dec_p)
        assert prep_d == [d.GUARD] and prep_p == [d.PROP, d.GUARD], (prep_d, prep_p)
        done, out = f.finish(declared, [ix.prep(d.GUARD, d.PIN_GUARD)], d.WK)
        assert out["gate_passed"] is True, out
        assert ix.entry(f.manifest(declared, d.WK), d.GUARD)["source"] == f.NOT_PINNED
        stored = f.pins(declared, d.WK)
        assert list(stored) == [f.key_of(d.GUARD)], f"the declaration was written to the pin store: {list(stored)}"


def test_pin_used_again_after_the_declaration_is_removed():
    # covers: TQ-500g-1-xvii
    # angle: boundary
    with tempfile.TemporaryDirectory() as tmp:
        sb = d.build(Path(tmp), [d.PROP, d.GUARD], d.decl(d.DECLARED), _two_pins())
        before = f.pin_bytes(sb, d.WK)
        d.plan(sb)
        done, out = f.finish(sb, None, d.WK)
        assert out["gate_passed"] is True and {r["source"] for r in d.rows_of(out, d.PROP)} == {"declared"}, out
        assert f.pin_bytes(sb, d.WK) == before, "control: the pin was changed while the declaration existed"
        d.set_ac(sb, [d.PROP, d.GUARD], None)  # the declaration is deleted from the entry
        to_prepare, decisions = d.plan(sb)
        assert to_prepare == [] and decisions == [(d.PROP, f.PINNED), (d.GUARD, f.PINNED)], decisions
        done, out = f.finish(sb, None, d.WK)
        assert out["gate_passed"] is True, out
        entry = ix.entry(f.manifest(sb, d.WK), d.PROP)
        pin_dicts = f.repl_dicts(d.PIN_PROP)
        assert entry["source"] == f.PINNED and entry["replacements"] == pin_dicts, entry
        assert "declared_by" not in entry and all("declared_by" not in r for r in d.rows_of(out, d.PROP))
        expected = (sb.work / d.REFRESH).read_text(encoding="utf-8").replace(d.PIN_PROP[1], d.PIN_PROP[2], 1)
        assert f.copy_text(entry) == expected, "the earlier pin was not the replacement applied"
        assert f.pin_bytes(sb, d.WK) == before


def test_tq_500g_1_xvii_reachable_from_entry_point():
    # covers: TQ-500g-1-xvii
    # angle: reachability
    # Entry point (CLI via subprocess): python scripts/build_orchestration/wrong_version_gate.py finish, with
    # wrong_version_writer.py list before it. A valid declaration is applied and judged; the same declaration
    # made stale must not reach the runner as an alteration: the gate's exit status consumes the refusal.
    with tempfile.TemporaryDirectory() as tmp:
        sb = d.build(Path(tmp) / "ok", [d.PROP], d.decl(d.DECLARED))
        proc, out = f.finish(sb, None, d.WK)
        assert proc.returncode == 0 and out["gate_passed"] is True, (proc.returncode, out)
        assert ix.entry(f.manifest(sb, d.WK), d.PROP)["source"] == "declared"
        assert {r["result"] for r in d.rows_of(out, d.PROP)} == {"caught"}
        stale = d.build(Path(tmp) / "stale", [d.PROP], d.decl(d.DECLARED))
        f.edit_source(stale, d.OLD_BLOCK, f"    if retry_due and refresh_due:\n        {w.RETURN_REFRESH}\n")
        proc, out = f.finish(stale, None, d.WK)
        assert proc.returncode != 0 and out["gate_passed"] is False and out["verdict"]["reason"] == "unfinished", (proc.returncode, out)
        entry = ix.entry(f.manifest(stale, d.WK), d.PROP)
        assert entry["status"] == "could_not_prepare" and entry["reason"] == f"{d.PREFIX}target changed", entry
