---
title: "Reference: AC Traceability Store Schema"
description: "Field-by-field reference for AC YAML files, the hierarchical ID format and parent derivation algorithm, status lifecycle, and pre-commit hooks that enforce the AC store at commit time."
type: reference
status: active
created: 2026-06-04
last_updated: 2026-06-18
components:
  - build_pipeline
related_docs:
  - docs/how-to/ac-traceability-store.md
  - docs/acceptance-criteria/README.md
  - config/ac_store_schema.json
---

# AC Traceability Store Schema

Reference for every field in an acceptance-criterion (AC) YAML file, the
ID format and assignment rules, the status lifecycle, the pre-commit hooks
that enforce the schema, and the agent integration points that read from or
write to the AC store.

---

## YAML Schema Fields

Each AC file is a single YAML document with the following fields.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | **yes** | Stable AC identifier. Format: `PREFIX-NNN` (see ID Format below). Never changes after creation. |
| `title` | string | **yes** | One-line human-readable description of the criterion. |
| `component` | string | **yes** | AC-store namespace/prefix key — matches a kebab `id` in `docs/acceptance-criteria/index.yaml`. Used for file placement and ID-prefix resolution. Retained for backward compatibility; the knowledge graph reads the `components` **list** (below), not this scalar. This is a different axis from the `components` list; the two registries are intentionally separate. |
| `status` | enum | **yes** | Lifecycle state: `active`, `deprecated`, `superseded_by`, or `superseded`. (`superseded_by` is canonical; `superseded` is accepted for older records.) |
| `criteria` | string | **yes** | Multi-line Gherkin scenario body (`Given`/`When`/`Then`/`And`). |
| `created` | date or string | no | Date this AC was created (`YYYY-MM-DD`). Most records use this field (92 %). YAML bare dates are parsed as native date objects; both forms are accepted. |
| `created_by` | string | no | Path to the ticket that introduced this criterion. Used by some older authoring flows (14 % of records). Newer records use `created` + `created_by_ticket` instead. |
| `created_by_ticket` | string or null | no | Path to the ticket that introduced this criterion. Used by newer authoring flows (10 % of records) alongside `created`. |
| `superseded_by` | string, list of strings, or null | no | AC ID of the replacement criterion. Null when not superseded. A list form (`[ID-1, ID-2]`) is accepted when an AC is split into multiple successors. Must be set when `status` is `superseded_by`; null otherwise. |
| `amended_by` | list | no | Amendment history. Items may be plain strings (ticket paths or free-form notes) or objects with a `reason` key (structured records produced by agent workflows). Default: `[]`. |
| `covered_by` | list of strings | no | Test file paths (optionally with `::test_function`) or child AC IDs that verify or cover this criterion. Default: `[]`. |
| `implemented_by` | list of strings | no | Source file paths (optionally with `#anchor`) that implement this criterion. Default: `[]`. |
| `depends_on` | list of strings or null | no | List of AC IDs that this AC depends on. Used for two purposes: (1) parent-child hierarchy links — a child AC lists its structural parent ID so the hierarchy is navigable from the child direction; (2) pattern composition — a composite pattern AC lists the atomic pattern AC IDs it wires together. **Must not form a cycle.** The `check_ac_circular_deps` pre-commit hook enforces a directed-acyclic-graph (DAG) invariant on all `depends_on` edges and blocks commits that would introduce a cycle. Default: `[]`. |
| `origin_agent` | string | no | Identity of the agent or workflow that created this AC file. Free-form provenance string — any non-empty value is valid. The field is **not** validated against the current agent registry. Historical agent names (including names of deleted, renamed, or decomissioned agents) remain valid and are never rewritten during schema upgrades. Example values: `business-analyst` (canonical name, also used historically as v1 and promoted from v3), `business-analyst-v2` (deleted agent), `business-analyst-v3` (legacy v3 name, now renamed to `business-analyst`), `create-ticket` (deleted agent), `refinement` (deleted agent), `BrainCandy` (human author), `ticket-wiring` (workflow). |
| `readiness` | enum or null | no | Lifecycle readiness state: `draft`, `reviewed`, or `approved`. Present on ~69 % of records. |
| `priority` | enum or null | no | Implementation priority: `critical`, `high`, `medium`, or `low`. Present on ~69 % of records. |
| `level` | enum or null | no | Hierarchy level: `L0` (portfolio), `L1` (feature), `L2` (story/task), `L3` (sub-task). |
| `work_status` | enum or null | no | Implementation lifecycle: `not_started` / `todo` (aliases), `in_progress`, `done`. |
| `req_status` | enum | no | Requirement lifecycle status from a product perspective: `active`, `draft`, `approved`, or `superseded`. Independent of `work_status`. |
| `assigned_agent` | string or null | no | Implementation agent assigned to this AC (e.g. `python-coder`). Set by it-po during technical enrichment. |
| `estimated_complexity` | enum or null | no | T-shirt size estimate: `XS`, `S`, `M`, `L`, or `XL`. Set by it-po. |
| `delivers_to` | null, string, object, or list | no | Downstream contract: what this AC's implementation delivers. May be null, a free-form agent name string, a structured `{agent, contract}` object, or a list of such objects. |
| `expects_from` | null, string, object, or list | no | Upstream contract: what this AC expects to receive. Same type space as `delivers_to`. |
| `it_requirements` | string, list of strings, or null | no | Technical requirements for implementation. May be a multi-line string or a list of requirement strings. Set by it-po. |
| `doc_links` | list | no | Documentation links. Items are either plain path strings or objects with `path`, `relationship`, `status` (`exists`/`planned`), and optional `relevance` fields. Default: `[]`. |
| `roadmap_phase` | string | no | Roadmap phase this AC belongs to (e.g. `phase_1`). Matches a phase key in `docs/roadmap.json`. |
| `notes` | string | no | Free-form contextual notes — authorship context, post-implementation findings, or rationale that does not belong in `criteria`. |
| `parent` | string | no | Explicit parent AC ID. Used when the structural parent cannot be mechanically derived from the ID format. Prefer the id-based derivation algorithm where possible. |
| `components` | list of strings | **yes** | Authoritative **graph-membership** list — **this is the field the knowledge graph reads** to build `component_membership` edges (see `config/paths.json` `acs` surface `edge_fields`). Must be present and non-empty, and every value must be an underscore `id` from `docs/components.json` (the 42 graph component ids, e.g. `knowledge_system`, `build_pipeline`). This is a distinct axis from the scalar `component` field: `component` is the AC-store namespace key (index.yaml kebab ids); `components` is the graph vocabulary (components.json underscore ids). An AC may legitimately have different values on each axis. Existing records were brought up to standard by `scripts/ac_store/backfill_components.py`. |
| `scope` | string | no | Scope qualifier (e.g. `standing` for standing/permanent requirements that persist across sprints). |
| `child_limit_override` | integer or null | no | **Temporary escape hatch.** Raises (never lowers) the default child count hard cap for this parent AC. When set to `N`, the `check-ac-tree-limits` hook uses `max(default_cap, N)` as the effective cap. An override below the default is silently ignored (fail-open). An `OVERRIDE ACTIVE` audit line is emitted to stderr (non-blocking) when the override is active and `child_count` exceeds the default. Only meaningful on L0 and L1 ACs. **Must be removed once the structural reorganisation (e.g. AC-UID-decoupling) is complete.** |
| `implements_pattern` | string or null | no | ID of the reusable behavior pattern this AC inherits from (e.g. `PTN-001`). When set, the effective behavior is derived from the referenced pattern combined with any `pattern_bindings`. The `criteria` field may contain a plain-text placeholder rather than a full `Given`/`When`/`Then` scenario. |
| `pattern_bindings` | object or null | no | Key-value bindings that instantiate the referenced pattern for this AC. Values may be strings, arrays, or objects. Only meaningful when `implements_pattern` is set. Example: `{entity_type: "users", columns: ["name", "email"]}`. |
| `pattern_slots` | list of strings or null | no | List of `{word}` placeholder strings that this pattern AC exposes as bindable slots. Only meaningful on pattern ACs — ACs that other ACs reference via `implements_pattern`. Each entry is a placeholder matching a named placeholder in the `criteria` field (e.g. `"{columns}"`, `"{default_sort}"`). Consuming ACs must supply a value for every slot via `pattern_bindings`. The `check_ac_schema.py` hook derives required slots from this list (falling back to scanning `criteria` for `{word}` placeholders when `pattern_slots` is absent). |
| `documentation_triggers` | list of enums or null | no | Documentation types required for this feature. Valid on L1 ACs only. Values: `how-to`, `sequence-diagram`, `state-diagram`, `component-diagram`, `reference-doc`. Empty array = no docs needed (provide `documentation_rationale`). |
| `documentation_rationale` | string or null | no | Explains why no documentation is needed when `documentation_triggers` is empty on an L1 AC. |
| `change_target` | string or list of strings | no | Classification of what kind of artifact this AC targets (ADR-017 blast-radius vocabulary). Used by the computed quality-gates pipeline (`_build_agents_map`) to look up mandatory guardrail agents. Accepts a single value OR a list when the AC spans multiple targets. Valid values: `code`, `schema`, `ui`, `infrastructure`, `pipeline`, `prompt`, `model`, `config`, `docs`, `dependency`. Optional — absent on ACs that predate the computed-gates pipeline (ticket 10 will backfill). |
| `risk_surface` | string | no | Classification of the blast-radius / risk exposure of this AC (ADR-017 blast-radius vocabulary). Combined with `change_target` to select mandatory guardrail agents. Valid values: `internal`, `contract_boundary`, `auth`, `privacy`, `safety`, `cost`. Optional — absent on pre-computed-gates ACs. |

