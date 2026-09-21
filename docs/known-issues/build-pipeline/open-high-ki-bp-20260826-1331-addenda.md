---
title: "KI-BP-20260826-1331 (addenda) — material moved out of the main entry"
description: "KI-BP-20260826-1331 (addenda) — material moved out of the main entry"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260826-1331 (addenda) — material moved out of the main entry

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

**A dangling id, noted in passing.** Earlier drafts of this entry cited **`KI-BO-001`** for the
changelog-presence gate. That id has **no definition anywhere in the registers** — it is cited
seven times across the repo, including in `fast-lane-ship.js`'s own source comments and in two
other register entries, and defined zero times. The citations here have been replaced with
plain description. Whoever owns `build-orchestration.md` should either write the entry or
retire the id; a reference that resolves to nothing is indistinguishable from one whose target
was deleted, and readers cannot tell which they are looking at.

---

**Independently rediscovered, 2026-08-26 (EPIC-BuildPipelinePhantomRemediation).** A second
session hit the same mechanism from the drift-gate side and authored a duplicate entry as
`KI-BP-20260826-1340`, nine minutes after this one and — independently — with the same
timestamped-id convention. That duplicate is withdrawn in favour of this entry; its distinct
evidence is folded in below rather than filed twice. Two sessions converging on the same
hazard and the same fix for ids, in the same hour, without either knowing of the other, is
itself the strongest available argument that the convention above was the right call.

Five further observations, all from the drift-gate side, all cleared by a single rebuild from
the correct worktree:

1. `check-output-drift` reported `drifted=27`. Twenty-six were files the branch never touched —
   `git diff origin/main...HEAD` showed no change to `templates/agents/adr-author.md` or the
   other nine agent templates flagged.
2. Later in the same session the same gate reported `drifted=55`, again entirely cleared by a
   rebuild.
3. Three failures in `unit_tests/commit_guardian/test_ge_120_doc_types_deployed_resolution.py`,
   which reads the shared tree. Its `doc_type_validators.py` had been rewritten while the
   `doc_types.json` beside it was a week older — the tree was internally inconsistent, mixing
   two builds. They passed again later with no code change.
4. `unit_tests/commit_guardian/test_bp_100k_4.py`'s real-registry test flipped red three
   separate times while the source registry held the fix throughout, each time because a build
   from the main checkout redeployed main's pre-fix `commit_guardian.json` over it. Fixed by
   pointing the test at the *source* registry via `HOOK_TEST_CONFIG` — a test that asserts a
   property of this repository must read the version-controlled artifact, not a build output of
   unknown provenance.
5. Seventeen orphaned files (12 of them `.py` under `scripts/commit_guardian/`) sat in the
   shared tree with no template in any worktree and no git history in any commit — another
   session's uncommitted work, leaked in and reported as coverage gaps against an unrelated
   branch.

**Beyond the deploy tree: any shared mutable state here has the same property.** On the same
day a concurrent session removed an *active* worktree mid-drive, snapshotting first as
`8cd1e3c0` (`WIP SNAPSHOT ... not for merge`, author `manual`, `git add -A --no-verify`).
Nothing was lost, but a foreign commit appeared on the branch and one subagent's edits were
silently absent afterwards. Separately, an uncommitted known-issues entry in the main checkout
was overwritten by `4c47882a` within the hour. The deploy tree, the main checkout's working
tree, and a worktree's very existence are all writable by a session that does not know you
exist — so treat an uncommitted edit anywhere outside your own worktree as volatile, and commit
register entries immediately rather than leaving them staged.

---
