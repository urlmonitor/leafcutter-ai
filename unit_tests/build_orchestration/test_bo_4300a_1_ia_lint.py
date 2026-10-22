"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
AC: BO-4300a-1-ia -- "No workflow body asks an agent to make a workspace in
    its own words" (second Given/When/Then: the repo-wide shell-dispatch
    permission lint).
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    02_TICKET-20260927-BO-4300a-1-ia.md

WHAT THIS PROVES: every `agent()` dispatch in every templates/workflows-js/
*.js whose prompt instructs the agent to run a shell command names an
agentType whose config/agent_registry.json entry declares
`permits_shell: true` -- including dispatch sites a single harness run does
not reach (a STATIC source-text scan, never a runtime drive). Split out of
test_bo_4300a_1_ia.py (which holds the harness-DRIVEN tests) to keep each
file under the 400-line ratchet and because this file needs no Node.js
subprocess at all.

Sourced from this AC's own test_spec (docs/acceptance-criteria/
build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml), entries
5 and 6 -- see test_bo_4300a_1_ia.py's own module docstring for the AC
Coverage map across both files.

RED BASELINE (2026-09-28, test-writer; re-authored 2026-10-12 for ticket 10): test_every_shell_running_dispatch_...
is expected RED today -- the blast-radius note in this AC's own
it_requirements records 62 dispatches to status-checker (permits_shell:
false) and several RELEASE_EXECUTOR_AGENT_TYPE ("python-coder", no
permits_shell field at all) shell-running dispatches in
fast-lane-ship.js alone. test_shell_dispatch_lint_catches_a_status_checker_
git_dispatch is a pure self-check of this file's own detection rule against
synthetic fixture text (no real file read) and is expected to pass on its
own terms today -- it is not a RED-baseline entry for the AC's production
fix, only a correctness proof of the rule test_every_shell_running_dispatch_
... relies on. It is included here because the AC's own test_spec requires
it ("the test carries a self-check proving the rule catches a known
status-checker git dispatch").
"""
from __future__ import annotations

import unittest

from unit_tests.build_orchestration._bo_4300a_1_ia_fixtures import (
    cwd_relative_maker_hits,
    TEMPLATE_WORKFLOWS_DIR,
    list_deployed_workflow_files,
    load_agent_registry,
    shell_dispatch_violations,
    shell_permitted_agent_ids,
)

_KNOWN_BAD_STATUS_CHECKER_GIT_DISPATCH = """
const result = await agent(
  `Run this single Bash command from the repository root:\\n` +
  `   git reset --hard\\n`,
  { agentType: "status-checker", label: "reset-step" }
);
"""

_KNOWN_BAD_UNREGISTERED_PYTHON_DISPATCH = """
const result2 = await agent(
  `Run this single Bash command:\\n` +
  `   python3 scripts/some_script.py\\n`,
  { agentType: "unregistered-agent", label: "python-step" }
);
"""

_SAME_PROMPTS_TO_A_PERMITTED_AGENT = """
const result3 = await agent(
  `Run this single Bash command from the repository root:\\n` +
  `   git reset --hard\\n`,
  { agentType: "worktree-agent", label: "reset-step-safe" }
);
const result4 = await agent(
  `Run this single Bash command:\\n` +
  `   python3 scripts/some_script.py\\n`,
  { agentType: "worktree-agent", label: "python-step-safe" }
);
"""

_FIXTURE_PERMITTED_IDS = {"worktree-agent"}


class TestBO4300a1iaShellDispatchLint(unittest.TestCase):
    def test_every_shell_running_dispatch_in_every_workflow_targets_a_shell_permitted_agent(self):
        # covers: BO-4300a-1-ia
        # angle: seam
        """AC's second Given/When/Then: EVERY templates/workflows-js/*.js
        agent() dispatch whose prompt runs a shell command must name an
        agentType with permits_shell: true in config/agent_registry.json,
        read at test time -- no hard-coded workflow or agent list (both
        list_deployed_workflow_files() and shell_permitted_agent_ids() read
        real, current, on-disk sources). Includes dispatch sites a single
        run does not reach (this is a source-text scan, not a harness run).
        Each violation is reported by workflow, step, agentType and command.
        """
        workflow_files = list_deployed_workflow_files(TEMPLATE_WORKFLOWS_DIR)
        self.assertGreater(
            len(workflow_files), 0, "no workflow files found under templates/workflows-js/"
        )
        permitted = shell_permitted_agent_ids(load_agent_registry())

        violations = []
        for wf_path in workflow_files:
            source = wf_path.read_text(encoding="utf-8")
            violations.extend(shell_dispatch_violations(source, wf_path.name, permitted))

        self.assertEqual(
            violations,
            [],
            msg=(
                f"{len(violations)} shell-dispatch permission violation(s) found across "
                f"{[p.name for p in workflow_files]}: {violations}"
            ),
        )

    def test_shell_dispatch_lint_catches_a_status_checker_git_dispatch(self):
        # covers: BO-4300a-1-ia
        # angle: failure
        """Self-check (required by this AC's own test_spec): fed a fixture
        workflow that asks status-checker to run `git reset --hard`, and one
        that asks an agent with no permits_shell field to run a python
        script, the rule reports BOTH, each naming workflow/step/agentType/
        command; fed the SAME prompts dispatched to worktree-agent (a
        permits_shell: true agent) it reports NEITHER.
        """
        bad_source = _KNOWN_BAD_STATUS_CHECKER_GIT_DISPATCH + _KNOWN_BAD_UNREGISTERED_PYTHON_DISPATCH
        bad_violations = shell_dispatch_violations(bad_source, "fixture-bad.js", _FIXTURE_PERMITTED_IDS)

        self.assertEqual(
            len(bad_violations),
            2,
            msg=f"expected exactly 2 violations (status-checker + unregistered-agent), got: {bad_violations}",
        )
        reported_agents = {v["agent_type"] for v in bad_violations}
        self.assertEqual(reported_agents, {"status-checker", "unregistered-agent"})
        for violation in bad_violations:
            self.assertEqual(violation["workflow"], "fixture-bad.js")
            self.assertIn("git" if violation["agent_type"] == "status-checker" else "python3", violation["command"])
            self.assertTrue(violation["step"])

        good_violations = shell_dispatch_violations(
            _SAME_PROMPTS_TO_A_PERMITTED_AGENT, "fixture-good.js", _FIXTURE_PERMITTED_IDS
        )
        self.assertEqual(
            good_violations,
            [],
            msg=f"the SAME prompts dispatched to a permits_shell:true agent must report nothing: {good_violations}",
        )

        # ADR-070: the new narrow executor is shell-permitted in the REAL
        # registry (read at test time), so the same prompts sent to it are
        # clean. Red until shell-runner has a permits_shell: true entry.
        real_permitted = shell_permitted_agent_ids(load_agent_registry())
        self.assertIn("shell-runner", real_permitted, msg="config/agent_registry.json has no permits_shell: true entry for shell-runner")
        to_shell_runner = _SAME_PROMPTS_TO_A_PERMITTED_AGENT.replace("worktree-agent", "shell-runner")
        self.assertEqual(
            shell_dispatch_violations(to_shell_runner, "fixture-shell-runner.js", real_permitted),
            [],
            msg="the SAME prompts dispatched to shell-runner must report nothing against the real registry",
        )

    def test_no_template_runs_the_maker_by_a_cwd_relative_path(self):
        # covers: BO-4300a-1-ib
        # angle: criterion
        """A scan of EVERY text file under templates/ (.md .js .mjs .py .yaml .json; no folder is skipped) finds no
        `python(3) scripts/worktree.py` (or .leafcutter/-prefixed) spelling, no output-root-relative maker
        command and no unquoted maker path: every maker command is the absolute, quoted form."""
        templates = TEMPLATE_WORKFLOWS_DIR.parent
        files = [
            p for p in sorted(templates.rglob("*")) if p.is_file() and p.suffix in {".md", ".js", ".mjs", ".py", ".yaml", ".json"}
        ]
        self.assertGreater(len(files), 0, "no template files found to scan")
        hits = []
        for path in files:
            hits.extend(cwd_relative_maker_hits(path.relative_to(templates).as_posix(), path.read_text(encoding="utf-8")))
        self.assertEqual(hits, [], msg=f"{len(hits)} cwd-relative maker spelling(s):\n" + "\n".join(hits))

    def test_maker_lint_exempts_nothing_and_still_catches_relative_paths(self):
        # covers: BO-4300a-1-ib
        # angle: discrimination
        """Control: a relative `python3 .leafcutter/scripts/worktree.py`, a bare `python3 worktree.py` and an
        output-root-relative maker command are reported in ANY file (shared block included); the absolute, quoted
        form is not."""
        shared = "workflows-js/_shared/workspace-answer.js"
        for rel in ("workflows-js/build-epic.js", shared, "agents/worktree-agent.md"):
            for bad in (
                "python3 .leafcutter/scripts/worktree.py ensure --kind epic --slug x",
                "python3 worktree.py ensure --kind epic --slug x",
                "python3 {{config.output_root}}/scripts/worktree.py ensure --kind epic",
            ):
                self.assertEqual(len(cwd_relative_maker_hits(rel, bad)), 1, msg=f"{rel}: {bad}")
        absolute = 'python3 "/abs/proj/.leafcutter/scripts/worktree.py" ensure --kind epic --slug "x"'
        self.assertEqual(cwd_relative_maker_hits(shared, absolute), [])

    def test_maker_lint_covers_every_templates_folder_and_the_docs_absolute_forms(self):
        # covers: BO-4300a-1-ib
        # angle: failure
        """Control: a cwd-relative maker command in templates/workflows/*.md (a folder the scan once missed) is
        caught, as is an UNQUOTED absolute or placeholder maker path; the quoted absolute forms the docs use
        (`"<absolute-install-root>/scripts/worktree.py"`, `"<project root>/.leafcutter/scripts/worktree.py"`) are not."""
        close_worktree = "workflows/close-worktree.md"
        for bad in (
            "python scripts/worktree.py remove --path x",
            "python3 .leafcutter/scripts/worktree.py remove --path x",
            "python <absolute-install-root>/scripts/worktree.py ensure --kind ticket",
            "python /abs/proj/.leafcutter/scripts/worktree.py ensure --kind ticket",
            "python <project root>/.leafcutter/scripts/worktree.py ensure --kind scratch",
        ):
            self.assertEqual(len(cwd_relative_maker_hits(close_worktree, bad)), 1, msg=bad)
        for good in (
            'python "<absolute-install-root>/scripts/worktree.py" ensure --kind ac --slug "<slug>" --repo-root "<absolute-project-root>"',
            'python "<project root>/.leafcutter/scripts/worktree.py" ensure --kind scratch --slug "base"',
        ):
            self.assertEqual(cwd_relative_maker_hits(close_worktree, good), [], msg=good)


if __name__ == "__main__":
    unittest.main()
