---
title: "Reference: AC Traceability Store Schema"
description: "Field-by-field reference for AC YAML files, the hierarchical ID format and parent derivation algorithm, status lifecycle, and pre-commit hooks that enforce the AC store at commit time."
type: reference
status: active
created: 2026-06-04
last_updated: 2026-06-08
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
| `component` | string | **yes** | Component name matching an `id` key in `docs/acceptance-criteria/index.yaml`. |
| `status` | enum | **yes** | Lifecycle state: `active`, `deprecated`, or `superseded_by`. |
| `created_by` | string | **yes** | Path to the ticket (relative to repo root) that first introduced this criterion. |
| `criteria` | string | **yes** | Multi-line Gherkin scenario body (`Given`/`When`/`Then`/`And`). |
| `superseded_by` | string or null | no | AC ID of the replacement criterion. Must be set when `status` is `superseded_by`; null otherwise. |
| `amended_by` | list of strings | no | Ticket paths that subsequently amended this criterion. Default: `[]`. |
| `covered_by` | list of strings | no | Test file paths (optionally with `::test_function`) that verify this criterion. Default: `[]`. |
| `implemented_by` | list of strings | no | Source file paths (optionally with `#anchor`) that implement this criterion. Default: `[]`. |
| `origin_agent` | string | no | Identity of the agent or workflow that created this AC file. Common values: `business-analyst`, `debug`, `human`, `ticket-wiring`. |
| `pattern_slots` | list of strings or null | no | Named placeholder slots in curly-brace notation (e.g. `{columns}`, `{default_sort}`) that consuming ACs must fill. Present only on ACs that act as shared-behavior patterns. Absent or null means this AC is not a pattern. |
| `implements_pattern` | string or null | no | AC ID of the pattern AC that this AC instantiates. Must reference an AC whose `pattern_slots` is non-empty. Set on consuming ACs; absent on pattern ACs. |
| `pattern_bindings` | mapping (string → string) or null | no | Maps each slot name (without curly braces) to its concrete value for this consuming AC. Every slot in the referenced pattern's `pattern_slots` must appear as a key. Only valid when `implements_pattern` is set. |

### Full example

```yaml
id: FIN-001
title: "Merge main before running tests"
component: finalize
status: active
created_by: "tickets/00_inbox/epics/EPIC-FinalizeFeatureHardening/01_merge_main.md"
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

---

## Pattern ACs — Shared Behavior Reuse

A **pattern AC** is an L2 AC whose `criteria` field contains named placeholders
in curly-brace notation (e.g. `{columns}`, `{default_sort}`). It defines a
single authoritative specification for a behavior that multiple pages, endpoints,
or components share. Each placeholder marks a **slot** that consuming ACs fill
with concrete values through `pattern_bindings`.

### Three fields involved

| Field | Set on | Value |
|---|---|---|
| `pattern_slots` | Pattern AC | List of slot strings, e.g. `["{columns}", "{default_sort}"]` |
| `implements_pattern` | Consuming AC | AC ID of the pattern, e.g. `ACS-500a-1` |
| `pattern_bindings` | Consuming AC | Mapping of slot name → concrete value |

### Single source of truth invariant

No two ACs in the store may contain an equivalent `criteria` body for the same
shared behavior. If a behavior recurs across multiple pages or endpoints, the
canonical definition lives in exactly one pattern AC. All consuming ACs reference
it via `implements_pattern` and supply concrete values via `pattern_bindings`.

### Pattern AC example

```yaml
id: ACS-500a-1
title: "Sortable table shared behavior pattern"
component: ac-store
level: L2
status: active
created_by: "tickets/00_inbox/epics/EPIC-PatternReuse/01_pattern_ac.md"
criteria: |
  Given a page contains a sortable table with columns {columns},
  When the user loads the page,
  Then the table is sorted by {default_sort} ascending by default,
  And each column header is clickable to toggle sort direction.
pattern_slots:
  - "{columns}"
  - "{default_sort}"
covered_by: []
implemented_by: []
origin_agent: BrainCandy
```

### Consuming AC example

```yaml
id: ACS-500a-2
title: "Invoice list page satisfies the sortable table pattern"
component: ac-store
level: L2
status: active
created_by: "tickets/00_inbox/epics/EPIC-PatternReuse/01_pattern_ac.md"
criteria: |
  Given the Invoice List page is open,
  When the user loads the page,
  Then the table is sorted by date ascending by default,
  And each column header (invoice_number, date, amount, status) is clickable
    to toggle sort direction.
implements_pattern: ACS-500a-1
pattern_bindings:
  columns: "invoice_number, date, amount, status"
  default_sort: "date"
