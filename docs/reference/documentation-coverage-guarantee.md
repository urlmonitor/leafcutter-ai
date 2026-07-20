---
title: "Reference: Documentation Coverage Guarantee"
description: "Lookup reference for the documentation-coverage guarantee: the declarative documentation_gates trigger policy, the documentation-verifier enforcement phase, and the Agent Contracts brief that is the single source of truth for what documentation is demanded and verified."
type: reference
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
  - doc_compliance
related_docs:
  - docs/architecture/components/doc-compliance.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/adrs/ADR-017-computed-quality-gates.md
source_ac: BO-2200c-6
---

# Documentation Coverage Guarantee

This reference describes the documentation-coverage guarantee end to end: which
change classifications trigger a documentation demand, how the
`documentation-verifier` phase enforces that docs are real and not placeholders,
and how the `## Agent Contracts` / `### documentation-expert` block serves as
the single brief both the writer reads and the verifier asserts against.

**Context:** The documentation-coverage guarantee is the documentation-specific
hardening of the computed quality gates (see
[ADR-017](../architecture/adrs/ADR-017-computed-quality-gates.md)). It sits
inside the [build-orchestration](../architecture/components/build-orchestration.md)
component because it is a drive-time gate concern, layered on top of the general
`(change_target, risk_surface)` mapping. Structural compliance of the
documentation artifacts themselves falls under
[doc-compliance](../architecture/components/doc-compliance.md).

---

## 1. The `documentation_gates` Trigger Policy

The declarative `documentation_gates` section of
`config/guardrail_gates.yaml` is the single place that controls when
`documentation-expert` is required. The ticket generator
(`scripts/ac_store/generate_ticket_from_ac.py::_build_agents_map`) reads it at
ticket-generation time and sets `documentation-expert: needed` in the ticket's
`agents:` map when any trigger fires.

### 1.1 `change_target_triggers`

`documentation-expert` is required when the AC's `change_target` matches **any**
value in the following list (union semantics — one match is sufficient):

| `change_target` | What it covers |
|---|---|
| `ui` | User-visible interface changes |
| `schema` | Database or data-structure schema changes |
| `pipeline` | Build and delivery pipeline changes |
| `docs` | Documentation-only changes |

Adding or removing a value from `change_target_triggers` in
`config/guardrail_gates.yaml` is a **configuration edit only** — no generator
code change is required (AC BO-2200a-1).

### 1.2 `risk_surface_triggers`

`documentation-expert` is also required when the AC's `risk_surface` matches
any value in the following list:

| `risk_surface` | Blast radius |
|---|---|
| `contract_boundary` | Change crosses a public API or system boundary |
| `safety` | Change that could cause harm, data loss, or irreversible state |
| `auth` | Change to authentication or authorisation logic |
| `privacy` | Change that touches PII or private user data |

`risk_surface_triggers` is reserved for future generator read-path activation.
The current generator reads `change_target_triggers` only; `risk_surface_triggers`
appears in the configuration for forward-compatibility.

### 1.3 Non-Triggering Classifications

Certain `(change_target, risk_surface)` pairs explicitly carry zero documentation
burden regardless of any trigger-list expansion. The `non_triggering_classifications`
list in `config/guardrail_gates.yaml` enumerates them:

| `change_target` | `risk_surface` | Rationale |
|---|---|---|
| `code` | `internal` | Purely internal refactor — nothing observable changes |
| `code` | `cost` | Cost-surface code change — no user-visible impact |
| `config` | `internal` | Internal configuration tweak |
| `prompt` | `internal` | Internal prompt adjustment |
| `infrastructure` | `internal` | Internal infrastructure change |

A pair on this list MUST NOT trigger `documentation-expert` even if its
`change_target` or `risk_surface` appears in a trigger list (AC BO-2200a-3).

---

## 2. The `documentation-verifier` Phase

The `documentation-verifier` is a conditional phase agent (template:
`templates/agents/documentation-verifier.md`) that enforces that every
documentation file named in the ticket's Agent Contracts block has a **real
change** in the git diff. It is the documentation analogue of the BP-1100
phantom-done enforcement posture — do not fold it into that family.

### 2.1 Priority and Position

