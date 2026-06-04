---
title: "Reference: AC Traceability Store Schema"
type: reference
status: active
created: 2026-06-04
last_updated: 2026-06-04
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

**Regex:** `^[A-Z]{2,6}-[0-9]{3}$`

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

### business-analyst

When authoring a ticket that introduces new functionality, the
`business-analyst` agent reads the ticket's acceptance criteria and, when
`origin_agent: business-analyst` ACs are requested, writes new AC YAML
files to `docs/acceptance-criteria/<component>/`.

**Key behaviour:** the agent validates the file against `check_ac_schema.py`
before finalising. If validation fails, the agent self-corrects the YAML.

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