### Full example

```yaml
id: FIN-001
title: "Merge main before running tests"
component: finalize
status: active
created: 2026-06-04
criteria: |
  Given a worktree branched from an older commit of main
  When the finalize-feature workflow begins
  Then it merges origin/main into the current branch before running any tests
  And it aborts with a clear error message if the merge produces a conflict
covered_by:
  - "unit_tests/test_finalize.py::test_merge_main_before_tests"
implemented_by:
  - "scripts/finalize.py#merge_main"
amended_by: []
origin_agent: business-analyst
```

### Pattern AC example (with pattern_slots)

A pattern AC declares the slots that consuming ACs must bind. The `pattern_slots`
field lists each `{word}` placeholder from the `criteria` field explicitly.

```yaml
id: ACS-500a-1
title: "A pattern AC defines shared behavior with parameterized slots"
component: ac-store
level: L2
status: active
created_by: "tickets/00_inbox/epics/EPIC-PatternReuse/01_define_pattern.md"
criteria: |
  Given an AC YAML file with level: L2,
  When its criteria describes behavior with named slots
    (e.g. "sortable table with columns {columns}, sorted by {default_sort}"),
  Then that AC is the single authoritative definition of the shared behavior.
pattern_slots:
  - "{columns}"
  - "{default_sort}"
readiness: approved
priority: high
origin_agent: BrainCandy
```

