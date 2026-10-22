"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
AC: BO-4300a-1-ia -- "No workflow body asks an agent to make a workspace in
    its own words." (ticket 10). Harness-DRIVEN tests over the DEPLOYED
    workflows (built by the real build phase); the repo-wide static lint lives
    in test_bo_4300a_1_ia_lint.py. Shared helpers: _bo_4300c_3_fixtures.py
    (pinned contract: workspace step = one "workspace-ensure" dispatch to
    shell-runner, reply {command, exit_status, stdout, stderr}).

The workspace-consuming set is derived from the deployed workflows (floor:
REQUIRED_CONSUMERS), never listed. Replies to non-workspace shell steps are
scripted explicitly; the harness no longer answers unscripted dispatches with
success.

RED BASELINE (2026-10-12): all red -- build-feature.js still sends the
free-form 'Open a NEW git worktree ... Bootstrap it' prompt, no workflow
dispatches the maker via a shared block, and ~40 shell dispatches go to
agents without permits_shell.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ia_fixtures import (
    FIXTURE_COMMON_DIR_STDOUT,
    MARKER_LABEL,
    RELATIVE_MAKER_SPELLING,
    RESOLVE_LABEL,
    TEMPLATE_WORKFLOWS_DIR,
    UNANCHORED_BRANCH_COMMAND,
    all_shell_dispatch_violations,
    free_form_workspace_phrase,
    list_deployed_workflow_files,
    load_agent_registry,
    maker_command_defects,
    maker_command_line,
    marker_reply,
    shell_permitted_agent_ids,
    workspace_branch_results,
)
from unit_tests._workflow_engine_harness import run_workflow_under_e2
from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    REQUIRED_CONSUMERS,
    WORKSPACE_LABEL,
    consuming_workflows,
    deployed_workflow_names,
    deployed_workflows_dir,
    extract_between_markers,
    hostile_reply,
    ok_maker_answer,
    run_scenario,
    scenario_inputs,
    shell_result,
    terminal,
    terminal_text,
    workspace_calls,
)

_NODE_RUNNER = """
const fs = require('fs'), vm = require('vm');
const [src, names] = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const calls = [];
const ctx = { agent: async (prompt, opts) => { calls.push({ prompt, opts: opts || null }); return null; },
              args: {}, log() {}, console };
vm.createContext(ctx);
(async () => {
  vm.runInContext(src + '\\n;globalThis.__fns = {' + names.map(n => n + ': typeof ' + n + " === 'function' ? " + n + ' : undefined').join(',') + '};', ctx);
  for (const n of names) {
    const fn = ctx.__fns[n];
    if (!fn) continue;
    try { await fn('@@CMD@@'); } catch (e) { /* try the next candidate */ }
    if (calls.length) break;
  }
  process.stdout.write(JSON.stringify(calls[0] || null));
})();
"""


def _consumers() -> tuple[str, ...]:
    found = consuming_workflows()
    assert set(REQUIRED_CONSUMERS) <= set(found), f"consuming workflows {found}; required {REQUIRED_CONSUMERS}"
    return found


