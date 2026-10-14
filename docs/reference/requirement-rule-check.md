---
title: "Reference: Requirement Rule Check"
description: "Lookup reference for the requirement rule check CLI, its JSON report, dispositions, rule families, fail-closed paths, /plan-feature use and family registration."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/ac-schema.md
  - docs/reference/ac-readiness-and-assignment-gates.md
  - docs/reference/ac-declared-files.md
  - docs/reference/ac-id-hierarchy.md
  - docs/reference/code-aware-step.md
  - docs/architecture/components/ac-driven-dev.md
  - docs/architecture/diagrams/c3-030-requirement-rule-check-components.md
  - scripts/ac_store/requirement_rule_check.py
---

# Requirement Rule Check

The CLI, JSON report, dispositions and rule families of `requirement_rule_check.py`, the script that decides whether a `/plan-feature` authoring stage is complete.

The check reads a set of requirement records, repairs three one-right-answer violations, and prints one JSON report. `/plan-feature` reads the exit status and that report, never a stage agent's prose. Field rules for the records themselves are in [ac-schema.md](ac-schema.md) and are not repeated here.

---

## Overview

| Item | Value |
|---|---|
| Script | `scripts/ac_store/requirement_rule_check.py` (deployed to `<root>/scripts/ac_store/`, with the `_rc_*.py` modules, flat) |
| Output | One JSON document on stdout; logging goes to stderr |
| Exit codes | `0` passed, `1` failed, `2` usage error |
| Rule families | 9 rule families plus the pass-through `record schema` and `record readable` |
| Writer | `_rc_edit.py` only; it may write `covered_by`, `components` and `readiness` |

---

## CLI

```bash
python scripts/ac_store/requirement_rule_check.py --stage ba --changed-since HEAD --before-ref HEAD
python scripts/ac_store/requirement_rule_check.py --stage itpo --location docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent --before-snapshot before.json
python scripts/ac_store/requirement_rule_check.py --stage approval --for-ids ACD-2500a-1,ACD-2500a-2
```

One of `--changed-since`, `--location` or `--for-ids` is needed; with none the script prints a usage line and exits `2`.

| Flag | Value | Description |
|---|---|---|
| `--changed-since` | git REV | Check every record file under the store that is modified, added or untracked against REV. The mode `/plan-feature` uses. Adds `records_to_commit` to the report. |
| `--location` | folder | Check every record file under that folder (absolute, or repo-root relative). |
| `--for-ids` | `ID,ID,...` | Check the deepest common folder of those records. An id absent from the store, or outside that folder, is a `failed` finding. |
| `--stage` | `po`, `ba`, `itpo`, `test-design`, `approval` | The authoring stage that just ended. An unknown or missing stage is a `failed` finding, not a usage error. |
| `--before-ref` | git REV | Revision that holds each record's readiness before the stage. |
| `--before-snapshot` | JSON file | `{id: readiness or null}`; the before-state without git. Wins over `--before-ref`. |
| `--store-root` | folder | Default `<repo-root>/docs/acceptance-criteria`. |
| `--repo-root` | folder | Default: nearest ancestor of the location that holds `docs/acceptance-criteria`. |
| `--schema` | file | Override `config/ac_store_schema.json`. |
| `--components-registry` | file | Override `docs/components.json`. |
| `--surface-map` | file | Override `config/surface_craft_map.yaml`. |
| `--migration-map` | JSON or YAML file | Override the namespace-to-graph-component-ids map used by `non-empty graph component list`. |

Every stage except `approval` needs a before-state (`--before-ref` or `--before-snapshot`); without one the run is `failed`.

---

## Report

```json
{
  "verdict": "failed",
  "location": "docs/acceptance-criteria/x/y",
  "records_checked": 3,
  "findings": [
    {
      "file": "docs/acceptance-criteria/x/y/X-1-i.yaml",
      "record_id": "X-1-i",
      "rule_family": "producer/consumer contract symmetry",
      "disposition": "needs a decision",
      "message": "X-1-i delivers to python-coder, but no python-coder record in the checked folder expects from X-1-i",
      "line": null,
      "detail": null
    }
  ],
  "family_counts": {"producer/consumer contract symmetry": {"evaluated": 3, "not_evaluated": 0}},
  "records_to_commit": ["docs/acceptance-criteria/x/y/X-1-i.yaml"]
}
```

