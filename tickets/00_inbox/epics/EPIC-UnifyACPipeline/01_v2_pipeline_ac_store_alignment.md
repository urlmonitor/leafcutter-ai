---
title: "Wire AC store query and ac_creations/ac_amendments into the v2 ticket-creation pipeline"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: agent_orchestrated
actuation_contract: "When /create-ticket-v2 runs on a request that introduces genuinely new behaviour, the pipeline writes AC YAML files to docs/acceptance-criteria/{component}/{id}.yaml and the ticket body references the new AC IDs — matching the behaviour already delivered by the v1 /create-ticket pipeline."
files_touched:
  - templates/agents/business-analyst-v2.md
  - templates/agents/create-ticket-v2.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
ac_coverage: 0/7
---

# Wire AC store query and ac_creations/ac_amendments into the v2 ticket-creation pipeline

## Actor / Goal

As a developer using `/create-ticket-v2`, I need the v2 pipeline to produce and
write AC YAML files to `docs/acceptance-criteria/` for genuinely new behaviours —
so the AC traceability store stays current regardless of which pipeline I use.

## Context

The v1 pipeline (`/create-ticket`) already does this correctly:

1. `business-analyst.md` §Step 0.5 reads the AC store at `docs/acceptance-criteria/`,
   compares proposed criteria against active ACs, and outputs `ac_creations` and
   `ac_amendments` arrays in its JSON payload.
2. `create-ticket.md` delegates to the `ticket-wiring` skill, whose **Step 2.5**
   reads `ba_output.ac_creations` / `ba_output.ac_amendments` and writes or amends
   YAML files in the AC store.

The v2 pipeline (`/create-ticket-v2`) has two gaps:

**Gap 1 — `business-analyst-v2.md` omits the AC store query entirely.**
Its output contract (§Output Contract) has no `ac_creations` or `ac_amendments`
fields. The v2 BA (lines 190–239) mirrors the v1 field list except these two fields.
Without them, there is nothing for downstream steps to consume.

**Gap 2 — `create-ticket-v2.md` writes the ticket inline (Steps 3a/3b/4) and never
calls the `ticket-wiring` skill.**
Even if Gap 1 were fixed, `create-ticket-v2` assembles the ticket body and calls
`Write` directly rather than delegating to `ticket-wiring`. As a result, Step 2.5
(AC file writes) is structurally bypassed in the v2 path.

### v1 pipeline flow (correct baseline)

```
/create-ticket
  └─ business-analyst.md
       §Step 0.5 — reads AC store, produces ac_creations + ac_amendments
  └─ [routes: simple → refinement; standard/novel → it-po]
  └─ ticket-wiring SKILL.md
       Step 2.5 — writes/amends AC YAML files from ba_output fields
       Step 4   — verify + cross-link
```

### v2 pipeline flow (current — broken path)

```
/create-ticket-v2
  └─ business-analyst-v2.md
       (no AC store query; no ac_creations / ac_amendments in output)
  └─ [routes: trivial/simple → refinement; standard/novel → it-po]
  └─ create-ticket-v2.md Steps 3a/3b/4 (inline Write — bypasses ticket-wiring skill)
       (Step 2.5 never fires)
```

### Decision on ownership in the v2 flow

The user is unsure whether the v2 BA or the IT PO should own AC classification. The
answer follows from the v1 design intent: the BA owns AC store querying because it runs
before routing decisions are made (before refinement or IT PO). If AC classification
were deferred to IT PO, it would not fire on `trivial` / `simple` tickets (which skip
IT PO). Therefore:

- **`business-analyst-v2.md` must own AC store query + classification** (same
  responsibility as v1 BA §Step 0.5).
- **`create-ticket-v2.md` must invoke the `ticket-wiring` skill's Step 2.5 logic**
  after the ticket body is assembled (or replicate it inline with identical semantics).

### Critical constraint preserved

`create-ticket-v2.md` explicitly prohibits touching any v1 template. The fix must stay
within the v2 files and must not modify `templates/agents/business-analyst.md`,
`templates/agents/create-ticket.md`, or `templates/skills/ticket-wiring/SKILL.md`.

## Acceptance Criteria

- [ ] AC-1: `templates/agents/business-analyst-v2.md` contains a §Step 0 (or equivalent
  numbered step before §1 elicitation) that reads `docs/acceptance-criteria/index.yaml`
  when it exists, loads active ACs for the relevant component(s), and classifies each
  proposed AC as "covered by existing", "amends existing", or "genuinely new behaviour"
  — matching the semantics of v1 BA §Step 0.5.

