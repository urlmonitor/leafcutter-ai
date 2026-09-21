---
title: "KI-TQ-009 — A test-local oracle that duplicated the production bug it was written to detect"
description: "medium as a pattern, even where the instance is fixed"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-009 — A test-local oracle that duplicated the production bug it was written to detect

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium as a pattern, even where the instance is fixed
- **Status:** open as a pattern — **the instance is NOT on `main`** (PR #495's
  `test_ge_122e_3.py`) and is fixed on the branch; the pattern has no enforcement anywhere
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `test_ge_122e_3.py` (`_read_lifecycle_folder_names`) against its
  `_work_items_scanner.py`

**Symptom.** The test file defined its own local `_read_lifecycle_folder_names` helper carrying
the **identical basename-collapse defect** as the production function it was verifying. The exit
gate's oracle shared the blind spot of the code it was written to check.

It passed for exactly the reason the production bug was invisible: every real lifecycle folder
happens to sit one level under `tickets/`.

**Why this is a class, not an incident.** This is the same bias that once let a `files_touched`
parser defect survive an entire epic in this repository — synthetic fixtures and hand-written
oracles reproduce the implementation's assumptions, so they cannot falsify them. It is also
`KI-TQ-006` in miniature: a check authored from the same mental template as the thing it checks.
The branch committed it *inside the entry describing the fix for it*, which is the sharpest
available demonstration that knowing about the pattern does not prevent it.

**Detection.** When a test computes an expected value, ask whether it derives that value
**independently** or re-implements the logic under test. An oracle that mirrors the
implementation proves only self-consistency.

**Fix direction (pattern, not instance).** Derive oracles from the data, not from a
reimplementation — read the config's full declared paths rather than recomputing folder
discovery. Where a helper must be shared between a test and production code, **import the
production one**, so a bug shows up as a failure rather than as agreement.

---
