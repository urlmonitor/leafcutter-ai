---
title: "ADR-072: The Code-Aware Test Designer May Read Source"
description: "One pre-approval agent, test-designer (Sonnet), may open source and existing tests; it writes the test design and the file findings to separate fields, after a deterministic pre-pass and before the /plan-feature approval gate, and its success is judged from disk. The technical planner still may not read source (ADR-009), because a design or a file verdict written without opening the files cannot be trusted."
type: "adr"
status: "active"
created: "2026-10-14"
last_updated: "2026-10-14"
deciders:
  - BrainCandy
  - adr-author
components:
  - ac_driven_dev
  - testing_quality
  - agent_registry
related_docs:
  - docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - docs/architecture/adrs/ADR-033-agent-model-tiers.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/components/ac-driven-dev.md
  - docs/reference/ac-readiness-and-assignment-gates.md
  - docs/reference/plan-feature-workflow-rationale.md
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500c.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500d.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500d-5.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500d-5-i.yaml
related_code:
  - templates/workflows-js/plan-feature.js
  - config/agent_registry.json
  - config/ac_store_schema.json
  - templates/agents/it-po.md
  - scripts/ac_store/_approval_holds.py
  - scripts/ac_store/_impl_readiness_gate.py
  - scripts/ac_store/requirement_rule_check.py
  - scripts/build_phases_ac_store_rc.py
---

# ADR-072: The Code-Aware Test Designer May Read Source

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-14 |
| **Author** | adr-author (on request from BrainCandy) |
| **Supersedes** | None |

---

## Context

