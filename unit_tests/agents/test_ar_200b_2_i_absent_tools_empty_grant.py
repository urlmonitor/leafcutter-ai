"""AR-200b-2-i: absent tools is a shortfall; absent or empty grant is not.

Same assumed entry points as test_ar_200b_2_skill_tool_grant.py
(contract in _ar_200b_2_support.py).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_HELPER = Path(__file__).resolve().parent / "_ar_200b_2_support.py"
_spec = importlib.util.spec_from_file_location("_ar_200b_2_support", _HELPER)
S: Any = sys.modules.get("_ar_200b_2_support") or importlib.util.module_from_spec(_spec)
if "_ar_200b_2_support" not in sys.modules:
    sys.modules["_ar_200b_2_support"] = S
    _spec.loader.exec_module(S)


class TestAbsentAndEmptyDeclarations(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tdir = Path(self._tmp.name) / "agents"
        self.tdir.mkdir()

    def _plant(self, name, tools, skills):
        S.write_agent(self.tdir, name, tools, skills)

    def test_grant_with_absent_tools_declaration_is_reported(self):
        # covers: AR-200b-2-i
        # angle: boundary
        """No `tools:` key at all plus a grant -> reported, tools shown as none.
        Wrong version: skip the agent because no constraint was recorded."""
        self._plant("newest", None, ["signoff"])
        self._plant("blank", "", ["signoff"])
        report = S.load_checker().check_skill_tool_grants(self.tdir)
        self.assertEqual(sorted(f["agent"] for f in report["findings"]), ["blank", "newest"])
        by_name = {f["agent"]: f for f in report["findings"]}
        self.assertEqual(by_name["newest"]["declared_tools"], [])
        self.assertEqual(by_name["newest"]["granted_abilities"], ["signoff"])
        self.assertEqual((report["examined_count"], report["granted_count"]), (2, 2))

    def test_tool_without_a_grant_is_not_reported(self):
        # covers: AR-200b-2-i
        # angle: failure
        """Holding Skill without a grant is no shortfall (control: a granted
        agent lacking Skill in the same run IS reported, so the empty result
        is not a dead check)."""
        self._plant("holder", "Bash, Skill", None)
        self._plant("holder_empty", "Bash, Skill", [])
        self._plant("control", "Bash", ["g"])
        report = S.load_checker().check_skill_tool_grants(self.tdir)
        self.assertEqual([f["agent"] for f in report["findings"]], ["control"])
        self.assertEqual(report["examined_count"], 3)
        self.assertEqual(report["granted_count"], 1)

    def test_empty_grant_is_not_reported_and_counts_as_holding_no_grant(self):
        # covers: AR-200b-2-i
        # angle: boundary
        """`skills: []` -> no finding and granted_count excludes it (not unknown)."""
        self._plant("empty_no_tools", None, [])
        self._plant("empty_tools", "Bash", [])
        self._plant("absent_grant_no_tools", None, None)
        self._plant("granted", "Bash, Skill", ["g"])
        report = S.load_checker().check_skill_tool_grants(self.tdir)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["examined_count"], 4)
        self.assertEqual(report["granted_count"], 1)

    def test_absent_means_permits_nothing_on_tools_but_holds_nothing_on_grants(self):
        # covers: AR-200b-2-i
        # angle: boundary
        """The asymmetry in one run, all four absence combinations. Wrong
        version: one shared 'missing -> empty/skip' normaliser."""
        self._plant("grant_absent_tools", None, ["g"])
        self._plant("absent_grant_absent_tools", None, None)
        self._plant("absent_grant_no_skill", "Bash, Read", None)
        self._plant("grant_with_skill", "Skill", ["g"])
        report = S.load_checker().check_skill_tool_grants(self.tdir)
        self.assertEqual([f["agent"] for f in report["findings"]], ["grant_absent_tools"])
        self.assertEqual((report["examined_count"], report["granted_count"]), (4, 2))

    def test_the_three_shapes_through_the_real_validator_entry_point(self):
        # covers: AR-200b-2-i
        # angle: seam
        """Real template shapes (yaml.safe_dump) -> validate_skill_tool_grants:
        exactly the first agent produces an error line, naming it."""
        self._plant("first", None, ["g"])
        self._plant("second", "Skill, Bash", None)
        self._plant("third", None, [])
        errors = S.load_checker().validate_skill_tool_grants(self.tdir)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith(S.ERROR_PREFIX))
        self.assertIn("first", errors[0])
        for innocent in ("second", "third"):
            self.assertNotIn(innocent, errors[0])


if __name__ == "__main__":
    unittest.main()
