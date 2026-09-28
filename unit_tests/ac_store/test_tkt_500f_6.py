"""
MODULE: unit_tests/ac_store/test_tkt_500f_6.py
GOAL: Tests for TKT-500f-6 — when a leaf AC's files_touched holds at least one
      qualifying implementation ``.py``, the generated ticket must carry a
      ``## Test Requirements`` section that is (a) present, (b) non-empty, and
      (c) explicit about WHICH implementation file each stub applies to. Both
      generators must produce it from one shared helper, and the section must be
      a live signal that the real downstream consumer reads.
COVERS: TKT-500f-6

RED expectation at authoring time (2026-09-14): the section IS emitted today,
but for an unrelated reason — the gate in ``_build_ticket_body`` asks whether
the COMPUTED AGENT MAP contains a production_code producer, never whether
files_touched holds a qualifying implementation ``.py``. Two consequences:

  * the presence and non-emptiness tests pass on arrival (the right answer, via
    the wrong question — an AC with only test files in files_touched gets a
    section too, which is TKT-500f-6-ii's RED);
  * every stub entry names only a DERIVED unit-test path
    (``file: unit_tests/test_<ac>.py``) and the AC id it covers. No stub names
    the implementation file in scope, so the "names the implementation file"
    test, the seam test and the consumer round-trip's file-naming assertion are
    RED.

NOTE ON PATCHING: nothing is patched — see _tkt_500f_support's ARCHITECTURE
note on the 8b2b899ae module split.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _tkt_500f_support import (  # noqa: E402
    IMPL_PY,
    consumer_reads_requirements_present,
    consumer_verdict,
    generate_dry_run,
    generate_via_goal_path,
    generate_written,
    extract_requirements_section,
    make_ac,
)


class TestTestRequirementsEmittedForImplementationPy(unittest.TestCase):
    """TKT-500f-6: a qualifying implementation .py obliges a Test Requirements section."""

    def test_qualifying_implementation_py_emits_test_requirements_section(self):
        # covers: TKT-500f-6
        # angle: criterion
        """The generated body carries a heading spelled exactly '## Test Requirements'.

        The exact spelling matters more than it looks: every downstream reader —
        the commit-guardian guard, the build-ticket planner prompt — locates the
        section by that literal heading, so a near-miss such as
        '## Test requirements' or '### Test Requirements' is invisible to all
        of them and is therefore not a section at all.
        """
        generated = generate_dry_run(
            make_ac(files_touched=[IMPL_PY]), "TKT-500f-6-present"
        )

        self.assertTrue(
            generated.has_test_requirements_heading(),
            "files_touched holds a qualifying implementation .py "
            f"({IMPL_PY}), so the ticket must carry a '## Test Requirements' "
            f"heading. files_touched={generated.frontmatter.get('files_touched')}",
        )

    def test_section_contains_at_least_one_test_stub_entry(self):
        # covers: TKT-500f-6
        # angle: criterion
        """A bare heading does not satisfy the AC — the section must carry a stub.

        The criteria require "at least one test stub entry describing a test to
        be written". An empty section satisfies the presence check above while
        leaving test-writer with nothing to write, and — because the guard reads
        the fenced block, not the heading — would still be reported as a code
        ticket missing its test requirements.
        """
        generated = generate_dry_run(
            make_ac(files_touched=[IMPL_PY]), "TKT-500f-6-non-empty"
        )
        section = extract_requirements_section(generated.text)

        self.assertIsNotNone(section, "No '## Test Requirements' section was emitted")
        self.assertTrue(
            consumer_reads_requirements_present(generated.text),
            "The section must contain at least one '- name:' stub entry. The "
            "reader used here is the production predicate from "
            "check_ticket_test_requirements.py, so 'non-empty' means what the "
            f"real consumer means by it. Section was: {section!r}",
        )

    def test_test_stub_entry_names_the_implementation_file(self):
        # covers: TKT-500f-6
        # angle: criterion
        """The stub must name the implementation file it applies to.

        This is what makes the section actionable rather than decorative: a stub
        that names only a derived unit-test path and an AC id tells test-writer
        where to put a file, not what production surface the test has to
        constrain. Today every stub names ``unit_tests/test_<ac>.py`` and the AC
        id, and no stub anywhere names the implementation file — so a ticket
        whose files_touched holds three implementation files is indistinguishable
        from one holding none.
        """
        generated = generate_dry_run(
            make_ac(files_touched=[IMPL_PY]), "TKT-500f-6-names-file"
        )
        section = extract_requirements_section(generated.text)

        self.assertIsNotNone(section, "No '## Test Requirements' section was emitted")
        self.assertIn(
            IMPL_PY,
            section,
            f"The stub entry must name {IMPL_PY!r} — the qualifying "
            "implementation file it applies to — so a downstream reader can map "
            f"the requirement to the file in scope. Section was: {section!r}",
        )


class TestBothGeneratorsAgree(unittest.TestCase):
    """TKT-500f-6: the two emission points must not drift."""

    def test_both_generators_emit_the_section_from_one_shared_helper(self):
        # covers: TKT-500f-6
        # angle: seam
        """Pipe one AC through BOTH real generators and compare the sections.

        The producing side is the direct path (``generate_ticket_from_ac.main``
        with real argv); the consuming side is the goal path
        (``epic_tickets.generate_tickets_for_leaves``), which shells out to the
        same script as a genuine subprocess with ``--location-kind
        epic_member``. Neither side is mocked, so this is the real seam rather
        than two unit tests either side of it.

        Byte-equality alone would be a weak seam assertion here, because the
        goal path currently delegates to the direct path and would agree even if
        both were wrong. So the content contract is asserted on BOTH sides
        first: each must name the implementation file. A future refactor that
        inlines the predicate into epic_tickets.py — the drift the
        it_requirements forbid — breaks the equality; an implementation that
        never names the file breaks the content assertions.
        """
        ac = make_ac(files_touched=[IMPL_PY])
        direct = generate_written(ac, "TKT-500f-6-seam")
        goal = generate_via_goal_path(ac, "TKT-500f-6-seam")

        direct_section = extract_requirements_section(direct.text)
        goal_section = extract_requirements_section(goal.text)

        self.assertIsNotNone(
            direct_section, "The direct generator emitted no Test Requirements section"
        )
        self.assertIsNotNone(
            goal_section, "The goal-path generator emitted no Test Requirements section"
        )
        self.assertIn(
            IMPL_PY,
            direct_section,
            f"The direct generator's section must name {IMPL_PY!r}. "
            f"Got: {direct_section!r}",
        )
        self.assertIn(
            IMPL_PY,
            goal_section,
            f"The goal-path generator's section must name {IMPL_PY!r}. "
            f"Got: {goal_section!r}",
        )
        self.assertEqual(
            direct_section,
            goal_section,
            "The two generators produced DIFFERENT Test Requirements sections "
            "for the same AC. The classification and emission must be reached "
            "from one shared helper; a predicate inlined in either generator "
            "drifts the moment one of them is edited.\n"
            f"direct: {direct_section!r}\ngoal:   {goal_section!r}",
        )


class TestSectionIsALiveSignal(unittest.TestCase):
    """TKT-500f-6: the emitted section must be read, not merely present."""

    def test_generated_section_is_read_by_the_real_test_writer_signal(self):
        # covers: TKT-500f-6
        # angle: real_artifact
        """Round-trip a REAL on-disk ticket through the REAL consumer.

        The bytes asserted on here were written to disk by the generator's write
        path and read back off disk — not a string this test assembled, and not
        a ``--dry-run`` capture. The reader is
        ``check_ticket_has_test_requirements`` from
        scripts/commit_guardian/check_ticket_test_requirements.py, the guard
        that actually blocks a code ticket whose Test Requirements are absent
        or empty.

        The assertion that makes this a consumption proof rather than a second
        presence check: deleting the section from that same generated artifact
        must FLIP the consumer's verdict to blocked. If the verdict is identical
        with and without the section, the section is decorative text and its
        presence signals nothing.
        """
        written = generate_written(
            make_ac(files_touched=[IMPL_PY]), "TKT-500f-6-live-signal"
        )
        self.assertIsNotNone(
            written.written_path, "The generator wrote no ticket file to disk"
        )
        # ``written.text`` was read back off disk inside generate_written's
        # temporary directory; re-reading written_path here would fail, because
        # the directory is gone by now. These are the real on-disk bytes.
        on_disk = written.text

        with_section_ok, _ = consumer_verdict(on_disk)
        self.assertTrue(
            consumer_reads_requirements_present(on_disk),
            "The real consumer must read the generated on-disk ticket as "
            "carrying populated Test Requirements. "
            f"Section was: {extract_requirements_section(on_disk)!r}",
        )
        self.assertTrue(
            with_section_ok,
            "The generated ticket must pass the Test Requirements guard as "
            "written, with no hand-editing.",
        )

        stripped = _without_test_requirements(on_disk)
        without_section_ok, reason = consumer_verdict(stripped)
        self.assertFalse(
            without_section_ok,
            "Removing the ## Test Requirements section from the generated "
            "ticket must flip the consumer's verdict to blocked. It did not, "
            "which means the consumer's decision does not depend on the "
            "section — so emitting it proves nothing about the test-writer "
            "signal.",
        )
        self.assertIn(
            "Test Requirements",
            reason,
            "The blocked verdict must name the section that is missing. "
            f"Got: {reason!r}",
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
- 2026-09-14 [TKT-500f-6/test-writer]: Initial tests from the AC's five
  test_spec descriptors. The seam test asserts the content contract on BOTH
  sides before asserting equality, because the goal path currently delegates to
  the direct path via subprocess and so agrees trivially — equality alone would
  be green on arrival and would prove nothing. The real_artifact test asserts a
  VERDICT FLIP rather than a second presence check, for the same reason: a
  consumer whose answer is unchanged by removing the section is not consuming it.
====================================================================
"""
