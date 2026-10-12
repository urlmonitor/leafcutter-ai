"""AR-200b-3: an agent permitted to dispatch sub-agents (a non-empty ``spawn_allowlist`` in its
own definition) is permitted the tool by which an agent is dispatched -- the exact token
``Agent`` in its own ``tools:`` -- and the build refuses until the tool is granted.

Entry points assumed (see _ar_200b_3_support.py for the contract):
  * scripts/skill_tool_grant_validator.check_spawn_tool_grants(template_dir) -> dict
  * scripts/registry_validator.validate_agent_registry(package_root) -> list[str]
  * scripts/build.py _validate_all(...) (refuses, return 1, on any registry error)

RED BASELINE (slice 5): the spawn pair does not exist, so every check of it fails (absence
red); the validator's own pass reports no spawn shortfall at all (assertion red).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_HELPER = Path(__file__).resolve().parent / "_ar_200b_3_support.py"
_spec = importlib.util.spec_from_file_location("_ar_200b_3_support", _HELPER)
S: Any = importlib.util.module_from_spec(_spec)
sys.modules["_ar_200b_3_support"] = S
_spec.loader.exec_module(S)


def _plant(tmp: str, rows: list[tuple[str, str | None, list[str] | None]]) -> Path:
    tdir = Path(tmp) / "agents"
    tdir.mkdir()
    for name, tools, spawn in rows:
        S.write_spawn_agent(tdir, name, tools, spawn)
    return tdir


class TestSpawnToolGrantCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_agent_with_sub_agents_but_without_agent_tool_is_reported(self):
        # covers: AR-200b-3
        # angle: criterion
        """A permission without ``Agent`` is reported naming the agent, its sub-agents and
        the tools it does declare; an agent holding the tool is not."""
        tdir = _plant(self.tmp, [("alpha", "Bash, Read", ["research-agent", "zz-x"]),
                                 ("beta", "Bash, Agent", ["research-agent"])])
        report = S.check_spawn(tdir)
        findings = report["findings"]
        self.assertEqual([f["agent"] for f in findings], ["alpha"])
        self.assertEqual(sorted(findings[0]["declared_sub_agents"]), ["research-agent", "zz-x"])
        self.assertEqual(findings[0]["declared_tools"], ["Bash", "Read"])

    def test_suggested_action_is_grant_the_agent_tool(self):
        # covers: AR-200b-3
        # angle: criterion
        """The finding's suggested action is to GRANT the Agent tool, never to remove the
        permission."""
        tdir = _plant(self.tmp, [("alpha", "Bash, Read", ["research-agent"])])
        action = S.check_spawn(tdir)["findings"][0]["suggested_action"].lower()
        self.assertIn("grant", action)
        self.assertIn("agent", action)
        for wrong in ("remove", "delete", "empty the"):
            self.assertNotIn(wrong, action, "remediation must grant the tool, never drop the permission")

    def test_newly_permitted_agent_is_checked_with_no_edit_to_the_check(self):
        # covers: AR-200b-3
        # angle: seam
        """Real producer (a template gaining a ``spawn_allowlist``) -> real consumer
        (validate_agent_registry): a finding appears with no code edit, naming the agent and
        its sub-agent and the build refuses (nonzero error list); editing ONLY the registry's
        copy changes nothing -- both sides are read from the frontmatter."""
        root = S.make_clean_spawn_package(Path(self.tmp) / "pkg")
        pop = S.derive_population(root / "templates" / "agents")
        fresh = [a for a in pop if not a["spawn"] and S.INVOKING_TOOL not in (a["tools"] or [])]
        self.assertTrue(fresh, "need an agent lacking Agent to permit tomorrow")
        target = fresh[0]
        errors, _ = S.run_validate(root)
        self.assertEqual(S.spawn_errors(errors, target["name"]), [], "control: a clean package reports the agent")

        import json
        reg = root / "config" / "agent_registry.json"
        data = json.loads(reg.read_text(encoding="utf-8"))
        for entry in data["agents"]:
            if entry["id"] == target["name"]:
                entry["spawn_allowlist"] = ["research-agent"]
        reg.write_text(json.dumps(data), encoding="utf-8")
        errors, _ = S.run_validate(root)
        self.assertEqual(S.spawn_errors(errors, target["name"]), [], "a registry-only edit moved the verdict")

        S.add_spawn_declaration(target["path"], ["zz-tomorrow"])
        errors, _ = S.run_validate(root)
        hits = S.spawn_errors(errors, target["name"])
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("zz-tomorrow", hits[0])
        self.assertIn("Agent", hits[0])

    def test_agent_tool_is_matched_exactly_after_stripping_a_trailing_comment(self):
        # covers: AR-200b-3
        # angle: discrimination
        """On REAL template bytes (business-analyst's ``tools:`` carries a trailing YAML
        comment that no serializer can produce): ``Agent`` followed by that comment counts;
        a longer token embedding 'Agent' does not; a comment that merely CONTAINS the word
        'Agent' does not. Wrong versions caught: substring match on the raw tools string; the
        trailing comment parsed as part of the last tool token."""
        real = (S.REAL_TEMPLATES / "business-analyst.md").read_text(encoding="utf-8")
        self.assertRegex(real, r"(?m)^tools:[^\n]*\s#", "control: the real line carries a trailing comment")
        tdir = Path(self.tmp) / "agents"
        tdir.mkdir()
        variants = {"ok-comment": (["Read", "Skill", "Agent"], None),
                    "bad-embedded": (["Read", "Skill", "SubAgent"], None),
                    "bad-plural": (["Read", "Agents"], None),
                    "bad-mcp": (["Read", "mcp__x__Agent"], None),
                    "bad-comment-word": (["Read", "Skill"], "  # Agent is deliberately not granted here")}
        for name, (tokens, comment) in variants.items():
            path = tdir / f"{name}.md"
            path.write_text(real, encoding="utf-8")
            S.rename_agent(path, name)
            S.set_tools_line(path, tokens, comment=comment)
            S.add_spawn_declaration(path, ["research-agent"])
        report = S.check_spawn(tdir)
        self.assertEqual(report["examined_count"], 5)
        self.assertEqual(sorted(f["agent"] for f in report["findings"]),
                         ["bad-comment-word", "bad-embedded", "bad-mcp", "bad-plural"])

    def test_counts_examined_and_permitted_and_fails_on_zero(self):
        # covers: AR-200b-3
        # angle: boundary
        """Exact counts (README is not an agent; an empty declaration is not a permission);
        the validator's own pass prints the spawn counts line and they equal the derived
        population on the real tree, so a comparison that resolved to no agents is never read
        as one that found no violations."""
        tdir = _plant(self.tmp, [("a", "Bash", ["x"]), ("b", "Bash, Agent", ["x"]),
                                 ("c", "Bash", []), ("d", "Bash", None)])
        (tdir / "README.md").write_text("# not an agent\n", encoding="utf-8")
        report = S.check_spawn(tdir)
        self.assertEqual((report["examined_count"], report["granted_count"]), (4, 2))
        self.assertEqual(len(report["findings"]), 1)
        empty = Path(self.tmp) / "empty"
        empty.mkdir()
        self.assertEqual(S.check_spawn(empty)["examined_count"], 0)
        pop = S.derive_population(S.REAL_TEMPLATES)
        _errors, out = S.run_validate(S.REPO_ROOT)
        self.assertEqual(S.counts_line(out), (len(pop), len(S.holders(pop))), out[-400:])

    def test_skill_and_spawn_pairs_share_one_check(self):
        # covers: AR-200b-3
        # angle: discrimination
        """ONE ``validate_agent_registry`` pass yields both the Skill-tool and the Agent-tool
        finding for an agent lacking both, in the same shape (agent named, the permission
        listed, the tool named, a grant-the-tool action). The two pairs also agree on EVERY
        tools line of a battery (same parse): wrong version caught -- a separate spawn checker
        with its own tools parse."""
        root = S.make_clean_spawn_package(Path(self.tmp) / "pkg")
        pop = S.derive_population(root / "templates" / "agents")
        fresh = [a for a in pop if not a["spawn"] and not a["skills"]
                 and not {"Skill", "Agent"} & set(a["tools"] or [])]
        self.assertTrue(fresh, "need an agent holding neither tool and neither declaration")
        victim = fresh[0]
        S2 = sys.modules["_ar_200b_2_support"]
        S2.add_grant(victim["path"], ["zz-skill"])
        S.add_spawn_declaration(victim["path"], ["zz-sub"])
        errors, _ = S.run_validate(root)
        skill_hits, agent_hits = S.skill_errors(errors, victim["name"]), S.spawn_errors(errors, victim["name"])
        self.assertEqual((len(skill_hits), len(agent_hits)), (1, 1), (skill_hits, agent_hits))
        self.assertIn("zz-skill", skill_hits[0])
        self.assertIn("zz-sub", agent_hits[0])
        shapes = [S.SHAPE_RE.match(h) for h in (skill_hits[0], agent_hits[0])]
        self.assertTrue(all(shapes), f"the two pairs do not share one finding shape: {skill_hits + agent_hits}")
        self.assertEqual([m.group("tool") for m in shapes], ["Skill", "Agent"])
        self.assertEqual({m.group("name") for m in shapes}, {victim["name"]})
        for n, line in enumerate(("Read, Skill, Agent", "Read, Skill", "Read, Agent", "Read", "SkillX, AgentX",
                                  "Read,Skill,Agent")):
            tdir = Path(self.tmp) / f"battery-{n}"
            tdir.mkdir()
            S2.write_agent(tdir, "bat", line, ["g"])
            S.add_spawn_declaration(tdir / "bat.md", ["x"])
            skill = S2.load_checker().check_skill_tool_grants(tdir)["findings"]
            spawn = S.check_spawn(tdir)["findings"]
            self.assertEqual(bool(skill), "Skill" not in line.replace(" ", "").split(","), line)
            self.assertEqual(bool(spawn), "Agent" not in line.replace(" ", "").split(","), line)


class TestRealTemplatesAndEntryPoints(unittest.TestCase):
    def test_real_tree_passes_after_remediation_and_failed_before(self):
        # covers: AR-200b-3
        # angle: real_artifact
        """On a COPY of the real templates with the Agent remediation reverted (``Agent``
        stripped from every agent permitted a sub-agent), exactly the derived permitted
        population is reported -- build-ac and business-analyst among them, the two whose
        tools omitted the tool on 2026-10-09; on the real templates no Agent-tool finding
        remains. Population derived by parsing, counted, never empty."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = S.copy_real_templates(Path(tmp) / "real_copy")
            pop = S.derive_population(copy)
            permitted = S.holders(pop)
            self.assertGreater(len(permitted), 20, f"derived only {len(permitted)} permitted agents")
            for agent in permitted:
                S.remove_agent_tool(agent["path"])
            report = S.check_spawn(copy)
            self.assertEqual(report["examined_count"], len(pop))
            self.assertEqual(report["granted_count"], len(permitted))
            self.assertEqual({f["agent"] for f in report["findings"]}, {a["name"] for a in permitted})
            self.assertTrue({"build-ac", "business-analyst"} <= {f["agent"] for f in report["findings"]})
        real = S.check_spawn(S.REAL_TEMPLATES)
        self.assertEqual(real["findings"], [], f"real templates lack the Agent tool: {real['findings']}")

    def test_build_refuses_on_a_spawn_shortfall(self):
        # covers: AR-200b-3
        # angle: reachability
        """ADR-050 refuse-not-warn: build._validate_all returns 1 (abort) on a planted
        shortfall and 0 on the clean package (``Agent`` granted to every permitted agent)."""
        import contextlib
        import io

        sys.path.insert(0, str(S.REPO_ROOT))
        import build

        with tempfile.TemporaryDirectory() as tmp:
            config = build.load_config(None, Path(tmp))
            root = S.make_clean_spawn_package(Path(tmp) / "pkg")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build._validate_all(config, root, False, False), 0)
                victim = S.holders(S.derive_population(root / "templates" / "agents"))[0]
                S.remove_agent_tool(victim["path"])
                self.assertEqual(build._validate_all(config, root, False, False), 1)


if __name__ == "__main__":
    unittest.main()
