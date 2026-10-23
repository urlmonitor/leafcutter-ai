---
title: "ADR-070: One Narrow shell-runner Runs Workflow Shell Commands, and a Reply That Is Not a Result Ends the Run"
description: "Every workflow step that gives an agent a shell command line goes to shell-runner, a new agent whose only job is to run that one command unchanged and pass its output back word for word. The one exception is the fast lane's command steps, which stay with command-step-runner. A lint over the registry's permits_shell field enforces this. A decline, prose or result-less reply ends the run and quotes what came back. No existing agent's charter changes: each permits_shell grant would be a charter change, and the E2 engine gives workflow bodies no way to run a process themselves."
type: "adr"
status: "active"
created: "2026-10-12"
last_updated: "2026-10-12"
deciders:
  - BrainCandy
components:
  - build_orchestration
  - agent_registry
related_docs:
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/architecture/adrs/ADR-018-agent-isolation-topology.md
  - docs/architecture/adrs/worktree-maker-amendment-1-2026-09-27.md
  - docs/architecture/components/agent-registry.md
  - docs/architecture/components/build-orchestration.md
  - docs/analysis/2026-09-25-worktree-creation-consolidation.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md
  - docs/known-issues/build-orchestration/open-blocker-ki-bo-20260925-finalize-gate-accepts-agent-answers.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-3-i.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-3-ii.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400a-1-i.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-5-i.yaml
related_code:
  - config/agent_registry.json
  - config/agent_registry.schema.json
  - templates/agents/command-step-runner.md
  - templates/agents/status-checker.md
  - templates/agents/worktree-agent.md
  - scripts/build_phases_workflows.py
  - unit_tests/_workflow_engine_harness.py
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/quick-fix.js
---

