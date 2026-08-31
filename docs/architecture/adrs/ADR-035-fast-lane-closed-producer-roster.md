---
title: "ADR-035: The Fast Lane's Producer Roster Becomes Data, But Stays Closed"
description: "Replaces the fast lane's hardcoded literal agentType strings with a declared allowlist of producer agents selected by the criterion's assigned_agent, requires a declared-artifact diff plus a content assertion as the proof obligation for non-code deliverables, and sequences the work behind assigned_agent validation and a lane that can finish one run end to end."
type: "adr"
status: "active"
created: "2026-08-25"
last_updated: "2026-08-25"
deciders:
  - BrainCandy
components:
  - build_orchestration
  - ac_store
  - agent_registry
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/fast-lane-build.md
  - docs/how-to/compare-build-lanes.md
  - docs/how-to/done-proof-enforcement.md
  - docs/architecture/adrs/ADR-019-build-feature-inline-phase-dispatch.md
related_code:
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/build-feature.js
  - scripts/build_orchestration/fast_lane.py
  - scripts/ac_store/done_proof.py
  - config/agent_registry.json
  - config/ac_store_schema.json
---

# ADR-035: The Fast Lane's Producer Roster Becomes Data, But Stays Closed

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-25 |
| Deciders | BrainCandy |
| Author | Recorded from the 2026-08-25 fast-lane roster consultation; measurements re-verified against the `build-orchestration` worktree at authoring time |
| Supersedes | None |
| Context ADRs | ADR-019 (build-feature inline phase dispatch) — supplies the dynamic-dispatch precedent this decision leans on |

## 1. Context

The fast lane — *point at one acceptance-criterion id, get a pull request back* — carries a
**fixed** phase roster hardcoded in `templates/workflows-js/fast-lane-ship.js`: worktree →
resolve → claim → context-bundle → test-writer → coder → review → changelog → commit →
pull-request. Every dispatch names a **literal** `agentType` string. The coder slot is always
`python-coder` (three sites: lines 475, 635, 843). The only other producers the lane can reach
are `test-writer`, `pr-reviewer`, `commit`, `pull-request`, `worktree-agent` and
`status-checker`.

The AC store, meanwhile, already declares a producer per criterion in `assigned_agent`. The IT
PO populates it as part of normal authoring. **The lane never reads it.**

### The gap, measured

`assigned_agent` across the `build-orchestration` component — 842 records, 657 carrying a
value:

| `assigned_agent` | Count |
|---|---|
| `python-coder` | 402 |
| *(null)* | 185 |
| `llm-expert` | 174 |
| `architecture-diagram-author` | 33 |
| `documentation-expert` | 32 |
| `workflow-architect` | 8 |
| `reference-author` | 3 |
| `frontend-coder` | 2 |
| `test-writer` | 2 |
| `test-runner` | 1 |

**253 of those 657 name a producer the lane cannot dispatch** — every value except
`python-coder` (402) and `test-writer` (2, already a lane phase). Store-wide, **647** not-done
criteria name a non-coder producer.

> *Correction to the figures this consultation opened with:* the null count is **185**, not 81
> — the reported breakdown did not sum to its own stated total. The 253 and 657 figures are
> confirmed exactly. The store-wide non-coder figure is 647, not "roughly 643".

### The mechanism is not hypothetical

`templates/workflows-js/build-feature.js:1498` already dispatches `agentType: phaseName` — a
variable, driven by a per-ticket plan. **Dynamic dispatch is proven in this codebase.** What
the heavy lane needed to survive it, and the fast lane lacks:

- a **ticket body** as the per-producer brief (`## Agent Contracts`),
- a **read-back verification point** after each dispatch,
- a hardcoded **24-entry ordering table** (`phaseOrder`, `build-feature.js` lines 284-308).

### Why "any agent" is wrong

- `config/agent_registry.json` holds **60** agents; exactly **24** carry
  `is_ticket_phase: true`, and that set is identical to `build-feature.js`'s `phaseOrder`.
  The other 36 have never been proven to work as a workflow phase.
- **Registry and template contradict each other, and it is load-bearing.** 17 agent templates
  carry an "internal — invoked by X only" self-declaration in their own description. For the
  five documentation producers the contradiction is exact and checked:
  `architecture-diagram-author`'s template says *"internal — dispatched by
  documentation-expert only"* while its registry `spawned_by` reads
  `['ticket-supervisor', 'documentation-expert']`. Same shape for `adr-author`,
  `explanation-author`, `how-to-author`, `reference-author`. **87 not-done criteria name
  `architecture-diagram-author`.**
  *(The consultation reported 19 templates in contradiction with the registry; the
  self-declaration count measured here is 17. The five-way documentation-producer
  contradiction is verified directly; the exact total is reported-but-unverified.)*
