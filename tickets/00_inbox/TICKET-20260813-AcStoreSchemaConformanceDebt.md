---
title: "AC store schema conformance debt: test_spec framework vocabulary + missing components (39 files)"
status: todo
components:
  - ac_store
  - ux_prototyping
created: 2026-08-13
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
complexity: medium
change_target: schema
risk_surface: contract_boundary
files_touched:
  - config/ac_store_schema.json
  - unit_tests/ac_store/test_acs_200e_validator_schema_parity.py
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-607.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-607-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-607-2.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-608.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-608-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-608-2.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-608-3.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-609.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-609-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-609-2.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-610.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-610-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-610-2.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-602.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-603.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-603a.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-604.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-604a.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-605.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-605a.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-597.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-598.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-599.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-599a.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-600.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-601.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-600a.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-606.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1400-web-app-ci-gate/BP-1400c-1.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1400-web-app-ci-gate/BP-1400c-1-i.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-300-product-truth-store/UXP-300.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-400-define-a-feature/UXP-491.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-410-flow-render/UXP-492.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-420-architecture/UXP-493.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-500-product-truth-generation/UXP-515.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-500-product-truth-generation/UXP-516.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-500-product-truth-generation/UXP-590.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-530-request-classifier/UXP-531.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-530-request-classifier/UXP-592.yaml
agents:
  architect-review: needed
  adr-author: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# AC store schema conformance debt: test_spec framework vocabulary + missing components

## Context

`check-ac-schema` (pre-commit) and `scripts/ac_store/validate_ac_schema.py` both validate
AC YAML against `config/ac_store_schema.json`. A measured sweep of the whole store
(**2026-08-13**, `index.yaml` excluded, jsonschema Draft7) found:

| | files | class |
|---|---|---|
| **2824** | total AC YAML | — |
| **290** | failing schema validation (~10%) | — |
| 251 | `it_requirements` not a structured object / absent | **Class A** — out of scope, see follow-up |
| 28 | `test_spec[].framework` / `.type` outside enum | **Class B** — in scope |
| 9 | `components` required property missing | **Class C** — in scope |
| 2 | `test_rationale` additional property not allowed | **Class D** — in scope |

> **Re-measure before starting.** These counts are a point-in-time sweep taken on
> 2026-08-13 and the store grows daily. The parent investigation that triggered this
> ticket quoted 277/2784 from a slightly earlier sweep; the numbers above are the same
> defects a few files later. Re-run the sweep as step 1 and treat any delta as normal.

The 13 `UXP-550-atlas-mock-mode` files are the subset that **blocks commits today**,
because they sit in the diff of active Atlas work. That block was deferred with a
documented `[HOOK-SKIP: check-ac-schema]` when merging PR #424
(commit `7c8c505e3`, 2026-08-13) — fixing another component's ACs was correctly ruled
out of scope for a merge commit. This ticket is the follow-up that skip promised.

## Investigation findings

### 1. What shape does the schema actually want?

The list-of-objects shape is **correct** — the schema wants exactly that. The failure is
**not** structural. From `config/ac_store_schema.json` (`test_spec`, lines 378-433):

```json
"test_spec": {
    "oneOf": [
        {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "target_dir"],
                "additionalProperties": false,
                "properties": {
                    "name":       { "type": "string", "minLength": 1 },
                    "target_dir": { "type": "string", "minLength": 1 },
                    "framework":  { "type": "string", "enum": ["unittest", "pytest"] },
                    "type":       { "type": "string",
                                    "enum": ["unit", "integration", "e2e", "behavioral"] },
                    "description":{ "type": "string", "minLength": 1 },
                    "covers":     { "type": "array", "items": {"type": "string"} },
                    "requires_db":{ "type": "boolean" }
                }
            }
        },
        { "type": "null" }
    ]
}
```

A **conforming** example — `docs/acceptance-criteria/ac-driven-dev/ACD-1200-goal-to-epic/ACD-1200a-12.yaml`:

```yaml
test_spec:
  - name: test_implemented_by_path_is_repo_relative
    target_dir: unit_tests/ac_store/
    framework: unittest
    type: unit
    description: "After generation, assert the implemented_by entry does not start with '/' ..."
```

The failing example — `docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-607.yaml`:

```yaml
test_spec:
  - name: badge_reflects_resolved_mock_decision
    target_dir: leafcutter-web/components/shell/__tests__/
    framework: vitest          # <-- NOT in enum ["unittest", "pytest"]
    type: unit
    description: "When the seam resolves the decision to 'mock', ..."
```

