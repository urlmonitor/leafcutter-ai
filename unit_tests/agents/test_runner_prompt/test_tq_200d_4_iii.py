"""
MODULE: unit_tests/agents/test_runner_prompt/test_tq_200d_4_iii.py
COVERS: TQ-200d-4-iii
GOAL: Red-first specification of the test-runner prompt change of TQ-200d-4-iii: a run that executed
    no test is reported as NO TEST RAN, never as a PASS; PASS needs a passed-test count above zero
    quoted from the runner's own summary; the machine-parsed reply keeps its keys and sets
    `passed` false (reason in `anomalies`) when no test ran.
HONEST LIMIT: a prompt; the behaviour is a model's report, proved by TQ-200d-4-iv's recorded trap row.
    These tests pin the rules the template must state, each scoped to its own section, with the
    report blocks (fenced) read apart from the prose. Every bad case is the REAL template with ONE
    thing swapped, and the sibling rules are asserted to still hold so a bad case cannot be caught
    by a rule that belongs to another test.
RED STATE: the template has no PASS-needs-a-count rule, no '## Output: No Test Ran' section and no
    NO TEST RAN vocabulary.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_SUPPORT_FILE = Path(__file__).with_name("_support.py")
_spec = importlib.util.spec_from_file_location("_tq_200d_4_support", _SUPPORT_FILE)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

OLD_SUCCESS_SECTION = (
    "## Output: Success\n\n```\n## Test Results — <suite-name>\n\nStatus: PASS\n"
    "Tests run: <N>   Failures: 0   Errors: 0   Skipped: <S>\nElapsed: <T>s\n```\n\n"
    "One-liner only. Do not include raw stdout.\n\n"
)
EXIT_ENOUGH = "An exit status of 0 is enough to report PASS."


def _drop_fenced_lines(text: str, title: str, pattern: str) -> str:
    """The template with the lines of the section's FENCED blocks that match `pattern` removed (prose untouched)."""
    block = S.section(text, title)
    assert block is not None
    kept, in_fence, dropped = [], False, 0
    for line in block.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif in_fence and re.match(pattern, line):
            dropped += 1
            continue
        kept.append(line)
    assert dropped, f"no fenced line matched {pattern!r}"
    return S.replace_section(text, title, "\n".join(kept))


def test_template_requires_a_quoted_passed_count_for_pass():
    # covers: TQ-200d-4-iii
    # angle: discrimination
    # must_catch: revert the fix
    # must_catch: exit status 0 alone allowed to report PASS
    text = S.read(S.TEMPLATE)
    assert S.success_problems(text) == [], "'## Output: Success' must say PASS needs a quoted passed-test count above zero"
    assert "No-op Rule" in S.section_titles(text) and "No Test-Relevant Changes" in S.section(text, "No-op Rule"), \
        "the No-op Rule stays and stays distinct (control)"

    # bad case 1: the revert, the old Success section word for word
    reverted = S.replace_section(text, "Output: Success", OLD_SUCCESS_SECTION)
    assert set(S.success_problems(reverted)) == {
        "no-pass-needs-a-count-rule", "exit-status-alone-not-excluded", "report-block-quotes-no-runner-summary",
        "unittest-count-note-missing"}

    # bad case 2: an exit status of 0 alone is allowed to report PASS (the rule sentence stays)
    exit_alone = S.rewrite_sentences(text, "Output: Success", S.is_exit_pass_sentence, EXIT_ENOUGH)
    assert "exit-status-alone-not-excluded" in S.success_problems(exit_alone)

    # bad case 3: the count rule is weakened, three ways; the exit-status sentence stays
    weakened = {
        "no count at all": "PASS is reported when the runner's summary shows the tests passed.",
        "zero allowed": "PASS is reported only when the report quotes a passed-test count of zero or more from the runner's own summary.",
        "count not from the summary": "PASS is reported only when a passed-test count greater than zero is estimated from the output.",
    }
    for label, sentence in weakened.items():
        mutated = S.rewrite_sentences(text, "Output: Success", S.is_pass_rule, sentence)
        problems = S.success_problems(mutated)
        assert "no-pass-needs-a-count-rule" in problems, (label, problems)
        assert "exit-status-alone-not-excluded" not in problems, (label, problems)

    # bad case 4: the report block no longer quotes the runner's summary
    quiet = _drop_fenced_lines(text, "Output: Success", r".*[Ss]ummary.*")
    assert S.success_problems(quiet) == ["report-block-quotes-no-runner-summary"]

    # bad case 5: the unittest note is missing (unittest prints 'Ran N tests ... OK', not '1 passed')
    no_note = S.rewrite_sentences(text, "Output: Success", lambda sentence: "unittest" in sentence, "")
    assert S.success_problems(no_note) == ["unittest-count-note-missing"]

    # probes: other wordings of the same rule are accepted
    for good in (
        "Report PASS only if you can quote a passed-test count above zero from the runner's own summary.",
        "A PASS requires a passed-test count of more than zero, quoted from the runner's own summary.",
        "Never report PASS unless the runner's own summary shows at least one passed test.",
    ):
        assert S.is_pass_rule(good), good
    assert S._is_unittest_count_note("For unittest, 'Ran N tests ... OK' with N above zero is the passed count.")
    assert not S._is_unittest_count_note("For unittest, 'Ran N tests ... OK' is the passed count.")
    assert not S.is_pass_rule("PASS means the suite ran and exited 0.")


