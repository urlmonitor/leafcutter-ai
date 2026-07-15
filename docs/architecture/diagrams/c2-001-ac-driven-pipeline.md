---
title: "AC-Driven Pipeline — Component Diagram"
type: architecture
diagram_type: component
status: active
created: 2026-06-05
last_updated: 2026-06-05
flight_level: L2
parent: agent_delivery_workflows.md
components:
  - ac_store
  - ticket_creation_pipeline
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/ac-authoring-pipeline.md
  - docs/architecture/diagrams/build-ac-flow.md
  - docs/architecture/diagrams/ac-readiness-states.md
  - docs/how-to/ac-driven-development.md
tags:
  - ac-store
  - ticket-creation
  - pipeline
  - scanner
  - generator
---

# AC-Driven Pipeline — Component Diagram

This diagram shows all seven components of the AC-driven pipeline, the AC
store data source, and the data flows between them. Components are grouped
by phase: **authoring-time** (run when an AC is committed) and
**build-time** (run when `/build-ac` is invoked). Arrows are labelled with
the data format that flows along each edge.

---

## Diagram Legend

| Color | Role | Description |
|---|---|---|
| Grey | Data store | Persistent YAML files or Markdown tickets |
| Green | Script | Purpose-built scripts that read or transform store data |
| Blue | Agent | Orchestrating agent that sequences script calls and user prompts |
| Purple | Commit-time | Pre-commit hook or git merge step |
| Yellow | External | Existing build pipeline components unchanged by this epic |

---

## Component Diagram

```mermaid
flowchart TD
    classDef store fill:#f3f4f6,stroke:#4b5563,stroke-width:2px;
    classDef script fill:#d1fae5,stroke:#059669,stroke-width:2px;
    classDef agent fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef committime fill:#ede9fe,stroke:#7c3aed,stroke-width:2px;
    classDef external fill:#fef3c7,stroke:#d97706,stroke-width:2px;

    %% ── Data stores ──────────────────────────────────────────────────
    ACS[("AC Store\ndocs/acceptance-criteria/\n*.yaml")]:::store
    TICK[("Ticket file\ntickets/00_inbox/\n*.md")]:::store

    %% ── Authoring-time ───────────────────────────────────────────────
    subgraph Authoring ["Authoring-time (pre-commit)"]
        direction TB
        VAL["validate_ac_schema.py\n─────────────────────\nEnforces JSON Schema\nRequires readiness + priority\nBlocks commit on invalid YAML"]:::committime
    end

    %% ── Build-time ───────────────────────────────────────────────────
    subgraph BuildTime ["Build-time (/build-ac invoked)"]
        direction TB
        SCAN["scan_ac_store.py\n────────────────────\n--level leaf\n--work-status todo\nReturns: READY list\n(readiness:approved only)"]:::script
        PRI["ac_prioritizer.py\n──────────────────\n--json\nReturns: top-ranked AC\nSort: priority then\nestimated_complexity"]:::script
        GEN["generate_ticket_from_ac.py\n──────────────────────────\n--ac <id>\nWrites ticket to\ntickets/00_inbox/\nSets source_ac in ticket"]:::script
        DONE["mark_ac_done.py\n────────────────\n--ticket <path>\nReads source_ac\nSets work_status→done\nIdempotent"]:::script
        BAC["build-ac agent\n────────────────\nSequences: scan →\nrank → propose →\nyes/review/skip →\nbuild → done-link"]:::agent
    end

    %% ── External ─────────────────────────────────────────────────────
    BF["build-feature\n(/build-feature command)"]:::external
    GIT["git / PR merge"]:::external

    %% ── Authoring-time flows ─────────────────────────────────────────
    ACS -->|"YAML files (staged)"| VAL
    VAL -->|"exit 0 — valid\nor non-zero — blocked"| ACS

    %% ── Build-time flows ─────────────────────────────────────────────
    ACS -->|"YAML files"| SCAN
    SCAN -->|"JSON: READY list"| PRI
    PRI -->|"JSON: top AC\n{id, title, priority}"| BAC
    BAC -->|"--ac <id>"| GEN
    GEN -->|"ticket_path (string)"| TICK
    GEN -->|"ticket_path"| BAC
    BAC -->|"ticket_path"| BF
    BF -->|"build complete"| BAC
    BAC -->|"--ticket <ticket_path>"| DONE
    DONE -->|"YAML patch:\nwork_status→done"| ACS

    %% ── Git close-out ────────────────────────────────────────────────
    BF -->|"commits + PR"| GIT
    TICK -->|"read by"| BF
```

