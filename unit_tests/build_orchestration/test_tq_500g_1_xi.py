"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_xi.py
GOAL: RED tests for TQ-500g-1-xi: once a named wrong version is prepared and passes its checks for a piece
    of work, every later run of that work applies the same replacement to the CURRENT code instead of asking
    the preparer again (pin store, plan, list --work-key, write step, pin step, finish's ``pins``).
BUSINESS CONTEXT: Every test drives the real writer and gate CLIs (subprocess, fresh processes) on a real git
    sandbox and a real AC store (see _tq500g1xi_fixtures.py). Today ``list`` knows no ``--work-key``, no
    ``to_prepare`` and the writer has no ``pin`` step, so each test fails on an assertion about the JSON the
    CLIs print or the files they leave, never on an import.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.build_orchestration._tq500g1xi_fixtures as f

BOTH = [f.N1, f.ALWAYS]


def _names(items: list[dict]) -> list[str]:
    return [i["name"] for i in items]


def _decisions(listed: dict) -> list[tuple[str, str]]:
    return [(d["name"], d["source"]) for d in listed["decisions"]]


def _first_run(sb, work_key: str = f.WK1, entries: list[dict] | None = None) -> dict:
    """List, then finish with the preparer's reply: the first run of the work; it must pass and pin."""
    proc, listed = f.run_list(sb, work_key)
    assert proc.returncode == 0 and list(listed) == ix.LIST_KEYS, (proc.returncode, listed, proc.stderr[-300:])
    done, out = f.finish(sb, f.first_entries() if entries is None else entries, work_key)
    assert done.returncode == 0 and out["gate_passed"] is True and out["stopped_at"] is None, out
    return out


def _run1_pins_applied_replacements(sb) -> tuple[dict, bytes]:
    """Run 1: the preparer is asked, the gate passes, both are pinned from the replacements the writer applied.

    The reply's replacement carries a key beside path/old/new: only the applied path/old/new may travel on.
    """
    entries = f.first_entries()
    entries[0]["replacements"][0]["why"] = "WRONGREPLKEY"
    done, out1 = f.finish(sb, entries, f.WK1)
    assert done.returncode == 0 and out1["gate_passed"] is True, out1
    assert out1["pins"] and out1["pins"]["error"] is None, out1["pins"]
    assert sorted(_names(out1["pins"]["pinned"])) == sorted(BOTH), out1["pins"]
    m1_n1 = ix.entry(f.manifest(sb, f.WK1), f.N1)
    n1_repl = f.repl_dicts(f.repl(f.COND_ALT))
    assert m1_n1["replacements"] == n1_repl, "the manifest carries the preparer's raw replacement, not the applied one"
    first_copy = f.copy_text(m1_n1)
    assert f.LOG_OLD in first_copy and "if refresh_due:" in first_copy, "control: run 1 altered the code as it then stood"
    stored = f.pins(sb, f.WK1)
    assert sorted(stored) == sorted(f.key_of(n) for n in BOTH), sorted(stored)
    n1_pin = stored[f.key_of(f.N1)]
    assert list(n1_pin) == f.PIN_KEYS, list(n1_pin)
    assert n1_pin["replacements"] == n1_repl, n1_pin
    assert n1_pin["alteration_id"] == f.alteration_id(n1_repl)
    assert n1_pin["reset"] is False and n1_pin["failed_check"] is None
    raw_pin = f.pin_bytes(sb, f.WK1)
    for leaked in (b"WRONGDIFFMARK", b"caught_by", b"WRONGREPLKEY"):
        assert leaked not in raw_pin, f"a pin was taken from the preparer's raw reply ({leaked!r})"
    return stored, raw_pin


def _run2_applies_pins_to_current_code(sb, stored: dict) -> dict:
    """Run 2, in fresh processes: nothing goes to the preparer, both decisions are "pinned"; returns its manifest."""
    proc2, listed2 = f.run_list(sb, f.WK1)
    assert proc2.returncode == 0 and listed2["to_prepare"] == [] and _names(listed2["owed"]) == BOTH, listed2
    assert _decisions(listed2) == [(f.N1, f.PINNED), (f.ALWAYS, f.PINNED)], listed2["decisions"]
    assert [d["alteration_id"] for d in listed2["decisions"]] == [stored[f.key_of(n)]["alteration_id"] for n in BOTH]
    done2, out2 = f.finish(sb, None, f.WK1)
    assert done2.returncode == 0 and out2["gate_passed"] is True, out2
    m2 = f.manifest(sb, f.WK1)
    for name, now in ((f.N1, "if refresh_due:"), (f.ALWAYS, "if True:")):
        e = ix.entry(m2, name)
        text = f.copy_text(e)
        assert e["status"] == "prepared" and e["source"] == f.PINNED, e
        assert now in text and f.COND not in text, f"{name}: the replacement was not applied: {text!r}"
        assert f.LOG_NEW in text and f.LOG_OLD not in text, f"{name}: the altered copy is not built from the code as it now stands"
        assert e["replacements"] == stored[f.key_of(name)]["replacements"], e
        assert e["alteration_id"] == stored[f.key_of(name)]["alteration_id"], e
    return m2


def test_second_new_run_reapplies_pinned_replacement_to_current_code():
    # covers: TQ-500g-1-xi
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        proc, listed = f.run_list(sb, f.WK1)
        assert proc.returncode == 0 and list(listed) == ix.LIST_KEYS, (proc.returncode, listed)
        assert _names(listed["to_prepare"]) == BOTH and listed["to_prepare"] == listed["owed"], listed
        assert _decisions(listed) == [(f.N1, f.NOT_PINNED), (f.ALWAYS, f.NOT_PINNED)], listed["decisions"]
        stored, raw_pin = _run1_pins_applied_replacements(sb)
        # A coder changes refresh_config.py elsewhere; the gate line is not touched.
        f.edit_source(sb, f.LOG_OLD, f.LOG_NEW)
        m2 = _run2_applies_pins_to_current_code(sb, stored)
        assert f.pin_bytes(sb, f.WK1) == raw_pin, "a pinned name rewrote the pin file"
        # Run 3 applies both pins again in the same way.
        done3, out3 = f.finish(sb, None, f.WK1)
        assert done3.returncode == 0 and out3["gate_passed"] is True, out3
        m3 = f.manifest(sb, f.WK1)
        for name in BOTH:
            e2, e3 = ix.entry(m2, name), ix.entry(m3, name)
            assert e3["source"] == f.PINNED and e3["replacements"] == e2["replacements"] and e3["alteration_id"] == e2["alteration_id"], e3
            assert f.copy_text(e3) == f.copy_text(e2), f"{name}: run 3 built different code than run 2"
        assert f.pin_bytes(sb, f.WK1) == raw_pin


def test_pins_never_cross_work_keys():
    # covers: TQ-500g-1-xi
    # angle: discrimination
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _first_run(sb, f.WK1)
        wk1_pins = f.pin_bytes(sb, f.WK1)
        proc, listed = f.run_list(sb, f.WK2)  # the same requirement, the same names, another piece of work
        assert proc.returncode == 0 and _names(listed["to_prepare"]) == BOTH and listed["to_prepare"] == listed["owed"], listed
        assert _decisions(listed) == [(f.N1, f.NOT_PINNED), (f.ALWAYS, f.NOT_PINNED)], listed["decisions"]
        other = f.first_entries(n1="if refresh_due or retry_due", always="if not False")
        done, out = f.finish(sb, other, f.WK2)
        assert done.returncode == 0 and out["gate_passed"] is True, out
        m = f.manifest(sb, f.WK2)
        for name, now in ((f.N1, "if refresh_due or retry_due:"), (f.ALWAYS, "if not False:")):
            e = ix.entry(m, name)
            assert e["source"] == f.NOT_PINNED and now in f.copy_text(e), f"{name}: {e}"
            assert "if refresh_due:" not in f.copy_text(e) and "if True:" not in f.copy_text(e), f"{name}: another key's pin was applied"
        assert f.pin_bytes(sb, f.WK1) == wk1_pins, "a run for another work key changed the first work's pins"
        assert f.pins(sb, f.WK2)[f.key_of(f.N1)]["replacements"] == f.repl_dicts(f.repl("if refresh_due or retry_due"))
        control_proc, control = f.run_list(sb, f.WK1)  # control: the first work still holds both pins
        assert control_proc.returncode == 0 and _decisions(control) == [(f.N1, f.PINNED), (f.ALWAYS, f.PINNED)], control


def test_fix_undone_is_never_pinned():
    # covers: TQ-500g-1-xi
    # angle: boundary
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp), with_alias=True)
        proc, listed = f.run_list(sb, f.WK1)
        assert proc.returncode == 0 and _names(listed["owed"]) == [f.N1], listed
        assert _names(listed["to_prepare"]) == [f.N1] and [d["name"] for d in listed["decisions"]] == [f.N1], listed
        done, out1 = f.finish(sb, [f.first_entries()[0]], f.WK1)
        assert done.returncode == 0 and out1["gate_passed"] is True, out1
        undone1 = [r for r in out1["verdict"]["results"] if r["wrong_version"] == fx.WV_UNDONE]
        assert undone1 and all(r["result"] == "caught" for r in undone1), out1["verdict"]["results"]
        assert sorted(f.pins(sb, f.WK1)) == [f.key_of(f.N1)], "only the named wrong version is pinned"
        raw = f.pin_bytes(sb, f.WK1).lower()
        assert b"undone" not in raw and ix.ALIAS.encode() not in raw, "the fix undone (or its alias) is in the pin file"
        f.edit_source(sb, f.LOG_OLD, f.LOG_NEW)
        _run2_rebuilds_the_fix_undone_from_base(sb, raw)
        _pin_step_refuses_the_fix_undone(sb)


