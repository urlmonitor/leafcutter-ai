"""AR-200b-3-i: a permission held only through the ticket-phase entry still requires the
dispatch tool, an absent ``tools:`` line is a shortfall, and an empty (or absent) permission
is not -- the ASYMMETRY of AR-200b-2-i carried over to the (``spawn_allowlist``, ``Agent``)
pair.

Entry points assumed (see _ar_200b_3_support.py): ``check_spawn_tool_grants(template_dir)``
and ``validate_agent_registry(package_root)``.

RED BASELINE (slice 5): the spawn pair does not exist (absence red); the validator's own
pass reports no spawn shortfall (assertion red).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_HELPER = Path(__file__).resolve().parent / "_ar_200b_3_support.py"
_spec = importlib.util.spec_from_file_location("_ar_200b_3_support", _HELPER)
S: Any = sys.modules.get("_ar_200b_3_support") or importlib.util.module_from_spec(_spec)
if "_ar_200b_3_support" not in sys.modules:
    sys.modules["_ar_200b_3_support"] = S
    _spec.loader.exec_module(S)


def _plant(tmp: str, rows) -> Path:
    tdir = Path(tmp) / "agents"
    tdir.mkdir()
    for name, tools, spawn in rows:
        S.write_spawn_agent(tdir, name, tools, spawn)
    return tdir


class TestMacroAbsentAndEmpty(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_macro_only_permission_without_agent_tool_is_reported(self):
        # covers: AR-200b-3-i
        # angle: discrimination
        """An agent whose ``spawn_allowlist`` is ONLY ``__ticket_phase_agents__`` and whose
        tools omit Agent is reported -- on the declaration as written, and also in a package
        where NO agent is marked ticket-phase (the macro resolves to nothing). Wrong version
        caught: the macro is resolved first and an empty resolution exempts the holder."""
        tdir = _plant(self.tmp, [("zz-macro", "Bash, Read", [S.MACRO]), ("zz-ok", "Bash, Agent", [S.MACRO])])
        report = S.check_spawn(tdir)
        self.assertEqual([f["agent"] for f in report["findings"]], ["zz-macro"])
        self.assertEqual(report["findings"][0]["declared_sub_agents"], [S.MACRO])

        root = S.make_clean_spawn_package(Path(self.tmp) / "pkg")
        reg = root / "config" / "agent_registry.json"
        data = json.loads(reg.read_text(encoding="utf-8"))
        for entry in data["agents"]:
            entry["is_ticket_phase"] = False
        reg.write_text(json.dumps(data), encoding="utf-8")
        pop = S.derive_population(root / "templates" / "agents")
        victim = next(a for a in pop if not a["spawn"] and S.INVOKING_TOOL not in (a["tools"] or []))
        S.add_spawn_declaration(victim["path"], [S.MACRO])
        errors, _ = S.run_validate(root)
        hits = S.spawn_errors(errors, victim["name"])
        self.assertEqual(len(hits), 1, hits)

    def test_absent_tools_line_with_a_permission_is_reported(self):
        # covers: AR-200b-3-i
        # angle: boundary
        """An agent with a named sub-agent and NO ``tools:`` line is reported (an absent tools
        declaration is not read as permitting everything); its declared tools are empty."""
        tdir = _plant(self.tmp, [("zz-notools", None, ["research-agent"]), ("zz-fine", "Agent", ["research-agent"])])
        report = S.check_spawn(tdir)
        self.assertEqual([f["agent"] for f in report["findings"]], ["zz-notools"])
        self.assertEqual(report["findings"][0]["declared_tools"], [])

    def test_empty_spawn_allowlist_without_agent_tool_is_not_reported_and_counted_as_none(self):
        # covers: AR-200b-3-i
        # angle: boundary
        """An agent with ``spawn_allowlist: []`` and no Agent tool produces no finding and is
        counted as holding NO permission (not an unknown one): 2 examined, 1 holding. Control:
        the holder that lacks the tool IS reported, so the quiet is not a dead check."""
        tdir = _plant(self.tmp, [("zz-empty", "Bash", []), ("zz-holder", "Bash, Agent", ["x"])])
        report = S.check_spawn(tdir)
        self.assertEqual((report["examined_count"], report["granted_count"]), (2, 1))
        self.assertEqual(report["findings"], [])
        S.write_spawn_agent(tdir, "zz-short", "Bash", ["x"])
        again = S.check_spawn(tdir)
        self.assertEqual((again["examined_count"], again["granted_count"]), (3, 2))
        self.assertEqual([f["agent"] for f in again["findings"]], ["zz-short"])

    def test_agent_tool_without_permission_is_not_reported(self):
        # covers: AR-200b-3-i
        # angle: failure
        """An agent holding Agent with no ``spawn_allowlist`` (absent, or empty) produces no
        finding -- holding the means without a permission is not a shortfall -- and is counted
        as holding none. Control row: a holder lacking the tool is reported."""
        tdir = _plant(self.tmp, [("zz-absent", "Bash, Agent", None), ("zz-empty", "Bash, Agent", []),
                                 ("zz-short", "Bash", ["x"])])
        report = S.check_spawn(tdir)
        self.assertEqual((report["examined_count"], report["granted_count"]), (3, 1))
        self.assertEqual([f["agent"] for f in report["findings"]], ["zz-short"])


if __name__ == "__main__":
    unittest.main()