- **2 registry entries have no template file at all**: `architect-review-deep`,
  `conflict-resolver-deep`.
- **Agents with confirmation gates cannot be workflow phases.** KI-BO-007 records the
  `pull-request` agent halting at its gate while the caller recorded `status: ok` with no PR.
- **KI-BO-020**: dispatching an agent under a role name that is not its own makes it *refuse*,
  and a refusal can be well-formed and schema-valid. All **nine** of the lane's
  release-on-failure dispatches (`release-on-*` labels at lines 506, 574, 596, 648, 668, 751,
  773, 871, 943) name `status-checker` under "You are the release-phase agent". Every one is
  dead.
- The registry has **no general vocabulary for "dispatched by a workflow."** The `spawned_by`
  value set is 27 tokens: 25 agent names, `user`, and one ad-hoc script token
  `finalize-feature.js`. There is no `fast-lane-ship` equivalent, so a dynamic roster cannot
  currently be made registry-legible without extending that vocabulary.

### The field is not trustworthy yet

`assigned_agent` is **unconstrained free text** (`config/ac_store_schema.json` line 254:
`oneOf` string-with-`minLength: 1` or null) with **no registry cross-check** — while the very
same validator does referential integrity for `components` one field over
(`validate_ac_schema.py` line 235 → `components_field_errors(data, registry_ids)`).

The store already contains values that are not agents at all: **23** records naming
`finalize-feature-workflow` (a workflow script) and **1** naming `create-ticket` (a slash
command retired by ADR-012). The field nonetheless already reaches a live dispatch target via
`generate_ticket_from_ac.py` → the heavy lane.

### The binding constraint is proof, not dispatch

A grep for `assigned_agent|test_required` across `scripts/build_orchestration/` and
`templates/workflows-js/` returns **one passthrough** (`build_dataflow.py:157`,
`rec.get("test_required", True)`) and **two prose mentions** (`quick-fix.js:408`,
`plan-feature.js:2453`). `fast_lane.py` reads **neither** field. The done chain is blind to
both.

Therefore: **adding a documentation phase without changing the proof chain converts KI-BO-013
from "jams at commit" into "jams at commit having also written the doc" — strictly worse.**

- `done_proof` scans only `.py` and `.ts`/`.tsx` for `# covers:` tags
  (`done_proof.py:428`, `944-947`). A markdown deliverable has **no tag surface**, so its only
  admissible proof today is a Python test asserting text appears in a file — a presence-only
  assertion by construction. **Automating that loop is automated phantom-done.**
- The existing doc-proof mechanism, the `documentation-verifier` agent, is **ticket-shaped**:
  it reads its required-doc list from the ticket body and takes `ticket_path` as a required
  input. It is therefore structurally inaccessible to a ticket-less lane.

### Engine limits

The workflow engine exposes only `agent()` and `parallel()` as awaited primitives — no
filesystem access, no command primitive.

> **INFERENCE, NOT MEASUREMENT.** Sub-agent nesting is capped at depth 1, which *would* put the
> internal-only documentation producers at depth 2 if they were reachable only *through*
> `documentation-expert`. This ADR does not treat that as established, and one piece of
> evidence cuts against it: the registry lists `ticket-supervisor` in `spawned_by` for all five
> of those producers, so direct dispatch is at least nominally permitted. The depth question
> must be settled empirically before any roster design depends on it.

## 2. Decision

### Decision 1 — The roster becomes DATA, not literals, and it does NOT become open

The fast lane **will** replace its literal `agentType` strings with a **closed producer
roster**: an allowlist of a small number of agent ids declared in **one place**. Each entry
**MUST** carry:

1. a hand-written prompt,
2. a **canonical self-name** used in its dispatch — never an invented role name,
3. a **declared proof obligation**.

Selection **MUST** be: *pick from the allowlist by the criterion's declared producer; refuse
the whole set if it names anything outside it.* The lane **MUST NOT** dispatch an agent that
is absent from the allowlist, and **MUST NOT** fall back to `python-coder` for an unrecognised
producer.

This is what `BO-2400f-12` already presupposes. Its Gherkin is phrased against **"the run's own
phase roster"** rather than naming documentation:

> *Then it decides, for each member of the set, whether the run's own phase roster contains a
> phase that produces the deliverable that member declares and a phase that produces the proof
> that member's done-obligation requires.*

A literal roster cannot answer that predicate. A declared one can.

### Decision 2 — Non-code proof is a declared-artifact diff PLUS a content assertion

A non-code deliverable's proof obligation **MUST** be **both**:

1. the criterion's **declared output path changed non-trivially** in the run's diff, **and**
2. **at least one content assertion** derived from the criterion.

The lane **MUST** verify the diff by **re-reading the diff itself**. It **MUST NOT** accept the
producing agent's self-report as evidence.

The content assertion is **not optional**, and the reason is recorded plainly as a cost:
**diff-presence alone cannot distinguish a real document from a placeholder.** BrainCandy chose
this over the cheaper diff-only variant for exactly that reason.

**Prerequisite, discovered while recording this.** The consultation assumed `doc_links` already
carries the output path as `relationship: modifies|creates`. It does not, in the sense
required: `relationship` is an **unconstrained free-text string** in the schema (line 497,
description only, no `enum`), and the store's actual usage is 15+ distinct values dominated by
`describes` (3,639). `modifies` appears 322 times and `creates` **11**. So the declared-output-
path input this decision depends on **must be constrained before Decision 2 is implementable**.
The decision stands; its input does not exist yet in usable form.

### Decision 3 — Sequencing

**No producer will be added to the roster until all three of the following hold:**

1. `assigned_agent` is **validated against the registry** — the same referential-integrity
   treatment `components` already receives.
2. `BO-2400f-12`'s **up-front refusal** ships.
3. **KI-BO-019** and **KI-BO-020** are fixed, so the lane can complete a single end-to-end run.

Rationale: **building a dynamic roster on a lane that has never once finished makes new
failures indistinguishable from the foundation's.**

> **Numbering note.** KI-BO-019 and KI-BO-020 as cited here are the entries at
> `docs/known-issues/build-orchestration.md` lines 967 and 1085 — the context-bundle
> pass-through halt, and the dead `status-checker` release path. This document collided on
> `main` on 2026-08-25; the branch's own KI-BO-019/020 were renumbered to KI-BO-022/023. Cite
> by title, not by number alone.

### Explicitly deferred, not settled

- **Which agents join the allowlist first.** Two independent assessments split between
  `documentation-expert` and `llm-expert`. The disagreement is itself informative:
  `llm-expert` is the easiest to add *precisely because the proof gate is already vacuous for
  markdown* — "no gate change needed" and "the gate proves nothing here" are the same sentence.
  Ease of adding it is a symptom of the hole, not evidence the hole is closed.
- **Whether the registry gains a vocabulary for workflow-dispatch** — i.e. extending
  `spawned_by` beyond its 25 agent names, `user`, and the ad-hoc `finalize-feature.js`.

## 3. Consequences

**Good.**

- The roster becomes inspectable. Today, answering "can the lane build this criterion?"
  requires reading `agentType` string literals scattered across ten call sites in
  `fast-lane-ship.js`. A declared roster makes `BO-2400f-12`'s predicate computable.
- 253 build-orchestration criteria (647 store-wide) get a **named reason** for being
  un-buildable instead of silently routing to `python-coder` or nowhere.
- Requiring a canonical self-name in each dispatch structurally forecloses the KI-BO-020
  refusal class — the failure that killed all nine release dispatches.
- Re-reading the diff, rather than trusting a self-report, makes the doc-proof gate the same
  kind of evidence as the code-proof gate.

**Bad — and deliberate.**

- **The store can declare a producer the lane still refuses, and that gap is intentional.**
  A closed roster means `assigned_agent: workflow-architect` (8 records) stays un-buildable by
  the fast lane until someone hand-writes that entry. Refusal is the designed behaviour, not a
  defect to be reported. The alternative — dispatching whatever the field says — is the
  rejected Alternative A below.
- Every allowlist entry is **hand-written work**: a prompt, a self-name, a proof obligation.
  The roster will not grow by configuration alone, and it will lag the store.
- Decision 3 means **none of this ships soon.** Three prerequisites gate it, one of which
  (a lane that finishes end to end) has never been true.
- Decision 2 has an unbuilt input: `doc_links.relationship` must be constrained first.
- The content assertion is **derived from the criterion**, so its strength is bounded by how
  specifically the criterion was written. A vague criterion yields a weak assertion. This
  narrows the phantom-done window; it does not close it.

**Neutral but load-bearing.**

- This ADR changes no code. It records the decision so the sequencing is not re-litigated when
  the first documentation criterion looks cheap to automate.
- **71 `llm-expert` criteria are reported to be already `done` via presence-only assertions.**
  This figure was carried into the consultation and is **not re-verified here** — recorded as
  reported-but-unverified. If it holds, those criteria are a pre-existing debt this decision
  does not retire.

## 4. Alternatives