The L0 goal ACD-2500 ("every part of a requirement is written by whoever can actually get
it right") moves two jobs away from the technical planner (IT PO), which may not read
source ([ADR-009](ADR-009-itpo-no-source-code-access.md)):

- **Test design** ([ACD-2500c](../../acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500c.yaml)).
  [ADR-071](ADR-071-test-intent-is-not-a-test-contract.md) already split the planner's
  `test_intent` from the `test_spec` design and holds intent-only records as
  `test design pending`. Nothing yet writes the design, so those records cannot be built.
- **File judgments** ([ACD-2500d](../../acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500d.yaml)).
  These are whether each declared file really holds the behaviour, and which reference
  file a package-surface piece of work follows. The planner guesses both from the
  requirement text today.

Both jobs need someone to open files before the build starts. That is the one thing
ADR-009 forbids the planner to do. If no decision is recorded, one of three things
happens. The planner's restriction erodes ticket by ticket. Several agents grow
overlapping read access. Or the workflow starts judging file facts itself. Any of
these leaves designs and verdicts that nobody checked against the code.

The design was worked out in the G4 architect review of
[EPIC-RightJobRightAgent](../../../tickets/00_inbox/epics/EPIC-RightJobRightAgent/Master_Plan.md)
(ticket 29, ACD-2500c-1, comment "2026-10-14 14:06 — architect-review", sections 1–5 and 9).
It is recorded for ticket 27
([ACD-2500d-5](../../acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500d-5.yaml)).
Tickets 27–40 of the epic build it.

---

## Decision

### 1. One pre-approval agent reads source; the technical planner does not

Exactly one agent that runs before approval, `test-designer`, is permitted to open source
files and existing tests. Its canonical template is `templates/agents/test-designer.md` (the deployed
copies are build output, [ADR-001](ADR-001-self-hosting-boundary.md)), and it has one entry
in `config/agent_registry.json` with `spawned_by: ["plan-feature.js"]`. It MUST be pinned
to `model: sonnet` and MUST carry exactly `tools: Bash, Read, Write, Edit` (the Sonnet floor
of [ADR-033](ADR-033-agent-model-tiers.md) §2.6). It MUST NOT carry `Agent`, `Skill`, Grep,
Glob or any MCP search tool. Its template MUST forbid shell search of the repository
(`find`, `grep -r`, `rg`, `git grep`).

The IT PO (`templates/agents/it-po.md`) MUST still declare no source-code access. ADR-009
stays in force unchanged; this ADR amends nothing in it. A second pre-approval agent with
source access needs a new ADR.

### 2. Two output groups in separate fields

The agent MUST write its two outputs to disjoint record fields:

| Group | Fields |
|---|---|
| Test design (ACD-2500c) | `test_spec`, `test_design_authorship`, `test_design_opened_files` |
| File findings (ACD-2500d) | `file_findings`, `file_findings_opened_files`, `it_requirements.reference_file_path` (and clearing the `reference file pending` marker, §5) |

A run that produces only one group MUST leave the other group's fields untouched. Every
write MUST be a field-targeted edit of the AC YAML. The agent MUST NOT rewrite a whole
record. It MUST NOT touch `criteria`, `test_intent`, `assigned_agent`, `implements_pattern`,
`pattern_bindings`, `declared_files`, `covered_by`, `delivers_to`, `expects_from` or any
other `it_requirements` key. The rule check, run with `--before-ref HEAD` against the
committed planner output, is the deterministic backstop. Each opened-files list MUST name
the files the agent actually opened. Only "present and non-empty" is checked mechanically.

### 3. Deterministic pre-pass for file facts, agent judgment for the rest

File facts MUST come from `scripts/ac_store/design_prepass.py`, not from the agent and not
from the workflow. For each in-scope record it reports:

- the state of each declared file (`exists` / `to_be_created` / `neither`);
- whether each test directory exists;
- for each reference-file candidate, whether it exists and whether it has the same type
  (same lower-cased suffix) and is in the same area (same parent directory) as the
  deliverable.

The script MUST be read-only and MUST only `stat` the tree, never read file contents. It
MUST print one JSON document. Two runs on the same batch and tree MUST produce
byte-identical output. On any error it MUST exit non-zero and print nothing on stdout.

The agent MUST read the pre-pass report embedded in its prompt before it opens any file
(ACD-2500d-5). It MUST NOT re-derive any fact in the report. Judgment belongs to the agent:
the test design itself, each file verdict (`consistent`, `describes, does not implement`,
`absent, not to-be-created`, `behaviour found elsewhere`) and the choice of reference file,
with a one-sentence reason. The agent MUST NOT decide routing. A finding that questions
the assignment goes back to the planner (§4).

### 4. Stage order in /plan-feature

The test design MUST be a `pipeline` entry
`{agent: "test-designer", stage: "test-design", gate: "final"}` appended after the `itpo`
entry, whose gate becomes `"auto"`. It MUST NOT be a hook inside the `itpo` iteration. The
order is:

1. `it-po` authors (stage `itpo`);
2. `rule-check-itpo`;
3. automatic approve and commit of the `itpo` stage, so `HEAD` is the designer's before-state;
4. `design_prepass.py`;
5. `test-designer`;
6. `rule-check-test-design` (`--changed-since HEAD --before-ref HEAD`);
7. `approval_hold_report.py`;
8. hand-back of undecided file findings to `it-po`, at most 2 rounds, each followed by
   the rule check and the hold report again;
9. the final gate. It shows each approvable record's criteria next to its `test_spec` and
   lists held records separately with their reason and no approve option.

An `edit` retry re-dispatches `test-designer`, never `it-po`. After round 2, any finding
still undecided is shown as held and is never approved.

### 5. Success is judged from disk and fails closed

The designer's JSON reply (`{status, records: [{id, test_design, file_findings, reason}],
anomalies}`) MUST only route. It MUST NOT be read as proof of success. Success MUST be
read from disk by the rule check (changed records) and `approval_hold_report.py` (every
record). The step MUST fail closed:

- no pre-pass report: the designer is not dispatched and the stage fails;
- the designer returns `blocked` for the batch: the stage fails;
- the hold report is missing or unreadable: every record is treated as held;
- a designer that claims `written` but wrote nothing: the record reads `test design pending`.

A batch with no in-scope record is the one case that passes without a dispatch. The
pre-pass reports `records: []`, and the stage records a passed, skipped result.

### 6. Two hold reasons, one emission path

`reference file pending` and `file finding undecided` MUST be emitted only through
`APPROVAL_HOLD_CHECKS` in `scripts/ac_store/_approval_holds.py`. The order is
`test design pending`, `reference file pending`, `file finding undecided`, one reason per
record, first match wins. The reasons stay members of `HOLD_REASONS` (ADR-071 §4). The
readiness gate is not extended.

- **`reference file pending` is a carried marker.** The record's `hold_reason` field is set
  to exactly that value, and the hold is never inferred from a missing key.
  `config/ac_store_schema.json` MUST declare `hold_reason` with `enum` equal to
  `HOLD_REASONS`. The designer clears the marker when it fills
  `it_requirements.reference_file_path`.
- **`file finding undecided` is computed.** It MUST be derived from `file_findings` on disk
  (a non-`consistent` finding whose `decision` is null) and MUST NOT be stored as a marker.
  A stored marker would be a second source of truth that drifts from the findings. An
  undecided finding is an approval hold. It is NOT a rule-check failure.

/plan-feature's `apply-approval` step MUST receive only the ids the hold report returns as
not held. Held records stay `reviewed`.

### 7. must_catch is Sonnet-only

`must_catch` entries in `test_spec` MUST be written only by `test-designer`, from reading
the code, with no Opus sub-call (user decision 2026-09-28). The agent has no `Agent` tool,
so no sub-call route exists. Adding an Opus sub-call later needs evidence that Sonnet
misses mutants and an amendment that takes the ADR-033 §2.3 route.

---

## Consequences

### Positive

- Test designs and file verdicts come from a step that opened the files. The test writer
  and the planner's routing decisions get grounded input (ACD-2500c, ACD-2500d).
- ADR-009's boundary holds. Exactly one named, Sonnet-tier, search-less agent crosses it
  before approval, so source access is easy to audit.
- File facts are reproducible and cheap. Only judgment uses an LLM, and every outcome is
  checkable on disk.
- The existing generic loop, retry cap and re-approval rule cover the new stage, so there
  is no second retry path.

### Negative

- **plan-feature.js ratchet cost.** The file measures 2,819 lines against a 1,000 limit.
  Ticket 31 adds about 76 measured lines and ticket 39 about 16. Each commit MUST remove
  at least twice what it adds, by moving rationale comments verbatim into
  `docs/reference/plan-feature-workflow-rationale.md` (or a second rationale doc). That is
  real churn with no behaviour gain.
- **Paused runs cannot be resumed.** Runs paused at the old final gate (on `itpo`) before
  this change cannot be resumed and MUST be re-run. The final gate id stays `final-gate`
  but now belongs to `test-design`. The final commit subject becomes
  `plan-feature(TEST-DESIGN, final)`.
- **The M-5 bypass stays open.** /plan-feature approves through an agent edit
  (`apply-approval`: a `status-checker` edits `readiness`), not through `approve_acs.py`.
  This change filters that edit's id list through the same hold predicates that
  `approve_acs.py` uses. It does not route approval through the tool. Closing the bypass is
  a separate follow-up.
- Byte-identity of fields the agent does not own is enforced by the prompt and the
  committed `HEAD` before-state, not by a dedicated rule family.

### Operational

- Two rule families join the requirement rule check: `test design grounding` and
  `file findings consistency`. `design_prepass.py`, `approval_hold_report.py`,
  `_file_findings.py` and `_approval_holds.py` are deployed through `RULE_CHECK_DEPLOY_MAP`
  in `scripts/build_phases_ac_store_rc.py`.
- New record fields `file_findings` (closed objects, no `oneOf`) and
  `file_findings_opened_files`, plus the declared `hold_reason`, go into the one schema
  file. Both validators read that file.
- An empty batch followed by a resume asks the user once more at the gate. This is accepted.

---

## Alternatives

- **Two agents (a test designer and a separate file checker).** Rejected. Both would open
  the same declared files for the same records in the same stage, doubling reads and
  dispatches. Two agents with source access would widen the ADR-009 exception. The
  "separate outputs" need is met by disjoint fields (§2), not by separate agents.
- **An Opus sub-call for `must_catch`.** Rejected (user decision 2026-09-28). It needs the
  `Agent` tool and the ADR-033 §2.3 gatekeeper route, which adds a tier and a dispatch per
  record with no evidence yet that Sonnet misses mutants.
- **The workflow judges file facts itself.** Rejected. Existence, to-be-created and
  same-type/same-area checks in plan-feature.js would add measured lines to a file already
  2,819 over a 1,000 limit. They would also be untestable outside the Node driver and
  could not be reused by `approve_acs.py`. A standalone, byte-deterministic Python CLI is
  testable as a subprocess and keeps facts out of the LLM.
- **A hook inside the `itpo` iteration instead of a pipeline entry.** Rejected. The hook
  would run before the planner output is committed, so `--before-ref HEAD` could not prove
  that the designer changed only its own fields. An `edit` retry would re-dispatch `it-po`,
  which cannot read source and so cannot repair grounding errors.

---

## References

- Architect review: `tickets/00_inbox/epics/EPIC-RightJobRightAgent/29_TICKET-20261012-ACD-2500c-1.md`,
  comment 2026-10-14 14:06 (sections 1–5, 9).
- Originating ACs: ACD-2500c, c-1, c-2, ACD-2500d, d-1, d-2-i, d-3-i, d-5, d-5-i under
  `docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/`.
- [ADR-009](ADR-009-itpo-no-source-code-access.md): the IT PO has no source-code access (in force, not amended).
- [ADR-071](ADR-071-test-intent-is-not-a-test-contract.md): test intent versus test design, and the closed hold-reason list (adopted, not amended).
- [ADR-033](ADR-033-agent-model-tiers.md): model tiers and tool floors.
