"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_xii.py
GOAL: RED tests for TQ-500g-1-xii: only a name that is new to the work, whose pinned old text no longer
    matches, or whose wording changed goes to the preparer; every other name comes from the pin.
BUSINESS CONTEXT: Every test drives the real writer and gate CLIs (subprocess, fresh processes) on a real git
    sandbox, a real AC store and pin files in the pin store's own shape (see _tq500g1xii_fixtures.py). The
    decision lives in ``_wvp_plan`` and is shared by the list and the write step, so the list's
    ``to_prepare``, the manifest's ``source`` values and the verdict rows are all read back and compared.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.build_orchestration._tq500g1xi_fixtures as f
import unit_tests.build_orchestration._tq500g1xii_fixtures as v
import unit_tests.build_orchestration._tq500g1xiii_fixtures as w

TARGET_CHANGED = "re-prepared: target changed"


def _names(items: list[dict]) -> list[str]:
    return [i["name"] for i in items]


def test_only_new_retargeted_or_reworded_names_go_to_the_preparer():
    # covers: TQ-500g-1-xii
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.N1, v.N2, v.N3_NOW, v.COLD, v.N5])
        v.pin(sb, v.N1, v.N2, v.N3_PIN, v.WARM)
        v.rewrite_return_line(sb)  # N2's pinned old text no longer occurs; N1's still occurs exactly once
        raw_pins = f.pin_bytes(sb, v.WK)
        proc, listed = f.run_list(sb, v.WK)
        assert proc.returncode == 0 and list(listed) == ix.LIST_KEYS, (proc.returncode, listed, proc.stderr[-300:])
        assert _names(listed["owed"]) == [v.N1, v.N2, v.N3_NOW, v.COLD, v.N5], listed["owed"]
        assert _names(listed["to_prepare"]) == [v.N2, v.COLD, v.N5], f"exactly N2, cold and N5: {listed['to_prepare']}"
        for item in listed["to_prepare"]:
            assert item == v.by_name(listed["owed"], item["name"]), f"{item['name']}: to_prepare differs from its owed item"
            assert item["files"], f"{item['name']}: no files in scope were sent"
        got = dict(w.decisions(listed))
        assert got == {v.N1: f.PINNED, v.N2: TARGET_CHANGED, v.N3_NOW: f.PINNED, v.COLD: f.NOT_PINNED, v.N5: f.NOT_PINNED}, got
        assert v.WARM not in got, "the warm pin is reported while no entry names it"
        assert f.pin_bytes(sb, v.WK) == raw_pins, "the list step rewrote the pins"


def test_case_and_trailing_space_difference_uses_pin_with_current_spelling():
    # covers: TQ-500g-1-xii
    # angle: boundary
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.N3_NOW])
        v.pin(sb, v.N3_PIN)
        proc, listed = f.run_list(sb, v.WK)
        assert proc.returncode == 0 and listed["to_prepare"] == [], f"a case/space difference re-prepared the name: {listed}"
        assert [(d["name"], d["source"]) for d in listed["decisions"]] == [(v.N3_NOW, f.PINNED)], listed["decisions"]
        done, out = f.finish(sb, None, v.WK)
        assert done.returncode == 0 and out["gate_passed"] is True, out
        m = f.manifest(sb, v.WK)
        assert _names(m["entries"]) == [v.N3_NOW], f"the manifest spells the name as the pin stored it: {_names(m['entries'])}"
        e = m["entries"][0]
        assert e["source"] == f.PINNED and e["replacements"] == f.repl_dicts(v.PIN_REPLS[v.N3_PIN]), e
        rows = v.verdict_names(out)
        assert v.N3_NOW in rows and v.N3_PIN not in rows, f"the verdict spells the name as the entry now spells it: {rows}"
        assert _names(out["writer"]["entries"]) == [v.N3_NOW], _names(out["writer"]["entries"])


def test_retargeted_pin_never_applied_and_row_says_target_changed():
    # covers: TQ-500g-1-xii
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.N2])
        v.pin(sb, v.N2)
        v.rewrite_return_line(sb)
        raw_pins = f.pin_bytes(sb, v.WK)
        proc, listed = f.run_list(sb, v.WK)
        assert _names(listed["to_prepare"]) == [v.N2], listed
        assert [(d["name"], d["source"]) for d in listed["decisions"]] == [(v.N2, TARGET_CHANGED)], listed["decisions"]
        done, out = f.finish(sb, v.fresh_entries(v.N2), v.WK)
        assert out["writer"]["written"] is True and done.returncode == 0 and out["gate_passed"] is True, out
        e = ix.entry(f.manifest(sb, v.WK), v.N2)
        assert e["status"] == "prepared" and e["source"] == TARGET_CHANGED, e
        assert e["replacements"] == f.repl_dicts(v.FRESH_REPLS[v.N2]), "the fresh preparation is not what was applied"
        text = f.copy_text(e)
        assert "STALEPIN" not in text and "return 'refresh'" in text, f"the stale pinned copy was applied: {text!r}"
        assert v.STALE_NEW in json.loads(raw_pins.decode("utf-8"))["pins"][f.key_of(v.N2)]["replacements"][0]["new"], \
            "control: the pin held the stale replacement"


