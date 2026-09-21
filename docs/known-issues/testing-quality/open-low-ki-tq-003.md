---
title: "KI-TQ-003 — The eval staleness gate asks you to stage a file that is gitignored"
description: "KI-TQ-003 — The eval staleness gate asks you to stage a file that is gitignored"
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

# KI-TQ-003 — The eval staleness gate asks you to stage a file that is gitignored

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_eval_staleness.py:156` (a commit-guardian hook, filed here because its subject is the eval workflow); `scripts/evals/results/.gitignore`

**Symptom.** On a stale result the hook prints `Re-run the affected eval(s) locally, then
re-stage the result:`. Re-staging is impossible: `scripts/evals/results/.gitignore` is
`*.json`, so no result file can ever enter the index.

**Evidence.** The gate nonetheless works, because `eval_selector.py` reads the result from
disk rather than from the index. Only the remediation message is wrong — which makes it a
documentation defect that costs the next person a confused minute, not a correctness one.

**Fix direction.** Reword the message to "re-run the eval so the on-disk result is fresh";
drop the staging instruction.

---

> **Entries `KI-TQ-004` … `KI-TQ-009` are recovered from an unmerged branch.** They were
> written between 2026-08-19 and 2026-08-25 while driving
> `EPIC-GE122UniquenessPassAndRepair`, into the parallel known-issues register PR #495
> invented (`KI-TQ-1` … `KI-TQ-7`), which lost every reconciliation conflict against this file
> and was discarded. The two registers turned out to be disjoint in subject matter — this file
> is entirely about the agent eval harness, that one entirely about test-isolation and
> verification-method defects — so the analysis below would have been lost with the branch.
> Every entry was re-verified against `main` at `37655862`, and each `Status` line says whether
> the code it describes is on `main` or only on the unmerged branch.
>
> One entry from that set was **dropped as no longer true**: it reported
> `test_ge_122e_1.py::test_goal_record_claims_a_new_id_and_its_folder_matches_origin_main`
> failing as a function of branch staleness, because it required `git diff origin/main --
> <folder>` to be empty. That assertion was amended on 2026-08-18 (before the entry was
> written) to a one-directional set difference — `missing = baseline_ids - current_ids`
> (`test_ge_122e_1.py:514`) — which tolerates `origin/main` growing ahead by design, and the
> baseline ref is now resolved from the first of `origin/main`, `main`, `HEAD^2` that exists.
> Both halves of the reported failure mode are gone.

---
