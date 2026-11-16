"""
MODULE: unit_tests/agents/test_runner_prompt/test_tq_200d_4_ii.py
COVERS: TQ-200d-4-ii
GOAL: Red-first specification of the test-runner prompt change of TQ-200d-4-ii: the runner runs a
    named test file through the project's configured test command (testing_context.test_command),
    falls back to `python -m pytest <file>` only when the setting is unset, and offers no plain
    `python <file>.py` form for running one file.
HONEST LIMIT: the deliverable is a prompt; what a model does with it happens in a model run that a
    unit test cannot reproduce (the behavioural proof is the test-runner eval, TQ-200d-4-iv). These
    tests pin what is decidable: the frontmatter key, the absence of a plain-script run, the
    single-file sentence and the `single <path>` bullet (each scoped to its own section), and the
    reference row. Every bad case is the REAL template (or reference doc) with ONE thing swapped.
RED STATE: the template still says `python unit_tests/live_trader/<file>.py` for a single file and
    declares no testing_context.test_command; the reference doc has no such row.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_SUPPORT_FILE = Path(__file__).with_name("_support.py")
_spec = importlib.util.spec_from_file_location("_tq_200d_4_support", _SUPPORT_FILE)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

KEY_BLOCK = re.compile(r"\n  testing_context\.test_command:\n(?:    .*\n)+")


def test_template_declares_testing_context_test_command():
    # covers: TQ-200d-4-ii
    # angle: real_artifact
    # must_catch: config key left out of the frontmatter
    text = S.read(S.TEMPLATE)
    assert S.key_problems(text) == [], "frontmatter config_keys must declare testing_context.test_command (required: false)"
    config_keys = S.frontmatter(text)["config_keys"]
    assert {"test_command_live_trader", "test_output_dir"} <= set(config_keys), "the existing keys stay (control)"

    # bad case 1: the key block is deleted from the frontmatter, everything else untouched
    head, body = S.split_frontmatter(text)
    without_key, removed = KEY_BLOCK.subn("\n", "\n" + head + "\n")
    assert removed == 1
    assert S.key_problems("---\n" + without_key.strip("\n") + "\n---\n" + body) == ["key-missing"]

    # bad case 2: the key is only mentioned in another key's description, not declared
    mentioned = text.replace(
        'description: "Command to run the fast unit test suite"',
        'description: "Command to run the fast unit test suite; see testing_context.test_command"',
        1,
    )
    mentioned = KEY_BLOCK.sub("\n", mentioned, count=1)
    assert KEY in mentioned and S.key_problems(mentioned) == ["key-missing"]

    # bad case 3: declared as a required key (a project without the setting would be refused)
    required = re.sub(r"(testing_context\.test_command:\n    required: )false", r"\1true", text, count=1)
    assert required != text and S.key_problems(required) == ["key-not-optional"]


KEY = S.KEY
OLD_SINGLE_FILE = "`python unit_tests/live_trader/<file>.py`"


def _with_extra_run_instruction(text: str, title: str, line: str) -> str:
    original = S.section(text, title)
    assert original is not None
    return S.replace_section(text, title, original.rstrip("\n") + "\n\n" + line + "\n\n")


def test_template_offers_no_plain_script_run_of_a_test_file():
    # covers: TQ-200d-4-ii
    # angle: discrimination
    # must_catch: revert the fix
    # must_catch: plain 'python <file>.py' single-file form offered as an alternative
    text = S.read(S.TEMPLATE)
    assert S.plain_script_runs(text) == [], "the template must not run a test file as a plain script"

    # controls: runs that are NOT a plain-script run of a test file stay allowed and unflagged
    controls = (
        "Run `python -m pytest tests/check_window_total.py -v`.",
        "Run `poetry run python -m pytest unit_tests/sql_functions -v`.",
        "Run `python -m unittest discover -s unit_tests -t . -p \"test_*.py\"`.",
        'Run `python "{{config.output_root}}/scripts/db_check/checker.py" --target-dir .`.',
    )
    for control in controls:
        assert S.plain_script_runs(_with_extra_run_instruction(text, "Actions", control)) == [], control

    # bad case: the revert (the old single-file form comes back beside the new one)
    reverted = S.swap(
        text, "Routing Table", "For the **single-file** action",
        f"For the **single-file** action: {OLD_SINGLE_FILE} or, for a named file,",
    )
    assert len(S.plain_script_runs(reverted)) == 1 and "unit_tests/live_trader/<file>.py" in S.plain_script_runs(reverted)[0]

    # bad cases: a plain-script form offered as an alternative, in three spellings and two sections
    offered = {
        "Routing Table": "Alternatively run `python tests/check_window_total.py`.",
        "Actions": "Or `PYTHONPATH=. python tests/check_window_total.py` when imports fail.",
    }
    for title, line in offered.items():
        found = S.plain_script_runs(_with_extra_run_instruction(text, title, line))
        assert len(found) == 1 and "check_window_total.py" in found[0], (title, found)
    poetry = S.plain_script_runs(_with_extra_run_instruction(text, "Actions", "Or `poetry run python unit_tests/x/test_a.py`."))
    assert len(poetry) == 1


def test_single_file_instruction_names_configured_command_and_fallback():
    # covers: TQ-200d-4-ii
    # angle: real_artifact
    # must_catch: fallback named as plain python instead of python -m pytest
    text = S.read(S.TEMPLATE)
    assert S.routing_problems(text) == [], "the single-file sentence under '## Routing Table' must name the configured command and the fallback"
    assert S.action_problems(text) == [], "the 'single <path>' bullet under '## Actions' must name the same command"

    # bad case 1: the fallback is plain python in the Routing Table sentence
    plain_fallback = S.swap(text, "Routing Table", S.FALLBACK_FORM, "python <file>")
    assert S.routing_problems(plain_fallback) == [f"missing:{S.FALLBACK_FORM}"]
    assert S.action_problems(plain_fallback) == [], "the bullet is a separate rule and still holds"

    # bad case 2: the fallback is plain python in the Actions bullet
    bullet = S.single_action_bullet(text)
    assert "python -m pytest" in bullet
    plain_bullet = S.swap(text, "Actions", "python -m pytest", "python")
    assert S.action_problems(plain_bullet) == ["missing:python -m pytest"]
    assert S.routing_problems(plain_bullet) == [], "the sentence is a separate rule and still holds"

    # bad case 3: the sentence names a generic command, not the setting (the key still appears in the
    # frontmatter, which must not satisfy a rule scoped to the sentence)
    unnamed = S.swap(text, "Routing Table", S.CONFIGURED_FORM, "<test command> <file>")
    assert KEY in text and S.routing_problems(unnamed) != []
    assert S.action_problems(unnamed) == [], "the bullet is a separate rule and still holds"

    # probes of realistic variants: other wordings of the same rule pass the checker
    variants = (
        f"Run `{S.CONFIGURED_FORM}` (the {KEY} setting); when it is unset, run `{S.FALLBACK_FORM}`.",
        f"Use `{S.CONFIGURED_FORM}`; if {KEY} is not set or empty, fall back to `{S.FALLBACK_FORM}`.",
    )
    for variant in variants:
        assert S._command_problems(variant, (S.CONFIGURED_FORM, S.FALLBACK_FORM)) == [], variant
    # the fallback first, or an unconditional fallback, is wrong
    wrong = f"Run `{S.FALLBACK_FORM}`, or `{S.CONFIGURED_FORM}` ({KEY})."
    assert set(S._command_problems(wrong, (S.CONFIGURED_FORM, S.FALLBACK_FORM))) == {
        "fallback-not-conditional", "fallback-before-configured-command"}


def test_skills_config_reference_lists_test_command():
    # covers: TQ-200d-4-ii
    # angle: real_artifact
    # must_catch: row left out of the Testing Context table of docs/reference/skills-config-fields.md
    doc = S.read(S.REFERENCE_DOC)
    assert S.reference_problems(doc) == [], "the Testing Context table needs a testing_context.test_command row naming the test runner"
    row = S.reference_row(doc)
    assert row is not None and row[1] == "string" and row[2].lower() == "no"
    assert "testing_context.db_connection_test" in doc, "the neighbouring rows stay (control)"

    lines = doc.split("\n")
    index = next(i for i, line in enumerate(lines) if line.startswith("| `testing_context.test_command`"))

    # bad case 1: the row is deleted
    deleted = "\n".join(lines[:index] + lines[index + 1:])
    assert S.reference_problems(deleted) == ["row-missing-from-testing-context-table"]

    # bad case 2: the row sits in another section's table, not the Testing Context table
    moved = lines[:index] + lines[index + 1:]
    moved.extend(["", "## Elsewhere", "", "| Field | Type | Required | Default | Description |", "|---|---|---|---|---|", lines[index]])
    assert S.reference_problems("\n".join(moved)) == ["row-missing-from-testing-context-table"]

    # bad case 3: the row exists but does not name the test runner as a reader
    anonymous = lines[:index] + [re.sub(r"[Tt]est[- ]runner", "caller", lines[index])] + lines[index + 1:]
    assert S.reference_problems("\n".join(anonymous)) == ["test-runner-not-named"]
