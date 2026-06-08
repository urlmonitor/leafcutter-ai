---
title: "Agent Code Delivery Workflows"
description: "Visualises how the leafcutter-ai agent ecosystem orchestrates code delivery — slash-command entry points, supervisor dispatch topology, quick-fix workflow, and blocker adjudication flows."
type: "reference"
status: "active"
created: "2026-05-11"
last_updated: "2026-06-08"
flight_level: "L3-Component"
diagram_type: agent_flow
components:
  - "infrastructure"
tags:
  - "agents"
  - "workflows"
  - "slash commands"
  - "supervisor"
related_docs:
  - "docs/agents/README.md"
  - "docs/architecture/adrs/ADR-010-agent-supervisor-signoff-pattern.md"
  - "docs/superpowers/specs/2026-05-08-agent-supervisor-design.md"
related_agents:
  - "leafcutter/templates/agents/epic-supervisor.md"
  - "leafcutter/templates/agents/ticket-supervisor.md"
  - "leafcutter/templates/agents/create-ticket.md"
  - "leafcutter/templates/agents/create-epic.md"
  - "leafcutter/templates/agents/business-analyst.md"
  - "leafcutter/templates/agents/test-planner.md"
  - "leafcutter/templates/agents/refinement.md"
  - "leafcutter/templates/agents/architect-review.md"
  - "leafcutter/templates/agents/python-coder.md"
  - "leafcutter/templates/agents/sql-coder.md"
  - "leafcutter/templates/agents/sql-table-creator.md"
  - "leafcutter/templates/agents/sql-index-creator.md"
  - "leafcutter/templates/agents/sql-procedure-creator.md"
  - "leafcutter/templates/agents/sql-function-creator.md"
  - "leafcutter/templates/agents/sql-view-creator.md"
  - "leafcutter/templates/agents/documentation-expert.md"
  - "leafcutter/templates/agents/how-to-author.md"
  - "leafcutter/templates/agents/adr-author.md"
  - "leafcutter/templates/agents/reference-author.md"
  - "leafcutter/templates/agents/explanation-author.md"
  - "leafcutter/templates/agents/test-writer.md"
  - "leafcutter/templates/agents/test-runner.md"
  - "leafcutter/templates/agents/pr-reviewer.md"
  - "leafcutter/templates/agents/commit.md"
  - "leafcutter/templates/agents/pull-request.md"
  - "leafcutter/templates/agents/brainstorm-lead.md"
  - "leafcutter/templates/agents/brainstorm-worker.md"
  - "leafcutter/templates/agents/status-checker.md"
  - "leafcutter/templates/agents/worktree-agent.md"
related_tickets:
  - "tickets/09_done/EPIC-CodingAgents/Master_Plan.md"
  - "tickets/09_done/EPIC-AgentSupervisor/Master_Plan.md"
---

# Agent Code Delivery Workflows

## Purpose

This document visualises how the Brain Trader agent ecosystem orchestrates code delivery. It uses a layered abstraction approach: starting with a high-level mapping of slash commands to their primary agents, followed by detailed "drill-down" views showing how orchestrators and supervisors distribute work to specialised sub-agents. 

> [!TIP]
> For the authoritative rules on how these agents are grouped into model tiers (Haiku, Sonnet, Opus), see [ADR-006](ADR-006-agent-model-tiers.md). For the underlying supervisor architecture and sign-off status mechanics, see [ADR-010](ADR-010-agent-supervisor-signoff-pattern.md).

---

## Diagram Legend

All diagrams in this document use a consistent color-coding scheme to distinguish agent roles and system components:

| Color | Role | Description |
|---|---|---|
| **Yellow/Orange** | **User Interface (UI)** | Slash commands directly invoked by the human user. |
| **Blue** | **Orchestrator** | Supervisory agents that delegate tasks to sub-agents and never write the final code themselves (e.g., `epic-supervisor`, `sql-coder`). |
| **Green** | **Worker** | Implementation agents that execute specific technical tasks (e.g., `python-coder`, `sql-table-creator`). |
| **Pink** | **Gatekeeper** | Agents that enforce quality controls, review code, or escalate issues to Opus (e.g., `pr-reviewer`, `architect-review`). |
| **Grey** | **Input** | Static data files or configuration (e.g., `Master_Plan.md`). |
| **Red** | **Halt / Error** | Terminal states where execution halts and requests human intervention. |

---

## 1. High-Level Overview: Entry Points

This diagram maps user-facing slash commands to their **top-level agents**. Internal specialist sub-agents are omitted here to focus on the primary interfaces.