def _run2_rebuilds_the_fix_undone_from_base(sb, raw: bytes) -> None:
    """Run 2: the fix undone is never listed, planned or decided, is still judged, and nothing new is pinned."""
    _proc2, listed2 = f.run_list(sb, f.WK1)
    assert listed2["to_prepare"] == [] and _decisions(listed2) == [(f.N1, f.PINNED)], listed2
    text = json.dumps(listed2).lower()
    assert "undone" not in text and ix.ALIAS not in text, "the fix undone is listed, planned or decided"
    done2, out2 = f.finish(sb, None, f.WK1)
    assert done2.returncode == 0 and out2["gate_passed"] is True, out2
    undone2 = [r for r in out2["verdict"]["results"] if r["wrong_version"] == fx.WV_UNDONE]
    assert undone2 and all(r["result"] == "caught" for r in undone2), out2["verdict"]["results"]
    assert _names(f.manifest(sb, f.WK1)["entries"]) == [f.N1], "the manifest holds an entry for the fix undone"
    assert f.pin_bytes(sb, f.WK1).lower() == raw, "run 2 pinned something new"


def _pin_step_refuses_the_fix_undone(sb) -> None:
    """Second line of defence: the pin step itself, handed prepared and passing entries for the fix undone
    under both spellings, pins neither; the named wrong version beside them is pinned (control)."""
    undone_repl = f.repl("if False")
    hand = f.hand_manifest(sb, f.WK3, [f.prepared_entry(fx.WV_UNDONE, f.NOT_PINNED, undone_repl),
                                        f.prepared_entry(ix.ALIAS, f.NOT_PINNED, undone_repl),
                                        f.prepared_entry(f.N1, f.NOT_PINNED, f.repl(f.COND_ALT))])
    verdict = f.verdict_of(("t::T1", fx.WV_UNDONE, "caught"), ("t::T1", ix.ALIAS, "caught"), ("t::T1", f.N1, "caught"))
    pin_proc, pinned = f.run_pin(sb, f.WK3, hand, verdict)
    assert pin_proc.returncode == 0 and pinned["error"] is None, (pin_proc.returncode, pinned, pin_proc.stderr[-300:])
    assert _names(pinned["pinned"]) == [f.N1], f"the pin step pinned the fix undone: {pinned['pinned']}"
    assert sorted(f.pins(sb, f.WK3)) == [f.key_of(f.N1)], sorted(f.pins(sb, f.WK3))