- [ ] AC-2: `business-analyst-v2.md` output contract includes `ac_creations` and
  `ac_amendments` arrays in its JSON schema, with identical field shapes to those in
  `business-analyst.md` (`proposed_id`, `title`, `criteria`, `origin_agent` for
  creations; `ac_id`, `change`, `new_criteria` for amendments).

- [ ] AC-3: `business-analyst-v2.md` sets `origin_agent: "business-analyst-v2"` (not
  `"business-analyst"`) in each `ac_creations` entry, so compliance auditing can
  distinguish v1 vs v2 machine-generated ACs.

- [ ] AC-4: `templates/agents/create-ticket-v2.md` Step 3a and Step 3b (or a new
  dedicated step after ticket body assembly) invoke the AC YAML write logic from
  `ticket-wiring` Step 2.5 — either by loading and following that skill, or by
  replicating its Sub-step A and Sub-step B semantics inline — when `ba_output.ac_creations`
  or `ba_output.ac_amendments` is non-empty.

- [ ] AC-5: After running `/create-ticket-v2` on a request that the BA classifies as
  introducing at least one genuinely new AC (i.e. `ac_creations` is non-empty), a
  corresponding `docs/acceptance-criteria/{component}/{proposed_id}.yaml` file exists
  on disk and passes `python scripts/commit_guardian/check_ac_schema.py`.

- [ ] AC-6: When `docs/acceptance-criteria/` does not exist in the target project
  (pre-AC-store install), `business-analyst-v2.md` sets both `ac_creations: []` and
  `ac_amendments: []` and skips the AC query step without hard-failing — matching the
  graceful fallback in v1 BA §Step 0.5.

- [ ] AC-7: A test in `unit_tests/` (or `tests/`) asserts that `business-analyst-v2.md`
  contains all four of these strings: `ac_creations`, `ac_amendments`, `origin_agent`,
  and `docs/acceptance-criteria` — verifying the wiring is present at the template level
  without requiring a live agent invocation.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |
| AC-6 |      |                |           |
| AC-7 |      |                |           |

## Implementation Tasks

- [ ] Add §Step 0 (AC Store Query) to `business-analyst-v2.md` — insert before §1
  Elicitation Framework, following the same logic as v1 BA §Step 0.5:
  check if `docs/acceptance-criteria/` exists; if yes, load active ACs for
  relevant component(s); classify proposed ACs; populate `ac_creations` /
  `ac_amendments`.
- [ ] Extend `business-analyst-v2.md` output contract JSON schema to include
  `ac_creations` and `ac_amendments` arrays with correct field shapes.
- [ ] Set `origin_agent: "business-analyst-v2"` in the `ac_creations` entry template.
- [ ] Add AC YAML write step to `create-ticket-v2.md` after ticket body assembly
  (between Step 3a/3b and Step 4 / the Write call) — invoke `ticket-wiring` skill
  Step 2.5 logic or replicate it inline.
- [ ] Write test `tests/test_v2_pipeline_ac_store_wiring.py` (or
  `unit_tests/ticket_creation/test_v2_ba_ac_fields.py`) that asserts the four
  required strings are present in `business-analyst-v2.md`.
- [ ] Smoke-test with a real `/create-ticket-v2` invocation on a request touching
  a component that has a `docs/acceptance-criteria/{component}/` directory; confirm
  `.yaml` file is written and passes schema check.

## Risk & Safety

- Touches money? No.
- Touches data? Writes new `.yaml` files to `docs/acceptance-criteria/` — same
  behaviour as the v1 pipeline already does. Reversible by deleting the files.
- Reversibility? Template changes to `business-analyst-v2.md` and
  `create-ticket-v2.md` are text edits; revert via git. AC YAML files written by
  the pipeline can be deleted if incorrect.
- Regression risk: low. The v1 pipeline (`business-analyst.md`, `create-ticket.md`,
  `ticket-wiring` SKILL.md) MUST NOT be modified. This change is isolated to the v2
  parallel test path. Consumer projects on v1 only are unaffected.
- The `origin_agent: "business-analyst-v2"` distinction (AC-3) ensures v2-generated
  ACs are auditable separately from v1-generated ones — no schema change required
  (the field is already in the v1 schema; only the value changes).

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
