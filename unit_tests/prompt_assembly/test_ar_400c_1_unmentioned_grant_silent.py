"""AR-400c-1 / AR-400c-1-i -- a grant the instructions never mention produces no message at
all, and removing that noise does not silence a real fault about the same specialist
(TDD red phase: today ``check_skills_invoked_xref`` prints ~21 [WARNING] lines).

find-structural-smells (real template) grants ``review-for-structural-code-smells`` and its
body never names it. Doors: validator CLI (fresh subprocess), validator in-process, and the
build decision point ``build._validate_all`` -- all over a COPIED slice, plus the real tree.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
from _ar_400_support import ability_rows, built_prompts, installed_skill_ids  # noqa: E402

AGENT = "find-structural-smells"
GRANT = "review-for-structural-code-smells"
OLD_FORMS = (re.compile(r"skills_invoked declares '[^']*' but no reference found in template body"),
             re.compile(r"template references skill '[^']*' but skills_invoked does not declare it"))


def _pair_lines(text: str) -> list[str]:
    return [ln for ln in H.lines_of(text) if AGENT in ln and GRANT in ln]


def _all_doors_silent(tc: unittest.TestCase, root) -> None:
    """No line naming BOTH the specialist and the grant, at any severity, on any door."""
    rc, out = H.cli(root)
    tc.assertEqual(_pair_lines(out), [], out)
    tc.assertEqual(rc, 0, out)
    errors, stdout = H.validate(root)
    tc.assertEqual(_pair_lines(stdout) + [e for e in errors if AGENT in e and GRANT in e], [])
    brc, bout = H.build_door(root)
    tc.assertEqual(_pair_lines(bout), [], bout)
    tc.assertEqual(brc, 0, bout)


class TestUnmentionedGrant(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)

    def test_granted_but_unmentioned_ability_prints_nothing_in_validator_or_build(self):
        # covers: AR-400c-1
        # angle: criterion
        """The slice's find-structural-smells grants the ability and never names it as a path
        reference. Neither the validator (CLI + in-process) nor the build gate prints any
        line containing both names, at any severity (a downgrade to [INFO] still fails)."""
        body = (self.root / "templates" / "agents" / f"{AGENT}.md").read_text(encoding="utf-8").split("\n---\n", 1)[1]
        self.assertNotIn(f"skills/{GRANT}", body, "fixture invalid: the body names the grant")
        _all_doors_silent(self, self.root)

    def test_unmentioned_grant_still_reaches_the_compiled_prompt(self):
        # covers: AR-400c-1
        # angle: deployed
        """Wrong version caught: the noise is removed by removing the grant. The compiled
        find-structural-smells prompt (real in-process build, both platform roots) still
        lists the ability in its delivered abilities section -- AND, on the same tree, the
        validator prints no line naming both (so this cannot pass while the noise remains)."""
        installed = installed_skill_ids(H.REPO_ROOT)
        for root_name, text in built_prompts(AGENT).items():
            self.assertIn(GRANT, ability_rows(text, installed), f"{root_name}: grant lost from abilities section")
        _rc, out = H.cli(H.REPO_ROOT)
        self.assertEqual(_pair_lines(out), [], "real tree still prints noise about the unmentioned grant")

    def test_real_tree_prints_neither_old_xref_message_form(self):
        # covers: AR-400c-1
        # angle: real_artifact
        """Validator output over the checked-out package (in-process stdout and a fresh CLI
        process) contains no line of either removed message form, and the run exits 0."""
        errors, stdout = H.validate(H.REPO_ROOT)
        rc, out = H.cli(H.REPO_ROOT)
        for text in (stdout, out):
            bad = [ln for ln in H.lines_of(text) for pat in OLD_FORMS if pat.search(ln)]
            self.assertEqual(bad, [], f"{len(bad)} old xref line(s), first: {bad[:2]}")
        self.assertEqual([e for e in errors for pat in OLD_FORMS if pat.search(e)], [])
        self.assertEqual(rc, 0, out)

    def test_real_fault_survives_noise_removal_as_the_only_finding(self):
        # covers: AR-400c-1-i
        # angle: discrimination
        """Wrong version caught: the whole reference check is deleted with the old xref.
        find-structural-smells keeps its unmentioned grant AND gains a Load of ghost-ability:
        the CLI fails (exit 1, build gate aborts) with EXACTLY ONE line naming
        find-structural-smells -- the 'ability does not exist' ERROR for ghost-ability --
        and nothing about the unmentioned grant."""
        path = self.root / "templates" / "agents" / f"{AGENT}.md"
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + H.GHOST_SENTENCE + "\n", encoding="utf-8")
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 1, out)
        mine = [ln for ln in H.lines_of(out) if AGENT in ln]
        self.assertEqual(len(mine), 1, f"want exactly one finding naming {AGENT}: {mine}")
        self.assertTrue(mine[0].startswith("ERROR:"), mine[0])
        self.assertEqual(len(H.findings(mine, H.GHOST, AGENT)), 1, mine)
        self.assertEqual([ln for ln in H.lines_of(out) if GRANT in ln], [], "noise about the unmentioned grant")
        brc, bout = H.build_door(self.root)
        self.assertEqual(brc, 1, bout)
        self.assertEqual(len(H.findings(bout, H.GHOST, AGENT)), 1, bout)


if __name__ == "__main__":
    unittest.main()