def test_list_without_work_key_is_unchanged_and_writes_nothing():
    # covers: TQ-500g-1-xi
    # angle: boundary
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _first_run(sb, f.WK1)  # a pin file is present
        assert f.pin_path(sb, f.WK1).is_file()
        before_status = x.snapshot(sb)
        before_files = f.git_files(sb)
        proc, plain = f.run_list(sb, None)
        assert proc.returncode == 0 and list(plain) == ix.LIST_KEYS, (proc.returncode, plain)
        assert len(plain["owed"]) == 2 and plain["to_prepare"] == plain["owed"] and plain["decisions"] == [], plain
        assert f.git_files(sb) == before_files, f"list without --work-key wrote: {sorted(f.git_files(sb) - before_files)}"
        assert x.snapshot(sb) == before_status, "list without --work-key changed the working tree, index or status"
        proc2, keyed = f.run_list(sb, f.WK3)
        assert proc2.returncode == 0 and list(keyed) == ix.LIST_KEYS and keyed["owed"] == plain["owed"], keyed
        assert f.git_files(sb) - before_files == {f"leafcutter/work/{f.WK3}/plan.json"}, sorted(f.git_files(sb) - before_files)
        assert before_files - f.git_files(sb) == set(), "list removed a file"
        assert x.snapshot(sb) == before_status, "list --work-key changed the working tree, index or status"
        plan = json.loads((sb.git_dir / "leafcutter" / "work" / f.WK3 / "plan.json").read_text(encoding="utf-8"))
        assert list(plan) == ["work_key", "fingerprint", "decisions"] and plan["work_key"] == f.WK3, list(plan)
        assert isinstance(plan["fingerprint"], str) and plan["fingerprint"], plan["fingerprint"]
        assert [d["name"] for d in plan["decisions"]] == BOTH, plan["decisions"]
        assert len(f.pins(sb, f.WK1)) == 2, "control: the other work's pins are still there"


