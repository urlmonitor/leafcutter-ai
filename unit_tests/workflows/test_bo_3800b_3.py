"""BO-3800b-3: a complexity refusal brings in the restructuring specialist, not the
coder that wrote the change, and the skill it is told to apply is the one the
refusing check declares.

One test per declared descriptor, named exactly as the AC's test_spec names it.
Each EXECUTES build-feature.js and build-ticket.js (TWIN_DRIVERS) through the
driver harness and reads the dispatch record and the brief the run actually
sent. The declarations come from the REAL package seed routing table.

Named mutations:
  (1) THE AUTHOR AGAIN     -- route complexity to python-coder as well/instead.
  (2) THE ALWAYS-ON SKILL  -- tell the specialist complexity-reduction every time.
  (3) THE OVER-BROAD SUMMONS -- engage the specialist on every refusal.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800b_support as S  # noqa: E402

H = S.H
TWINS = list(H.TWIN_DRIVERS)
SKILL = "complexity-reduction"


@unittest.skipUnless(S.node_available(), "node is not on PATH")
class TestBo3800b3(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            S.drop_worktree(d)

    def _wt(self):
        d = S.make_worktree()
        self._dirs.append(d)
        return d

    def _complexity(self, driver):
        decl = S.declaration("check-complexity")
        return S.drive(driver, self._wt(), decl, S.complexity_demand())

    def _file_size(self, driver):
        decl = S.declaration("check-file-size", agent=S.SPECIALIST, skills=[])
        return S.drive(driver, self._wt(), decl, S.size_demand(lines=120))

    @staticmethod
    def _brief_skills(obs):
        (disp,) = S.specialist_dispatches(obs)
        brief = disp["opts_brief"]
        assert isinstance(brief, dict), f"no machine-readable brief on the dispatch: {disp}"
        return list(brief.get("skills") or []), disp

    def test_bo3800b3_complexity_refusal_engages_specialist_with_complexity_reduction_not_the_author(self):
        # covers: BO-3800b-3
        # angle: criterion
        # must_catch: THE AUTHOR AGAIN -- route complexity to python-coder as well as or instead
        # reachability surface: build-feature.js and build-ticket.js top-level bodies via TWIN_DRIVERS
        """Arm 1: specialist after the refusal and before the retry, brief names
        complexity-reduction, python-coder not engaged; same sequence in both twins."""
        sequences = {}
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, _ = self._complexity(driver)
                ls = S.labels(obs)
                self.assertIn(S.SPECIALIST, ls, ls)
                between = S.between_refusal_and_retry(obs)
                self.assertEqual(between, [S.SPECIALIST], ls)
                self.assertNotIn("python-coder", between, ls)
                self.assertEqual(S.commit_attempts(obs), 2, ls)
                skills, disp = self._brief_skills(obs)
                self.assertEqual(skills, [SKILL], disp["opts_brief"])
                self.assertIn(SKILL, disp["prompt"], "the skill is not in what the specialist was given")
                sequences[driver] = ls
        self.assertEqual(len(set(map(tuple, sequences.values()))), 1, sequences)

    def test_bo3800b3_file_size_refusal_brief_omits_complexity_reduction(self):
        # covers: BO-3800b-3
        # angle: discrimination
        # must_catch: THE ALWAYS-ON SKILL -- complexity-reduction on every engagement
        """Arm 2: a file-size specialist refusal engages the specialist and its brief
        does NOT name complexity-reduction, while a complexity refusal in the same
        harness does (control row: the field can say the skill)."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, _ = self._file_size(driver)
                self.assertIn(S.SPECIALIST, S.labels(obs), S.labels(obs))
                skills, disp = self._brief_skills(obs)
                self.assertEqual(skills, [], disp["opts_brief"])
                self.assertNotIn(SKILL, json.dumps(disp["opts_brief"]))
                self.assertNotIn(SKILL, disp["prompt"])
                control, _ = self._complexity(driver)
                control_skills, _ = self._brief_skills(control)
                self.assertEqual(control_skills, [SKILL])

    def test_bo3800b3_author_clears_and_mechanical_autofix_refusals_engage_no_extra_party(self):
        # covers: BO-3800b-3
        # angle: boundary
        # must_catch: THE OVER-BROAD SUMMONS -- the specialist on every refusal
        # must_catch: engage the declared agent of every declaration, including mechanical fixers
        """Arm 3 (green today = regression boundary): for a check-doc-links refusal
        (author-clears) and a check-doc-frontmatter refusal (mechanical-autofix,
        general-purpose) the dispatch record equals the record of the same run with
        the remedy record absent, and neither the specialist nor general-purpose is
        engaged by the driver."""
        cases = [
            ("check-doc-links", S.declaration("check-doc-links")),
            ("check-doc-frontmatter", S.declaration("check-doc-frontmatter")),
        ]
        for driver in TWINS:
            for hook_id, decl in cases:
                with self.subTest(driver=driver, hook=hook_id):
                    self.assertEqual(
                        decl["disposition"],
                        "author-clears" if hook_id == "check-doc-links" else "mechanical-autofix",
                    )
                    refusal = {"status": "blocker", "message": f"{hook_id} refused delivery",
                               "remedy": {"hook_id": hook_id, "disposition": decl["disposition"],
                                          "skills": decl["skills"], "demand": []}}
                    with_remedy, _ = S.drive(driver, self._wt(), decl, [], reply=refusal)
                    baseline, _ = S.drive(driver, self._wt(), decl, [], reply=refusal, strip_remedy=True)
                    self.assertEqual(S.labels(with_remedy), S.labels(baseline))
                    self.assertNotIn(S.SPECIALIST, S.labels(with_remedy))
                    self.assertNotIn("general-purpose", S.labels(with_remedy))


if __name__ == "__main__":
    unittest.main()
