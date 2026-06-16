---
title: "ADR-007: AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model"
description: "Defines the AC YAML schema, hierarchical ID format with parent derivation algorithm, status lifecycle, and stdlib-only commit-time enforcement model for the leafcutter AC Traceability Store."
type: "adr"
status: "accepted"
created: "2026-06-04"
last_updated: "2026-06-16"
components:
  - build_pipeline
---

# ADR-007: AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model

## Status

Accepted (2026-06-04)

## Context

Acceptance criteria (ACs) in the leafcutter-ai project have historically lived
as Gherkin blocks inside ticket bodies. This placement has two drawbacks:

1. **Not machine-readable in isolation.** A CI tool cannot extract, validate,
   or cross-reference ACs without parsing arbitrary Markdown.
2. **Not traceable bidirectionally.** There is no machine-enforced link between
   an AC and the test(s) that verify it, or the implementation artifact(s) that
   realise it.

The AC Traceability Store epic (EPIC-ACTraceabilityStore) addresses both
drawbacks by persisting ACs as standalone YAML files under
`docs/acceptance-criteria/`. A stable, versioned JSON Schema contract is
required before any AC YAML files are written to prevent schema churn later.

Four design questions needed resolution before coding:

1. What fields are required vs optional in each AC YAML file?
2. How are AC IDs assigned, formatted, and made globally unique across components?
3. What is the status lifecycle for an AC (active → deprecated / superseded)?
4. How is schema compliance enforced at commit time without adding a heavy
   external dependency?

## Decision

### YAML Schema (JSON Schema draft-07)

The canonical schema is stored at `config/ac_store_schema.json` and defines the
following fields:

**Required fields:**

| Field | Type | Description |
|---|---|---|
| `id` | string | AC identifier matching regex `^[A-Z]{2,6}-[0-9]{3}$` |
| `title` | string | One-line human description of the criterion |
| `component` | string | Component name (must match a key in `docs/components.json`) |
| `status` | enum | `active`, `deprecated`, or `superseded_by` |
| `created_by` | string | Path to the ticket that first introduced this AC |
| `criteria` | string | Multi-line Gherkin scenario body |

**Optional fields:**

| Field | Type | Description |
|---|---|---|
| `superseded_by` | string or null | AC ID of the replacement criterion |
| `amended_by` | array of strings | Ticket paths that subsequently amended this AC |
| `covered_by` | array of strings | Test file paths (and optionally `::test_func`) that verify this AC |
| `implemented_by` | array of strings | Source file paths (and optionally `#anchor`) that implement this AC |

### ID Format

`<COMPONENT_PREFIX>-<NNN>` where:

- `COMPONENT_PREFIX` is 2–6 **uppercase** letters derived from the component
  abbreviation (e.g. `FIN` for `finalize`, `SUP` for `supervisor`, `BLD` for
  `build_pipeline`). The abbreviation must be documented in
  `docs/components.json` alongside the full component name.
- `NNN` is a **zero-padded three-digit** sequential integer within the
  component's namespace (e.g. `001`, `042`, `100`).
- IDs are **assigned at AC creation time** by the business-analyst agent.
  Once assigned, they never change — not on rename, deprecation, or
  supersession. This provides a stable cross-reference anchor for
  `covered_by` and `implemented_by` arrays.
- Root regex: `^[A-Z]{2,6}-[0-9]{3}$`.

### Hierarchical ID Extension and Parent Derivation

Root-level IDs (`PREFIX-NNN`) are extended to form a hierarchy. Each level
appends a new segment. The segments and their derivation rules are:

| Level | Format | Example | Parent |
|---|---|---|---|
| L0 (root) | `PREFIX-NNN` | `ACS-100` | (none) |
| L1 (alpha suffix) | `PREFIX-NNNx` | `ACS-100a` | `ACS-100` |
| L2 (hyphen-numeric) | `PREFIX-NNNx-N` | `ACS-100a-1` | `ACS-100a` |
| L3+ (hyphen-ext) | `PREFIX-NNNx-N-y...` | `ACS-100a-1-i` | `ACS-100a-1` |

