"""
MODULE: unit_tests/ac_store/test_tkt_500f_6_i.py
GOAL: Tests for TKT-500f-6-i — a files_touched list mixing ONE implementation
      ``.py`` with a documentation file and a configuration file still obliges
      the generated ticket to carry ``## Test Requirements``, with a stub naming
      that one qualifying path. The classification is a logical OR over entries,
      never a unanimity check.
COVERS: TKT-500f-6-i

Fixture files_touched (copied verbatim from the AC's Gherkin):

    scripts/ac_store/generate_ticket_from_ac.py   <- the one qualifying entry
    docs/reference/ac-schema.md                   <- documentation
    config/agent_registry.json                    <- configuration

RED expectation at authoring time (2026-09-14): the section is emitted for this
fixture today, but on the agent-map gate rather than on any files_touched
classification, so the presence half is green on arrival. The stub-naming half
is RED — no stub names any implementation file (see test_tkt_500f_6.py's module
docstring). The any-vs-all test is RED on the same naming clause while its
structural half is green; its value is forward-looking and is spelled out in
its own docstring.

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
    consumer_reads_requirements_present,
    generate_dry_run,
    make_ac,
    extract_requirements_section,
)

#: The AC's mixed list, in the order the Gherkin states it.
_MIXED = [IMPL_PY, DOCS_MD, CONFIG_JSON]


class TestMixedFilesTouchedStillRequiresTestRequirements(unittest.TestCase):
    """TKT-500f-6-i: docs and config alongside one .py do not change the answer."""

    def test_mixed_impl_docs_config_set_still_emits_test_requirements(self):
        # covers: TKT-500f-6-i
        # angle: criterion
        """One qualifying .py among three paths is enough to oblige the section.

        The generated ticket must carry the heading AND a populated section —
        populated as the real commit-guardian predicate defines it, so "emitted"
        cannot be satisfied by a heading with nothing under it.
        """
        generated = generate_dry_run(make_ac(files_touched=_MIXED), "TKT-500f-6-i-mixed")

        self.assertEqual(
            sorted(generated.frontmatter.get("files_touched") or []),
            sorted(_MIXED),
            "Fixture guard: the generated ticket must carry exactly the mixed "
            "three-path files_touched the AC describes, otherwise this test is "
            "not exercising the case it claims to.",
        )
        self.assertTrue(
            generated.has_test_requirements_heading(),
            "One qualifying implementation .py among three paths must still "
            f"produce a '## Test Requirements' heading. files_touched={_MIXED}",
        )
        self.assertTrue(
            consumer_reads_requirements_present(generated.text),
            "The section must be populated, not a bare heading. Section was: "
            f"{extract_requirements_section(generated.text)!r}",
        )

    def test_mixed_set_stub_entry_names_the_single_implementation_file(self):
        # covers: TKT-500f-6-i
        # angle: criterion
        """The stub must name the one qualifying path — and only that one.

        Of the three entries only ``generate_ticket_from_ac.py`` qualifies, so
        the section must name it. It must NOT raise a stub against the
        documentation or configuration file: doing so would send test-writer off
        to write a test for a markdown file, and would mean the stub set is a
        copy of files_touched rather than the output of a classification.
        """
        generated = generate_dry_run(
            make_ac(files_touched=_MIXED), "TKT-500f-6-i-stub-names"
        )
        section = extract_requirements_section(generated.text)

        self.assertIsNotNone(section, "No '## Test Requirements' section was emitted")
        self.assertIn(
            IMPL_PY,
            section,
            f"The section must carry a stub entry for {IMPL_PY!r} — the one "
            f"qualifying path among the three. Section was: {section!r}",
        )
        for non_qualifying in (DOCS_MD, CONFIG_JSON):
            self.assertNotIn(
                non_qualifying,
                section,
                f"{non_qualifying!r} is not an implementation .py and must not "
                "receive a test stub. Its presence means the stub set is being "
                "copied from files_touched rather than classified. "
                f"Section was: {section!r}",
            )


class TestAnyVersusAllBoundary(unittest.TestCase):
    """TKT-500f-6-i: the discriminating case — ANY qualifying entry, not ALL."""

    def test_docs_and_config_paths_do_not_suppress_the_section(self):
        # covers: TKT-500f-6-i
        # angle: boundary
        """The single-file case and the mixed case must give the SAME answer.

        This is the any-vs-all boundary, and it is written as a comparison
        rather than as a second presence check on purpose. An implementation
        that requires EVERY files_touched entry to qualify — the natural reading
        of "a docs/config-only ticket needs no tests", and a one-character
        difference in code (``all(...)`` where ``any(...)`` was meant) — passes
        TKT-500f-6's single-file case, passes TKT-500f-6-ii's all-excluded case,
        and fails ONLY here.

        Both halves are asserted against each other: the section must be present
        in both, and the set of implementation files the section names must be
        identical in both. The second half is what stops a partial
        implementation from emitting a section for the mixed case whose content
        has been degraded by the two non-qualifying neighbours.
        """
        single = generate_dry_run(
            make_ac(files_touched=[IMPL_PY]), "TKT-500f-6-i-boundary-single"
        )
        mixed = generate_dry_run(
            make_ac(files_touched=_MIXED), "TKT-500f-6-i-boundary-mixed"
        )

        self.assertTrue(
            single.has_test_requirements_heading(),
            "Control arm: the single-file case must emit the section. If this "
            "fails the comparison below is meaningless — fix TKT-500f-6 first.",
        )
        self.assertTrue(
            mixed.has_test_requirements_heading(),
            "Adding docs/reference/ac-schema.md and config/agent_registry.json "
            "alongside a qualifying implementation .py must NOT suppress the "
            "section. Suppression here is the signature of an ALL-must-qualify "
            "predicate where the AC requires ANY: the docs and config entries "
            "are extra work in the same ticket, not a statement that the .py "
            "needs no tests.",
        )

        single_section = extract_requirements_section(single.text) or ""
        mixed_section = extract_requirements_section(mixed.text) or ""
        self.assertEqual(
            IMPL_PY in single_section,
            IMPL_PY in mixed_section,
            "The implementation file named by the section must not depend on "
            "which non-qualifying paths happen to accompany it. "
            f"single={single_section!r}\nmixed={mixed_section!r}",
        )
        self.assertIn(
            IMPL_PY,
            mixed_section,
            f"The mixed case must still name {IMPL_PY!r}. Section was: "
            f"{mixed_section!r}",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-6-i/test-writer]: Initial tests from the AC's three
  test_spec descriptors. The boundary test compares the single-file arm against
  the mixed arm in ONE test rather than asserting the mixed arm alone, because
  an all-must-qualify implementation is only visible as a DIFFERENCE between the
  two — asserted alone, the mixed arm is indistinguishable from a restatement of
  TKT-500f-6's first descriptor. The stub-naming test also asserts the
  non-qualifying paths are ABSENT from the section, which is what separates a
  real classification from a files_touched copy.
====================================================================
"""