The two documents are structurally identical. The **only** difference is the value of
`framework`. Because `framework` lives inside a `oneOf`, jsonschema reports the whole
array as "not valid under any of the given schemas", which reads like a shape mismatch
and is why the debt was originally described as "shape drift". It is a **vocabulary**
mismatch, one word wide.

Exact offending values across all 28 Class-B files:

- `framework: vitest` — 40 stanzas
- `framework: playwright` — 2 stanzas
- `type: component` — 12 stanzas (enum is `unit|integration|e2e|behavioral`)

Store-wide framework usage for contrast: `unittest` 550, `pytest` 269, `vitest` 40,
`playwright` 2.

### 2. Is the schema right, or is the data right? — the data is right

`git log -S` on `config/ac_store_schema.json` puts **both** the `framework` enum and the
package-surface `if/then` block in the same commit:

```
9e59b1fe7  2026-07-09  feat(prompt-assembly): ticket 03 — Implementation Notes emission
                       + read-ticket dispatch (#242)
```

Splitting the failing files by their `created:` date against that boundary is decisive:

| class | authored BEFORE 2026-07-09 | authored AFTER |
|---|---|---|
| A — `it_requirements` (251) | **251** | 0 |
| B — `test_spec` enum (28) | 0 | **28** |
| C — `components` (9) | 0 | **9** |
| D — `test_rationale` (2) | 0 | **2** |

Two different stories, cleanly separated:

- **Class A is classic tighten-after-authoring drift.** Every one of the 251 files
  predates the rule that now rejects it. The schema tightened underneath valid data.
- **Class B is the opposite** — every file postdates the schema. But the schema is still
  the thing that is wrong: it was written on 2026-07-09 when this repo was Python-only,
  so it hardcoded a Python-only test vocabulary. `leafcutter-web/` (Next.js, vitest,
  playwright) arrived later. An AC that says a `.tsx` component test is a `vitest`
  `component` test is stating the truth; the enum simply has no word for it. Every
  Class-B file lives under `ux-prototyping/` or `build_pipeline/BP-1400-web-app-ci-gate/`
  — i.e. exactly the frontend-era ACs.

**Recommendation: widen the schema, do not degrade the data.** Add `vitest`,
`playwright` (and, if the frontend stack uses it, `jest`) to `framework`; add `component`
to `type`. Writing `framework: unittest` on a `.tsx` test would be a lie, and deleting
the key (it is optional — only `name` and `target_dir` are required) would silently make
`test-writer` default to the Python convention and author the wrong kind of test.

> **AC GATE — read before building the Class-B half.**
> Widening the enum changes what the validator accepts. That is a **behaviour change to a
> validation contract**, not data remediation, so per CLAUDE.md "New Work Goes Through ACs"
> it must be specified as an AC via `/plan-feature` **before** it is implemented. No
> existing AC governs the `test_spec.framework` vocabulary (searched: no AC in the store
> references it; `ACS-500*`/`ACS-800*` cover pattern and identity fields, `INF-1000`
> covers schema-vs-*fixture* coherence, not store data). Author that AC first.
> Classes C and D below need no AC — they are pure data conformance against rules that
> already exist and were already in force when the files were written.

### 3. Scope recommendation — 39 files (B+C+D), not 13, and not 290

The 13/277 split the debt was originally framed with is **not the natural seam**. Two
corrections:

- **Fixing only the 13 UXP-550 files does not clear the class.** 15 more files with the
  identical `framework: vitest` defect sit in `UXP-520`, `UXP-596`, and
  `BP-1400-web-app-ci-gate`. They are not blocking *today* only because they are not in
  today's diff — the next Atlas or web-CI commit hits exactly the same wall and needs
  exactly the same one-word fix. Splitting a homogeneous 28-file mechanical class into
  13-now/15-later buys nothing and guarantees a repeat interruption.
- **Class A (251 files) genuinely is a separate ticket** — different root cause
  (pre-tightening drift, not vocabulary), different component (build-orchestration /
  build_pipeline / guardrail-engine, not ux-prototyping), and non-mechanical (see §4).

So: **this ticket = Classes B + C + D = 39 files**, all post-tightening, all in the
frontend-era corner of the store, all mechanical once the vocabulary decision is made.
Class A is deferred to a follow-up (see Out of Scope).

### 4. Is a mechanical fix possible?

**Class B — yes, and the cheapest fix is one edit, not a migration.** If the enum is
widened (pending the AC gate above), all 28 files become valid with **zero** file edits.
If the decision instead goes the data-side way, a migration script rewriting
`framework`/`type` across 28 files is trivially mechanical.

**Class C — yes, mechanical.** 9 files are missing the `components` list. The value is
recoverable without judgement: each file already carries the scalar
`component: ux-prototyping`, and the two-axis mapping (kebab `component` →
`components.json` underscore id) is deterministic — `ux-prototyping` → `ux_prototyping`.

