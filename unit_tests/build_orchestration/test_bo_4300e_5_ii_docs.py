"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_5_ii_docs.py
AC: BO-4300e-5-ii -- the clearing how-to and the answer reference cover a clearing that stopped
    part-way, a leftover whose repository can no longer be read, and a record-less leftover; every
    code, field and message they name is one the deployed maker really emits.
GOAL: Prove the how-to tells a person that asking again finishes a stopped clearing without a token,
    that ensure and locate answer HALF_CLEARED, that an unreadable repository means its commits cannot
    be checked (token read from the refusal), and the narrowed record-less rule; that neither page
    publishes a deletion that bypasses the maker; and that the reference documents each new answer
    once, by code and fields, matching what the real maker CLI prints.
BUSINESS CONTEXT: A page that overstates the record-less rule sends a person to expect a token that
    never comes; a page whose phrases drift from the maker sends them to a refusal that never appears.
ARCHITECTURE: Reads the two docs and the maker sources as text (shared helpers come from the
    BO-4300e-5-i test). One test runs the real maker CLI in a subprocess (fixtures of
    test_bo_4300e_2_ix/_x/_xi) and compares its printed JSON with the reference.

DECISION HISTORY
====================================================================
- 2026-11-04 [test-writer/fast-lane bo-4300e-5-ii, BO-4300e-5-ii]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2_x import LeftoverCase
from unit_tests.build_orchestration.test_bo_4300e_5_i_docs import (
    CLEAR_DOC,
    DELETE_COMMANDS,
    REF_DOC,
    REMOVE_SOURCES,
    _read,
    _section,
)

REPO = Path(__file__).resolve().parents[2]
ANSWER_SRC = REPO / "templates/scripts/worktree_answer.py"
HALF_SRC = REPO / "templates/scripts/worktree_remove_half.py"
STOPPED_HEADING = "If an earlier clearing stopped part-way"
NO_RECORD_HEADING = "If the folder has no workspace record"
REFERENCE_LINK = "../reference/workspace-maker-answer.md"
# Key phrases the maker itself emits (worktree_remove.py / worktree_remove_checks.py / worktree_remove_half.py).
STOPPED_WORDING = "The clearing stopped part-way and is not finished"
UNREADABLE_WORDING = "commits cannot be checked"
REPO_UNREADABLE_WORDING = "can no longer be read"
NOT_SHOWN_WORDING = "is not shown to be a workspace of this project"
FIRST_CHANGE_DATE = "2026-11-03"


def _sections(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2)
            for m in re.finditer(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S)}


def _rows(section: str) -> list[str]:
    """Data rows of the markdown tables in *section* (header and separator rows left out)."""
    lines = [line for line in section.splitlines() if line.startswith("| ")]
    return [line for line in lines if "---" not in line][1:]


