"""BO-3800a-2 (arms 1 and 2): a commit made by a drive's commit step, or by the commit
agent outside a drive, brings the restructuring specialist in on a complexity refusal.

(Arm 3 -- a direct commit engages nobody and is shown the declared next step -- is a
real ``git commit`` and lives in unit_tests/commit_guardian/test_bo_3800a_2_direct_commits.py.)

Test names are exactly those of the AC's test_spec.

DECISIONS THE CODER MUST CONFORM TO (the AC leaves the exact names to the build):
* HELPER. ``templates/scripts/commit_guardian/remedy_handoff.py`` is a script. Run as
  ``python remedy_handoff.py --hook-id <id>`` with the hook's refusal output on stdin,
  from the project root, it prints ONE JSON object on stdout and exits 0::

      {"status": "handoff", "handoff_target": <declared specialist>,
       "message": <non-empty>, "record_handoff_target": <declared specialist>,
       "flips_signed_off": false,
       "remedy": {"hook_id", "disposition", "skills": [...], "demand": [...]}}

  ``demand`` is the machine-readable record check-complexity printed, verbatim and in
  refusal order; ``disposition``/``skills``/the specialist come from the shared
  remedy-declaration loader (never from the refusal prose). Output it cannot read, or
  a hook with no engage-specialist declaration, is a NON-ZERO exit with a named
  reason on stderr and nothing on stdout -- never an empty payload.
* INTERACTIVE DISPATCHER. ``templates/workflows-js/commit.js`` is a depth-0 workflow
  script. It dispatches the commit agent as ``agent(prompt, {agentType: "commit",
  label: "commit"})``; on a ``status: "handoff"`` reply carrying a remedy for an
  engage-specialist hook it dispatches ``{agentType: <handoff_target>, label:
  <handoff_target>}`` ("restructuring-specialist"), then re-offers the commit.

Fixture authenticity: the refusal the helper reads is the REAL output of the real
check_complexity.py against a real staged change in a real git repo
(``_bo3800c_support.real_complexity_record``); the payload fed to both dispatchers is
the REAL helper's output, never a hand-typed dict.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import _bo3800a_support as A  # noqa: E402
import _workflow_engine_harness as E  # noqa: E402

C, S, H, TWINS = A.C, A.S, A.H, A.TWINS
REPO = Path(H.REPO_ROOT)
HELPER = REPO / "templates" / "scripts" / "commit_guardian" / "remedy_handoff.py"
COMMIT_WORKFLOW = REPO / "templates" / "workflows-js" / "commit.js"
PLANNER = "scripts/planner.py"


def run_helper(refusal_output: str, hook_id: str = "check-complexity"):
    """The REAL helper, as a subprocess from the project root, refusal text on stdin."""
    return subprocess.run(
        [sys.executable, str(HELPER), "--hook-id", hook_id],
        input=refusal_output, cwd=str(REPO), capture_output=True, text=True, timeout=60, check=False,
    )


class _Base(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _scratch(self) -> Path:
        d = tempfile.mkdtemp(prefix="bo3800a2-")
        self._dirs.append(d)
        return Path(d)

    def real_payload(self) -> dict:
        """plan_batches 30 -> 31 refused by the real check; the payload the real helper
        builds from that output."""
        record, output, code = C.real_complexity_record(
            self._scratch() / "repo", {"plan_batches": 30}, {"plan_batches": 31}
        )
        self.assertEqual(code, 1, output)
        self.assertIsNotNone(record, output)
        self.assertTrue(HELPER.exists(), f"{HELPER} does not exist: the payload helper is not built")
        done = run_helper(output)
        self.assertEqual(done.returncode, 0, f"helper failed: {done.stdout!r} {done.stderr!r}")
        payload = json.loads(done.stdout)
        self.assertEqual(payload["status"], "handoff")
        self.assertEqual(payload["handoff_target"], S.SPECIALIST)
        self.assertEqual(payload["remedy"]["hook_id"], "check-complexity")
        self.assertEqual(payload["remedy"]["demand"], record)
        self.assertEqual(payload["remedy"]["skills"], ["complexity-reduction"])
        self.assertEqual(payload["remedy"]["demand"][0]["function"], "plan_batches")
        self.assertEqual((payload["remedy"]["demand"][0]["score"], payload["remedy"]["demand"][0]["ceiling"]), (31, 30))
        return payload


@unittest.skipUnless(S.node_available(), "node is not on PATH")
class TestBo3800a2(_Base):
    def _drive_commit_step(self, driver, payload):
        wt = S.make_worktree("bo3800a2-drive-")
        self._dirs.append(wt)
        A.author_change(wt)
        before = A.tree_digest(wt)
        decl = S.declaration("check-complexity")
        phases = ["test-writer", "python-coder", "commit"]
        path = H.write_ticket_record(wt, S.TICKET, phases, extra_frontmatter={"component": "build-orchestration"})
        cfg = {
            "title": "complexity refusal in a drive",
            "phases": phases,
            "has_test_requirements": True,
            "results": {"commit": [payload, {"status": "ok"}], S.SPECIALIST: {"status": "ok"}},
        }
        scenario = H.single_ticket_scenario(wt, path, cfg)
        scenario["remedy_declarations"] = {decl["hook_id"]: decl}
        obs = H.run_driver(H.TWIN_DRIVERS[driver], scenario)
        return obs, path, before, A.tree_digest(wt)

    def test_bo3800a2_drive_commit_refusal_engages_specialist_between_refusal_and_retry(self):
        # covers: BO-3800a-2
        # covers: BO-3800a
        # angle: criterion
        # reachability surface: unit_tests/prompt_assembly/_driver_harness.py executing build-feature.js (TWIN_DRIVERS)
        """Arm 1. The commit phase returns the payload the REAL helper produced from real
        check-complexity output (plan_batches, 31, 30). The dispatch record reads commit,
        then restructuring-specialist, then commit; the author's change is byte-identical
        across the hold. RED TODAY: the helper does not exist."""
        payload = self.real_payload()
        for driver in TWINS:
            with self.subTest(driver=driver):
                obs, path, before, after = self._drive_commit_step(driver, payload)
                self.assertEqual(S.between_refusal_and_retry(obs), [S.SPECIALIST], S.labels(obs))
                self.assertEqual(S.commit_attempts(obs), 2, S.labels(obs))
                self.assertEqual(before, after)
                self.assertTrue(S.completed(path), obs.get("result"))
                (specialist,) = S.specialist_dispatches(obs)
                self.assertEqual(specialist["opts_brief"]["skills"], ["complexity-reduction"])
                self.assertEqual(specialist["opts_brief"]["demand"], payload["remedy"]["demand"])

    def test_bo3800a2_interactive_commit_agent_handoff_is_consumed_by_depth0_dispatcher(self):
        # covers: BO-3800a-2
        # angle: discrimination
        # must_catch: ONE ROUTE WIRED: bring the specialist in only from the drive's commit step
        # reachability surface: templates/workflows-js/commit.js executed through unit_tests/_workflow_engine_harness.py
        """Arm 2. Outside any drive, the stubbed commit agent returns the same payload.
        The depth-0 dispatcher engages restructuring-specialist after the refusal and
        before the second commit attempt, in the same position as arm 1. Control row: a
        commit agent that lands its commit engages nobody. RED TODAY: commit.js does
        not exist."""
        payload = self.real_payload()
        # What the drive does with this payload, for the 'same position' comparison.
        obs, _path, _b, _a = self._drive_commit_step("build-feature.js", payload)
        drive_order = [lab for lab in S.labels(obs) if lab in ("commit", S.SPECIALIST)]
        self.assertEqual(drive_order, ["commit", S.SPECIALIST, "commit"])

        self.assertTrue(COMMIT_WORKFLOW.exists(), f"{COMMIT_WORKFLOW} does not exist: no depth-0 dispatcher for /commit")
        refused = E.run_workflow_under_e2(
            COMMIT_WORKFLOW,
            label_responses={"commit": payload, S.SPECIALIST: {"status": "ok"}},
        )
        calls = [c.label or c.agent_type for c in refused.agent_calls]
        relevant = [c for c in calls if c in ("commit", S.SPECIALIST)]
        self.assertEqual(relevant[:3], drive_order, calls)
        self.assertEqual(relevant.count(S.SPECIALIST), 1, calls)
        specialist_call = next(c for c in refused.agent_calls if (c.label or c.agent_type) == S.SPECIALIST)
        self.assertEqual(specialist_call.agent_type, S.SPECIALIST)
        self.assertIn("complexity-reduction", json.dumps(specialist_call.prompt) + json.dumps(specialist_call.opts))
        # presence-only: checks the prompt commit.js built at run time from the real refusal record, not the script's source text
        self.assertIn("plan_batches", json.dumps(specialist_call.prompt) + json.dumps(specialist_call.opts))
        self.assertEqual(refused.contract_violations, [])

        landed = E.run_workflow_under_e2(COMMIT_WORKFLOW, label_responses={"commit": {"status": "ok"}})
        landed_calls = [c.label or c.agent_type for c in landed.agent_calls]
        self.assertEqual([c for c in landed_calls if c in ("commit", S.SPECIALIST)], ["commit"], landed_calls)


if __name__ == "__main__":
    unittest.main()
