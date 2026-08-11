---
title: "Code-Smell Review — Fowler Refactoring Review Capability"
description: "Architecture of the Fowler code-smell review capability: the developer-facing /code-smell-review flow, the shared core review method plus the two bucket catalogues, the two cost-tiered leaf reviewers (Sonnet + Opus), and the top-level orchestration that fans them out in parallel and merges their findings into one severity-ranked report."
type: architecture
diagram_type: component
status: active
flight_level: L3-Component
root: true
created: 2026-08-11
last_updated: 2026-08-11
source_ticket: null
components:
  - review_system
related_code:
  - templates/skills/code-smell-review/SKILL.md
  - templates/skills/review-for-code-smells/SKILL.md
  - templates/skills/review-for-structural-code-smells/SKILL.md
  - templates/skills/review-for-design-code-smells/SKILL.md
  - templates/agents/find-structural-smells.md
  - templates/agents/find-design-smells.md
related_docs:
  - docs/architecture/agent_delivery_workflows.md
tags:
  - code-smell
  - refactoring
  - fowler
  - review
  - parallel-fan-out
---

# Code-Smell Review — Fowler Refactoring Review Capability

This capability runs a full Martin Fowler *Refactoring* (2nd ed) "Bad Smells in Code"
review over a target and returns **one** prioritised report that maps every finding to
its named refactoring. It is cost-tiered and focused: a shared core method defines the
process and report format, two bucket catalogues split the Modern-12 smells by difficulty,
and two leaf reviewers each hold only their six smells. A top-level orchestration fans the
two reviewers out **in parallel** and merges their findings into a single severity-ranked
report.

## Why this shape

The Modern-12 smells split by difficulty:

- **Structural** (local / mechanical, near-lint): Mysterious Name, Duplicated Code, Long
  Function, Long Parameter List, Loops, Repeated Switches → handled by
  `find-structural-smells` on **Sonnet**.
- **Design** (cross-cutting / judgment, needs whole-target reasoning): Global Data, Mutable
  Data, Feature Envy, Data Clumps, Primitive Obsession, Shotgun Surgery → handled by
  `find-design-smells` on **Opus**.

Splitting keeps each reviewer focused on six smells (better recall than one agent juggling
twelve) and spends Opus only where judgment is needed. The fan-out lives in the **top-level
loop** (depth-0) because a spawned sub-agent cannot spawn further sub-agents (Claude Code's
depth-1 hard limit, ADR-006 "flatten the supervisor chain"); the two reviewers therefore
run at depth-1.

## Diagram 1 — Invocation to single report (CR-100e-3)

The ordered flow from the developer's `/code-smell-review` invocation, through the top-level
orchestration, to the **single** returned report. The target (a file, a folder, or a pasted
snippet) enters the flow; one consolidated report leaves it.

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Developer
    participant Cmd as /code-smell-review (skill)
    participant Orch as code-smell-review orchestration (depth-0)
    participant Reviewers as Leaf reviewers (structural + design)
    participant Report as Single report file

    Dev->>Cmd: /code-smell-review <target: file / folder / snippet>
    Cmd->>Orch: run orchestration in the top-level loop
    Orch->>Orch: resolve target to concrete paths / diff range (shared by both reviewers)
    Orch->>Reviewers: dispatch the review (parallel fan-out — see Diagram 3)
    Reviewers-->>Orch: return findings sections (not files)
    Orch->>Orch: merge into one prioritised report — dedup, continuous IDs, scorecard
    Orch->>Report: write code-smells-<target-id>.md at the workspace root
    Orch-->>Dev: SINGLE consolidated report (path + finding counts by severity)
