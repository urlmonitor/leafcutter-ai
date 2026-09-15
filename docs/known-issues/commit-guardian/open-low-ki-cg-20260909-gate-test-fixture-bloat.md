---
title: "KI-CG-20260909-gate-test-fixture-bloat — `check-test-fixture-bloat` is disabled by an absent config section, hiding 499 violations, and only one of its three axes ratchets cleanly"
description: "medium (latent) — section absent → `enabled` defaults `False`."
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

# KI-CG-20260909-gate-test-fixture-bloat — `check-test-fixture-bloat` is disabled by an absent config section, hiding 499 violations, and only one of its three axes ratchets cleanly

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium (latent) — section absent → `enabled` defaults `False`.
- **Status:** open — no AC. Needs its own session.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/check_test_fixture_bloat.py`; `test_fixture_bloat` **absent** from `commit_guardian.json`. It does carry a `grandfathered_paths` list, currently empty.

**The numbers.** **499 violations across 266 files**: 328 inline-dict (>5 keys), 160 line-count (>500 lines), 11 parametrize-rows (>3).

**Ratchet shape — mixed, and that is the interesting part.** The `line_count` axis ratchets exactly like `check-file-size` (one scalar per file, compare to `HEAD`) and could reuse `_file_size_ratchet.py` directly rather than growing a second implementation of the same idea. The `inline_dict` and `parametrize_rows` axes have no single scalar — they need "count of over-limit AST nodes in this file must not increase." The existing empty `grandfathered_paths` list is a third, cruder option: enumerate the 266 files. Prefer the ratchet; a path list of 266 entries rots the moment a file is renamed.

**Definition of done.** The 499 stay green; a new oversized fixture is refused on each of the three axes; `line_count` shares the `check-file-size` ratchet rather than reimplementing it.

---
