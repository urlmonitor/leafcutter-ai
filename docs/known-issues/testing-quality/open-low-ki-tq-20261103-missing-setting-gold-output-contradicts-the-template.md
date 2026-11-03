---
title: "KI-TQ-20261103-missing-setting-gold-output-contradicts-the-template — the recorded test-writer gold output for the missing-setting row writes no test, which the template forbids"
description: "low — scripts/evals/sets/test-writer/recorded/missing-setting-database-work/: the gold report says no test file was written and the database test was not run, while templates/agents/test-writer.md requires the test to be written and run red in setUp. The gold still passes, so the scorer is proven against an output the real agent never produces."
type: reference
category: reference
status: active
created: '2026-11-03'
last_updated: '2026-11-03'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/acceptance-criteria/testing-quality/TQ-200-per-agent-eval-coverage/TQ-200d-4-vi.yaml
---

# KI-TQ-20261103-missing-setting-gold-output-contradicts-the-template — the gold writes no test

> Filed 2026-11-03. Index: [testing-quality.md](../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** low. Nothing scores wrongly today; the gap is that `--score-gold` proves the
  `missing-setting-database-work` checks against an output shape the real agent does not produce.
- **Status:** open, no AC. Found by the IT-PO while enriching TQ-200d-4-vi (OQ-4vi-1); the user
  decided on 2026-11-03 to keep it out of that AC as a separate follow-up.
- **Occurrences:** 1 (code reading, 2026-11-02).
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `scripts/evals/sets/test-writer/recorded/missing-setting-database-work/report.md`
  (the row's `gold_output` in `scripts/evals/sets/test-writer.jsonl`, row 7).

## Symptom

The gold report reads: "The database test for the stored procedure refresh_totals() was not run,
and no test file was written that would guess a connection." It records no test file.

## Mechanism

`templates/agents/test-writer.md` requires the agent to write the requested test and verify it is
red (Step 4, "Required outcome: non-zero exit code (tests MUST be red)"). Both kept live re-runs of
2026-11-02 did that: they wrote the test, ran it, and reported a red run that stopped in `setUp`
before any connection. The gold output instead writes nothing, so a scorer change that misreads the
real shape (a red verification run next to a not-run statement) can still pass `--score-gold`.

## Fix direction

Re-record the gold from a kept live re-run output (test file plus report), with local paths
replaced by placeholders, after TQ-200d-4-vi lands; confirm `--score-gold` still passes all rows.
