---
title: "KI-BP-005 — Deleting a template leaves its deployed copy behind, and the build reports \"no stale files found\""
description: "KI-BP-005 — Deleting a template leaves its deployed copy behind, and the build reports \"no stale files found\""
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

# KI-BP-005 — Deleting a template leaves its deployed copy behind, and the build reports "no stale files found"

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **RE-VERIFIED 2026-08-25 — LIVE.** Removed `templates/scripts/commit_guardian/check_eval_staleness.py`
> from a scratch package and rebuilt into an adopter: exit 0, `(no stale files found)`, and the
> deployed copy still present carrying the *previous* build's timestamp.
>
> **The reassurance is not a weak check — it is an unrelated check wearing the right label.**
> `build.py:1676-1679` prints the message; `_cleanup_stale_paths` (`build.py:1262-1292`) only
> iterates `_PRE_CONSOLIDATION_PATHS` (`:1187-1199`), eleven hardcoded *legacy migration*
> paths. It has nothing to do with deploy orphans and structurally cannot see one.
>
> **Two corrections to the entry's evidence.** (1) The "manifest entry is gone" framing
> overstates it: `.build_manifest.json` never tracked commit_guardian scripts in the first
> place — its `templates` section covers only `templates/agents/`, and `output_mappings`
> covers only agents/skills/commands/rules/workflows-js. The orphan itself is exactly as
> described. (2) Deleting an **agent** template *does* fail the build
> (`[ERROR] [REGISTRY] Agent 'brainstorm-worker': template_path ... does not exist`, exit 1),
> so the gap is scoped to artifact classes that have no registry behind them. That is a
> useful narrowing of the fix and an argument that the registry pattern is the one that works.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build.py` — the "Stale file cleanup" step, and whatever drives it from `.build_manifest.json`

**Symptom.** Delete a file from `templates/` and rebuild. The build drops the entry from
`.build_manifest.json` and prints `Stale file cleanup: (no stale files found)` — while the
previously-deployed artifact stays on disk in `.leafcutter/`. The manifest forgets the file;
the file itself is never removed. Nothing reports this, because the cleanup's own notion of
"stale" is derived from the manifest it has already pruned, so a deleted template is
invisible to the very step that exists to catch it.

The result is an orphaned executable in every install that ever received the artifact,
permanently, with no surface that mentions it. Deleting a template is a normal operation —
this is not an exotic path.

**Evidence.** Observed while removing `templates/scripts/commit_guardian/known_failing_tests.py`
(PR #486). Template deleted, then `python scripts/build.py --target-dir . --force-breaking`:

```text
Stale file cleanup:
  (no stale files found)

$ grep -n "known_failing" .build_manifest.json
(exit 1 — no matches; the manifest entry is gone)

$ ls -la .leafcutter/scripts/commit_guardian/known_failing_tests.py
-rw-r--r-- 1 henzeh henzeh 11458 Aug 18 11:16 .../known_failing_tests.py
```

The `11:16` timestamp is the *earlier* build, before the deletion. The file was not rewritten
and not removed — it was simply abandoned.

`.leafcutter/` is gitignored, so this never shows up in a diff and no CI gate can see it. It
was found only by checking the deployed path by hand after distrusting the "no stale files
found" line.

**Why it matters beyond tidiness.** Tests and hooks import from the deployed tree. An orphan
there can keep a local test green after its source is gone, while CI — which builds fresh —
fails. That is a false green pointing the wrong way: the local run is the optimistic one. In
this instance the orphan was removed by hand before the suite was run, specifically so the
result would be honest.

**Relationship to existing criteria.** This is the *inverse* of `BP-900g-9` ("a declared
deploy entry whose source is missing fails the build") — there, the manifest names something
absent; here, something present is named by nothing. It is the same shape as `BP-900g-7`
("a registry entry naming an executable artifact that exists nowhere"), also inverted:
artifact real, registry entry gone. Nothing in the AC store currently covers this direction,
so an AC is probably warranted rather than a silent patch.

**Fix direction.** The cleanup step must compare the deployed tree against the *new* manifest
and remove what the manifest no longer claims — i.e. diff against the previous manifest, or
walk `.leafcutter/` and delete unclaimed files. Pruning the manifest before computing
staleness is the actual bug: it destroys the only record that the file was ever ours. Whatever
the mechanism, a build that removes an entry and leaves the artifact must say so out loud
rather than printing a clean bill of health.

**Two more instances of this class, both found 2026-08-19.** The proposed fix above ("walk
`.leafcutter/` and delete unclaimed files") would resolve all three, which is the argument for
doing it that way rather than diffing manifests:

- **A live orphan the cleanup mechanism structurally cannot see.**
  `.leafcutter/workflows/pause-resume-substrate.js` has no template and is claimed by nothing.
  Clean-mode has a `workflows` entry meant to remove exactly this, and it never executes — see
  KI-BP-010.
- **Hand-placed files are indistinguishable from deployed ones.**
  `.leafcutter/config/doc_types.json` and `diagram_types.json` are present in the self-hosted
  workspace and deployed by no build phase; someone copied them in as a workaround for
  KI-BP-003. Since `.leafcutter/` is gitignored and nothing reconciles it against the manifest,
  that workaround is invisible **and** it masks the deploy gap it was working around, so
  KI-BP-003 tests as fixed there. Same root cause as the orphan, opposite origin: this file
  arrived from outside the build rather than being abandoned by it. It also means any local
  verdict on KI-BP-003 taken from that workspace is vacuous.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in its orphan form — the deployed tree holds something the
source no longer has.

---