```mermaid
flowchart TD
    classDef ui fill:#fef3c7,stroke:#d97706,stroke-width:2px;
    classDef orchestrator fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef worker fill:#d1fae5,stroke:#059669,stroke-width:2px;
    classDef gatekeeper fill:#fce7f3,stroke:#db2777,stroke-width:2px;

    %% Slash Commands
    subgraph Commands ["User Slash Commands"]
        cmdBuild["/build-feature"]:::ui
        cmdTicket["/create-ticket"]:::ui
        cmdQuickFix["/quick-fix"]:::ui
        cmdPy["/python-coder"]:::ui
        cmdSql["/sql-coder"]:::ui
        cmdDoc["/documentation"]:::ui
        cmdCommit["/commit"]:::ui
        cmdPR["/pull-request"]:::ui
        cmdReview["/pr-review"]:::ui
        cmdDeploy["/prod-deploy"]:::ui
        cmdOther["/test, /database, /status, /worktree"]:::ui
    end

    %% Top-Level Agents
    subgraph Primary_Agents ["Top-Level Agents"]
        epicSup["epic-supervisor"]:::orchestrator
        createTick["create-ticket"]:::orchestrator
        quickFixAgt["ticket-supervisor (inline,<br/>current worktree — no branch switch)"]:::orchestrator
        pyCoder["python-coder"]:::worker
        sqlCoder["sql-coder"]:::orchestrator
        docExp["documentation-expert"]:::orchestrator
        commitAgt["commit"]:::worker
        prAgt["pull-request"]:::worker
        prRev["pr-reviewer"]:::gatekeeper
        prodDep["prod-deploy"]:::gatekeeper
        otherAgts["test-runner, database-agent, status-checker, worktree-agent"]:::worker
    end

    %% Mappings
    cmdBuild --> epicSup
    cmdTicket --> createTick
    cmdQuickFix --> quickFixAgt
    cmdPy --> pyCoder
    cmdSql --> sqlCoder
    cmdDoc --> docExp
    cmdCommit --> commitAgt
    cmdPR --> prAgt
    cmdReview --> prRev
    cmdDeploy --> prodDep
    cmdOther --> otherAgts
```

---

## 2. Detail View: Ticket Creation Orchestration (`/create-ticket`)

This view shows how the `create-ticket` orchestrator delegates ticket formulation to specialists, and how it handles fan-out for large requests by escalating to `create-epic`. Note that `business-analyst` always spawns `test-planner` as a sub-agent to produce the `test_requirements` block before the BA payload is returned.

```mermaid
flowchart TD
    classDef orchestrator fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef worker fill:#d1fae5,stroke:#059669,stroke-width:2px;
    classDef gatekeeper fill:#fce7f3,stroke:#db2777,stroke-width:2px;
    classDef decision fill:#fde68a,stroke:#ca8a04,stroke-width:2px;
    classDef utility fill:#ede9fe,stroke:#7c3aed,stroke-width:2px;

    CT_Orch["create-ticket (Orchestrator)"]:::orchestrator
    
    BA["business-analyst<br/>(Analyzes intent & sets routing decision)"]:::worker
    TP["test-planner<br/>(Spawned by BA — produces test_requirements)"]:::utility
    ScaleCheck{"Routing: Epic or Ticket?"}:::decision
    
    Refine["refinement<br/>(Technical clarity + test_requirements validation)"]:::worker
    ArchRev["architect-review<br/>(Structural impact)"]:::gatekeeper
    Finalise["Finalise Ticket<br/>(Apply skill & parity hooks)"]:::worker
    
    CE_Orch["create-epic (Scaffolder)<br/>Creates Master_Plan + Stubs"]:::orchestrator

    CT_Orch --> BA
    BA -->|Step 2: spawns| TP
    TP -->|returns test_requirements| BA
    BA --> ScaleCheck
    
    %% Small flow
    ScaleCheck -->|No - Standard Ticket| Refine
    ScaleCheck -->|No - Standard Ticket| ArchRev
    Refine --> Finalise
    ArchRev --> Finalise
    
    %% Large flow
    ScaleCheck -->|Yes - Epic| CE_Orch
    CE_Orch -. "Fans out N parallel passes" .-> CT_Orch
```

---

## 3. Detail View: Implementation Orchestrators (`/sql-coder` & `/documentation`)

> [!IMPORTANT]
> **Strict Delegation Rule:** Orchestrator agents (like `sql-coder` or `documentation-expert`) never write the final code themselves. They assess the user intent, gather architectural context, and route to the correct specialist worker, ensuring quality enforcement and context isolation.

```mermaid
flowchart LR
    classDef orchestrator fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef worker fill:#d1fae5,stroke:#059669,stroke-width:2px;

    %% SQL Coder Flow
    subgraph SQL_Orchestration ["/sql-coder Routing"]
        direction TB
        SqlOrch["sql-coder"]:::orchestrator
        SqlTbl["sql-table-creator"]:::worker
        SqlIdx["sql-index-creator"]:::worker
        SqlProc["sql-procedure-creator"]:::worker
        SqlFunc["sql-function-creator"]:::worker
        SqlView["sql-view-creator"]:::worker
        
        SqlOrch --> SqlTbl
        SqlOrch --> SqlIdx
        SqlOrch --> SqlProc
        SqlOrch --> SqlFunc
        SqlOrch --> SqlView
    end

    %% Docs Expert Flow
    subgraph Doc_Orchestration ["/documentation Routing (Diataxis)"]
        direction TB
        DocOrch["documentation-expert"]:::orchestrator
        DocHow["how-to-author"]:::worker
        DocAdr["adr-author"]:::worker
        DocArch["architecture-author"]:::worker
        DocRef["reference-author"]:::worker
        DocExp["explanation-author"]:::worker
        
        DocOrch --> DocHow
        DocOrch --> DocAdr
        DocOrch --> DocArch
        DocOrch --> DocRef
        DocOrch --> DocExp
    end
```

---

## 4. Detail View: Epic & Ticket Supervisor Flow (`/build-feature`)

This flow illustrates how `epic-supervisor` automates parallel delivery by calculating physical dependencies (`files_touched`), and how `ticket-supervisor` distributes work to phase agents based on the ticket's frontmatter. It also outlines the adjudication ladder for blockers.

The canonical phase-agent dispatch order is:
`architect-review → python-coder → test-writer → test-runner → documentation-expert → pr-reviewer → commit → pull-request`

