"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_xiii.py
GOAL: RED tests for TQ-500g-1-xiii: every run re-checks each pinned replacement against the current code
    before any wrong version is run, and a pin that fails a check is neither used nor dropped but prepared
    again (checks e, a, c, b, d in ``_wvp_checks``, called from ``_wvp_plan``; failed_check in ``_wvp_store``).
BUSINESS CONTEXT: Every test drives the real writer and gate CLIs (subprocess, fresh processes) on a real git
    sandbox with real pytest tests, a real AC store and a pin file written in the pin store's own shape (see
    _tq500g1xiii_fixtures.py). Today a failing pin reads "prepared: not pinned", the load and effect checks do
    not exist and a pin is never replaced, so each test fails on an assertion about the JSON the CLIs print or
    the files they leave, never on an import.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1xi_fixtures as f
import unit_tests.build_orchestration._tq500g1xiii_fixtures as w

OTHERS = [w.P2, w.P3, w.P4, w.P5, w.P6]


def _sandbox_with_six_pins(tmp: str):
    sb = w.build(Path(tmp))
    w.write_pins(sb, w.six_pins())
    return sb


def test_six_pins_checked_before_any_run_and_failures_re_prepared():
    # covers: TQ-500g-1-xiii
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = _sandbox_with_six_pins(tmp)
        before_pins = f.pin_bytes(sb, w.WK)
        assert w.log_lines(sb) == 0, "control: no test has run before the list step"
        proc, listed = f.run_list(sb, w.WK)
        assert proc.returncode == 0 and list(listed) == ix.LIST_KEYS, (proc.returncode, listed, proc.stderr[-300:])
        assert [o["name"] for o in listed["owed"]] == w.SIX, listed["owed"]
        assert [i["name"] for i in listed["to_prepare"]] == OTHERS, f"to_prepare must be exactly P2 to P6: {listed['to_prepare']}"
        got = dict(w.decisions(listed))
        assert got[w.P1] == f.PINNED, f"P1 passes every check and stays pinned: {got}"
        for name in OTHERS:
            assert got[name] == w.REASONS[name], f"{name}: {got[name]!r} != {w.REASONS[name]!r}"
        pinned = [d for d in listed["decisions"] if d["name"] == w.P1][0]
        assert pinned["alteration_id"] == f.alteration_id(f.repl_dicts(*w.six_pins()[w.P1])), pinned
        assert all(d["alteration_id"] is None for d in listed["decisions"] if d["name"] != w.P1), listed["decisions"]
        # The effect check (d) is made by one traced run of T1 in the list step: before any finish call.
        assert w.log_lines(sb) == 1, "the pre-run (one traced run of the tests naming a candidate) did not happen in the list step"
        assert f.pin_bytes(sb, w.WK) == before_pins, "the list step rewrote the pin file"


def test_load_check_puts_the_file_back_and_leaves_git_status_unchanged():
    # covers: TQ-500g-1-xiii
    # angle: real_artifact
    with tempfile.TemporaryDirectory() as tmp:
        sb = _sandbox_with_six_pins(tmp)
        refresh_before = (sb.work / w.REFRESH).read_bytes()
        status_before = gitfx.run_git(["status", "--porcelain"], cwd=sb.work)
        stash_before = gitfx.run_git(["stash", "list"], cwd=sb.work)
        assert status_before.strip(), "control: the sandbox has an uncommitted change, so a status comparison can differ"
        proc, listed = f.run_list(sb, w.WK)
        assert proc.returncode == 0 and dict(w.decisions(listed))[w.P3] == w.DID_NOT_LOAD, listed["decisions"]
        assert (sb.work / w.REFRESH).read_bytes() == refresh_before, "the load check left the altered file in the working tree"
        assert gitfx.run_git(["status", "--porcelain"], cwd=sb.work) == status_before
        assert gitfx.run_git(["stash", "list"], cwd=sb.work) == stash_before, "git stash was used for the load check"
        runs = sb.git_dir / "leafcutter" / "wrong-version-runs"
        assert runs.is_dir(), "the load check did not go through the journalled run gate (no wrong-version-runs folder)"
        open_journals = sorted(p.as_posix() for p in runs.rglob("journal.json"))
        assert open_journals == [], f"a load check's journal is still open: {open_journals}"