def _front(text: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(\S+)\s*$", text, re.M)
    assert m, f"no {key} in frontmatter"
    return m.group(1)


class TestClearHowToStoppedAndDamaged(unittest.TestCase):
    def setUp(self):
        self.text = _read(CLEAR_DOC)

    def test_how_to_says_a_stopped_clearing_is_finished_by_asking_again_with_no_token(self):
        # covers: BO-4300e-5-ii
        # angle: criterion
        """AC-1: the stopped-part-way section says the same request is made again, that no token is
        needed, and links to the reference instead of restating answer fields."""
        body = _section(self.text, STOPPED_HEADING)
        self.assertRegex(body, r"same request", msg="section does not say to make the same request again")
        self.assertRegex(body, r"\bno token\b|\bwithout (a|any) token\b",
                         msg="section does not say a stopped clearing needs no token")
        self.assertIn(REFERENCE_LINK, body, msg="section does not link the answer reference")
        self.assertNotIn("remnant_path", self.text, msg="the how-to restates a reference field")

    def test_how_to_names_the_code_ensure_and_locate_really_emit_for_a_half_cleared_leftover(self):
        # covers: BO-4300e-5-ii
        # angle: criterion
        """AC-1: the section names HALF_CLEARED for a request for the workspace (ensure) and for the
        question where it is (locate), and tells the person to clear it again; every code the page
        names is in the maker's code table, and HALF_CLEARED is emitted by the half-cleared source."""
        body = _section(self.text, STOPPED_HEADING)
        for phrase in ("HALF_CLEARED", "ensure", "locate"):
            self.assertIn(phrase, body, msg=f"section lacks {phrase!r}")
        self.assertRegex(body, r"clear it again", msg="section does not tell the person to clear it again")
        answer_src, half_src = _read(ANSWER_SRC), _read(HALF_SRC)
        self.assertIn('"HALF_CLEARED"', answer_src, msg="HALF_CLEARED is not in the maker's code table")
        self.assertIn('"HALF_CLEARED"', half_src, msg="HALF_CLEARED is not emitted by the half-cleared source")
        for code in sorted(set(re.findall(r"`([A-Z][A-Z_]{3,})`", self.text))):
            self.assertIn(f'"{code}"', answer_src, msg=f"the how-to names {code}, which the maker never emits")

    def test_how_to_warns_that_an_unreadable_repository_means_commits_cannot_be_checked(self):
        # covers: BO-4300e-5-ii
        # angle: criterion
        """AC-1: a section says a leftover whose repository can no longer be read is refused as
        half-cleared (UNSENT_WORK), lists remaining files under unsent, says its commits cannot be
        checked, and shows the discard_token read from that refusal each time and never stored."""
        holders = [h for h, b in _sections(self.text).items() if UNREADABLE_WORDING in b]
        self.assertEqual(len(holders), 1, msg=f"sections saying {UNREADABLE_WORDING!r}: {holders}")
        body = _sections(self.text)[holders[0]]
        for phrase in ("UNSENT_WORK", "half-cleared", "unsent", "discard_token", "--discard-token", "never store",
                       REPO_UNREADABLE_WORDING):
            self.assertIn(phrase, body, msg=f"'{holders[0]}' lacks {phrase!r}")
        self.assertRegex(body, r"each time", msg="section does not say the token is read from the refusal each time")
        # the wording must be what the maker really says
        checks_src = "\n".join(_read(p) for p in REMOVE_SOURCES)
        self.assertIn(UNREADABLE_WORDING, checks_src, msg="remove never says that commits cannot be checked")
        self.assertIn(REPO_UNREADABLE_WORDING, checks_src)

    def test_how_to_states_the_narrowed_record_less_rule_without_overstating_it(self):
        # covers: BO-4300e-5-ii
        # angle: boundary
        """AC-1: the no-record section says such a folder is half-cleared only when a leftover piece of
        its repository names this project's shared project, and is otherwise refused NOT_FOUND with
        nothing changed and no token. Keeping only the old wording (always NOT_FOUND) or only the new
        one (always a token) fails."""
        body = _section(self.text, NO_RECORD_HEADING)
        for phrase in ("NOT_FOUND", "UNSENT_WORK", "half-cleared", "leftover", "shared project"):
            self.assertIn(phrase, body, msg=f"'{NO_RECORD_HEADING}' lacks {phrase!r}")
        self.assertRegex(body, r"only (when|if)", msg="rule is not stated as a narrow condition ('only when')")
        self.assertRegex(body, r"otherwise|any other|every other", msg="the other case is not stated")
        self.assertRegex(body, r"changed nothing|nothing (was|is) changed|nothing changed",
                         msg="refusal does not say nothing was changed")
        self.assertRegex(body, r"\bno token\b|offers no token|without a token", msg="NOT_FOUND case offers no token")

    def test_neither_page_publishes_a_deletion_step_that_bypasses_the_maker(self):
        # covers: BO-4300e-5-ii
        # angle: criterion
        """AC-1: no fenced block or inline command of either page matches the delete-command pattern;
        control: the new sections do show the maker's own remove request as a fenced command, so the
        scan has something to scan."""
        for path in (CLEAR_DOC, REF_DOC):
            text = _read(path)
            for block in re.findall(r"```[^\n]*\n(.*?)```", text, re.S):
                self.assertIsNone(DELETE_COMMANDS.search(block), msg=f"deletion step in {path.name}:\n{block}")
            for span in re.findall(r"`([^`\n]+)`", text):
                if re.match(r"\s*(rm|rmdir|Remove-Item|del)\s", span) or "rmtree" in span or "worktree remove" in span:
                    self.fail(f"deletion command {span!r} in {path.name}")
        body = _section(self.text, STOPPED_HEADING)
        blocks = re.findall(r"```[^\n]*\n(.*?)```", body, re.S)
        self.assertTrue(any("worktree.py remove" in b for b in blocks),
                        msg="the stopped-part-way section shows no fenced worktree.py remove request")


class TestAnswerReferenceNewAnswers(unittest.TestCase):
    def setUp(self):
        self.ref = _read(REF_DOC)
        self.refusals = _section(self.ref, "Refusals of remove")
        self.sources = "\n".join(_read(p) for p in (*REMOVE_SOURCES, ANSWER_SRC, HALF_SRC))

    def test_reference_documents_each_new_or_changed_answer_by_code_and_fields_the_maker_emits(self):
        # covers: BO-4300e-5-ii
        # angle: criterion
        """AC-1: HALF_CLEARED (ensure and locate, remnant_path, no workspace_path), the stopped-part-way
        remove refusal, the unreadable-repository refusal and the record-less half-cleared refusal are
        each documented once, by code and fields; every key phrase is found in the maker sources; both
        pages carry a last_updated of the change."""
        rows = _rows(self.refusals)
        self.assertEqual(len(rows), 8, msg="\n".join(rows))
        # HALF_CLEARED: once in the code table, with ensure/locate and remnant_path; once as a field owner.
        code_rows = [r for r in _rows(_section(self.ref, "Codes")) if r.startswith("| `HALF_CLEARED`")]
        self.assertEqual(len(code_rows), 1, msg=str(code_rows))
        for phrase in ("ensure", "locate", "remnant_path"):
            self.assertIn(phrase, code_rows[0])
        field_rows = [r for r in _rows(_section(self.ref, "Fields on a non-ok answer")) if "`remnant_path`" in r]
        self.assertEqual(len(field_rows), 1, msg=str(field_rows))
        self.assertIn("HALF_CLEARED", field_rows[0], msg="the remnant_path field row does not name HALF_CLEARED")
        # the stopped-part-way wording of the PROCESS_HOLDS_FILES refusal
        stopped = [r for r in rows if STOPPED_WORDING in r]
        self.assertEqual(len(stopped), 1, msg=str(stopped))
        self.assertIn("`PROCESS_HOLDS_FILES`", stopped[0])
        # the unreadable-repository refusal: its own row
        unreadable = [r for r in rows if UNREADABLE_WORDING in r]
        self.assertEqual(len(unreadable), 1, msg=str(unreadable))
        for phrase in ("`UNSENT_WORK`", "`unsent`", "`discard_token`", REPO_UNREADABLE_WORDING):
            self.assertIn(phrase, unreadable[0])
        # the gone-repository refusal is a different row from the unreadable one
        gone = [r for r in rows if "repository is gone" in r]
        self.assertEqual(len(gone), 1, msg=str(gone))
        self.assertNotEqual(gone[0], unreadable[0])
        # the record-less leftover that names this project's shared project: its own UNSENT_WORK row
        leftover = [r for r in rows if "`UNSENT_WORK`" in r and re.search(r"no (workspace )?record", r)
                    and "shared project" in r]
        self.assertEqual(len(leftover), 1, msg="no single record-less half-cleared row:\n" + "\n".join(rows))
        self.assertNotIn(leftover[0], (gone[0], unreadable[0]))
        self.assertIn("`discard_token`", leftover[0])
        # the plain record-less refusal quotes the maker's own words
        plain = [r for r in rows if "`NOT_FOUND`" in r]
        self.assertEqual(len(plain), 1, msg=str(plain))
        self.assertIn(NOT_SHOWN_WORDING, plain[0])
        # every phrase quoted above is one the maker sources emit
        for phrase in (STOPPED_WORDING, UNREADABLE_WORDING, REPO_UNREADABLE_WORDING, NOT_SHOWN_WORDING,
                       "is a half-cleared workspace"):
            self.assertIn(phrase, self.refusals, msg=f"reference does not quote {phrase!r}")
            self.assertIn(phrase, self.sources, msg=f"the maker never says {phrase!r}")
        self.assertIn("remnant_path=", self.sources)
        # both pages carry a last_updated of the change (the date the maker behaviour landed or later)
        for path in (CLEAR_DOC, REF_DOC):
            self.assertGreaterEqual(_front(_read(path), "last_updated"), FIRST_CHANGE_DATE, msg=path.name)


class TestDocumentedAnswersMatchRealMaker(LeftoverCase):
    def test_documented_half_cleared_answers_are_what_the_real_maker_cli_prints(self):
        # covers: BO-4300e-5-ii
        # angle: reachability
        """AC-1: the real maker CLI is run for the stopped-part-way remove refusal, the HALF_CLEARED
        ensure answer and the unreadable-repository refusal; every code, field and key phrase the
        reference documents for them is present in the printed JSON."""
        ref = _read(REF_DOC)
        refusals = _section(ref, "Refusals of remove")
        # 1. a clearing that stops part-way: the refusal of the stopped request itself
        ws = self.bulk_alpha("invoice-export")
        stopped = self.stopped_request(ws, "repo10")
        answer = stopped["answer"]
        self.assertEqual((answer.get("code"), stopped["exit_code"]), ("PROCESS_HOLDS_FILES", 2), msg=f"{stopped}")
        self.assertNotIn("holders", answer, msg=f"{answer}")
        self.assertIn(STOPPED_WORDING, answer.get("message", ""), msg=f"{answer}")
        self.assertIn(STOPPED_WORDING, refusals, msg="reference does not quote the stopped-part-way wording")
        # 2. the HALF_CLEARED ensure answer for that leftover
        res = self.ensure_cli(ws.name)
        self.assert_half_cleared(res, ws, "stopped")
        half = res["answer"]
        code_row = next((r for r in _rows(_section(ref, "Codes")) if r.startswith("| `HALF_CLEARED`")), "")
        self.assertTrue(code_row, msg="reference has no HALF_CLEARED code row")
        field_row = next((r for r in _rows(_section(ref, "Fields on a non-ok answer")) if "`remnant_path`" in r), "")
        self.assertIn("HALF_CLEARED", field_row, msg="reference does not give HALF_CLEARED its remnant_path field")
        self.assertIn("remnant_path", half, msg=f"{half}")
        self.assertIn("remnant_path", code_row)
        self.assertNotIn("workspace_path", half, msg=f"{half}")
        located = self.locate_cli(ws)["answer"]
        self.assertEqual(located.get("code"), "HALF_CLEARED", msg=f"{located}")
        # 3. the unreadable-repository refusal (record says ready, objects gone)
        unreadable = self.refusal(self.zeta("invoice-export-b"))["answer"]
        row = next((r for r in _rows(refusals) if UNREADABLE_WORDING in r), "")
        self.assertTrue(row, msg="reference has no row saying commits cannot be checked")
        self.assertIn(UNREADABLE_WORDING, unreadable.get("message", ""), msg=f"{unreadable}")
        for field in ("unsent", "discard_token"):
            self.assertIn(f"`{field}`", row)
            self.assertIn(field, unreadable, msg=f"{unreadable}")
        self.assertEqual(unreadable["unsent"]["commits"], [], msg=f"{unreadable}")
        self.assertTrue(unreadable["unsent"]["files"], msg=f"{unreadable}")


if __name__ == "__main__":
    unittest.main()