`test-writer` is dispatched when the ticket has a non-empty `test_requirements.tests` array (produced by `test-planner` during ticket creation). If the array is empty (docs-only or config-only tickets), `ticket-wiring` sets `test-writer: not_needed` and the phase is skipped.

```mermaid
flowchart TD
    classDef input fill:#f3f4f6,stroke:#4b5563,stroke-width:2px;
    classDef orchestrator fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef worker fill:#d1fae5,stroke:#059669,stroke-width:2px;
    classDef decision fill:#fde68a,stroke:#ca8a04,stroke-width:2px;
    classDef error fill:#fee2e2,stroke:#ef4444,stroke-width:2px;
    classDef gatekeeper fill:#fce7f3,stroke:#db2777,stroke-width:2px;

    %% Data Inputs
    MP["Master_Plan.md<br/>+ Ticket Files"]:::input
    
    %% Epic Supervisor
    subgraph Epic_Supervisor_Layer ["Epic Supervisor (Sonnet)"]
        ES_Read["Read Master_Plan & sub-tickets"]:::orchestrator
        ES_Graph["Build Dependency Graph<br/>(depends_on + files_touched)"]:::orchestrator
        ES_Batch{"Compute next ready batch<br/>(disjoint files)"}:::decision
        ES_Spawn["Spawn N × ticket-supervisor<br/>(parallel)"]:::orchestrator
        
        MP --> ES_Read
        ES_Read --> ES_Graph
        ES_Graph --> ES_Batch
        ES_Batch -->|Batch Ready| ES_Spawn
        ES_Batch -->|All Done| ES_Finish((Finish))
    end
    
    %% Ticket Supervisor
    subgraph Ticket_Supervisor_Layer ["Ticket Supervisor (Sonnet)"]
        TS_Start(("Start Ticket"))
        TS_ReadFront["Read frontmatter 'agents' map"]:::orchestrator
        TS_FindNext{"Find next 'needed' agent"}:::decision
        TS_SpawnAgent["Spawn Phase Agent<br/>(e.g., python-coder)"]:::orchestrator
        
        ES_Spawn -. "invokes" .-> TS_Start
        TS_Start --> TS_ReadFront
        TS_ReadFront --> TS_FindNext
        TS_FindNext -->|Agent Needed| TS_SpawnAgent
        TS_FindNext -->|No More Needed| TS_Done(("Mark Ticket Done"))
        TS_Done -. "returns" .-> ES_Batch
    end
    
    %% Agent Execution & Signoff
    subgraph Phase_Execution ["Phase Agent Execution (ordered)"]
        AgentRun["Agent Does Work<br/>(e.g. architect-review, python-coder,<br/>test-writer, test-runner,<br/>documentation-expert, ...)"]:::worker
        AgentSignoff["Agent invokes signoff skill<br/>(Appends to ## Comments)"]:::worker
        
        TS_SpawnAgent --> AgentRun
        AgentRun --> AgentSignoff
    end
    
    %% Comment Adjudication
    subgraph Adjudication_Ladder ["Comment Parsing & Adjudication"]
        TS_Parse{"Parse Comment<br/>Status Tag"}:::decision
        
        AgentSignoff --> TS_Parse
        
        TS_Parse -->|ok / handoff| TS_ReadFront
        TS_Parse -->|question| TS_HaltUser["Halt & Ask User"]:::error
        
        %% Blocker ladder
        TS_Parse -->|blocker| TS_Blocker{"Blocker Adjudication Ladder"}:::decision
        
        TS_Blocker -->|1. Mechanical Error| TS_Respawn["Respawn sibling<br/>with error comment"]:::worker
        TS_Blocker -->|2. Cross-Agent Rework| TS_Respawn
        TS_Blocker -->|3. Design Choice| B_Lead["Spawn brainstorm-lead (Opus)"]:::gatekeeper
        TS_Blocker -->|4. Exhausted| TS_Fail["Halt & Surface to User"]:::error
        
        TS_Respawn -. "retries phase" .-> AgentRun
        
        %% Brainstorming
        B_Worker["N × brainstorm-worker (parallel)"]:::worker
        B_Lead --> B_Worker
        B_Worker --> B_Merge["Synthesise Recommendation"]:::gatekeeper
        B_Merge --> TS_HaltUser
    end
```

> [!TIP]
> The **Blocker Adjudication Ladder** is designed to shield the user from trivial issues. Only open-ended design questions (which escalate through the `brainstorm-lead` tier) or completely exhausted retries will interrupt the user.

---

---

## 5. Detail View: Quick-Fix Workflow (`/quick-fix`)

The `/quick-fix` command is a **current-worktree-only** workflow. Unlike `/build-feature`, it
never creates a new worktree or switches branches. The user invokes it from an existing
worktree (e.g. `EPIC-SomeFeature`) and all operations — AC creation, test writing, fix, and
commit — complete on the **same branch** the user was already on.

### AC BP-600a-1 — Worktree invariant

```
Given a user is on branch "EPIC-SomeFeature" in an existing worktree,
When they invoke /quick-fix with a diagnosis specifying a file and root cause,
Then the workflow performs all operations (AC creation, test writing, fix, commit)
  in the current worktree,
And git branch --show-current returns the same branch name both before and after
  the workflow completes,
And no new worktree directory is created during execution.
```

### Contrast with `/build-feature`

