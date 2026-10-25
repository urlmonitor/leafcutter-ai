"""
MODULE: unit_tests/evals/tq200d3/test_tq200d3_bug_fix_and_gate
GOAL: RED tests for TQ-200d-3 on the "bug fix" and "gate" rows of the test-designer eval set: the
    guarding test entry must name "revert the fix" plus a wrong version naming the retry_due
    condition (bug fix), or one wrong version per condition plus "the gate always allows" (gate).
Target: scripts/evals/produced_tests_scoring.py (the designer kinds it registers),
    scripts/evals/designer_eval/, scripts/evals/sets/test-designer.jsonl
"""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d3._helpers as h

BUG_BAD = {
    "revert_alone": ([h.REVERT], ("retry_due",), ("revert the fix",)),
    "condition_alone": ([h.DROP_RETRY], ("revert the fix",), ("retry_due",)),
    "the_other_condition_named": ([h.REVERT, "drop the refresh_due condition"], ("retry_due",), ("revert the fix",)),
    "unrelated_names": ([h.REVERT, "return an empty list", "raise on a closed connection"], ("retry_due",), ("revert the fix",)),
    "alias_alone": ([h.ALIAS], ("retry_due",), ("revert the fix",)),
    "retry_later_when_it_is_due_is_no_variant": ([h.REVERT, "retry later when it is due"], ("retry_due",), ("revert the fix",)),
    "decoy_carrying_no_condition": ([h.REVERT, "return a stale refresh", "swallow the database error"], ("retry_due",), ("revert the fix",)),
}


@pytest.mark.parametrize("how", sorted(BUG_BAD))
def test_bug_fix_row_requires_revert_and_a_condition_naming_version(tmp_path, how):
    # covers: TQ-200d-3
    # angle: criterion
    # must_catch: bug-fix row passes with 'revert the fix' alone
    # must_catch: alias spelling 'the fix undone' not matched
    row = h.real_row("bug")
    names, words, absent = BUG_BAD[how]
    spec = {a["kind"]: a for a in row["expected"]["assertions"]}
    assert h.K_WRONG in spec and h.K_JUDGEMENT in spec and h.K_SCHEMA in spec, sorted(spec)
    # Control: the recorded gold design (revert the fix + a retry_due wrong version) passes the whole row.
    h.expect_passes(row, tmp_path, h.gold_dir(row), "control")
    out = h.with_record("bug", tmp_path, h.set_names(names))
    # Exactly the wrong-version rule fails: the design still states its judgement (discrimination angle) and is schema-valid.
    h.expect_fails(row, tmp_path, out, h.only(h.K_WRONG, "wrong version", *words, absent=absent))


def test_bug_fix_row_fails_when_the_two_wrong_versions_sit_in_different_entries(tmp_path):
    # covers: TQ-200d-3
    # angle: discrimination
    # The criterion says the guarding test ENTRY names both, so a union over entries is a wrong version of the scorer.
    row = h.real_row("bug")

    def split(data: dict) -> None:
        h.guard_of(data)["must_catch"] = [h.REVERT]
        h.extra_entry(data, angle="discrimination", must_catch=[h.DROP_RETRY])

    out = h.with_record("bug", tmp_path, split)
    h.expect_fails(row, tmp_path, out, h.only(h.K_WRONG, "wrong version"))


def test_bug_fix_condition_named_only_outside_must_catch_does_not_count(tmp_path):
    # covers: TQ-200d-3
    # angle: discrimination
    row = h.real_row("bug")

    def mention(data: dict) -> None:
        guard = h.guard_of(data)
        guard["must_catch"] = [h.REVERT]
        guard["description"] = "must fail when the retry_due condition is dropped"
        guard["name"] = "test_refresh_runs_only_when_retry_due"

    out = h.with_record("bug", tmp_path, mention)
    h.expect_fails(row, tmp_path, out, h.only(h.K_WRONG, "retry_due"))