def test_stale_plan_is_recomputed_never_trusted():
    # covers: TQ-500g-1-xi
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _first_run(sb, f.WK1)
        raw_pin = f.pin_bytes(sb, f.WK1)
        proc, listed = f.run_list(sb, f.WK1)
        assert listed["to_prepare"] == [] and _decisions(listed) == [(f.N1, f.PINNED), (f.ALWAYS, f.PINNED)], listed
        f.edit_source(sb, f.COND, "if retry_due and refresh_due")  # the pinned old text is edited away before finish
        done, out = f.finish(sb, None, f.WK1)
        assert out["writer"]["written"] is True, out["writer"]
        full = {e["name"]: (e["status"], e["reason"]) for e in out["writer"]["entries"]}
        # TQ-500g-1-xiii: a stale pin is re-prepared, so its reason names the failed check first.
        assert full == {n: ("could_not_prepare", "re-prepared: target changed; no alteration returned") for n in BOTH}, full
        status = {n: (s, r.removeprefix("re-prepared: target changed; ")) for n, (s, r) in full.items()}
        assert status == {n: ("could_not_prepare", "no alteration returned") for n in BOTH}, status
        m = f.manifest(sb, f.WK1)
        for name in BOTH:
            e = ix.entry(m, name)
            assert e["status"] == "could_not_prepare" and e["reason"] == "re-prepared: target changed; no alteration returned", e
            assert e["files"] == [] and e["diff"] == "" and e["replacements"] == [] and e["alteration_id"] is None, e
        assert done.returncode == 1 and out["gate_passed"] is False, "a stale pin was applied or the gate passed on unprepared names"
        assert f.pin_bytes(sb, f.WK1) == raw_pin, "an unprepared name changed the pins"


def test_pin_step_promotes_only_passing_preparations():
    # covers: TQ-500g-1-xi
    # angle: discrimination
    with tempfile.TemporaryDirectory() as tmp:
        sb = x.build(Path(tmp))
        n_caught, n_survived, n_applied, n_pinned, n_declared, n_unloaded = (
            "drop the retry_due condition", "ignore retry_due", "retry only once", "refresh twice",
            "refresh from the settings file", "retry on a timeout")
        test, test_2 = x.E1, x.E3
        old4, new4 = ("refresh_config.py", "return \"skip\"", "return \"refresh\""), ("refresh_config.py", f.COND, "if True")
        # Step A: n_pinned becomes a pin through the real step (no hand-made store).
        seed = f.hand_manifest(sb, f.WK1, [f.prepared_entry(n_pinned, f.NOT_PINNED, old4)], "seed.json")
        proc_a, out_a = f.run_pin(sb, f.WK1, seed, f.verdict_of((test, n_pinned, "caught")))
        assert proc_a.returncode == 0 and [p["name"] for p in out_a["pinned"]] == [n_pinned], (proc_a.returncode, out_a)
        before = f.pins(sb, f.WK1)[f.key_of(n_pinned)]
        # Step B: caught, survived, not_applied, did_not_load, plus a pinned and a declared entry.
        entries = [
            f.prepared_entry(n_caught, f.NOT_PINNED, f.repl(f.COND_ALT)),
            f.prepared_entry(n_survived, f.NOT_PINNED, f.repl("if refresh_due or True")),
            f.prepared_entry(n_applied, f.NOT_PINNED, f.repl(f.COND, f.COND)),
            f.prepared_entry(n_unloaded, f.NOT_PINNED, f.repl("if not retry_due")),
            f.prepared_entry(n_pinned, f.PINNED, new4),  # a different replacement than the stored pin
            f.prepared_entry(n_declared, "declared", f.repl("if False")),
        ]
        verdict = f.verdict_of((test, n_caught, "caught"), (test, n_survived, "survived"), (test, n_applied, "not_applied"),
                               (test, n_unloaded, "caught"), (test_2, n_unloaded, "did_not_load"),
                               (test, n_pinned, "caught"), (test, n_declared, "caught"))
        proc, out = f.run_pin(sb, f.WK1, f.hand_manifest(sb, f.WK1, entries), verdict)
        assert proc.returncode == 0 and list(out) == ["pinned", "kept", "error"] and out["error"] is None, (proc.returncode, out)
        want = {n_caught: f.repl_dicts(f.repl(f.COND_ALT)), n_survived: f.repl_dicts(f.repl("if refresh_due or True"))}
        assert {p["name"]: p["alteration_id"] for p in out["pinned"]} == {n: f.alteration_id(r) for n, r in want.items()}, out["pinned"]
        stored = f.pins(sb, f.WK1)
        assert sorted(stored) == sorted(f.key_of(n) for n in (n_caught, n_survived, n_pinned)), sorted(stored)
        assert stored[f.key_of(n_survived)]["replacements"] == want[n_survived], "a survivor must be pinned: survival judges the test"
        assert f.key_of(n_applied) not in stored, "a not_applied (no-op) preparation was pinned"
        assert f.key_of(n_unloaded) not in stored, "a name with a did_not_load row was pinned"
        assert f.key_of(n_declared) not in stored, "a declared replacement was written into the pin store"
        assert stored[f.key_of(n_pinned)] == before, "a pinned entry rewrote its pin"
        assert list(stored[f.key_of(n_caught)]) == f.PIN_KEYS and stored[f.key_of(n_caught)]["reset"] is False


