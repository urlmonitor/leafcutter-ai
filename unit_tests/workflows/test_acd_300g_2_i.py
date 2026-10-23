"""
MODULE: test_acd_300g_2_i
GOAL: RED-baseline tests for ACD-300g-2-i -- orphaned AC drafts from a crashed
    prior /create-ac (plan-feature) session are detected on the next run and put
    to the user as a yes/no/discard choice BEFORE any new triage begins.
BUSINESS CONTEXT: the AC names the orphan authors as product-owner-v3,
    business-analyst-v3 and it-po-v3 (the real origin_agent values on disk).
    scanOrphanedAcDrafts() in templates/workflows-js/plan-feature.js qualifies an
    orphan against the unversioned names only, so a real v3-authored orphan is
    silently skipped and the run proceeds straight to triage.
ARCHITECTURE: plan-feature.js's own top-level body through
    unit_tests/_workflow_engine_harness.run_workflow_under_e2; orphan file bytes
    come from yaml.safe_dump (real serializer), git status is the porcelain line
    git emits for an untracked AC file.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "unit_tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_JS = _REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_ORPHAN_PATH = "docs/acceptance-criteria/build-orchestration/ZZ-300-1.yaml"
_V3_AGENTS = ("product-owner-v3", "business-analyst-v3", "it-po-v3")


def _orphan_yaml(origin_agent: str, readiness: str = "draft") -> str:
    return yaml.safe_dump(
        {"id": "ZZ-300-1", "origin_agent": origin_agent, "readiness": readiness,
         "criteria": "Given a\nWhen b\nThen c\n"},
        sort_keys=False,
    )


def _run(origin_agent: str, readiness: str = "draft", git_exit: int = 0):
    return run_workflow_under_e2(
        _JS,
        timeout=60,
        label_responses={
            "scan-orphans-git-status": {"output": f"?? {_ORPHAN_PATH}\n", "exit_code": git_exit},
            "scan-orphans-read-file": {"content": _orphan_yaml(origin_agent, readiness)},
            "stage-0-triage": {"route": "technical", "existing_acs": []},
        },
        args={"workspace_setup_permission": {"permits": True}, "run_id": "r300g2i"},
    )


def _labels(res) -> list:
    return [c.label for c in res.agent_calls]


class TestOrphanDetection(unittest.TestCase):
    def test_orphan_authored_by_v3_agents_is_detected_before_triage(self):
        # covers: ACD-300g-2-i
        # angle: criterion
        """Then the workflow detects the uncommitted AC file (origin_agent one
        of the -v3 authoring agents, readiness draft) and asks the user
        yes/no/discard before any new triage."""
        for agent_name in _V3_AGENTS:
            with self.subTest(origin_agent=agent_name):
                res = _run(agent_name)
                self.assertNotIn("stage-0-triage", _labels(res), _labels(res))
                self.assertIsInstance(res.result, dict, res.error)
                self.assertEqual(res.result.get("gate_id"), "resolve-orphans-choice", res.result)

    def test_non_draft_or_foreign_files_are_not_orphans(self):
        # covers: ACD-300g-2-i
        # angle: boundary
        """Control: a v3-authored file that is NOT draft, and a draft authored
        by a non-authoring agent, are not orphans -- the run goes on to triage.
        Distinguishes 'accept any origin_agent' from 'accept the -v3 set'."""
        for origin, readiness in (("business-analyst-v3", "approved"), ("human-editor", "draft")):
            with self.subTest(origin=origin, readiness=readiness):
                res = _run(origin, readiness)
                self.assertIn("stage-0-triage", _labels(res), _labels(res))
                res_gate = (res.result or {}).get("gate_id") if isinstance(res.result, dict) else None
                self.assertNotEqual(res_gate, "resolve-orphans-choice")

    def test_git_status_failure_degrades_without_crashing(self):
        # covers: ACD-300g-2-i
        # angle: failure
        """git status failing (non-zero exit) must not crash the run and must
        not invent orphans; and a real v3 orphan must NOT be reported when the
        scan itself failed."""
        res = _run("business-analyst-v3", git_exit=128)
        self.assertFalse(res.error, res.stderr)
        self.assertNotEqual((res.result or {}).get("gate_id") if isinstance(res.result, dict) else None,
                            "resolve-orphans-choice")


class TestOrphanChoiceIsConsumed(unittest.TestCase):
    def test_orphan_no_answer_aborts_and_discard_or_yes_reaches_next_step(self):
        # covers: ACD-300g-2-i
        # angle: reachability
        """Production entry (workflow body, real argv-equivalent args): the
        gate answer is consumed in control flow. 'no' aborts with the
        resolve-first message and never reaches triage."""
        res = run_workflow_under_e2(
            _JS,
            timeout=60,
            label_responses={
                "scan-orphans-git-status": {"output": f"?? {_ORPHAN_PATH}\n", "exit_code": 0},
                "scan-orphans-read-file": {"content": _orphan_yaml("it-po-v3")},
                "stage-0-triage": {"route": "technical", "existing_acs": []},
            },
            args={
                "workspace_setup_permission": {"permits": True},
                "run_id": "r300g2i-no",
                "resume_answer": {"gate_id": "resolve-orphans-choice", "action": "no"},
            },
        )
        self.assertIn("scan-orphans-read-file", _labels(res))
        self.assertNotIn("stage-0-triage", _labels(res), _labels(res))
        self.assertIsInstance(res.result, dict)
        self.assertEqual(res.result.get("gate_id"), "resolve-orphans-choice", res.result)


if __name__ == "__main__":
    unittest.main()