BUG_GOOD = {
    "alias_spelling": h.set_names(["The Fix Undone", "drop the retry_due condition"]),
    "padded_upper_case": h.set_names(["  REVERT THE FIX  ", "Drop the RETRY_DUE condition"]),
    "hyphenated_condition": h.set_names([h.REVERT, "remove the retry-due check"]),
    "spaced_condition": h.set_names([h.REVERT, "ignore the retry due condition"]),
    "other_words_for_the_condition": h.set_names([h.REVERT, "refresh without checking retry_due, so a retry storm returns"]),
    "reversed_order": h.set_names(["drop the retry_due condition", h.REVERT]),
    "extra_unrelated_names": h.set_names([h.REVERT, "return a stale refresh", h.DROP_RETRY, "swallow the database error"]),
    "no_discrimination_angle": h.set_names([h.REVERT, h.DROP_RETRY], angle="criterion"),
    "no_angle_at_all": h.set_names([h.REVERT, h.DROP_RETRY], angle=None),
    "variant_retry_is_due": h.set_names([h.REVERT, "ignores whether a retry is due"]),
    "variant_retry_due_words": h.set_names([h.REVERT, "refreshes even when no retry due is signalled"]),
}


@pytest.mark.parametrize("how", sorted(BUG_GOOD))
def test_bug_fix_row_accepts_other_wordings_of_a_good_design(tmp_path, how):
    # covers: TQ-200d-3
    # angle: boundary
    row = h.real_row("bug")
    out = h.with_record("bug", tmp_path, BUG_GOOD[how])
    h.expect_passes(row, tmp_path, out)


@pytest.mark.parametrize("style", h.STYLES)
def test_bug_fix_row_accepts_any_yaml_formatting_of_the_record(tmp_path, style):
    # covers: TQ-200d-3
    # angle: real_artifact
    row = h.real_row("bug")
    out = h.with_record("bug", tmp_path, None, style=style)
    h.expect_passes(row, tmp_path, out)


def test_bug_fix_row_accepts_extra_unrelated_and_reordered_entries(tmp_path):
    # covers: TQ-200d-3
    # angle: boundary
    row = h.real_row("bug")

    def reorder(data: dict) -> None:
        h.extra_entry(data, angle="reachability", description="Running the CLI as a subprocess exits 0.")
        h.extra_entry(data, angle="real_artifact", description="The artifact is read back.")
        h.spec_of(data).reverse()

    out = h.with_record("bug", tmp_path, reorder)
    h.expect_passes(row, tmp_path, out)


GATE_BAD = {
    "position_limit_missing": ([h.ALWAYS, h.DROP_WINDOW], ("position limit",), ("window open", "the gate always allows")),
    "window_open_missing": ([h.ALWAYS, h.DROP_LIMIT], ("window open",), ("position limit", "the gate always allows")),
    "always_allows_missing": ([h.DROP_WINDOW, h.DROP_LIMIT], ("the gate always allows",), ("window open", "position limit")),
    "always_allows_only": ([h.ALWAYS], ("window open", "position limit"), ("the gate always allows",)),
    "revert_does_not_stand_in_for_always_allows": ([h.REVERT, h.DROP_WINDOW, h.DROP_LIMIT], ("the gate always allows",), ("window open", "position limit")),
    "always_allows_reworded": ([h.DROP_WINDOW, h.DROP_LIMIT, "the gate always allows trades"], ("the gate always allows",), ("window open", "position limit")),
    "both_conditions_in_one_name": ([h.ALWAYS, "drop the window-open and position-limit conditions"], ("wrong version",), ()),
    "both_variants_in_one_name": ([h.ALWAYS, "ignore whether the window is open and the limit is reached"], ("wrong version",), ()),
    "window_check_has_no_variant": ([h.ALWAYS, "drop the window check", h.DROP_LIMIT], ("window open",), ("position limit", "the gate always allows")),
    "window_opens_is_not_window_open": ([h.ALWAYS, "the window opens at nine", h.DROP_LIMIT], ("window open",), ("position limit",)),
    "decoy_carrying_no_condition": ([h.ALWAYS, h.DROP_WINDOW, "return an empty list"], ("position limit",), ("window open",)),
    "decoy_raise_the_limit_is_no_variant": ([h.ALWAYS, h.DROP_WINDOW, "raise the limit"], ("position limit",), ("window open",)),
}


