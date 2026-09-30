---
title: "ADR-044: Example Content Declares Its Example Product in One `example_product` Key, Cross-Checked Against Its Product Root"
description: "Every example artifact and example acceptance criterion carries one optional top-level `example_product` key naming its product-root slug, absent on the project's own record and cross-checked against the product root the artifact lives under, because a marker inferred from location is invisible to a reader holding only the file, and a marker nothing cross-checks is a second hand-maintained field that drifts."
type: "adr"
status: "active"
created: "2026-09-16"
last_updated: "2026-09-17"
deciders:
  - BrainCandy
components:
  - ux_prototyping
  - ac_store
related_docs:
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-3.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-3-i.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-3-ii.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-2.yaml
  - docs/architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md
  - docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md
  - docs/architecture/adrs/ADR-025-first-class-flow-decisions.md
  - docs/architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md
  - docs/architecture/adrs/ADR-043-journey-record-carries-its-own-behind-mark.md
  - docs/architecture/components/ux-prototyping.md
  - docs/reference/ac-schema.md
related_code:
  - docs/product-truth/schemas/flow.schema.json
  - docs/product-truth/schemas/mockup.schema.json
  - docs/product-truth/schemas/mock-data.schema.json
  - docs/product-truth/scripts/product_ownership.py
  - docs/product-truth/scripts/validate_product_truth.py
  - scripts/ac_store/scan_ac_store.py
---

# ADR-044: Example Content Declares Its Example Product in One `example_product` Key, Cross-Checked Against Its Product Root

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-16 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded during the `UXP-700d-3` self-declared example marker pass of 2026-09-16 |
| Supersedes | None |

## Context

The product-truth store holds two kinds of content side by side: the project's own
record (`docs/product-truth/{flows,mockups,mock-data}/leafcutter/…`) and the example
product **Fern & Fig** (`…/fern-and-fig/…`), which
[ADR-022](ADR-022-mockups-are-the-real-app-in-mock-mode.md) requires to stay in place and
stay addressable (separation, never deletion). The AC store holds 18 example criteria
(`UXP-210-buy-a-plant`, `UXP-220-track-an-order`) next to thousands of real ones, under
the same component directories.

[`UXP-700d-1`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-1.yaml)
settled *ownership*: an artifact belongs to the product whose root it lives under,
decided by `docs/product-truth/scripts/product_ownership.py` from the first
`/`-segment of the artifact id, never from content.
[`UXP-700d-3`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-3.yaml),
the AC this record serves, requires the opposite axis as well: an example artifact or
criterion, **read on its own** by someone who does not know where it came from, must
itself state which product it belongs to and that the product is an example; the
project's own artifacts must carry no such statement; and a statement that disagrees
with the product root must be reported, naming both.

The cost of not deciding is concrete.

**The marker is currently spelled five different ways, and none of them says "example".**

| Surface | What exists today | Why it is not the marker |
|---|---|---|
| Flow | `product: "Fern & Fig"` / `"Leafcutter"` | A display name, present on *every* flow including the project's own, so its presence says nothing. |
| Flow, mockup | `source: mock` / `real` (required on both) | Means "renders mock/demo data vs a real system surface". A real Leafcutter screen rendered in mock mode (ADR-022) is `mock` too. Absent from mock-data and ACs. Names no product. |
| Flow, mockup, mock-data | `realization: built` / `spec` / `mock` (optional) | Means "does it exist in the repo today". Absent defaults to `built`; the Fern & Fig catalog omits it entirely. Names no product. |
| AC | `product: fern-and-fig` (18 files) | Read by `scan_ac_store._is_example_content` (UXP-700d-2), but undocumented in `docs/reference/ac-schema.md` and spelled like the flow's display-name field while meaning a root slug. |
| Mock-data | nothing | The Fern & Fig catalog carries no example statement of any kind. |