def test_passing_re_preparation_replaces_the_pin():
    # covers: TQ-500g-1-xiii
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = _sandbox_with_six_pins(tmp)
        old_pins = f.pins(sb, w.WK)
        proc, listed = f.run_list(sb, w.WK)
        assert proc.returncode == 0 and dict(w.decisions(listed))[w.P2] == w.TWICE, listed["decisions"]
        done, out = f.finish(sb, [w.fresh_p2()], w.WK)
        assert out["stopped_at"] is None, out
        entry = ix.entry(f.manifest(sb, w.WK), w.P2)
        assert entry["status"] == "prepared" and entry["source"] == w.TWICE, entry
        assert w.result_words(out, w.P2) == {"caught"}, out["verdict"]["results"]
        new_repl = f.repl_dicts(*[(w.REFRESH, p["old"], p["new"]) for p in w.fresh_p2()["replacements"]])
        stored = f.pins(sb, w.WK)
        p2 = stored[f.key_of(w.P2)]
        assert list(p2) == f.PIN_KEYS, list(p2)
        assert p2["replacements"] == new_repl and p2["replacements"] != old_pins[f.key_of(w.P2)]["replacements"], p2
        assert p2["alteration_id"] == f.alteration_id(new_repl), p2
        assert p2["failed_check"] is None and p2["reset"] is False, p2
        assert stored[f.key_of(w.P1)] == old_pins[f.key_of(w.P1)], "control: the passing pin P1 was rewritten"
        for name in (w.P3, w.P4, w.P5, w.P6):
            assert stored[f.key_of(name)] == old_pins[f.key_of(name)], f"{name}: an unanswered pin was changed"


def test_failed_re_preparation_is_unfinished_and_keeps_the_earlier_pin():
    # covers: TQ-500g-1-xiii
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        sb = _sandbox_with_six_pins(tmp)
        before = f.pins(sb, w.WK)
        no_op = ix.prep(w.P4, (w.REFRESH, w.FLAG, w.FLAG))  # the fresh replacement again changes nothing
        f.run_list(sb, w.WK)
        done, out = f.finish(sb, [ix.cnp(w.P3, "no way to call the renamed function"), no_op], w.WK)
        assert out["stopped_at"] is None and out["gate_passed"] is False, out
        assert out["verdict"]["reason"] == "unfinished", out["verdict"]["reason"]
        manifest = f.manifest(sb, w.WK)
        for name, check in ((w.P3, w.DID_NOT_LOAD), (w.P4, w.NOTHING)):
            entry = ix.entry(manifest, name)
            assert entry["status"] == "could_not_prepare" and entry["reason"].startswith(check), f"{name}: {entry}"
            assert entry["files"] == [], f"{name}: the earlier pin was applied as a fallback: {entry}"
            rows = w.unfinished(out, name)
            assert len(rows) == 1 and check in rows[0]["detail"], f"{name}: {out['verdict']['unfinished']}"
            assert w.result_words(out, name) <= {"invalid", "not_applied", "not_run"}, w.result_words(out, name)
            assert name not in w.survivor_names(out), f"{name} is reported as survived"
        assert not {w.P3, w.P4} & w.survivor_names(out)
        stored = f.pins(sb, w.WK)
        for name in (w.P3, w.P4):
            assert stored[f.key_of(name)] == before[f.key_of(name)], f"{name}: the earlier pin changed or was dropped"


