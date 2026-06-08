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

---

## See Also

- `docs/how-to/ac-traceability-store.md` — task-oriented guide for creating, amending, and deprecating ACs.
- `docs/acceptance-criteria/README.md` — directory structure and quick-start.
- `config/ac_store_schema.json` — machine-readable JSON Schema (draft-07) for the AC YAML format.
- `docs/README.md` — full documentation index.
