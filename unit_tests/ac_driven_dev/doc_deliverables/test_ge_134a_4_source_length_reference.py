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
    """The quoted rule is exactly describe_measurement_rule()'s output, and the doc names what is left out:
    decision-history blocks and the text the rule already left out (triple-quoted strings, block comments)."""
    sec = D.section(D.read(PAGE), "## The rule")
    quote = " ".join(ln[2:] for ln in sec.splitlines() if ln.startswith("> "))
    assert quote == R.describe_measurement_rule()
    table = D.flat(D.section(D.read(PAGE), "## What is left out, and what is counted"))
    for row in ("| Triple-quoted strings (`\"\"\"` or `'''`) | No |", "| Block comments (`/* ... */`) | No |",
                "| Decision-history block | No |", "| Ordinary comment lines (`#`, `//`, `--`) | Yes |"):
        assert row in table, f"left-out table lost: {row}"


def test_python_and_javascript_examples_measure_what_they_state():
    # covers: GE-134a-4
    # angle: real_artifact
    """One Python and one JavaScript example each show raw count and measured length side by side, and the
    real counting function, run on the example with its notes removed, gives exactly those two numbers."""
    for language in ("Python", "JavaScript"):
        lines, raw, measured = _example(language)
        assert len(lines) == raw, (language, len(lines), raw)
        assert R.count_content_lines("\n".join(lines) + "\n") == measured, language
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
    """Through the real ratchet: adding a decision-history entry adds no measured line and leaves the length
    unchanged, an ordinary comment still counts as one line, and the published rule names what is left out."""
    before = "x = 1\n\n# ==============\n# DECISION HISTORY\n# ==============\n# - 2026-10-01 [coder/X-1]: Created.\n"
    history = before + "# - 2026-10-02 [coder/X-2]: Changed.\n"
    comment = before.replace("x = 1\n", "x = 1\n# an ordinary comment\n")
    assert R.count_content_lines(before) == 2 == R.count_content_lines(history)
    assert R.count_added_measured_lines(before, history) == 0
    assert R.count_added_measured_lines(before, comment) == 1
    assert R.count_content_lines(comment) == 3
    rule = R.describe_measurement_rule()
    assert "a decision-history block is not counted" in rule and "ordinary '#' comments" in rule