| Aspect | `/build-feature` | `/quick-fix` |
|--------|-----------------|-------------|
| Worktree | Creates a new isolated worktree per epic/ticket | Stays in the **current** worktree |
| Branch | Creates and switches to a new feature branch | Stays on the **current** branch |
| Entry point | `build-ticket.js` (JS workflow) or `build-single-ticket` skill | `quick-fix.js` (JS workflow, inline) |
| Depth model | `ticket-supervisor` at depth 0; phase agents at depth 1 (ADR-006) | Same depth model — `ticket-supervisor` inline at depth 0 |
| Ticket lifecycle | Full inbox → todo → done lifecycle | Lightweight — single-shot fix; ticket created inline and driven to commit in one pass |

### Flow

```mermaid
flowchart TD
    classDef ui fill:#fef3c7,stroke:#d97706,stroke-width:2px;
    classDef orchestrator fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef worker fill:#d1fae5,stroke:#059669,stroke-width:2px;
    classDef invariant fill:#fee2e2,stroke:#ef4444,stroke-width:2px;

    QF["/quick-fix (slash command)<br/>Current worktree — no branch switch"]:::ui

    subgraph Invariant ["Worktree Invariant (BP-600a-1)"]
        direction TB
        Check["git branch --show-current == SAME before/after"]:::invariant
        NoNewWT["No new worktree directory created"]:::invariant
    end

    subgraph Phases ["Inline Phases (current branch)"]
        direction TB
        AC["1. AC creation<br/>(build-ac agent)"]:::worker
        TW["2. Test writing<br/>(test-writer agent)"]:::worker
        Fix["3. Fix implementation<br/>(python-coder / sql-coder)"]:::worker
        TR["4. Test runner<br/>(test-runner agent)"]:::worker
        CM["5. Commit<br/>(commit agent)"]:::worker
    end

    QF --> Invariant
    QF --> Phases
    AC --> TW --> Fix --> TR --> CM
```

### AC BP-600a-1 constraint: no `git worktree add`, no `setup_ticket_worktree.py`

The `quick-fix.js` workflow script MUST NOT call `setup_ticket_worktree.py` or any equivalent
command that creates a new worktree directory. All phases run in the directory where `/quick-fix`
was invoked. This is enforced by the AC store entry `BP-600a-1` and checked by
`git branch --show-current` before and after the workflow completes.

### AC BP-600a-2 — No isolation infrastructure

Beyond the worktree invariant, `/quick-fix` must use **no isolation infrastructure** from
the full build pipeline. Specifically, the following are unconditionally prohibited in
`quick-fix.js` and in any agent dispatched by it:

| Prohibited item | Why |
|---|---|
| `worktree-agent` dispatch | Creates/manages isolated git worktrees — the opposite of stay-in-place |
| `feature` skill invocation | Calls `git worktree add`; creates branch isolation — violates BP-600a-1 |
| `git worktree add` | Direct worktree creation command — prohibited by BP-600a-1 |
| `setup_ticket_worktree.py` | Bootstrap script for new isolated worktrees — not needed in existing worktree |
| Any branch-switching command | `git checkout -b`, `git switch -c`, etc. |

The phase agents dispatched by `/quick-fix` (`build-ac`, `test-writer`, `python-coder`,
`test-runner`, `commit`) are worktree-agnostic — they operate on files in the current
directory and do not require an isolated branch context.

**Rationale:** `/quick-fix` is designed for rapid, in-place fixes to known bugs. Isolation
infrastructure adds 30–60 seconds of overhead and introduces branch-switch race conditions
when the user is mid-work on an active epic branch. The invariant is verifiable:
`git branch --show-current` must return the same branch name before and after the workflow.

### AC BP-600a-3 — Uncommitted changes guard

Before executing any phase, `/quick-fix` MUST check whether the target file has
uncommitted changes in the working tree. The Gherkin contract:

```gherkin
Given the user's worktree has unstaged changes in the file
  "scripts/build_helpers.py",
When the user invokes /quick-fix with a diagnosis targeting
  "scripts/build_helpers.py",
Then the workflow halts before any AC creation or code changes,
And it reports the conflicting uncommitted changes in the target file,
And it suggests the user commit or stash before retrying.
```

**Implementation contract:**

The guard runs as the **first step** of `/quick-fix`, immediately after parsing the
diagnosis input and resolving the target file path. Before any AC creation, test writing,
or code modification:

1. Run `git status --porcelain <target_file>`.
2. If the output is non-empty (the file has unstaged or staged changes):
   a. Print a structured halt message identifying the target file and the conflicting
      change (modified `M`, untracked `??`, staged `A`, etc.).
   b. Print the suggested remediation: `git commit` the current changes or
      `git stash push <target_file>` before retrying.
   c. Exit the workflow immediately — no AC file is written, no test is created, no
      code is changed.
3. If the output is empty, the target file is clean — proceed normally.

**Why this guard is necessary:**

Without it, `/quick-fix` could write a new failing test and apply a code fix to a file
that already contains in-progress work. The subsequent commit would bundle both the
user's uncommitted work and the quick-fix changes into a single commit, obscuring the
audit trail and potentially corrupting in-progress feature work. The guard enforces a
clean-slate assumption: `/quick-fix` is a rapid-fix tool, not a merge tool.

**Output format (halt message):**

