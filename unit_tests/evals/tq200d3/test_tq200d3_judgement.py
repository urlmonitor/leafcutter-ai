"""
MODULE: unit_tests/evals/tq200d3/test_tq200d3_judgement
GOAL: RED tests for TQ-200d-3 on how the designer's bug fix / gate / neither judgement is read: from
    the fields of the test entries it wrote onto the record (must_catch, angle discrimination), never
    from the reply text, and on the schema check every produced record must pass.
Target: scripts/evals/produced_tests_scoring.py (the designer kinds it registers),
    scripts/evals/designer_eval/, scripts/ac_store/validate_ac_schema.py
"""

from __future__ import annotations

import json

import unit_tests.evals.tq200d3._helpers as h

NEITHER_WORDS = ("neither", "must_catch", "discrimination")
GATE_CLAIM = json.dumps({
    "status": "ok",
    "records": [{"id": h.AC_IDS["gate"], "test_design": "written", "file_findings": "none",
                 "reason": "This is a gate: the guarding test names the wrong versions drop the window-open condition, "
                           "drop the position-limit condition and the gate always allows."}],
    "anomalies": [],
})
NEITHER_CLAIM = json.dumps({
    "status": "ok",
    "records": [{"id": h.AC_IDS["bug"], "test_design": "written", "file_findings": "none",
                 "reason": "Neither a bug fix nor a gate: no wrong version is needed and none is named."}],
    "anomalies": [],
})


def _angle_only(data: dict) -> None:
    guard = h.guard_of(data)
    guard.pop("must_catch")
    guard["angle"] = "discrimination"


def _drop_target_dir(data: dict) -> None:
    del h.guard_of(data)["target_dir"]


def _classification(data: dict) -> None:
    h.guard_of(data)["classification"] = "bug fix"


def _top_level_judgement(data: dict) -> None:
    data["judgement"] = "bug fix"


def _must_catch_with_a_number(data: dict) -> None:
    h.guard_of(data)["must_catch"].append(7)


SCHEMA_BAD = {
    "free_text_classification_key_on_an_entry": _classification,
    "required_target_dir_missing": _drop_target_dir,
    "judgement_key_on_the_record": _top_level_judgement,
    "must_catch_holds_a_number": _must_catch_with_a_number,
}


def test_stated_judgement_read_from_record_fields(tmp_path):
    # covers: TQ-200d-3
    # angle: boundary
    # must_catch: judgement read from the reply text instead of the record
    # must_catch: schema-invalid record accepted
    bug, gate = h.real_row("bug"), h.real_row("gate")
    h.expect_passes(bug, tmp_path / "bug", h.gold_dir(bug))
    h.expect_passes(gate, tmp_path / "gate", h.gold_dir(gate))

    # (a) must_catch alone states the judgement: neither the discrimination angle nor any other declaration is needed.
    out = h.with_record("bug", tmp_path, h.set_names([h.REVERT, h.DROP_RETRY], angle="criterion"), name="a")
    record = h.expect_passes(bug, tmp_path, out, "a_score")
    assert h.K_JUDGEMENT in [x["kind"] for x in h.passed(record)]

    # (b) the discrimination angle alone states it too; with no wrong version named only the wrong-version rule fails.
    out = h.with_record("gate", tmp_path, _angle_only, name="b")
    record = h.expect_fails(gate, tmp_path, out, h.only(h.K_WRONG, "wrong version"), "b_score")
    assert h.K_JUDGEMENT in [x["kind"] for x in h.passed(record)]

    # (c) a gate record with no must_catch and no discrimination angle states neither: the judgement rule fails, in its own words.
    out = h.with_record("gate", tmp_path, h.strip_wrong_versions, name="c")
    h.expect_fails(gate, tmp_path, out, {h.K_JUDGEMENT: (NEITHER_WORDS, ()), h.K_WRONG: (("wrong version",), ("neither",))}, "c_score")

    # (d) the reply's text never decides it: a reply that says "this is a gate" and lists every wrong version does not
    # rescue a record that carries none of them ...
    out = h.with_record("gate", tmp_path, h.strip_wrong_versions, reply=GATE_CLAIM, name="d")
    h.expect_fails(gate, tmp_path, out, {h.K_JUDGEMENT: (NEITHER_WORDS, ()), h.K_WRONG: (("wrong version",), ())}, "d_score")
    # ... and a reply that says "neither" does not sink a record that carries them.
    out = h.with_record("bug", tmp_path, None, reply=NEITHER_CLAIM, name="e")
    h.expect_passes(bug, tmp_path, out, "e_score")

    # (e) blank wrong-version names do not state a judgement (the template: non-blank strings).
    out = h.with_record("gate", tmp_path, h.set_names(["  ", ""], angle="criterion"), name="f")
    assert h.K_JUDGEMENT in failed_kinds(gate, tmp_path, out)

    # (f) a produced record that fails validate_ac_schema.py fails its row, and only on the schema rule: the change
    # breaks the record's shape, not what it says about wrong versions.
    for how, mutate in sorted(SCHEMA_BAD.items()):
        out = h.with_record("bug", tmp_path, mutate, name=f"schema_{how}")
        h.expect_fails(bug, tmp_path, out, h.only(h.K_SCHEMA, "validate_ac_schema.py", h.AC_IDS["bug"]), f"schema_{how}_score")