```

This capability is the root of its own architecture-doc tree; it has no parent container doc.
See also: [Agent Code Delivery Workflows](../agent_delivery_workflows.md) — the depth-1
dispatch topology the parallel fan-out below respects.

## Diagram 2 — Component structure (CR-100f-6)

The shared core method, the two bucket catalogues, the two tiered leaf reviewers, and the
top-level orchestration. Each leaf reviewer depends on the **core** method **plus** its own
bucket catalogue. The orchestration fans out to both leaf reviewers and merges their
findings into one report.

```mermaid
flowchart TB
    orch["code-smell-review<br/>(top-level orchestration, depth-0)"]

    subgraph agents["Leaf reviewers (depth-1 sub-agents, read-only)"]
        leaf_struct["find-structural-smells<br/>(Sonnet — 6 mechanical smells)"]
        leaf_design["find-design-smells<br/>(Opus — 6 judgment smells)"]
    end

    subgraph skills["Review skills"]
        core["review-for-code-smells<br/>(shared core: method, severity, report format)"]
        b_struct["review-for-structural-code-smells<br/>(structural bucket catalogue)"]
        b_design["review-for-design-code-smells<br/>(design bucket catalogue)"]
    end

    report["Single merged report<br/>(severity-ranked)"]

    orch -->|"fan out (parallel)"| leaf_struct
    orch -->|"fan out (parallel)"| leaf_design

    leaf_struct -->|loads core| core
    leaf_struct -->|loads its bucket| b_struct
    leaf_design -->|loads core| core
    leaf_design -->|loads its bucket| b_design

    leaf_struct -->|returns findings| report
    leaf_design -->|returns findings| report
    orch -->|merges findings into one| report
```

Both leaf reviewers load the **same** `review-for-code-smells` core (so the two finding
sets share one method, severity rubric, and report format) and diverge only in the bucket
catalogue they load. The core on its own defines the process, not the smells; a bucket on
its own defines smells, not the process — they are always loaded together.

## Diagram 3 — Parallel fan-out and post-return merge (CR-100f-7)

The top-level orchestration dispatches **both** leaf reviewers **in parallel** (one message,
two `Agent` calls), both reviewers return their findings, and the orchestration merges those
findings into one severity-ranked report **only after both have returned**.

```mermaid
sequenceDiagram
    autonumber
    participant Orch as code-smell-review orchestration
    participant Struct as find-structural-smells (Sonnet)
    participant Design as find-design-smells (Opus)
    participant Report as Single severity-ranked report

    Note over Orch,Design: One message, two Agent calls — both reviewers run concurrently (depth-1)
    par Dispatch both leaf reviewers IN PARALLEL
        Orch->>Struct: review the same target (structural bucket)
    and
        Orch->>Design: review the same target (design bucket)
    end
    Struct-->>Orch: structural findings sections
    Design-->>Orch: design findings sections
    Note over Orch: Merge happens ONLY after BOTH reviewers have returned
    Orch->>Orch: reconcile context, de-dup overlaps, re-number IDs, rank by severity
    Orch->>Report: write ONE merged, severity-ranked report
```

If one reviewer returns nothing usable, the orchestration writes the report from the other's
findings and states plainly that only one bucket ran. For a tiny target it may skip the
fan-out and run one reviewer — but it says so; it never silently narrows coverage.

## Responsibilities

- **`code-smell-review` (orchestration):** resolve the target, fan out to both leaf reviewers
  in parallel, merge their returned findings into one report, and write/confirm that single
  file. It never reviews code itself — its job is dispatch + merge.
- **`review-for-code-smells` (core):** the shared method — gather, infer stack, scan,
  classify severity, and the finding/report format that maps each smell to a Fowler
  refactoring.
- **`review-for-structural-code-smells` / `review-for-design-code-smells` (buckets):** the
  two six-smell catalogues that build on the core.
- **`find-structural-smells` (Sonnet) / `find-design-smells` (Opus):** read-only leaf
  reviewers that load the core plus their own bucket and **return** findings sections
  (they do not write files), so the orchestration can merge them into one report.

## Cross-References

- [Agent Code Delivery Workflows](../agent_delivery_workflows.md) — the depth-1 sub-agent
  dispatch topology the parallel fan-out respects (ADR-006).
- `templates/skills/code-smell-review/SKILL.md` — the orchestration skill (fan-out, merge,
  depth-1 rule).
- `templates/skills/review-for-code-smells/SKILL.md` — the shared core method and report
  format.
- `templates/skills/review-for-structural-code-smells/SKILL.md` and
  `templates/skills/review-for-design-code-smells/SKILL.md` — the two bucket catalogues.
- `templates/agents/find-structural-smells.md` (Sonnet) and
  `templates/agents/find-design-smells.md` (Opus) — the two leaf reviewers.
