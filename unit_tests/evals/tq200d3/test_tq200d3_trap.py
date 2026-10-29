"""
MODULE: unit_tests/evals/tq200d3/test_tq200d3_trap
GOAL: RED tests for TQ-200d-3 on the "new behaviour" trap row ("export the report as CSV"). For
    neither a bug fix nor a gate, no entry carries must_catch or angle: discrimination (user decision
    2026-10-25, superseding OQ-14): any non-blank must_catch (a revert alias or any other name) or a
    discrimination angle fails the row, a design that names none passes it. The row also needs a
    WRITTEN design, so an agent that leaves the record untouched fails it (reviewer H-1).
Target: scripts/evals/designer_eval/ (the designer kinds), scripts/evals/sets/test-designer.jsonl
"""

from __future__ import annotations

import pytest
import yaml

import unit_tests.evals.tq200d3._helpers as h

WRITTEN_FIELDS = ("test_spec", "test_design_authorship", "test_design_opened_files")


def _first_entry(names: list[str] | None, angle: str | None = "discrimination"):
    """A mutation: the FIRST test_spec entry names *names* (none when None) and has *angle* (removed when None)."""
    def mutate(data: dict) -> None:
        entry = h.spec_of(data)[0]
        if names is not None:
            entry["must_catch"] = list(names)
        if angle is None:
            entry.pop("angle", None)
        else:
            entry["angle"] = angle
    return mutate


def _last_entry(names: list[str]):
    """A mutation: a NEW last entry names *names* (the other entries stay as recorded)."""
    def mutate(data: dict) -> None:
        h.extra_entry(data, angle="discrimination", must_catch=list(names))
    return mutate


def _later_discrimination(data: dict) -> None:
    """A mutation: a NEW last entry is a discrimination test with no must_catch."""
    h.extra_entry(data, angle="discrimination")


def _set(key: str, value):
    """A mutation: top-level *key* of the record becomes *value*."""
    def mutate(data: dict) -> None:
        data[key] = value
    return mutate


def _authorship(step: str):
    """A mutation: test_design_authorship.step becomes *step*."""
    def mutate(data: dict) -> None:
        data["test_design_authorship"]["step"] = step
    return mutate


TRAP_BAD = {
    "revert_the_fix": (_first_entry([h.REVERT]), h.only(h.K_NEITHER, "revert the fix", "must_catch")),
    "the_fix_undone": (_first_entry([h.ALIAS]), h.only(h.K_NEITHER, "the fix undone", "must_catch")),
    "revert_padded_and_upper_case": (_first_entry(["  Revert The Fix  "]), h.only(h.K_NEITHER, "Revert The Fix", "must_catch")),
    "fix_undone_upper_case": (_first_entry(["THE FIX UNDONE"]), h.only(h.K_NEITHER, "THE FIX UNDONE", "must_catch")),
    "restore_the_old_behaviour": (_first_entry(["restore the old behaviour"]), h.only(h.K_NEITHER, "restore the old behaviour", "must_catch")),
    "undo_the_change": (_first_entry(["undo the change"]), h.only(h.K_NEITHER, "undo the change", "must_catch")),
    "other_name_the_export_drops_a_column": (_first_entry(["the export drops a column"]), h.only(h.K_NEITHER, "the export drops a column", "must_catch")),
    "other_names_without_discrimination_angle": (_first_entry(["the CSV is not quoted", "the header row is missing"], angle="criterion"),
                                                 h.only(h.K_NEITHER, "the CSV is not quoted", "must_catch")),
    "alias_among_other_names": (_first_entry(["the export drops a column", h.ALIAS, "the header row is missing"]), h.only(h.K_NEITHER, "the fix undone", "must_catch")),
    "name_on_a_later_entry": (_last_entry([h.REVERT]), h.only(h.K_NEITHER, "revert the fix", "must_catch")),
    "other_name_on_a_later_entry": (_last_entry(["undo the change"]), h.only(h.K_NEITHER, "undo the change", "must_catch")),
    "discrimination_angle_and_no_must_catch": (_first_entry(None), h.only(h.K_NEITHER, "angle discrimination")),
    "discrimination_angle_on_a_later_entry": (_later_discrimination, h.only(h.K_NEITHER, "angle discrimination")),
}

# The trap row also needs a WRITTEN design (reviewer H-1). Each case breaks exactly one part of it.
def _not_written(present: str, absent: tuple[str, ...], *, schema: bool = False) -> dict:
    """The expected failures: the written-design rule in its own words (and the schema rule where the shape breaks too)."""
    expected = h.only(h.K_WRITTEN, "no design was written", present, h.AC_IDS["new"], absent=absent)
    if schema:
        expected.update(h.only(h.K_SCHEMA, "validate_ac_schema.py"))
    return expected


def _fixture_content(data: dict) -> None:
    """A mutation: the record becomes the row's pending fixture record (what an agent that did nothing leaves)."""
    data.clear()
    data.update(yaml.safe_load(h.fixture_record_bytes("new")))


