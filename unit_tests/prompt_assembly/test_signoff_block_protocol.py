"""
Tests for the _signoff_block.md template.

Verifies that the shared sign-off protocol is self-contained and portable
in the sign-off block, per BO-2000a and its leaves.

These tests read `templates/agents/_signoff_block.md` and assert that
the required content is present. The implementation is already complete,
so all tests should be GREEN on first run; a red result indicates a
regression in the template.

Covers: BO-2000a-1, BO-2000a-1-i, BO-2000a-2, BO-2000a-2-i,
        BO-2000a-3, BO-2000a-4, BO-2000a-4-i, BO-2000a-5
"""
import os
import unittest

# Resolve the path to _signoff_block.md relative to the repo root.
# This file lives at templates/agents/_signoff_block.md.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_SIGNOFF_BLOCK_PATH = os.path.join(
    _REPO_ROOT, "templates", "agents", "_signoff_block.md"
)


def _read_signoff_block() -> str:
    """Read and return the full text of _signoff_block.md."""
    with open(_SIGNOFF_BLOCK_PATH, encoding="utf-8") as fh:
        return fh.read()


class TestSignoffBlockDualPathResolution(unittest.TestCase):
    """
    AC-1 (BO-2000a-1): dual-path skill resolution is stated in the block.
    AC-7 (BO-2000a-1-i): block instructs fail with signoff-skill-unreadable.
    """

    def test_signoff_block_dual_path_resolution(self):
        # covers: BO-2000a-1
        # covers: BO-2000a-1-i
        text = _read_signoff_block()
        self.assertIn(
            ".claude/skills/signoff/SKILL.md",
            text,
            "_signoff_block.md must mention the consumer path "
            "(.claude/skills/signoff/SKILL.md) for deployed projects.",
        )
        self.assertIn(
            "templates/skills/signoff/SKILL.md",
            text,
            "_signoff_block.md must mention the source/worktree path "
            "(templates/skills/signoff/SKILL.md) for package development.",
        )
        self.assertIn(
            "signoff-skill-unreadable",
            text,
            "_signoff_block.md must instruct the agent to fail with "
            "signoff-skill-unreadable when the skill file cannot be loaded, "
            "not proceed from memory.",
        )


class TestSignoffBlockAtomicAndHeading(unittest.TestCase):
    """
    AC-2 (BO-2000a-2): block requires the three-part atomic edit.
    AC-3 (BO-2000a-2-i): comment heading uses em-dash (U+2014), not hyphen.
    """

    def test_signoff_block_atomic_and_heading(self):
        # covers: BO-2000a-2
        # covers: BO-2000a-2-i
        text = _read_signoff_block()

        # Part (a) of atomic edit: frontmatter status
        self.assertIn(
            "agents.<your-name>: signed_off",
            text,
            "block must require the frontmatter status update "
            "(agents.<your-name>: signed_off) as part a of the atomic edit.",
        )

        # Part (b) of atomic edit: Sign-offs checkbox
        self.assertIn(
            "- [x]",
            text,
            "block must require the Sign-offs checkbox to be ticked "
            "as part b of the atomic edit.",
        )

        # Part (c) of atomic edit: Implementation-Tasks checkboxes
        self.assertIn(
            "## Implementation Tasks",
            text,
            "block must require flipping Implementation-Tasks checkboxes "
            "as part c of the atomic edit.",
        )

        # Em-dash (U+2014) separator must be specified
        em_dash = "—"
        self.assertIn(
            em_dash,
            text,
            "block must contain the em-dash character (U+2014) as the "
            "required separator in the comment heading.",
        )

        # Block must also explicitly reject the hyphen
        self.assertIn(
            "not** a hyphen",
            text,
            "block must state that the separator is an em-dash, NOT a hyphen.",
        )


class TestSignoffBlockSubmitFailedAndSelfVerify(unittest.TestCase):
    """
    AC-4 (BO-2000a-3): block carries (submit-failed) fallback.
    AC-5 (BO-2000a-4 / BO-2000a-4-i): self-verify returns signoff-write-lost.
    """

    def test_signoff_block_submit_failed_and_self_verify(self):
        # covers: BO-2000a-3
        # covers: BO-2000a-4
        # covers: BO-2000a-4-i
        text = _read_signoff_block()

        self.assertIn(
            "(submit-failed)",
            text,
            "block must contain the (submit-failed) fallback so that an "
            "unreachable feedback sink does not cause the phase to fail.",
        )

        self.assertIn(
            "signoff-write-lost",
            text,
            "block must mandate a self-verify step that returns "
            "signoff-write-lost when a sign-off write did not land on disk.",
        )


class TestSignoffBlockKnowledgeCapture(unittest.TestCase):
    """
    AC-6 (BO-2000a-5): block includes the §7 knowledge-capture step.
    """

    def test_signoff_block_knowledge_capture(self):
        # covers: BO-2000a-5
        text = _read_signoff_block()

        self.assertIn(
            "Knowledge capture",
            text,
            "block must include a 'Knowledge capture' step (BO-2000a-5).",
        )
        self.assertIn(
            "§7",
            text,
            "block must reference §7 (the knowledge-capture step "
            "from the signoff skill).",
        )


if __name__ == "__main__":
    unittest.main()
