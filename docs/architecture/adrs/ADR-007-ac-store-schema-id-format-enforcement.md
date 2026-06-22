---
title: "ADR-007: AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model"
description: "Defines the AC YAML schema, hierarchical ID format with parent derivation algorithm, status lifecycle, and stdlib-only commit-time enforcement model for the leafcutter AC Traceability Store."
type: "adr"
status: "accepted"
created: "2026-06-04"
last_updated: "2026-06-18"
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

### Circular `depends_on` Dependency Enforcement (ACS-500e-1-i)

A second enforcement hook `scripts/commit_guardian/check_ac_circular_deps.py`
enforces a directed-acyclic-graph (DAG) invariant on the `depends_on` field.

**Why `depends_on` must be a DAG:** The `depends_on` field is used for two
purposes: (1) parent-child hierarchy links (child AC lists its structural parent)
and (2) pattern composition (composite pattern AC lists the atomic patterns it
wires together). Both uses assume the graph is acyclic — any tool that
recursively resolves `depends_on` references (pattern resolution, hierarchy
navigation, coverage aggregation) would loop infinitely if a cycle existed.

**Enforcement algorithm:**

1. When any `docs/acceptance-criteria/**/*.yaml` file is staged, the hook
   builds a complete `depends_on` adjacency list by reading all on-disk AC
   YAML files in the AC store.
2. The staged files' parsed content is overlaid on the on-disk graph, so
   the graph reflects the proposed commit state rather than HEAD.
3. An iterative DFS is run from each staged AC id to detect cycles reachable
   from that node.
4. If a cycle is found that involves at least one staged AC id, the commit is
   blocked with an error naming the full cycle path:
   ```
   [check-ac-circular-deps] BLOCKED — circular depends_on chain(s) detected:
     [1] Circular dependency detected: PTN-010 -> PTN-020 -> PTN-010
   ```

**Fail-open guarantee:** Any unexpected exception (I/O error, YAML parse
failure, missing AC store directory) causes the hook to exit `0` with a
`WARNING` prefix on stderr. A script failure never hard-blocks a commit that
is unrelated to the circular dependency concern.

**Configuration:** The hook is registered in `commit_guardian.json` with id
`check-ac-circular-deps`, file pattern `^docs/acceptance-criteria/.*\.yaml$`,
and `pass_filenames: false`.

**Why stdlib only:** External validator libraries (`jsonschema`) are not
guaranteed to be installed in the commit hook environment of every adopter
project. A stdlib-only fallback ensures the hook runs without a separate
`pip install` step. If `jsonschema` is available it is used for full draft-07
validation; if absent the script performs equivalent manual checks.

### Composition Depth Visibility (ACS-500e-2)

Composition depth is visible through the AC parent-child hierarchy using
only the two standard fields `implements_pattern` and `depends_on`. No
additional hierarchy mechanism is needed.

**Layer resolution algorithm:**

1. Read the page AC — its `criteria` provides page-specific behavior.
2. Follow `implements_pattern` to the composite pattern AC — its `criteria`
   provides the composite wiring behavior.
3. Follow the composite's `depends_on` list — each referenced AC provides
   an atomic behavior.

The function `resolve_behavior_stack(ac_id, id_index)` in
`scripts/ac_store/scan_ac_store.py` implements this algorithm. It returns an
ordered list of `BehaviorLayer` dicts with keys `layer`, `ac_id`, `criteria`,
and `source`. The `layer` values are `"page"`, `"composite"`, and `"atomic"`;
`source` values are `"self"`, `"implements_pattern"`, and `"depends_on"`.

**Design invariant:** `depends_on` on a pattern AC is purely declarative
(documents composition intent). A validator may warn when a target is absent
but MUST NOT block commits — pattern references are non-blocking by design
(see Circular `depends_on` Dependency Enforcement above for the contrast with
the blocking DAG invariant on structural parent-child links).

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

## Partial-Run Recovery — Field-Based Orphan Detection

The `origin_agent` and `readiness` fields defined in this ADR are used by the
`/create-ac` workflow's Partial-Run Recovery pre-flight (AC ACD-300g-2-i) to
detect orphaned AC files left by a prior crashed session.

**Detection approach:**

1. `git status --porcelain <ac-store-dir>` identifies YAML files with any
   uncommitted change (modified, added, or untracked).
2. Each candidate file is loaded and its `origin_agent` field is checked
   against the set of AC-authoring agents:
   `{product-owner-v3, business-analyst-v3, it-po-v3}`.
3. The `readiness` field is checked for the value `draft` — only ACs that
   have not yet been reviewed or approved can be orphaned.

A file qualifies as an orphan only if both checks pass. Files that fail
either check (e.g. a YAML file modified by a human, or an AC already
promoted to `readiness: reviewed`) are skipped. This ensures the recovery
pre-flight is non-destructive and does not accidentally commit or discard
intentionally-staged work.

The `origin_agent` field is optional in the schema (see Optional fields
table above) but is written by all three AC-authoring agents (product-owner-v3,
business-analyst-v3, it-po-v3) as part of their standard output. The
`readiness` field is also optional in the raw schema but is always set by
authoring agents.

Full pre-flight specification: `templates/skills/create-ac/SKILL.md §PRR`.