def test_pin_write_failure_fails_the_gate():
    # covers: TQ-500g-1-xi
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        blocker = f.pin_path(sb, f.WK1).parent  # a file where the pins folder must be: no pin can be written, even by root
        blocker.parent.mkdir(parents=True, exist_ok=True)
        blocker.write_bytes(b"not a folder")
        proc, listed = f.run_list(sb, f.WK1)
        assert proc.returncode == 0 and _names(listed["to_prepare"]) == BOTH, (proc.returncode, listed)
        done, out = f.finish(sb, f.first_entries(), f.WK1)
        assert done.returncode == 1 and out["gate_passed"] is False and out["stopped_at"] == "pin", (done.returncode, out)
        assert isinstance(out["verdict"], dict) and out["verdict"]["gate_passed"] is True, "the runner ran before the pin step"
        assert isinstance(out["pins"], dict) and isinstance(out["pins"]["error"], str) and out["pins"]["error"].strip(), out["pins"]
        blocker.unlink()  # control: with the folder writable the same run passes and pins
        _, ok = f.finish(sb, f.first_entries(), f.WK1)
        assert ok["gate_passed"] is True and ok["stopped_at"] is None and ok["pins"]["error"] is None, ok


def test_tq_500g_1_xi_reachable_from_entry_point():
    # covers: TQ-500g-1-xi
    # angle: reachability
    # surface_invoked: python scripts/build_orchestration/wrong_version_gate.py finish / wrong_version_writer.py list --work-key (CLI via subprocess)
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        cmd = [sys.executable, str(g.GATE), "finish", "--work-key", f.WK1, "--reply", "-", "--ac-ids", ix.AC_ID,
               "--ac-root", str(sb.ac_root), "--test-root", str(sb.work), "--base-ref", sb.base_sha]
        raw = subprocess.run(cmd, cwd=sb.work, input=f.reply_text(f.first_entries(), f.WK1).encode("utf-8"),
                             capture_output=True, timeout=600, env=x.env())
        out = json.loads(raw.stdout.decode("utf-8").strip())
        assert raw.returncode == 0 and out["gate_passed"] is True and out["pins"]["error"] is None, (raw.returncode, out)
        assert f.pin_path(sb, f.WK1).is_file(), "the real gate CLI left no pin file for the work"
        proc, listed = f.run_list(sb, f.WK1)  # a fresh process reads it
        assert proc.returncode == 0 and listed["to_prepare"] == [] and _decisions(listed) == [(f.N1, f.PINNED), (f.ALWAYS, f.PINNED)], listed
        again, out2 = f.finish(sb, None, f.WK1)  # and the next run needs no preparer at all
        assert again.returncode == 0 and out2["gate_passed"] is True, out2
        assert {e["source"] for e in f.manifest(sb, f.WK1)["entries"]} == {f.PINNED}
