"""The judgement questions sent to Jev, and what each answer means for an attack.

Rules followed (from docs.typesafe.ai "Jev 1.13 jaggedness"):
- one literal judgement per question, with explicit true/false criteria;
- nothing code can compute (counting, skips, assertion kinds) -- that lives in
  collect.static_flags;
- the state names its parts, and questions point at them in backticks.

Every question here is TRIAGE. A high "weak" answer means "attack this first",
never "this test is bad". The verdict belongs to a mutation run.
"""

from __future__ import annotations

# key -> (question dict, attack to run if the answer points at weakness)
TEST_QUESTIONS: dict[str, tuple[dict, str]] = {
    "mock_replaces_unit": ({
        "type": "noul",
        "instructions": "Does `test.source` (with `test.fixtures`) replace the function or class "
                        "from `code_under_test` with a mock, patch or stub, so the real code never runs?",
        "criteria": {"true": "The real code under test is mocked or patched out.",
                     "false": "The real code under test executes; only its collaborators may be mocked."},
    }, "Replace the unit's body with `return None` (or an empty result). If the test stays green it never ran the real code."),
    "asserts_only_on_mocks": ({
        "type": "noul",
        "instructions": "Are all assertions in `test.source` about mock calls or call arguments, "
                        "rather than about a value, row, file or state the real code produced?",
        "criteria": {"true": "Only mock-call / argument assertions.",
                     "false": "At least one assertion checks a real output or stored state."},
    }, "Delete the side effect the code should produce but keep the call. If the test stays green it tests wiring, not behaviour."),
    "has_control_case": ({
        "type": "noul",
        "instructions": "Does `test.source` (with `test.fixtures`) include a positive-control case: "
                        "input that SHOULD pass the condition being tested, asserted to pass, "
                        "alongside input that should not?",
        "criteria": {"true": "Both a should-pass and a should-fail case are set up and asserted.",
                     "false": "Only one side is set up, or the should-pass side is never asserted."},
    }, "Mutate the condition to exclude everything. Without a control case the test cannot tell 'filtered correctly' from 'filtered all'."),
    "fixture_is_static_population": ({
        "type": "noul",
        "instructions": "Does `code_under_test` process items in capped batches (a LIMIT, batch size "
                        "or max per call) while `test.source` only ever uses a fixed set of items "
                        "processed in a single call?",
        "criteria": {"true": "Capped batching in the code, a single fixed population in the test.",
                     "false": "No cap in the code, or the test runs repeated calls with new items arriving."},
    }, "Restore the old ordering and add a second, continuously arriving population that outranks the target rows; run several cycles."),
    "time_dependent": ({
        "type": "noul",
        "instructions": "Does the behaviour in `code_under_test` depend on the current time, "
                        "time windows, or timestamp boundaries?",
        "criteria": {"true": "Time, windows or timestamp boundaries matter to the result.",
                     "false": "The result does not depend on time."},
    }, "Move fixture rows onto a bucket boundary and shift the clock/timezone. If the test stays green, boundaries are untested."),
    "test_kind": ({
        "type": "choice",
        "instructions": "What is `test.source` mainly written to do?",
        "criteria": {
            "regression_pin": "Pin a specific bug fix so the bug cannot return.",
            "behaviour_spec": "Specify a feature's intended behaviour.",
            "smoke": "Check that something runs, imports or returns without error.",
            "characterization": "Record whatever the code currently outputs.",
        },
    }, "For regression_pin: revert the fix (git show <base>:<file>) and run the test. It must go red."),
    "weakness": ({
        "type": "score",
        "instructions": "How likely is it that a small wrong change to `code_under_test` "
                        "(an inverted or dropped condition, a removed filter, an empty result) "
                        "would still leave `test.source` passing?",
        "criteria": ["Very unlikely: the assertions pin exact outputs of the changed logic.",
                     "Possible: some wrong changes would slip through.",
                     "Likely: the assertions barely constrain the changed logic."],
    }, "Run the attack list for this test; start with the categories flagged above."),
}

TICKET_QUESTIONS: dict[str, tuple[dict, str]] = {
    "exercises_ticket_scenario": ({
        "type": "noul",
        "instructions": "Does `test.source` set up and check the specific failure scenario "
                        "described in `ticket_intent`?",
        "criteria": {"true": "The test reproduces the scenario the ticket describes.",
                     "false": "The test checks something else, or only a general happy path."},
    }, "Write the ticket's failure scenario as a mutant and check this test catches it."),
}