def _helper_dispatch(block: str) -> dict | None:
    """Evaluate the WORKSPACE-ANSWER block in Node with a recording agent() and
    call each function declared in it with a sentinel command; return the first
    dispatch it records (found by behaviour, not by function name)."""
    names = re.findall(r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", block)
    names += re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()", block)
    with tempfile.TemporaryDirectory(prefix="bo4300a1ia-node-") as tmp:
        payload = Path(tmp, "in.json")
        payload.write_text(json.dumps([block, names]), encoding="utf-8")
        runner = Path(tmp, "run.js")
        runner.write_text(_NODE_RUNNER, encoding="utf-8")
        proc = subprocess.run(["node", str(runner), str(payload)], capture_output=True, text=True, timeout=30)
    return json.loads(proc.stdout) if proc.stdout.strip() else None


class TestBO4300a1iaWorkspaceDispatch(unittest.TestCase):
    def test_each_workflow_receives_answer_or_issues_one_verbatim_maker_request(self):
        # covers: BO-4300a-1-ia
        # angle: criterion
        """No args.workspace: exactly one workspace dispatch = exact maker
        command + verbatim-relay instruction. With args.workspace: none."""
        failures = []
        for name in _consumers():
            baseline = workspace_calls(run_scenario(name, hostile_reply("ok")))
            if len(baseline) != 1:
                failures.append(f"{name}: {len(baseline)} workspace dispatches without args.workspace")
            else:
                prompt = baseline[0].prompt or ""
                if "worktree.py" not in prompt or "ensure" not in prompt:
                    failures.append(f"{name}: dispatch does not carry the maker command: {prompt[:160]!r}")
                if not re.search(r"verbatim|unchanged", prompt, re.I):
                    failures.append(f"{name}: dispatch lacks a verbatim/unchanged relay instruction")
            given = workspace_calls(run_scenario(name, args_extra={"workspace": ok_maker_answer()}))
            if given:
                failures.append(f"{name}: args.workspace supplied but {len(given)} workspace dispatch(es) issued")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_no_dispatch_asks_an_agent_to_build_a_workspace_by_its_own_steps(self):
        # covers: BO-4300a-1-ia
        # angle: criterion
        """Across every deployed workflow's harness run (ready answer scripted
        for the one workspace step), no recorded prompt asks for create/copy/
        set-up/link/repair of a workspace outside the one maker command."""
        hits = []
        for name in deployed_workflow_names():
            result = run_scenario(name, hostile_reply("ok"))
            for call in result.agent_calls:
                if call.label == WORKSPACE_LABEL:
                    continue
                phrase = free_form_workspace_phrase(call.prompt)
                if phrase:
                    hits.append((name, call.label, phrase))
        self.assertEqual(hits, [], msg=f"free-form workspace instruction (workflow, label, phrase): {hits}")
        self.assertTrue(set(REQUIRED_CONSUMERS) <= set(_consumers()))

    def test_workspace_requests_only_reach_shell_permitted_agents(self):
        # covers: BO-4300a-1-ia
        # angle: boundary
        """Every workspace dispatch targets an agent whose registry entry has
        permits_shell: true (registry read at test time), for each consumer."""
        permitted = shell_permitted_agent_ids(load_agent_registry())
        offenders = []
        for name in _consumers():
            calls = workspace_calls(run_scenario(name, hostile_reply("ok")))
            if len(calls) != 1:
                offenders.append((name, "no single workspace dispatch", len(calls)))
            offenders += [(name, c.label, c.agent_type) for c in calls if c.agent_type not in permitted]
        self.assertEqual(offenders, [], msg=f"(workflow, label, agentType): {offenders}")

    def test_every_deployed_workflow_is_covered_without_editing_a_list(self):
        # covers: BO-4300a-1-ia
        # angle: seam
        """Enumeration is directory-derived: adding a file extends it; the
        deployed set equals the template set; the same scan finds no violation."""
        with tempfile.TemporaryDirectory(prefix="bo4300a1ia-enum-") as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "existing.js").write_text("// noop\n", encoding="utf-8")
            before = {p.name for p in list_deployed_workflow_files(tmp)}
            (tmp / "brand-new.js").write_text("// noop\n", encoding="utf-8")
            after = {p.name for p in list_deployed_workflow_files(tmp)}
        self.assertEqual((before, after), ({"existing.js"}, {"existing.js", "brand-new.js"}))
        self.assertEqual({p.name for p in list_deployed_workflow_files(deployed_workflows_dir())},
                         {p.name for p in list_deployed_workflow_files(TEMPLATE_WORKFLOWS_DIR)})
        violations = all_shell_dispatch_violations(deployed_workflows_dir())
        self.assertEqual(violations, [], msg=f"{len(violations)} violation(s): {violations[:5]}")

    def test_refused_non_workspace_shell_step_ends_the_workflow_with_a_quoting_error(self):
        # covers: BO-4300a-1-ia
        # angle: failure
        """A NON-workspace shell step (fast-lane resolve-connected, plan-feature
        detect-current-branch), scripted to decline / answer in prose / answer
        without the requested result: the run ends status error quoting the
        scripted reply and nothing is dispatched after it. A ready workspace
        answer is supplied via args.workspace so the step is reached."""
        replies = {
            "decline": {"declined": True, "agent": "shell-runner", "reason": "TOKEN-decline outside my role"},
            "prose": "Sure, ran it, all looks fine. TOKEN-prose",
            "no_result": {"note": "TOKEN-no_result attempted"},
        }
        failures = []
        for name, step in (("fast-lane-ship.js", "resolve-connected"), ("plan-feature.js", "detect-current-branch")):
            for case, reply in replies.items():
                result = run_scenario(name, args_extra={"workspace": ok_maker_answer()},
                                      extra_labels={step: reply, MARKER_LABEL: marker_reply()})
                labels = [c.label for c in result.agent_calls]
                if step not in labels:
                    failures.append(f"{name}/{case}: step {step!r} never dispatched: {labels}")
                    continue
                term = terminal(result)
                # BO-4300a-1-ia (amended): a plain error, OR -- where a more
                # specific rule classifies the refusal (fast lane's
                # BO-2400f-5-iii declined step) -- that rule's halt, which
                # must carry its own classification/halt_kind.
                declined_halt = (
                    name == "fast-lane-ship.js"
                    and term.get("status") == "halt"
                    and term.get("classification") == "halt"
                    and term.get("halt_kind") == "declined_step"
                )
                if term.get("status") != "error" and not declined_halt:
                    failures.append(f"{name}/{case}: status {term.get('status')!r}")
                if f"TOKEN-{case}" not in terminal_text(result):
                    failures.append(f"{name}/{case}: terminal payload does not quote the reply")
                if labels[-1] != step:
                    failures.append(f"{name}/{case}: dispatches after the refused step: {labels}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_workspace_dispatch_goes_through_the_shared_block_helper(self):
        # covers: BO-4300a-1-ia
        # angle: criterion
        """The recorded workspace dispatch (prompt, agentType, schema) is what
        the block's own helper produces for the same command: the block is run
        in Node with a recording agent(), then the recorded dispatch must match
        its prompt template (command slot filled), agentType and schema."""
        failures = []
        for name in _consumers():
            block = extract_between_markers((deployed_workflows_dir() / name).read_text(encoding="utf-8"))
            if block is None:
                failures.append(f"{name}: no WORKSPACE-ANSWER block")
                continue
            produced = _helper_dispatch(block)
            calls = workspace_calls(run_scenario(name, hostile_reply("ok")))
            if produced is None or len(calls) != 1:
                failures.append(f"{name}: helper produced {produced!r}; recorded {len(calls)} workspace dispatches")
                continue
            parts = str(produced["prompt"]).split("@@CMD@@")
            pattern = "(.+?)".join(re.escape(p) for p in parts[:2]) + "".join(
                (r"\1" + re.escape(p)) for p in parts[2:]) if len(parts) > 1 else re.escape(parts[0])
            if not re.fullmatch(pattern, calls[0].prompt or "", re.S):
                failures.append(f"{name}: recorded prompt is not the helper's prompt for its command")
            helper_opts = produced.get("opts") or {}
            for key in ("agentType", "schema"):
                recorded = (calls[0].opts or {}).get(key)
                if recorded != helper_opts.get(key):
                    failures.append(f"{name}: {key} differs from the helper's ({recorded!r} vs {helper_opts.get(key)!r})")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_every_workflow_dispatches_the_maker_by_an_absolute_quoted_path(self):
        # covers: BO-4300a-1-ia
        # angle: deployed
        """M13: each consumer, run from a fixture project (the maker-path probe is scripted to answer that
        project's git common dir), sends every maker command (ensure, and verify of a handed-in location) as
        `python "<abs>/scripts/worktree.py" <verb> ...` with every --slug/--path/--ticket value quoted. At
        least one maker command is seen per consumer, and none is cwd-relative."""
        # consumer_drift: a handed-in location's project comes from its marker (one more probe step), not the cwd.
        probe = {RESOLVE_LABEL: shell_result(FIXTURE_COMMON_DIR_STDOUT), MARKER_LABEL: marker_reply()}
        given = ok_maker_answer()
        failures = []
        for name in _consumers():
            runs = {
                "ensure": run_scenario(name, hostile_reply("ok"), extra_labels=probe),
                "verify": run_scenario(
                    name, args_extra={"workspace_path": given["workspace_path"]},
                    extra_labels={**probe, "workspace-verify": shell_result(json.dumps(given))}),
            }
            for kind, result in runs.items():
                commands = [c for c in (maker_command_line(call.prompt) for call in result.agent_calls) if c]
                if not commands:
                    failures.append(f"{name}/{kind}: no maker command was dispatched: {[c.label for c in result.agent_calls]}")
                for command in commands:
                    failures += [f"{name}/{kind}: {why}: {command!r}" for why in maker_command_defects(command)]
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_no_deployed_workflow_spells_the_maker_relative_or_unanchored(self):
        # covers: BO-4300a-1-ia
        # angle: deployed
        """M13/M16 over every deployed workflow source (the sites a single run does not reach: finalize's
        remove, plan-feature's two fallback branch checks, the verify fallback): no relative maker spelling
        (`python3 {{config.output_root}}/scripts/worktree.py` etc.), and no dispatched `git branch
        --show-current` that names no location."""
        hits = []
        for path in list_deployed_workflow_files(deployed_workflows_dir()):
            for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if RELATIVE_MAKER_SPELLING.search(line):
                    hits.append(f"{path.name}:{no}: relative maker spelling: {line.strip()[:110]}")
                if UNANCHORED_BRANCH_COMMAND.search(line):
                    hits.append(f"{path.name}:{no}: branch check names no location: {line.strip()[:110]}")
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_branch_check_transport_failure_ends_the_run(self):
        # covers: BO-4300a-1-ia
        # angle: deployed
        """M16 / ADR-070 5.2: the deployed plan-feature.js, with the detect-current-branch dispatch REJECTING
        (no reply at all), ends status error with nothing dispatched after it. The command it sent is
        `git -C "<absolute project>" branch --show-current`. The rejection is injected by a prefix shim on a
        copy of the deployed script (the harness's agent() mock cannot throw); the shim records the call first."""
        shim = (
            "{ const __orig = agent; agent = async function (p, o) { const r = await __orig(p, o);"
            " if (o && o.label === 'detect-current-branch') throw new Error('TOKEN-transport'); return r; }; }\n"
        )
        source = (deployed_workflows_dir() / "plan-feature.js").read_text(encoding="utf-8")
        labels, wf_args = scenario_inputs("plan-feature.js")
        labels[RESOLVE_LABEL] = shell_result(FIXTURE_COMMON_DIR_STDOUT)
        labels["detect-current-branch"] = shell_result("feature-x\n")
        with tempfile.TemporaryDirectory(prefix="bo4300a1ia-throw-") as tmp:
            copy = Path(tmp, "plan-feature.js")
            copy.write_text(shim + source, encoding="utf-8")
            result = run_workflow_under_e2(copy, timeout=90, label_responses=labels, args=wf_args)
        labels_seen = [c.label for c in result.agent_calls]
        self.assertIn("detect-current-branch", labels_seen, msg=f"step never dispatched: {labels_seen}")
        self.assertEqual(labels_seen[-1], "detect-current-branch", msg=f"dispatches after the failed step: {labels_seen}")
        self.assertEqual(terminal(result).get("status"), "error", msg=f"terminal: {result.result!r}")
        sent = next(c.prompt for c in result.agent_calls if c.label == "detect-current-branch")
        self.assertRegex(str(sent), r'git -C "(?:/|[A-Za-z]:)[^"]+" branch --show-current')

    def test_refused_verify_of_handed_in_location_stops_the_run(self):
        # covers: BO-4300a-1-ia
        # angle: failure
        """M5 caller re-check: build-feature.js handed a location, with the verify dispatch answering
        refused/VERIFY_FAILED: status error quoting the answer, and no dispatch after the verify."""
        refusal = shell_result(json.dumps({"status": "refused", "code": "VERIFY_FAILED", "message": "TOKEN-vf"}), 2)
        result = run_scenario(
            "build-feature.js", args_extra={"workspace_path": ok_maker_answer()["workspace_path"]},
            extra_labels={RESOLVE_LABEL: shell_result(FIXTURE_COMMON_DIR_STDOUT), MARKER_LABEL: marker_reply(),
                          "workspace-verify": refusal})
        labels = [c.label for c in result.agent_calls]
        self.assertIn("workspace-verify", labels)
        self.assertEqual(labels[-1], "workspace-verify", msg=f"dispatches after the refused verify: {labels}")
        self.assertEqual(terminal(result).get("status"), "error")
        self.assertIn("TOKEN-vf", terminal_text(result))

    def test_workspace_branch_reads_top_level_branch_then_marker_branch(self):
        # covers: BO-4300a-1-ia
        # angle: boundary
        """M5: the deployed block's workspaceBranch returns the top-level `branch` when present (also when a
        marker disagrees), the marker's branch otherwise, and "" when neither names one."""
        name = _consumers()[0]
        block = extract_between_markers((deployed_workflows_dir() / name).read_text(encoding="utf-8"))
        self.assertIsNotNone(block, msg=f"{name}: no WORKSPACE-ANSWER block")
        got = workspace_branch_results(block, [
            {"branch": "top-level", "marker": {"branch": "from-marker"}},
            {"marker": {"branch": "from-marker"}},
            {"branch": "only-top"},
            {"marker": {}},
        ])
        self.assertEqual(got, ["top-level", "from-marker", "only-top", ""])


if __name__ == "__main__":
    unittest.main()
