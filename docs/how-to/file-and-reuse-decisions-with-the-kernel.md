---
title: "How to file approved decisions and reuse them as precedent"
description: "Publish the decision record a kernel run staged into docs/decisions/, review it as a normal git change, validate the store and the generated index, and see how a later run finds the record, judges whether it applies and asks you to reuse it or decide anew."
type: how-to
status: active
created: 2026-10-01
last_updated: 2026-10-10
components:
  - decision_kernel
related_docs:
  - docs/how-to/run-the-decision-kernel.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md
  - docs/architecture/components/decision-kernel.md
  - docs/reference/decision-record.md
  - docs/architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md
  - docs/architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md
  - docs/architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md
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
- A shell in the leafcutter-ai checkout; publishing and validating need no Jev key.

## Steps

### Step 1 — Find the staged record

The completed run's envelope lists it under `limitations` (`decision record staged: <staged
path>; publish writes it into <decisions folder> (the kernel checkout); publish it for review
with: <python> <repo>/scripts/run_kernel.py decisions publish --run-id <run id>`) and `report.md`
shows it. `<decisions folder>` is the configured `memory.decisions_dir` under the kernel
checkout (`docs/decisions` by default). The command runs as printed from any shell. It
sits in the run root, not in the repository:
`<run_root>/runs/<run id>/staged/decisions/<dec-id>.yaml`. Open it if you want to check it first.
How a run builds and stages the record is drawn in
[c3-026](../architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md).

### Step 2 — Publish it (explicit; never part of a run)

```bash
python -m kernel decisions publish --run-id <run id>
```

Before anything is written, publish checks, in this order:

1. the run id is a plain identifier, and the run staged at least one record;
2. the whole store in `docs/decisions/` is valid (schema, unique ids, resolvable links);
3. each staged record: schema, plain YAML, the file name is its id, a human approver, and every
   filter (`components`, `change_target`, `risk_surface`, `roadmap_phase`) is in the existing
   vocabularies;
4. no different record with the same id is already published, and the staged record's links resolve;
5. every `--correct` target is a record in the store that a staged record supersedes (Step 6).

If anything fails, publish writes nothing, prints the problems as JSON and exits 3 (Troubleshooting
lists each stop and its fix). If every check passes it writes two files: `docs/decisions/<dec-id>.yaml`
and the regenerated `docs/decisions/index.json`. It prints one JSON line with `ok`, `problems`,
`published`, `already_present`, `corrected` and `index_written`. Running it twice is harmless
(`already_present`). The `/leafcutter` skill may tell you a record is ready; it never runs this.
The sequence is drawn in
[c3-027](../architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md).

### Step 3 — Review and commit

The change is one new YAML file plus the index (and the older record too, when you used `--correct`).
Read the `approval` block (who, when), the `options`, `assumptions` and `evidence` references, and the
`provenance` (run, trace, repository revision, versions). Then commit those files on a branch and open
a pull request like any other change; the record counts as precedent once it is merged. Never
hand-edit `index.json`.

```bash
git add docs/decisions
git commit -m "Record decision <dec-id>"
```

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

A record you leave staged is never found as precedent. Lookup reads only the published store in
`docs/decisions/`, never the run root, so an unpublished record, or one still in review, does not
count until it is published and merged. The lifecycle is drawn in
[c3-028](../architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md).

Set `memory.backend` to `null` in a config override to switch all of this off.

### Step 6 — Correct a record

Deciding anew against a precedent never edits the older record. If your new decision should
replace it, the staged record lists it under `supersedes`; publish it with an explicit correction:

```bash
python -m kernel decisions publish --run-id <run id> --correct <old dec-id> [--reason "why"]
```

That appends one correction (reason, time, approver, the original selected option, evidence ids
and assumptions) and a `superseded_by` link to the old record and changes nothing else. The older
record is only appended to, never rewritten; without `--reason` the correction takes the note on the
precedent, or a sentence naming the approver and the run. `--correct` is explicit and never implied:
the old id must be in the store and a staged record must list it under `supersedes`, or publish
refuses (Troubleshooting 3).

## What a record holds

Every field of the record, with its type, default and meaning, is listed in [Decision record](../reference/decision-record.md).

The filters sit at the top level so the stdlib knowledge-map parser reads each record's id, title
and component edges (through the existing `docs` surface in `config/paths.json`).

## Verification

```bash
python -m kernel decisions validate
```

Expected output: one JSON line `{"ok": true, "problems": [], "records": N}` and exit code 0.

## Troubleshooting

1. **Publish exits 3, `no staged decision record for this run`.** The run did not end with a
   decision a human approved, or you named another run. Only `completed` runs with a human
   approval stage a record. Check the `--run-id` against the run's `limitations`; if the run
   staged nothing, run the decision again and approve it.
2. **Publish exits 3, `components value '<id>' is not in the existing vocabulary` (or
   `roadmap_phase value '<id>' is not in the existing vocabulary`).** A scope component or
   phase is not in `docs/components.json` or `docs/roadmap.json`. Fix the value in the staged file or
   the task's scope, then publish again. Nothing was written.
3. **Publish exits 3, `--correct names a record that is not in the store` or `no staged record
   supersedes it; a correction is applied only for a record that does`.** Check the old id, and that
   the staged record lists it under `supersedes`. Drop `--correct` if you did not mean to correct it.
4. **Validate says the index is out of date.** Run `python -m kernel decisions index` and commit.
5. **A precedent is not offered.** It scored below `memory.reuse_threshold`, the decision already
   had options, it was never published, or a later record superseded it; it may still appear as
   evidence.

## See Also

- [How to run the decision kernel](run-the-decision-kernel.md)
- [Reference: Decision record](../reference/decision-record.md)
- [c3-026: staging a record](../architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md), [c3-027: publishing](../architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md), [c3-028: record lifecycle](../architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md)
- [ADR-059: Decision store](../architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md)
- [ADR-060: Source of truth and approval authority](../architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md)
- [ADR-061: Identity](../architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md)
- [Documentation Index](../INDEX.md)