def test_retargeted_pin_with_no_reply_is_could_not_prepare_not_the_pin():
    # covers: TQ-500g-1-xii
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.N1, v.N2])
        v.pin(sb, v.N1, v.N2)
        v.rewrite_return_line(sb)
        raw_pins = f.pin_bytes(sb, v.WK)
        done, out = f.finish(sb, [], v.WK)  # the preparer answers with no entry at all
        assert out["writer"]["written"] is True, out["writer"]
        status = {e["name"]: (e["status"], e["reason"]) for e in out["writer"]["entries"]}
        assert status[v.N2] == ("could_not_prepare", f"{TARGET_CHANGED}; no alteration returned"), status
        assert status[v.N1][0] == "prepared", f"control: the matching pin is still applied: {status}"
        m2 = ix.entry(f.manifest(sb, v.WK), v.N2)
        assert m2["files"] == [] and m2["replacements"] == [] and m2["alteration_id"] is None, m2
        assert done.returncode == 1 and out["gate_passed"] is False, "an unprepared name must not pass the gate"
        assert f.pin_bytes(sb, v.WK) == raw_pins, "the pins changed although no name was re-prepared"


def test_reworded_name_never_takes_the_old_wordings_pin():
    # covers: TQ-500g-1-xii
    # angle: discrimination
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.COLD])
        v.pin(sb, v.WARM)
        raw_pins = f.pin_bytes(sb, v.WK)
        proc, listed = f.run_list(sb, v.WK)
        assert _names(listed["owed"]) == [v.COLD] and _names(listed["to_prepare"]) == [v.COLD], listed
        assert [(d["name"], d["source"]) for d in listed["decisions"]] == [(v.COLD, f.NOT_PINNED)], listed["decisions"]
        assert v.WARM not in json.dumps(listed), "the unowed warm pin is reported by the list"
        plan = json.loads((sb.git_dir / "leafcutter" / "work" / v.WK / "plan.json").read_text(encoding="utf-8"))
        assert [d["name"] for d in plan["decisions"]] == [v.COLD], plan["decisions"]
        assert f.pin_bytes(sb, v.WK) == raw_pins
        done, out = f.finish(sb, v.fresh_entries(v.COLD), v.WK)
        assert done.returncode == 0 and out["gate_passed"] is True, out
        e = ix.entry(f.manifest(sb, v.WK), v.COLD)
        assert e["source"] == f.NOT_PINNED and e["replacements"] == f.repl_dicts(v.FRESH_REPLS[v.COLD]), e
        assert v.WARM_NEW not in f.copy_text(e), "the warm pin was applied to the cold name"
        assert v.WARM not in json.dumps(f.manifest(sb, v.WK)) and v.WARM not in json.dumps(out["verdict"])
        stored = f.pins(sb, v.WK)
        assert f.key_of(v.WARM) in stored and stored[f.key_of(v.WARM)]["replacements"] == f.repl_dicts(v.PIN_REPLS[v.WARM]), \
            "the unowed warm pin was removed or changed"


def test_unowed_pin_used_again_when_the_name_returns():
    # covers: TQ-500g-1-xii
    # angle: boundary
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.N1, v.WARM])
        first = [ix.prep(n, v.PIN_REPLS[n], caught_by=[x.E1], would_catch=True, outcome="caught") for n in (v.N1, v.WARM)]
        done, out = f.finish(sb, first, v.WK)
        assert done.returncode == 0 and out["gate_passed"] is True, out
        # A run that does not owe the warm name, and that pins a new name (so it writes the pin file).
        v.set_owed(sb, [v.N1, v.N5])
        pins_before = f.pins(sb, v.WK)
        f.run_list(sb, v.WK)
        done2, out2 = f.finish(sb, v.fresh_entries(v.N5), v.WK)
        assert done2.returncode == 0 and out2["gate_passed"] is True, out2
        assert [p["name"] for p in out2["pins"]["pinned"]] == [v.N5], "control: this run wrote the pin file"
        assert v.WARM not in json.dumps(f.manifest(sb, v.WK)), "a run that does not owe the name still carries it"
        pins_after = f.pins(sb, v.WK)
        for name in (v.N1, v.WARM):
            assert pins_after.get(f.key_of(name)) == pins_before[f.key_of(name)], f"a run that does not owe it dropped or changed {name}'s pin"
        v.set_owed(sb, [v.N1, v.WARM])  # a later entry names it again
        proc, listed = f.run_list(sb, v.WK)
        assert listed["to_prepare"] == [] and [d["source"] for d in listed["decisions"]] == [f.PINNED, f.PINNED], listed
        done3, out3 = f.finish(sb, None, v.WK)
        assert done3.returncode == 0 and out3["gate_passed"] is True, out3
        e = ix.entry(f.manifest(sb, v.WK), v.WARM)
        assert e["source"] == f.PINNED and e["replacements"] == f.repl_dicts(v.PIN_REPLS[v.WARM]), e
        assert v.WARM_NEW in f.copy_text(e), "the warm pin was not applied to the current file"


