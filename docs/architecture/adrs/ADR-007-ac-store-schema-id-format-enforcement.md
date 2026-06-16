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
| `pattern_bindings` | object (string → string or string[]) or null | Maps each slot name (without curly braces) to its concrete value. Values may be strings or arrays of strings (e.g. a list of column names). Required when `implements_pattern` is set. |

These fields are all optional and default to null. Existing ACs without pattern
semantics are unaffected — the schema extension is fully additive. The
`additionalProperties: false` constraint in the schema was already allowing for
named optional properties; the three new properties are registered there.

The single-source-of-truth invariant — no two ACs in the store may define an
equivalent behavior for the same shared pattern — is enforced by
`check_ac_schema.py` at commit time (AC ACS-500c-3). See the section below for
the duplicate detection algorithm.

**Pattern binding values extended to arrays (added 2026-06-16, AC ACS-500b-1):**

`pattern_bindings` values may now be either plain strings or arrays of strings.
This allows a consuming AC to bind a slot such as `{columns}` to a structured
list rather than a comma-separated string, improving readability and enabling
machine-readable binding validation in future tooling. Example:

```yaml
pattern_bindings:
  entity_type: "invoices"
  columns:
    - "number"
    - "date"
    - "amount"
    - "status"
  default_sort: "date descending"
```

The `additionalProperties` constraint on `pattern_bindings` in
`config/ac_store_schema.json` now accepts `oneOf: [string, array of strings]`
for each binding value. The binding completeness check (every slot declared in
the pattern's `pattern_slots` must appear as a key) is unchanged — only the
allowed value types are broadened. Existing string-valued bindings remain valid.

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

**Deprecated pattern reference enforcement (added 2026-06-16, AC ACS-500a-3-ii):**

`check_ac_schema.py` now enforces that no consuming AC references a pattern AC
that has `status: deprecated` via its `implements_pattern` field. The check runs
as part of the same `check-ac-schema` pre-commit hook — no new hook is required.

When a consuming AC references a deprecated pattern, the hook exits 1 with:

```
<consuming_ac_file>: implements_pattern references deprecated pattern <pattern_id>;
use its successor (see <pattern_id> superseded_by field) or remove the reference
```

The error names the consuming AC file path so the author can locate and update the
reference. The `superseded_by` field on the deprecated pattern AC identifies the
correct replacement; if no successor exists, the `implements_pattern` field must be
removed.

### Pattern Deviation Convention — Separate Files Only (added 2026-06-16, AC ACS-500b-2)

When a consuming page or component needs behavior that differs from a pattern
on one specific axis, that deviation is written as a **separate AC file** in
the same feature folder. Inline overrides — modifying `pattern_bindings` on the
consuming AC, or introducing ad-hoc fields — are not permitted.

**Decision:** A deviation AC is a standalone YAML file that:

1. Has its own `id` (following the normal `PREFIX-NNNx-N` L2 format).
2. Contains a full `criteria` block (Given/When/Then) describing only the
   non-standard behavior.
3. Sets `depends_on` to include the consuming AC that instantiates the pattern
   (establishing the traceability link back to the pattern instantiation context).
4. Does **not** set `implements_pattern` — a deviation AC is not a pattern
   instantiation; it describes an explicit override for one component.
5. The original consuming AC's `pattern_bindings` remain unchanged.

**Rationale:**

1. **Single-responsibility.** Each AC file describes one testable behavior.
   Mixing a pattern instantiation record with a deviation in the same file
   creates an ambiguous contract that is hard to review and test independently.
2. **Stable traceability.** The consuming AC's `pattern_bindings` is a
   snapshot of "which pattern with what slot values." If a deviation modified
   the bindings, the bindings would no longer accurately represent the pattern
   in use — they would partially describe a custom behavior instead.
3. **No new schema fields needed.** A deviation AC uses the existing required
   fields (`id`, `title`, `component`, `status`, `created_by`, `criteria`) and
   the existing `depends_on` pointer. The schema extension is purely a
   convention that authoring agents enforce; the JSON Schema validator requires
   no changes.
4. **Tooling simplicity.** A scanner that identifies all ACs with
   `implements_pattern` gets a clean list of pattern instantiations. Deviation
   ACs (no `implements_pattern`) are simply additional ACs in the feature
   folder — the scanner does not need a special code path to handle them.

This convention is described in detail in `docs/reference/ac-schema.md` under
the subsection "Pattern deviations — separate files, not inline overrides."

### Duplicate Criteria Detection (added 2026-06-16, AC ACS-500c-3)

`check_ac_schema.py` now detects when a new standalone AC's `criteria` text
restates the same behavior as an existing pattern AC by substituting concrete
values for pattern slots. Such ACs must instead use `implements_pattern` +
`pattern_bindings` to preserve the single-source-of-truth invariant.

**Algorithm:**

1. For every AC file being validated that does NOT have `implements_pattern` set:
2. Collect all pattern ACs in the store (those with a non-empty `pattern_slots`
   list, or whose `criteria` text contains at least one `{slot}` placeholder).
   Skip deprecated patterns (no live pattern to reference).
3. For each pattern AC, normalize its criteria: collapse whitespace runs to a
   single space. Build a regex by escaping fixed text between slots and replacing
   each `{slot_name}` with `.+` (one-or-more-character wildcard).
4. Normalize the candidate AC's criteria the same way (whitespace collapse).
5. Apply `re.fullmatch` against the normalized candidate criteria. A full match
   means the candidate criteria is structurally identical to the pattern with
   slots filled in.
6. On a match, emit an error:
   ```
   <file>: criteria is a likely duplicate of pattern <id>; use
   implements_pattern: <id> with pattern_bindings instead of restating
   the behavior inline
   ```
   The commit is blocked (exit 1).

**Design choices:**

- **Whitespace normalization before matching.** Gherkin criteria often have
  varying indentation (leading spaces on continuation lines). Normalizing to a
  single flat string ensures matching works regardless of formatting style.
- **`re.fullmatch` for structural equivalence.** Partial matches (substring
  presence) would produce excessive false positives on criteria that share
  common Gherkin phrases. A full match requires the entire criteria body to
  follow the pattern structure.
- **Greedy `.+` per slot (not `.*`).** Each slot must be filled with at least
  one character. This prevents erroneous matches on boundary-adjacent patterns
  and makes the match semantically accurate (a slot that bound to an empty
  string would not be a valid binding).
- **Fail-open on regex compilation errors.** If a pattern AC's criteria
  produces an invalid regex (e.g., unmatched curly braces in non-slot
  positions), the check is skipped for that pattern rather than blocking
  all commits. The pattern author should fix the malformed criteria.
- **No hook file added.** The check is integrated into the existing
  `check-ac-schema` hook rather than introducing a new
  `check_ac_pattern_uniqueness.py` hook. This keeps the hook surface minimal
  and avoids requiring a separate hook registration entry.

### Pattern Criteria Propagation — Effective Behavior at Read Time (added 2026-06-16, AC ACS-500d-1)

When a pattern AC's `criteria` field is amended, every consuming AC that
references it via `implements_pattern` automatically inherits the updated
behavior. No change to consuming AC files is required, and no migration ticket
is created.

**Decision:** Pattern criteria propagation is a read-time resolution, not a
write-time fan-out.

A consuming AC stores only:
- `implements_pattern: <pattern-id>` — the reference to the pattern.
- `pattern_bindings: {...}` — the concrete values for each slot.

The consuming AC's effective behavior is evaluated by any reader (agent, tool,
or human) at the time the AC is read:

