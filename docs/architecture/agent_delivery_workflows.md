---
title: "Agent Code Delivery Workflows"
description: "Visualises how the leafcutter-ai agent ecosystem orchestrates code delivery — slash-command entry points, supervisor dispatch topology, and blocker adjudication flows."
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
`architect-review → python-coder → sql-coder → frontend-coder → test-writer → test-runner → documentation-expert → pr-reviewer → commit → pull-request`

Priority slots: `python-coder` (6), `sql-coder` (7), `frontend-coder` (8), `test-runner` (9). `frontend-coder` is a **unified** implementation agent — the `frontend-design` skill is embedded inside it (not a separate box in the dispatch topology) and the optional `webapp-testing` skill is invoked internally after UI changes.

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
    subgraph Phase_Execution ["Phase Agent Execution (priority order)"]
        AgentRun["Agent Does Work<br/>(e.g. architect-review [4],<br/>python-coder [6], sql-coder [7],<br/>frontend-coder [8], test-runner [9],<br/>documentation-expert [10], ...)"]:::worker
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

## 5. Detail View: Unified `frontend-coder` at Priority 8

`frontend-coder` is a **unified** sibling implementation agent — a single box at priority 8 in the dispatch topology. It replaces the previously planned `frontend-coder + frontend-design skill` split. The `frontend-design` skill is embedded inside `frontend-coder` and is never a separate node in the dispatch graph. Optional skills (`webapp-testing`) are invoked internally based on file-existence detection.

```mermaid
flowchart TD
    classDef orchestrator fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef worker fill:#d1fae5,stroke:#059669,stroke-width:2px;
    classDef input fill:#f3f4f6,stroke:#4b5563,stroke-width:2px;
    classDef optional fill:#fef9c3,stroke:#ca8a04,stroke-width:1px,stroke-dasharray:4 2;
    classDef embedded fill:#ede9fe,stroke:#7c3aed,stroke-width:1px;

    TS["ticket-supervisor<br/>(priority 8 slot)"]:::orchestrator

    subgraph FrontendCoder ["frontend-coder (unified agent — priority 8)"]
        direction TB
        FC_Read["1. Read ticket + PROJECT_CONTEXT.md<br/>(adopter overrides)"]:::worker
        FC_Design["2. Apply embedded design principles<br/>(frontend-design skill, internal)"]:::embedded
        FC_Impl["3. Write markup / CSS / JS / TS<br/>(React, Vue, Svelte, HTML)"]:::worker
        FC_Test["4. Optionally invoke webapp-testing<br/>(if skill exists at .claude/skills/webapp-testing/)"]:::optional
        FC_Sign["5. Sign off via signoff skill"]:::worker

        FC_Read --> FC_Design
        FC_Design --> FC_Impl
        FC_Impl --> FC_Test
        FC_Test --> FC_Sign
    end

    PC["PROJECT_CONTEXT.md<br/>(adopter design tokens,<br/>CSS vars, brand guide)"]:::input
    WT[".claude/skills/webapp-testing/<br/>(optional — file-existence detection)"]:::optional

    TS -->|dispatches at priority 8| FrontendCoder
    PC -->|pre-flight read — overrides defaults| FC_Read
    WT -->|loaded if present| FC_Test
```

> [!NOTE]
> `frontend-design` does NOT appear as a separate agent or skill box in the dispatch topology. It is a first-class part of `frontend-coder`'s own reasoning — its design principles are embedded in the agent template (Step 2 above). This is the key architectural difference from the legacy split design.

---

## Key Design Principles

1. **Self-Documenting State:** The `epic-supervisor` determines what phase a ticket is in by parsing the structured `agents:` YAML map in the ticket's frontmatter. It never reads the conversational history.
2. **Safe Parallelism:** Tickets are batched for parallel execution only if their `files_touched` sets are disjoint and logical `depends_on` constraints are met.
3. **Escalating Adjudication:** When a worker encounters a blocker, `ticket-supervisor` attempts mechanical retries before calling an Opus-level brainstormer or bothering the user.
4. **Single Source of Truth:** User-facing slash commands (`/sql-coder`, `/pr-review`) map directly to their underlying orchestration agents, decoupling UX from complex internal routing.

---

## Cross-References

- [Agent Inventory](../agents/README.md) — Comprehensive table of all existing agents and slash commands.
- [ADR-010 — Agent Supervisor & Ticket Sign-off Pattern](ADR-010-agent-supervisor-signoff-pattern.md) — Formal specification for the frontmatter status enum, commit-phase serialization lock, and pre-commit parity guards.
- [Agent Supervisor Design Spec](../superpowers/specs/2026-05-08-agent-supervisor-design.md) — In-depth breakdown of the supervisor execution algorithms.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-08 10:00 [BrainCandy]: Added frontend-coder at priority 8 to §4 canonical dispatch order. Added §5 diagram showing unified frontend-coder topology: embedded frontend-design, PROJECT_CONTEXT.md pre-flight, optional webapp-testing skill. No separate frontend-design box in dispatch graph. (#EPIC-Oneagenthandlesboththelookandthecodefor/05)
- 2026-05-13 [Antigravity]: Added test-planner spawn to ticket-creation diagram (§2) and test-writer to phase-agent dispatch order (§4) per ADR-018 and ticket 36 (test-expert injection).
- 2026-05-11 [Antigravity]: Refactored to feature layered abstraction, splitting a single large flow into a high-level overview and specific orchestration detail views. Removed non-coding elements like `trade-report`.
- 2026-05-11 [Antigravity]: Initial creation. Visualises slash command distribution and Epic Supervisor execution flow based on EPIC-CodingAgents and EPIC-AgentSupervisor patterns.
====================================================================
-->