**Parent ID derivation algorithm (ACS-100i-1):**

The parent ID is derived from a child ID by stripping the last segment:

1. If the ID matches `^[A-Z]{2,6}-[0-9]{3}$`: no parent (`None`).
2. If the ID matches `^[A-Z]{2,6}-[0-9]{3}[a-z]+$` (alpha suffix directly on
   numeric part, no hyphen before the letters): strip trailing letters.
   Example: `ACS-100a` → `ACS-100`.
3. Otherwise: strip the last hyphen-delimited segment.
   Examples: `ACS-300h-1` → `ACS-300h`; `ACS-300h-2-i` → `ACS-300h-2`.

The canonical implementation of this algorithm is `derive_parent_id()` in
`scripts/ac_store/scan_ac_store.py`. All parent-child enforcement features
(pre-commit hooks, store-wide scans, agent auto-updates) MUST call this
function rather than re-implementing the parsing logic.

### Status Lifecycle

```
active ──→ deprecated          (AC permanently retired; no replacement)
active ──→ superseded_by       (AC replaced by a newer AC; superseded_by field set)
```

- `deprecated` ACs remain in the store but are excluded from coverage reports.
- `superseded_by` ACs remain and link to their successor. The successor carries
  `amended_by` tracking back to the ticket that performed the supersession.
- Re-activating a deprecated AC requires a ticket edit (setting `status: active`
  again); the pre-commit validator does not block re-activation.

### Bidirectional Enforcement Model

A standalone Python stdlib script `templates/commit-guardian/check_ac_schema.py`
is installed as a commit-guardian hook. It runs on every commit that touches
`docs/acceptance-criteria/**/*.yaml`:

1. Loads each `.yaml` file in the glob pattern using `PyYAML` (fallback: manual
   field checks if `PyYAML` is absent).
2. Validates required fields are present.
3. Validates `status` is one of the three allowed enum values.
4. Validates `id` matches the regex `^[A-Z]{2,6}-[0-9]{3}$`.
5. Exits 0 if all files pass; exits 1 with per-file error messages naming the
   file path and the failing field.

The hook is registered in `templates/commit-guardian/commit_guardian.json` with
`pass_filenames: false` and a file-pattern filter to
`docs/acceptance-criteria/**/*.yaml`.

**Why stdlib only:** External validator libraries (`jsonschema`) are not
guaranteed to be installed in the commit hook environment of every adopter
project. A stdlib-only fallback ensures the hook runs without a separate
`pip install` step. If `jsonschema` is available it is used for full draft-07
validation; if absent the script performs equivalent manual checks.

### Migration Strategy for Existing Tests

No existing AC YAML files exist at the time this ADR is written — the store
is being created from scratch. However, for any future migration of Gherkin
blocks from ticket bodies to AC YAML files:

- Phase 1 (Grace Period): validation is **warning-only** (exit 0 with a
  `WARNING:` prefix line) for files in `docs/acceptance-criteria/draft/`.
- Phase 2 (Enforcement): once a file is moved out of `draft/`, full validation
  with exit 1 on failure is applied.
- No back-migration of existing tickets is required — ACs in ticket bodies
  remain valid; the AC store supplements rather than replaces them.

### Schema Extension: Pattern AC Fields (added 2026-06-11)

Three optional fields were added to `config/ac_store_schema.json` to support
shared-behavior reuse across ACs (AC ACS-500a-1):

| Field | Type | Purpose |
|---|---|---|
| `pattern_slots` | array of strings or null | Declares named curly-brace placeholders on a pattern AC (e.g. `["{columns}", "{default_sort}"]`). Absent or null on non-pattern ACs. |
| `implements_pattern` | string or null | References the AC ID of the pattern this AC instantiates. Set on consuming ACs only. |
| `pattern_bindings` | object (string → string) or null | Maps each slot name (without curly braces) to its concrete value. Required when `implements_pattern` is set. |

These fields are all optional and default to null. Existing ACs without pattern
semantics are unaffected — the schema extension is fully additive. The
`additionalProperties: false` constraint in the schema was already allowing for
named optional properties; the three new properties are registered there.