```
/quick-fix halted: target file has uncommitted changes.

  File:    scripts/build_helpers.py
  Status:  M  (modified, unstaged)

  The quick-fix workflow requires a clean working tree for the target file.
  Please resolve the uncommitted changes before retrying:

    Option A — commit the changes:
      git add scripts/build_helpers.py
      git commit -m "wip: save in-progress changes before quick-fix"

    Option B — stash the changes:
      git stash push scripts/build_helpers.py

  Then re-invoke: /quick-fix <your-diagnosis>
```

### AC BP-600c-1 — Test-writer dispatch with AC input (test before fix)

After creating the AC YAML file (AC BP-600b-1), the quick-fix workflow MUST dispatch the
`test-writer` agent before applying any fix code. The Gherkin contract:

```gherkin
Given the quick-fix workflow has created an AC YAML file for the
  diagnosed bug,
When the workflow reaches the test-writing phase,
Then it dispatches the test-writer agent with the AC as input,
And the test-writer produces a test that reproduces the diagnosed bug,
And the test includes a "# covers: <AC-ID>" tag referencing the
  newly created AC,
And the test is written to the appropriate test directory before any
  fix code is applied.
```

**Dispatch contract (Agent-tool input to `test-writer` at depth 1):**

The test-writer agent is dispatched with the following structured inputs:

| Input field | Value | Source |
|---|---|---|
| `ticket_path` | Absolute path to the quick-fix workflow's internal ticket file | Workflow context at depth 0 |
| `ac_path` | Absolute path to the newly created AC YAML file (from BP-600b-1) | AC creation phase output |
| `target_file` | Absolute path to the buggy source file (from diagnosis parsing) | BP-600d-1 parsed struct |
| `location_hint` | Line number or function name (optional) | BP-600d-1 parsed struct |
| `symptom` | Observable incorrect behaviour | BP-600d-1 parsed struct |

**Test file requirements:**

1. **`# covers: <AC-ID>` tag** — every test function written by the test-writer for this
   quick-fix MUST include the tag `# covers: <AC-ID>` (where `<AC-ID>` is the ID from the
   newly created AC YAML file, e.g. `# covers: BP-600c`). The tag must appear on the line
   above `def test_*`, on the first body line, or in the docstring — matching the format
   required by `check_test_ac_tags.py`.

2. **Test directory** — the test file is written to the project's canonical test directory
   (e.g. `unit_tests/`) before any fix code is applied. The test-writer MUST NOT write to
   `src/` or any source directory.

3. **Red-phase assertion** — the test is expected to FAIL against the unfixed code. It
   asserts the correct behaviour (`Then` clause of the AC), which the buggy code does not
   yet satisfy. The test-runner phase (BP-600c-2) verifies this red state.

4. **Ordering invariant** — the test file write and the `covered_by` update to the AC YAML
   file (see AC Schema §test-writer integration) MUST both complete before the fix-implementation
   phase (`python-coder` / `sql-coder`) is dispatched. This ordering is enforced by the
   sequential phase chain in `quick-fix.js`.

**`covered_by` update (AC store integration):**

After writing the test file, the test-writer MUST append the new test path to the `covered_by`
list in the AC YAML file created during the AC creation phase:

```yaml
# After test-writer runs — BP-600c-1 AC YAML excerpt:
covered_by:
  - "unit_tests/test_<component>_<bug-id>.py::test_<function_name>"
```

This update is part of the same agent turn as the test file write — both the test file and
the `covered_by` update are committed together (see `docs/reference/ac-schema.md` §test-writer
for the full integration protocol).

---

### AC BP-600c-3 — Test-runner confirms green phase after fix is applied

After the python-coder has applied the fix to the diagnosed file (AC BP-600d-2), the quick-fix
workflow MUST dispatch the `test-runner` agent a second time to verify that the fix actually
resolves the failing test. The Gherkin contract:

```gherkin
Given the python-coder has applied the fix to the diagnosed file,
When the workflow reaches the green-phase verification step,
Then it dispatches the test-runner agent targeting the same test file
  from the red phase,
And the test-runner reports all tests PASSED,
And if the test still fails the workflow halts with a warning:
  "The fix did not resolve the failing test -- the root cause may be
  different than diagnosed."
```

**Dispatch contract (Agent-tool input to `test-runner` at depth 1 — green phase):**

| Input field | Value | Source |
|---|---|---|
| `ticket_path` | Absolute path to the quick-fix workflow's internal ticket file | Workflow context at depth 0 |
| `test_file` | Absolute path to the test file written by test-writer (from BP-600c-1) | test-writer phase output (same file as red phase) |
| `expected_outcome` | `"green"` — the test must pass after the fix | Hardcoded in quick-fix.js for the green-phase step |

**Green-phase outcome routing:**

| test-runner result | Workflow action |
|---|---|
| All tests **PASSED** | Proceed to commit phase — the fix is confirmed correct |
| Any test **FAILED** (fix did not resolve) | Halt the workflow immediately with the structured warning below |
| Test file not found / runner error | Halt the workflow with a structured error; do not proceed to commit |

**Halt message for persistent failure (fix did not resolve):**

```
/quick-fix halted: green-phase verification failed.

  Test file: <absolute path to test file>
  Result:    FAILED (at least one test still fails after the fix)

  Warning: The fix did not resolve the failing test -- the root cause may be
  different than diagnosed.

  Possible causes:
    1. The fix targeted the wrong location in the file (check location_hint).
    2. The root cause is in a different file than diagnosed.
    3. The fix is incomplete -- the logic branch requires additional changes.

  Suggested next steps:
    - Review the failing test output and the python-coder's diff.
    - Re-invoke /quick-fix with a refined diagnosis targeting the actual root
      cause, or fix the target file manually and commit.
```

