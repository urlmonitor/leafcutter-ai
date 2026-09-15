---
title: "KI-CG-20260909-gate-ticket-ac-limits-and-the-three-inert — the one gate ready to register today, and three whose population is empty here"
description: "KI-CG-20260909-gate-ticket-ac-limits-and-the-three-inert — the one gate ready to register today, and three whose population is empty here"
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

# KI-CG-20260909-gate-ticket-ac-limits-and-the-three-inert — the one gate ready to register today, and three whose population is empty here

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low.
- **Status:** open — no AC. Probably one short session covering all four.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09

**`check-ticket-ac-limits` — ready, with one caveat.** Limits are ≤7 ACs per agent block and ≤20 per ticket; measured maximum is 10 total and 7 per-agent (the check is `> 7`, so 7 passes). 0 violations across 1,295 tickets. **The caveat:** that result was obtained by forcing the repo root. Run from the deployed path in this workspace the hook is a silent no-op — `leafcutter-ai/scripts/commit_guardian` symlinks into `.leafcutter/`, which contains its own `.git`, and `_find_project_root()` walks up from `__file__` rather than CWD, stopping at `/home/henzeh/projects/leafcutter/.leafcutter`. Measured from there: **1,295 of 1,295 tickets unreadable → all skipped → exit 0 having read nothing.** Same family as the `.security-allowlist` symlink hazard in `CLAUDE.md`. Registering it is safe; trusting a green run of the deployed hook is not.

**`check-pytest-style`, `check-sql-complexity`, `check-sql-dependencies` — inert here.** Populations are empty: no `unit_tests/live_trader/`, and **0 `.sql` files tracked**. All three report 0 because they inspect nothing, which is materially different from compliance and must not be recorded as a pass. They are harmless to register and would become live if the repo ever gains SQL or that test directory. The session's question is whether a permanently-inert gate should be registered at all, or removed — an unregistered script that inspects nothing and a registered one that inspects nothing are both dead weight, but only the second one looks like coverage.

**Definition of done.** `check-ticket-ac-limits` registered, with the deployed-layout no-op noted where a reader will hit it. An explicit keep-or-delete decision on the three inert scripts, recorded either way.

---
