---
title: "KI-ACS-20261015-rule-check-without-before-state-demotes-approved — run by hand on a feature folder without a before-state, the requirement rule check rewrites every approved record to draft"
description: "medium — requirement_rule_check.py repairs records in place. Its readiness family takes a record missing from the before-state as created during the stage and resets an approved one to draft. With no --before-ref or --before-snapshot, every record is missing from the before-state. A hand run with --location and no --stage (or any non-approval stage) therefore silently demotes the whole folder's approved records in the working tree. Hit 2026-10-15: 46 ACD-2500 records."
type: reference
category: reference
status: active
created: '2026-10-15'
last_updated: '2026-10-15'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
  - docs/reference/requirement-rule-check.md
---

# KI-ACS-20261015-rule-check-without-before-state-demotes-approved — a hand run demotes approved records

> Filed 2026-10-15 after EPIC-RightJobRightAgent. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Nothing reaches the store unless the demotions are committed. But they
  sit in the working tree among real edits, the run prints no warning that it had no
  before-state, and a commit that sweeps them in takes approval away from buildable records.
- **Status:** open, no AC.
- **Occurrences:** 1 · **First seen:** 2026-10-15 · **Last seen:** 2026-10-15
- **Where:** `scripts/ac_store/requirement_rule_check.py` (`main()` builds `ctx.before` only
  from `--before-snapshot` or `--before-ref`) and `scripts/ac_store/_rc_readiness.py`
  (`evaluate_record`).

## What happens

1. Without `--before-snapshot` or `--before-ref`, `ctx.before` is unset, so
   `ctx.before_state(record)` reports every record as absent from the before-state.
2. The readiness family treats an absent record as "created during the stage". It restores
   an `approved` record to the authoring default `draft` and writes that repair to the file.
3. Only `--stage approval` is exempt. An empty `--stage` draws one "unrecognised --stage ''"
   warning, then the run demotes anyway.

`/plan-feature` always passes a before-state, so the workflow is not affected. The trap is the
standalone CLI, which the reference doc presents as a way to check a folder.

## Seen

While restoring four `expects_from` contracts after PR #1245, the check was run by hand as
`--location docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent` to confirm
nothing new was flagged. It rewrote `readiness: approved` to `draft` in 46 records, all done
and approved. The edits were caught in `git status` before any commit and discarded.

## Fix direction

- **Refuse to repair without a before-state.** With no `--before-ref` or `--before-snapshot`,
  report the readiness family as "not evaluated: no before-state" instead of repairing.
- **Or add a report-only mode** (`--no-repair`) and make it the default for hand runs.
- Either way, the reference doc should say a before-state is required for a repairing run.
