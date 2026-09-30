---
title: "KI-CG-20260929-hook-run-strips-em-dashes-from-deployed-config — a commit's own hook run rewrites the deployed commit_guardian.json without its em-dashes, so the next commit fails check-output-drift"
description: "high — every commit that stages the config makes the following commit fail; cause not yet identified."
type: reference
category: reference
status: active
created: '2026-09-29'
last_updated: '2026-09-29'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260929-hook-run-strips-em-dashes-from-deployed-config — a commit's own hook run rewrites the deployed commit_guardian.json without its em-dashes, so the next commit fails check-output-drift

> One known issue, filed on sight during the GE-127f-2 build (ticket 07 of
> EPIC-FilesStayWorkable). Index: [commit-guardian.md](../commit-guardian.md).
> Sibling of [KI-CG-20260929-output-drift-scans-gitignored-cache](open-high-ki-cg-20260929-output-drift-scans-gitignored-cache.md),
> found in the same session but a distinct defect: that one is a file that should
> not be in the census, this one is a real, unexplained rewrite of a file that should.

- **Severity:** high — it blocks the next commit, and the cause is unknown so the only current remedy is manual.
- **Status:** open — no AC. **Cause not identified**; see "What is not yet known".
- **Occurrences:** measured once with exact counts, `0374b637` → `b18112ef`; the same symptom is recorded in operator memory from earlier sessions. · **First seen:** 2026-09-29 · **Last seen:** 2026-09-29
- **Where:** deployed `.leafcutter/scripts/commit_guardian/commit_guardian.json`; detected by `check_output_drift.py`.

**The measurement.** Immediately after `build.py`, the deployed config and its
template agree. After a commit's hook run, they do not:

```
.leafcutter/scripts/commit_guardian/commit_guardian.json:   0   em-dashes
templates/scripts/commit_guardian/commit_guardian.json:    90   em-dashes
```

The next commit then fails:

```
check-output-drift: RESULT verified=495 uncomparable=5 exempt=5 gaps=0 drifted=1 missing=0 unreadable=0
```

**Why the printed fix is misleading.** The hook says to edit the template and re-run
`build.py`. The template is not wrong — it still has all 90. Nothing needs editing.
The deployed copy was rewritten after the build, and `build.py` alone restores it
(confirmed: rebuild → 90 em-dashes → `drifted=0`).

**Why a plain copy is the wrong repair.** The template contains unresolved
`{{config.output_root}}` tokens that `inject_config` expands at deploy time, so
copying template over deployed leaves live tokens in a file the hooks execute from.
Re-running `build.py` is the correct restore.

**What is not yet known.** Which step performs the rewrite. It happens between the
build and the drift census, during a commit's own hook run. It is NOT simply "the
config was staged" — in the observed case `commit_guardian.json` was not in the staged
set for the commit whose run stripped it. Candidates worth checking first are the
`transform_*` hooks and any autofix path that reserialises JSON, since a
`json.load` → `json.dump` round trip with a non-UTF-8 encoding or `ensure_ascii`
mishandling would produce exactly this signature: structure preserved, non-ASCII
characters lost.

**Why em-dashes specifically are a good tracer.** They are the only high-frequency
non-ASCII characters in the file (90 of them, all inside `_comment` prose), so their
count is a cheap, precise probe for "did something reserialise this file". Any fix
should assert on that count, not merely on the drift verdict.

**Current workaround.** Re-run `build.py` before the next commit. It costs a build
(~60s) and must be repeated after every affected commit, which is why this is filed
rather than absorbed as routine.
