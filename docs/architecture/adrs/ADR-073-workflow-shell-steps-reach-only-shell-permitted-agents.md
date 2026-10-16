---
title: "ADR-073: Workflow Shell Steps Reach Only Shell-Permitted Agents, and a Refusal Ends the Run"
description: "Every workflow step that asks an agent to run a shell command, including the one step that obtains a workspace, MUST go to an agent whose config/agent_registry.json entry says permits_shell: true, MUST carry a result schema, and MUST end the run with a quoting error when the agent declines or answers without a result. About sixty workflow dispatches send git, rm, gh and script commands to status-checker, the one agent registered as not permitted to run them, and a refusal is read as an answer, so steps silently fail whenever the model reads its charter strictly."
type: "adr"
status: "active"
created: "2026-10-14"
last_updated: "2026-10-14"
deciders:
  - adr-author
  - architect-review
components:
  - build_orchestration
  - worktree_manager
  - agent_registry
  - supervisor_system
related_docs:
  - docs/architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/components/worktree-manager.md
  - docs/analysis/2026-09-25-worktree-creation-consolidation.md
  - docs/analysis/2026-09-25-worktree-failure-modes.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-3.yaml
related_code:
  - config/agent_registry.json
  - templates/agents/command-step-runner.md
  - templates/agents/worktree-agent.md
  - templates/agents/status-checker.md
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/fast-lane-ship.js
  - scripts/build_phases_workflows.py
  - unit_tests/_workflow_engine_harness.py
---