### Pattern-inherited AC example (empty criteria)

When an AC inherits all of its behavior from a reusable pattern, the `criteria`
field may contain a plain-text placeholder instead of a full `Given`/`When`/`Then`
scenario. The schema validator accepts this form when `implements_pattern` is set.

```yaml
id: PAGE-005
title: "Users list page — standard CRUD table (PTN-001)"
component: users-ui
status: active
created_by: "tickets/00_inbox/epics/EPIC-UsersUI/03_users_list.md"
criteria: "No page-specific behavior — all behavior inherited from pattern."
implements_pattern: "PTN-001"
pattern_bindings:
  entity_type: "users"
  columns:
    - "name"
    - "email"
readiness: draft
priority: medium
origin_agent: business-analyst
```

**Key points:**
- `criteria` must still be a non-empty string (the schema requires `minLength: 1`).
- A plain-text placeholder like `"No page-specific behavior — all behavior inherited from pattern."` satisfies this requirement.
- The effective behavior is entirely derived from the pattern referenced in `implements_pattern`, instantiated with the `pattern_bindings` values.
- The schema validator does **not** enforce `Given`/`When`/`Then` format — any non-empty string is valid.

---

## ID Format and Assignment

AC IDs follow the pattern `PREFIX-NNN`, where `NNN` may be followed by
optional hierarchical suffix segments. Compound prefixes (two uppercase
groups joined by a hyphen, e.g. `KM-DBF`) are also accepted.

| Part | Rules |
|---|---|
| `PREFIX` | 2–6 uppercase ASCII letters. Derived from the component's `prefix` field in `docs/acceptance-criteria/index.yaml`. May itself contain a hyphen-separated uppercase sub-group for compound namespaces (e.g. `KM-DBF`, `KM-KQS`). |
| `-` | Literal hyphen separator. |
| `NNN` | One or more digits (historically three zero-padded digits, e.g. `001`; the schema accepts any positive integer). |
| Hierarchical suffix | Optional. See the Hierarchical AC IDs table below. |

**Examples:** `FIN-001`, `AUTH-007`, `BP-042`, `ACS-100`, `KM-DBF-001`.

**Assignment:** IDs are assigned at creation time and never reused. If an
AC is deprecated, its ID remains reserved so that historical references
(e.g. in commit messages or tickets) remain resolvable.

**Full ID regex:** `^[A-Z]{2,6}(-[A-Z]{2,6})?-\d+([a-z]\d*(-\d+[a-z\d]*(-[a-z\d]+)?)?|-\d+[a-z\d]*(-[a-z\d]+)?)?$`

This single regex covers all supported forms:

| Form | Example | Matches |
|---|---|---|
| Root / base | `ACS-100`, `FIN-001` | `PREFIX-\d+` |
| Compound-prefix root | `KM-DBF-001` | `PREFIX-SUB-\d+` |
| L1 alpha | `ACS-100a`, `ACS-200d` | `PREFIX-\d+[a-z]` |
| L1 alpha with digit suffix | `BP-800a2` | `PREFIX-\d+[a-z]\d+` |
| L2 alpha-first | `ACS-500a-1` | `PREFIX-\d+[a-z]-\d+` |
| L2 numeric-only (no alpha L1) | `BO-510-1`, `BO-610-3` | `PREFIX-\d+-\d+` |
| L2 with trailing alpha | `ACS-300g-4a`, `PER-100d-2a` | `PREFIX-\d+[a-z]-\d+[a-z]` |
| L3 alpha extension (alpha-first) | `ACS-500a-1-i`, `ACS-1100b-3-i` | `PREFIX-\d+[a-z]-\d+-[a-z]+` |
| L3 alpha extension (numeric-only) | `BO-510-3-i`, `BO-610-4-i` | `PREFIX-\d+-\d+-[a-z]+` |
| L3 numeric extension | `BO-300a-2-1`, `BP-900a-1-1` | `PREFIX-\d+[a-z]-\d+-\d+` |

### Hierarchical AC IDs and Parent Derivation

ACs form a hierarchy. Child ACs extend the root pattern with additional
segments. The parent ID is derived from the child ID by stripping the last
segment. This derivation is implemented in `scripts/ac_store/ac_parent_id.py`
and is the canonical algorithm for all parent-child enforcement (pre-commit
hooks, store-wide scans, agent auto-updates).

| Level | Format | Example | Parent |
|---|---|---|---|
| L0 (root) | `PREFIX-NNN` | `ACS-100` | (none) |
| L1 (alpha) | `PREFIX-NNNx` | `ACS-100a` | `ACS-100` |
| L2 (numeric) | `PREFIX-NNNx-N` | `ACS-100a-1` | `ACS-100a` |
| L3 (extension) | `PREFIX-NNNx-N-y` | `ACS-100a-1-i` | `ACS-100a-1` |

**Derivation rules (ACS-100i-1):**