---

## Component Descriptions

| Component | Phase | Purpose |
|---|---|---|
| **AC Store** | Both | YAML files under `docs/acceptance-criteria/`; authoritative backlog. Each AC carries `readiness`, `work_status`, `priority`, `assigned_agent`, and `estimated_complexity`. |
| **validate_ac_schema.py** | Authoring-time | Pre-commit hook. Enforces `config/ac_schema.json` on every staged AC YAML. Requires `readiness` and `priority` fields. Blocks invalid commits. |
| **scan_ac_store.py** | Build-time | Walks the AC store, filters by `readiness: approved` and `work_status: todo`, resolves `depends_on` chains, returns a sorted READY list as JSON. |
| **ac_prioritizer.py** | Build-time | Receives the READY list, ranks by `priority` (critical → high → medium → low) then `estimated_complexity` ascending, returns the top candidate as JSON. |
| **generate_ticket_from_ac.py** | Build-time | Reads an AC by ID, generates a full Markdown ticket file in `tickets/00_inbox/`, and writes `source_ac: <id>` into the ticket frontmatter for traceability. Idempotent: exits non-zero if a ticket for this AC already exists. |
| **mark_ac_done.py** | Build-time | Reads a ticket's `source_ac` field, locates the AC YAML, and sets `work_status: done`. Called after `/build-feature` completes. Idempotent. |
| **build-ac agent** | Build-time | Thin coordinator that sequences `scan → rank → propose → yes/review/skip → build → done-link`. Does not write files itself; all mutations go through the scripts above. |

---

## Data Flow Labels

| Arrow | Data format |
|---|---|
| AC Store → validate_ac_schema.py | YAML files (git-staged) |
| AC Store → scan_ac_store.py | YAML files (directory walk) |
| scan_ac_store.py → ac_prioritizer.py | JSON array of AC objects |
| ac_prioritizer.py → build-ac | JSON: `{id, title, priority, estimated_complexity}` |
| build-ac → generate_ticket_from_ac.py | AC id string (CLI `--ac` argument) |
| generate_ticket_from_ac.py → ticket file | Markdown (`.md`) ticket |
| generate_ticket_from_ac.py → build-ac | ticket_path string |
| build-ac → build-feature | ticket_path string |
| build-ac → mark_ac_done.py | ticket_path string (CLI `--ticket` argument) |
| mark_ac_done.py → AC Store | YAML patch (`work_status: done`) |

---

## Key Design Constraints

1. **AC store is read-only during scan.** `scan_ac_store.py` never modifies
   the store. The only mutation points are `generate_ticket_from_ac.py`
   (writes `source_ac` to the ticket) and `mark_ac_done.py` (writes
   `work_status: done` back to the AC YAML).
2. **Idempotency is mandatory.** Both `generate_ticket_from_ac.py` and
   `mark_ac_done.py` detect and skip re-runs to avoid duplicate tickets or
   double-done writes.
3. **Generated tickets are structurally identical to hand-written tickets.**
   The build pipeline has no awareness of how a ticket was created. No
   special-casing is needed in `epic-supervisor` or `ticket-supervisor`.
4. **Only `readiness: approved` ACs are visible to the pipeline.** ACs at
   `draft` or `reviewed` are excluded by `scan_ac_store.py` before
   `ac_prioritizer.py` sees the list.

---

## Cross-References

- [AC authoring pipeline](ac-authoring-pipeline.md) — sequence view of
  how ACs reach `readiness: approved`.
- [/build-ac execution flow](build-ac-flow.md) — sequence view of the
  build-time flow.
- [AC readiness state machine](ac-readiness-states.md) — five states and
  the transitions exercised by this pipeline.
- [How to use the AC-driven development system](../../how-to/ac-driven-development.md) — task-oriented guide.
- [Agent Delivery Workflows](../agent_delivery_workflows.md) — parent
  diagram; shows how `epic-supervisor` and `ticket-supervisor` execute
  tickets produced by this pipeline.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [documentation-expert]: Rewrote to include all 7 components
  (validate_ac_schema.py, scan_ac_store.py, ac_prioritizer.py,
  generate_ticket_from_ac.py, mark_ac_done.py, build-ac agent, AC Store)
  per ticket 07 AC-4. Supersedes the ticket-01-only scope of the prior draft.
====================================================================
-->
