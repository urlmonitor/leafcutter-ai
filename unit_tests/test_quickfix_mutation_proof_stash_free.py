"""
unit_tests/test_quickfix_mutation_proof_stash_free.py

Content-guard tests for BP-600c-3-ii: the /quick-fix mutation proof must
revert and restore the fix WITHOUT using the shared git stash stack.

Background
----------
The mutation proof (BP-600c-3) reverts the fix, confirms the test goes red,
then restores the fix and confirms green.  Both copies of that instruction --
the skill prose at ``templates/skills/quick-fix/SKILL.md`` Step 4.2 and the
agent prompt inside ``templates/workflows-js/quick-fix.js`` -- prescribed
``git stash push -- <file>`` followed by an unqualified ``git stash pop``.

The stash stack is shared by every session and every agent working in the same
repository.  An unqualified ``git stash pop`` pops whatever entry is on TOP of
that stack, which is not necessarily the entry the popper pushed.  Followed
verbatim while a concurrent session held a stash entry, the recipe destroyed
that session's uncommitted work.

The stash-free mechanism: save the fixed copy outside the repo, materialise
the HEAD content into a second temp file, copy that over the target to revert,
copy the saved fix back to restore, and prove the restore by byte-comparison.

These tests MUST FAIL (red) until both artifacts drop the stash commands from
their mutation-proof sections.
"""
# @ac-tag: BP-600c-3-ii

import os
import re
import unittest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_SKILL_MD = os.path.join(
    _REPO_ROOT, "templates", "skills", "quick-fix", "SKILL.md"
)
_WORKFLOW_JS = os.path.join(
    _REPO_ROOT, "templates", "workflows-js", "quick-fix.js"
)

# Any reference to the stash stack: `git stash`, `git -C <x> stash`.  Matches
# prose as well as commands, so it is only ever applied to text already narrowed
# down to commands -- a prohibition ("do not use git stash") contains the same
# characters as the prescription it replaced.
_STASH_MENTION = re.compile(r"git\s+(?:-C\s+\S+\s+)?stash")

# The stash stack actually being *operated on*: a subcommand follows.  Safe to
# apply to mixed prose+command text.
_STASH_OPERATION = re.compile(
    r"git\s+(?:-C\s+\S+\s+)?stash\s+(?:push|pop|save|apply|list|drop|branch|clear)"
)

# The revert half of the stash-free mechanism reads the pre-fix content out of
# HEAD rather than pushing the fix onto a stack.
_SHOW_FROM_HEAD = re.compile(r"git\s+(?:-C\s+\S+\s+)?show\s+\"?HEAD:")

# A ```bash fenced block in a markdown file.
_BASH_FENCE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise AssertionError(f"Could not read {path}: {exc}") from exc


def _slice_between(text: str, start_pattern: str, end_pattern: str, what: str) -> str:
    """Return the text between the first match of start_pattern and the first
    match of end_pattern that follows it.

    Raises AssertionError when either anchor is missing -- a structural change
    to the artifact that needs looking at rather than silently passing.
    """
    start = re.search(start_pattern, text, re.MULTILINE)
    if start is None:
        raise AssertionError(
            f"Could not locate the start of the {what} section "
            f"(pattern {start_pattern!r}). The artifact may have been restructured."
        )
    rest = text[start.end():]
    end = re.search(end_pattern, rest, re.MULTILINE)
    if end is None:
        raise AssertionError(
            f"Could not locate the end of the {what} section "
            f"(pattern {end_pattern!r}). The artifact may have been restructured."
        )
    return rest[: end.start()]


