---
title: "How documentation coverage flows through the pipeline, and why it does not work"
description: "End-to-end trace of the documentation-coverage mechanism — which agent writes which field, which component reads it, and the four places where the writing side and the reading side disagree."
type: explanation
status: active
created: 2026-08-31
last_updated: 2026-08-31
components:
  - ac_driven_dev
  - ac_store
  - build_orchestration
  - documentation_system
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/reference/false-green-mechanisms.md
  - docs/architecture/adrs/ADR-012-retire-create-ticket-js.md
---

# How documentation coverage flows through the pipeline, and why it does not work

This traces one question end to end: **when a piece of work needs documentation,
how does the system decide that, decide what to write, and check it happened?**

Three separate mechanisms answer those three questions. None of them consults
the others. The result is a documentation demand placed on almost every ticket
and satisfiable by almost none.

Measured on `EPIC-StartingNewWorkTheProperWayAlways` (25 tickets), the epic where
this surfaced:

| | |
|---|---|
| Tickets carrying a documentation demand | **25 of 25** |
| Tickets that own the document they are told to produce | **1 of 25** |

The drive halted on it. Three tickets blocked at `documentation-verifier`; the
other 22 would have blocked the same way on reaching that phase.

---

## 1. Who writes what

Four authors contribute to the documentation decision. They never see each
other's output directly — everything passes through the AC store.

| Author | Field | Meaning to its author | Where |
|---|---|---|---|
| **Product Owner** | `documentation_triggers` | Which Diataxis genres this feature needs. Required on every L1; `documentation_rationale` required when `[]`. | L1 only (schema-enforced) |
| **Business Analyst** | `criteria` | The Gherkin behaviour. Reads the parent's `documentation_triggers` to decide whether to author documentation ACs at all. | L2 / L3 |
| **IT PO** | `doc_links` | **Related reading for the implementer** — see §4.1, this is the crux | L2 / L3 |
| **IT PO** | `change_target`, `risk_surface` | ADR-017 classification of the *code* change | L2 / L3 |

What IT PO is actually told about `doc_links` (`templates/agents/it-po.md` §2.6):

> Add entries pointing to architecture docs, component docs, and ADRs that
> **describe** the relevant component. Use `relationship: describes` for
> architecture documentation. […] If a relevant architecture doc does not exist
> yet, set `status: planned`. Never link to source files.

Note what is absent: there is **no field, and no instruction, for "the document
this record produces."** `doc_links` is specified purely as context.

---

## 2. What the generator does with it

`scripts/ac_store/generate_ticket_from_ac.py`, at ticket-generation time. Three
independent computations:

**2a. Is documentation required?** — `_build_agents_map`

Reads `config/guardrail_gates.yaml`:

```yaml
documentation_gates:
  change_target_triggers: [ui, schema, pipeline, docs]
  non_triggering_classifications:
    - {change_target: code,   risk_surface: internal}
    - {change_target: config, risk_surface: internal}
    ...
```

There are **two** trigger dimensions, and either one alone is sufficient:

- `change_target` intersects `change_target_triggers` (BO-2200a-1), **or**
- `risk_surface` matches `risk_surface_triggers` (BO-2200a-2).

A match on either adds `documentation-expert`, unless the
`(change_target, risk_surface)` pair appears in `non_triggering_classifications`
(BO-2200a-3). Surviving that also injects `documentation-verifier` and sets
`documentation_required: true` (BO-2200b-4).

> The comment above `risk_surface_triggers` in `guardrail_gates.yaml` calls it
> *"reserved for future use … not yet read by the generator"*. **That comment is
> stale.** BO-2200a-2 wired it up on 2026-07-17 and it is read at
> `generate_ticket_from_ac.py:894`. Anyone reasoning about the trigger policy
> from the config file alone will conclude one dimension is live when two are.

**Neither dimension looks at `doc_links`.** The decision is made entirely from
the classification of the code change.

**2b. Which genre?** — `_resolve_genres_from_parent`

From the parent L1's `documentation_triggers`. Unresolvable parent yields the
explicit marker `(unspecified genre)` rather than a silent blank (BO-2200c-3-i).

**2c. Which document?** — `_extract_doc_path`