1. If the ID matches `^[A-Z]{2,6}-[0-9]{3}$` (root pattern): no parent (`None`).
2. If the ID matches `^[A-Z]{2,6}-[0-9]{3}[a-z]+$` (alpha suffix directly on the
   numeric part, no hyphen): strip the trailing lowercase letters.
   Example: `ACS-100a` → `ACS-100`.
3. Otherwise: strip the last hyphen-delimited segment (everything after the final `-`).
   Examples: `ACS-300h-1` → `ACS-300h`; `ACS-300h-2-i` → `ACS-300h-2`.

Use `derive_parent_id(ac_id)` from `scripts/ac_store/ac_parent_id.py` rather than
re-implementing this logic inline.

---

## Status Lifecycle

```
active ──── deprecated
  │
  └──────── superseded_by ──── (points to new active AC)
  │
  └──────── superseded ──────── (alternate form; equivalent to superseded_by)
```

| Status | Meaning | Effect on hooks |
|---|---|---|
| `active` | Criterion is currently enforced. | `check_ac_coverage.py` requires at least one `covered_by` entry. |
| `deprecated` | Criterion is retired; retained for audit. | `check_ac_coverage.py` skips this AC. `check_test_ac_tags.py` emits a warning if any test still tags this AC. |
| `superseded_by` | Criterion was replaced by another AC. `superseded_by` field identifies the replacement. Canonical form for new records. | Same as `deprecated` — excluded from active enforcement. |
| `superseded` | Alternate form of `superseded_by` accepted by the schema for older records. Functionally equivalent. | Same as `deprecated` — excluded from active enforcement. |

**Transition rules:**

- `active` → `deprecated`: set `status: deprecated`. No other changes required.
- `active` → `superseded_by`: set `status: superseded_by` and `superseded_by: <new-ID>` (canonical) or `superseded_by: [ID-1, ID-2]` when split into multiple successors.
- `deprecated` or `superseded_by` → re-activation is not supported. Create a new AC instead.

---

## Composition Depth and the Behavior Stack (ACS-500e-2)

When an AC references a composite pattern, the **full behavior stack** for
that AC spans multiple layers. Each layer is a distinct AC file with its own
`id` and `criteria`. The layering is expressible using only the standard
`depends_on` and `implements_pattern` fields — no additional hierarchy
mechanism is required.

### Layer ordering (highest to lowest precedence)

| Layer | Source field | AC role | Description |
|---|---|---|---|
| 1. Page-specific | (the AC itself) | page / consumer AC | Criteria unique to this page or component. Overrides or supplements inherited behavior. |
| 2. Composite wiring | `implements_pattern` | composite pattern AC | Wiring behavior that connects multiple atomic patterns (e.g. "filter changes reset pagination"). Defined once; reused by every consumer. |
| 3. Atomic behaviors | composite's `depends_on` | atomic pattern ACs | Isolated, single-concern behaviors (e.g. column sorting, filter bar, pagination). Each atomic AC is an independent reusable unit. |

### Traversal algorithm

A reader can resolve the full behavior stack for any page AC by following two
standard fields:

1. **Read the page AC.** Its own `criteria` field provides the page-specific layer.
2. **Follow `implements_pattern`.** If set, load the referenced composite pattern
   AC. Its `criteria` field provides the composite wiring layer.
3. **Follow the composite's `depends_on`.** For each listed AC id, load that AC.
   Each provides an atomic behavior layer, in `depends_on` declaration order.

```
page AC
  └─ implements_pattern ──→ composite pattern AC (PTN-020)
                               └─ depends_on ──→ atomic AC (PTN-010)
                               └─ depends_on ──→ atomic AC (PTN-011)
                               └─ depends_on ──→ atomic AC (PTN-012)
```

The function `resolve_behavior_stack(ac_id, id_index)` in
`scripts/ac_store/scan_ac_store.py` implements this algorithm and returns
the stack as an ordered list of `BehaviorLayer` dicts.

### Example: CRUD list page

Given the following ACs:

```yaml
# Page AC (consumer)
id: PAGE-001
implements_pattern: PTN-020
criteria: "No page-specific wiring — all behavior inherited from PTN-020."

# Composite pattern AC
id: PTN-020
depends_on: [PTN-010, PTN-011, PTN-012]
criteria: |
  Given a page implements sort, filter, and pagination,
  When the user changes a filter, Then pagination resets to page 1 ...

# Atomic pattern ACs
id: PTN-010
criteria: |
  Given a page contains a sortable table ...
id: PTN-011
criteria: |
  Given a page contains a filter bar ...
id: PTN-012
criteria: |
  Given a page displays a paginated collection ...
```

`resolve_behavior_stack("PAGE-001", id_index)` returns:

```python
[
  {"layer": "page",      "ac_id": "PAGE-001", "source": "self", ...},
  {"layer": "composite", "ac_id": "PTN-020",  "source": "implements_pattern", ...},
  {"layer": "atomic",    "ac_id": "PTN-010",  "source": "depends_on", ...},
  {"layer": "atomic",    "ac_id": "PTN-011",  "source": "depends_on", ...},
  {"layer": "atomic",    "ac_id": "PTN-012",  "source": "depends_on", ...},
]
```

### Design invariants

- **Atomic patterns are independent.** Atomic pattern ACs have no `depends_on`
  links to each other — they define isolated behaviors.
