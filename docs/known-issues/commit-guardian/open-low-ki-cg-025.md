---
title: "KI-CG-025 — `check_ticket_state_integrity.py` retains an always-exit-0 contract that a coder cannot unilaterally retire"
description: "KI-CG-025 — `check_ticket_state_integrity.py` retains an always-exit-0 contract that a coder cannot unilaterally retire"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-025 — `check_ticket_state_integrity.py` retains an always-exit-0 contract that a coder cannot unilaterally retire

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — **the code is NOT on `main`**; the script lives only on unmerged
  PR #495. Filed so the constraint is not rediscovered when that branch lands.
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `templates/scripts/commit_guardian/check_ticket_state_integrity.py`

**Symptom.** The script documents a `Returns: Always 0` fail-open contract, so the hook
cannot block anything. GE-122a-2 widened work-item integrity checking but did **not** retire
it.

**Root cause of the stall, which is the part worth recording.** The contract is pinned by
existing tests, so a coder may not unilaterally weaken it — retiring it needs a `test-writer`
pass first to change the pinned expectations. That ordering constraint is why a known
fail-open survived a change that touched the same file.

**Fix direction.** Sequence it as test-writer (amend the pinned expectations) → coder (retire
the contract), not the reverse. Any AC written for it must name the pinned tests explicitly,
or the coder phase will correctly refuse again.

---