Returns the **first** `doc_links` entry whose path contains a `/`. It ignores
`relationship`. It ignores `status`. With no usable `doc_links` it invents
`docs/<genre>/<slug>.md`.

The three are then rendered into the ticket:

```
## Agent Contracts
### documentation-expert

Existing docs to update / cross-link:
- docs/reference/plan-feature-layout-and-startup-checks.md (relationship: describes | status: planned | relevance: …)

- [ ] AC-1: reference-doc | docs/reference/plan-feature-layout-and-startup-checks.md | the copy that executes is …
```

That `- [ ] AC-N:` line is the contract. Everything downstream reads it and
nothing else.

---

## 3. What happens at run time

**`documentation-expert`** (Contract-Aware Mode, `templates/agents/documentation-expert.md:315-329`):

1. Read every `- [ ] AC-N:` line under `### documentation-expert`.
2. Extract the doc requirement from each.
3. Pass it to the matching specialist (`reference-author`, `how-to-author`,
   `architecture-diagram-author`, `explanation-author`, `adr-author`) **to write**.
4. If any AC was not satisfied, surface it in `Open Questions`.
5. Sign off, with `completion_manifest: {doc_written, cross_links_added, diataxis_genre_correct}`.

There is **no existence check** anywhere in that sequence. The agent either
writes or it does not. Step 4 is its only exit when it cannot.

**`documentation-verifier`** (priority 11.9, before `commit`):

1. Parse the `- [ ] AC-N:` lines as `<genre> | <target_path> | <content_constraint>`.
2. Collect `target_path` values into `required_docs`.
3. Assert each appears in the git diff (branch range ∪ working tree).
4. Fail **closed** on anything it cannot parse or resolve.

Four distinct blocking shapes, worth knowing apart:

| Shape | Result |
|---|---|
| No `## Agent Contracts` section at all | no-op — the only safe rendering |
| Section present, `### documentation-expert` subsection absent | **blocker** (`:133-137`) |
| Subsection present, zero parseable AC lines | **blocker** (`:162-167`) |
| AC line parses, target not in diff | **blocker** |

---

## 4. Where it breaks

### 4.1 A context field is read as a contract field

This is the root cause and everything else follows from it.

IT PO authors `doc_links` as *"architecture docs that describe this component,"*
with `relationship: describes` as the instructed default. `_extract_doc_path`
reads `entry[0]` as *"the document this ticket must produce."*

Consequence in the epic: 22 tickets each cross-linked
`docs/reference/plan-feature-layout-and-startup-checks.md` as background reading.
All 22 were told to create it. It is one page, and a 23rd ticket
(`ACD-2100d-4`, the only record in the epic declaring `relationship: creates`)
exists specifically to author it.

Reordering cannot resolve this. `ACD-2100d-4` documents behaviour those tickets
deliver, so it legitimately depends on them; making them wait for it closes a
cycle (`a-1 → d-4 → a-5 → a-1`, all three edges present in the store today).

### 4.2 The trigger is the code classification, not the documentation need

`change_target: pipeline` on 22 records and `docs` on 3 means all 25 acquire a
documentation demand. Nothing checks whether the record has anything of its own
to write. Ownership information exists in the store — it is simply not on the
path that makes the decision.

### 4.3 `status` is an authored snapshot of a moving target

`status: planned` is written by hand, by IT PO, at authoring time. It is:

- **unvalidated** — `validate_ac_schema.py` has no `doc_links` handling of any
  kind: no shape check, no enum for `status`, no enum for `relationship`;
- **unconsumed** — no gate reads it; the only reader is
  `_build_doc_links_cross_link_lines`, which renders it as prose;
- **never refreshed** — nothing marks it `exists` when the page lands.

It is already wrong in the store: ticket 22 of the epic carries
`describes / exists` for a page that must change in its own diff.

### 4.4 "Already documented" is inexpressible

The verifier satisfies a target only if its path appears in the diff. An agent
that correctly determines the information is already documented, and therefore
changes nothing, produces no diff entry — and is blocked. There is no way for
the system to say *"this was already true."*

---

## 5. What has to change

Ordered by dependency. Steps 1 and 2 are prerequisites: doing 3 before them
switches documentation off across the repo rather than fixing it.