**Two agents are about to spell the field.** `UXP-700d-3`'s `delivers_to` hands the marker
to `frontend-coder` ("so any reading surface can label it without consulting a
registry") in a later ticket. `architect-review` classified this ticket LARGE on exactly
the shape [ADR-043](ADR-043-journey-record-carries-its-own-behind-mark.md) was written
for: a new durable key on `flow.schema.json`, whose `additionalProperties: false`
posture ([ADR-025](ADR-025-first-class-flow-decisions.md)) means the name is fixed the
moment it is registered, with its consumer not yet written.

**An unchecked declaration drifts.** `UXP-700d-3`'s own notes say it: without the
disagreement clause the marker becomes "a fourteenth hand-written summary". Ownership
already has one authority (the product root, per `UXP-700d-1`); the declaration must be
checked against that authority, not become a rival to it.

**ACs have no product root.** The AC store is organised by component, not by product, so
"the product root it lives under" has no direct meaning for a criterion. Each of the 18
example ACs does, however, carry an `implemented-by-step` `doc_link` into
`docs/product-truth/flows/fern-and-fig/`, and no project-owned AC does — project ACs that
point at Fern & Fig artifacts (e.g. `UXP-515`, `UXP-614`) use other relationships.

**The store holds a root that is neither the project nor an example.**
`docs/product-truth/mock-data/guardrails/frontend-ac-declarations.mock.json` has id
`guardrails/…` and is the project's own spec dataset. `product_ownership.is_example_artifact_id`
calls it example content (root ≠ `leafcutter`); `product_ownership.own_record_flows`
would not (root ≠ `EXAMPLE_PRODUCT`). A cross-check must pick one of those definitions or
it will fail the store on day one.

This ADR originates from ticket
`EPIC-TruthfulProjectRecord/35_TICKET-20260909-UXP-700d-3.md`.

## Decision

### 1. The marker MUST be one optional top-level string key named `example_product`

Every example artifact and every example acceptance criterion MUST carry exactly one
top-level key named `example_product`, whose value is the **product-root slug** of the
example product it belongs to:

```json
"example_product": "fern-and-fig"
```

```yaml
example_product: fern-and-fig
```

The key's **presence** states that the content is an example; its **value** states which
product. One key carries both facts, so they cannot be written or removed separately.

The name `example_product` MUST be used verbatim by every producer, checker, and consumer.
It MUST NOT be spelled `product`, `source`, `realization`, `example`, `is_example`, or
`mock`, because each of those is already taken by a field with a different meaning (see
Context) and a reader who meets one word in two senses will conflate them.

### 2. The value MUST be the product-root slug, never a display name

The value MUST be a string matching `^[a-z0-9-]+$` and MUST equal the first
`/`-delimited segment of the ids of that product's artifacts (the same value
`product_ownership.product_of_artifact_id` returns). It MUST NOT be a display name such
as `"Fern & Fig"`.

The value MUST NOT equal the project's own product root
(`product_ownership.PROJECT_PRODUCT`). The schema MUST NOT hard-code the project's root
name (the package installs into other projects); the checker enforces this rule (§6c).

### 3. The project's own record MUST carry no marker — absence is the only representation

An artifact or criterion of the project's own record MUST NOT carry the `example_product`
key at all. `"example_product": null`, `""`, `false`, or the project's own root slug are
all prohibited: a present-but-empty key reads as a live marker to the presence test §8
requires of consumers.

### 4. The key MUST be registered on every artifact kind and documented for ACs

- `docs/product-truth/schemas/flow.schema.json`,
  `docs/product-truth/schemas/mockup.schema.json`, and
  `docs/product-truth/schemas/mock-data.schema.json` MUST each register
  `example_product` as an optional top-level property with the §2 pattern. It MUST NOT
  be added to any schema's `required` list — project artifacts must be able to omit it.
- `docs/reference/ac-schema.md` MUST document `example_product` as an optional AC field
  in its field table, with the §1–§3 semantics.

Registering the key on the flow schema alone is not sufficient: the AC's
"any example artifact" covers journeys, screens, and datasets alike, and a mockup or
catalog carrying the key would be rejected by its own `additionalProperties: false`
schema.

### 5. Every existing example item MUST be marked in the same change, and the AC `product` field MUST be migrated

Delivered by `UXP-700d-3-i` — registration (§4) and backfill (this section) land together,
with no cross-check yet; `UXP-700d-3-ii` (§6-§7) is ordered strictly after, once nothing is
unmarked. Landing the checker first would report every existing example artifact and
criterion as undeclared and refuse its own commit — see that AC's own notes.

In the change that registers the key:

- every `*.flow.json`, `*.mockup.json`, and `*.mock.json` under a `fern-and-fig` product
  root MUST gain `"example_product": "fern-and-fig"` (today: 3 flows, 10 mockups,
  1 dataset);