_OTHER = {"test_spec": ("test_design_authorship", "test_design_opened_files"),
          "test_design_authorship": ("test_spec", "test_design_opened_files"),
          "test_design_opened_files": ("test_spec", "test_design_authorship")}
TRAP_BAD.update({
    "design_untouched_fixture_record": (_fixture_content, h.only(h.K_WRITTEN, "no design was written", *WRITTEN_FIELDS, h.AC_IDS["new"])),
    "design_empty_test_spec": (_set("test_spec", []), _not_written("test_spec", _OTHER["test_spec"], schema=True)),
    "design_no_test_spec_key": (lambda d: d.pop("test_spec"), _not_written("test_spec", _OTHER["test_spec"])),
    "design_authorship_step_is_another_agent": (_authorship("test-writer"), _not_written("test_design_authorship", _OTHER["test_design_authorship"])),
    "design_no_authorship_mark": (lambda d: d.pop("test_design_authorship"), _not_written("test_design_authorship", _OTHER["test_design_authorship"])),
    "design_no_opened_files": (_set("test_design_opened_files", []), _not_written("test_design_opened_files", _OTHER["test_design_opened_files"])),
})


@pytest.mark.parametrize("how", sorted(TRAP_BAD))
def test_new_behaviour_trap_fails_invented_wrong_versions(tmp_path, how):
    # covers: TQ-200d-3
    # angle: discrimination
    # must_catch: new-behaviour trap passes a design that names 'revert the fix'
    row = h.real_row("new")
    assert row["expected"]["negative"] is True, "the trap row is the negative row"
    assert {a["kind"] for a in row["expected"]["assertions"]} >= h.ROW_KINDS["new"]
    # A design that names no wrong version passes the row (the recorded gold design); so does the row's control run.
    gold = h.gold_record("new")
    assert not [e for e in h.spec_of(gold) if e.get("must_catch") or e.get("angle") == "discrimination"], "the gold trap design names nothing"
    h.expect_passes(row, tmp_path, h.gold_dir(row), "control")
    mutate, expected = TRAP_BAD[how]
    out = h.with_record("new", tmp_path, mutate)
    # Only the rule the change breaks fails (the 'neither' rule, or the written-design rule), nothing else.
    h.expect_fails(row, tmp_path, out, expected)


def test_new_behaviour_trap_fails_the_untouched_fixture_record(tmp_path):
    # covers: TQ-200d-3
    # angle: failure
    row = h.real_row("new")
    out = h.with_record_bytes("new", tmp_path, h.fixture_record_bytes("new"))
    # The agent did nothing: the pending record is valid and names nothing, and that is exactly why it must not pass.
    h.expect_fails(row, tmp_path, out, h.only(h.K_WRITTEN, "no design was written", *WRITTEN_FIELDS, h.AC_IDS["new"]))


@pytest.mark.parametrize("key", ["bug", "gate"])
def test_bug_fix_and_gate_rows_fail_the_untouched_fixture_record(tmp_path, key):
    # covers: TQ-200d-3
    # angle: failure
    row = h.real_row(key)
    out = h.with_record_bytes(key, tmp_path, h.fixture_record_bytes(key))
    record = h.score(row, out, tmp_path / "bad")
    assert record["score"]["passed"] is False
    failed = {a["kind"]: a["detail"] for a in h.failed(record)}
    assert set(failed) == {h.K_WRITTEN, h.K_JUDGEMENT, h.K_WRONG}, failed
    for field in WRITTEN_FIELDS:
        assert field in failed[h.K_WRITTEN]


@pytest.mark.parametrize("style", ["json", "flow", "crlf", "comments"])
def test_new_behaviour_trap_fails_an_alias_in_any_yaml_formatting(tmp_path, style):
    # covers: TQ-200d-3
    # angle: real_artifact
    row = h.real_row("new")
    out = h.with_record("new", tmp_path, _first_entry([h.ALIAS]), style=style)
    h.expect_fails(row, tmp_path, out, h.only(h.K_NEITHER, "the fix undone", "must_catch"))


@pytest.mark.parametrize("style", h.STYLES)
def test_new_behaviour_trap_passes_a_design_naming_none_in_any_yaml_formatting(tmp_path, style):
    # covers: TQ-200d-3
    # angle: boundary
    row = h.real_row("new")
    out = h.with_record("new", tmp_path, None, style=style)
    h.expect_passes(row, tmp_path, out)


@pytest.mark.parametrize("blank", [[], [" "], [""]])
def test_new_behaviour_trap_blank_or_empty_must_catch_is_not_a_name(tmp_path, blank):
    # covers: TQ-200d-3
    # angle: boundary
    # A blank name carries nothing (the template: non-blank strings), so it does not fail the 'neither' rule.
    record = h.score(h.real_row("new"), h.with_record("new", tmp_path, _first_entry(blank, angle="criterion")), tmp_path / "blank")
    assert h.K_NEITHER in [a["kind"] for a in h.passed(record)], h.failed(record)