**1. Validate the field that is about to become load-bearing.** `doc_links` has
no schema validation at all. If `relationship` is to carry the ownership
decision, a typo must not silently delete a document from the build. Add shape
validation and an enum to `validate_ac_schema.py`.

**2. Backfill ownership, and add the gap check.** Only ~18 of 3,701 records
carry `relationship: creates`. Until the store records who owns what, an
ownership-driven trigger yields near-zero documentation. The gap check —
*every `planned` cross-link target is `created` by some record* — is a
whole-store invariant, so it belongs in `validate_ac_schema.py`, which walks a
directory. It cannot be a commit hook: the AC hooks see only the staged index.

**3. Give IT PO the concept.** Its template has no notion of a document a record
produces. Until §2.6 distinguishes *"docs I should read"* from *"the doc I
deliver,"* the store will keep being authored the way that produced this defect.

**4. Select the doc target by ownership, not position.** `{creates, modifies}`
only — **not** the wider `_EDIT_SURFACE_RELATIONSHIPS` set used for
`files_touched`. That set includes `specifies` and `constrains`, which the store
uses to mean *"this doc governs me"*: **169 records link
`docs/reference/ac-schema.md` as `specifies`**, and the wide set would tell all
169 to write it — the same collision, an order of magnitude larger.

Doc ownership should be a strict *subset* of edit-surface membership, so a doc
target is never absent from `files_touched`. Do not narrow
`_EDIT_SURFACE_RELATIONSHIPS` itself; that silently shrinks `files_touched`
store-wide, which is the phantom-done surface.

**5. Suppress the phase, not just the rendering.** A record owning no document
must not get `documentation-expert` / `documentation-verifier` /
`documentation_required` at all. Emitting no AC line while leaving the
subsection is not sufficient — see the blocking table in §3. A partial
suppression already exists (`documentation_triggers: []` drops the subsection at
`generate_ticket_from_ac.py:2084`) and it produces the *worse* outcome: the
agents stay in the map, `delivers_to`/`expects_from` keep the `## Agent
Contracts` heading alive, the verifier hits its subsection-absent blocker, and
`documentation-expert` falls through to v1 free-text mode with no brief at all.

**6. Make `documentation-expert` idempotent, and the verifier able to accept
it.** Check the target first; three distinguishable outcomes — *already
satisfied*, *updated*, *authored*. Declining on ownership grounds should be a
failed sign-off, not an `Open Question`. This cannot ship without the matching
verifier change: an already-satisfied target produces no diff entry, so the
verifier must be able to accept a doc absent from the diff **after reading it**
and running its own content and placeholder checks. Ship the agent half alone
and every already-documented target becomes a hard stop.

**7. Amend `BO-2200a-1`.** It is approved and done, and states each of
`ui`/`schema`/`pipeline`/`docs` "on its own, causes documentation-expert to be
required." Step 5 makes that necessary but no longer sufficient. It needs an
`amended_by` entry and its fixture needs an owning `doc_link`.

---

## 6. What is deliberately not being proposed

**Runtime-discovered ownership** — letting whichever ticket first needs a fact
write it. It removes the ownership bookkeeping entirely and is attractive for
that reason, but tickets run in parallel batches: 22 agents independently
concluding "not documented yet, I will write it" against one page is a write
race. It also weakens the gate in the place this repo has been burned most —
*"is this information documented somewhere?"* is a semantic judgment, where
*"is this file in the diff?"* is mechanically checkable.

The cost of not doing it: a fact nobody was assigned to document stays
undocumented and no gate complains. That is what the §5.2 gap check is for.

---

## Provenance

Written 2026-08-31 from the post-mortem of the
`EPIC-StartingNewWorkTheProperWayAlways` halt. Every count in this document was
measured against the store at that date rather than estimated; the flow steps
cite the source files so they can be re-checked when the code moves.

The pipe-delimited AC-line format described in §2 landed separately in #602
(`f1726aefa`) as the fix for `KI-ACD-002`; before it, the generator emitted
`[genre] path — constraint` and the verifier rejected every generated ticket
outright. That was a different defect in the same seam, and it is fixed.