| Key | Type | Description |
|---|---|---|
| `verdict` | `"passed"` or `"failed"` | `passed` only when `records_checked` is above 0 and no final finding is `needs a decision` or `failed`. Exit `0` iff `passed`. |
| `location` | string | The location as given, repo-root-relative POSIX; the comma-joined ids for `--for-ids`; the REV for `--changed-since`. |
| `records_checked` | int | Record files seen, readable or not. |
| `findings` | list | See the finding format below. |
| `family_counts` | object | Additive. Per family name: `{evaluated, not_evaluated}`, the records given to the family and the records it declined to judge. |
| `records_to_commit` | list of strings | Additive; only with `--changed-since`. Sorted repo-relative POSIX paths of every record file changed against REV after the run, repaired parents included. `[]` on a git failure. |

Consumers must ignore keys they do not know. Output is deterministic: sorted keys, ASCII, no timestamps or absolute paths.

### Finding format

Each finding states **file, record id, rule family, disposition**, plus `message`, `line` and `detail`.

| Field | Type | Description |
|---|---|---|
| `file` | string | Repo-root-relative POSIX path. For run-level failures (ids, git, scope) it is the location string. |
| `record_id` | string or null | Null only when the file could not be read or the finding is about the run (git, ids, rule source). |
| `rule_family` | string | Exact name string from the rule family table. |
| `disposition` | enum | One of the four dispositions. |
| `message` | string | Human-readable cause. |
| `line` | int or null | Set for an unreadable YAML file when known. |
| `detail` | object or null | Structured data such as `{path, specialist, assigned_agent}`. |

Findings are sorted by file, rule family, subject, record id, message. There is at most one finding per (file, record id, rule family, subject); when two share that key the highest disposition wins (`failed` over `needs a decision` over `fixed` over `not evaluated`).

---

## Dispositions

| Disposition | Meaning | Fails the verdict |
|---|---|---|
| `fixed` | The check repaired the record itself; the finding records what changed. | No |
| `needs a decision` | A person must choose; the record is not rewritten. | Yes |
| `failed` | The check could not judge (see Fail-closed paths) or a repair did not stick. | Yes |
| `not evaluated` | The family could not judge this record (for example no declared files). Counted in `family_counts`. | No, never |

---

## Rule families

Ten rule families, evaluated in the order listed after `record schema`. Only families 1, 2 and 4 repair. Every repair goes through `_rc_edit`, which refuses any field outside `{covered_by, components, readiness}` (`ProtectedFieldError`), and writes only after proving that the old and new YAML differ in the target key alone.

| # | Family name (exact string) | Dispositions it produces | Repairable field |
|---|---|---|---|
| 1 | `parent-to-child back-links` | `fixed`, `needs a decision` | `covered_by` |
| 2 | `non-empty graph component list` | `fixed`, `needs a decision` | `components` |
| 3 | `producer/consumer contract symmetry` | `needs a decision` | none |
| 4 | `readiness never raised to approved by an authoring agent` | `fixed` | `readiness` |
| 5 | `documentation trigger to documentation requirement mapping` | `needs a decision`, `failed` | none |
| 6 | `specialist versus surface` | `needs a decision`, `not evaluated`, `failed` | none |
| 7 | `declared files versus modifies links` | `needs a decision`, `not evaluated` | none |
| 8 | `test intent coverage` | `needs a decision` | none |
| 9 | `test design grounding` | `needs a decision`, `not evaluated` | none |
| 10 | `file findings consistency` | `needs a decision` | none |
| - | `record schema` (pass-through) | `needs a decision`, `failed` | none |
| - | `record readable` (pass-through) | `failed` | none |

### 1. parent-to-child back-links

Every child id must be in its parent's `covered_by`. The parent id comes from `derive_parent_id` ([ac-id-hierarchy.md](ac-id-hierarchy.md)) and is looked up in the checked folder (in `--changed-since` mode also in the store).

- Parent present, child missing: `fixed`; appends the child to the parent's `covered_by`. The finding names the parent's file and id.
- Parent absent: `needs a decision` on the child. The check never creates a record.
- Parent's `covered_by` is not a list: `needs a decision`.

### 2. non-empty graph component list

`component` is the kebab namespace (`ac-driven-dev`); `components` holds graph ids (`ac_driven_dev`).

- `components` empty or missing and the namespace maps to exactly one graph id that is in the registry: `fixed`; sets `components` to that id.
- Empty and zero or several candidates, or the single candidate is not in the registry: `needs a decision`.
- Non-empty but invalid (for example an id not in `docs/components.json`): `needs a decision`, never rewritten.

### 3. producer/consumer contract symmetry

Presence only. `expects_from` and `delivers_to` may each be null, a string, an object or a list.

- A record expects a contract from an id that does not exist in the store, or whose record declares no `delivers_to`: `needs a decision`.
- A record delivers to an agent, but no record in the checked folder is assigned that agent and names this record in its `expects_from`: `needs a decision`.

