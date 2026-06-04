---
title: "ADR-007: AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model"
type: "adr"
status: "accepted"
created: "2026-06-04"
last_updated: "2026-06-04"
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
- Regex: `^[A-Z]{2,6}-[0-9]{3}$`.

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