def failed_kinds(row: dict, tmp_path, out) -> list[str]:
    """The kinds that fail for *out* (the row fails)."""
    record = h.score(row, out, tmp_path / "blank_score")
    assert record["score"]["passed"] is False, record["score"]
    return [a["kind"] for a in h.failed(record)]


def test_stated_judgement_a_record_that_fails_validate_ac_schema_fails_its_row(tmp_path):
    # covers: TQ-200d-3
    # angle: failure
    # Every row, not only the bug-fix row, runs the check; the new-behaviour row too.
    for key in ("gate", "new"):
        row = h.real_row(key)

        def break_shape(data: dict) -> None:
            h.spec_of(data)[0]["classification"] = "neither"

        out = h.with_record(key, tmp_path, break_shape, name=f"bad_{key}")
        h.expect_fails(row, tmp_path, out, h.only(h.K_SCHEMA, "validate_ac_schema.py", h.AC_IDS[key]), f"{key}_score")


def test_stated_judgement_missing_or_unreadable_record_fails_every_rule_without_crashing(tmp_path):
    # covers: TQ-200d-3
    # angle: failure
    row = h.real_row("bug")
    for label, raw in (("absent", None), ("unparseable", b"test_spec: [unclosed\n  - name: x\n"), ("empty", b""), ("not_a_mapping", b"- just\n- a list\n")):
        out = h.with_record_bytes("bug", tmp_path / label, raw)
        # A reply that claims everything is fine changes nothing: the record is the evidence.
        (out / "report.md").write_text(GATE_CLAIM, encoding="utf-8")
        record = h.score(row, out, tmp_path / f"{label}_score")
        assert record["score"]["passed"] is False, label
        assert not record.get("error"), f"{label}: a bad record is a failed row, not a harness error: {record.get('error')}"
        bad = {a["kind"] for a in h.failed(record)}
        # An absent record file leaves the pending fixture record in the sandbox: valid, but it states and names nothing.
        want = {h.K_JUDGEMENT, h.K_WRONG, h.K_WRITTEN} if label == "absent" else {h.K_SCHEMA, h.K_JUDGEMENT, h.K_WRONG, h.K_WRITTEN}
        assert bad == want, (label, h.failed(record))
        for item in h.failed(record):
            assert h.AC_IDS["bug"] in item["detail"], (label, item)


def test_stated_judgement_a_record_written_to_the_wrong_place_is_not_found(tmp_path):
    # covers: TQ-200d-3
    # angle: failure
    row = h.real_row("gate")
    out = h.with_record("gate", tmp_path, None, reply=GATE_CLAIM)
    target = h.record_file(out, h.AC_IDS["gate"])
    moved = out / "files" / "elsewhere" / f"{h.AC_IDS['gate']}.yaml"
    moved.parent.mkdir(parents=True)
    moved.write_bytes(target.read_bytes())
    target.unlink()
    record = h.score(row, out, tmp_path / "moved_score")
    assert record["score"]["passed"] is False, "an edited copy outside the row's store is not the requirement record"