@pytest.mark.parametrize("how", sorted(GATE_BAD))
def test_gate_row_requires_one_wrong_version_per_condition(tmp_path, how):
    # covers: TQ-200d-3
    # angle: criterion
    # must_catch: gate row passes with one condition's wrong version missing
    # must_catch: gate row passes without 'the gate always allows'
    row = h.real_row("gate")
    names, words, absent = GATE_BAD[how]
    spec = {a["kind"]: a for a in row["expected"]["assertions"]}
    assert h.K_WRONG in spec and h.K_JUDGEMENT in spec and h.K_SCHEMA in spec, sorted(spec)
    h.expect_passes(row, tmp_path, h.gold_dir(row), "control")
    out = h.with_record("gate", tmp_path, h.set_names(names))
    h.expect_fails(row, tmp_path, out, h.only(h.K_WRONG, "wrong version", *words, absent=absent))


def test_gate_row_fails_when_the_wrong_versions_sit_in_different_entries(tmp_path):
    # covers: TQ-200d-3
    # angle: discrimination
    row = h.real_row("gate")

    def split(data: dict) -> None:
        h.guard_of(data)["must_catch"] = [h.ALWAYS, h.DROP_WINDOW]
        h.extra_entry(data, angle="discrimination", must_catch=[h.DROP_LIMIT])

    out = h.with_record("gate", tmp_path, split)
    h.expect_fails(row, tmp_path, out, h.only(h.K_WRONG, "wrong version"))


GATE_GOOD = {
    "case_and_padding": h.set_names(["  The Gate Always Allows ", "Drop the Window-Open condition", "drop the POSITION-LIMIT condition"]),
    "underscored": h.set_names([h.ALWAYS, "skip the window_open check", "ignore the position_limit check"]),
    "spaced": h.set_names([h.ALWAYS, "drop the window open condition", "drop the position limit condition"]),
    "reversed_order": h.set_names([h.DROP_LIMIT, h.DROP_WINDOW, h.ALWAYS]),
    "extra_names": h.set_names([h.ALWAYS, h.DROP_WINDOW, "allow every trade after hours", h.DROP_LIMIT]),
    "no_discrimination_angle": h.set_names([h.ALWAYS, h.DROP_WINDOW, h.DROP_LIMIT], angle="criterion"),
    "variants_open_and_reached": h.set_names([h.ALWAYS, "ignore whether the window is open", "allow the trade once the limit is reached"]),
    "variants_closed_and_is_reached": h.set_names([h.ALWAYS, "allow the trade when the window is closed", "skip the check that the limit is reached"]),
    "variants_open_window_and_limit_reached": h.set_names([h.ALWAYS, "trade in an open window only", "limit reached must block"]),
    "variants_window_closed_and_limit_is_reached": h.set_names([h.ALWAYS, "the window closed case", "the limit is reached case"]),
}


@pytest.mark.parametrize("how", sorted(GATE_GOOD))
def test_gate_row_accepts_other_wordings_of_a_good_design(tmp_path, how):
    # covers: TQ-200d-3
    # angle: boundary
    row = h.real_row("gate")
    out = h.with_record("gate", tmp_path, GATE_GOOD[how])
    h.expect_passes(row, tmp_path, out)


@pytest.mark.parametrize("style", h.STYLES)
def test_gate_row_accepts_any_yaml_formatting_of_the_record(tmp_path, style):
    # covers: TQ-200d-3
    # angle: real_artifact
    row = h.real_row("gate")
    out = h.with_record("gate", tmp_path, None, style=style)
    h.expect_passes(row, tmp_path, out)
