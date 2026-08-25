"""
MODULE: unit_tests/commit_guardian/test_bo_2900g_2_ii.py
COVERS: BO-2900g-2-ii

GOAL: the durable-effect derivation must key on the OBJECT written, not on the
verb. A write to a stream, a reported clause whose subject is a document, and a
relative clause merely naming where something lives must all derive False, while
a file or record that outlives the run still derives True.

Every non-durable phrase below is lifted VERBATIM from a real record that the
pre-BO-2900g-2-ii pattern marked. Invented examples are how the original pattern
came to accept a bare "is written": the author pictured "a file is written" and
the expression also accepted "the file suppressions are written in".
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "commit_guardian"))

from _ac_schema_validators import (  # noqa: E402
    derive_declares_side_effect,
    validate_declares_side_effect,
)


def _record(criteria: str, **extra: object) -> dict[str, object]:
    """Build a minimal AC-shaped dict carrying the given criteria text."""
    return {"id": "ZZ-2900g-2-ii-fixture", "criteria": criteria, **extra}


class TestTheObjectDecidesNotTheVerb:
    def test_bo_2900g_2_ii_stream_writes_and_described_writes_do_not_derive_true(self) -> None:
        # covers: BO-2900g-2-ii
        """The three non-durable shapes derive False; a real file still derives True."""
        # (1) A stream write — observable, but gone when the terminal closes.
        #     Verbatim from GE-125d-1.
        stream = _record(
            "Then a notice is written to the error stream that names the check,\n"
            "  states that 3 findings were withheld from the report across 2 files,\n"
        )
        assert derive_declares_side_effect(stream) is False

        # (2) A REPORTED clause: the subject is a document, and the write it
        #     describes belongs to a different AC. Verbatim from GE-123d-4-ii.
        reported = _record(
            "Then the reference states that a notice naming the file, the 1-based\n"
            "  line number and the granting shape is written to the error stream,\n"
        )
        assert derive_declares_side_effect(reported) is False

        # (3) A relative clause naming a location. No write is asserted at all.
        #     Verbatim from GE-123c-4.
        location = _record(
            "Then they find a section on suppressing a finding that names the file\n"
            "  suppressions are written in, describes an entry as three parts,\n"
        )
        assert derive_declares_side_effect(location) is False

        # (4) The shape that must survive: a file that outlives the run.
        #     Verbatim from BP-1500d-1.
        durable = _record(
            "Then a record file is written into that project's own tree, so that\n"
            "  project holds its own record of what the build put there,\n"
        )
        assert derive_declares_side_effect(durable) is True

    def test_bo_2900g_2_ii_authoring_verbs_are_not_side_effects(self) -> None:
        # covers: BO-2900g-2-ii
        """"before any test is written" is a person writing a test later.

        Verbatim from BO-2600b-2 and BP-900h-4-i — two records that carried a
        true declaration purely on these phrases.
        """
        for phrase in (
            "Then that statement appears in the record before any test is written\n"
            "  and before any production code is changed,\n",
            "Then an adopter who names the directory something other than the one\n"
            "  name the current lookup is written against is not a broken install,\n",
            "Then a hand-maintained manifest does not satisfy this criterion even\n"
            "  when it happens to be complete on the day it is written,\n",
        ):
            assert derive_declares_side_effect(_record(phrase)) is False, phrase


class TestAnAuthorWhoIsRightCanRecordIt:
    def test_bo_2900g_2_ii_an_author_who_is_right_can_record_it(self) -> None:
        # covers: BO-2900g-2-ii
        """A non-durable record may author False and be ACCEPTED.

        This must pass because the derivation AGREES, not because validation
        became permissive — so the paired assertion below checks that a genuinely
        durable record authoring False is still rejected. A fix that added an
        override flag would satisfy the first assertion and fail the second.
        """
        honest_false = _record(
            "Then a notice is written to the error stream naming the allowlist file,\n",
            declares_side_effect=False,
        )
        assert validate_declares_side_effect(Path("x.yaml"), honest_false) == []

        # The escape-hatch guard: permissiveness would let this through too.
        dishonest_false = _record(
            "Then a record file is written into that project's own tree,\n",
            declares_side_effect=False,
        )
        assert validate_declares_side_effect(Path("x.yaml"), dishonest_false) != []


class TestKnownDeferredOverMatch:
    def test_bo_2900g_2_ii_later_scenario_over_match_is_pinned_as_known(self) -> None:
        # covers: BO-2900g-2-ii
        """CHARACTERISATION of a defect this change deliberately did NOT fix.

        The search runs from the first ``Then`` to the END of the criteria, so a
        durable phrase in a LATER scenario's Given still counts. Bounding each
        scenario was measured and reverted: it moves BO-2400c-1-v, UXP-612 and
        UXP-614 into disagreement, and the latter two genuinely produce a file
        and only say so in a ``When``.

        When someone does bound the scenarios, this test fails — which is the
        point. Update it together with those three records, not on its own.
        """
        multi_scenario = _record(
            "Then the value is handed back to the caller.\n"
            "\n"
            "Given a record file is written into the project tree,\n"
            "When the reader looks,\n"
            "Then the reader sees it.\n"
        )
        assert derive_declares_side_effect(multi_scenario) is True, (
            "Expected the KNOWN over-match. If this now returns False the scenario "
            "boundary has been implemented — reconcile BO-2400c-1-v, UXP-612 and "
            "UXP-614 in the same change and rewrite this test."
        )
