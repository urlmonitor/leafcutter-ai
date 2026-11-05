"""GE-134a-4 and its parent GE-134a -- the source-file length reference and the free decision history.

GE-134a-4 is ``test_required: false`` (a reference doc). Its checks read docs/reference/source-file-length-measurement.md
and hold it to the rule in force: the quoted rule must equal ``describe_measurement_rule()``, and each worked
example, with its line annotations removed, must measure what the doc says under the real ``count_content_lines``.
The GE-134a check drives the same real ratchet module on a small file.
"""

from __future__ import annotations

import re
import sys

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

sys.path.insert(0, str(D.REPO / "unit_tests" / "commit_guardian"))
import _ge_134a_fixture  # noqa: E402

R = _ge_134a_fixture.load_ratchet()  # the real templates/scripts/commit_guardian/_file_size_ratchet.py

PAGE = D.REPO / "docs" / "reference" / "source-file-length-measurement.md"
# The trailing "# counted ..." / "// not counted ..." note the doc puts after each example line.
_ANNOTATION = re.compile(r"\s*(?:#|//) (?:not )?counted\b.*$")


def _example(language: str) -> tuple[list[str], int, int]:
    """The example's lines with annotations removed, and the raw and measured counts its heading states."""
    text = D.read(PAGE)  # not D.section: the examples' own "# ..." lines would read as headings
    sec = text[text.index("\n## Examples\n"):text.index("\n## Moving history out of a file")]
    heading = re.search(r"^### " + language + r": (\d+) raw lines, (\d+) measured$", sec, re.M)
    assert heading, f"no {language} example heading stating raw and measured counts"
    block = re.search(r"```" + language.lower() + r"\n(.*?)```", sec[heading.end():], re.DOTALL)
    assert block, f"no fenced {language} example"
    lines = block.group(1).splitlines()
    assert all(_ANNOTATION.search(ln) for ln in lines), "control: every example line carries its annotation"
    return [_ANNOTATION.sub("", ln) for ln in lines], int(heading.group(1)), int(heading.group(2))


def test_reference_quotes_the_published_rule_verbatim_and_names_what_is_left_out():
    # covers: GE-134a-4
    # angle: real_artifact
    """The quoted rule is exactly describe_measurement_rule()'s output, and the doc names what is left out under
    the 2026-10-21 rule: comments of every style, standalone strings and blank lines are not counted; used
    strings, standalone f-strings and markers inside strings are; a decision-history block is uncounted
    because it is comments or a standalone string."""
    sec = D.section(D.read(PAGE), "## The rule")
    quote = " ".join(ln[2:] for ln in sec.splitlines() if ln.startswith("> "))
    assert quote == R.describe_measurement_rule()
    table = D.flat(D.section(D.read(PAGE), "## What is left out, and what is counted"))
    for row in ("| Comment, any style (`#`, `//`, `--`, `/* ... */`) | No |",
                "| Python string standing alone as a statement | No |",
                "| Python string that is used | Yes |",
                "| Standalone f-string | Yes |",
                "| Blank line | No |",
                "| Comment marker inside a string, glob, regex literal or here-document | Yes |"):
        assert row in table, f"left-out table lost: {row}"
    assert "in a line-comment form it is comments" in table and "standalone string" in table
    assert "uncounted either way" in table


def test_python_and_javascript_examples_measure_what_they_state():
    # covers: GE-134a-4
    # angle: real_artifact
    """One Python and one JavaScript example each show raw count and measured length side by side, and the
    real counting function, run on the example with its notes removed, gives exactly those two numbers."""
    for language, extension in (("Python", ".py"), ("JavaScript", ".js")):
        lines, raw, measured = _example(language)
        assert len(lines) == raw, (language, len(lines), raw)
        assert R.count_content_lines("\n".join(lines) + "\n", extension) == measured, language
        assert f"{raw} raw - " in D.read(PAGE) and f"= {measured} measured." in D.read(PAGE)


def test_reference_states_history_costs_nothing_so_moving_it_frees_nothing():
    # covers: GE-134a-4
    # angle: criterion
    """It states a decision-history block costs no measured lines, so moving it elsewhere frees none."""
    D.assert_all(
        D.section(D.read(PAGE), "## Moving history out of a file frees no lines"),
        ["A decision-history block costs no measured lines.",
         "Moving a file's decision history into another file or document therefore removes nothing from its "
         "measured length"],
        "source-file-length-measurement.md",
    )


def test_reference_links_ge_134a_and_the_doc_enforcer_convention_instead_of_restating_it():
    # covers: GE-134a-4
    # angle: criterion
    """It links GE-134a and the doc-enforcer skill's decision-history convention and says the convention is
    not repeated here."""
    text = D.flat(D.read(PAGE))
    assert "(../acceptance-criteria/guardrail-engine/GE-134-history-never-costs-size/GE-134a.yaml)" in text
    assert "[doc-enforcer skill](../../templates/skills/doc-enforcer/SKILL.md) and are not repeated here" in text


# ---------------------------------------------------------------- GE-134a (parent)
def test_parent_decision_history_is_free_while_code_and_comments_still_count():
    # covers: GE-134a, GE-134
    # angle: criterion
    """Through the real ratchet, under the 2026-10-21 rule (GE-127d-3 supersedes GE-134a: no comment, standalone
    string or blank line counts): adding a decision-history entry adds no measured line and leaves the length
    unchanged, an ordinary comment or blank line adds nothing either, an added code line counts one, and the
    published rule names what is left out."""
    before = "x = 1\n\n# ==============\n# DECISION HISTORY\n# ==============\n# - 2026-10-01 [coder/X-1]: Created.\n"
    history = before + "# - 2026-10-02 [coder/X-2]: Changed.\n"
    comment = before.replace("x = 1\n", "x = 1\n# an ordinary comment\n")
    blank = before.replace("x = 1\n", "x = 1\n\n\n")
    code = before.replace("x = 1\n", "x = 1\ny = 2\n")
    code_lines = [ln for ln in before.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert len(code_lines) == 1  # independent derivation: only `x = 1` is a code line
    assert R.count_content_lines(before) == len(code_lines) == R.count_content_lines(history)
    assert R.count_content_lines(comment) == R.count_content_lines(blank) == len(code_lines)
    assert R.count_added_measured_lines(before, history) == 0
    assert R.count_added_measured_lines(before, comment) == 0
    assert R.count_added_measured_lines(before, blank) == 0
    assert R.count_added_measured_lines(before, code) == 1
    assert R.count_content_lines(code) == len(code_lines) + 1
    rule = R.describe_measurement_rule()
    assert re.search(r"not count[^;]*\bcomments\b", rule) and re.search(r"not count[^;]*blank lines", rule)