The check never adds, removes or compares contract text. Judging whether two contract descriptions agree stays with the technical planner.

### 4. readiness never raised to approved by an authoring agent

A record that ends the stage `approved` but was not `approved` in the before-state is restored: `fixed`; sets `readiness` to the before value, or to `draft` when the record had none or did not exist. Unchanged records, and every record under `--stage approval`, are left alone; the exemption is by stage identity, not by inspecting values.

### 5. documentation trigger to documentation requirement mapping

Applies to `L1` records whose `documentation_triggers` is a list. The trigger-to-specialist map lives in `_rc_doc_triggers.py`:

| Trigger | Specialist |
|---|---|
| `how-to`, `reference-doc` | `documentation-expert` |
| `sequence-diagram`, `state-diagram`, `component-diagram` | `architecture-diagram-author` |

**Coverage is counted per specialist.** A trigger is covered when any record in the checked folder, other than the L1 declaring it, has `assigned_agent` equal to the trigger's specialist. One `documentation-expert` record therefore covers both `how-to` and `reference-doc`.

- Uncovered trigger: `needs a decision`, one per trigger.
- `documentation_triggers: []` with no `documentation_rationale`: `needs a decision`. An absent or null key (legacy L1) is not reported.
- A trigger missing from the map: `failed`.

### 6. specialist versus surface

Each declared file path ([ac-declared-files.md](ac-declared-files.md)) is resolved to a craft through the surface map ([ac-readiness-and-assignment-gates.md](ac-readiness-and-assignment-gates.md)). A path whose craft differs from `assigned_agent`: `needs a decision`, one per path, with `detail {path, specialist, assigned_agent}`. No declared files, no `assigned_agent` or a path with no map entry: `not evaluated`. An unreadable map: `failed`.

### 7. declared files versus modifies links

Every `doc_links` entry whose relationship is `modifies` must also be a declared file. Each one that is not: `needs a decision`, one per path. No declared files: `not evaluated`.

### 8. test intent coverage

Judges coverage of `test_intent` ([test-intent.md](test-intent.md)) against the outcome clauses of `criteria`; the entry shape is the `record schema` family's job. Only a record whose `test_intent` is a non-empty list is evaluated; a record with only a `test_spec`, or with neither, is never judged. Nothing is repaired.

| `detail.kind` | Reported when |
|---|---|
| `missing` | An outcome clause has no entry. |
| `stale` | An entry names a clause that is no longer in `criteria`. |
| `duplicate` | A clause has more than one entry. |

Each finding is `needs a decision`, one per clause, with `detail {kind, clause}` and no line. Clauses and entry texts are compared under `normalise_clause`. A failing `itpo` stage goes back to the IT PO.

### 9. test design grounding

Judges a code-aware design: a record with a non-empty `test_spec` and the authorship mark. Each finding is `needs a decision` with `detail {kind, entry, path}`, `entry` being the `test_spec` entry `name`: `absent` (the `code_file` is neither in the tree nor declared `to_be_created`; the flag alone never grounds it), `not-grounded` (`test_design_opened_files` empty or missing; no `entry`/`path`), `no-clause`, `dangling-clause`, `missing-dir`, `missing-convention`, `no-reachability` (no entry with `angle` reachability; judged unless `test_required` is false or a present `change_target` omits `code`), and `unmarked-design` (a markless `test_spec` on a record with `test_intent`; one without `test_intent` is legacy and exempt). A `to_be_created` entry on a record with no declared files is `not evaluated: no declared files`.

### 10. file findings consistency