**Class D — yes, mechanical.** 2 files (`UXP-600a`, `UXP-606`) carry a `test_rationale`
key the schema forbids via `additionalProperties: false`. Either drop it or fold the text
into `notes:`. Decide once, apply twice.

**Class A — NO, not mechanical.** This is the load-bearing reason it is out of scope. The
`then` branch demands `it_requirements` be an object with five required fields —
`config_schema_fragment`, `reference_file_path`, `n_location_rule`, `required_skills`,
`post_write_commands`. Those are real per-AC technical content (a JSON Schema fragment, a
real resolvable repo path, a location-count rule). They cannot be synthesised from the
existing prose strings, and 49 of the 251 have no `it_requirements` at all. That is 251
IT-PO judgement calls, i.e. an epic, not a script.

## Related work already in the inbox

- `tickets/00_inbox/TICKET-20260710-ITPOv3-StructuredItRequirements.md` — fixes the
  **authoring agent** so it-po-v3 stops emitting list-form `it_requirements` for
  package-surface ACs. That stops Class A growing; it does **not** remediate the 251
  existing files. The Class-A follow-up should depend on it.
- `INF-1000` (`docs/acceptance-criteria/infrastructure/INF-1000-schema-fixture-coherence/`)
  — "Schema changes never silently break test fixtures", still `work_status: todo`. Same
  failure mode one layer over (fixtures rather than store data). Worth pairing: whatever
  gate is built here should be the reason a future enum tightening cannot silently
  invalidate 251 files again.

## Acceptance Criteria

- [ ] AC-1: The sweep is re-run at start-of-work and the ticket body's counts are updated
      to the measured values on that date (expected drift from 290/2824, not a failure).
- [ ] AC-2: An ADR records the `test_spec` vocabulary decision — widen the
      `framework`/`type` enums to admit the JS/TS test stack, or normalise the data —
      with the 2026-07-09 Python-only-era rationale from §2 stated explicitly.
- [ ] AC-3: An AC authored via `/plan-feature` specifies the enum widening **before** any
      edit to `config/ac_store_schema.json` lands. (Skip only if AC-2 decides the
      data-side option, which needs no AC.)
- [ ] AC-4: All 28 Class-B files validate clean against `config/ac_store_schema.json`.
- [ ] AC-5: All 9 Class-C files carry a `components` list whose ids exist in
      `docs/components.json`, consistent with their scalar `component` field.
- [ ] AC-6: Both Class-D files validate clean (`test_rationale` removed or folded into a
      permitted field, with the text preserved).
- [ ] AC-7: A test asserts the **whole** AC store validates clean except for a named,
      explicitly-listed Class-A allowlist — so this class of debt cannot silently regrow,
      and the allowlist shrinking to empty is the Class-A follow-up's done-condition.
- [ ] AC-8: `python3 scripts/ac_store/validate_ac_schema.py` over
      `docs/acceptance-criteria/ux-prototyping/` and
      `docs/acceptance-criteria/build_pipeline/BP-1400-web-app-ci-gate/` exits 0, and a
      commit touching a UXP-550 file no longer needs `[HOOK-SKIP: check-ac-schema]`.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |
| AC-8 | | | |

## Implementation Tasks

- [ ] Re-run the store-wide sweep; update the counts table and the file lists.
- [ ] architect-review + adr-author: settle and record the vocabulary decision (AC-2).
- [ ] If widening: author the AC via `/plan-feature` (AC-3), then edit the two enums in
      `config/ac_store_schema.json`.
- [ ] Fix the 9 Class-C files (`components` list) and the 2 Class-D files
      (`test_rationale`).
- [ ] Add the store-wide conformance test with the named Class-A allowlist (AC-7).
- [ ] Verify: run `validate_ac_schema.py` over the full store and confirm only the
      allowlisted Class-A files fail.
- [ ] Behavioural spot-check per CLAUDE.md: stage a real UXP-550 file and run the
      **deployed** `check-ac-schema` hook (not just the source validator) to prove the
      commit path is unblocked.

## Out of Scope

- **Class A — the 251 `it_requirements` files.** Needs its own epic: per-AC IT-PO
  judgement for five structured fields each, 49 of them from nothing. Should depend on
  `TICKET-20260710-ITPOv3-StructuredItRequirements.md` so the authoring agent is fixed
  before the backfill starts, and should close by emptying the AC-7 allowlist.
- Any change to `docs/acceptance-criteria/ac-store/ACS-200-automated-verification/` or
  `build_pipeline/BP-100-reliable-builds/`.
- Re-litigating the package-surface `if/then` rule itself.

