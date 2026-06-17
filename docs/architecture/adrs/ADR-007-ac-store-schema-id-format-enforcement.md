---
title: "ADR-007: AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model"
description: "Defines the AC YAML schema, hierarchical ID format with parent derivation algorithm, status lifecycle, and stdlib-only commit-time enforcement model for the leafcutter AC Traceability Store."
type: "adr"
status: "accepted"
created: "2026-06-04"
last_updated: "2026-06-08"
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
| `implements_pattern` | string or null | ID of the reusable behavior pattern this AC inherits from (e.g. `PTN-001`). When set, the `criteria` field may be a plain-text placeholder rather than a full Gherkin scenario (see below). |
| `pattern_bindings` | object or null | Key-value bindings that instantiate the referenced pattern. Only meaningful when `implements_pattern` is set. |

**Pattern-inherited ACs and the `criteria` field:**

When `implements_pattern` is set, the AC's effective behavior is entirely derived
from the referenced pattern combined with `pattern_bindings`. In this case, the
`criteria` field may contain a plain-text placeholder such as
`"No page-specific behavior — all behavior inherited from pattern."` instead of a
full `Given`/`When`/`Then` scenario. The schema validator accepts any non-empty
string for `criteria` — it does not enforce Gherkin format. This is by design: the
schema's role is structural integrity (field presence and type), not behavioral
completeness (which is owned by the pattern registry). ACs that have no unique
page-specific behavior are therefore valid with an empty-criteria placeholder as
long as `implements_pattern` is set.

**Pattern deviations and update isolation (ACS-500d-2):**

A deviation is a separate, standalone AC file that captures non-standard behavior for
a specific page or endpoint that otherwise inherits from a shared pattern. The key
design invariants are:

1. **Deviations are standard ACs.** A deviation AC has its own `id`, full
   `Given`/`When`/`Then` `criteria`, and a `depends_on` referencing the consuming AC.
   It does NOT have an `implements_pattern` field.

2. **Deviations take precedence.** For the specific behavior the deviation AC
   describes, that AC is authoritative. The shared pattern's definition of the same
   behavior is overridden by the deviation for that page or endpoint only.

3. **Pattern updates do not affect deviation ACs.** When a pattern AC is amended to
   add a new behavior, every consuming AC inherits the new behavior via the
   `implements_pattern` reference — but existing deviation ACs remain completely
   unchanged. The pattern resolution logic MUST NOT modify, overwrite, or delete any
   deviation AC when the referenced pattern is updated.

4. **No conflict at the schema level.** Because deviations are independent files (not
   inline overrides), there is no merge conflict between an updated pattern and an
   existing deviation. The two mechanisms are orthogonal: the consuming AC inherits
   new pattern behaviors by reference; the deviation continues to override only the
   specific aspect it was written for.

This design was adopted to keep the schema minimal (no special deviation fields) and
to make the precedence rule declarative: if a separate AC exists in the same feature
folder that addresses the same behavior, it takes precedence over the pattern.

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