**Ordering invariant:**

The green-phase test-runner invocation MUST run after the python-coder completes
(BP-600d-2) and BEFORE the commit phase starts. This sequencing is enforced by the
phase chain in `quick-fix.js`:

```
build-ac (depth 1) → test-writer (depth 1) → test-runner/red-phase (depth 1)
  → python-coder/fix (depth 1) → test-runner/green-phase (depth 1) → commit (depth 1)
```

The depth-0 executing context controls the ordering: `test-runner/green-phase` is
dispatched only after the `python-coder` Agent-tool call returns with a successful
sign-off. The `commit` phase is dispatched only after the green-phase `test-runner`
reports all tests PASSED. Any other outcome halts the workflow before commit is
ever invoked.

**Why this guard is necessary:**

Without the green-phase verification step, the quick-fix workflow could commit a
"fix" that does not actually resolve the diagnosed bug. The commit would record a
passing test suite (because the test from BP-600c-1 is the only new test), giving
a false green signal. The green-phase check enforces that:

1. The fix genuinely resolves the diagnosed defect (the test transitions from red to green).
2. The commit records a meaningful state transition — the bug is actually fixed.
3. The audit trail is trustworthy: test-red before fix, test-green after fix, then commit.

**Contrast with red-phase (BP-600c-2):**

| Phase | `expected_outcome` | Halt condition |
|---|---|---|
| Red (BP-600c-2) | `"red"` — test must FAIL | Halt if test unexpectedly passes |
| Green (BP-600c-3) | `"green"` — test must PASS | Halt if test still fails |

Both phases dispatch the same `test-runner` agent targeting the same `test_file`;
only the `expected_outcome` field and the halt-message copy differ.

---

### AC BP-600d-1 — Structured diagnosis input parsing

Before any phase runs, `/quick-fix` MUST parse the user-provided diagnosis text and extract
four structured fields. The Gherkin contract:

```gherkin
Given the user invokes /quick-fix with text containing "In
  scripts/build_helpers.py line 42, _resolve_precommit_cmd() returns
  a non-executable path because the executability probe is skipped
  when shutil.which returns None",
When the workflow parses the input,
Then it extracts the target file path ("scripts/build_helpers.py"),
  the location hint ("line 42"), the symptom ("returns a
  non-executable path"), and the root cause ("executability probe
  is skipped"),
And it uses these fields to drive AC creation, test writing, and
  fix application in subsequent phases.
```

**Parsed fields and their downstream consumers:**

| Field | Example value | Consumed by |
|---|---|---|
| `target_file` | `scripts/build_helpers.py` | Uncommitted changes guard (BP-600a-3), python-coder, test-writer |
| `location_hint` | `line 42` | python-coder (narrows the fix scope), test-writer (anchors the failing assertion) |
| `symptom` | `returns a non-executable path` | AC creation (describes observable failure), test-writer (names the expected vs actual) |
| `root_cause` | `executability probe is skipped` | AC creation (names the cause), python-coder (targets the exact logic branch to fix) |

**Parsing contract:**

The workflow accepts two input forms:

1. **Natural-language sentence** — the canonical form. The parser uses the following
   structural markers to identify fields:
   - `In <path>` or `In <path> line <N>` → `target_file` + optional `location_hint`
   - `<function>() returns ...` or similar verb phrase → `symptom`
   - `because ...` or `when ...` → `root_cause`

2. **Structured JSON** — an alternative form for programmatic invocation:
   ```json
   {
     "target_file": "scripts/build_helpers.py",
     "location_hint": "line 42",
     "symptom": "returns a non-executable path",
     "root_cause": "executability probe is skipped when shutil.which returns None"
   }
   ```

**Validation rules:**

- `target_file` MUST resolve to an existing file in the current worktree. If the file
  does not exist, the workflow halts with:
  ```
  /quick-fix halted: target file not found.
    File: <target_file>
    The diagnosis references a file that does not exist in the current worktree.
  ```
- `symptom` and `root_cause` MUST be non-empty strings. If either is absent after
  parsing, the workflow halts and asks the user to clarify:
  ```
  /quick-fix needs clarification: could not extract symptom and root cause from diagnosis.
    Parsed so far: target_file=<value>, location_hint=<value or (none)>
    Please rephrase: "In <file> [line N], <function>() <symptom> because <root_cause>."
  ```
- `location_hint` is optional. If absent, the downstream agents receive `null` for
  this field and must handle it gracefully (i.e. they do not require a line number to
  proceed; they use the symptom and root cause alone).

**How the parsed fields drive downstream phases:**

1. **AC creation** (`build-ac` agent) — receives `target_file`, `symptom`, and
   `root_cause` as structured inputs. Uses them to populate the AC Gherkin template:
   - Given: the target file exists and the buggy function is present
   - When: the triggering condition (derived from `root_cause`)
   - Then: the expected correct behaviour (derived from `symptom` negation)

2. **Test writing** (`test-writer` agent) — receives all four fields. Uses
   `target_file` and `location_hint` to locate the test anchor, and `symptom` to
   name the assertion (`assert result != <symptom-value>`).

3. **Fix implementation** (`python-coder` agent) — receives all four fields. Uses
   `location_hint` to narrow the edit scope and `root_cause` to identify the logic
   branch to repair.

### AC BP-600c-2 — Test-runner confirms red phase before fix code is applied

After the test-writer has produced the failing test (AC BP-600c-1), the quick-fix workflow
MUST dispatch the `test-runner` agent to verify that the new test actually fails against the
unfixed codebase. The Gherkin contract:

