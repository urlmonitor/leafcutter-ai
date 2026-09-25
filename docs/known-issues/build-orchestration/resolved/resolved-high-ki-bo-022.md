---
title: "KI-BO-022 — A CRLF acceptance-criterion record is rewritten LF end-to-end by a single `work_status` flip, and every value-level check still passes"
description: "KI-BO-022 — A CRLF acceptance-criterion record is rewritten LF end-to-end by a single `work_status` flip, and every value-level check still passes"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-022 — A CRLF acceptance-criterion record is rewritten LF end-to-end by a single `work_status` flip, and every value-level check still passes

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Renumbered 2026-08-25 from KI-BO-019.** PR #538 landed its own KI-BO-019 at 14:51 UTC;
> PR #539 landed this one at 15:09 UTC and the two collided on `main`. #538 was first, so
> it keeps the number and this entry moves. See KI-BO-024.

- **Severity:** high
- **Status:** **RESOLVED** (`f1726aef`, PR #602; verified 2026-09-25 by `test_bo2400e_4_crlf_preservation.py` (3 passed) and a CRLF probe on the real `BO-2400a-3-i.yaml`: 1 changed line, 0 bare LF). Scope was the fast-lane writer only; the same LF rewrite in other AC-store writers is tracked separately (see Resolution).
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where (as filed; code has since moved to `scripts/build_orchestration/_fl_lifecycle.py`):** `scripts/build_orchestration/fast_lane.py:169-171` (read) and `:205-207` (write), function `_update_ac_work_status`; reached from all three call sites (`:288`, `:346`, `:461`)

**Symptom.** Both the read and the write use text mode with default newline handling. The
read collapses `\r\n` to `\n`; the write emits `\n`. So flipping one `work_status` value on
a CRLF-encoded record rewrites **every line in the file**. Confirmed by execution against
the real `BO-2400a-3-i.yaml` converted to CRLF: **154 changed lines** from one flip.

```
'-id: BO-2400a-3-i\r'
'-components:\r'
... 142 more
```

**Why it will not be noticed.** `yaml.safe_load` still reports `work_status = 'done'`
afterwards, so every parsed-value assertion passes. This is the same blindness that let
the original KI-BO-003 defect survive — a re-serialised record parses equal to the
original. Any test that checks values rather than bytes is blind to it.

**Why it matters.** This is precisely the failure `BO-2400e-4` ("Recording progress on a
requirement changes the progress and nothing else") exists to prevent, arriving through a
door that AC did not anticipate. `BO-2400e-4` was marked done on 2026-08-25 on the
strength of tests that only exercise LF records, so the AC now reads as satisfied while
this hole is open.

**Exposure.** A scan of all 3,257 store records found **0** with CRLF, so nothing is
broken today. It is filed rather than fixed because the exposure is one careless write
away: this repo is developed under WSL2 with a checkout reachable from `/mnt/c`, and any
Windows-side editor that normalises line endings on save would introduce a CRLF record
silently. There is no guard that would report it.

**Fix sketch.** Open both ends with `newline=""` so line endings round-trip, or read bytes
and splice. A CRLF fixture belongs in
`unit_tests/build_orchestration/test_ki_bo_003_ac_yaml_preservation.py` alongside the
existing byte-level cases.

**Resolution (verified 2026-09-25).**

- Fixed in `f1726aef` (PR #602, 2026-08-26). The code was later moved out of `fast_lane.py`
  by `2e770ed6` (#804). `_update_ac_work_status` now lives in
  `scripts/build_orchestration/_fl_lifecycle.py:170`. It reads with `newline=""` (`:220`).
  The rewritten line keeps its own ending through `_line_ending_suffix` (`:239-240`).
  `_atomic_write_text` writes with `newline=""` (`:112`). All three call sites (`:337` claim,
  `:395` release, `:510` done) go through this one function. No other writer exists in
  `fast_lane.py` or `_fl_*.py`.
- The CRLF fixture asked for by the fix sketch exists:
  `python -m pytest unit_tests/build_orchestration/test_bo2400e_4_crlf_preservation.py -q`
  gives **3 passed**.
- The KI's own repro was re-run against current main (`d2fe85a1`). The real
  `BO-2400a-3-i.yaml` was converted to CRLF and `work_status` flipped `done` -> `in_progress`.
  Result: **1 changed line** (was 154), and **0 bare LF** bytes in the output.
- **Out of scope here, still open:** `mark_ac_done.py`, `approve_acs.py`,
  `_gtfa_implemented_by.py` and other AC-store writers still rewrite CRLF records as LF.
  That is tracked in
  [open-high-ki-acs-20260925-mark-ac-done-reports-success-without-writing-the-key.md](../../ac-store/open-high-ki-acs-20260925-mark-ac-done-reports-success-without-writing-the-key.md).

---