## Risk & Safety

- Touches money? No.
- Touches data? Yes — edits 39 AC YAML files in the store. All edits are additive or
  single-key; no AC criteria text is rewritten and no AC is deleted. Reversible via git.
- Reversibility? Full. The schema edit is a two-line enum widening; the data edits are
  per-file and independently revertable.
- **Contract-boundary risk**: `config/ac_store_schema.json` is read by both
  `check-ac-schema` (pre-commit) and `validate_ac_schema.py`, and ACS-200e requires those
  two verdicts not to drift. Widening the enum is permissive-only — it cannot newly reject
  anything that passes today — but re-run
  `unit_tests/ac_store/test_acs_200e_validator_schema_parity.py` to confirm parity holds.
- **Deployment risk**: the pre-commit hook runs from the **deployed** layout
  (`.leafcutter/`), not the source tree. After editing the schema, run `build.py` and
  re-test the deployed hook — a source-only fix will read as green while the real commit
  path stays blocked (CLAUDE.md, "New Hook / Gate Dependencies Must Be in the Build
  Deploy-Manifest").

## Comments

### 2026-08-17 — re-measure before starting (status: ok)

The ticket's own instruction ("Re-measure before starting") was followed. **The scope has
collapsed from 39 files to 11.** Build the numbers below, not the ones in §3.

**Root cause of the delta: the ticket's own recommendation was already implemented.**
Commit `f8cfdfc47` (PR #435, "Count vitest tests as proof-of-done; harden Atlas mock
mode") widened both enums in `config/ac_store_schema.json` — exactly the "widen the
schema, do not degrade the data" path §2 argued for. Current state:

```
framework: enum ["unittest", "pytest", "vitest"]
type:      enum ["unit", "integration", "e2e", "behavioral", "component"]
```

Sweep re-run 2026-08-17 (same method: `index.yaml` excluded, jsonschema Draft7):

| | 2026-08-13 (ticket) | 2026-08-17 (measured) | note |
|---|---|---|---|
| total AC YAML | 2824 | **2971** | store grew, expected |
| failing validation | 290 | **262** | |
| A — `it_requirements` | 251 | **251** | exact match; still correctly out of scope |
| B — `test_spec` enum | 28 | **2** | 26 fixed by the enum widening |
| C — `components` missing | 9 | **9** | unchanged, still valid |
| D — `test_rationale` | 2 | **0** | already resolved |

The vocabulary census in §1 is still exactly right: `vitest` 40 stanzas, `playwright` 2,
`type: component` 12. What changed is that 52 of those 54 stanzas now validate.

**Remaining Class B — 2 files, one word.** `playwright` was NOT added to the enum:
- `docs/acceptance-criteria/build_pipeline/BP-1400-web-app-ci-gate/BP-1400c-1.yaml`
- `docs/acceptance-criteria/build_pipeline/BP-1400-web-app-ci-gate/BP-1400c-1-i.yaml`

Both are the route-render ACs, failing solely on `framework: playwright` (`type: e2e` is
already valid). §2's reasoning applies unchanged and now has a shipped precedent: add
`playwright` to the `framework` enum rather than mislabel a Playwright test.

**Remaining Class C — the same 9 files listed in `files_touched`.** Unchanged.

**Class D — nothing to do.** Both files now validate.

**Correction to §4's Class-D premise.** `test_rationale` is a **valid top-level
property** in the schema — it is only forbidden *nested inside* `test_spec` items, where
`additionalProperties: false` applies and the allowed keys are `name`, `target_dir`,
`framework`, `type`, `description`, `covers`, `requires_db`. Do not strip top-level
`test_rationale` anywhere; several ACs legitimately carry it (e.g. the BP-100k and
BP-1100b families enriched 2026-08-17).

**Consequences for the ACs as written:**
- **AC-2 / AC-3** (ADR + `/plan-feature` gate before widening) are largely **moot for
  `vitest`/`component`** — that decision was made and shipped in #435. They still apply
  to the `playwright` addition, which is the same class of contract change. Re-scope them
  to `playwright` rather than re-litigating the settled part.
- **AC-4** now means 2 files, not 28.
- **AC-6** is already satisfied — verify and close it, do not hunt for work.
- **AC-1, AC-5, AC-7, AC-8** are unchanged and still the substance of this ticket. AC-7
  (whole-store conformance test with a named Class-A allowlist) is now the highest-value
  item here, since it is the thing that stops this recurring.

Note the store-wide failure count only fell from 290 to 262 while 28 files were fixed —
Class A held exactly steady at 251 across four days, which is the evidence that the
`it_requirements` backlog is inert and genuinely needs its own epic rather than
opportunistic chipping.
