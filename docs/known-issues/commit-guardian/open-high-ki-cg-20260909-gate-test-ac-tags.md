---
title: "KI-CG-20260909-gate-test-ac-tags — `check-test-ac-tags` is one absent config key away from refusing 5,566 test functions"
description: "high (latent) — currently `warn`, so it blocks nothing; flipping one key blocks nearly the whole test suite."
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

# KI-CG-20260909-gate-test-ac-tags — `check-test-ac-tags` is one absent config key away from refusing 5,566 test functions

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high (latent) — currently `warn`, so it blocks nothing; flipping one key blocks nearly the whole test suite.
- **Status:** open — no AC. Needs its own session, and the largest backlog of the set.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/check_test_ac_tags.py`; mode resolves to `warn` because `test_ac_tag_enforcement` is **absent** from `commit_guardian.json`.

**The numbers.** **5,566 test functions across 595 of 597 test files** carry no `# covers: XX-NNN` tag. Only 2 files are fully tagged. Registered in `warn` mode this is 0 blocking and a very large amount of console noise; registered in error mode it stops essentially all test work.

**Ratchet shape — this one does have a scalar.** Untagged-function count per file must not increase versus `HEAD`. That makes every existing untagged test permanently tolerated while any newly added test must carry a tag, which is precisely the "guard all new work" rule. It also degrades correctly under refactors: moving a tagged test between files raises one file's count and lowers another's, so per-file comparison needs the "new file starts at 0" case handled explicitly.

**Sequencing note.** Do not attempt a bulk backfill of 5,566 tags. The tags must name real ACs, and `check_done_proof`'s Python scanner additionally requires the tag to sit *inside* a test function (see `KI-CG-20260908-covers-tag-must-be-inside-a-test-function` above) — a mechanical backfill would produce thousands of tags pointing at nothing, which `_collect_dangling_tags` is supposed to reject. Ratchet first, backfill opportunistically.

**Definition of done.** Existing 5,566 stay green; a newly added untagged test function is refused; `test_ac_tag_enforcement` is present and its value deliberate.

---