# ADR-073: Workflow Shell Steps Reach Only Shell-Permitted Agents, and a Refusal Ends the Run

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-14 |
| **Author** | adr-author (dispatched for ticket BO-4300a-1-ia after architect-review) |
| **Supersedes** | None. Adopts [ADR-030](ADR-030-dual-engine-workflow-support.md)'s no-process-access rule for E2 workflow bodies and [ADR-006](ADR-006-flatten-supervisor-chain.md)'s depth-1 dispatch rule without changing either. Applies [ADR-070 §1.3](ADR-070-single-workspace-maker-and-resolver.md#1-exactly-one-maker-creates-locates-lists-verifies-and-removes-workspaces) ("a workflow step MUST NOT hand workspace creation to an agent as free-form shell work") to workflow bodies. |

> Component IDs come from `docs/components.json`. `build_orchestration` owns the
> workflows whose dispatches this ADR binds. `worktree_manager` owns the workspace maker
> that the one workspace dispatch runs. `agent_registry` owns the `permits_shell` field
> the check reads. `supervisor_system` owns the E2 engine contract
> ([ADR-030](ADR-030-dual-engine-workflow-support.md)) that leaves workflow bodies no way
> to run a process themselves.

## Context

Under [ADR-030](ADR-030-dual-engine-workflow-support.md), workflow bodies run in the E2
engine. They have no filesystem access and cannot start a process. Any step that needs a
command run (`git`, `gh`, `rm`, a `python` script, the test suite, or the workspace maker
from [ADR-070](ADR-070-single-workspace-maker-and-resolver.md)) has to be sent to a
depth-1 agent ([ADR-006](ADR-006-flatten-supervisor-chain.md)) with an `agent()` call.
The prompt is the only thing that says what to run.

Two separate defects grew from that.

**Shell work goes to an agent that is registered as not allowed to do it.**
`config/agent_registry.json` gives `status-checker` `permits_shell: false`. It is the
only explicit `false` in the registry. Its template limits it to ticket investigation.
Even so, the workflows send it about sixty dispatches whose prompts run commands.
[KI-BO-20260927-status-checker-runs-workflow-shell-commands](../../known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md)
lists them, verified on 2026-09-25. They include finalize's `git reset --hard HEAD`, its
`git worktree add` and `rm -rf`, plan-feature's `git restore` and `rm -f`, and
build-feature's resolver probes. `status-checker` usually complies. When it reads its
charter strictly, it declines. That has happened at least three times, and one of those
runs ended in a way it could not resume from. The fixes so far have each moved one
failing site to `worktree-agent`, because `worktree-agent` was the only
`permits_shell: true` entry. Its own charter covers only create and remove, so that move
was a stopgap. `command-step-runner` was added later for the fast lane's claim step
(BO-2400a-1-i). It is chartered to run one given command and relay its output unchanged.
No other workflow has adopted it yet. Nothing checks which agent a shell step goes to, so
every new workflow can repeat the mistake. Most agents have no `permits_shell` field at
all, so the registry does not state the answer either.

**A refusal is taken as an answer.** When a dispatched agent declines, or answers in prose
instead of the JSON the step asked for, most call sites read the reply as a real result.
They conclude "no orphans", "branch unknown" or "store absent" and go on to the next step.
The workspace incident of 2026-09-25 had this shape. A workflow body told an agent in its
own words to "open a new git worktree … bootstrap it (copy/symlink .leafcutter …)". It
got back a workspace that was not the one it asked for, and kept going
([consolidation analysis](../../analysis/2026-09-25-worktree-creation-consolidation.md),
[failure modes](../../analysis/2026-09-25-worktree-failure-modes.md) F2, F13).

AC [BO-4300a-1-ia](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml)
(epic EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace) asks for a check covering every step
of every workflow, including steps a single run does not reach. Run against today's tree,
that check fails. Making it pass means deciding which agents may run shell commands. That
is a decision about agent charters, not just an implementation detail. If it is not
recorded, each fix will grant `permits_shell` to whichever agent the failing site
happened to use, and the registry field will stop meaning anything.

## Decision

### 1. Shell permission is a registry fact, and a missing field means "not permitted"

1. An agent is permitted to run shell commands for a workflow if and only if its entry in
   `config/agent_registry.json` has `permits_shell: true`. A missing `permits_shell`
   field, and any value other than the JSON literal `true`, MUST count as not permitted.
2. Whether a workflow step is allowed to go to a given agent MUST be decided only by
   reading that field when the check runs. A workflow, test or helper MUST NOT keep its
   own list of shell-permitted agents.

### 2. Which agents hold `permits_shell: true`, and why

1. **`command-step-runner` is the default executor for workflow shell steps.** Unless
   §2.2 or §2.3 names another agent, every workflow step that runs a shell command MUST go to
   `command-step-runner`, using its request shape (`step`, `command`, `target`) and its
   reply contract (a result carrying `exit_status`, or a decline without one). Its
   `permits_shell: true` stays.
2. **`worktree-agent` runs the workspace maker and nothing else.** Its `permits_shell: true`
   stays because its charter is the workspace lifecycle. From this ADR on, that charter
   means running the maker's command
   ([ADR-070 §1.3](ADR-070-single-workspace-maker-and-resolver.md#1-exactly-one-maker-creates-locates-lists-verifies-and-removes-workspaces))
   exactly as given and relaying its stdout word for word. Workflows MUST NOT send
   `worktree-agent` any other shell step, such as pause-store calls, `git log` or `rm`.
   The sites that went there as stopgaps MUST move to `command-step-runner`.
3. **Grants by charter class.** A phase agent MUST NOT be given a workflow shell step
   because it happened to comply once. An agent MUST gain `permits_shell: true` only when
   two things hold. First, its template already makes running that class of command part
   of its job: `commit` runs `git commit` under the confirmation gate, `test-runner` runs
   the test suite, `pull-request` runs `git push` and `gh pr`. Second, the grant is
   reviewed as a charter change in the same pull request that adds it. Every other shell
   step MUST be moved to `command-step-runner`.
4. **`status-checker` stays `permits_shell: false`.** Every workflow dispatch to
   `status-checker` whose prompt runs a shell command MUST be moved off it. Its read-only
   `Bash` use for its own ticket investigation is not a workflow shell step, and this ADR
   does not change it.
5. **No dispatch is exempted by name.** No exemption list exists. A step that fails the
   check is fixed by moving it (§2.1) or by a grant that meets §2.3.

### 3. A workflow gets its workspace in exactly one of two ways

1. A workflow that needs a workspace MUST get it in one of two ways. (a) It receives
   `args.workspace`, which is the maker's JSON answer passed unchanged by the entry
   command or skill (BO-4300a-1-ib). (b) It issues exactly one dispatch through the
   dispatch helper in the build-inlined `WORKSPACE-ANSWER` block (BO-4300c-3). That
   helper sends the exact absolute maker command and the instruction to run it unchanged
   and relay stdout word for word to `worktree-agent` (§2.2), with the BO-4300c-2 result
   schema attached. The helper MUST name its agent once, and the §5 check MUST still
   confirm that agent holds `permits_shell: true` from the registry.
2. A workflow MUST NOT build its own workspace dispatch or parse the reply itself. A
   dispatched prompt MUST NOT ask any agent to create, copy, set up, link, bootstrap or repair
   a workspace using steps the agent chooses. The free-form prompts in
   `build-feature.js`, `plan-feature.js`, `finalize-feature.js` and `fast-lane-ship.js`
   MUST be removed.
3. When the workspace answer is not accepted, the run MUST NOT fall back to the current
   checkout, the epic folder, the folder it was started from, or any location it did not
   receive in an accepted answer.

### 4. A refusal ends the run, and that rule lives in one shared place

1. Every workflow dispatch whose prompt runs a shell command MUST carry a result schema.
2. The run MUST end with an error in any of these cases: the agent declines, it answers
   in prose, the reply is not JSON, or the reply lacks the result the step asked for
   (for a `command-step-runner` step, no `exit_status`; for the workspace dispatch, no
   `status`). The error MUST quote the reply it received, cut to 2 KB. After such a
   reply, the workflow MUST NOT dispatch any later step. A refusal MUST NOT be treated as
   the step having run.
3. This rule MUST be implemented once, in a shared, build-inlined runtime block used the
   same way as `WORKSPACE-ANSWER`. It MUST NOT be written separately in each workflow, so
   a workflow added later picks it up.
4. A command that ran and exited non-zero is a result, not a refusal. What to do with it
   is the step's own decision.

### 5. One repository-wide check covers every workflow and every agent

1. A test MUST fail when any `agent()` dispatch in any `templates/workflows-js/*.js`
   asks an agent to run a shell command and names an `agentType` that §1 does not count
   as permitted. This includes dispatch sites that a single run never reaches.
2. The test MUST find the workflows by listing that directory, and MUST read the registry
   when it runs. A list of workflows or agents MUST NOT be written into the check.
3. What counts as "a prompt that runs a shell command" MUST be one declared rule, kept in
   one place in the test and reviewed. Example: the prompt, including template-literal
   fragments, contains a command line starting with `git`, `gh`, `python`/`python3`,
   `node`/`npm`, `pytest`, `rm`, `mv`, `cp`, `bash`/`sh` or `pwsh`. The test MUST include
   a self-check showing the rule catches a known `status-checker` `git` dispatch.
4. Every failure MUST name the workflow, the step (dispatch label or location), the
   `agentType`, and the command found.
5. Behaviour MUST be proved by running the DEPLOYED workflow under
   `unit_tests/_workflow_engine_harness.py` with scripted replies, and by checking the
   recorded dispatch list rather than the workflow source text. The harness MUST be able
   to script a decline, a prose answer, a non-JSON answer and a JSON answer without the
   result.

### 6. Commits are not spelled as shell steps

A workflow prompt this ADR touches MUST NOT spell a commit as `git -C <path> commit`
(KI-CG-20260925-commit-delegation-hook-misses-git-dash-c). Commits MUST go through the
`commit` agent, following the Commit Delegation rule in the repository `CLAUDE.md`.

## Consequences

### Positive

- **Refusals stop being intermittent failures.** Shell steps go to agents whose charter
  is to run the command. A charter-based refusal now means a real misroute, and §4
  surfaces it as an error that quotes the reply instead of silently reading it as "empty".
- **`permits_shell` means something again.** It is true for the generic executor, the
  workspace-lifecycle agent and agents chartered for one command class. It is false or
  missing for everything else. The check makes the field enforced, not decorative.
- **New workflows and registry changes are covered automatically.** Workflows are found
  from the directory and the registry is read when the check runs, so nobody has to
  remember to update a list.
- **The 2026-09-25 workspace failure becomes impossible to write.** A workflow body has
  no way to describe a workspace in its own words. It either receives the maker's answer
  or relays the maker's command unchanged.

### Negative

- **The check fails on today's tree, and fixing that is a large change.** About sixty
  `status-checker` dispatches across `plan-feature.js`, `finalize-feature.js`,
  `build-feature.js`, `fast-lane-ship.js`, `build-ticket.js` and `build-epic.js` have to
  move. Callers that used to ask `status-checker` to reshape output into JSON must now do
  that parsing themselves, because `command-step-runner` returns stdout untouched.
- **More dispatches, more cost.** A step that used to combine "run this, then interpret
  it" in one status-checker prompt can become a `command-step-runner` dispatch plus
  parsing in the caller, and sometimes a second dispatch.
- **The shell-command rule is a heuristic.** A prompt that runs a command without naming
  one of the listed programs gets past §5.3 until the rule is extended. The self-check
  proves the rule catches the known case, not every case.
- **Grants need judgment.** §2.3 calls for a reviewed charter change, and that cannot be
  checked mechanically. A careless review can still grant `permits_shell` too widely.

### Operational

- The `worktree-agent` template text ("exactly two actions: create and remove") MUST be
  brought into line with §2.2 when the workspace dispatch moves onto the maker. Until
  then, the stopgap sites still on `worktree-agent` are open items under the KI above.
- The KI-BO-20260927 and KI-BO-20260901-1620 registers close only after the §5 check is
  green on `main`.
- A workflow added after this ADR needs no step to be covered. If it sends a shell step
  to an agent that is not permitted, the check fails, and the fix is §2.1 or §2.3.
- This ADR does not change E2's lack of process access
  ([ADR-030](ADR-030-dual-engine-workflow-support.md) §1). It does not change the depth-1
  topology either ([ADR-006](ADR-006-flatten-supervisor-chain.md)), because
  `command-step-runner` and `worktree-agent` both have an empty `spawn_allowlist`.

## Alternatives

- **Keep moving each failing site to `worktree-agent`.** Rejected. Its charter is create
  and remove. Every pause-store, `git log` or `rm` step sent there is just as outside its
  charter as it was for `status-checker`, so the intermittent refusal moves to a new
  agent instead of going away. The KI's "Pattern" line describes exactly this: one site
  fixed, about forty left live.
- **Set `status-checker` to `permits_shell: true`.** Rejected. Its template keeps it to
  editing ticket files and investigating them read-only. Granting shell for workflow use
  would put repository-mutating commands like `git reset --hard` and `rm -rf` into an
  analysis agent's charter, which is the opposite of what the registry field is for.
- **Grant `permits_shell: true` to every agent that holds `Bash`.** Rejected. The field
  would become identical to the `tools:` list, and the check could no longer tell a
  read-only diagnostic agent from one chartered to change the repository.
- **Exempt known sites by name in the check.** Rejected. An exemption list is a
  hand-maintained list, which is what the AC forbids. It would also turn the roughly
  sixty current violations into permanent, approved debt that later workflows copy.
- **Let workflow bodies run commands directly.** Rejected. E2 gives workflow bodies no
  process access ([ADR-030](ADR-030-dual-engine-workflow-support.md)), so this is not
  available. Running commands through a build-time E1 shim would also split behaviour
  between engines, which ADR-030 §4 forbids.
- **Check refusals in each workflow, next to each call.** Rejected. That is the
  hand-copy pattern that produced
  `KI-BO-20260925-finalize-gate-accepts-agent-answers`, and the precedent `BO-3900` blocks
  have already drifted apart. Only a single shared block guarantees that a new workflow
  inherits the rule.
- **Check only the workspace dispatch.** Rejected. The workspace step is one of about
  sixty shell-running dispatches with the same misrouting defect. Checking only that one
  leaves the other refusal points live.

## References

- Originating ticket:
  `tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02_TICKET-20260927-BO-4300a-1-ia.md`
  (AC [BO-4300a-1-ia](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml)).
- Related ACs: BO-4300a-1-ib (`args.workspace` from the entry command), BO-4300c-2 (maker
  result contract), [BO-4300c-3](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-3.yaml)
  (`WORKSPACE-ANSWER` block), BO-2400a-1-i (`command-step-runner`).
- [ADR-070](ADR-070-single-workspace-maker-and-resolver.md): the one workspace maker.
- [ADR-030](ADR-030-dual-engine-workflow-support.md): E2 workflow bodies have no process access.
- [ADR-006](ADR-006-flatten-supervisor-chain.md): depth-1 dispatch from workflows.
- [KI-BO-20260927-status-checker-runs-workflow-shell-commands](../../known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md),
  [KI-BO-20260901-1620](../../known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md).