Judges a record whose `file_findings` is a list (an absent field means the file-aware step has not run). Each finding is `needs a decision` with `detail {kind, path}`: `missing` (a declared file has no finding; a declared `to_be_created` file not yet in the tree is exempt), `undeclared` (a finding for a file that is neither declared nor the record's `it_requirements.reference_file_path`), `tree-absent` / `tree-present` (the verdict contradicts the tree for a declared file), `line_range` / `found_in` / `found_in_null` (a verdict missing its companion field, or `found_in` set on another verdict) and `unopened` (a verdict on an existing file not in `file_findings_opened_files`). An undecided finding is NOT reported: it is the approval hold `file finding undecided` (`_file_findings.undecided_findings`).

### Pass-through families

| Family | Behaviour |
|---|---|
| `record schema` | Calls the store's record check (`validate_ac_schema._validate_file`) with the check's schema and registry, and reports at most one `needs a decision` per violated subject. The `components` subject is reported by family 2 instead. Known gap: checks that only the commit hook runs (test contract, side effect, pattern bindings) are not repeated here. |
| `record readable` | `failed` for a file that cannot be read, and for run-level problems: empty scope, git failure, bad ids. |

### Which store check owns a shared rule

| Rule | Owner |
|---|---|
| Record shape, required fields, enums, the `components` rule | `validate_ac_schema._validate_file`, enforced at commit by the `check_ac_schema` hook. This check calls it and reports each violation once. |
| Parent back-link | `check_ac_parent_covered_by` (commit hook). Family 1 applies the same rule earlier and also repairs it. |
| Surface-to-craft map | `assignment_quality.resolve_craft_in`; family 6 reads it, with no second file-type table. |
| Declared files | `declared_files.get_declared_files`; families 6 and 7 read it. |
| Protected fields (`criteria`, `title`, `req_status`, `depends_on`) | `check_ac_governance`; this check's writer cannot reach them. |
| Families 3, 4, 5 and 7 | This check alone; no existing store check enforces them. |

---

## Fail-closed paths

Every inconclusive path is a `failed` finding and so verdict `failed`; none is a silent pass.

| Path | Finding family | Notes |
|---|---|---|
| Zero records checked | `record readable` | `no requirement records found at ...` or `... changed since REV`; `record_id` null. |
| Unreadable record (YAML error, bad encoding, no top-level `id`) | `record readable` | Names the file and, for YAML errors, the line. The file still counts in `records_checked`. |
| A rule family raises, or returns a non-`Finding` | the family's name | Scoped to that record and family; the run continues. |
| Unreadable schema, registry, surface map or migration map | `record schema` (family 6 for the surface map) | `rule source unreadable: ...`. |
| Missing before-state on an authoring stage, or unknown `--stage` | `readiness never raised to approved by an authoring agent` | |
| Git failure listing changed files, nothing changed, or ids absent or outside the folder | `record readable` | |
| A repair refused by `_rc_edit`, unprovable, or still violated after the second pass | the repairing family | `repair of ... was not applied` or `still violated after the repair pass`. |
| A repaired record that no longer reads | `record readable` | |

---

## How /plan-feature uses it

`runRuleCheck(stage, ...)` in `plan-feature.js` runs, after each authoring stage:

```bash
python .leafcutter/scripts/ac_store/requirement_rule_check.py --stage <stage> --changed-since HEAD --store-root <ac-store> --repo-root <worktree> --before-ref HEAD
```

1. **Stage-end check.** It runs through a shell-permitted agent under the label `rule-check-<stage>`, after the stage agent finishes and before the user gate. The stages are `po`, `ba`, `itpo` and `test-design`.
2. **Fail-closed reading.** The check passes only if the exit code is `0`, `verdict` is `passed` and `records_checked` is above 0. A dispatch error, an unreadable reply, or an exit code and verdict that disagree is a failed check.
3. **Gate behaviour on failure.** The summary (each finding's file, family and message) goes into the gate prompt. If the user chose `approve`, the action becomes `edit` and the findings are fed back to the stage agent as feedback; `cancel` still cancels. After the edit-retry limit the pipeline returns `status: "error"` with the failed report in `failed_check`.
4. **Committing records.** On approval the stage commit stages `records_to_commit` in addition to the stage's own ACs, so a parent repaired by the check is committed.

---

## How a new family registers

1. Add `scripts/ac_store/_rc_<name>.py` exposing `NAME` (a string constant from `_rc_report`) and a pure `evaluate_record(ctx, record) -> list[Finding]`. Optional `CLAIMS_SUBJECTS = ("components",)` takes a subject over from `record schema`.
2. In `requirement_rule_check.py`, `import _rc_<name>` and append it to `FAMILIES` (order is evaluation order); add the module to `AC_STORE_DEPLOY_MAP` in `scripts/build_phases_ac_store_rc.py`.
3. Build findings with `Finding.for_record(record, NAME, disposition, message, subject=..., line=..., detail=...)`. A repairing family returns a `fixed` finding with `repair=(field, ("set", value))` or `("append", item)` for the record the change lands on; the field must be in `{covered_by, components, readiness}`.

`evaluate_record` never writes. The orchestrator applies repairs in two passes: evaluate, repair, reload the written records, evaluate again.

---

## See Also

- [ac-schema.md](ac-schema.md) - field rules for the records the check reads.
- [ac-readiness-and-assignment-gates.md](ac-readiness-and-assignment-gates.md) - surface map and assignment-quality check used by family 6.
- [ac-declared-files.md](ac-declared-files.md) - the declared-files seam used by families 6 and 7.
- [ac-id-hierarchy.md](ac-id-hierarchy.md) - parent derivation used by family 1.
- [c3-030 requirement rule check components](../architecture/diagrams/c3-030-requirement-rule-check-components.md) - component diagram.
- [ADR-026](../architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md) - phased rollout of the AC-driven build.