covered_by: []
implemented_by: []
origin_agent: BrainCandy
```

### Authoring rules for pattern ACs

1. **Pattern ACs are L2 only.** L0/L1 ACs are composites; L3 ACs are too
   fine-grained. The pattern mechanism operates at the implementable-leaf level.
2. **Slot names must be valid identifiers.** Each `pattern_slots` entry must
   match `\{[a-zA-Z_][a-zA-Z0-9_]*\}`.
3. **All slots must be bound.** A consuming AC's `pattern_bindings` must contain
   a key for every slot declared in the pattern's `pattern_slots`. The schema
   validator (`check_ac_schema.py`) does not currently enforce binding
   completeness — authors and reviewers are responsible for this check.
4. **Pattern ACs remain standalone ACs.** A pattern AC satisfies its own
   acceptance criterion (the general-case behavior). Consuming ACs satisfy
   per-instance specializations. Both are independently reviewable and traceable.

---

## ID Format and Assignment

AC IDs follow the pattern `PREFIX-NNN`:

| Part | Rules |
|---|---|
| `PREFIX` | 2–6 uppercase ASCII letters. Derived from the component's `prefix` field in `docs/acceptance-criteria/index.yaml`. |
| `-` | Literal hyphen separator. |
| `NNN` | Three-digit zero-padded sequential integer. The first AC in a namespace is `001`; each subsequent AC increments by one. |

**Examples:** `FIN-001`, `AUTH-007`, `BP-042`.

**Assignment:** IDs are assigned at creation time and never reused. If an
AC is deprecated, its ID remains reserved so that historical references
(e.g. in commit messages or tickets) remain resolvable.

**Root-level regex:** `^[A-Z]{2,6}-[0-9]{3}$`

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
```

| Status | Meaning | Effect on hooks |
|---|---|---|
| `active` | Criterion is currently enforced. | `check_ac_coverage.py` requires at least one `covered_by` entry. |
| `deprecated` | Criterion is retired; retained for audit. | `check_ac_coverage.py` skips this AC. `check_test_ac_tags.py` emits a warning if any test still tags this AC. |
| `superseded_by` | Criterion was replaced by another AC. `superseded_by` field identifies the replacement. | Same as `deprecated` — excluded from active enforcement. |

**Transition rules:**

- `active` → `deprecated`: set `status: deprecated`. No other changes required.
- `active` → `superseded_by`: set `status: superseded_by` and `superseded_by: <new-ID>`.
- `deprecated` or `superseded_by` → re-activation is not supported. Create a new AC instead.

---

## Pre-Commit Hooks

Three hooks are installed by `build.py` to enforce the AC store at commit time.

### `check_ac_schema.py` (blocking)

Validates every YAML file under `docs/acceptance-criteria/` against
`config/ac_store_schema.json` (JSON Schema draft-07).

| Attribute | Value |
|---|---|
| Exit code | `1` on schema violation; `0` when all files pass. |
| Mode | Always blocking (`error` mode). |
| Invocation | `python check_ac_schema.py [file ...]` |

Validates: required fields present, `status` is one of the allowed enum
values, `id` matches the `PREFIX-NNN` regex, `superseded_by` is non-null
only when `status == superseded_by`.

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

---

## Agent Integration Points

### Authoring agents — parent covered_by update (mandatory)

Every requirement-authoring agent (`business-analyst-v3`, `product-owner-v3`,
`it-po-v3`) that writes a new child AC file MUST, in the same write batch,
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

### business-analyst-v3

The `business-analyst-v3` agent produces L2/L3 AC YAML files from L1 ACs.
When writing a new L2 or L3 file, it applies the parent covered_by update
protocol described above: the child's `depends_on` includes the parent ID,
and the parent's `covered_by` list is updated in the same write batch.

### product-owner-v3

The `product-owner-v3` agent produces L0 and L1 AC YAML files. When writing
a new L1 file (child of an L0), it applies the parent covered_by update
protocol: the L1's `depends_on` includes the L0 ID, and the L0's `covered_by`
list is updated to include the new L1 ID.

### it-po-v3

The `it-po-v3` agent enriches existing L2/L3 AC files. When it creates new
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
`docs/acceptance-criteria/<component-id>/.quick-fix-lock` before the scan
(step 2) and release it after the file is written. Use `O_CREAT | O_EXCL` for
lock acquisition. Release the lock unconditionally in all exit paths (success
and error).

If the lock cannot be acquired within 5 seconds, surface an error to the user:

```
Error: AC store for '<component-id>' is locked by another process.
Retry after the concurrent quick-fix completes, or manually remove
docs/acceptance-criteria/<component-id>/.quick-fix-lock if the process
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
- `docs/acceptance-criteria/README.md` — directory structure and quick-start.
- `config/ac_store_schema.json` — machine-readable JSON Schema (draft-07) for the AC YAML format.
- `docs/README.md` — full documentation index.