- every AC YAML carrying `product: fern-and-fig` (today: 18 files) MUST have that line
  replaced by `example_product: fern-and-fig`, and
  `scripts/ac_store/scan_ac_store._is_example_content` MUST read `example_product`
  instead of `product`. The AC-level `product` key MUST NOT survive as a second spelling
  of the same fact.

The flow-level `product` display-name field, and `source` / `realization` on every kind,
are **unchanged** by this decision. They MUST NOT be used to decide whether content is an
example.

The marker is an authored field, not derived data: it is written once by hand (or by the
authoring agent that creates example content) and is not regenerated by
`generate_product_truth.py`. Unlike ADR-043's `behind` mark, no checker writes it.

### 6. The checker (`UXP-700d-3-ii`, landing after §5) MUST cross-check every declaration against the product root and report disagreements naming both values

`docs/product-truth/scripts/validate_product_truth.py` MUST run an `example_product`
check over every loaded flow, mockup, and mock-data artifact, and over every AC record it
already loads via `load_ac_records`. Each finding MUST be appended to `errors` with the
prefix `[example]` and MUST name **both** the declared value (or `absent`) and the product
root it was compared against. The check reports through the existing error channel and
the outcome vocabulary of
[ADR-042](ADR-042-product-truth-checker-outcome-vocabulary.md); it MUST NOT introduce a new
outcome value.

**The product root compared against:**

- For a product-truth artifact: `product_ownership.product_of_artifact_id(artifact["id"])`.
- For an AC: the product root of every `doc_links` entry whose `relationship` is
  `implemented-by-step` and whose `path` lies under
  `docs/product-truth/{flows,mockups,mock-data}/<root>/`. Links with any other
  relationship MUST NOT be consulted, because project ACs legitimately cite example
  artifacts as context.

**Example roots.** A root is an example product root iff it equals
`product_ownership.EXAMPLE_PRODUCT`. The check MUST NOT use
`is_example_artifact_id` (root ≠ project) for this purpose, because that classifies the
project's own `guardrails/` dataset as example content.

**Findings (each is reported):**

- **(a) mismatch** — `example_product` is present and differs from the compared root.
  Includes an example declaration on an artifact under the project's own root. For an AC
  with several `implemented-by-step` roots, each differing root is a separate finding.
- **(b) undeclared** — the compared root is an example product root and `example_product`
  is absent.
- **(c) project-declared** — `example_product` equals `PROJECT_PRODUCT` (§2), regardless
  of root.

An AC with **no** `implemented-by-step` link into the product-truth store has no root to
compare against: only (c) applies to it, and the absence of a root MUST NOT itself be
reported.

### 7. The ownership predicate stays the authority; the check MUST reuse it, not re-derive it

`product_ownership.py` remains the single authority for which product an artifact belongs
to (`UXP-700d-1`). The declaration never decides ownership: `own_record_artifacts`,
`own_record_flows`, and every other ownership function MUST NOT read `example_product`.
The §6 check MUST import `product_of_artifact_id`, `PROJECT_PRODUCT`, and
`EXAMPLE_PRODUCT` from `product_ownership.py`; it MUST NOT re-declare the root constants
or re-split ids. The pure verdict helper (declared value + compared root → findings) MUST
live in `product_ownership.py` beside the predicate it cross-checks, and
`validate_product_truth.py` MUST only load records and call it, so the 716-line checker
does not grow a second copy of the rule.

### 8. Consumers MUST read the key, and MUST NOT infer example-ness from anything else

Every reading surface — starting with the Atlas labelling delivered to `frontend-coder`
under `UXP-700d-3`'s `delivers_to` contract — MUST decide that an item is an example by
testing for the presence of `example_product` on the loaded record, and MUST display the
value as the product it belongs to. Consumers MUST NOT infer example-ness from the file's
directory, from the id prefix, from `source`, from `realization`, or from a registry of
example products, because the AC's point is that a reader holding only the record is
enough.

## Consequences

### Positive

- An agent or person handed a single Fern & Fig flow, screen, dataset, or criterion — out
  of its directory, pasted into a prompt, attached to a review — can tell it is example
  content and which product it belongs to, which is the whole of `UXP-700d-3`.
