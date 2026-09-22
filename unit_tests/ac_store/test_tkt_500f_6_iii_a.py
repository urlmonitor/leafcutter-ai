"""
MODULE: unit_tests/ac_store/test_tkt_500f_6_iii_a.py
GOAL: Tests for TKT-500f-6-iii-a — the generator side of the test-writer signal.
      The presence or absence of ``## Test Requirements`` in a generated ticket
      must be a RELIABLE signal (present iff at least one qualifying
      implementation ``.py`` is in files_touched) that a real consumer reads to
      decide whether the test-writer phase is required; and the qualifying-.py
      predicate must live in exactly ONE shared helper rather than being inlined
      in either generator.
COVERS: TKT-500f-6-iii-a

The consumer used below is
``scripts/commit_guardian/check_ticket_test_requirements.py`` — the guard that
actually blocks a code ticket whose Test Requirements are absent or empty. The
AC's ``delivers_to`` also names the ticket-supervisor template, but that surface
is markdown prose and, per the AC's own third it_requirement, is reconciled by
SPEC PARITY rather than by code — there is nothing there for a Python test to
invoke, so it is deliberately out of scope here.

RED expectation at authoring time (2026-09-14): the signal is not reliable in
either direction. The section is gated on whether the computed agent map holds a
production_code producer, so an AC whose files_touched is only docs/.yaml/.json/
tickets paths still receives one. The predicate does not exist anywhere: an AST
scan of every function under scripts/ for one that mentions ``_test.py``,
``test_`` and ``tickets`` together returns zero matches. Three of the four tests
are RED; the failure-angle test is green on arrival and is a forward guard (see
its docstring).

NOTE ON PATCHING: nothing is patched — see _tkt_500f_support's ARCHITECTURE
note on the 8b2b899ae module split.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _tkt_500f_support import (  # noqa: E402
    CONFIG_JSON,
    DOCS_MD,
    IMPL_PY,
    REPO_ROOT,
    consumer_reads_requirements_present,
    consumer_verdict,
    generate_dry_run,
    generate_for_absent_ac,
    generate_written,
    make_ac,
    predicate_owning_functions,
    extract_requirements_section,
)

#: The AC's second Given: docs, .yaml, .json and tickets-path files only.
_NO_IMPLEMENTATION_PY = [
    DOCS_MD,
    CONFIG_JSON,
    "config/guardrail_gates.yaml",
    "tickets/00_inbox/notes.md",
]

#: Sections every generated ticket carries regardless of the signal, used to
#: tell a deliberate omission from a truncated artifact.
_STRUCTURAL_SECTIONS = ("## Acceptance Criteria", "## Sign-offs", "## Comments")


class TestSectionPresenceIsTheSignal(unittest.TestCase):
    """TKT-500f-6-iii-a: presence means 'test-writer required', and is consumed."""

    def test_section_presence_is_the_signal_that_test_writer_is_required(self):
        # covers: TKT-500f-6-iii-a
        # angle: criterion
        """An implementation .py yields a section AND the consumer answers 'required'.

        Asserting the heading alone would only prove the text is there. What the
        AC claims is stronger — that the presence IS the authoritative signal —
        so the decision is asserted too: the real guard must read the generated
        ticket as carrying populated Test Requirements and must pass it.

        The omitted-ticket contrast is the part that makes this a decision test.
        The SAME generated artifact, with only that section removed, must be
        read as 'not populated'. If both readings agree, the consumer is not
        looking at the section and emitting it signals nothing to anyone.
        """
        generated = generate_dry_run(
            make_ac(files_touched=[IMPL_PY]), "TKT-500f-6-iii-a-required"
        )

        self.assertTrue(
            generated.has_test_requirements_heading(),
            "An AC with a qualifying implementation .py must generate a ticket "
            "carrying '## Test Requirements'. files_touched="
            f"{generated.frontmatter.get('files_touched')}",
        )
        self.assertTrue(
            consumer_reads_requirements_present(generated.text),
            "The real consumer must read this ticket as 'test-writer required'. "
            f"Section was: {extract_requirements_section(generated.text)!r}",
        )

        ok, _ = consumer_verdict(generated.text)
        self.assertTrue(
            ok,
            "A code ticket carrying the section must pass the Test "
            "Requirements guard as generated, with no hand-editing.",
        )
        self.assertFalse(
            consumer_reads_requirements_present(
                _without_test_requirements(generated.text)
            ),
            "Removing only the ## Test Requirements section from this same "
            "artifact must flip the consumer's reading. It did not, so the "
            "consumer's answer does not depend on the section and its presence "
            "is not a signal.",
        )

    def test_section_absence_is_the_signal_that_a_skip_is_legitimate(self):
        # covers: TKT-500f-6-iii-a
        # angle: criterion
        """Docs/.yaml/.json/tickets-only files_touched yields no section, read as 'skip'.

        The AC's second Given. Absence has to MEAN something for a skip to be
        legitimate, and it can only mean something if it is reliable: today the
        section is emitted for this fixture too, so an absent section carries no
        information and a downstream reader cannot distinguish "no tests needed"
        from "the generator declined to say".

        The consumer's reading is asserted alongside the heading, so an
        implementation that omits the heading while leaving some other
        Test-Requirements-shaped block in the body does not pass.
        """
        generated = generate_dry_run(
            make_ac(files_touched=_NO_IMPLEMENTATION_PY),
            "TKT-500f-6-iii-a-skip",
        )

        self.assertFalse(
            generated.has_test_requirements_heading(),
            "files_touched holds no implementation .py — only docs, .yaml, "
            ".json and a tickets/ path — so the ticket must carry no "
            "'## Test Requirements' section, and that absence is what makes a "
            "test-writer skip legitimate rather than an oversight. Section "
            f"emitted was: {extract_requirements_section(generated.text)!r}",
        )
        self.assertFalse(
            consumer_reads_requirements_present(generated.text),
            "The real consumer must read this ticket as carrying no test "
            "requirements. Got a populated reading from: "
            f"{extract_requirements_section(generated.text)!r}",
        )


class TestSinglePredicateOwner(unittest.TestCase):
    """TKT-500f-6-iii-a: one helper owns the qualifying-.py predicate."""

    def test_shared_classification_helper_is_the_single_owner_of_the_predicate(self):
        # covers: TKT-500f-6-iii-a
        # angle: seam
        """Exactly one function under scripts/ may implement the predicate.

        The seam is generate_ticket_from_ac.py (direct path) against
        epic_tickets.py (goal path). Both must reach the SAME predicate, and the
        it_requirements forbid inlining or duplicating it in either. A duplicated
        predicate fails this test even while both generators produce correct
        output today — which is the whole point: duplication is not a bug yet,
        it is the mechanism by which the next edit becomes one.

        Discovery is by AST fingerprint rather than by a hard-coded module path,
        so the implementer is free to choose where the helper lives. A function
        that mentions the ``*_test.py`` suffix rule, the ``test_`` prefix rule
        and the ``tickets`` path rule together IS this predicate; nothing else
        under scripts/ has a reason to mention all three (the scan returns zero
        matches today, which is why this test is currently RED for absence
        rather than for duplication).
        """
        owners = predicate_owning_functions()

        self.assertEqual(
            len(owners),
            1,
            "Exactly one function under scripts/ may implement the "
            "qualifying-implementation-.py predicate.\n"
            "  0 matches  -> the shared classification helper has not been "
            "written; the generators are still deciding by some other means.\n"
            "  2+ matches -> the predicate has been duplicated or inlined, "
            "which is exactly the drift TKT-500f-6's it_requirements forbid: "
            "the two generators will agree until the day one of them is "
            "edited.\n"
            f"Found {len(owners)}: {owners}",
        )

        owner_module = owners[0].split("::", 1)[0]
        generator_source = (
            REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
        ).read_text(encoding="utf-8")
        owner_stem = owner_module.rsplit("/", 1)[-1].removesuffix(".py")
        self.assertTrue(
            owner_stem == "generate_ticket_from_ac" or owner_stem in generator_source,
            "The direct generator must reach the shared helper — either by "
            f"owning it or by importing {owner_stem!r}. The predicate lives in "
            f"{owner_module!r} and generate_ticket_from_ac.py never mentions "
            "it, so the two cannot be the same code.",
        )


class TestAbsenceIsDeliberate(unittest.TestCase):
    """TKT-500f-6-iii-a: a legitimate omission must not look like a failed run."""

    def test_absent_section_is_distinguishable_from_an_ungenerated_ticket(self):
        # covers: TKT-500f-6-iii-a
        # angle: failure
        """'Deliberately omitted' must be observably different from 'never produced'.

        This is the phantom-done risk the AC guards: a skip signal is only safe
        if a reader can tell it apart from a generation that fell over. So the
        docs-only run must leave behind a complete, well-formed artifact —
        written to disk, with parseable frontmatter naming the source AC and
        every other structural section intact — while a run against an AC id
        that does not exist must leave NO artifact at all.

        Green on arrival: nothing today omits the section for this fixture, so
        the "complete artifact" half is trivially satisfied and the contrast
        half already holds. Its value is forward-looking — the obvious way to
        implement the omission is an early return, and an early return placed
        one line too high produces exactly the truncated ticket this test
        refuses.
        """
        written = generate_written(
            make_ac(files_touched=_NO_IMPLEMENTATION_PY),
            "TKT-500f-6-iii-a-deliberate",
        )

        self.assertIsNotNone(
            written.written_path,
            "A ticket whose Test Requirements are legitimately omitted must "
            "still be WRITTEN. No file on disk is indistinguishable from a "
            "generation that failed.",
        )
        self.assertIn(
            written.exit_code,
            (0, None),
            f"The omission must not be reported as a failure. Exit code: "
            f"{written.exit_code!r}",
        )
        self.assertTrue(
            written.frontmatter,
            "The written ticket must have parseable frontmatter — a truncated "
            f"artifact is a failed generation. Got: {written.text[:400]!r}",
        )
        for section in _STRUCTURAL_SECTIONS:
            self.assertIn(
                section,
                written.text,
                f"A deliberately section-less ticket must still carry "
                f"{section!r}. Its absence means generation stopped early "
                "rather than skipping one block.",
            )

        failed = generate_for_absent_ac("TKT-500f-6-iii-a-no-such-ac")
        self.assertIsNone(
            failed.written_path,
            "Contrast arm: a generation against an AC that does not exist must "
            "write no ticket. If it writes one, the two states this test is "
            "trying to tell apart are not distinguishable by artifact presence "
            "and the skip signal is unsafe for a different reason.",
        )
        self.assertNotEqual(
            written.written_path is None,
            failed.written_path is None,
            "A deliberately section-less ticket and a failed generation must "
            "be distinguishable: the first leaves a complete artifact on disk, "
            "the second leaves none.",
        )


def _without_test_requirements(ticket_text: str) -> str:
    """Return *ticket_text* with its ``## Test Requirements`` section removed.

    Args:
        ticket_text: Full ticket markdown.

    Returns:
        str: The same ticket with that one section's heading and body dropped
        and every other section left byte-identical.
    """
    kept: list[str] = []
    skipping = False
    for line in ticket_text.splitlines():
        if line.strip().startswith("## "):
            skipping = line.strip() == "## Test Requirements"
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-6-iii-a/test-writer]: Initial tests from the AC's four
  test_spec descriptors. The seam test discovers the shared helper by AST
  fingerprint instead of asserting a module path, so it constrains the
  single-owner property the it_requirements actually state without dictating
  where the implementer puts the function or what signature it takes. The
  delivers_to target named in the AC is the ticket-supervisor markdown template,
  which by the AC's own third it_requirement is reconciled by spec parity rather
  than code; the code-side consumer exercised here is the commit-guardian guard.
====================================================================
"""
