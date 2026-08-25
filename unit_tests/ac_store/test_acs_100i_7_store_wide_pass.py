"""
MODULE: test_acs_100i_7_store_wide_pass
GOAL: Pin ACS-100i-7 — on the REAL acceptance-criteria store, exactly as it
    stands and with no record edited, refusals attributable to the
    package-surface rule must drop to zero, and every other refusal must be
    unchanged file-for-file and message-for-message.
BUSINESS CONTEXT: KI-ACS-005. The defect is a property of the corpus, not of a
    fixture: the gate is diff-scoped, so it is invisible until an unrelated
    change drags one of these records into a commit, at which point the commit
    needs a [HOOK-SKIP: check-ac-schema] directive to land. A fixture-only test
    cannot observe that property — hence CLAUDE.md's "Real-artifact behavioral
    spot-check" rule, applied here as a whole-corpus assertion.
ARCHITECTURE: The pass runs the real jsonschema helper the commit-time hook
    calls over every AC YAML under docs/acceptance-criteria/ (index.yaml
    excluded), and the pre-change refusal baseline is a recorded artifact —
    tests/fixtures/acs_100i_7/pre_change_refusal_baseline.json — measured on
    this worktree at 9b16d013 BEFORE the narrowing: 3232 records, 280 refused,
    243 of them on this rule, 37 for unrelated reasons. The last test executes
    the real commit-time hook as a subprocess.

    The second test is the anti-loosening guard. If an implementation reaches
    "zero rule refusals" by weakening validation generally — for instance by
    relaxing the `it_requirements` object branch — the 37 unrelated refusals
    shrink too and that test fails.

AC: ACS-100i-7 (docs/acceptance-criteria/ac-store/
    ACS-100-structured-requirements/ACS-100i-7.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_support import (  # noqa: E402
    AC_SCHEMA_HOOK,
    NAMED_FALSE_REFUSALS,
    REPO_ROOT,
    SCHEMA_VALIDATOR_CLI,
    find_store_record,
    load_baseline,
    run_cli,
    store_relative,
    top_level_rule_is_present,
    whole_store_pass,
)


def test_no_real_store_record_is_refused_on_the_package_surface_rule():
    # covers: ACS-100i-7
    """ACS-100i-7 s1: with no record edited and no record carrying
    `package_surface: true`, the number of records the whole-store pass refuses
    for lacking a structured implementation spec must be zero.

    Currently RED: 243 of the store's 3232 records are refused on this rule,
    including BO-2000d-1 / -2 / -1-i — the three records that *specify* it.

    The guard on `top_level_rule_is_present()` keeps this from passing
    vacuously: the rule is being narrowed, not deleted, and with the block gone
    the attribution would be empty for every record.
    """
    baseline = load_baseline()
    assert top_level_rule_is_present(), (
        "the schema no longer carries a top-level if/then pair. ACS-100i-7 "
        "requires zero refusals ON THIS RULE, not the rule's deletion — with "
        "the block gone this assertion is vacuous."
    )

    refusals = whole_store_pass()
    on_rule = sorted(
        store_relative(path) for path, v in refusals.items() if v.rule_messages
    )

    assert on_rule == [], (
        f"{len(on_rule)} records are still refused for lacking a structured "
        f"implementation spec (baseline before the change: "
        f"{baseline['refused_on_package_surface_rule']}). No record in the "
        "store declares `package_surface: true`, so the obligation must apply "
        f"to none of them. First 10: {on_rule[:10]}"
    )


def test_unrelated_refusals_are_unchanged_file_for_file():
    # covers: ACS-100i-7
    """ACS-100i-7 s2: the refusals that remain must be exactly the ones that
    were failing for other reasons before the change — the same file paths and
    the same messages, none added and none removed.

    This is the anti-loosening guard, and it is GREEN today by construction (the
    baseline was recorded from this same corpus). It must STAY green: a change
    that reaches zero rule-refusals by weakening validation generally will shrink
    this set and fail here.

    If the store itself has legitimately changed since the baseline was recorded
    (records added, `documentation_triggers` fixed, a `test_spec` shape
    corrected), regenerate the fixture in a separate, clearly-labelled commit —
    do NOT weaken this assertion.
    """
    baseline = load_baseline()
    expected = {path: sorted(msgs) for path, msgs in baseline["unrelated_refusals"].items()}

    refusals = whole_store_pass()
    actual = {
        store_relative(path): sorted(v.other_messages)
        for path, v in refusals.items()
        if v.other_messages
    }

    added = sorted(set(actual) - set(expected))
    removed = sorted(set(expected) - set(actual))
    changed = sorted(p for p in set(actual) & set(expected) if actual[p] != expected[p])

    assert (added, removed, changed) == ([], [], []), (
        "the unrelated refusals must be identical to the pre-change baseline "
        f"({baseline['unrelated_refusal_count']} records measured at "
        f"{baseline['measured_at_commit']}). Added: {added}. Removed: "
        f"{removed}. Messages changed: {changed}."
    )


@pytest.mark.parametrize("ac_id", NAMED_FALSE_REFUSALS)
def test_named_previously_refused_record_is_accepted_on_its_own(ac_id):
    # covers: ACS-100i-7
    """ACS-100i-7 s3: BO-2000d-1, BO-2000d-2, BO-2000d-1-i, BP-006a-1 and
    BO-1800a-1 — all previously refused on this rule, none of them edited by
    this change — must each be accepted when validated on their own.

    The real on-disk record is passed to the shipped CLI by file path; nothing
    is copied, rewritten or reconstructed, so this asserts against the actual
    corpus artifact rather than a fixture that reproduces the author's
    assumptions about it.

    Currently RED: each exits 1 today.
    """
    path = find_store_record(ac_id)

    run = run_cli(SCHEMA_VALIDATOR_CLI, str(path))

    assert run.returncode == 0, (
        f"{ac_id} is unedited and declares no package surface, so it must be "
        f"accepted; validate_ac_schema.py exited {run.returncode}\n{run.output}"
    )


def test_commit_time_ac_check_does_not_block_an_unedited_build_record(tmp_path):
    # covers: ACS-100i-7
    """ACS-100i-7 s4: a commit whose diff contains one of those records
    unchanged, alongside an unrelated edit elsewhere, must not be blocked, and
    must need no skip directive to complete.

    This runs the REAL pre-commit hook
    (templates/scripts/commit_guardian/check_ac_schema.py) as a subprocess
    through its production HOOK_TEST_STAGED_FILES seam, with cwd set to this
    worktree so the hook's `git rev-parse --show-toplevel` root resolution — and
    therefore its schema lookup — behaves exactly as it does in a real commit.

    Currently RED. Verified by hand at 9b16d013: the hook exits 1 with
    "[check-ac-schema]: 1 file(s) failed validation" on BO-2000d-1.yaml. That is
    the closing condition KI-ACS-005 states — a commit touching a
    build-orchestration AC no longer needing [HOOK-SKIP: check-ac-schema].
    """
    unedited = find_store_record("BO-2000d-1")
    unrelated_edit = tmp_path / "unrelated_change.txt"
    unrelated_edit.write_text("an edit elsewhere in the commit\n", encoding="utf-8")

    staged = "\n".join([str(unedited), str(unrelated_edit)])
    run = run_cli(
        AC_SCHEMA_HOOK,
        cwd=REPO_ROOT,
        env_overrides={"HOOK_TEST_STAGED_FILES": staged},
    )

    assert run.returncode == 0, (
        "the commit-time AC check must not block a commit that merely carries "
        f"an unedited, undeclared build record; exit={run.returncode}\n"
        f"{run.output}"
    )
    assert "HOOK-SKIP" not in run.output, (
        "no skip directive may be needed to complete the commit; the hook "
        f"suggested one:\n{run.output}"
    )
