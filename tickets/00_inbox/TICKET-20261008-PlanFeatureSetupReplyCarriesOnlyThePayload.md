---
title: "/plan-feature worktree setup keeps bootstrap output out of the setup agent's reply"
status: todo
components:
  - build_orchestration
  - worktree_manager
created: 2026-10-08
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - plan-feature
  - worktree-setup
  - agent-relay
  - bo-1500
last_updated: 2026-10-08
files_touched:
  - templates/workflows-js/plan-feature.js
  - unit_tests/workflows/test_plan_feature_setup_reply_payload_only.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# /plan-feature worktree setup keeps bootstrap output out of the setup agent's reply

## Actor / Goal
In order that `/plan-feature` starts on its first run in a project, not only on a re-run, we
need the worktree-setup step to keep the bootstrap's long progress output away from the agent
that relays the setup result, so that the reply the workflow parses holds the one JSON line and
nothing that can push it out.

## Context
- **Observed 2026-10-07, run `wf_bfcfe2c8-006`.** On a first run, `create-ac-worktree` creates a
  NEW authoring worktree. Its bootstrap prints tens of thousands of characters: git checkout
  progress, the pip install and the build output. Since BO-1500a-1-ii that output is on stderr
  and stdout holds only the JSON payload. The setup agent (Haiku `worktree-agent`) still
  reported both streams. It also cut its reply off with "... (FULL JSON RESPONSE SAVED TO FILE)"
  before the JSON line. So even BO-1500a-5-iii's last-line parse found no payload, and the run
  halted with `setup_failure_kind` `no_workspace_named`. A re-run with the worktree already
  present succeeds, because the reuse path prints little.
- **Why the agent relays stderr.** The dispatch prompt asks for it. In
  `templates/workflows-js/plan-feature.js` (:2491-2496):
  `"Run the following command and return ONLY the raw stdout output:\n" + worktreeSetupCommand + "\n" + "Return JSON: { \"output\": \"<raw stdout line>\", \"exit_code\": <number>, \"stderr\": \"<stderr or empty>\" }"`.
  The reply is required to carry the full stderr, so its size grows with the bootstrap. Any
  relaying model then truncates or summarises it.
- **The command** is built at :2484-2487:
  `python "<resolved setup_ticket_worktree.py>" create-ac-worktree "<slug>"`, with no redirection.
- **Related ACs (all done):** BO-1500a-1-ii (the command's stdout holds only the JSON),
  BO-1500a-5-i (uninterpretable replies halt), BO-1500a-5-iii (parse the last non-empty line).
  Each was correct for the shape it saw. None of them bounds the reply's size.
- **Size.** `plan-feature.js` measures 2959 lines against the 1000-line `.js` limit, so the change
  must leave the file shorter than at HEAD.

## Acceptance Criteria
- [ ] AC-1: The worktree-setup command the workflow dispatches redirects the setup script's
  stderr to a log file whose path contains the run id. The file lives in a git-ignored runtime
  folder of the repository the run works in, and the dispatched command text names that path.
- [ ] AC-2: The setup dispatch prompt no longer asks the agent to return stderr. The reply
  carries the stdout JSON line and the exit code only. The workflow's halt and success messages
  name the log file path.
- [ ] AC-3: A setup script stub that prints 60,000 characters to stderr and then its JSON line to
  stdout, run through the real dispatch prompt and parse path, gives a reply the workflow
  adopts. The run goes on to dispatch its first authoring agent with that `worktree_path`.
- [ ] AC-4: When the setup command exits non-zero, the halt payload names the log file and
  quotes its last 20 lines, which the workflow reads back through a separate bounded dispatch.
  The failure stays diagnosable without stderr in the reply.
- [ ] AC-5: The re-run path (worktree already present) and every BO-1500a-5-i / -5-iii halt case
  behave as before. Their existing tests pass unchanged.

## Test Requirements

```yaml
tests:
  - name: test_setup_command_redirects_stderr_to_run_log
    location: unit_tests/workflows/test_plan_feature_setup_reply_payload_only.py
    type: unit
    covers: [AC-1, AC-2]
    description: |
      Capture the worktree-setup dispatch prompt: the command redirects stderr to a path holding
      the run id, and the prompt no longer requests a stderr field.
  - name: test_large_bootstrap_stderr_does_not_reach_the_reply
    location: unit_tests/workflows/test_plan_feature_setup_reply_payload_only.py
    type: integration
    covers: [AC-3]
    description: |
      A stub setup script prints 60,000 characters on stderr and the JSON payload on stdout;
      the run adopts worktree_path and dispatches its first authoring agent.
  - name: test_failed_setup_halt_names_log_and_quotes_tail
    location: unit_tests/workflows/test_plan_feature_setup_reply_payload_only.py
    type: unit
    covers: [AC-4]
    description: |
      Exit code 1 from the stub: the halt payload names the log path and quotes its last lines.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_setup_command_redirects_stderr_to_run_log | | |
| AC-2 | test_setup_command_redirects_stderr_to_run_log | | |
| AC-3 | test_large_bootstrap_stderr_does_not_reach_the_reply | | |
| AC-4 | test_failed_setup_halt_names_log_and_quotes_tail | | |
| AC-5 | existing BO-1500a-5-i / -5-iii tests | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Build the setup command with `2> "<log path>"`. The quoting must work in the shell the
  `worktree-agent` uses on Windows (Git Bash) and Linux.
- [ ] Drop the `stderr` field from the reply contract and name the log path in the messages.
- [ ] On a non-zero exit, read back the log's last lines through a separate bounded dispatch.
- [ ] Tests above. Keep `plan-feature.js` shorter than at HEAD.

## Design Notes
An alternative to AC-1 is for the setup script to write its payload to a file the workflow reads
back (`--payload-file`). That removes the relay from the success path entirely, but it changes
`setup_ticket_worktree.py`'s CLI and its two copies. Choose it only if the redirection cannot be
made portable. Either way the agent must never be asked to relay unbounded output.

## Risk & Safety
- Touches money? No.
- Touches data? Writes one log file per run into a git-ignored runtime folder.
- Reversibility: revert the commit.

## Out of Scope
- Other `worktree-agent` dispatches that ask for "raw stdout" of short commands
  (`plan-feature.js` :610, :832, :1138, :1374, :2242, :2312). Their output is small and bounded.
- Shrinking the bootstrap's own output.
