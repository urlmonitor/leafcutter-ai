"""AR-400e-1-iii -- a specialist's published card and its abilities done-verdict agree with
its declaration (TDD red phase).

Cards are produced by the real ``generate_agent_cards.build_agent_cards`` into a temporary
slice (never into ``docs/agents/cards/``); the verdict by ``agent_ability_verdict.verify_abilities``.
Fixture specialists are written with ``yaml.safe_dump`` and registry records are deep copies
of a real record.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400e_support as H  # noqa: E402
import agent_ability_verdict as verdict  # noqa: E402  (scripts/ is on sys.path via the support module)



def test_cards_list_exactly_declared_abilities_with_mode_and_condition(tmp_path):
    # covers: AR-400e-1-iii
    # angle: real_artifact
    """Cards regenerated from a copy of the real tree: each specialist's '## Skills Used' table
    lists exactly its declared ids, each with its declared mode, and (for conditional grants) its
    declared condition. descriptive_only ids are not listed. Red while the card reads the
    registry (descriptive entries, skills_used-only specialists with mode '—')."""
    root = H.lean_root(tmp_path)
    decl = H.declared(root)
    for entries in decl.values():  # precondition: a table cell can hold the condition text verbatim
        assert all("|" not in e.get("condition", "") for e in entries)
    view, rows = H.view_cards(root)
    problems = [m for m in H.mismatches("card", view, {a: {e["skill_id"] for e in es} for a, es in decl.items()})
                if "examined" not in m]
    for agent, entries in sorted(decl.items()):
        got = {sid: (mode, cond) for sid, mode, cond in rows.get(agent, [])}
        for e in entries:
            if e["skill_id"] not in got:
                continue  # already reported above
            mode, cond = got[e["skill_id"]]
            if mode != e["mode"]:
                problems.append(f"card: {agent}/{e['skill_id']} mode {mode!r} != declared {e['mode']!r}")
            if e["mode"] == "conditional" and cond != e["condition"]:
                problems.append(f"card: {agent}/{e['skill_id']} condition {cond!r} != declared {e['condition']!r}")
    assert any(e["mode"] == "conditional" for es in decl.values() for e in es), "need a conditional grant"
    assert not problems, f"{len(problems)} problem(s):\n" + "\n".join(problems[:25])


class TestVerdictAndPlantedOlderField(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_verdict_is_computed_over_declared_abilities_only(self):
        # covers: AR-400e-1-iii
        # angle: criterion
        """Verdict over (A) the committed registry and (B) the hook's output with the retired
        field hand-removed: abilities_examined equals the total declared grants exactly, and no
        finding exists or mentions an id that only a registry skills_used field holds. (B) is red
        while the verdict still draws four specialists' abilities from skills_used."""
        root = H.lean_root(self.base, name="committed")
        decl = H.declared_ids(root)
        total = sum(len(v) for v in decl.values())
        self.assertGreater(total, 0)
        stray = {a["id"]: {e if isinstance(e, str) else e["skill_id"] for e in a.get("skills_used") or []}
                 - decl.get(a["id"], set()) for a in H.registry(root)["agents"]}
        stray = {a: s for a, s in stray.items() if s}
        _view, committed = H.view_verdict(root, self.base)
        self.assertEqual(committed["abilities_examined"], total)
        mentioned = [f for f in committed["findings"] if any(i in json.dumps(f) for s in stray.values() for i in s)]
        self.assertEqual(mentioned, [], f"findings mention ids only skills_used holds: {mentioned}")
        regen = H.regenerated_root(self.base)
        _view, result = H.view_verdict(regen, self.base)
        self.assertEqual(result["abilities_examined"], total)
        # AR-400d-2 retarget: sql-coder's project-supplied grants are not installed in the (empty)
        # scratch project -- a statement at informational severity, never a finding that blocks.
        absent = {(f["agent"], f["ability"]) for f in result["findings"] if f["kind"] == "project-ability-absent"}
        self.assertEqual(absent, {(a, i) for a, ids in H.project_supplied_unshipped(regen).items() for i in ids})
        blocking = [f for f in result["findings"] if f["kind"] != "project-ability-absent"]
        self.assertEqual(blocking, [], "verdict over exactly the declared abilities must be clean")
        self.assertTrue(result["ok"])

    def _fixture(self, name: str, *, invoked: list, used: list) -> Path:
        root = self.base / name
        for sid in ("a1", "a2"):
            (root / "templates" / "skills" / sid).mkdir(parents=True)
            (root / "templates" / "skills" / sid / "SKILL.md").write_text(
                "---\n" + yaml.safe_dump({"name": sid, "description": f"{sid} fixture"}) + "---\n\nbody\n", encoding="utf-8")
        fm = {"name": "probe-card", "description": "probe", "tools": "Bash, Read, Skill", "model": "sonnet",
              "skills": [{"skill_id": "a1", "mode": "always"}]}
        (root / "templates" / "agents").mkdir(parents=True)
        (root / "templates" / "agents" / "probe-card.md").write_text(
            "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody\n", encoding="utf-8")
        rec = copy.deepcopy(next(a for a in H.registry(H.REPO_ROOT)["agents"] if a["id"] == "product-owner"))
        rec.update({"id": "probe-card", "name": "probe-card", "template_path": "templates/agents/probe-card.md",
                    "skills_invoked": invoked, "skills_used": used})
        (root / "config").mkdir()
        H.write_registry(root, {"agents": [rec]})
        return root

    def test_planted_older_field_entry_is_ignored_by_card_and_verdict(self):
        # covers: AR-400e-1-iii
        # angle: discrimination
        """Fixture specialist declares a1; its registry entry carries a hand-planted skills_used
        ['a2']. Variant A has the correct skills_invoked [a1]; variant B has none (the card's old
        fallback). Wrong versions caught: the card falls back to skills_used (B), and
        _record_abilities still unions skills_used (A and B). The card lists only a1; the verdict
        never mentions a2 (A: clean verdict)."""
        a1 = {"skill_id": "a1", "mode": "always"}
        problems: list[str] = []
        for variant, invoked in (("A", [a1]), ("B", [])):
            root = self._fixture(f"probe{variant}", invoked=invoked, used=["a2"])
            view, _rows = H.view_cards(root)
            if view.abilities != {"probe-card": {"a1"}}:
                problems.append(f"variant {variant}: card lists {view.abilities}, expected only a1")
            result = verdict.verify_abilities(
                {"probe-card": [a1]}, H.registry(root)["agents"],
                packaged_skills_root=root / "templates" / "skills", project_root=root)
            if "a2" in json.dumps(result):
                problems.append(f"variant {variant}: verdict mentions a2: {result['findings']}")
            if variant == "A" and not result["ok"]:
                problems.append(f"variant A: verdict not clean: {result['findings']}")
            if variant == "B" and "a1" not in json.dumps(result["findings"]):
                problems.append("variant B: control failed, verdict is vacuously clean")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