```gherkin
Given the test-writer has produced a test file for the diagnosed bug,
When the workflow reaches the red-phase verification step,
Then it dispatches the test-runner agent targeting the new test file,
And the test-runner reports at least one FAILED result for the new test,
And if the test unexpectedly passes the workflow halts with a warning:
  "The test passes before the fix was applied -- the diagnosis may be
  incorrect or the bug is already fixed."
```

**Dispatch contract (Agent-tool input to `test-runner` at depth 1):**

The test-runner agent is dispatched with the following structured inputs:

| Input field | Value | Source |
|---|---|---|
| `ticket_path` | Absolute path to the quick-fix workflow's internal ticket file | Workflow context at depth 0 |
| `test_file` | Absolute path to the test file written by test-writer (from BP-600c-1) | test-writer phase output |
| `expected_outcome` | `"red"` — the test must fail | Hardcoded in quick-fix.js for the red-phase step |

**Red-phase outcome routing:**

| test-runner result | Workflow action |
|---|---|
| At least one test **FAILED** | Proceed to fix-implementation phase (`python-coder` / `sql-coder`) — this is the expected red state |
| All tests **PASSED** (unexpected green) | Halt the workflow immediately with the structured warning below |
| Test file not found / runner error | Halt the workflow with a structured error; do not proceed to fix |

**Halt message for unexpected green (test passes before fix):**

```
/quick-fix halted: red-phase verification failed.

  Test file: <absolute path to test file>
  Result:    PASSED (all assertions green before fix was applied)

  Warning: The test passes before the fix was applied -- the diagnosis may be
  incorrect or the bug is already fixed.

  Possible causes:
    1. The diagnosed bug has already been fixed in a prior commit.
    2. The test assertion does not correctly reproduce the diagnosed symptom.
    3. The target file path or location hint was mis-parsed (see BP-600d-1 output).

  Suggested next steps:
    - Review the test file at <test_file> and confirm it asserts the diagnosed
      failure condition.
    - Run git log <target_file> to check for recent fixes.
    - Re-invoke /quick-fix with a more precise diagnosis, or mark the bug as
      already-fixed.
```

**Ordering invariant:**

The red-phase test-runner invocation MUST run after the test-writer completes
(BP-600c-1) and BEFORE the fix-implementation phase starts (AC for fix phase). This
sequencing is enforced by the phase chain in `quick-fix.js`:

```
build-ac (depth 1) → test-writer (depth 1) → test-runner/red-phase (depth 1) → fix-coder (depth 1) → commit (depth 1)
```

The depth-0 executing context controls the ordering: `test-runner` is dispatched only
after the `test-writer` Agent-tool call returns with a successful sign-off. The fix-coder
is dispatched only after the `test-runner` reports at least one FAILED result. Any other
outcome halts the workflow before the fix-coder is ever invoked.

**Why this guard is necessary:**

Without the red-phase verification step, the quick-fix workflow could silently skip the
TDD contract — writing a test that happens to pass against the current code, applying
a "fix" that changes nothing meaningful, and committing a green test suite that never
actually reproduced the bug. The red-phase check enforces that:

1. The test genuinely targets the diagnosed defect (it fails against unfixed code).
2. The subsequent green-phase (after the fix) is meaningful — a real state transition
   from red to green.
3. The audit trail is valid: the commit history shows test-red before fix, test-green
   after fix.

### AC BP-600d-2 — python-coder dispatched with diagnosis after red-phase confirmation

After the red-phase test-runner has confirmed the bug is reproducible (AC BP-600c-2), the
quick-fix workflow MUST dispatch the `python-coder` agent to apply the fix. The Gherkin
contract:

```gherkin
Given the red-phase test has confirmed the bug is reproducible
  (test fails as expected),
When the workflow reaches the fix-application phase,
Then it dispatches the python-coder agent with the diagnosis,
  the failing test file, and the target file path,
And the python-coder modifies only the target file specified in
  the diagnosis,
And no other source files are modified by the python-coder in
  this phase.
```

**Dispatch contract (Agent-tool input to `python-coder` at depth 1):**

The python-coder agent is dispatched with the following structured inputs:

| Input field | Value | Source |
|---|---|---|
| `ticket_path` | Absolute path to the quick-fix workflow's internal ticket file | Workflow context at depth 0 |
| `target_file` | Absolute path to the buggy source file (from diagnosis parsing) | BP-600d-1 parsed struct |
| `test_file` | Absolute path to the failing test file produced by test-writer | BP-600c-1 output |
| `location_hint` | Line number or function name (optional) | BP-600d-1 parsed struct |
| `symptom` | Observable incorrect behaviour | BP-600d-1 parsed struct |
| `root_cause` | Root cause of the bug | BP-600d-1 parsed struct |

**Scope constraint (single-file modification):**

The python-coder MUST modify only the `target_file` supplied in the Agent-tool input.
No other source files may be created or modified during this phase:

| Constraint | Rule |
|---|---|
| Only `target_file` modified | The python-coder edit must be scoped to the single file named in the diagnosis. Changes to any other source file are unconditionally prohibited in this phase. |
| No test file edits | The test file written by test-writer (BP-600c-1) MUST NOT be modified by the python-coder. The test is the acceptance gate — editing it during the fix phase would invalidate the TDD contract. |
| No new source files | The python-coder MUST NOT create new source files as part of the fix. If the fix genuinely requires a new module, the workflow halts and surfaces to the user for a scoped re-diagnosis. |

