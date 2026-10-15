"""AR-400e-2-i -- a registry entry that still carries the retired ``skills_used`` list is
refused by the registry validator AND by the build (TDD red phase).

Doors (as in test_ar_400c_5_signoff_false_grant / _ar_400a_1_support): a REAL copy of the
package slice; ``registry_validator.validate_agent_registry`` in-process (returned error list),
the real CLI ``python <pkg>/scripts/registry_validator.py`` (exit code + printed ``ERROR:``),
and ``build._validate_all`` (the exact decision ``build.py`` aborts on; 1 == abort). No build.py
spawn. ``probe-agent`` is planted (template via ``yaml.safe_dump``, registry record a deep copy of
the real ``product-owner`` record) with a CORRECT ``skills_invoked``; every other record has the
retired field hand-removed so the planted entry is the only candidate for a finding.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as A  # noqa: E402

logging.disable(logging.CRITICAL)
AGENT = "probe-agent"


def _is_finding(text: str) -> bool:
    return AGENT in text and "skills_used" in text


class TestRetiredFieldRefused(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = A.make_slice(self._tmp.name)
        data = A._registry(self.root)
        for rec in data["agents"]:
            rec.pop("skills_used", None)
        A._write_registry(self.root, data)
        A.plant_agent(self.root, AGENT, grants=("signoff",))

    def _set_skills_used(self, value) -> None:
        data = A._registry(self.root)
        rec = next(a for a in data["agents"] if a["id"] == AGENT)
        if value is None:
            rec.pop("skills_used", None)
        else:
            rec["skills_used"] = value
        A._write_registry(self.root, data)

    def _doors(self) -> dict:
        errors, _out = A.validate(self.root)
        rc_cli, out_cli = A.cli(self.root)
        rc_build, out_build = A.build_door(self.root)
        return {"errors": [e for e in errors if _is_finding(e)], "rc_cli": rc_cli,
                "cli": [ln for ln in out_cli.splitlines() if _is_finding(ln)], "rc_build": rc_build,
                "build": [ln for ln in out_build.splitlines() if _is_finding(ln)],
                "all_cli": out_cli, "all_build": out_build}

    def _assert_refused(self, label: str) -> None:
        d = self._doors()
        self.assertEqual(len(d["errors"]), 1, f"{label}: validator must return one finding: {d['all_cli'][-800:]}")
        self.assertEqual(d["rc_cli"], 1, f"{label}: CLI must exit 1: {d['all_cli'][-800:]}")
        self.assertTrue(d["cli"] and d["cli"][0].startswith("ERROR:"), f"{label}: printed as ERROR: {d['cli']}")
        self.assertEqual(d["rc_build"], 1, f"{label}: build gate must abort: {d['all_build'][-800:]}")
        self.assertTrue(d["build"], f"{label}: build output must carry the finding")
        for text in (d["errors"][0], d["cli"][0], d["build"][0]):
            low = text.lower()
            self.assertIn("retired", low, text)
            self.assertIn("regenerated", low, text)
            self.assertIn("must not be authored", low, text)
            self.assertIn("declaration", low, text)

    def _assert_accepted(self, label: str) -> None:
        d = self._doors()
        self.assertEqual((d["errors"], d["cli"], d["build"]), ([], [], []), label)
        self.assertEqual((d["rc_cli"], d["rc_build"]), (0, 0), f"{label}: {d['all_cli'][-600:]}")

    def test_registry_entry_with_skills_used_is_refused_by_validator_and_build(self):
        # covers: AR-400e-2-i
        # angle: criterion
        """probe-agent carries skills_used ['signoff'] beside a correct skills_invoked: the
        validator returns ONE finding, the CLI exits 1 printing it as ERROR, and the build gate
        aborts; each names probe-agent and skills_used and says the field is retired, regenerated
        from the declaration and must not be authored. Presence alone is refused: the same holds
        for the empty list. Control first: the unplanted registry passes both doors, so a refusal
        is the planted field and nothing else. Wrong versions: silently dropped; schema-only."""
        self._assert_accepted("control: no skills_used anywhere")
        self._set_skills_used(["signoff"])
        self._assert_refused("skills_used ['signoff']")
        self._set_skills_used([])
        self._assert_refused("skills_used []")

    def test_removing_the_field_makes_both_pass(self):
        # covers: AR-400e-2-i
        # angle: discrimination
        """Positive first (else the negative control is vacuous): with the field planted both
        doors refuse. Then the field is removed from the same entry: validator, CLI and build all
        pass and no output line mentions skills_used for probe-agent."""
        self._set_skills_used(["signoff"])
        self._assert_refused("planted")
        self._set_skills_used(None)
        self._assert_accepted("removed")


if __name__ == "__main__":
    unittest.main()