1. Read the consuming AC's own `criteria` (page-specific behavior, if present).
2. Follow `implements_pattern` → read the pattern AC's current `criteria`.
3. Substitute `pattern_bindings` values for each `{slot}` placeholder in the
   pattern criteria.
4. The effective criteria is the union of steps 1 and 3.

Because the reference is resolved at read time, amending the pattern AC's
`criteria` is immediately reflected in all consumers' effective behavior without
any additional writes.

**Rationale:**

1. **Zero-cost propagation.** A write-time fan-out would require the amending
   agent to locate all consumers, update each one, and commit all changes
   atomically. With N consumers this is an O(N) write operation that is error-
   prone and produces noisy diffs. Read-time resolution makes propagation
   O(0) writes and O(1) per read.

2. **Consumer files are immutable records of instantiation.** A consuming AC's
   YAML records "which pattern, with what bindings, for which component." That
   record does not change when the pattern's behavior changes — the record
   accurately describes the consuming AC's intent at all times. Rewriting the
   consumer file on every pattern amendment would conflate amendment history with
   instantiation records.

3. **Consistent with the single-source-of-truth invariant.** The pattern AC is
   the sole owner of the shared behavior definition. Propagating criteria to
   consumer files would create N+1 copies of the definition — exactly the
   redundancy the pattern mechanism was designed to eliminate.

4. **No schema change required.** The `implements_pattern` reference field
   already carries the information needed for read-time resolution. No new field
   (e.g. `criteria_inherited_version`) is introduced.

**Amendment traceability:** When a pattern AC's `criteria` is amended, the
amending ticket path is appended to the pattern AC's `amended_by` list. Consumer
ACs do not receive `amended_by` entries for pattern-inherited changes. An auditor
who wants to know which consumers were affected by a pattern amendment reads the
pattern AC's `amended_by` list and queries `implements_pattern: <pattern-id>`
across the store.

**Detailed specification:** see `docs/reference/ac-schema.md` under
"Effective behavior propagation — amending a pattern AC."

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