class TestQuickFixSkillMutationProofStashFree(unittest.TestCase):
    """SKILL.md Step 4.2 must not prescribe the shared stash stack."""

    @classmethod
    def setUpClass(cls):
        cls.full = _read(_SKILL_MD)
        cls.step_4_2 = _slice_between(
            cls.full,
            r"^###\s+Step\s+4\.2\b",
            r"^##\s+Phase\s+5\b",
            "SKILL.md Step 4.2 mutation proof",
        )
        cls.guard = _slice_between(
            cls.full,
            r"^###\s+Guard\s+BP-600a-3\b",
            r"^##\s+Phase\s+1\b",
            "SKILL.md Guard BP-600a-3 uncommitted-changes",
        )

    def test_ac_bp600c3ii_skill_step_4_2_uses_no_stash_command(self):
        # covers: BP-600c-3-ii
        """Step 4.2's runnable commands must contain no `git stash`.

        `git stash pop` with no argument pops the top of a stack shared with
        every other session in the repo.  Replace the pair with: save the fixed
        copy outside the repo, write HEAD's content over the target to revert,
        copy the saved fix back to restore.

        Only the ```bash fenced blocks are scanned.  The surrounding prose is
        where the prohibition itself is written, and it has to name the command
        it forbids.
        """
        commands = "\n".join(_BASH_FENCE.findall(self.step_4_2))
        self.assertTrue(
            commands.strip(),
            msg=(
                f"No ```bash fenced blocks found under Step 4.2 in {_SKILL_MD}. "
                "The mutation proof has no runnable commands left to check, so "
                "this assertion would pass vacuously (BP-600c-3-ii)."
            ),
        )
        found = _STASH_MENTION.findall(commands)
        self.assertEqual(
            found,
            [],
            msg=(
                "templates/skills/quick-fix/SKILL.md Step 4.2 still prescribes "
                f"the shared stash stack ({found!r}). An unqualified `git stash "
                "pop` pops whatever entry is on top of the stack, which may "
                "belong to a concurrent session -- following this recipe has "
                "already destroyed another session's uncommitted work. "
                "Revert via a saved copy plus HEAD content instead (BP-600c-3-ii)."
            ),
        )

    def test_ac_bp600c3ii_skill_step_4_2_reverts_from_head(self):
        # covers: BP-600c-3-ii
        """Step 4.2 must revert by reading the pre-fix content out of HEAD.

        Guards against the stash commands merely being deleted: the proof still
        has to revert the fix, just by a mechanism that touches no shared state.
        """
        self.assertRegex(
            self.step_4_2,
            _SHOW_FROM_HEAD,
            msg=(
                "templates/skills/quick-fix/SKILL.md Step 4.2 no longer uses the "
                "stash, but neither does it read the pre-fix content out of HEAD "
                "(`git -C <root> show HEAD:<path>`). The mutation proof must still "
                "revert the fix -- removing the revert entirely would make the "
                "proof vacuous (BP-600c-3-ii)."
            ),
        )

    def test_ac_bp600c3ii_skill_guard_advises_labelled_stash(self):
        # covers: BP-600c-3-ii
        """The uncommitted-changes guard must not advise a bare `git stash`.

        This block is advice to a human rather than an agent command, but the
        hazard is identical: an unlabelled entry cannot be told apart from a
        concurrent session's when it is popped back.

        Every stash *operation* it offers must be qualified -- pushed with a
        `-m` label, listing the stack, or popping an explicit `stash@{n}` ref.
        An operation with none of those is popping the top of a shared stack
        blind.
        """
        qualified = ("-m", "stash list", "stash@{")
        # Command lines only -- a line starting with `git `.  Prose that names
        # the forbidden command in order to forbid it is not an offer of it.
        # `git -C <root> stash` with no subcommand at all (the shape the old
        # text offered) counts as unqualified too, hence _STASH_MENTION rather
        # than _STASH_OPERATION.
        bare = [
            line.strip()
            for line in self.guard.splitlines()
            if line.strip().startswith("git ")
            and _STASH_MENTION.search(line)
            and not any(marker in line for marker in qualified)
        ]
        self.assertEqual(
            bare,
            [],
            msg=(
                "The Guard BP-600a-3 block in templates/skills/quick-fix/SKILL.md "
                f"advises an unlabelled stash command ({bare!r}). Advise "
                "`git stash push -m \"<label>\"` and popping by the entry's own "
                "ref located via `git stash list` (BP-600c-3-ii)."
            ),
        )


class TestQuickFixWorkflowMutationProofStashFree(unittest.TestCase):
    """No path through quick-fix.js may operate the shared git stash stack.

    Originally scoped to just the mutation-proof block via `_slice_between`,
    because at the time that was the only place the file still needed
    checking -- other sections legitimately used `git stash` too. That is no
    longer true: the whole file should be stash-free. The region anchor was
    REMOVED rather than kept as an apparent belt-and-suspenders, because an
    anchor on a literal like `halt_reason: 'mutation_proof_failed'` couples
    the test to the source's physical layout -- a same-behaviour refactor
    that moves that literal from an object key into a function argument (a
    shared helper for the two mutation-proof failure returns) broke this
    test even though nothing about the prompt or its stash-freedom changed.
    Do not reintroduce region-slicing here; it reads like tightening the
    guard but it narrows what gets checked and re-couples the test to
    wherever the halt_reason literal happens to sit today.

    Whole-file scope makes this guard STRONGER, not weaker: it now also
    catches a stash operation introduced anywhere else in the workflow, not
    only inside the mutation-proof section.
    """

    @classmethod
    def setUpClass(cls):
        cls.full = _read(_WORKFLOW_JS)

    def test_ac_bp600c3ii_workflow_uses_no_stash_command_anywhere(self):
        # covers: BP-600c-3-ii
        """No stash *operation* may appear anywhere in quick-fix.js.

        Matched on stash *operations* (`push`/`pop`/`list`/...), so the file
        can still spell out the prohibition ("DO NOT USE git stash...") in
        prose without tripping its own guard -- `_STASH_OPERATION` requires a
        subcommand, unlike the bare `_STASH_MENTION`.
        """
        found = _STASH_OPERATION.findall(self.full)
        self.assertEqual(
            found,
            [],
            msg=(
                "templates/workflows-js/quick-fix.js instructs some agent to "
                f"use the shared stash stack ({found!r}). This is the executing "
                "copy of the Step 4.2 recipe -- correcting the skill prose "
                "alone leaves the workflow path unchanged (BP-600c-3-ii)."
            ),
        )

    def test_ac_bp600c3ii_workflow_mutation_prompt_reverts_from_head(self):
        # covers: BP-600c-3-ii
        """The mutation-proof prompt must still revert, by reading HEAD's content."""
        self.assertRegex(
            self.full,
            _SHOW_FROM_HEAD,
            msg=(
                "templates/workflows-js/quick-fix.js no longer instructs the "
                "mutation-proof agent to revert the fix from HEAD "
                "(`git -C <root> show HEAD:<path>`). Dropping the revert makes "
                "the proof vacuous rather than safe (BP-600c-3-ii)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
