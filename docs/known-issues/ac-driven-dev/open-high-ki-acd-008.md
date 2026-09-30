---
title: "KI-ACD-008 — AC id allocation misses ids owned by feature folders, and has already minted a live duplicate on main"
description: "KI-ACD-008 — AC id allocation misses ids owned by feature folders, and has already minted a live duplicate on main"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-008 — AC id allocation misses ids owned by feature folders, and has already minted a live duplicate on main

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **partially fixed, 2026-09-23.** No live duplicate is on `main` right now
  (both instances below are resolved). The downstream "nothing catches it" half is also
  fixed: `templates/hooks/check_identifier_uniqueness_authoring.py`, wired into
  `templates/settings.json`'s `PostToolUse Edit|Write` (landed 2026-09-01, before and
  independent of the ACD-2100 epic), now recursively walks the whole
  `docs/acceptance-criteria/` tree via `scan_acceptance_criteria()`
  (`templates/scripts/commit_guardian/_uniqueness_scanners.py:568-599`,
  `ac_root.rglob("*.yaml")`) and fails closed (exit 2) the moment a colliding `id:` is
  written, at authoring time — before commit, before CI. This directly closes the "why
  nothing caught it" mechanism this entry blamed on `KI-ACS-001` ("the store validator
  ... does not test id uniqueness" is no longer accurate). What is **not** fixed: the
  id-**allocation** step itself — the PO/BA agent's own reasoning for picking a new id
  — has no mechanical enumerate-then-refuse logic; `grep`s for id-allocation guidance in
  `templates/agents/product-owner.md`, `templates/agents/business-analyst.md`, and
  `templates/skills/plan-feature/SKILL.md` all return nothing. An agent can still
  propose a colliding id; it is now blocked immediately after writing it rather than
  reaching `main` clean. See "Re-verified 2026-09-23" below.
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
- **Where:** `/plan-feature` AC-authoring stages — the id-selection step

**Symptom.** When choosing the next free AC id, the pipeline does not see ids that are
owned by an existing **feature folder**. It picked an id that a 43-file tree already
held, producing two records with the same `id` in the same component.

**Evidence — the duplicate is on `main` right now.**

```
docs/acceptance-criteria/guardrail-engine/GE-120.yaml
  id: "GE-120"   level: L2
  "A guard enforces the document types the project declared, not a narrower list ..."

docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
  id: GE-120     level: L0
  "Trust that a green check actually checked something"       (+42 descendant files)
```

Ordering, from git:

| When | Commit | What |
|---|---|---|
| 2026-08-17 16:48 | `ec8bb173a` (#453) | a tree was renamed onto `GE-120` from its now-retired predecessor id — folder + 43 files |
| 2026-08-18 09:09 | `160d4f47a` (#466) | a **`plan-feature(AC)`** run authored a loose L2 *also* claiming `GE-120` |

The tree held the id for ~16 hours before `/plan-feature` reissued it. A
product-owner agent run manually on 2026-08-18 avoided the same trap only because it
was told to scan both, and reported: *"Scanned BOTH the feature folders and the LOOSE
`GE-*.yaml` files at component root (a folder-only listing under-reports)."* The
pipeline needs that behaviour by construction, not by prompt luck.

**Why nothing caught it.** See `docs/known-issues/ac-store.md` KI-ACS-001 — the
store validator behind the *required* `AC store valid` CI check does not test id
uniqueness, so a duplicate id merges clean.

**Fix direction.** Id allocation must enumerate every `id:` field actually present in
the component's store — walking the directory tree, not listing folder names or loose
files alone — and must refuse to allocate an id already in use. It should also treat
retired ids as taken: the id between GE-118 and GE-120 is recorded as retired and
must never be reissued (see PR #453; not written out here, because the GE-122e-1
guard fails the build on any live citation of it).

**Not fixed here.** Resolving the live `GE-120` collision means renaming one of the two
records. The loose L2 is the later claimant (#466) and is the cheaper move — 1 AC file
plus 4 `# covers: GE-120` tags in
`unit_tests/commit_guardian/test_ge_120_doc_types_deployed_resolution.py` — versus 43
files for the tree. Left for a decision rather than done unilaterally, because it
renames another author's AC and edits their tests.

**Update — the collision is resolved (2026-08-18); the allocator defect above is NOT.**
The loose L2 was renumbered from `GE-120` to `GE-118c` and moved into
`docs/acceptance-criteria/guardrail-engine/GE-118-hooks-work-in-worktrees/`, parented under
`GE-118` (2 of 7 children -> 3 of 7). Its four `# covers:` tags moved with it and the test
module was renamed to `test_ge_118c_doc_types_deployed_resolution.py`. The goal tree keeps
`GE-120`, as its claim is test-enforced by `unit_tests/commit_guardian/test_ge_122e_1.py`.
A suffix-shaped id was chosen over the free root number `GE-124` because
`check_ac_parent_covered_by.py` and `scan_ac_orphans.py` derive a parent from id SHAPE and
`derive_parent_id()` returns `None` for a root id — a root-shaped id would carry a parent
link no gate could police. The evidence block above is left exactly as written: it records
what was true on `main` when this issue was filed. **This entry stays open** — nothing about
the id-allocation step has changed, and the next `/plan-feature` run can still mint a
duplicate the same way.

**Second occurrence, 2026-08-25 — and it widens the entry.** A `business-analyst` run
authoring ACs for `GE-122d` allocated `BP-900h-4`, an id already live and
`readiness: approved` on `main`. Caught before the PR by a manual store-wide grep;
renumbered to `BP-900h-6` across 11 references.

Two things this adds to the entry as written above. First, the defect is **not confined to
`/plan-feature`**: this run was a directly-dispatched authoring agent in an isolated
worktree, so the fix must land in whatever the shared id-allocation step is, not in one
command's prompt. Second, and worse for detection, the collision was minted **in a
worktree branched from `origin/main`** — the colliding id was present in the branch's own
checkout the whole time. So this is not a stale-clone problem that fetching would fix; the
allocator simply did not look. Combined with KI-ACS-001 (the required `AC store valid`
check does not test id uniqueness), a duplicate authored this way reaches `main` with every
gate green.

**Re-verified 2026-09-23.** Checked the store's actual factual claims, not the entry's
narrative:

- **`GE-120` — no live duplicate.** `grep -rl '^id: "GE-120"' docs/acceptance-criteria/`
  now returns exactly one file:
  `docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml`.
  The loose L2 this entry's own "Update — the collision is resolved (2026-08-18)" note
  describes was renamed to `GE-118c` and is no longer present under the old id — matches
  what the entry itself already recorded.
- **`BP-900h-4` — no live duplicate.** Only one `BP-900h-4.yaml` exists
  (`docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/`); the
  colliding second claimant was renumbered to `BP-900h-6`, per this entry's own "Second
  occurrence" note.
- **The allocator mechanism itself — unfixed, but now caught mechanically.** No code
  change addresses "enumerate every `id:` field ... walking the directory tree" at the
  point an id is *chosen*. What changed instead is downstream: a duplicate can no longer
  merge silently, because `check_identifier_uniqueness_authoring.py` +
  `scan_acceptance_criteria()` block it at the first `Edit`/`Write` that creates it (see
  Status line above). This is a real closure of the "merges clean" harm, not of the
  "picks a bad id in the first place" defect — kept open and downgraded to partially
  fixed for that reason.

---