def test_any_inner_wording_change_counts_as_a_new_name():
    # covers: TQ-500g-1-xii
    # angle: discrimination
    exact = v.N3_PIN
    for variant in ("retry only  once", "retry only once."):
        with tempfile.TemporaryDirectory() as tmp:
            sb = v.build(Path(tmp), [exact, variant])
            v.pin(sb, v.N3_PIN)
            proc, listed = f.run_list(sb, v.WK)
            assert proc.returncode == 0, proc.stderr[-300:]
            got = [(d["name"], d["source"]) for d in listed["decisions"]]
            assert got == [(exact, f.PINNED), (variant, f.NOT_PINNED)], f"{variant!r}: {got}"
            assert _names(listed["to_prepare"]) == [variant], f"{variant!r}: control name must stay pinned: {listed['to_prepare']}"


def test_multi_replacement_pin_is_judged_in_order_against_the_result_of_the_one_before():
    # covers: TQ-500g-1-xii
    # angle: boundary
    both = "if refresh_due and retry_due or refresh_due and retry_due"
    cases = {
        # (2) matches only once the first replacement has been applied: the pin is still good
        "applies in order": ([(f.REFRESH, f.COND, "if refresh_due or retry_due"), (f.REFRESH, "or retry_due", "or not retry_due")], f.PINNED),
        # (2) occurs once in the file as it now stands but twice in the result of (1): the second names the reason
        "second fails": ([(f.REFRESH, f.COND, both), (f.REFRESH, "and retry_due", "and not retry_due")],
                         "re-prepared: old text found 2 times"),
        # (2) occurs nowhere in the result of (1)
        "second vanishes": ([(f.REFRESH, f.COND, "if refresh_due"), (f.REFRESH, "and retry_due", "and not retry_due")], TARGET_CHANGED),
    }
    for label, (repls, want) in cases.items():
        with tempfile.TemporaryDirectory() as tmp:
            sb = v.build(Path(tmp), [v.N1])
            w.write_pins(sb, {v.N1: repls}, v.WK)
            proc, listed = f.run_list(sb, v.WK)
            assert proc.returncode == 0, (label, proc.stderr[-300:])
            got = [(d["name"], d["source"]) for d in listed["decisions"]]
            assert got == [(v.N1, want)], f"{label}: {got}"
            assert (listed["to_prepare"] == []) == (want == f.PINNED), f"{label}: {listed['to_prepare']}"


def test_list_output_and_plan_are_byte_identical_for_the_same_state():
    # covers: TQ-500g-1-xii
    # angle: boundary
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.N1, v.N2, v.N3_NOW, v.COLD, v.N5])
        v.pin(sb, v.N1, v.N2, v.N3_PIN, v.WARM)
        v.rewrite_return_line(sb)
        plan = sb.git_dir / "leafcutter" / "work" / v.WK / "plan.json"
        first, first_json = f.run_list(sb, v.WK)
        first_plan = plan.read_bytes()
        again, again_json = f.run_list(sb, v.WK)
        assert first.stdout == again.stdout and first_json == again_json, "the list output changed with nothing changed"
        assert plan.read_bytes() == first_plan, "plan.json changed with nothing changed"
        assert len(_names(first_json["to_prepare"])) == 3 and first_json["to_prepare"] == [
            i for i in first_json["owed"] if i["name"] in {v.N2, v.COLD, v.N5}], first_json["to_prepare"]


def test_tq_500g_1_xii_reachable_from_entry_point():
    # covers: TQ-500g-1-xii
    # angle: reachability
    # surface_invoked: python scripts/build_orchestration/wrong_version_gate.py finish (CLI via subprocess)
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [v.N1, v.N3_NOW, v.N5])
        v.pin(sb, v.N1, v.N3_PIN)
        cmd = [sys.executable, str(g.GATE), "finish", "--work-key", v.WK, "--reply", "-", "--ac-ids", ix.AC_ID,
               "--ac-root", str(sb.ac_root), "--test-root", str(sb.work), "--base-ref", sb.base_sha]
        text = f.reply_text(v.fresh_entries(v.N5), v.WK)
        raw = subprocess.run(cmd, cwd=sb.work, input=text.encode("utf-8"), capture_output=True, timeout=600, env=x.env())
        out = json.loads(raw.stdout.decode("utf-8").strip())
        assert raw.returncode == 0 and out["gate_passed"] is True, (raw.returncode, out)
        sources = {e["name"]: e["source"] for e in f.manifest(sb, v.WK)["entries"]}
        assert sources == {v.N1: f.PINNED, v.N3_NOW: f.PINNED, v.N5: f.NOT_PINNED}, sources
        assert set(v.verdict_names(out)) >= {v.N1, v.N3_NOW, v.N5}, v.verdict_names(out)