def test_fresh_preparation_pinned_only_after_every_check():
    # covers: TQ-500g-1-xiii
    # angle: discrimination
    with tempfile.TemporaryDirectory() as tmp:
        sb = w.build(Path(tmp), names=[w.FRESH])
        # Work 1: a first guess whose new text equals its old is held to the checks before it is run.
        f.run_list(sb, "wk-no-op")
        _, out1 = f.finish(sb, [ix.prep(w.FRESH, (w.REFRESH, w.FLAG, w.FLAG))], "wk-no-op")
        entry = ix.entry(f.manifest(sb, "wk-no-op"), w.FRESH)
        assert entry["status"] == "could_not_prepare" and "changes nothing" in entry["reason"], entry
        assert w.unfinished(out1, w.FRESH) and w.FRESH not in w.survivor_names(out1), out1["verdict"]["unfinished"]
        assert w.pins_or_empty(sb, "wk-no-op") == {}, "a first-guess no-op was locked in as the pin"
        # Second line: the pin step itself, handed a prepared entry whose run read not_applied (a no-op the
        # write step's check missed), pins nothing; the caught entry beside it is pinned (control).
        noop, good = (w.REFRESH, w.FLAG, w.FLAG), (w.REFRESH, w.RETURN_REFRESH, 'return "skip"')
        hand = f.hand_manifest(sb, "wk-pin-step", [f.prepared_entry(w.FRESH, f.NOT_PINNED, noop),
                                                   f.prepared_entry("control name", f.NOT_PINNED, good)])
        verdict = f.verdict_of(("t::T1", w.FRESH, "not_applied"), ("t::T1", "control name", "caught"))
        pin_proc, pinned = f.run_pin(sb, "wk-pin-step", hand, verdict)
        assert pin_proc.returncode == 0 and pinned["error"] is None, (pin_proc.returncode, pinned)
        assert [p["name"] for p in pinned["pinned"]] == ["control name"], f"a not_applied preparation was pinned: {pinned}"
        # Work 2: a replacement on a line no test naming the name runs reads not executed; never a pin.
        f.run_list(sb, "wk-idle")
        _, out2 = f.finish(sb, [ix.prep(w.FRESH, (w.REFRESH, w.IDLE, 'return "busy"'))], "wk-idle")
        assert "not_executed" in {u["result"] for u in w.unfinished(out2, w.FRESH)}, out2["verdict"]["unfinished"]
        assert w.FRESH not in w.survivor_names(out2)
        assert w.pins_or_empty(sb, "wk-idle") == {}, "a replacement on a line no holder runs was pinned"
        # Work 3 (control): a faithful preparation T1 catches becomes the pin.
        faithful = (w.REFRESH, w.RETURN_REFRESH, 'return "skip"')
        f.run_list(sb, "wk-faithful")
        _, out3 = f.finish(sb, [ix.prep(w.FRESH, faithful)], "wk-faithful")
        assert out3["gate_passed"] is True and [p["name"] for p in out3["pins"]["pinned"]] == [w.FRESH], out3
        assert f.pins(sb, "wk-faithful")[f.key_of(w.FRESH)]["replacements"] == f.repl_dicts(faithful)


def test_run_time_load_failure_marks_the_pin_for_re_preparation():
    # covers: TQ-500g-1-xiii
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        sb = w.build(Path(tmp), names=[w.RT])
        calls_renamed = [(w.REFRESH, w.RETURN_REFRESH, "return old_helper()")]  # the name is looked up inside a function body
        w.write_pins(sb, {w.RT: calls_renamed})
        before = f.pins(sb, w.WK)[f.key_of(w.RT)]
        _, listed1 = f.run_list(sb, w.WK)
        assert listed1["to_prepare"] == [] and w.decisions(listed1) == [(w.RT, f.PINNED)], "control: check (b) passes this pin"
        done, out = f.finish(sb, None, w.WK)
        assert out["gate_passed"] is False and w.result_words(out, w.RT) == {"did_not_load"}, out["verdict"]["results"]
        assert w.RT not in w.survivor_names(out)
        after = f.pins(sb, w.WK)[f.key_of(w.RT)]
        assert after["replacements"] == before["replacements"] and after["alteration_id"] == before["alteration_id"], after
        assert after["reset"] is False, "the pin was reset"
        assert isinstance(after["failed_check"], dict) and set(after["failed_check"]) == {"check", "files_sha256"}, after
        assert after["failed_check"]["check"] == "did not load" and after["failed_check"]["files_sha256"], after
        _, listed2 = f.run_list(sb, w.WK)  # the same code: the pin is not used again unchanged
        assert [i["name"] for i in listed2["to_prepare"]] == [w.RT], listed2
        assert w.decisions(listed2) == [(w.RT, w.DID_NOT_LOAD)], listed2["decisions"]
        f.edit_source(sb, w.FLAG, 'FLAG = "yes"')  # the file changes: the pin is checked afresh
        _, listed3 = f.run_list(sb, w.WK)
        assert listed3["to_prepare"] == [] and w.decisions(listed3) == [(w.RT, f.PINNED)], listed3["decisions"]