- **The composite owns the wiring.** The composite pattern AC's `criteria`
  describes ONLY inter-pattern coordination (e.g. "filter changes reset
  pagination"), not the atomic behaviors that PTN-010, PTN-011, and PTN-012
  already define.
- **`depends_on` on pattern ACs is declarative.** It documents composition
  intent. No runtime resolution is required; a validator may warn when a
  `depends_on` target is absent but MUST NOT block commits for missing patterns.
- **No additional field is needed.** The full behavior stack is resolvable
  through `implements_pattern` and `depends_on` alone.

---

## Pre-Commit Hooks

Three hooks are installed by `build.py` to enforce the AC store at commit time.

> **Enforcement is not single-sourced — add a new field rule to every gate.**
> AC field validation lives in more than one place: the commit hook
> `check_ac_schema.py` validates against `config/ac_store_schema.json` (JSON
> Schema draft-07), but falls back to a **manual-validation branch** — plus
> per-file semantic validators in `_ac_schema_validators.py` — when `jsonschema`
> is unavailable, and that fallback is what actually gates in some environments.
> A separate agent-side validator, `scripts/ac_store/validate_ac_schema.py`,
> checks a subset independently. A new required-field rule added to only the JSON
> schema is therefore a partial (sometimes no-op) gate; add it to every
> enforcement point that should reject the field.

### `check_ac_schema.py` (blocking)

Validates every staged YAML file under `docs/acceptance-criteria/` against
`config/ac_store_schema.json` (JSON Schema draft-07). Runs two phases:
Phase 1 (schema + cross-file checks) and Phase 2 (field-preservation).

| Attribute | Value |
|---|---|
| Hook ID | `check-ac-schema` |
| Exit code | `1` on any violation; `0` when all files pass. |
| Mode | Always blocking (`error` mode). |
| Invocation | `python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_ac_schema.py` |
| Scoped to | `docs/acceptance-criteria/` staged files |
| Registered in | `commit_guardian.json` → `hooks_manifest.hooks` |

#### Phase 1 — Schema and cross-file checks

Validates required fields present, `status` is one of the allowed enum
values, `id` matches the `PREFIX-NNN` regex, `superseded_by` is non-null
only when `status == superseded_by`.

Additionally performs three cross-file checks against the full AC store index:

**Pattern bindings completeness (ACS-500f-1):**
When a staged AC has `implements_pattern` set, the hook loads the referenced
pattern AC and derives its required slots from `pattern_slots` (or by scanning
for `{slot_name}` placeholders in `criteria`). Every slot must appear as a key
in the consuming AC's `pattern_bindings`. If any slot is missing the commit is
blocked with an error that names the missing key and the pattern AC id:

```
<file>: pattern_bindings missing required key '<slot>' for pattern <pattern-id>
```

**Deprecated pattern reference (ACS-500a-3-ii):**
When `implements_pattern` references a pattern AC whose `status` is
`deprecated`, the commit is blocked with:

```
<file>: implements_pattern references deprecated pattern <id>;
        use its successor (see <id> superseded_by field) or remove the reference
```

**Duplicate criteria detection (ACS-500c-3):**
When a standalone AC (no `implements_pattern`) has `criteria` text
structurally equivalent to a live pattern AC (same Gherkin steps with
concrete values in place of `{slot}` placeholders), the commit is blocked:

```
<file>: criteria is a likely duplicate of pattern <id>;
        use implements_pattern: <id> with pattern_bindings instead
```

#### Phase 2 — implements_pattern field-preservation (ACS-500f-1)

For each staged *modified* AC YAML file (diff-filter M — files that already
existed in HEAD), the hook loads both the HEAD version (via `git show HEAD:`)
and the staged (disk) version. If `implements_pattern` was present and
non-empty in HEAD but is absent or empty in the staged version, the commit is
blocked:

```
<file>: implements_pattern was dropped — this field must not be removed
        from an AC that previously declared it (was: '<old-value>')
```

**Rationale:** Silently removing `implements_pattern` while leaving the AC
otherwise in place breaks the pattern-reuse contract without triggering
`check_ac_pattern_refs.py` (which only fires on referenced-but-nonexistent
patterns). The field-preservation check catches this category of unintentional
or unauthorized removal at commit time.

**Fail-open behaviour:** Any unexpected exception (I/O error, git subprocess
failure, parse error) causes the hook to exit `0` with a warning on stderr
so a script error never hard-blocks an unrelated commit.

### `check_test_ac_tags.py` (configurable)

Verifies that every `def test_*` function in staged test files carries a
`# covers: XX-NNN` comment linking it to an AC.

| Attribute | Value |
|---|---|
| Exit code | `1` when violations found and `test_ac_tag_enforcement: error`; `0` always in `warn` mode. |
| Default mode | `warn` (grace period; commits never blocked by default). |
| Config key | `commit_guardian.json` → `test_ac_tag_enforcement`: `"warn"` or `"error"`. |
| Env override | `CHECK_TEST_AC_TAGS_MODE=error python check_test_ac_tags.py` |
| Tag placement | Line above `def test_*`, first body line, or docstring. |

Tag format: `# covers: XX-NNN` where `XX-NNN` is a valid AC ID.

### `check_ac_coverage.py` (warning only)

Verifies the reverse direction: every *active* AC is referenced by at
least one test's `# covers:` tag.

| Attribute | Value |
|---|---|
| Exit code | Always `0` (warning mode only). |
| Mode | Non-blocking by design. An AC and its test can be created in the same commit. |
| Scope | Reads `docs/acceptance-criteria/**/*.yaml`; scans `unit_tests/` for `# covers:` tags. |

Emits a warning for each active AC with no corresponding test tag.

### `check_ac_limits.py` (advisory)

Checks project-level AC count limits configured in `commit_guardian.json`.
Advisory only; never blocks a commit.

### `check_ac_circular_deps.py` (blocking)

Detects circular `depends_on` chains in staged AC YAML files.

| Attribute | Value |
|---|---|
| Exit code | `1` when a cycle is detected in staged files; `0` when clean. |
| Mode | Always blocking. |
| Invocation | `python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_ac_circular_deps.py` |

When a staged AC YAML file's `depends_on` field would create a cycle in the
`depends_on` graph, the commit is blocked with an error message naming the
full cycle path:

```
[check-ac-circular-deps] BLOCKED — circular depends_on chain(s) detected:
  [1] Circular dependency detected: PTN-010 -> PTN-020 -> PTN-010
```

**Algorithm:** Builds a complete `depends_on` adjacency list from the entire
AC store (loading all on-disk YAML files), then overlays the staged changes so
the graph reflects the proposed commit state. Runs an iterative DFS from each
staged AC id to detect any cycle involving that node. Only cycles that include
at least one staged AC id are reported — pre-existing cycles in unmodified files
are not blocked (they must be remediated separately).

**Fail-open:** Any unexpected exception (I/O error, parse failure, missing AC
store) causes the hook to exit `0` with a warning on stderr so a script error
never hard-blocks an unrelated commit.

---

## Agent Integration Points

### Authoring agents — parent covered_by update (mandatory)

Every requirement-authoring agent (`business-analyst`, `product-owner`,
`it-po`) that writes a new child AC file MUST, in the same write batch,
also update the parent AC file to record the new child. This is the canonical
mechanic for building the parent-child link from the parent's direction.

**Protocol (applied by any authoring agent when creating a child AC):**

1. Derive the parent ID using `derive_parent_id()` from
   `scripts/ac_store/ac_parent_id.py`. If the result is `None` (root-level
   AC), skip steps 2–4.
2. Locate the parent AC YAML file at
   `docs/acceptance-criteria/<component>/<feature-folder>/<parent-id>.yaml`.
3. Append the child AC ID to the parent's `covered_by` list, ONLY if the
   child ID is not already present (idempotent — no duplicate entries).
4. Write the update using an `Edit` call that modifies ONLY the `covered_by`
   field. Do NOT overwrite the parent file with `Write` — all other fields
   and values MUST be preserved exactly.

**Child AC requirements:**

- The child's `depends_on` field MUST include the parent AC ID.
- The child is written in the same write batch as the parent update —
  both writes are part of the same agent turn, not two separate passes.

**Why this matters:** The `covered_by` field on a parent AC is the forward
pointer from parent to child. Without it, `scan_ac_orphans.py` will report
the child as an orphan. The `check_ac_parent_covered_by.py` pre-commit hook
verifies this link at commit time; missing links block the commit.

**Example (creating `ACS-100i-3` as a child of `ACS-100i`):**

```yaml
# Before (ACS-100i.yaml excerpt):
covered_by: []

# After (ACS-100i.yaml excerpt — only covered_by changes):
covered_by:
  - ACS-100i-3

# New child file (ACS-100i-3.yaml excerpt):
id: ACS-100i-3
depends_on:
  - ACS-100i
covered_by: []
```

---

### business-analyst

When authoring a ticket that introduces new functionality, the
`business-analyst` agent reads the ticket's acceptance criteria and, when
`origin_agent: business-analyst` ACs are requested, writes new AC YAML
files to `docs/acceptance-criteria/<component>/`.

**Key behaviour:** the agent validates the file against `check_ac_schema.py`
before finalising. If validation fails, the agent self-corrects the YAML.

### business-analyst

The `business-analyst` agent (promoted from the v3 pipeline) produces L2/L3 AC YAML files from L1 ACs.
When writing a new L2 or L3 file, it applies the parent covered_by update
protocol described above: the child's `depends_on` includes the parent ID,
and the parent's `covered_by` list is updated in the same write batch.

### product-owner

The `product-owner` agent (promoted from the v3 pipeline) produces L0 and L1 AC YAML files. When writing
a new L1 file (child of an L0), it applies the parent covered_by update
protocol: the L1's `depends_on` includes the L0 ID, and the L0's `covered_by`
list is updated to include the new L1 ID.

### it-po

The `it-po` agent (promoted from the v3 pipeline) enriches existing L2/L3 AC files. When it creates new
AC files (e.g. split ACs), it applies the parent covered_by update protocol
for any newly created child AC, ensuring the parent's `covered_by` list is
updated to include the new child.

### test-writer

The `test-writer` agent reads `covered_by` lists from AC YAML files to
discover which tests already exist for an AC. It adds `# covers: XX-NNN`
tags to every new test function it writes, and appends the new test path to
the `covered_by` list in the corresponding AC YAML file.

#### `/quick-fix` workflow — test-writer dispatch (AC BP-600c-1)

When the `test-writer` is invoked by the `/quick-fix` workflow (as opposed to a
standard `build-feature` epic), it receives the AC YAML file created during the
AC creation phase as an additional structured input. The dispatch contract is:

| Input field | Type | Description |
|---|---|---|
| `ac_path` | file_path | Absolute path to the newly created quick-fix AC YAML file |
| `target_file` | file_path | Absolute path to the buggy source file |
| `location_hint` | string or null | Line number or function name from the diagnosis |
| `symptom` | string | Observable incorrect behaviour from the diagnosis |

**`# covers: <AC-ID>` tag requirement (quick-fix context):**

Every test function written for a quick-fix MUST include a `# covers: <AC-ID>` tag
referencing the newly created AC. The tag may appear:

- On the line immediately above `def test_*`
- As the first statement inside the function body
- In the function's docstring

The tag format must match the `check_test_ac_tags.py` hook pattern exactly:
`# covers: XX-NNN` (e.g. `# covers: BP-601`). The `XX-NNN` value is the `id`
field from the AC YAML file passed in `ac_path`.

**Ordering invariant (BP-600c-1):**

The test file write and the `covered_by` update to the AC YAML file MUST both
complete before the fix-implementation phase (`python-coder` or `sql-coder`) is
dispatched. This red-phase-first ordering is enforced by the sequential phase chain
in `quick-fix.js` and mirrors the TDD discipline of the standard `build-feature` workflow.

**`covered_by` update (same write batch):**

After writing the test file, the test-writer MUST append the new test path to the
`covered_by` list in the AC YAML file at `ac_path`. Both writes — the test file
creation and the `covered_by` update — occur in the same agent turn so they are
committed atomically.

```yaml
# Example: after test-writer runs for a quick-fix on build-pipeline
covered_by:
  - "unit_tests/test_build_pipeline_BP-601.py::test_executability_probe_not_skipped"
```

The parent AC's `covered_by` update protocol (see §Authoring agents above) also
applies here: if the quick-fix AC is a child AC, the parent's `covered_by` list
is updated to include the child AC ID (this was already done by `build-ac` during
AC creation). The test-writer only updates the child AC's `covered_by` field.

### python-coder — AC Assignments section in generated card (INF-600b-2)

When `generate_agent_cards.py` (called by `build.py`) generates a card for
an agent, it now scans `docs/acceptance-criteria/` recursively for AC YAML
files whose `assigned_agent` field equals the card's agent ID and whose
`status` is `"active"`. The matching ACs are passed to `generate_card()` as
`ac_assignments` and rendered as a `## AC Assignments` section at the end of
the card:

```markdown
## AC Assignments

### python-coder
- INF-600g-1: spawned_by/spawn_allowlist reciprocity validation
- INF-600g-2: __ticket_phase_agents__ redundancy detection
```

This section is omitted entirely when no active ACs are assigned to the agent.

**`ac_traceability` frontmatter field → per-agent grouping**

When a ticket has `ac_traceability: [INF-600g-1, INF-600g-2, INF-600g-3]`
frontmatter referencing multiple L2/L3 AC YAML files, each of which has an
`assigned_agent` field, the generated agent card groups those ACs by their
`assigned_agent`. The grouping allows each agent to identify exactly which
ACs it is responsible for without inspecting ACs assigned to other agents,
and enables agents to implement one AC at a time rather than attempting all
ticket work at once.

**Data flow:**

1. `build_agent_cards()` calls `_scan_ac_assignments(agent_id, target_root)`.
2. `_scan_ac_assignments()` walks `docs/acceptance-criteria/**/*.yaml` and
   collects dicts `{id, title, assigned_agent}` for all active ACs whose
   `assigned_agent` equals the card agent.
3. Results are passed to `generate_card(..., ac_assignments=results)`.
4. `generate_card()` calls `render_ac_assignments(agent_id, ac_list)` which
   produces the `## AC Assignments` section or returns `""` for an empty list.

**Error handling:** `_scan_ac_assignments()` wraps file reads in
`try/except OSError` and YAML parsing in `try/except yaml.YAMLError`. On
error, a WARNING is emitted and the file is skipped — card generation
continues without failing the build.

### triage agent (glossary-triage, debug)

The `debug` skill and `glossary-triage` agent can look up AC IDs to
surface the criterion text and coverage status. They read
`docs/acceptance-criteria/` directly via the filesystem.

The `check_test_ac_tags.py` hook integrates with the triage flow: a test
tagged `# covers: XX-NNN` where `XX-NNN` is deprecated will surface as a
triage item during the debug skill's AC lookup step.

### ticket-wiring

When `origin_agent: ticket-wiring` is set on an AC YAML file, the AC was
created by the ticket-wiring workflow (e.g. from a ticket's Gherkin block).
The `ticket-wiring` skill reads existing ACs and skips creation when an
equivalent AC already exists in the store.

### /quick-fix workflow — ID assignment (AC BP-600b-2)

The `/quick-fix` workflow creates a new AC YAML file as part of its AC creation
phase (AC BP-600b-1). When assigning the AC ID, the workflow MUST follow the
algorithm below to ensure the correct component prefix and a strictly sequential,
non-reusing numeric suffix.

#### Step 1 — Resolve the component prefix

Read `docs/acceptance-criteria/index.yaml`. Locate the entry whose `id` matches
the target component (e.g. `build-pipeline`). Use its `prefix` field as the
ID prefix (e.g. `BP`).

If no matching entry exists in `index.yaml`, halt the AC creation phase and
surface a structured error to the user:

```
Error: component '<id>' not found in docs/acceptance-criteria/index.yaml.
Add the component entry before running /quick-fix.
```

#### Step 2 — Scan existing AC files for the highest numeric suffix

Scan all YAML files directly under `docs/acceptance-criteria/<component-id>/`
(non-recursively — only root-level L0 and L1 files; subdirectories are skipped).
Parse each filename matching the pattern `PREFIX-NNN*.yaml`. Extract the numeric
part `NNN` (zero-padded, three digits) and track the highest value found.

If no existing files match the prefix, start at `001`.

**Retired/deprecated AC IDs are reserved and MUST NOT be reused.** The scan
reads the `status` field of each matched file. Whether `active`, `deprecated`,
or `superseded_by`, the numeric slot is permanently occupied. The next
available integer is `max(occupied_slots) + 1`.

#### Step 3 — Assign the new ID

Assign `ID = PREFIX + "-" + zero_pad(max_seen + 1, width=3)`.

**Example:** if `build-pipeline` already contains `BP-001.yaml` through
`BP-006.yaml` (including any deprecated files), the next ID is `BP-007`.

#### Step 4 — Atomicity constraint

ID allocation MUST be atomic with respect to concurrent `/quick-fix` invocations.
Implement atomicity using a file-based lock at
`${TMPDIR:-/tmp}/leafcutter-quickfix-<component-id>.lock` before the scan
(step 2) and release it after the file is written. Use `O_CREAT | O_EXCL` for
lock acquisition. Release the lock unconditionally in all exit paths (success
and error).

The lock file MUST live outside the tracked working tree (a system-temp or
otherwise gitignored path) so it can never be accidentally staged or committed.
Never place it under `docs/` or any other version-controlled directory.

If the lock cannot be acquired within 5 seconds, surface an error to the user:

```
Error: AC store for '<component-id>' is locked by another process.
Retry after the concurrent quick-fix completes, or manually remove
${TMPDIR:-/tmp}/leafcutter-quickfix-<component-id>.lock if the process
is no longer running.
```

### AC persistence guarantee after ticket lifecycle close (AC BP-600b-3)

When the quick-fix workflow completes end-to-end — fix committed and the
workflow's internal ticket closed — the AC YAML file created during the AC
creation phase MUST remain untouched in the store.

**Invariant:**

```
Given the quick-fix workflow has completed end-to-end (fix committed
  and ticket closed),
When the user lists AC files under docs/acceptance-criteria/,
Then the AC YAML file created by the quick-fix workflow still exists,
And its status field is "active",
And it is not deleted or moved by the ticket lifecycle close step.
```

**Implementation constraint for the ticket lifecycle close step:**

The step that marks the quick-fix workflow's internal ticket as `done` (e.g.
flipping `status: in_progress → done` via `set_ticket_status.py`) MUST NOT
touch or reference any AC YAML file. Specifically:

- The close step operates only on the ticket markdown file (`*.md`) and the
  git index for that file.
- It MUST NOT delete, rename, move, or overwrite any file under
  `docs/acceptance-criteria/`.
- It MUST NOT set the AC's `status` field to `deprecated` or `superseded_by`
  as a side-effect of the ticket closing.

The AC lifecycle (active → deprecated → superseded_by) is governed exclusively
by human or agent intent expressed in separate commits. A ticket closing is not
a trigger for AC lifecycle transitions.

**Why this guarantee is necessary:**

The quick-fix workflow creates an AC YAML file as a permanent traceability
artefact. The AC documents what bug was fixed and what criterion the fix must
satisfy going forward. If the ticket lifecycle close step were to delete or
deactivate the AC, the traceability record would be destroyed, the pre-commit
`check_ac_coverage.py` hook would lose its anchor, and any test tagged
`# covers: <id>` would reference a ghost criterion. The persistence guarantee
ensures the AC outlives the workflow that created it.

---

## Component Registry (`index.yaml`)

`docs/acceptance-criteria/index.yaml` is the component registry. It maps
component IDs to their prefix and description.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | **yes** | Kebab-case component identifier. Must match the `component` field in all ACs for this namespace. |
| `prefix` | string | **yes** | 2–6 ALL-CAPS letters used in AC file names. |
| `description` | string | **yes** | Human-readable description of the component. |
| `owner` | string or null | no | Team or agent identifier responsible for this namespace. |
| `directory_patterns` | list of strings | no | Glob patterns for source file paths that belong to this component. Used by `/quick-fix` to infer the component from a diagnosed file path when no explicit component is provided (AC BP-600b-2-i). Example: `["scripts/build_*.py", "scripts/build_phases.py"]`. If absent or empty, component inference falls back to user prompt. |

---

## See Also

- `docs/how-to/ac-traceability-store.md` — task-oriented guide for creating, amending, and deprecating ACs.
- `docs/how-to/declare-component-membership.md` — how to add the `components` list to an AC (or any knowledge item) so it joins the component view, and how to query a component back to its criteria and delivering code.
- `docs/acceptance-criteria/README.md` — directory structure and quick-start.
- `config/ac_store_schema.json` — machine-readable JSON Schema (draft-07) for the AC YAML format.
- `docs/README.md` — full documentation index.
