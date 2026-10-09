"""
MODULE: unit_tests/workflows/test_inf_700a_1_iv_epic_drive_wiring.py
GOAL: Prove the epic drive's knowledge-routing step (ADR-040 section 3,
    INF-700a-1-iv) is wired where a commit actually follows it, and that its
    result is CONSUMED, not merely produced:

      1. build-epic.js, driven through the real Node-backed engine harness,
         puts each ticket-supervisor's knowledge_routing on its own result and
         sums it. Differing ticket figures give differing epic results with
         equal status (anti-fire-and-forget), and no routing reply changes the
         drive's outcome (fail-open).
      2. The skill-hosted step: ticket-supervisor's commit-phase procedure in
         building-epics SKILL.md section 5.9 cannot run in the unit layer, so
         per CLAUDE.md "Gate / Workflow ACs" we assert that the step's output
         is consumed in the procedure's control flow. The stage's manifest
         feeds the commit spawn's stage list, the observe reply is what gets
         returned, all of it sits inside the commit lock, and the pseudocode
         and the agent template both route the commit phase through it.
      3. The wiring declaration stays honest. The build-time guard enumerates
         workflow artefacts only, so build-epic.js stays EXCLUDED, with
         covered_by naming the skill section, and the guard still passes.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from build_phases_knowledge import check_knowledge_routing_wiring  # noqa: E402
from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_BUILD_EPIC = _REPO_ROOT / "templates" / "workflows-js" / "build-epic.js"
_SKILL = _REPO_ROOT / "templates" / "skills" / "building-epics" / "SKILL.md"
_SUPERVISOR = _REPO_ROOT / "templates" / "agents" / "ticket-supervisor.md"
_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_EPIC = "tickets/00_inbox/epics/EPIC-X"


def _routing(written: int, unwritten: int, case: str = "completed") -> dict:
    return {"case": case, "read": written + unwritten, "written": written,
            "unwritten": unwritten, "already_on_branch": 0, "detail": None}


def _run_epic(replies: dict[str, dict]):
    tickets = [{"path": path, "status": "todo"} for path in replies]
    responses = {
        "epic-planner": {"epic_path": _EPIC, "title": "EPIC-X",
                         "batches": [{"batch_number": 1, "tickets": tickets}]},
        **{f"ticket:{path}": reply for path, reply in replies.items()},
    }
    result = run_workflow_under_e2(
        _BUILD_EPIC, label_responses=responses,
        args={"epic_path": _EPIC, "worktree_path": "/tmp/wt"},
    )
    assert result.error == "", result.error
    return result


class TestBuildEpicConsumesEachTicketsRouting(unittest.TestCase):
    def test_the_epic_result_carries_each_tickets_routing_and_the_drive_totals(self) -> None:
        # covers: INF-700a-1-iv, INF-700a-1
        # angle: reachability
        result = _run_epic({
            "01_a.md": {"status": "ok", "knowledge_routing": _routing(2, 0)},
            "02_b.md": {"status": "ok", "knowledge_routing": _routing(1, 1)},
        }).result
        report = result["knowledge_routing"]
        per_ticket = {t["ticket_path"]: (t["written"], t["unwritten"]) for t in report["tickets"]}
        self.assertEqual(per_ticket, {"01_a.md": (2, 0), "02_b.md": (1, 1)}, report)
        self.assertEqual((report["written"], report["unwritten"]), (3, 1), report)

    def test_differing_ticket_figures_give_differing_epic_reports_with_equal_status(self) -> None:
        # covers: INF-700a-1-iv
        # angle: seam
        carried = _run_epic({"01_a.md": {"status": "ok", "knowledge_routing": _routing(2, 0)}})
        dropped = _run_epic({"01_a.md": {"status": "ok", "knowledge_routing": _routing(0, 2)}})
        self.assertNotEqual(carried.result["knowledge_routing"], dropped.result["knowledge_routing"])
        self.assertEqual(carried.result["status"], dropped.result["status"])

    def test_an_absent_or_unrecognised_routing_reply_is_did_not_run_and_changes_nothing(self) -> None:
        # covers: INF-700a-1-iv
        # angle: failure
        result = _run_epic({
            "01_a.md": {"status": "ok"},
            "02_b.md": {"status": "ok", "knowledge_routing": {"case": "bogus", "written": 9}},
        }).result
        self.assertEqual(result["status"], "ok")
        cases = {t["ticket_path"]: (t["case"], t["written"]) for t in result["knowledge_routing"]["tickets"]}
        self.assertEqual(cases, {"01_a.md": ("did_not_run", 0), "02_b.md": ("did_not_run", 0)})
        self.assertEqual(result["knowledge_routing"]["written"], 0)

    def test_a_halted_epic_still_reports_what_its_committed_tickets_routed(self) -> None:
        # covers: INF-700a-1-iv
        # angle: boundary
        result = _run_epic({
            "01_a.md": {"status": "ok", "knowledge_routing": _routing(1, 0)},
            "02_b.md": {"status": "blocked", "message": "hook refused"},
        }).result
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["knowledge_routing"]["written"], 1, result)

    def test_the_supervisor_is_told_to_return_its_section_5_9_observation(self) -> None:
        # covers: INF-700a-1-iv
        # angle: seam
        run = _run_epic({"01_a.md": {"status": "ok"}})
        prompt = next(c.prompt for c in run.agent_calls if c.label == "ticket:01_a.md")
        # presence-only: asserts the prompt the harness captured at runtime, not the JS source; consumption is proven by the tests above
        self.assertIn("knowledge_routing", str(prompt))
        self.assertIn("§5.9", str(prompt))


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = re.search(r"^#{2,3} ", text[start + len(heading):], re.MULTILINE)
    return text[start: start + len(heading) + (nxt.start() if nxt else len(text))]


def _steps(section: str) -> list[str]:
    """Split a section into its top-level numbered steps (`N. ...` blocks)."""
    return [m.group(0) for m in re.finditer(r"^\d+\. .*?(?=^\d+\. |\Z)", section, re.MULTILINE | re.DOTALL)]


def _first(steps: list[str], pattern: str) -> int:
    matches = [i for i, step in enumerate(steps) if re.search(pattern, step, re.DOTALL)]
    assert matches, f"no step matches {pattern!r}: {steps}"
    return matches[0]


class TestTheSkillConsumesTheStepAroundTheCommit(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = _SKILL.read_text(encoding="utf-8")
        self.steps = _steps(_section(self.skill, "### §5.9"))

    def test_the_skill_orders_stage_commit_by_name_and_observe_inside_the_commit_lock(self) -> None:
        # covers: INF-700a-1-iv
        # angle: seam
        acquire = _first(self.steps, r"§5\.2")
        stage = _first(self.steps, r"completion_routing_cli\.py stage --working-dir")
        commit = _first(self.steps, r"[Ss]pawn the `commit` agent")
        observe = _first(self.steps, r"completion_routing_cli\.py observe --working-dir \S+ --commit-status")
        release = _first(self.steps, r"§5\.3")
        self.assertEqual(sorted([acquire, stage, commit, observe, release]),
                         [acquire, stage, commit, observe, release])
        self.assertEqual(len({acquire, stage, commit, observe, release}), 5)
        self.assertRegex(self.steps[commit], r"`manifest`.*by name", "the commit must consume the manifest")
        self.assertRegex(self.steps[observe], r"`knowledge_routing`", "the observe reply must be what is returned")

    def test_exactly_one_observe_runs_on_success_and_failure_alike_and_nothing_fails_the_ticket(self) -> None:
        # covers: INF-700a-1-iv
        # angle: failure
        observe = self.steps[_first(self.steps, r"observe --working-dir")]
        self.assertRegex(observe, r"--commit-status ok\|failed|ok` or `failed")
        self.assertIn("exactly once", observe)
        section = _section(self.skill, "### §5.9")
        self.assertRegex(section, r"[Nn]ever (block|fail|retry)")

    def test_the_ticket_algorithm_routes_the_commit_spawn_through_section_5_9(self) -> None:
        # covers: INF-700a-1-iv
        # angle: reachability
        pseudocode = _section(self.skill, "### §2.1 Pseudocode")
        spawn = pseudocode[pseudocode.index("2.  SPAWN"): pseudocode.index("3.  RE-READ")]
        self.assertRegex(spawn, r"next_agent == \"commit\".*§5\.9", "the spawn step must branch into §5.9")
        table = _section(self.skill, "### §2.1.1 Canonical Phase Ordering Table")
        self.assertIn("§5.9", table, "ADR-040 section 3 names §2.1.1 as the placement")

    def test_the_agent_template_follows_section_5_9_and_returns_the_routing(self) -> None:
        # covers: INF-700a-1-iv
        # angle: reachability
        template = _SUPERVISOR.read_text(encoding="utf-8")
        lock_step = template[template.index("3. **If the next agent is `commit`"): template.index("4. Spawn the chosen agent")]
        self.assertIn("§5.9", lock_step)
        outputs = _section(template, "## Outputs")
        self.assertIn('"knowledge_routing"', outputs)


class TestTheWiringDeclarationStaysHonest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
        self.section = self.config["knowledge_routing_wiring"]
        self.excluded = {e["path"]: e for e in self.section["excluded"]}

    def test_build_epic_is_excluded_with_covered_by_naming_the_skill_section(self) -> None:
        # covers: INF-700a-1-iv, INF-700a-1-i
        # angle: boundary
        self.assertNotIn("build-epic.js", self.section["wired"])
        entry = self.excluded["build-epic.js"]
        self.assertIn("building-epics/SKILL.md", entry["covered_by"] or "")
        self.assertIn("§5.9", entry["covered_by"] or "")
        self.assertTrue((_REPO_ROOT / "templates" / "skills" / "building-epics" / "SKILL.md").is_file())
        result = check_knowledge_routing_wiring(_REPO_ROOT / "templates" / "workflows-js", self.config)
        self.assertEqual(result["unwired"], [], result)

    def test_build_feature_exclusion_no_longer_claims_it_completes_nothing(self) -> None:
        # covers: INF-700a-1-i
        # angle: criterion
        reason = self.excluded["build-feature.js"]["reason"].lower()
        self.assertNotIn("completes nothing", reason)
        self.assertIn("commit", reason)


if __name__ == "__main__":
    unittest.main()