- One spelling across four artifact kinds means the producer (`python-coder`) and the
  later consumer (`frontend-coder`) cannot disagree on the key, and the Atlas needs one
  presence test instead of a per-kind rule.
- The §6 cross-check turns the marker from a free-standing claim into a verified mirror of
  the product root: moving a file between roots, copying an example into the project's
  record, or forgetting to mark a new example artifact all fail the checker with both
  values named, so the declaration cannot silently drift from ownership.
- Migrating the AC `product` field (§5) removes an undocumented field whose name collided
  with the flow display-name field, and gives `ac-schema.md` a documented answer to "how
  is an example criterion marked".
- `source`, `realization`, and the flow `product` display name keep their existing
  meanings, so no existing reader of those fields changes behaviour.

### Negative

- The change set is far wider than the ticket's `files_touched`
  (`flow.schema.json`, `ac-schema.md`): it also touches two more schemas, 14 product-truth
  artifacts, 18 AC YAML files, `scan_ac_store.py`, `product_ownership.py`, and
  `validate_product_truth.py`. The ticket's scope declaration is understated and must be
  corrected before implementation, or the work will land half-marked and fail its own
  check (§6b).
- The same fact now exists twice for product-truth artifacts (directory root and
  declaration). The cross-check contains the drift but does not eliminate the duplication:
  every new example artifact must be marked by hand, and forgetting to is a commit-time
  failure rather than a non-event.
- An example AC with no `implemented-by-step` link into the product-truth store cannot be
  cross-checked (§6): if it omits the marker, nothing detects it. Today all 18 example ACs
  have such a link; a future example AC authored without one escapes the check.
- The check depends on a single `EXAMPLE_PRODUCT` constant. Adding a second example
  product requires widening that constant to a set, and the existing disagreement between
  `is_example_artifact_id` and `own_record_flows` over non-project, non-example roots such
  as `guardrails/` is worked around here, not resolved.
- Rendered mockup `.html` files carry no marker; only their `.mockup.json` records do. A
  reader handed a bare `.html` file still has only its location to go on.

### Operational

- `unit_tests/product_truth/test_uxp_700d_3_i.py` (`real_artifact`, `boundary`) and
  `unit_tests/product_truth/test_uxp_700d_3_ii.py` (`failure`, `reachability`) together pin
  this contract, split along the §5/§6 boundary: `real_artifact` reads a checked-in Fern &
  Fig file's own content (no index, no loader) and finds `example_product: fern-and-fig`;
  `boundary` asserts the key is **absent** from a project-owned artifact read the same way;
  `failure` asserts a mismatch names both the declared value and the root; `reachability`
  drives `validate_product_truth.py`'s `main()` as a subprocess.
- `check-product-truth-validate` is not modified; once `UXP-700d-3-ii` lands it fails
  commits that add an unmarked example artifact or a mismatched declaration, through its
  existing error path.
- `scan_ac_store.py`'s `set_aside_count`, over the real store with its default filters
  (leaf, `work_status: todo`, active, `readiness: approved`), MUST be unchanged by the §5
  rename. Measured 2026-09-17: 3 — not the 18 raw AC files carrying the marker, since most
  are not yet `readiness: approved`. A change in the reported count is evidence §5 missed
  a file.
- Authoring agents that create example content (`flow-author`, `mockup-author`,
  `mock-data-author`, and `business-analyst` for example criteria) must be taught to write
  the key; until they are, generated example content fails the §6b check on first commit.

## Alternatives

- **Reuse the existing `source: mock` field as the marker.** Rejected. `source` means
  "renders mock/demo data vs a real system surface", and ADR-022's real app in mock mode
  produces project-owned screens that are legitimately `mock`, so `mock` cannot mean
  "example" without mislabelling them. It also names no product, is absent from the
  mock-data schema and from ACs entirely, and is `required`, so it cannot express
  "absent on the project's own record" (AC clause 3).

- **Reuse `realization: mock`.** Rejected. `realization` answers "does this exist in the
  repo today", is optional with absent meaning `built`, and is already omitted by the
  Fern & Fig catalog. It names no product and conflates "not built" with "not ours".

- **Reuse the flow's existing `product` field (and the ACs' `product` field) as the one
  spelling.** Rejected. On flows `product` is a display name present on every flow,
  including all 11 project flows (`"Leafcutter"`), so presence cannot mean "example" and
  AC clause 3 fails for every project flow. Repurposing it would require stripping it from
  the project's own record and changing its value format from display name to slug in one
  step, silently changing the meaning of a field existing readers already display.

