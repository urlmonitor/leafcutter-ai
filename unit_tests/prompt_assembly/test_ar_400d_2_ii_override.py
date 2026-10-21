"""AR-400d-2-ii -- a misspelt UNMARKED package grant is not rescued by a same-named project ability,
while a ``provided_by: project`` grant to a PACKAGED id is a deliberate, announced override that the
build never overwrites or deletes (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400d-2-ii.yaml (decisions 5 and 10). Real ``build.py`` runs over a copied package inside a scratch
consumer project (see ``_ar400_3b_fixtures``); read-only tests share a cached build, the rebuilding
test takes a private copy. The packaged signoff description is read from the real SKILL.md.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3b_fixtures as G  # noqa: E402
from _ar_300ad_support import skill_description  # noqa: E402

PACKAGED_SIGNOFF = skill_description(F.REPO_ROOT / "templates" / "skills" / "signoff" / "SKILL.md")
OVERRIDE_INFO = r"in place of|instead of|overrid"
FALLBACK_INFO = r"does not supply|not supply|packaged copy"


def _row_description_has(text: str, marker: str) -> bool:
    rows = G.ability_rows(text, "signoff")
    return len(rows) == 1 and marker in rows[0]


class TestMisspeltGrantNotRescued(unittest.TestCase):
    @pytest.mark.shared_layout_mutator
    def test_misspelt_unmarked_grant_is_not_rescued_by_project_copy(self):
        # covers: AR-400d-2-ii
        # angle: discrimination
        # must_catch: the project-local fallback in agent_ability_verdict._resolve is left in place
        """The project's .leafcutter/skills holds complexity-reductio; probe-coder grants it UNMARKED.
        The build fails with 'ability does not exist' for probe-coder / complexity-reductio and prints
        no informational project-supplied line for it."""
        b = G.built("misspelt")
        self.assertEqual(len(F.of_kind(b.out, F.NONEXIST, "complexity-reductio", "probe-coder")), 1, b.out[-1500:])
        self.assertNotEqual(b.rc, 0)
        self.assertEqual(G.info_lines(b.out, "probe-coder", "complexity-reductio", r"project|not found|supplied"), [])


class TestMarkedOverrideOfPackagedId(unittest.TestCase):
    @pytest.mark.shared_layout_mutator
    def test_marked_grant_for_packaged_id_delivers_project_copy_and_says_so(self):
        # covers: AR-400d-2-ii
        # angle: criterion
        # must_catch: the marked grant is refused as masking a package ability (the superseded clause)
        # must_catch: the packaged signoff is delivered despite the marking
        """The project's own signoff has distinct content; probe-coder grants signoff ``provided_by:
        project``. The build passes, probe-coder's compiled signoff row carries the PROJECT copy's
        description (not the packaged one), and exactly one informational line says the project's
        signoff is used in place of the packaged one."""
        b = G.built("override")
        self.assertEqual(b.rc, 0, b.out[-1500:])
        for root, text in G.compiled(b.sc.project, "probe-coder").items():
            self.assertTrue(_row_description_has(text, G.PROJECT_MARK), f"{root}: project copy not delivered: {G.ability_rows(text, 'signoff')}")
            self.assertNotIn(PACKAGED_SIGNOFF, "\n".join(G.ability_rows(text, "signoff")))
        lines = G.info_lines(b.out, "probe-coder", "signoff", OVERRIDE_INFO)
        self.assertEqual(len(lines), 1, f"expected one informational override line, got {lines}")

    @pytest.mark.shared_layout_mutator
    def test_project_override_copy_survives_rebuild(self):
        # covers: AR-400d-2-ii
        # angle: failure
        # must_catch: the skills phase overwrites the project copy with the packaged one
        # must_catch: --clean or the .claude/skills shim step removes the project copy (KI-BP-009)
        """Rebuild the same scratch consumer without --clean, then WITH --clean: after each,
        .leafcutter/skills/signoff/SKILL.md still holds the project bytes and the compiled prompt
        still reflects them."""
        sc = G.fresh("override")
        rc, out = G.build(sc)
        self.assertEqual(rc, 0, out[-1200:])
        original = G.project_bytes(sc.project, "signoff")
        self.assertIn(G.PROJECT_MARK.encode(), original)
        for extra in ((), ("--clean",)):
            rc, out = G.build(sc, *extra)
            self.assertEqual(rc, 0, f"build {extra}: {out[-1200:]}")
            self.assertEqual(G.project_bytes(sc.project, "signoff"), original, f"build {extra} changed the project copy")
            for root, text in G.compiled(sc.project, "probe-coder").items():
                self.assertTrue(_row_description_has(text, G.PROJECT_MARK), f"{root} after build {extra}")

    @pytest.mark.shared_layout_mutator
    def test_unmarked_grant_of_marked_id_receives_project_copy(self):
        # covers: AR-400d-2-ii
        # angle: criterion
        """In the same project, probe-second grants signoff UNMARKED: its compiled signoff row carries
        the project copy's description, not the packaged one (one directory per id, project-wide)."""
        b = G.built("override")
        for root, text in G.compiled(b.sc.project, "probe-second").items():
            self.assertTrue(_row_description_has(text, G.PROJECT_MARK), f"{root}: {G.ability_rows(text, 'signoff')}")


class TestMarkedPackagedIdAbsentFromProject(unittest.TestCase):
    @pytest.mark.shared_layout_mutator
    def test_marked_packaged_id_absent_from_project_falls_back_with_one_info_line(self):
        # covers: AR-400d-2-ii
        # angle: boundary
        # must_catch: the absent marked id is reported 'not installed' and not delivered
        # must_catch: the fallback line is a warning or is printed per reader
        """The project area has no signoff; probe-coder marks signoff ``provided_by: project``. The
        build passes, probe-coder's compiled row carries the PACKAGED signoff description, and exactly
        one informational line says the project does not supply signoff and the packaged copy is used."""
        b = G.built("fallback")
        self.assertEqual(b.rc, 0, b.out[-1500:])
        for root, text in G.compiled(b.sc.project, "probe-coder").items():
            rows = G.ability_rows(text, "signoff")
            self.assertEqual(len(rows), 1, f"{root}: {rows}")
            self.assertIn(PACKAGED_SIGNOFF, rows[0], f"{root}: packaged copy not delivered")
            self.assertNotIn("not installed", rows[0].lower(), "a shipped id must fall back, not read as absent")
        every = [ln for ln in b.out.splitlines()
                 if "probe-coder" in ln and F.names(ln, "signoff") and re.search(FALLBACK_INFO, ln, re.IGNORECASE)]
        info = G.info_lines(b.out, "probe-coder", "signoff", FALLBACK_INFO)
        self.assertEqual(len(every), 1, f"the fallback must be said once, got {every}")
        self.assertEqual(info, [ln.strip() for ln in every], "the fallback line must be informational (no warning/error marker)")


if __name__ == "__main__":
    unittest.main()