def gate_question(gate: str) -> tuple[dict, str]:
    """One question per changed condition -- the ConfigCache / CvdWindow shape.

    Worded as "is it ever true", not "are all inputs set": a test with one
    control row and one negative row must not read as unreachable.
    """
    return ({
        "type": "noul",
        "instructions": {
            "gate": gate,
            "question": "Trace `test.source` step by step, including the state that its earlier "
                        "calls to the code leave behind. At the call the assertions are about, is "
                        "`gate` true for at least one item, so the guarded branch runs?",
        },
        "criteria": {"true": "At the asserted call, `gate` is true at least once and the branch runs.",
                     "false": "At the asserted call, some input of `gate` keeps it false "
                              "(for example a value left over from an earlier call), so the branch never runs."},
    }, f"Delete or invert `{gate}`. If the test stays green, it never reached this branch.")


# Pre-registered 2026-09-25 for the leafcutter replication (wiring-shaped incidents),
# written BEFORE any leafcutter case was built. Enabled with --wiring. true = good.
WIRING_QUESTIONS: dict[str, tuple[dict, str]] = {
    "reaches_entry_point": ({
        "type": "noul",
        "instructions": "Does `test.source` (with `test.fixtures`) run the code through its production "
                        "entry point -- a CLI run as a subprocess, a hook through its real runner, a "
                        "workflow, or main() with a real argument list -- instead of importing an inner "
                        "function and calling it directly?",
        "criteria": {"true": "The test goes through the real entry point the product uses.",
                     "false": "The test imports and calls an inner function, or only inspects mocks."},
    }, "Delete the line that wires the unit into its entry point (CLI subcommand, hook registration, "
       "workflow call). If the test stays green it never went through the entry point."),
    "fixture_is_real_artifact": ({
        "type": "noul",
        "instructions": "Is the input data in `test.source` (with `test.fixtures`) produced by the real "
                        "producer -- the real serializer, a file read from disk, or the real upstream "
                        "function -- rather than typed by hand as a literal?",
        "criteria": {"true": "The input comes from the real producer or a real on-disk artifact.",
                     "false": "The input is a hand-typed literal (string, dict or list) written in the test."},
    }, "Feed the unit a real artifact from the producer (e.g. yaml.safe_dump output or a real file). "
       "If behaviour changes, the hand-typed fixture was hiding a format bug."),
}


# --abstain (development pass, 2026-09-25, written after the leafcutter results): the ticket and
# gate questions as `choice`, so Jev can say the state lacks the deciding fact instead of
# guessing ~0.5 on a noul. The yes/no criteria are copied verbatim from the noul versions; only
# the need_* options are new. weak = P(no); the need_* mass is reported separately.
NEED_OPTIONS = {
    "need_production_callers": "Cannot decide from the state: the answer depends on how production code "
                               "reaches the tested code (its callers, entry points, CI or workflow config), "
                               "which the state does not show.",
    "need_fixture_source": "Cannot decide from the state: the answer depends on fixtures, helpers or "
                           "conftest code that the state does not show.",
    "need_more_code": "Cannot decide from the state: the answer depends on parts of the code under test "
                      "that the excerpt does not show.",
}


def as_abstain_choice(question: dict) -> dict:
    """Turn a noul question into a choice with yes / no / need_* options (criteria kept verbatim)."""
    crit = question["criteria"]
    instructions = question["instructions"]
    note = ("Choose a need_* option only when the fact that decides the answer is missing from the "
            "state; otherwise choose yes or no.")
    if isinstance(instructions, dict):
        instructions = {**instructions, "abstain_rule": note}
    else:
        instructions = f"{instructions} {note}"
    return {"type": "choice", "instructions": instructions,
            "criteria": {"yes": crit["true"], "no": crit["false"], **NEED_OPTIONS}}


def abstain_weak_is_no(key: str) -> bool:
    """For abstain choices, is the 'no' answer the weak reading? (true for inverted questions and gates)."""
    return key in INVERTED or key.startswith("gate:")


# How an answer is turned into "points at weakness" (weak) or not.
# nouls: probability of the WEAK reading. has_control_case / exercises / gate are inverted.
INVERTED = {"has_control_case", "exercises_ticket_scenario", "reaches_entry_point", "fixture_is_real_artifact"}
UNCERTAIN_BAND = (0.30, 0.70)
# Properties that pick WHICH attacks to run; they are not evidence of weakness.
TRIAGE_ONLY = {"time_dependent", "fixture_is_static_population", "test_kind"}