def test_template_has_a_no_test_ran_report():
    # covers: TQ-200d-4-iii
    # angle: real_artifact
    # must_catch: no-test-ran report drops the command that was run
    text = S.read(S.TEMPLATE)
    assert S.no_test_ran_problems(text) == [], "'## Output: No Test Ran' must follow '## Output: Success' and be complete"

    # bad case 1: the report drops the command that was run (the reasons and status stay)
    no_command = _drop_fenced_lines(text, "Output: No Test Ran", r"\s*Command( run)?:")
    assert S.no_test_ran_problems(no_command) == ["block-lacks-the-command-run"]

    # bad case 2: the report drops its reason line
    no_reason = _drop_fenced_lines(text, "Output: No Test Ran", r"\s*Reason:")
    assert set(S.no_test_ran_problems(no_reason)) == {"block-lacks-a-reason", "reason-line-lacks-a-named-reason"}

    # bad case 3: one of the two named reasons is missing, each in turn
    no_collect = S.swap(text, "Output: No Test Ran", "nothing collected", "nothing")
    assert set(S.no_test_ran_problems(no_collect)) == {"reason-nothing-collected-missing", "reason-line-lacks-a-named-reason"}
    no_summary = S.swap(text, "Output: No Test Ran", "no runner summary", "no output")
    assert set(S.no_test_ran_problems(no_summary)) == {"reason-no-runner-summary-missing", "reason-line-lacks-a-named-reason"}

    # bad case 3b: the third reason, 'no passed test', is dropped (a run whose summary shows no passed test)
    no_passed = S.swap(text, "Output: No Test Ran", "no passed test", "no output")
    assert set(S.no_test_ran_problems(no_passed)) == {"reason-no-passed-test-missing", "reason-line-lacks-a-named-reason"}
    # ... or only from the Reason line, the prose still naming it
    line_only = S.swap(text, "Output: No Test Ran", "nothing collected | no passed test | no runner summary",
                       "nothing collected | no runner summary")
    assert S.no_test_ran_problems(line_only) == ["reason-line-lacks-a-named-reason"]

    # bad case 3c: the skipped-only wording is missing, each of the three triggers in turn
    for trigger in S.NO_PASSED_TEST_TRIGGERS:
        no_trigger = S.swap(text, "Output: No Test Ran", trigger, "something else")
        assert S.no_test_ran_problems(no_trigger) == ["no-passed-test-trigger-wording-missing"], trigger

    # bad case 4: the report says PASS
    says_pass = S.swap(text, "Output: No Test Ran", "Status: NO TEST RAN", "Status: PASS")
    assert set(S.no_test_ran_problems(says_pass)) == {"block-lacks-status-no-test-ran", "block-says-pass"}

    # bad case 5: the section is placed after the failure report, not after the success report
    block = S.section(text, "Output: No Test Ran")
    removed = S.replace_section(text, "Output: No Test Ran", "")
    start, _end = S.section_span(removed, "Combined Output (action: all)")
    misplaced = removed[:start] + block + removed[start:]
    assert S.no_test_ran_problems(misplaced) == ["not-placed-after-success"]

    # bad case 6: no such section at all
    assert S.no_test_ran_problems(S.replace_section(text, "Output: No Test Ran", "")) == ["no-section"]


