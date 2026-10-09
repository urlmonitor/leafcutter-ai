"""AR-200b-2: an agent with a non-empty ability grant is permitted the `Skill` tool.

Entry points assumed (see _ar_200b_2_support.py for the full contract):
  * scripts/skill_tool_grant_validator.check_skill_tool_grants(template_dir) -> dict
  * scripts/registry_validator.validate_agent_registry(package_root) -> list[str]
  * `python scripts/registry_validator.py` (exit 1 on any error)
  * scripts/build.py _validate_all(...) (refuses, return 1, on any registry error)
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_HELPER = Path(__file__).resolve().parent / "_ar_200b_2_support.py"
_spec = importlib.util.spec_from_file_location("_ar_200b_2_support", _HELPER)
S: Any = importlib.util.module_from_spec(_spec)
sys.modules["_ar_200b_2_support"] = S
_spec.loader.exec_module(S)


def _plant(tmp: str, rows: list[tuple[str, str | None, list[str] | None]]) -> Path:
    tdir = Path(tmp) / "agents"
    tdir.mkdir()
    for name, tools, skills in rows:
        S.write_agent(tdir, name, tools, skills)
    return tdir


class TestSkillToolGrantCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_agent_with_a_grant_but_without_the_invoking_tool_is_reported(self):
        # covers: AR-200b-2
        # angle: criterion
        """A grant without Skill is reported naming agent, abilities, tools."""
        tdir = _plant(self.tmp, [
            ("alpha", "Bash, Read", ["signoff", "doc-enforcer"]),
            ("beta", "Bash, Skill", ["signoff"]),
        ])
        report = S.load_checker().check_skill_tool_grants(tdir)
        findings = report["findings"]
        self.assertEqual([f["agent"] for f in findings], ["alpha"])
        self.assertEqual(sorted(findings[0]["granted_abilities"]), ["doc-enforcer", "signoff"])
        self.assertEqual(findings[0]["declared_tools"], ["Bash", "Read"])
        action = findings[0]["suggested_action"].lower()
        self.assertIn("grant", action)
        self.assertIn("skill", action)
        for wrong in ("remove", "delete", "empty the"):
            self.assertNotIn(wrong, action, "remediation must grant the tool, never drop the grant")

    def test_read_only_agent_with_a_grant_is_reported_not_scoped_to_mutating_tools(self):
        # covers: AR-200b-2
        # angle: discrimination
        """Wrong version: AR-200b-1's mutating-tools scope filter leaks in and
        exempts an agent holding only read-only tools. Skill is not mutating."""
        tdir = _plant(self.tmp, [("reader", "Read, Grep", ["knowledge-query"])])
        report = S.load_checker().check_skill_tool_grants(tdir)
        self.assertEqual([f["agent"] for f in report["findings"]], ["reader"])

    def test_both_sides_are_read_from_the_agents_own_definition(self):
        # covers: AR-200b-2
        # angle: criterion
        """Registry edits do not move the verdict; a template edit does."""
        root = S.make_clean_package(Path(self.tmp) / "pkg")
        pop = S.derive_population(root / "templates" / "agents")
        victim = next(a for a in pop if a["abilities"])
        errors, _ = S.run_validate(root)
        self.assertEqual(S.prefixed(errors), [], "clean package must have no grant findings")

        import json
        reg = root / "config" / "agent_registry.json"
        data = json.loads(reg.read_text(encoding="utf-8"))
        for entry in data["agents"]:
            entry["skills_invoked"] = []
            entry["tools"] = "Skill"
        reg.write_text(json.dumps(data), encoding="utf-8")
        errors, _ = S.run_validate(root)
        self.assertEqual(S.prefixed(errors), [], "registry-only change moved the verdict")

        S.remove_skill_tool(victim["path"])
        errors, _ = S.run_validate(root)
        hits = S.prefixed(errors)
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(victim["name"], hits[0])

    def test_a_newly_granted_agent_is_reported_with_no_edit_to_the_comparison(self):
        # covers: AR-200b-2
        # angle: seam
        """Real producer (a template gaining a grant) -> real consumer
        (validate_agent_registry): a finding appears with no code edit."""
        root = S.make_clean_package(Path(self.tmp) / "pkg")
        pop = S.derive_population(root / "templates" / "agents")
        fresh = [a for a in pop if not a["abilities"] and S.INVOKING_TOOL not in (a["tools"] or [])]
        self.assertTrue(fresh, "need an ungranted agent lacking Skill to grant tomorrow")
        target = fresh[0]
        errors, _ = S.run_validate(root)
        self.assertEqual(S.prefixed(errors), [])
        S.add_grant(target["path"], ["tomorrow-skill"])
        errors, _ = S.run_validate(root)
        hits = S.prefixed(errors)
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(target["name"], hits[0])
        self.assertIn("tomorrow-skill", hits[0])

    def test_comparison_states_agents_examined_and_agents_holding_a_grant(self):
        # covers: AR-200b-2
        # angle: boundary
        """Exact counts; README (no frontmatter) is not an agent; empty grant
        is not held. Zero agents is a failure, never 'no violations'."""
        tdir = _plant(self.tmp, [
            ("a", "Bash", ["x"]),
            ("b", "Bash, Skill", ["x"]),
            ("c", "Bash", []),
            ("d", "Bash", None),
        ])
        (tdir / "README.md").write_text("# not an agent\n", encoding="utf-8")
        checker = S.load_checker()
        report = checker.check_skill_tool_grants(tdir)
        self.assertEqual((report["examined_count"], report["granted_count"]), (4, 2))
        self.assertEqual(len(report["findings"]), 1)

        empty = Path(self.tmp) / "empty"
        empty.mkdir()
        (empty / "README.md").write_text("# nothing\n", encoding="utf-8")
        self.assertEqual(checker.check_skill_tool_grants(empty)["examined_count"], 0)
        for bad in (empty, Path(self.tmp) / "does-not-exist"):
            errs = checker.validate_skill_tool_grants(bad)
            self.assertTrue(errs, f"zero-agent run on {bad.name} must fail")
            self.assertTrue(all(e.startswith(S.ERROR_PREFIX) for e in errs))

    def test_invoking_tool_is_matched_exactly_not_by_substring(self):
        # covers: AR-200b-2
        # angle: boundary
        """Wrong version: `'Skill' in tools_string`. Longer tokens embedding the
        name must not count; whitespace variants of the exact token must."""
        embedded = ["SkillBuilder", "mcp__x__Skill", "Skills", "MySkill", "Skill Tool"]
        rows = [(f"emb{i}", f"Bash, {tok}", ["g"]) for i, tok in enumerate(embedded)]
        rows += [("ok1", "Bash,Skill", ["g"]), ("ok2", "Skill, Bash", ["g"]), ("ok3", "Skill", ["g"])]
        tdir = _plant(self.tmp, rows)
        report = S.load_checker().check_skill_tool_grants(tdir)
        self.assertEqual(report["examined_count"], 8)
        self.assertEqual(sorted(f["agent"] for f in report["findings"]),
                         sorted(f"emb{i}" for i in range(5)))

    def test_comparison_reproduces_the_measured_mismatch_on_the_real_tree(self):
        # covers: AR-200b-2
        # angle: real_artifact
        """Real templates with Skill stripped (real bytes, not typed): the check
        must report exactly the derived granted population, non-vacuously."""
        import shutil
        copy = Path(self.tmp) / "real_copy"
        shutil.copytree(S.REAL_TEMPLATES, copy)
        pop = S.derive_population(copy)
        granted = [a for a in pop if a["abilities"]]
        self.assertGreater(len(granted), 0, "derived zero granted agents")
        for a in granted:
            S.remove_skill_tool(a["path"])
        report = S.load_checker().check_skill_tool_grants(copy)
        self.assertEqual(report["examined_count"], len(pop))
        self.assertEqual(report["granted_count"], len(granted))
        self.assertEqual({f["agent"] for f in report["findings"]}, {a["name"] for a in granted})
        self.assertEqual(len(report["findings"]), len(granted))


class TestRealTemplatesAndEntryPoints(unittest.TestCase):
    def test_every_granted_agent_in_the_real_templates_holds_the_skill_tool(self):
        # covers: AR-200b-2
        # angle: criterion
        """Whole derived population; fails on zero; names every offender."""
        pop = S.derive_population(S.REAL_TEMPLATES)
        granted = [a for a in pop if a["abilities"]]
        self.assertGreater(len(pop), 0, "derived zero agents")
        self.assertGreater(len(granted), 0, "derived zero granted agents")
        lacking = sorted(S.shortfall_names(pop))
        self.assertEqual(
            lacking, [],
            f"{len(lacking)} of {len(granted)} granted agents (of {len(pop)} examined) "
            f"lack the exact tool {S.INVOKING_TOOL!r}: {lacking}",
        )

    def test_registry_validator_states_counts_and_reports_none_on_the_real_tree(self):
        # covers: AR-200b-2
        # angle: reachability
        """The real validate_agent_registry on the real package prints the
        examined/granted counts and returns no grant finding."""
        errors, out = S.run_validate(S.REPO_ROOT)
        m = re.search(r"skill-tool-grant: examined=(\d+) granted=(\d+)", out)
        self.assertIsNotNone(m, "no 'skill-tool-grant: examined=N granted=G' line printed")
        pop = S.derive_population(S.REAL_TEMPLATES)
        self.assertEqual(int(m.group(1)), len(pop))
        self.assertEqual(int(m.group(2)), len([a for a in pop if a["abilities"]]))
        self.assertEqual(S.prefixed(errors), [])

    def test_cli_exits_nonzero_naming_the_agent_when_a_grant_lacks_the_tool(self):
        # covers: AR-200b-2
        # angle: reachability
        """Mutation: a planted shortfall must make the real CLI check FAIL
        (exit 1, agent named), while the clean package exits 0 with counts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = S.make_clean_package(Path(tmp) / "pkg")
            clean = S.run_registry_cli(root)
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            self.assertRegex(clean.stdout, r"skill-tool-grant: examined=\d+ granted=\d+")
            victim = next(a for a in S.derive_population(root / "templates" / "agents")
                          if a["abilities"])
            S.remove_skill_tool(victim["path"])
            bad = S.run_registry_cli(root)
            self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
            self.assertRegex(bad.stdout, rf"ERROR: {re.escape(S.ERROR_PREFIX)}.*{re.escape(victim['name'])}")

    def test_build_refuses_on_a_grant_shortfall(self):
        # covers: AR-200b-2
        # angle: reachability
        """ADR-050 refuse-not-warn: build._validate_all returns 1 (abort) on a
        planted shortfall and 0 on the clean package."""
        import contextlib
        import io

        sys.path.insert(0, str(S.REPO_ROOT))
        import build

        with tempfile.TemporaryDirectory() as tmp:
            config = build.load_config(None, Path(tmp))
            root = S.make_clean_package(Path(tmp) / "pkg")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build._validate_all(config, root, False, False), 0)
                victim = next(a for a in S.derive_population(root / "templates" / "agents")
                              if a["abilities"])
                S.remove_skill_tool(victim["path"])
                self.assertEqual(build._validate_all(config, root, False, False), 1)


if __name__ == "__main__":
    unittest.main()
