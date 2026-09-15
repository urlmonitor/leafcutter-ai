---
title: "KI-CG-20260909-gate-ticket-test-requirements — registered as configured, `check-ticket-test-requirements` would inspect nothing; wired correctly it fails 252 tickets"
description: "high — this is the one gate whose registration would actively create a false green."
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

# KI-CG-20260909-gate-ticket-test-requirements — registered as configured, `check-ticket-test-requirements` would inspect nothing; wired correctly it fails 252 tickets

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — this is the one gate whose registration would actively create a false green.
- **Status:** open — no AC. Needs its own session; fix the wiring BEFORE registering.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/check_ticket_test_requirements.py`; the proposed manifest entry sets `files: ^tickets/.*\.md$` with **`pass_filenames: false`**.

**The mechanism.** With `pass_filenames: false`, `run_hook.py` forwards zero arguments; the script's `main()` then falls back to `sys.stdin.readlines()`. With empty stdin it checks 0 files and exits 0. Registering it therefore adds a manifest entry that reports success having examined nothing — the exact false-assurance shape the census AC exists to remove, reproduced one level up by the fix for it.

**The numbers, if wired correctly.** **252 of 370 code tickets** have no populated `## Test Requirements` block.

**Ratchet shape.** Non-scalar: a per-file boolean — did this ticket have a populated block at `HEAD`? An existing under-specified ticket stays editable; a newly created code ticket must declare test requirements.

**Confidence caveat, carried from the census.** The stdin fallback was confirmed to check 0 files with empty stdin, but `pre_commit` is not importable in this environment so what pre-commit actually attaches to a hook's stdin was not observed. The gate receives no filenames either way; if stdin were attached to something unexpected the failure mode would be a hang rather than a clean pass. Confirm against a real pre-commit invocation as step one of the session.

**Definition of done.** `pass_filenames: true` (or an internal `git diff --cached` scan), verified to actually receive the staged tickets; the 252 grandfathered; a new code ticket without test requirements refused.

---
