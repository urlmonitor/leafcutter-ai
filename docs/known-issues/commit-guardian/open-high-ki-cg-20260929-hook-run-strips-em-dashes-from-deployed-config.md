---
title: "KI-CG-20260929-hook-run-strips-em-dashes-from-deployed-config — a commit's own hook run rewrites the deployed commit_guardian.json without its em-dashes, so the next commit fails check-output-drift"
description: "high — every commit makes the following commit fail. CAUSE IDENTIFIED 2026-10-07: check-negative-control-liveness rewrites the deployed config with json.dumps (ensure_ascii defaults True), unconditionally, on every run."
type: reference
category: reference
status: active
created: '2026-09-29'
last_updated: '2026-10-07'
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

- **Severity:** high — it blocks the next commit. Now that the cause is known the remedy is a one-line change, but until it lands the manual repair must be repeated before every commit.
- **Status:** open — no AC. **CAUSE IDENTIFIED 2026-10-07** and proven in isolation; see "The cause" below, which supersedes the former "What is not yet known" section.
- **Occurrences:** measured once with exact counts, `0374b637` → `b18112ef`; the same symptom is recorded in operator memory from earlier sessions. Reproduced continuously on 2026-10-07 across two worktrees — **every** commit of a four-commit sequence re-broke it, requiring the repair before each. · **First seen:** 2026-09-29 · **Last seen:** 2026-10-07
- **Where:** the rewrite is performed by `check_negative_control_liveness.py` (`_write_manifest`, the `json.dumps` call); the damaged file is the deployed `.leafcutter/scripts/commit_guardian/commit_guardian.json`; the symptom is reported by `check_output_drift.py` on the NEXT commit.

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

**Why copying the TEMPLATE is the wrong repair.** The template contains unresolved
`{{config.output_root}}` tokens that `inject_config` expands at deploy time, so
copying template over deployed leaves live tokens in a file the hooks execute from.
Measured 2026-10-07: the template holds **75** `{{` occurrences.

**But copying the deployed CONFIG copy is a correct and much cheaper repair**
(amendment, 2026-10-07 — this entry previously said `build.py` was the only valid
restore, which cost a 60s build per commit):

```bash
cp .leafcutter/config/commit_guardian/commit_guardian.json \
   .leafcutter/scripts/commit_guardian/commit_guardian.json
```

`.leafcutter/config/…` is itself a deploy-time artifact, so its tokens are already
resolved — measured **0** `{{` occurrences, against 75 in the template and 0 in a
healthy deployed copy. The two differ only in the em-dash escaping. This repair was
used before each of four commits on 2026-10-07 and `check-output-drift` passed on every
one of them. Do not generalise it to other outputs without checking the token count
first; it is correct here because this particular file has a resolved sibling under
`config/`.

**The cause (identified 2026-10-07).** It is `check-negative-control-liveness`
(GE-120f-1), not a `transform_*` hook. Its registration passes the deployed config as
its own input:

```
entry: python .leafcutter/scripts/commit_guardian/run_hook.py \
       .leafcutter/scripts/commit_guardian/check_negative_control_liveness.py \
       --manifest .leafcutter/scripts/commit_guardian/commit_guardian.json
```

`main()` loads that file, then calls `_write_manifest(manifest_path, data)` —
**unconditionally**, on every run, whether or not anything in the document changed.
`_write_manifest` is a single line:

```python
manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```

`json.dumps` defaults to `ensure_ascii=True`, so every em-dash is re-emitted as the
escape `—`. The file remains valid JSON with identical semantics, and the drift
census — which compares bytes — reports it as drifted.

The original hypothesis was right about the mechanism and wrong about the culprit: it
named `transform_*` hooks and "any autofix path that reserialises JSON", and the
signature it predicted (`json.load` → `json.dump` with `ensure_ascii` mishandling,
structure preserved, non-ASCII lost) is exactly what this is. It was missed because
this hook is neither a transform nor an autofix — it is a *judging* check that happens
to write its own input file.

That also explains the observation that it is NOT "the config was staged": the hook is
registered `pass_filenames: false`, so it runs on **every** commit regardless of the
staged set.

**Proof, run in isolation 2026-10-07.** Repair the deployed file, run only this hook,
re-count:

```
cp .leafcutter/config/commit_guardian/commit_guardian.json \
   .leafcutter/scripts/commit_guardian/commit_guardian.json
grep -o "u2014" .leafcutter/scripts/commit_guardian/commit_guardian.json | wc -l   ->   0

python .leafcutter/scripts/commit_guardian/check_negative_control_liveness.py \
       --manifest .leafcutter/scripts/commit_guardian/commit_guardian.json        ->   exit 0

grep -o "u2014" .leafcutter/scripts/commit_guardian/commit_guardian.json | wc -l   ->   110
```

No other hook ran. 0 → 110 escapes from that one invocation.

**Fix direction.** Two independent changes, either of which stops the damage and both of
which are worth making:

1. `ensure_ascii=False` in `_write_manifest`'s `json.dumps` call, so a write preserves
   the characters it read.
2. Write only when the document actually changed. The unconditional write is what makes
   this fire on every commit rather than only when a `currently` block is updated, and a
   judging check rewriting its own input on every run is the deeper defect — note that
   `run_hook.py`'s leave-it-as-you-found-it contract (GE-120g-1) reverts a judging
   check's working-copy changes, but `.leafcutter/` is not tracked, so nothing reverts
   this one.

Any test should assert on the em-dash count across a run, not merely on the drift
verdict, for the reason given below.

**Why em-dashes specifically are a good tracer.** They are the only high-frequency
non-ASCII characters in the file (90 of them, all inside `_comment` prose), so their
count is a cheap, precise probe for "did something reserialise this file". Any fix
should assert on that count, not merely on the drift verdict.

**Current workaround.** Run the `config/` copy shown above before the next commit —
instant, and it must be repeated before **every** commit, not merely after an affected
one, because the hook fires on all of them. Re-running `build.py` also restores it and
costs ~60s. Neither is a fix; both are repeats of the same manual step, which is why
this is filed rather than absorbed as routine.
