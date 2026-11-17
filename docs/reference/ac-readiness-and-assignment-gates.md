---
title: "Reference: AC Implementation-Readiness Hold Reasons and Assignment-Quality Check"
description: "Lookup reference for the single hold-reason list, the hold_reason record field and scan_ac_store flag behind the implementation-readiness gate, and the assignment-quality verdict, surface-to-craft map and CLI."
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-21
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/ac-schema.md
  - docs/reference/ac-declared-files.md
  - docs/architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md
  - config/surface_craft_map.yaml
  - scripts/ac_store/_impl_readiness_gate.py
  - scripts/ac_store/assignment_quality.py
  - scripts/ac_store/approve_acs.py
---

# AC Readiness and Assignment Gates

> **Parent document:** [ac-schema.md](ac-schema.md)

Two pre-dispatch checks on an AC record: the implementation-readiness gate (is the
record complete enough to build) and the assignment-quality check (does `assigned_agent`
own the deliverable surface). Both ship advisory under
[ADR-026](../architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md) rules 3-4.

---

## Hold reasons

`HOLD_REASONS` in `scripts/ac_store/_impl_readiness_gate.py` is the single hold-reason
list. This table mirrors it; there is no second list.

| Reason | Owner | Raised when |
|---|---|---|
| `missing file targets` | ACD-1600c-1 | The record is in the "no declared files" state ([declared_files](ac-schema.md#the-declared_files-field)). `it_requirements`, `doc_links` and `reference_file_path` neither raise nor clear it. |
| `missing test contract` | ACD-1600c-1 | The record has neither a non-empty `test_spec` nor `test_required: false`. |
| `test design pending` | ACD-2500b-2 | Computed, always held (whatever `--enforce-impl-readiness` and `schema_version` say): the record has a non-empty `test_intent` and no `test_spec`. Reported instead of `missing test contract`. Four points hold it: approval (`approve_acs.py`), this gate, the ticket generator and the commit check; see [test-intent.md](test-intent.md#intent-with-no-design-cannot-be-approved-or-built). |
| `reference file pending` | ACD-2500d-2-i | Set by the technical planner and cleared by the test-designer; carried on the record's `hold_reason` field: an object-form `it_requirements` has no `reference_file_path` and `hold_reason` is this value. The marker is explicit; a missing key alone is refused. Held at approval (`approve_acs.py`), after `test design pending`. |
| `file finding undecided` | ACD-2500b-2 | Computed from the record's `file_findings`, never carried on `hold_reason`. |

A record missing both of the first two is reported with both, in that order. A record
held for another listed reason is reported under that reason's own name, never folded
into the first two.

### `hold_reason` record field

| Field | Type | Required | Description |
|---|---|---|---|
| `hold_reason` | string | no | One value of the list above, set by its owner (the planner sets only `reference file pending`). The vocabulary is closed: a non-empty value outside `HOLD_REASONS` raises `ValueError`, in the gate and in `_approval_holds`. A listed value is appended unchanged after the reasons the gate computes itself. |

### Advisory versus held

| Condition | Reported | Held back from dispatch |
|---|---|---|
| Default (advisory), `schema_version` < 2 or absent (absent reads as 1) | yes | no |
| Default (advisory), `schema_version` >= 2 | yes | yes |
| `--enforce-impl-readiness` | yes | yes, for every flagged record |

`--enforce-impl-readiness` is a flag of `scripts/ac_store/scan_ac_store.py`, off by default.
The gate runs over the approved, dependency-ready leaf ACs. It is distinct from the
approval-readiness gate (ACD-1200b), which checks `readiness`.

Report: with `--json`, `scan_ac_store.py` adds a `not_implementation_ready` key (empty list
when none): one `{"ac_id", "reasons", "held_back"}` object per flagged record, held or not.
Held records are absent from `ready`.

```json
{"not_implementation_ready": [{"ac_id": "ACD-1", "reasons": ["missing file targets"], "held_back": false}]}
```

---

## Assignment-quality verdict

`scripts/ac_store/assignment_quality.py` returns one verdict per AC.

| Field | Type | Description |
|---|---|---|
| `ac_id` | string | The AC id, echoed. |
| `surface` | string | The deliverable surface (file path), echoed. |
| `resolved_craft` | string or null | Craft of the first matching map entry; null when none matches. |
| `assigned_agent` | string | The record's `assigned_agent`, echoed. |
| `verdict` | enum | `match`, `mismatch` or `unresolved`. |
| `held` | boolean | True exactly when `verdict` is `mismatch` (marks the AC for reassignment). |

| `verdict` | When |
|---|---|
| `match` | `resolved_craft` equals `assigned_agent`. |
| `mismatch` | A craft resolved and differs from `assigned_agent`. The only flagged case. |
| `unresolved` | No glob matched. Explicit advisory outcome: not a pass, not a mismatch, not held. |

### `config/surface_craft_map.yaml`

An `entries` list of `{glob, craft}`, evaluated in file order; the first match wins. It is
the single source of truth; no rule is duplicated in code. Matching is path-aware,
case-insensitive, with `\` read as `/` and a leading `./` stripped. `**/` spans zero or more
directories, `*` stays within one segment, `?` is one non-separator character.

| Order | Glob | Craft |
|---|---|---|
| 1-2 | `templates/workflows-js/**/*.js`, `templates/workflows-js/**/*.mjs` | `python-coder` |
| 3-6 | `templates/agents/*.md`, `templates/skills/**/SKILL.md`, `templates/commands/**/*.md`, `templates/workflows/**/*.md` | `llm-expert` |
| 7-10 | `**/*.jsx`, `**/*.tsx`, `**/*.vue`, `**/*.svelte` | `frontend-coder` |
| 11-19 | `web/**/*` `.js` `.mjs` `.ts` `.css` `.html`; `frontend/**/*` `.js` `.ts` `.css` `.html` | `frontend-coder` |
| 20 | `**/*.sql` | `sql-coder` |
| 21 | `**/*.py` | `python-coder` |

The workflow-body entries precede any web entry, so a `templates/workflows-js/` body
assigned to `python-coder` matches. A `.jsx` or `.sql` deliverable assigned to `python-coder`
is a mismatch. The file may be a bare list or `{entries: [...]}`.

### Split payload

Two or more surfaces produce a split payload instead of a verdict.

| Field | Type | Description |
|---|---|---|
| `ac_id` | string | The AC id, echoed. |
| `assigned_agent` | string | Echoed. |
| `surfaces` | list | One `{surface, craft}` per input surface, in input order; `craft` is null when unresolved. |
| `split_required` | boolean | True when more than one distinct craft resolved. Unresolved surfaces do not count as a craft. |
| `held` | boolean | Equal to `split_required`. |

### CLI

```bash
python scripts/ac_store/assignment_quality.py --ac-id ACD-1 --surface web/app/main.js --assigned-agent python-coder
python scripts/ac_store/assignment_quality.py --ac-id ACD-2 --surface a.py --surface b.sql --assigned-agent python-coder
```

| Argument | Required | Description |
|---|---|---|
| `--ac-id` | yes | AC id. |
| `--surface` | yes, repeatable | Deliverable path. One occurrence yields the verdict; two or more yield the split payload. |
| `--assigned-agent` | yes | Agent the AC is assigned to. |
| `--map` | no | Alternate map file; default `config/surface_craft_map.yaml`. |

Prints one JSON object and always exits 0 (advisory rollout, ADR-026). An unreadable map is
logged to stderr and raises. The script deploys to `<root>/scripts/ac_store/` and the map to
`<root>/config/` (`AC_STORE_DEPLOY_MAP`, `scripts/build_phases_ac_store.py`).

---

## `approve_acs.py` CLI

`scripts/ac_store/approve_acs.py` is the store's one approval step: a person runs it by hand,
and the `/plan-feature` final gate runs its deployed copy (`.leafcutter/scripts/ac_store/`,
`RULE_CHECK_DEPLOY_MAP`, `scripts/build_phases_ac_store_rc.py`). It promotes records from
`readiness: reviewed` to `approved` and never writes a record that `approval_hold_reason` holds.

```bash
python scripts/ac_store/approve_acs.py --goal ACD-1200 --json
python scripts/ac_store/approve_acs.py --ac ACD-1200a-1
python scripts/ac_store/approve_acs.py --ids ACD-1-1,ACD-1-2 --dry-run --json
python scripts/ac_store/approve_acs.py --ids ACD-1-1,ACD-1-2 --priority high --json
```

| Argument | Description |
|---|---|
| `--goal GOAL_AC_ID` | Promote every reviewed leaf in the goal's `covered_by`. |
| `--ac AC_ID` | Promote one record. |
| `--ids ID,ID` | Approve exactly these records, each under its own id at any level; an id is never expanded to its children. Every id must be a plain id (no glob characters) and exist, its file's `id:` equal to it, before anything is written. A record that is not held is approved whatever its readiness (`draft`, or no `readiness` line, which is inserted); holds are checked first. |
| `--priority P` | `critical`, `high`, `medium` or `low`, written with the approval (the `priority` line is inserted when the record has none). Required with `--ids` unless `--dry-run`; refused with `--goal`. |
| `--ac-root DIR` | Store root to search; default `docs/acceptance-criteria/`. |
| `--dry-run` | Write nothing. With `--json`, `approved` lists the ids that would be approved. |
| `--json` | Print the report on stdout. |

The report is `{"approved": [id], "held": [{id, file, reason}]}`; with `--ids` it also carries
`already_approved: [id]` and `failed: [id]` (records whose write failed read-back). A record already at `approved` is listed there and not written, so
running the same approval twice changes nothing and exits 0.

In one write per record the step changes the `readiness` line, the `priority` line (when
`--priority` is given) and appends exactly one `amended_by` entry (`action: approved`,
`agent: approve_acs`, the date) after the entries already there. Every earlier byte of the
record, including folded multi-line `amended_by` notes, is preserved, and the file keeps its own
line endings. The file is then read back; if it does not parse, or does not read back approved
with the earlier entries intact and the new entry last, the record is restored byte for byte, stderr
names the file and the reason, and the id is listed in `failed`. The run goes on through the other
ids, then exits 1 (records approved in the run stay approved).
Exit codes: 0 success, hold or no-op; 1 not found, unreadable or failed read-back; 2 unexpected
readiness.

---

## See Also

- [ac-schema.md](ac-schema.md) - parent AC schema reference.
- [ac-schema.md](ac-schema.md#the-declared_files-field) - the `declared_files` field behind `missing file targets`; [ac-declared-files.md](ac-declared-files.md) - how the generator uses it.
- [ADR-026](../architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md) - warn-before-required rollout.
- [requirement-rule-check.md](requirement-rule-check.md) - the `specialist versus surface` family of the requirement rule check applies this surface map.
