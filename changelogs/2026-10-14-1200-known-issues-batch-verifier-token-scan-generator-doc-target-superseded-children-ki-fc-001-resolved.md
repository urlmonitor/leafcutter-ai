---
title: "Known issues: verifier token scan, generator doc target, superseded children; KI-FC-001 resolved"
date: "2026-10-14"
time: "12:00"
type: manual
components: 
  - documentation_system
  - ac_driven_dev
  - ac_store
  - commit_guardian
  - feedback_collector
summary: "Records three defects that each needed a hand fix on 2026-10-12, each checked in code on main: one new known issue and two occurrences on existing entries. Records that the done-proof waiver gap is fixed at source. Moves KI-FC-001 to resolved."
description: "One content commit (78ae68bc1), documentation only. New KI-DS-20261014-token-scan-flags-f-string-fields-in-source-targets: documentation-verifier Step 6c reads a .py target's f-string fields as unfilled placeholders. KI-ACD-20260925-contract-target-is-parent-link Occurrence 2: the ticket generator picked a source file (relationship: implements) as the documentation target, and 604 not-done ACs would get a non-doc target today. KI-ACS-016 Occurrence 4: the superseded-child block fired on INF-400c-4, and 7 composites are blocked only by it. KI-CG-20260914 Occurrence 4: the composite waiver half is fixed at source by PR #1165, and an INF-500d-4 refusal came from an install built before it. KI-FC-001 is moved to resolved/ (PR #1169, 818c301c0); its harvester-identity remainder is fixed by PR #1175 (3af00c0b6), and the BO-100d remainder stays with KI-BO-20261009. Inbound links are repointed."
commits: 
  - 78ae68bc1
breaking: false
---

## Entry

Three defects needed a hand fix on 2026-10-12. Each was checked in the code on `main`
before it was recorded:

- **New: KI-DS-20261014-token-scan-flags-f-string-fields-in-source-targets.**
  documentation-verifier runs its unfilled-token check on every required path, so a `.py`
  target's f-string fields (`{exc}`, `{jsonl_path}`) block the phase as placeholders.
- **KI-ACD-20260925-contract-target-is-parent-link, Occurrence 2.** The ticket generator took a
  source file (`relationship: implements`) as the documentation-expert target. A read-only scan
  finds 604 not-done ACs that would get a non-doc target today, and 570 that would get an AC
  record.
- **KI-ACS-016, Occurrence 4.** A superseded child still blocks its composite. `INF-400c-4` was
  refused because of `INF-400c-4-ii`. 7 composites in the store are blocked only by this:
  `BO-100d`, `BO-530-3`, `GE-128a`, `INF-400c-2`, `INF-400c-4`, `INF-400c-5` and `TKT-500f-6`.
- **KI-CG-20260914, Occurrence 4.** The docs-only waiver gap for composites is fixed at source
  by PR #1165. The `INF-500d-4` refusal on 2026-10-14 came from an install built before that
  fix.

**KI-FC-001 resolved.** It is moved to `feedback-collector/resolved/`, fixed by PR #1169
(`818c301c0`). Its harvester-identity remainder was fixed by PR #1175 (`3af00c0b6`). The BO-100d
remainder stays open as KI-BO-20261009.

No code and no AC records changed.