- **A boolean `example: true` plus a separate `product` slug.** Rejected. Two keys must be
  kept in sync by convention: `additionalProperties: false` cannot express "if `example`
  is present then `product` must be", so a partial write leaves an example that names no
  product, or a product slug with no example flag. One key carrying both facts is atomic
  (the same argument ADR-043 made for nesting `behind`).

- **A nested object, `"example": {"product": "fern-and-fig"}`.** Rejected. It is equally
  atomic but adds a level with a single member and no foreseeable second one; every
  consumer and the AC YAML gain nesting for no additional information. If a second member
  is ever needed, amending this ADR to migrate is cheaper than carrying the nesting now.

- **Infer example-ness from the directory / id prefix, with no in-content marker.**
  Rejected. That is `UXP-700d-1`'s ownership rule and it already exists; `UXP-700d-3`
  exists precisely because it fails for a reader holding only the content ("held in the
  artifact itself rather than inferred from its location"). ACs have no product-root
  directory at all, so inference cannot work for them.

- **A registry of example products or example artifact ids (e.g. a sidecar list).**
  Rejected. The `delivers_to` contract names this directly ("without consulting a
  registry"), a reader holding one file cannot consult it, and a registry drifts from the
  files it lists on every rename or copy.

- **Declare without cross-checking.** Rejected. A declaration nothing verifies is a second
  hand-maintained summary, which is the drift surface `UXP-700c` and `UXP-514-6` exist to
  close, and AC clause 4 requires the disagreement be reported.

- **Let the declaration decide ownership instead of the root.** Rejected. It contradicts
  `UXP-700d-1` clause 3 ("decided by the product root … rather than by anything in its
  content, so an artifact … cannot be moved between them by an edit"). The root stays the
  authority; the declaration is checked against it.

- **Cross-check ACs against the product root of any `doc_links` path into the
  product-truth store.** Rejected. Project-owned ACs such as `UXP-515` and `UXP-614` link
  Fern & Fig mockups as evidence or context; every one of them would be reported
  undeclared. Only `implemented-by-step` expresses "this criterion describes that
  artifact".

- **Treat every root other than the project's as an example root (`is_example_artifact_id`).**
  Rejected. It reports the project's own `guardrails/frontend-ac-declarations` dataset as
  undeclared example content the day the check ships, forcing either a false marker on
  project content or an exemption list.

## References

- Originating ticket: `EPIC-TruthfulProjectRecord/35_TICKET-20260909-UXP-700d-3.md`
  (AC `UXP-700d-3`).
- Ownership authority this marker is cross-checked against:
  `EPIC-TruthfulProjectRecord/29_TICKET-20260909-UXP-700d-1.md` (AC `UXP-700d-1`) and
  `docs/product-truth/scripts/product_ownership.py`.
- Existing AC-level example classification migrated by §5:
  [`UXP-700d-2`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700d-2.yaml)
  and `scripts/ac_store/scan_ac_store.py` `_is_example_content`.
- [ADR-022 — Mockups Are the Real App in Mock Mode](ADR-022-mockups-are-the-real-app-in-mock-mode.md)
  — why example content stays in place and why `source: mock` cannot mean "example".
- [ADR-023 — Product-Truth Flow-First Upstream Layer](ADR-023-product-truth-flow-first-upstream-layer.md)
  — the store's authority.
- [ADR-025 — First-Class Flow Decisions](ADR-025-first-class-flow-decisions.md)
  — `flow.schema.json`'s `additionalProperties: false` posture.
- [ADR-042 — Product-Truth Checker Outcome Vocabulary](ADR-042-product-truth-checker-outcome-vocabulary.md)
  — the outcome channel §6 reports through without extending.
- [ADR-043 — Journey Record Carries Its Own Behind Mark](ADR-043-journey-record-carries-its-own-behind-mark.md)
  — the precedent for a presence-is-the-mark key fixed before its cross-component consumer
  exists.
- Pinned by `unit_tests/product_truth/test_uxp_700d_3_i.py` (§5) and `unit_tests/product_truth/test_uxp_700d_3_ii.py` (§6, not yet authored).