def test_machine_parsed_reply_is_not_passed_when_no_test_ran():
    # covers: TQ-200d-4-iii
    # angle: real_artifact
    # must_catch: machine-parsed reply allowed to set passed true when no test ran
    text = S.read(S.TEMPLATE)
    title = "Machine-Parsed Dispatch Output Contract"
    assert S.machine_problems(text) == [], "passed must be false, reason in anomalies, keys unchanged"
    assert S.combined_problems(text) == [], "the combined summary's Status vocabulary needs NO TEST RAN"
    assert S.manifest_problems(text) == [], "the manifest says test_suite_executed is false when no test ran"

    def about_no_test_ran(sentence: str) -> bool:
        return bool(re.search(r"no test ran", sentence, re.IGNORECASE))

    def passed_rule(sentence: str) -> bool:
        return about_no_test_ran(sentence) and "outcome" not in sentence

    assert S.machine_problems(text) == [], "outcome rule is its own sentence (control)"

    # bad case 1: the machine-parsed reply may set passed true when no test ran
    passed_true = S.rewrite_sentences(
        text, title, passed_rule, "When no test ran, set `passed` to `true` and name the reason in `anomalies`.")
    assert S.machine_problems(passed_true) == ["passed-not-false-when-no-test-ran"]

    # bad case 2: passed is false but the reason is not carried in anomalies
    no_reason = S.rewrite_sentences(text, title, passed_rule, "When no test ran, `passed` is `false`.")
    assert S.machine_problems(no_reason) == ["reason-not-in-anomalies"]

    # bad case 3: the rule is dropped from the machine-parsed section altogether
    dropped = S.rewrite_sentences(text, title, about_no_test_ran, "")
    assert S.machine_problems(dropped) == ["no-no-test-ran-rule"]

    # bad case 3b: the outcome rule is removed, or gives outcome as "failed" (quick-fix reads outcome
    # before passed, so a no-test run answered "failed" would read as a healthy red)
    no_outcome = S.rewrite_sentences(text, title, lambda sentence: "outcome" in sentence, "")
    assert S.machine_problems(no_outcome) == ["outcome-not-error-when-no-test-ran"]
    for wrong in ('"failed"', '"passed"'):
        wrong_outcome = S.swap(text, title, '`"error"`', f"`{wrong}`")
        assert S.machine_problems(wrong_outcome) == ["outcome-not-error-when-no-test-ran"], wrong

    # bad case 4: the combined summary keeps PASS/FAIL only
    pass_fail = S.swap(text, "Combined Output (action: all)", "PASS/FAIL/NO TEST RAN", "PASS/FAIL")
    assert S.combined_problems(pass_fail) == ["status-vocabulary-lacks-no-test-ran"]

    # bad case 5: the manifest keeps test_suite_executed true for a run that executed nothing
    manifest_true = S.rewrite_sentences(
        text, "Completion Manifest", lambda s: about_no_test_ran(s) and "test_suite_executed" in s,
        "When no test ran, `test_suite_executed` stays `true`.")
    assert S.manifest_problems(manifest_true) == ["manifest-lacks-test-suite-executed-false-for-no-test-ran"]

    # bad case 6: the manifest sentence does not mirror the three reasons
    for reason in S.NO_TEST_RAN_REASONS:
        unmirrored = S.swap(text, "Completion Manifest", reason, "something")
        assert S.manifest_problems(unmirrored) == ["manifest-reasons-not-mirrored"], reason
