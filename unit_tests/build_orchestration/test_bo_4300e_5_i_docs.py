"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_5_i_docs.py
AC: BO-4300e-5-i -- the clearing how-to covers the remove refusals added by BO-4300e-2-iv..viii,
    and the answer reference names each one by its code and fields.
GOAL: Prove the how-to has a section for a running program, a half-cleared workspace, a folder
    with no record and a detached workspace, links to the reference instead of restating it,
    and publishes no deletion step that bypasses the maker; and that every refusal message,
    code and field the reference documents is one the deployed remove code really emits.
BUSINESS CONTEXT: A guide whose answer codes or messages drift from the maker sends a person
    to a refusal that never appears. Tying the documented phrases to the code catches that.
ARCHITECTURE: unittest; reads the two docs and the remove sources as text. No maker run: the
    behaviour itself is proven by test_bo_4300e_2_{iv..viii}.py.

DECISION HISTORY
====================================================================
- 2026-11-02 [claude/BO-4300e-5-i]: Created with the how-to and reference update.
====================================================================
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLEAR_DOC = REPO / "docs/how-to/clear-a-workspace.md"
REF_DOC = REPO / "docs/reference/workspace-maker-answer.md"
REMOVE_SOURCES = (
    REPO / "templates/scripts/worktree_remove.py",
    REPO / "templates/scripts/worktree_remove_checks.py",
)
DELETE_COMMANDS = re.compile(r"\b(rm|rmdir|Remove-Item|rmtree|del)\b|git\s+worktree\s+remove")
# The fixed opening words of each refusal message, as the reference quotes them.
MESSAGE_OPENINGS = (
    "Programs are working inside",
    "The program check is unavailable",
    "Could not remove all of",
)
REFUSAL_FIELDS = ("holders", "files", "unsent", "discard_token")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"no '## {heading}' section"
    return m.group(1)


class TestClearHowTo(unittest.TestCase):
    def setUp(self):
        self.text = _read(CLEAR_DOC)

    def test_how_to_covers_each_new_refusal_and_links_the_reference(self):
        # covers: BO-4300e-5-i
        """AC-1: one section per situation, each pointing at what to do, and the guide links the
        reference for codes and fields."""
        for heading, must in (
            ("If a program is running in the workspace", ("PROCESS_HOLDS_FILES", "Nothing was deleted")),
            ("If an earlier clearing stopped part-way", ("UNSENT_WORK", "discard_token", "never store")),
            ("If the folder has no workspace record", ("NOT_FOUND",)),
            ("If the workspace is off its line of work", ("unsent.commits", "git push origin HEAD:refs/heads/<branch>")),
        ):
            body = _section(self.text, heading)
            for phrase in must:
                self.assertIn(phrase, body, msg=f"'{heading}' lacks {phrase!r}")
        self.assertIn("../reference/workspace-maker-answer.md", self.text)

    def test_how_to_publishes_no_deletion_that_bypasses_the_maker(self):
        # covers: BO-4300e-5-i
        """AC-1: no fenced command deletes a folder or repository outside the maker."""
        for block in re.findall(r"```[^\n]*\n(.*?)```", self.text, re.S):
            self.assertIsNone(DELETE_COMMANDS.search(block), msg=f"deletion step in:\n{block}")


class TestAnswerReference(unittest.TestCase):
    def setUp(self):
        self.refusals = _section(_read(REF_DOC), "Refusals of remove")
        self.code = "\n".join(_read(p) for p in REMOVE_SOURCES)

    def test_reference_names_each_new_refusal_by_code(self):
        # covers: BO-4300e-5-i
        """AC-1: the program, check-unavailable, partial-deletion, half-cleared, record-less and
        detached refusals are each listed with their code."""
        rows = [line for line in self.refusals.splitlines() if line.startswith("| ") and "---" not in line][1:]
        self.assertEqual(len(rows), 6, msg="\n".join(rows))
        for code in ("PROCESS_HOLDS_FILES", "UNSENT_WORK", "NOT_FOUND"):
            self.assertIn(f"`{code}`", self.refusals)
            self.assertIn(f'"{code}"', self.code, msg=f"{code} is not emitted by remove")

    def test_documented_messages_and_fields_are_emitted_by_remove(self):
        # covers: BO-4300e-5-i
        """AC-1: a message or field the reference documents that remove does not emit fails."""
        for opening in MESSAGE_OPENINGS:
            self.assertIn(opening, self.refusals, msg=f"reference does not quote {opening!r}")
            self.assertIn(opening, self.code, msg=f"remove never says {opening!r}")
        for field in REFUSAL_FIELDS:
            self.assertIn(f"`{field}`", self.refusals)
            self.assertRegex(self.code, rf"\b{field}=|[\"']{field}[\"']", msg=f"remove never emits {field}")


if __name__ == "__main__":
    unittest.main()
