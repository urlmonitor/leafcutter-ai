"""
MODULE: unit_tests/build_orchestration/test_bo4500a_4_one_answer_contract.py
GOAL: BO-4500a-4 -- every call of the shared commit step ends in ONE machine-readable
      answer (answer_version 1) with one of four statuses, whose vocabulary is read
      from config/commit_step.json and never from the step's code.

Every test runs the REAL script (templates/scripts/commit_changes.py) as a subprocess
against a REAL scratch git repository and parses its REAL standard output.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _bo4500a3_support import PACKAGE_CONFIG, ran_checks, run_count  # noqa: E402
from _bo4500a4_support import (  # noqa: E402
    CONFIG_ENV,
    CONTRACT_KEYS,
    FAMILIES,
    JUDGE_FAILS,
    STEP,
    StepScenario,
    complexity_scenario,
    four_outcomes,
    install_checks,
    load_vocabulary,
    run_in,
    scenario3,
    write_config_copy,
)
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_NEVER_SETTLES = 'ran format-py\necho "formatted $n" > a.py\nreport format-py Failed\necho "- files were modified by this hook"\nexit 1\n'
_ROUTE_JS = (
    "const reply = await agent(args.prompt, { label: 'commit-step', agentType: 'command-step-runner' });\n"
    "const text = typeof reply === 'string' ? reply : (reply && reply.stdout);\n"
    "return JSON.parse(text);\n"
)


def _one_object(case: unittest.TestCase, proc, where: str) -> dict:
    """Parse stdout as exactly one JSON object, failing the test with context otherwise."""
    try:
        answer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        case.fail(f"{where}: stdout is not exactly one JSON object: {proc.stdout!r} stderr={proc.stderr[-300:]!r}")
    case.assertIsInstance(answer, dict, where)
    return answer


class TestOneAnswerContract(unittest.TestCase):
    def test_each_outcome_prints_exactly_one_json_object_on_stdout(self):
        # covers: BO-4500a-4
        # angle: criterion
        """Four real calls print one JSON object each, nothing before or after, versioned."""
        for status, proc in four_outcomes(self).items():
            with self.subTest(outcome=status):
                answer = _one_object(self, proc, status)
                self.assertEqual(proc.stdout.strip().count("\n"), 0, "stdout holds more than one line")
                self.assertTrue(proc.stdout.startswith("{") and proc.stdout.endswith("}\n"), repr(proc.stdout))
                self.assertEqual(answer.get("status"), status, answer)
                self.assertEqual(answer.get("answer_version"), 1, "answer_version 1 missing from the answer")

    def test_every_answer_carries_every_contract_key(self):
        # covers: BO-4500a-4
        # angle: criterion
        """All 17 keys are always present; sha/hook_name/failing_files filled only when they apply."""
        for status, proc in four_outcomes(self).items():
            with self.subTest(outcome=status):
                answer = _one_object(self, proc, status)
                self.assertEqual(set(answer), set(CONTRACT_KEYS), "the answer's keys differ from the contract")
                committed, failed = status == "committed", status == "hook_failed"
                if committed:
                    self.assertRegex(answer["sha"] or "", r"^[0-9a-f]{40}$")
                    self.assertEqual(answer["paths"], ["a.py"])
                else:
                    self.assertIsNone(answer["sha"])
                    self.assertEqual(answer["paths"], [])
                self.assertEqual(answer["hook_name"], "judge-py" if failed else None)
                self.assertEqual(answer["failing_files"], ["a.py"] if failed else [])
                self.assertEqual(answer["reason_code"] is None, committed, "reason_code is null iff committed")
                self.assertEqual(answer["reason"] is None, committed, "reason is null iff committed")
                self.assertEqual((answer["run"], answer["ac_id"]), (None, None))
                self.assertEqual(answer["answer_version"], 1)
                if status == "refused":
                    self.assertTrue((answer["reason"] or "").strip(), "a refused answer needs a reason in words")
        vocabulary = load_vocabulary(self)
        self.assertEqual(set(vocabulary["answer_keys"]), set(CONTRACT_KEYS), "config answer_keys differ from the contract")
        self.assertEqual(vocabulary["answer_version"], 1)

    def test_every_non_committed_answer_has_a_reason_code_from_its_family(self):
        # covers: BO-4500a-4
        # angle: discrimination
        """Refusals carry policy_/step_ codes from the config families; lock != policy, protected branch != step.

        Wrong versions caught: a refused answer with reason text but no reason_code; an
        index-lock failure coded as a policy refusal; a protected-branch refusal coded as
        a step failure (checked in the config partition, where the step reads it from).
        """
        families = json.loads(PACKAGE_CONFIG.read_text(encoding="utf-8")).get("reason_codes", {})
        fixtures = {}
        sc = scenario3(self)
        fixtures["no_paths"] = (sc.run_raw(["--message-file", str(sc.message_file)]), "refused", "policy_no_explicit_paths", "policy")
        fixtures["not_found"] = (sc.run_raw(["--message-file", str(sc.message_file), "nope.py"]), "refused", "policy_path_not_found", "policy")
        fixtures["no_message"] = (sc.run_raw(["a.py"]), "refused", "policy_message_missing", "policy")
        lock = scenario3(self)
        (lock.repo / ".git" / "index.lock").write_text("", encoding="utf-8")
        (lock.repo / ".git" / "refs" / "heads" / "feature").mkdir(parents=True, exist_ok=True)
        (lock.repo / ".git" / "refs" / "heads" / "feature" / "x.lock").write_text("", encoding="utf-8")
        fixtures["index_locked"] = (lock.run_raw(["--message-file", str(lock.message_file), "a.py"]), "refused", "step_index_locked", "step")
        bare = StepScenario(self)
        bare.write("a.py", "a\n")
        plain = bare.scratch / "not_a_repo"
        plain.mkdir()
        fixtures["vcs_error"] = (run_in(plain, bare.env, ["--message-file", str(bare.message_file), "a.py"]), "refused", "step_vcs_error", "step")
        hook = scenario3(self)
        install_checks(hook, JUDGE_FAILS)
        fixtures["check_failed"] = (hook.run_raw(["--message-file", str(hook.message_file), "a.py"]), "hook_failed", "check_failed", "check")
        quiet = StepScenario(self)
        quiet.seed_and_commit({"a.py": "a\n"})
        fixtures["nothing"] = (quiet.run_raw(["--message-file", str(quiet.message_file), "a.py"]), "nothing_to_commit", "nothing_changed", "nothing")
        for name, (proc, status, code, family) in fixtures.items():
            with self.subTest(fixture=name):
                answer = _one_object(self, proc, name)
                self.assertEqual(answer.get("status"), status, answer)
                self.assertTrue(answer.get("reason_code"), f"{status} answer without a reason_code: {answer}")
                self.assertEqual(answer["reason_code"], code, answer)
                self.assertIn(answer["reason_code"], families.get(family, []), "code is not in its family in config")
                self.assertEqual([f for f in FAMILIES if answer["reason_code"] in families.get(f, [])], [family])
        families = load_vocabulary(self)["reason_codes"]
        every = [code for f in FAMILIES for code in families[f]]
        self.assertEqual(len(every), len(set(every)), "a reason_code sits in two families")
        self.assertEqual(families["nothing"], ["nothing_changed"])
        self.assertIn("policy_protected_branch", families["policy"])
        self.assertNotIn("policy_protected_branch", families["step"])
        self.assertIn("step_index_locked", families["step"])
        self.assertNotIn("step_index_locked", families["policy"])

    def test_hook_failed_remedy_equals_remedy_handoff_builder_output(self):
        # covers: BO-4500a-4
        # angle: seam
        """An engage-specialist check's remedy/handoff equal remedy_handoff.py's output; undeclared -> null."""
        sc = complexity_scenario(self)
        sc.git("add", "scripts/planner.py")

        produced = subprocess.run([sys.executable, "scripts/commit_guardian/check_complexity.py"], cwd=sc.repo, env=sc.env, capture_output=True, text=True, check=False)
        sc.git("reset", "-q")
        self.assertIn("COMPLEXITY_REFUSAL_RECORD:", produced.stdout)
        oracle = subprocess.run([sys.executable, "scripts/commit_guardian/remedy_handoff.py", "--hook-id", "check-complexity"], cwd=sc.repo, env=sc.env, input=produced.stdout, capture_output=True, text=True, check=False)
        self.assertEqual(oracle.returncode, 0, oracle.stderr)
        expected = json.loads(oracle.stdout)

        answer = sc.run_step(["scripts/planner.py"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(answer.get("reason_code"), "check_failed", answer)
        self.assertEqual(answer.get("handoff"), expected)
        self.assertEqual(answer.get("remedy"), expected["remedy"])
        self.assertEqual(set(expected["remedy"]), {"hook_id", "disposition", "skills", "demand"})
        self.assertEqual(set(answer), set(CONTRACT_KEYS), "the seam answer is not in the one contract shape")
        undeclared = scenario3(self)
        install_checks(undeclared, JUDGE_FAILS)
        plain = undeclared.run_step(["a.py"])
        self.assertEqual(plain.get("status"), "hook_failed", plain)
        self.assertEqual((plain.get("remedy"), plain.get("handoff")), (None, None))
        self.assertEqual(plain.get("answer_version"), 1)

    def test_plain_command_harness_gets_the_same_answer_as_a_workflow_route(self):
        # covers: BO-4500a-4
        # angle: reachability
        """A bare subprocess and a workflow route's command step yield answers equal except sha.

        No workflow route calls the step yet, and the E2 sandbox has no subprocess: a route
        reaches a command only through an agent()/command-step-runner call. So: (1) the
        fixture route is run under the harness to record the command it dispatches; (2) that
        recorded command is executed for real, as the runner would; (3) the route is run
        again with the command's real stdout as the runner's reply and returns its parse.
        """
        plain_sc, route_sc = scenario3(self), scenario3(self)
        plain = plain_sc.run_step(["a.py"])
        command = [sys.executable, str(STEP), "--message-file", str(route_sc.message_file), "a.py"]
        prompt = "COMMAND: " + shlex.join(command)
        script = route_sc.scratch / "route.js"
        script.write_text(_ROUTE_JS, encoding="utf-8")
        recorded = run_workflow_under_e2(script, args={"prompt": prompt})
        self.assertEqual(recorded.error, "", f"harness could not run the fixture route: {recorded.error}")
        self.assertEqual(recorded.dispatch_count, 1, "the route must dispatch exactly one command step")
        dispatched = recorded.agent_calls[0].prompt
        self.assertIn(str(STEP), dispatched, "the route's command step does not run the commit step")
        ran = run_in(route_sc.repo, route_sc.env, shlex.split(dispatched.split("COMMAND: ", 1)[1])[2:])
        routed = run_workflow_under_e2(script, args={"prompt": prompt}, label_responses={"commit-step": {"stdout": ran.stdout}})
        self.assertEqual(routed.error, "", routed.error)
        self.assertIsInstance(routed.result, dict, f"the route consumed no answer: stdout={routed.stdout!r} stderr={routed.stderr[-300:]!r}")
        self.assertEqual(set(routed.result), set(plain), "route and plain answers differ in keys")
        self.assertEqual({k: v for k, v in routed.result.items() if k != "sha"}, {k: v for k, v in plain.items() if k != "sha"})
        self.assertEqual(plain.get("answer_version"), 1, "the shared answer is not the versioned contract")
        self.assertRegex(routed.result["sha"] or "", r"^[0-9a-f]{40}$")

    def test_crash_before_answer_leaves_stdout_empty(self):
        # covers: BO-4500a-4
        # angle: failure
        """With git unrunnable, or its repository unusable, stdout is empty or one refused step_vcs_error."""
        broken = {"no_git_on_path": {"PATH": "/nonexistent-bin"}, "unusable_git_dir": {"GIT_DIR": "/nonexistent-git-dir"}}
        for name, changes in broken.items():
            with self.subTest(failure=name):
                sc = scenario3(self)
                proc = run_in(sc.repo, {**sc.env, **changes}, ["--message-file", str(sc.message_file), "a.py"])
                self.assertNotIn("Traceback", proc.stdout)
                self.assertEqual(sc.commit_count(), 1, "a commit was recorded despite the failure")
                if not proc.stdout.strip():
                    continue
                answer = _one_object(self, proc, name)
                self.assertEqual(answer.get("status"), "refused", answer)
                self.assertEqual(answer.get("reason_code"), "step_vcs_error", answer)
                self.assertTrue((answer.get("reason") or "").strip(), "the error is not quoted in reason")

    def test_contract_vocabulary_is_read_from_config_not_code(self):
        # covers: BO-4500a-4
        # angle: seam
        """Against a disposable config copy: new key/code/version flow through; ceiling 1; missing file refuses."""
        base = json.loads(PACKAGE_CONFIG.read_text(encoding="utf-8"))
        with self.subTest(arm="a_new_key_and_code_and_version"):
            sc = scenario3(self)
            families = base.get("reason_codes", {})
            codes = {**families, "step": [*families.get("step", []), "step_probe_code"]}
            write_config_copy(sc, answer_keys={**base.get("answer_keys", {}), "extra_probe_key": None}, reason_codes=codes, answer_version=2)
            answer = sc.run_step(["a.py"])
            self.assertEqual(answer.get("status"), "committed", answer)
            self.assertIn("extra_probe_key", answer, "the step does not read answer keys from config")
            self.assertIsNone(answer.get("extra_probe_key"))
            self.assertEqual(answer.get("answer_version"), 2, "answer_version is not read from config")
        with self.subTest(arm="b_ceiling_1_stops_a_never_settling_fixer_after_one_retry"):
            sc = scenario3(self)
            write_config_copy(sc, max_automated_fix_retries=1)
            install_checks(sc, _NEVER_SETTLES)
            answer = sc.run_step(["a.py"])
            self.assertEqual(run_count(sc), 2, "expected the first run plus exactly one retry")
            self.assertEqual(ran_checks(sc), ["format-py", "format-py"])
            self.assertEqual((answer.get("status"), answer.get("reason_code")), ("hook_failed", "check_unsettled"))
        for arm, make in (("c_missing_file", None), ("c_empty_object", "{}"), ("c_not_json", "not json")):
            with self.subTest(arm=arm):
                sc = scenario3(self)
                path = sc.scratch / "gone.json"
                if make is not None:
                    path.write_text(make, encoding="utf-8")
                sc.env[CONFIG_ENV] = str(path)
                answer = sc.run_step(["a.py"])
                self.assertEqual(answer.get("status"), "refused", answer)
                self.assertEqual(answer.get("reason_code"), "step_config_unreadable", answer)
                self.assertEqual(sc.commit_count(), 1, "the step committed with an unreadable config")
                self.assertTrue(re.search(r"\S", answer.get("reason") or ""), "no reason given")


if __name__ == "__main__":
    unittest.main()