# ADR-070: One Narrow shell-runner Runs Workflow Shell Commands, and a Reply That Is Not a Result Ends the Run

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-12 |
| Deciders | BrainCandy (user decision 2026-09-28 (b), recorded in the epic's `Master_Plan.md`, "Re-cut 2026-09-28") |
| Author | adr-author |
| Supersedes | — |
| Relates to | [ADR-006](ADR-006-flatten-supervisor-chain.md) (depth model), [ADR-030](ADR-030-dual-engine-workflow-support.md) (E2 authoring contract), [ADR-018 Amendment 1](worktree-maker-amendment-1-2026-09-27.md) A1.2 (one workspace maker). This ADR amends none of them. |

## Context

This decision serves ticket 10 of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`
(`10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md`), covering AC
[BO-4300a-1-ia](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml)
and the [BO-4300c-3](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-3.yaml) family.

### A workflow body cannot run a command itself

Under [ADR-030](ADR-030-dual-engine-workflow-support.md) every workflow is an E2 top-level
body. The engine injects `agent`, `parallel`, `args` and a few other globals, but gives the
body no `require`, no filesystem and no subprocess
([KI-BO-20260901-1620](../../known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md)
item 3). So every `git`, `gh`, `python`, `rm` or `pytest` a workflow needs runs inside an
agent the workflow dispatches at depth 1 ([ADR-006](ADR-006-flatten-supervisor-chain.md)).
The only open choice is which agent gets the command line.

### Command lines went to agents whose charters exclude them

On main at `93bd801c`, about 40 shell dispatches across six workflows go to
`status-checker`
([KI-BO-20260927](../../known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md)),
the one registry entry that says `permits_shell: false`. Other shell steps go to
`worktree-agent`, whose charter covers create and remove only, or to `python-coder`. These
agents read their charters and decline by judgement, so refusals are intermittent. Recorded
refusals include `pause-persist` (the run ended `pause_persist_failed` and could not be
resumed), the read-only `git log` of `scan-committed-stages`, and the fast lane's context
bundle, which `python-coder` declined in both recorded runs that got that far.

### A refusal was then treated as success (the 2026-09-25 incident)

The incident is recorded in
[the consolidation analysis](../../analysis/2026-09-25-worktree-creation-consolidation.md)
§1 and in the notes of BO-4300c-3-i and BO-4300c-3-ii. A `/plan-feature` run was started
from the workspace parent folder. Then:

1. `status-checker` refused the workspace resolver on charter grounds.
2. The workflow did not halt. It sent a different command, the path-resolution command, to
   `worktree-agent`.
3. That command exited 0 and printed a script path. `JSON.parse` threw, the exception was
   caught, and the workspace path stayed `null`.
4. The run carried on in its "no workspace" mode. The product owner wrote `INF-1400*` ACs,
   untracked, into the main checkout on `main`.

Three defects compound here: the wrong recipient, a different command substituted after the
decline, and a parse failure read as "no workspace needed".

### The cheap fix was refused, and the user chose a narrow agent

BO-4300a-1-ia's repo-wide lint went red on its first run (failed run, 2026-09-28): 17
dispatches across the eight workflows. The AC allows two remedies: (1) move the dispatch to
an agent with `permits_shell: true`, or (2) grant `permits_shell: true` to an agent that
"genuinely runs shell by charter", with that charter change reviewed. `python-coder`
refused the grant route because every grant is a charter change, and architect-review
agreed. The user then decided (2026-09-28, (b)): **one new narrow agent with
`permits_shell: true` that runs one exact command and relays its output verbatim. Every
shell-running workflow step moves to it, and no existing agent's charter changes.**

### A narrow executor already exists, but only for the fast lane

`command-step-runner`
([BO-2400a-1-i](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400a-1-i.yaml),
PR #942, merged on main 2026-09-28) already runs one given command and returns its output
untouched, but its charter only covers a workspace the run has **already opened**: every
request must carry the target `{workspace, branch, ac_id}`, and one without it is declined.
[BO-2400f-5-i](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-5-i.yaml)
(active) requires every fast-lane command step to go to it and to no other agent. Two kinds
of step therefore cannot go to it without a charter change: the workspace step, which runs
the maker from [ADR-018 Amendment 1](worktree-maker-amendment-1-2026-09-27.md) A1.2
**before** any workspace exists, because it is the step that obtains one; and steps that
run in the main copy, such as finalize's sync and its `gh` probes.

### The cost of not deciding

Every new workflow step would pick its recipient by hand, and every caller would parse
replies its own way. The incident path would stay open in every workflow that has not
failed yet, the pattern
[KI-BO-20260925-finalize-gate-accepts-agent-answers](../../known-issues/build-orchestration/open-blocker-ki-bo-20260925-finalize-gate-accepts-agent-answers.md)
records for hand-copied helpers.

## Decision

### 1. A new agent, `shell-runner`, runs workflow shell commands

1.1 **Charter.** `templates/agents/shell-runner.md` MUST hold one role: run one given
command line once, unchanged, and relay what it produced. llm-expert authors the charter.
The agent MUST NOT decide, interpret, plan, retry or substitute anything.

1.2 **Input.** A dispatch to `shell-runner` MUST carry exactly two things: one command
line with absolute paths, and the instruction to run it unchanged and relay its output
verbatim. It MUST NOT carry a goal, background, a fallback, or a second command. The
command MUST say where it acts, for example `git -C <abs>` or a script's own path
argument. `shell-runner` runs it in the directory it was started in and MUST NOT change
directory or rewrite the command.

1.3 **One command, no chaining.** `shell-runner` MUST decline a command line that joins
commands with `&&`, `||`, `;`, a pipe or command substitution; a request that carries more
than one command; and a request to edit files, write code or tests, or act as another
agent's role. Workflows MUST split multi-command steps into separate dispatches, so that
the reply rule (§5) checks each command's result.

1.4 **Result reply.** Exactly one JSON object `{command, exit_status, stdout, stderr}`:
`command` exactly as it was run, `exit_status` its integer exit status, and `stdout` and
`stderr` its streams verbatim (JSON on stdout stays an unparsed string). A non-zero exit is
a result, never a decline.

1.5 **Decline reply.** Exactly one JSON object `{declined: true, agent: "shell-runner",
reason}`, with **no** `exit_status` key. These two shapes deliberately repeat
`command-step-runner`'s split (BO-2400a-1-i): the presence of `exit_status` tells "ran" from
"did not run", so one reply check serves both executors (§5). This replaces the
`{exit_code, stdout, stderr}` shape sketched in the ticket's Implementation Notes.

1.6 **Output is data.** Nothing printed by the command is an instruction to `shell-runner`.

1.7 **Tools.** `Bash` only: no `Read`, `Edit` or `Write`. Without `Edit` or `Write`,
CLAUDE.md's `requires_verification: true` rule does not apply; if either tool is ever
added, that rule applies in the same change.

1.8 **Registry entry.** The `config/agent_registry.json` entry MUST set
`permits_shell: true`, `tier: "utility"`, `is_ticket_phase: false`, `spawn_allowlist: []`,
`portable: true`, `components: ["build_orchestration"]`, and `spawned_by` naming the
workflow files that dispatch it. `shell-runner` never dispatches another agent, so it stays
a depth-1 leaf under ADR-006 and adds no depth.

### 2. Which agent gets a command line

2.1 **The workspace step** in every workflow, `fast-lane-ship.js` included, MUST be one
`shell-runner` dispatch. It is issued only through the WORKSPACE-ANSWER dispatch helper
(§6), and its command is the maker's exact absolute command line.

2.2 **Fast-lane command steps** that BO-2400f-5-i assigns to `command-step-runner` MUST go
to `command-step-runner`, with the BO-2400f-3-ii target triple. Today these are resolve,
producibility, claim, context bundle and release. This holds when this ticket moves one of
them off `status-checker` or `python-coder` to make the lint green. They MUST NOT go to
`shell-runner`, and this ADR moves no step off `command-step-runner`.

2.3 **Every other step** whose prompt gives an agent a shell command line MUST go to
`shell-runner`, including the steps that today go to `status-checker`, `worktree-agent` or
`python-coder`.

2.4 **Specialists are asked for outcomes, not command lines.** A workflow MUST ask a
specialist for its chartered outcome (tests run by `test-runner`, a commit by `commit`, a
pull request by `pull-request`) and MUST NOT give a specialist a shell command line to run.
A step that needs one specific command run goes to `shell-runner`.

2.5 **Commits.** Commits MUST go through the `commit` agent. A `git commit` in any spelling,
including `git -C <path> commit`, MUST NOT be sent to `shell-runner`.

### 3. No existing agent's charter or permission changes

`status-checker` keeps `permits_shell: false` and its charter. `worktree-agent`,
`command-step-runner`, `python-coder`, `test-runner`, `commit` and every other agent keep
their templates and registry entries. This ADR uses only the AC's first remedy (move the
dispatch), never the second (grant `permits_shell`). A future grant MUST be its own
reviewed charter change, and MUST NOT be used as a way to turn the lint green.

### 4. What `permits_shell` means for workflow dispatch, and the lint that enforces it

4.1 **Meaning.** A workflow step whose prompt gives an agent a shell command line MUST
target an agent whose registry entry has `permits_shell: true`, whether the command only
reads or also mutates, because read-only steps were refused too (`scan-committed-stages`).
A missing field counts as not permitted. `config/agent_registry.schema.json` describes the
field in terms of repository-mutating commands only; for workflow dispatch, this ADR's
broader reading governs.

4.2 **The lint.** `unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py` enforces §2
and §4.1. It MUST:

- enumerate `templates/workflows-js/*.js` at test time with a shallow glob, so `_shared/`
  is not treated as a workflow, and read `config/agent_registry.json` at test time;
- hold one declared rule, kept in one place in the test, for "a prompt that runs a shell
  command": the prompt, including template-literal fragments, names a command line that
  starts with `git`, `gh`, `python`/`python3`, `node`/`npm`, `pytest`, `rm`, `mv`, `cp`,
  `bash`/`sh` or `pwsh`;
- check every dispatch site statically, including sites a single run never reaches, and
  report each violation by workflow, step label or location, `agentType` and command;
- carry a self-check fixture: a `status-checker` `git reset --hard` dispatch and a python
  dispatch to an agent with no `permits_shell` field MUST both be reported, and the same
  prompts sent to a permitted agent MUST NOT be.

No dispatch is exempted by name, and no workflow list or agent list is hard-coded, so a new
workflow, or a changed registry entry, is covered without editing the test.

### 5. A reply that is not a result ends the run

5.1 **One check first.** Every reply to a shell-running dispatch, from `shell-runner` or
from `command-step-runner`, MUST pass one shared reply check before any of its fields is
used. The reply passes only if it is one JSON object with no `declined` marker, an integer
`exit_status`, and string `stdout` and `stderr`.

5.2 **Failure ends the run.** A decline, prose, non-JSON output, an empty reply or no
reply, or a reply without the result the step asked for MUST end the run with status
`error`. The error message MUST quote the reply received, up to 2 KB.

5.3 **No later step, no substitute, no fallback.** After such a reply the workflow MUST NOT
dispatch any later step, MUST NOT send the same or a different command to the same or
another agent, and MUST NOT continue in the current checkout, the epic folder, the folder
it was started from, or any location that did not come from an accepted answer.

5.4 **Non-zero exit is a result.** A non-zero `exit_status` passes §5.1. The step's own
caller decides what it means; for the workspace step, the acceptance predicate (§6.2)
decides.

### 6. Shared runtime code reaches workflow bodies only by build-time inlining

6.1 **One tracked source.** The shared reply check (§5), the workspace acceptance predicate
and the workspace dispatch helper MUST live in one tracked source,
`templates/workflows-js/_shared/workspace-answer.js`. That folder is outside the shallow
`*.js` glob that deploys workflows.

6.2 **Acceptance predicate.** The predicate MUST accept a workspace answer only if the
relayed `stdout` parses as a single JSON object whose `status == "ok"` and whose
`workspace_path` is a non-empty string. This is the BO-4300c-2 answer contract, applied to
the relayed stdout. Any other answer is `{accepted: false, reason, received}`, with
`received` bounded to 2 KB. A parse failure MUST NOT be caught and turned into "no
workspace".

6.3 **Dispatch helper.** The helper MUST issue exactly one `agent()` call to `shell-runner`,
carrying the maker command (§2.1) and the shell-runner reply schema. The schema requires
no key, so a decline reaches the §5 check instead of failing inside the engine;
`fast-lane-ship.js`'s claim schema is the precedent. No workflow builds its own workspace
dispatch or its own reply parsing.

6.4 **Markers and the build.** Each consuming template carries only the marker pair
`// WORKSPACE-ANSWER-START` / `// WORKSPACE-ANSWER-END`. `scripts/build_phases_workflows.py`
MUST fill the pair from the source before config-placeholder injection, with
compare-before-write idempotency so that a second build writes nothing. The build MUST fail
if a template's marker pair already holds text, or if the source is missing. E2 bodies
still have no `require` (ADR-030): inlining happens at build time only.

6.5 **Parity and coverage on the deployed workflows.** In every deployed workflow, the text
between the markers MUST be byte-identical to the source. Every workflow that consumes a
workspace, or issues a shell-running dispatch, MUST carry the block and route that
dispatch's reply through its check. The set of consuming workflows is derived, never
listed.

## Consequences

### Positive

- **Picking the recipient becomes mechanical.** `shell-runner` has no other role to protect,
  so the "outside my role" refusal class disappears for workflow shell steps. The lint
  catches any dispatch that goes elsewhere.
- **The incident path is closed in every workflow at once.** A decline cannot be followed by
  a substitute command, a script path printed with exit 0 cannot be read as "no workspace",
  and the run cannot fall back to the main checkout. All three rules live in one inlined
  block that the build keeps identical everywhere.
- **New workflows inherit the rules.** The lint enumerates the directory and reads the
  registry at test time. The block's coverage set is derived. Nobody edits a list.
- **No charter churn.** No existing agent's role widens, so no grant has to be argued
  agent by agent.
- **One reply shape for both executors.** `shell-runner` and `command-step-runner` share
  the result/decline split, so one check serves both.

### Negative

- **Two narrow executors with near-identical contracts.** `shell-runner` and
  `command-step-runner` coexist, alongside `worktree-agent`'s `permits_shell` for its own
  lifecycle work, and readers must know the fast-lane boundary in §2.2. Merging the two
  needs its own decision: a charter change to `command-step-runner`, or an amendment to
  BO-2400a-1-i and BO-2400f-5-i.
- **More dispatches.** Compound commands become several dispatches. `finalize-feature.js`
  alone moves about 20 `status-checker` steps, some of which chain several commands. Each
  extra dispatch is another agent turn, with its latency and cost.
- **Runs end more often, and visibly.** Steps that "worked" because their parsing was
  tolerant now end the run with a quoted error. A transient refusal ends the run by design.
  Recovery uses each workflow's existing resume path.
- **Interpretation moves to the caller.** A step that asked `status-checker` to "check and
  report X" must now parse raw `stdout` in the workflow.
- **The lint is lexical.** A prompt that describes a command in prose without naming its
  command line escapes the lint. A prompt that only quotes a command can be a false
  positive. Both risks sit in one reviewed rule rather than in per-site judgement.
- **Existing tests change.** The test harness's default reply for an unscripted dispatch
  stops being a success. Tests that relied on that default must script their replies. Tests
  that assert on the agent or label of a moved step must be re-pointed. None may be skipped.

### Operational

- **Registry and docs.** A new registry entry, a row in `docs/agents/README.md`, and a card at
  `docs/agents/utility/shell-runner.md`, following `add-agent-to-package` steps 3-6 and
  `build.py --validate-only`. `spawned_by` names workflow files. The external-caller set in
  `templates/scripts/commit_guardian/agent_spawn_external_callers.py` is derived from the
  workflow directory, so those names validate.
- **Build.** `scripts/build_phases_workflows.py` gains the inliner. A hand-filled marker
  pair is now a build failure, not a deploy.
- **Schema description follow-up.** The `permits_shell` description in
  `config/agent_registry.schema.json` still speaks of repository-mutating commands only. It
  should be aligned with §4.1 in a change that owns that file. Until then this ADR governs
  workflow dispatch.
- **Out of scope here.** Moving the BO-3900 `PATH-HELPERS` blocks onto the same inliner is a
  follow-up. Taking the workspace location only from `workspace_path` in `fast-lane-ship.js`
  and `build-ticket.js` belongs to BO-4300c-4 (ticket 11).

## Alternatives

- **Grant `permits_shell: true` to the agents that already receive shell steps**
  (`status-checker`, `python-coder`, `test-runner`, `commit`). Rejected. Each grant is a
  charter change, which `python-coder` and architect-review refused. The flag also leaves
  unchanged the template text the agent reads before it declines, so the judgement-based
  refusals that caused the incident would continue.
- **Keep `worktree-agent` as the shell stopgap** (the PR #896 pattern). Rejected. Its
  charter is "exactly two actions: create and remove", so `pause_store.py`, `git log` and
  `rm` are outside it, and it declines on the same grounds `status-checker` does; the KI
  records it as a stopgap, not the answer.
- **Generalise `command-step-runner` into the one executor.** Rejected. Its charter requires
  an already-opened workspace, a branch and an AC id, and it declines a request without
  them. The workspace step runs before any workspace exists and the main-copy steps have no
  AC id, so taking either would be a charter change, which decision (b) excludes.
- **Retire `command-step-runner` and move fast-lane command steps to `shell-runner`.**
  Rejected. BO-2400a-1-i (done) and BO-2400f-5-i (active) bind those steps to
  `command-step-runner` and to no other agent, and nine test modules name it, among them
  `test_bo2400a_1_i_command_step_runner.py` and
  `test_bo2400f_7_iii_claim_refusal_workflow.py`. All of it lies outside this ticket's files.
- **Run the commands from the workflow body.** Rejected. The E2 engine gives the body no
  subprocess or filesystem access (ADR-030; KI-BO-20260901-1620 item 3), so this cannot be
  built.
- **Exempt known dispatches by name, or lint against hard-coded lists.** Rejected.
  BO-4300a-1-ia forbids exemption by name. A list does not cover a workflow added after it
  was written, which is the gap the lint exists to close.
- **Retry, or send a substitute command, after a decline.** Rejected. Substitution is steps
  2 and 3 of the 2026-09-25 incident: the substitute exited 0 with a path, and the run
  continued without a workspace. BO-4300c-3-ii requires the decline to end the run.
- **Hand-copy the check and helper into each workflow, or import them at run time.**
  Rejected. Hand copies drift: the BO-3900 `PATH-HELPERS` markers already hold different
  text in `build-feature.js` and `plan-feature.js`, and the finalize gate KI is the same
  failure. A run-time import is impossible because E2 bodies have no `require` (ADR-030).
- **Relay mode: the reply is the command's stdout itself, with the BO-4300c-2 answer schema
  as the dispatch schema.** Rejected. The engine would validate inside `agent()`, before the
  workflow sees the reply, so a decline would surface as an engine failure rather than as a
  quotable reply. Generic shell steps also need `exit_status`, so the workspace step would
  need a second reply shape and a second check.
- **A `shell-runner`-specific `{exit_code, stdout, stderr}` shape** (the ticket's sketch).
  Rejected. `command-step-runner` already uses `exit_status` with a decline that has no exit
  key. A second spelling of the same fact would force the shared check to accept both.

## References

- Ticket: `tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md`
- Epic decision: `tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/Master_Plan.md`, "Re-cut 2026-09-28", (b)
- Answer contract: BO-4300c-2 (ticket 03); the maker: [ADR-018 Amendment 1](worktree-maker-amendment-1-2026-09-27.md) A1.2
- Fast-lane executor: `templates/agents/command-step-runner.md`; BO-2400a-1-i, BO-2400f-3-ii, BO-2400f-5-i, BO-2400f-5-iii
- Starting point for the tests (re-verify, never apply wholesale): `refs/wip/bo4300-attempt1`

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-12 [adr-author]: Initial creation (Proposed) for ticket 10 of
  EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace. The ticket expected
  ADR-050; that number was taken on main by
  ADR-050-runtime-reachability-guard-refuses-not-warns, so this record
  takes 069, the first number scripts/adr_refs.py reports unclaimed.
  Records user decision 2026-09-28 (b) and resolves its overlap with
  command-step-runner (BO-2400a-1-i, merged the same day) by the
  section 2.2 fast-lane boundary. Tightened the same day to fit the
  400-line ADR limit (bullet lists folded into prose); no decision,
  consequence, alternative or cross-reference changed.
====================================================================
-->
