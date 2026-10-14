---
title: "Reference: AC Implementation-Readiness Hold Reasons and Assignment-Quality Check"
description: "Lookup reference for the single hold-reason list, the hold_reason record field and scan_ac_store flag behind the implementation-readiness gate, and the assignment-quality verdict, surface-to-craft map and CLI."
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-14
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
| `test design pending` | ACD-2500b-2 | Carried on the record's `hold_reason` field. |
| `reference file pending` | ACD-2500b-2 | Carried on the record's `hold_reason` field. |
| `file finding undecided` | ACD-2500b-2 | Carried on the record's `hold_reason` field. |

A record missing both of the first two is reported with both, in that order. A record
held for another listed reason is reported under that reason's own name, never folded
into the first two.

### `hold_reason` record field

| Field | Type | Required | Description |
|---|---|---|---|
| `hold_reason` | string | no | One value of the list above, set by its owner. The gate appends any non-empty string value unchanged after the two reasons it computes itself; it does not check the value against the list. |

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

## See Also

- [ac-schema.md](ac-schema.md) - parent AC schema reference.
- [ac-schema.md](ac-schema.md#the-declared_files-field) - the `declared_files` field behind `missing file targets`; [ac-declared-files.md](ac-declared-files.md) - how the generator uses it.
- [ADR-026](../architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md) - warn-before-required rollout.
- [requirement-rule-check.md](requirement-rule-check.md) - the `specialist versus surface` family of the requirement rule check applies this surface map.