def test_every_owed_name_appears_in_the_report():
    # covers: TQ-500g-1-xiii
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = _sandbox_with_six_pins(tmp)
        f.run_list(sb, w.WK)
        done, out = f.finish(sb, [w.fresh_p2()], w.WK)  # the reply answers only P2
        assert out["stopped_at"] is None and out["gate_passed"] is False, out
        manifest = f.manifest(sb, w.WK)
        assert [e["name"] for e in manifest["entries"]] == w.SIX, "each owed name is in the manifest exactly once"
        rowed = {r["wrong_version"] for r in out["verdict"]["results"]} - {"the fix undone", ""}  # "": the baseline row
        assert rowed == set(w.SIX), f"names with no row: {sorted(set(w.SIX) - rowed)}; extra: {sorted(rowed - set(w.SIX))}"
        assert w.result_words(out, w.P1) == {"caught"} and w.result_words(out, w.P2) == {"caught"}, out["verdict"]["results"]
        for name in OTHERS[1:]:
            rows = w.unfinished(out, name)
            assert len(rows) == 1 and w.REASONS[name] in rows[0]["detail"], f"{name}: {out['verdict']['unfinished']}"
            assert w.result_words(out, name) <= {"invalid", "not_applied", "not_run"}, w.result_words(out, name)


def test_tq_500g_1_xiii_reachable_from_entry_point():
    # covers: TQ-500g-1-xiii
    # angle: reachability
    # Entry point (CLI via subprocess): python scripts/build_orchestration/wrong_version_gate.py finish, with
    # wrong_version_writer.py list before it. A pin that fails a check (P6: settings.py left the scope) must not
    # reach the runner as an alteration; the check's result is consumed by the gate's control flow.
    with tempfile.TemporaryDirectory() as tmp:
        sb = w.build(Path(tmp), names=[w.P1, w.P6])
        w.write_pins(sb, {n: r for n, r in w.six_pins().items() if n in (w.P1, w.P6)})
        _, listed = f.run_list(sb, w.WK)
        assert dict(w.decisions(listed)) == {w.P1: f.PINNED, w.P6: w.NOT_IN_SCOPE}, listed["decisions"]
        proc, out = f.finish(sb, [], w.WK)
        assert proc.returncode != 0 and out["gate_passed"] is False and out["stopped_at"] is None, (proc.returncode, out)
        entries = {e["name"]: e for e in f.manifest(sb, w.WK)["entries"]}
        assert entries[w.P1]["status"] == "prepared" and entries[w.P1]["source"] == f.PINNED, entries[w.P1]
        assert entries[w.P6]["status"] == "could_not_prepare" and entries[w.P6]["files"] == [], entries[w.P6]
        assert entries[w.P6]["reason"].startswith(w.NOT_IN_SCOPE), entries[w.P6]
        assert w.result_words(out, w.P1) == {"caught"} and w.FRESH not in w.survivor_names(out)
        assert w.result_words(out, w.P6) <= {"invalid", "not_run"} and w.P6 not in w.survivor_names(out), out["verdict"]["results"]
        assert out["verdict"]["reason"] == "unfinished", out["verdict"]["reason"]