| Priority | Agent |
|---|---|
| 6–7 | Coder (python-coder / sql-coder / frontend-coder) |
| 9 | test-runner |
| 10 | documentation-expert |
| 11 | pr-reviewer |
| 11.5 | user-surface-smoker |
| 11.8 | live-surface-tester |
| **11.9** | **documentation-verifier** |
| 12 | commit |

The verifier runs **after** documentation has been written (priority 10) and
**before** the commit is staged (priority 12). It cannot be suppressed by
re-ordering: the canonical phase-order sources register it at 11.9 (AC BO-2200b-6).

### 2.2 Injection Condition

`documentation-verifier` is injected into the ticket's `agents:` map **only**
when the documentation trigger fires (AC BO-2200b-4):

- `documentation-expert: needed` is added to the agents map, AND
- `documentation_required: true` is set in ticket frontmatter, AND
- `documentation-verifier: needed` is added to the same agents map.

When no documentation trigger fires, neither `documentation_required` nor
`documentation-verifier` appear in the ticket.

### 2.3 Non-Suppressibility

Once injected, `documentation-verifier` cannot be overridden to `not_needed` by
any hand-edit. The ticket generator treats a `not_needed` override as an invalid
state and restores the entry to `needed` on the next generation pass (AC
BO-2200b-5, BO-2200b-5-i). This is the non-suppressibility guarantee: a ticket
that requires documentation **must** pass verification before commit.

### 2.4 What the Verifier Checks

The verifier performs six steps against the required-docs list extracted from the
Agent Contracts block:

| Step | What it checks |
|---|---|
| 1 | v1 / v2 detection (presence of `## Agent Contracts`) |
| 2 | Parse required doc paths from `### documentation-expert` AC lines |
| 3 | Locate the worktree root via `git rev-parse --show-toplevel` |
| 4 | Obtain the changed-file list via `git diff HEAD --name-only` |
| 5 | Assert every required doc path appears in the changed-file list |
| 6 | Scan each changed doc for placeholder content (four sub-checks) |

**Step 5 — Independent evaluation guarantee (AC BO-2200b-2-i):** The verifier
checks ALL required docs without early exit. A doc present in the diff is
satisfied regardless of whether a sibling doc is missing. The blocker message
lists ONLY the paths absent from the diff; satisfied paths are never listed.

**Step 6 — Placeholder sub-checks:**

| Sub-check | What it detects |
|---|---|
| 6a | TODO / PLACEHOLDER / FIXME / Replace-with / QUESTION markers (via `scripts/build_placeholder_detection.py`) |
| 6b | TBD markers |
| 6c | Unfilled `{template_token}` patterns |
| 6d | Empty or heading-only stubs (no prose, code block, or list item) |

**Brevity is not a placeholder signal.** A short but genuine doc — real prose
with no placeholder markers — passes all four sub-checks (AC BO-2200b-3-i). The
verifier keys on placeholder *signatures*, not on length.

**Fail-closed posture.** An ambiguous parse, a missing Agent Contracts block on
a v2 ticket, or a script error in sub-check 6a all emit `(status: blocker)`,
never `(status: ok)`.

---

## 3. The Agent Contracts Brief (`## Agent Contracts` / `### documentation-expert`)

The `## Agent Contracts` section in a generated ticket body is the **single
source of truth** for what documentation is required (AC BO-2200c-5). Both the
writer and the verifier draw from the same block — there is no second,
separately-maintained required-docs list.

### 3.1 Block Structure

```markdown
## Agent Contracts

### documentation-expert
- [ ] AC-1: <genre> | <target_doc_path> | <content_constraint>
- [ ] AC-2: <genre> | <target_doc_path> | <content_constraint>
```

Each line names three pipe-delimited fields:

| Field | Description |
|---|---|
| `genre` | Diataxis genre: `how-to`, `reference`, `explanation`, `architecture-doc`, or `adr` |
| `target_doc_path` | Relative path of the documentation file to be written or updated (e.g. `docs/reference/some-guide.md`) |
| `content_constraint` | Human-readable statement of what the doc must contain or cross-link |

### 3.2 How the Block Is Generated