The single-source-of-truth invariant — no two ACs in the store may define an
equivalent behavior for the same shared pattern — is an authoring discipline
enforced by review rather than by the schema validator. A future hook
(`check_ac_pattern_uniqueness.py`) may enforce this mechanically.

**Pattern bindings completeness enforcement (added 2026-06-16, AC ACS-500a-3-i):**

`check_ac_schema.py` now enforces that every consuming AC (one with
`implements_pattern` set) supplies a `pattern_bindings` entry for every slot
declared in the referenced pattern's `pattern_slots`. The check runs as part
of the existing `check-ac-schema` pre-commit hook — no new hook is required.

When a slot is missing, the hook exits 1 with the canonical error:

```
<consuming_ac_file>: pattern_bindings missing required key '<slot>' for pattern <pattern_id>
```

Both the consuming AC file path and the missing key name are included in the
error message so the author can locate and fix the issue immediately.

### Pattern AC Placement Convention (added 2026-06-11, AC ACS-500a-2)

Pattern ACs follow the **same file placement convention** as every other AC in
the store. No separate "pattern catalog" directory or registry file is created.

**Decision:** A pattern AC is stored at:

```
docs/acceptance-criteria/<component>/<feature-folder>/<id>.yaml
```

This is identical to the path for any non-pattern AC. The presence of
`pattern_slots` in the YAML body is the sole indicator that an AC is a pattern.

**Rationale:**

1. **No second root.** Introducing a `docs/acceptance-criteria/patterns/`
   directory would bifurcate the store into two roots, requiring every
   AC-scanning tool and hook to support two glob patterns. Keeping patterns
   within the standard hierarchy means `docs/acceptance-criteria/**/*.yaml`
   continues to be the complete scan expression.

2. **Component coherence.** A pattern AC defines behavior for a specific
   component. Placing it inside that component's folder (with the same
   `component` field) makes ownership and co-location obvious. Consumers and
   patterns are reviewable together in the same directory tree.

3. **Parent traceability unchanged.** A pattern AC appears in its parent AC's
   `covered_by` list exactly as any other child AC would. The
   `check_ac_parent_covered_by.py` hook does not need a special code path for
   patterns — they are just ACs.

4. **ID format unchanged.** Pattern AC IDs follow the same
   `PREFIX-NNNx-N` format as other L2 ACs. No special namespace, prefix, or
   reserved range is assigned to patterns.

## Consequences

**Positive:**
- Machine-readable, individually-addressable ACs with stable IDs.
- Bidirectional traceability: `covered_by` and `implemented_by` arrays link ACs
  to their tests and implementations.
- Lightweight enforcement via a stdlib script — no new runtime dependency.
- Status lifecycle prevents stale ACs from polluting coverage metrics.

**Negative:**
- AC authors must maintain `covered_by` and `implemented_by` manually until an
  automated linker is written (planned as a later EPIC-ACTraceabilityStore
  ticket).
- The `COMPONENT_PREFIX` abbreviation convention is informal until a canonical
  mapping is codified in `docs/components.json`.
- `PyYAML` is a soft dependency for the validator; without it the validator
  performs simpler checks that could miss malformed multi-line `criteria` blocks.

## Alternatives

**Alternative A: Gherkin-in-ticket only (status quo)**
Rejected. Does not enable machine cross-referencing or bidirectional traceability.
Extracting ACs from arbitrary Markdown is fragile.

**Alternative B: Database table instead of YAML files**
Rejected for this phase. Introduces a database dependency for what is
fundamentally a documentation artifact. YAML files are diffable, reviewable
in PRs, and version-controlled alongside the code they describe.

**Alternative C: JSON files instead of YAML**
Rejected. YAML supports multi-line `criteria` blocks with natural Gherkin
indentation without escaping. JSON requires escaping newlines in strings,
making Gherkin criteria illegible.

**Alternative D: Use `jsonschema` as a hard dependency**
Rejected. Commit hooks must be zero-dependency-at-runtime on fresh project
clones. A soft dependency with a stdlib fallback is the safer default.
