"""
MODULE: unit_tests/commit_guardian/test_ge_127e_1_parts_and_half_length.py
COVERS: GE-127e-1 -- "The refusal accounts for what is inside the file it
    refused, and names a division of that file in terms of those same parts"

GOAL: RED test-first stubs for the first two test_spec descriptors: every
    part name the refusal prints must be locatable in the refused file's own
    content, and the named parts' portions must sum to at least half the
    measured length the refusal quotes for the whole file.

THE DEFECT THIS FILE IS RED AGAINST. templates/scripts/commit_guardian/
    check_file_size.py's ``_print_too_large_file`` prints a FIXED, two
    -sentence block identical for every refused file (a pointer to
    ``/code-refactoring-specialist`` plus a warning not to strip content) --
    confirmed in this worktree at authoring time. It performs no per-file
    content analysis whatsoever, so it prints no ``Parts:`` block at all;
    both descriptors below fail on that absence alone.

See _ge_127e_1_fixture.py's module docstring for the printed-block contract
    ("Parts:" / "Division:") these extractors assume, and for why that
    contract is specified here rather than discovered (nothing to
    reverse-engineer yet).

DECISION HISTORY
- 2026-09-14 [GE-127e-1/test-writer]: Initial authoring of two RED test
    stubs per GE-127e-1's test_spec. Verified RED via
    `AC_ENFORCE_STRICT=1 python -m pytest
    unit_tests/commit_guardian/test_ge_127e_1_parts_and_half_length.py -v`
    -- see the test-writer sign-off comment on the ticket for the exact
    captured failures.
"""

from __future__ import annotations

import sys
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_1_fixture as fx  # noqa: E402

_PARTS = [
    ("alpha_handler", 150),
    ("bravo_processor", 140),
    ("charlie_worker", 150),
]


class PartsFixtureTestCase(unittest.TestCase):
    """A repo with one covered file made of several clearly-distinguishable
    named parts, taken over its permitted length, then refused."""

    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge127e1_parts_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

        small = self.root / "multi_part.py"
        small.write_text(fx.make_part_source("placeholder", 10) + "\n", encoding="utf-8")
        fx.commit_all(self.root, "establish under-limit file")

        self.fixture_content = fx.make_multi_part_fixture(_PARTS)
        small.write_text(self.fixture_content, encoding="utf-8")
        fx.stage_all(self.root)

        self.result = fx.run_check(self.root)
        self.combined = self.result.stdout + self.result.stderr


# ---------------------------------------------------------------------------
# 1. Every named part must be locatable in the refused file's own content
# ---------------------------------------------------------------------------


class TestNamedPartsAreLocatableInTheRefusedFile(PartsFixtureTestCase):
    def test_ge_127e_1_the_refusal_names_parts_that_can_be_located_in_the_refused_file(self):
        # covers: GE-127e-1
        # angle: criterion
        """Every part name the refusal prints must be findable in the
        refused file's own bytes. Names are read out of the process output
        via `_ge_127e_1_fixture.extract_named_portions`, never compared
        against a literal this test authored.

        NAMED MUTATION (BA's injection 1, per the AC -- mutation execution
        against a real implementation is python-coder's/pr-reviewer's
        responsibility once production code exists, per this component's own
        established convention -- see test_ge_127b_1.py's module docstring):
        "the refusal accounts for that file's measured length as a set of
        named constituent parts of that same file" -- MUTATION: replace the
        per-file parts with a fixed inventory selected from the file's KIND
        alone, so every refused file of that kind is described with the same
        part names and the same portions. Under that injection the named
        parts can no longer be located in the refused file's own content;
        this assertion must go RED, and must return to green on revert.

        RED TODAY: no ``Parts:`` block is printed at all (the shipped
        refusal is the fixed two-sentence block), so zero names are
        extracted and this assertion fails on an empty result.
        """
        self.assertNotEqual(0, self.result.returncode, msg=f"Fixture sanity: must be refused. Got: {self.combined!r}")

        named = fx.extract_named_portions(self.combined)
        self.assertTrue(
            named,
            msg=(
                "The refusal must name at least one constituent part of the "
                f"refused file. Got no 'Parts:' entries in: {self.combined!r}"
            ),
        )
        for name, _portion in named:
            self.assertIn(
                name,
                self.fixture_content,
                msg=(
                    f"Named part {name!r} could not be located in the refused "
                    f"file's own content. Full output: {self.combined!r}"
                ),
            )


# ---------------------------------------------------------------------------
# 2. The named parts account for at least half the quoted length
# ---------------------------------------------------------------------------


class TestNamedPartsAccountForAtLeastHalfTheQuotedLength(PartsFixtureTestCase):
    def test_ge_127e_1_the_named_parts_account_for_at_least_half_the_quoted_length(self):
        # covers: GE-127e-1
        # angle: criterion
        """The per-part portions must sum to at least half of the measured
        length the refusal quotes for the whole file. Both numbers are read
        out of the process output -- the arithmetic is between two numbers
        the gate itself printed, never against an expected literal.

        RED TODAY: no ``Parts:`` block is printed at all, so the extracted
        portion sum is 0, which cannot reach half of any positive quoted
        length.
        """
        self.assertNotEqual(0, self.result.returncode, msg=f"Fixture sanity: must be refused. Got: {self.combined!r}")

        quoted_length, _limit = fx.extract_quoted_length_and_limit(self.combined)
        named = fx.extract_named_portions(self.combined)
        portion_sum = sum(portion for _name, portion in named)

        self.assertGreaterEqual(
            portion_sum,
            quoted_length / 2,
            msg=(
                f"Named parts' portions ({portion_sum}) must account for at "
                f"least half of the quoted measured length ({quoted_length}). "
                f"Full output: {self.combined!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