The ticket generator (`scripts/ac_store/generate_ticket_from_ac.py`) populates
the Agent Contracts block from the AC store fields:

- **Genre** — sourced from the parent L1 AC's `documentation_triggers` value
  (AC BO-2200c-3). When the parent L1 is absent or unresolved, the genre field
  is left blank rather than causing a crash (AC BO-2200c-3-i).
- **Target path** — derived from the AC's `doc_links` entries or generated from
  the component and AC identifier.
- **Content constraint** — populated from the `doc_links` richness fields
  (relationship, status). A bare path or missing optional fields is surfaced
  gracefully (AC BO-2200c-4-i).

### 3.3 Two Readers, One Block

| Reader | How it uses the block |
|---|---|
| `documentation-expert` | Contract-Aware Mode: reads every `- [ ] AC-N:` line under `### documentation-expert` as its brief; each line names a genre, a target path, and a content constraint to satisfy |
| `documentation-verifier` | Assertion mode: parses the same lines to extract the required-docs list; asserts each `target_doc_path` appears in `git diff HEAD --name-only` with real, non-placeholder content |

A change to the Agent Contracts block changes both what the writer is told to
produce **and** what the verifier checks, keeping brief and enforcement in lockstep.

---

## 4. Phase-Ordering Summary (Doc-Required Ticket)

The following phase ordering applies to any ticket where the documentation trigger
fires and `documentation-verifier` is injected:

```
...
python-coder / sql-coder / frontend-coder (priority 6–7)
  → test-writer (priority 5 — runs before coder)
  → test-runner (priority 9)
  → documentation-expert (priority 10) — reads Agent Contracts brief; writes required docs
  → pr-reviewer (priority 11)
  → documentation-verifier (priority 11.9) — asserts Agent Contracts coverage; fails on missing or placeholder docs
  → commit (priority 12)
```

Note: `documentation-expert` is injected via the post-coder surface path (the
`documentation_gates` canonical-order slot), not via the pre-coder
`flow_change_gates` slot. This ensures exactly one injection per ticket for
doc-triggering flow-change pairs (AC BO-2200d-1, `surgical_removal_guard`
invariant `DOC_EXPERT_SINGLE_INJECTION`).

---

## 5. Quick Reference

### Trigger Values

| Axis | Values that require `documentation-expert` |
|---|---|
| `change_target` | `ui`, `schema`, `pipeline`, `docs` |
| `risk_surface` | `contract_boundary`, `safety`, `auth`, `privacy` (reserved — not yet read by generator) |

### Files and Configuration

| Artifact | Path | Role |
|---|---|---|
| Trigger policy | `config/guardrail_gates.yaml` | `documentation_gates` section |
| Ticket generator | `scripts/ac_store/generate_ticket_from_ac.py` | Reads policy; injects agents map |
| Agent template | `templates/agents/documentation-verifier.md` | Verifier behaviour |
| Agent registry | `config/agent_registry.json` | `documentation-verifier` entry at priority 11.9 |
| Placeholder helper | `scripts/build_placeholder_detection.py` | Sub-check 6a scanner |

---

## See Also

- [Build Orchestration component](../architecture/components/build-orchestration.md) —
  pre-dispatch sequencing gates and the drive-time gate system that houses this guarantee.
- [Doc Compliance component](../architecture/components/doc-compliance.md) —
  structural compliance checks (frontmatter, length limits, description fields)
  that operate alongside the coverage guarantee.
- [ADR-017: Computed Quality Gates](../architecture/adrs/ADR-017-computed-quality-gates.md) —
  the two-axis `(change_target, risk_surface)` classification system this
  documentation gate is layered on top of.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-21 [documentation-expert]: Initial creation per AC BO-2200c-6.
  Reference doc for the documentation-coverage guarantee end to end:
  documentation_gates trigger policy (change_target_triggers + risk_surface_triggers
  + non_triggering_classifications), documentation-verifier phase (priority 11.9,
  six-step algorithm, fail-closed posture, non-suppressibility), and the Agent Contracts
  ## Agent Contracts -> ### documentation-expert block as the single source of truth
  for brief and enforcement. Cross-links to doc-compliance component doc,
  build-orchestration component doc, and ADR-017.
====================================================================
-->
