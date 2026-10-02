---
title: "How to file approved decisions and reuse them as precedent"
description: "Publish the decision record a kernel run staged into docs/decisions/, review it as a normal git change, validate the store and the generated index, and see how a later run finds the record, judges whether it applies and asks you to reuse it or decide anew."
type: how-to
status: active
created: 2026-10-01
last_updated: 2026-10-01
components:
  - decision_kernel
related_docs:
  - docs/how-to/run-the-decision-kernel.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md
  - docs/architecture/components/decision-kernel.md
related_code:
  - kernel/memory/
  - kernel/adapters/cli.py
  - config/decision_record.schema.json
  - config/kernel_config.default.json
  - docs/decisions/
---

# How to file approved decisions and reuse them as precedent

A kernel run that ends with a decision **you** approved stages a record of it. You publish it with
one command, review it like any other change, and later runs offer it as precedent. The kernel
never writes into the repository during a run, and nothing a model wrote can become a record.

## Prerequisites

- The kernel is set up ([How to run the decision kernel](run-the-decision-kernel.md)).
- A run that ended `completed` with a decision you approved (a ranked choice you made, an
  approval you gave, or a reuse you confirmed). Decisions nobody approved leave no record.

## Steps

### Step 1 — Find the staged record

The completed run's envelope lists it under `limitations` (`decision record staged: <path>;
publish with: python -m kernel decisions publish --run-id <run id>`) and `report.md` shows it. It
sits in the run root, not in the repository:
`<run_root>/runs/<run id>/staged/decisions/<dec-id>.yaml`. Open it if you want to check it first.

### Step 2 — Publish it (explicit; never part of a run)

```bash
python -m kernel decisions publish --run-id <run id>
```

Publish validates the whole store and the staged record (schema, unique ids, resolvable links, a
human approver, filters from the existing vocabularies, plain YAML), then writes
`docs/decisions/<dec-id>.yaml` and regenerates `docs/decisions/index.json`. If anything is wrong
it writes nothing and lists the problems with exit code 3. Running it twice is harmless
(`already_present`). The `/leafcutter` skill may tell you a record is ready; it never runs this.

### Step 3 — Review and commit

The change is one new YAML file plus the index. Read the `approval` block (who, when), the
`options`, `assumptions` and `evidence` references, and the `provenance` (run, trace, repository
revision, versions); then commit it like any other change. Never hand-edit `index.json`.

### Step 4 — Validate at any time

```bash
python -m kernel decisions validate     # every record, the links, and that the index is current
python -m kernel decisions index        # regenerate the index (refuses while a record is invalid)
```

The same check runs in the test suite over the committed store (`tests/kernel/memory`) and in CI.
It exits 0 when the store is valid and 3 with the problems when it is not.

### Step 5 — See the precedent in the next run

When a decision starts, the kernel looks for records whose question matches (and, where the task
names them, whose components and roadmap phase match). Up to `memory.max_precedents` (3) go to Jev,
which answers one literal question per precedent: does this earlier decision apply to the current
question in its context?

- At `memory.applies_threshold` (0.5) the precedent becomes `prior_decisions` evidence, with its
  record path and approver, and appears in the report under "Precedent used".
- At `memory.reuse_threshold` (0.8), for a decision that has no options of its own yet, you are
  asked once: *"Decision dec-... (approved by human:you on 2026-10-01) chose ... for a matching
  question. Reuse it, or decide anew?"* Answer `reuse` or `decide_anew`. `reuse` resolves with the
  precedent's choice, **you** as approver, and stages a new record that cites it; `decide_anew`
  continues normally with the precedent kept as evidence. A superseded record is never offered.
- A precedent never resolves anything by itself, and it never changes routing or thresholds.

Set `memory.backend` to `null` in a config override to switch all of this off.

### Step 6 — Correct a record

Deciding anew against a precedent never edits the older record. If your new decision should
replace it, the staged record lists it under `supersedes`; publish it with an explicit correction:

```bash
python -m kernel decisions publish --run-id <run id> --correct <old dec-id> [--reason "why"]
```

That appends one correction (reason, time, approver, the original selected option, evidence ids
and assumptions) and a `superseded_by` link to the old record and changes nothing else.

## What a record holds

| Part | Fields |
|---|---|
| Identity | `id` (`dec-<16hex>`), `repository_id`, `kind`, `title`, `description` |
| The question | `question`, `decision_type`, `task_context`, `options`, `criteria` |
| Filters (existing vocabularies only) | `components`, `change_target`, `risk_surface`, `roadmap_phase`, `file_globs`, `repository_wide` |
| The answer | `selected_option_id`, `rationale`, `assumptions`, `assessment` (ranking, rank, confidence), `final_outcome` |
| Evidence | `evidence`: id, locator, category, content hash, source version (no text) |
| Authority | `approval` (`approved`, human approver, time), `precedents_considered`, `supersedes`, `superseded_by`, `related` |
| Provenance | run id, root task id, Langfuse trace id, repository revision, template, model and kernel versions |
| History | `corrections` (append-only) |

The filters sit at the top level so the stdlib knowledge-map parser reads each record's id, title
and component edges (through the existing `docs` surface in `config/paths.json`).

## Verification

```bash
python -m kernel decisions validate
```

Expected output: one JSON line `{"ok": true, "problems": [], "records": N}` and exit code 0.

## Troubleshooting

1. **Publish exits 3, "no staged decision record for this run".** The run did not end with a
   decision a human approved, or you named another run. Only `completed` runs with a human
   approval stage a record.
2. **Publish exits 3 naming a filter value.** A scope component or phase is not in
   `docs/components.json` or `docs/roadmap.json`. Fix the staged file or the task's scope.
3. **Validate says the index is out of date.** Run `python -m kernel decisions index` and commit.
4. **A precedent is not offered.** It scored below `memory.reuse_threshold`, the decision already
   had options, or a later record superseded it; it may still appear as evidence.

## See Also

- [How to run the decision kernel](run-the-decision-kernel.md)
- [ADR-059: Decision store](../architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md)
- [ADR-060: Source of truth and approval authority](../architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md)
- [ADR-061: Identity](../architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md)
- [Documentation Index](../INDEX.md)