**A — Fully open dispatch on the registry.** Let the lane dispatch any of the 60 registered
agents named by `assigned_agent`. **Rejected.** Only 24 carry `is_ticket_phase: true`; 2 have no
template file; 17 templates self-declare internal-only invocation in contradiction with their
registry `spawned_by`; and confirmation-gated agents cannot be phases at all (KI-BO-007). Open
dispatch converts every one of those contradictions into a runtime failure — and KI-BO-020
shows the failure can be *schema-valid*, so it would not even look like one.

**B — Per-AC roster selection (a roster computed per member of the build set).** **Rejected:
the red baseline becomes semantically void.** The lane's TDD gate depends on the whole set
being red before any producer runs. Under per-AC rosters, a test written for member 3 goes
green the moment member 2 lands, and the gate can no longer distinguish "the implementation
worked" from "a sibling's work happened to satisfy it." The lane's central anti-phantom-done
mechanism would report success on evidence it did not earn.

**C — Honour `test_required: false` as a licence to skip proof.** **Rejected on arithmetic.**
Only **91 of the 647** not-done non-coder-producer criteria declare the field at all — it
addresses **14%** of its target population and gives the remaining 86% a free pass **by
omission**. A gate whose default is "no field, therefore no proof required" is not a gate. It
also inverts the store's own posture, where an absent field means unspecified, not waived.

**D — Diff-presence only, without a content assertion (the cheaper variant of Decision 2).**
**Rejected.** A file that changed is not a file that says anything. Diff-presence alone cannot
distinguish a real document from a placeholder, which is the exact failure mode the fast lane
exists to prevent. BrainCandy chose the more expensive option knowingly.

## 5. References

**Known issues** (`docs/known-issues/build-orchestration.md`):

- **KI-BO-007** (line 111) — `build-feature` counts a phase as completed when the agent halted
  without doing it, yielding `status: ok` with no PR. The confirmation-gate hazard.
- **KI-BO-013** (line 383) — a documentation-only AC anywhere in a resolved build set jams the
  fast lane at commit, because `test_required: false` is honoured by nothing. The issue
  Decision 3 refuses to make worse.
- **KI-BO-019** (line 967) — the context bundle is passed through an agent's JSON return value,
  so a large bundle arrives as a file path and the fail-closed gate halts a run whose bundle was
  fine. Sequencing prerequisite 3.
- **KI-BO-020** (line 1085) — the fast lane's release-on-failure path is dead: it dispatches
  `status-checker`, which refuses the role, so aborted runs strand their claims. Sequencing
  prerequisite 3, and the origin of the canonical-self-name requirement in Decision 1.

**Acceptance criteria** (`docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/`):

- **`BO-2400f-12`** and its children **`BO-2400f-12-i`**, **`BO-2400f-12-ii`** — the up-front
  producibility refusal. Its "the run's own phase roster" phrasing is what Decision 1 makes
  answerable.
- **`BO-2400c-1-iii`**, **`BO-2400c-1-vi`** — resolved-build-set constraints.
- **`BO-2400f-10-i`**, **`BO-2400f-10-ii`** — the refusal-path obligations this roster must
  satisfy.

**Code:**

- `templates/workflows-js/fast-lane-ship.js` — the literal roster this decision replaces.
- `templates/workflows-js/build-feature.js:1498` — `agentType: phaseName`, the dynamic-dispatch
  precedent; `phaseOrder` at lines 284-308, the 24-entry table.
- `scripts/build_orchestration/fast_lane.py` — reads neither `assigned_agent` nor
  `test_required`.
- `scripts/ac_store/done_proof.py:428, 944-947` — `.py` / `.ts` / `.tsx` only.
- `config/ac_store_schema.json:254` — `assigned_agent` as unconstrained free text;
  line 497 — `doc_links.relationship` likewise.

**Related decisions:**

- [ADR-019: build-feature inline phase dispatch](ADR-019-build-feature-inline-phase-dispatch.md)
  — the heavy lane's dynamic dispatch.
- [ADR-012: retire create-ticket.js](ADR-012-retire-create-ticket-js.md) — retired the command
  that one AC still names as its producer.

## 6. Review Criteria

Revisit this decision if any of the following becomes true:

- The allowlist grows past the point where hand-writing each entry is the bottleneck, making
  the closed/open trade-off worth re-pricing.
- `assigned_agent` gains registry validation **and** the store's values converge on the 24
  `is_ticket_phase` agents, at which point Alternative A becomes materially less dangerous than
  it is today.
- A content-assertion mechanism appears that does not depend on the criterion's own
  specificity — the current bound on Decision 2's strength.
- The depth-2 nesting question is settled empirically in either direction; a measurement there
  changes which documentation producers are reachable at all.