**Ordering invariant:**

The python-coder dispatch occurs ONLY after both:
1. The test-writer has produced the failing test (BP-600c-1), AND
2. The red-phase test-runner has confirmed the test fails (BP-600c-2).

If either prior phase did not complete successfully, the fix-application phase MUST NOT
start. The ordering is enforced by the sequential phase chain in `quick-fix.js`:

```
build-ac (depth 1) → test-writer (depth 1) → test-runner/red-phase (depth 1)
  → python-coder/fix (depth 1) → test-runner/green-phase (depth 1) → commit (depth 1)
```

**Why single-file scope is enforced:**

The quick-fix workflow is a rapid-fix tool for known, localised bugs. A single-file
modification constraint ensures:

1. **Audit clarity** — the commit shows exactly which file was changed and why. A
   multi-file python-coder edit would obscure causality.
2. **Minimal blast radius** — the fix applies the smallest possible change to restore
   correct behaviour. Collateral edits to unrelated files introduce regression risk.
3. **AC traceability** — the single-file constraint makes it straightforward to verify
   that the committed change satisfies exactly the diagnosed AC (BP-600d-2). A
   multi-file change would require cross-file AC coverage analysis.

---

## Key Design Principles

1. **Self-Documenting State:** The `epic-supervisor` determines what phase a ticket is in by parsing the structured `agents:` YAML map in the ticket's frontmatter. It never reads the conversational history.
2. **Safe Parallelism:** Tickets are batched for parallel execution only if their `files_touched` sets are disjoint and logical `depends_on` constraints are met.
3. **Escalating Adjudication:** When a worker encounters a blocker, `ticket-supervisor` attempts mechanical retries before calling an Opus-level brainstormer or bothering the user.
4. **Single Source of Truth:** User-facing slash commands (`/sql-coder`, `/pr-review`) map directly to their underlying orchestration agents, decoupling UX from complex internal routing.
5. **Current-Worktree-First for Known Bugs:** The `/quick-fix` workflow stays in the current worktree and branch. Speed and quality discipline are not in tension — the same phase agents run inline without a branch switch (ADR-006; AC BP-600a-1).

---

## Cross-References

- [Agent Inventory](../agents/README.md) — Comprehensive table of all existing agents and slash commands.
- [ADR-010 — Agent Supervisor & Ticket Sign-off Pattern](ADR-010-agent-supervisor-signoff-pattern.md) — Formal specification for the frontmatter status enum, commit-phase serialization lock, and pre-commit parity guards.
- [Agent Supervisor Design Spec](../superpowers/specs/2026-05-08-agent-supervisor-design.md) — In-depth breakdown of the supervisor execution algorithms.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-08 [llm-expert]: Added AC BP-600c-3 green-phase verification section to Section 5: Gherkin contract, dispatch contract table, outcome routing table, halt message for persistent failure, ordering invariant, contrast table with red-phase, and rationale. (#EPIC-QuickFixWorkflow/11)
- 2026-06-08 [llm-expert]: Added AC BP-600d-2 python-coder fix-application dispatch section to Section 5: Gherkin contract, dispatch contract table, single-file scope constraint table, ordering invariant, and rationale. (#EPIC-QuickFixWorkflow/10)
- 2026-06-08 [llm-expert]: Added AC BP-600c-2 red-phase verification section to Section 5: Gherkin contract, dispatch contract table, outcome routing table, halt message for unexpected green, ordering invariant, and rationale. (#EPIC-QuickFixWorkflow/08)
- 2026-06-08 [llm-expert]: Added AC BP-600c-1 test-writer dispatch section to Section 5: Gherkin contract, dispatch contract table, test file requirements, red-phase assertion, ordering invariant, and covered_by update protocol. (#EPIC-QuickFixWorkflow/07)
- 2026-06-08 [llm-expert]: Added AC BP-600d-1 structured diagnosis input parsing section to Section 5: Gherkin contract, four parsed fields table, two input forms, validation rules, and downstream consumer mapping. (#EPIC-QuickFixWorkflow/09)
- 2026-06-08 [llm-expert]: Added AC BP-600a-3 uncommitted changes guard section to Section 5: guard contract, implementation steps, halt message format, and rationale. (#EPIC-QuickFixWorkflow/03)
- 2026-06-08 [llm-expert]: Added AC BP-600a-2 documentation to Section 5: prohibited isolation infrastructure table, no-worktree-agent/no-feature-skill constraint, and rationale for the exclusion. (#EPIC-QuickFixWorkflow/02)
- 2026-06-08 [llm-expert]: Added /quick-fix to high-level overview (§1) and Section 5 documenting the current-worktree-only flow, worktree invariant (BP-600a-1), contrast table with /build-feature, and Mermaid flow diagram. (#EPIC-QuickFixWorkflow/01)
- 2026-05-13 [Antigravity]: Added test-planner spawn to ticket-creation diagram (§2) and test-writer to phase-agent dispatch order (§4) per ADR-018 and ticket 36 (test-expert injection).
- 2026-05-11 [Antigravity]: Refactored to feature layered abstraction, splitting a single large flow into a high-level overview and specific orchestration detail views. Removed non-coding elements like `trade-report`.
- 2026-05-11 [Antigravity]: Initial creation. Visualises slash command distribution and Epic Supervisor execution flow based on EPIC-CodingAgents and EPIC-AgentSupervisor patterns.
====================================================================
-->
