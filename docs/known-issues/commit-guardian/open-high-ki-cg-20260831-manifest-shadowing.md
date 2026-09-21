---
title: "KI-CG-20260831-manifest-shadowing — `check-build-drift` takes the first `.build_manifest.json` it finds, and an obsolete one at a higher-priority root makes it report every template in the repository as unregistered"
description: "KI-CG-20260831-manifest-shadowing — `check-build-drift` takes the first `.build_manifest.json` it finds, and an obsolete one at a higher-priority root makes it report every template in the repository as unregistered"
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

# KI-CG-20260831-manifest-shadowing — `check-build-drift` takes the first `.build_manifest.json` it finds, and an obsolete one at a higher-priority root makes it report every template in the repository as unregistered

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `scripts/commit_guardian/check_build_drift.py` — `_resolve_manifest_path()`
  (first-match return, no validation) and the `package_offset` read at
  `manifest.get("package_root", "") or ""`; same resolution shared by `check_output_drift`

**Symptom.** A commit staging exactly one AC YAML file — no Python, no templates — was
refused by `check-build-drift` with 170 findings:

```text
UNCOMPARABLE: GAP templates/agents/README.md action=run build.py to register it
UNCOMPARABLE: GAP templates/agents/ac-validator.md action=run build.py to register it
... (168 more)
check-build-drift: RESULT verified=0 uncomparable=170 exempt=0 gaps=170 drifted=0 missing=0 unreadable=0
```

`verified=0` is the tell. The hook did not find drift — it compared **nothing at all** and
then failed on its own inability to compare. `drifted=0` says the same thing from the other
side: not one template actually differed from its deployed copy.

**Cause — two defects compounding.**

*First, manifest resolution returns the first hit and never asks whether it is the right
one.* `_resolve_manifest_path()` walks candidate roots in priority order and returns on the
first `.build_manifest.json` that exists. Root 1 is the git toplevel; root 2 is the workspace
root. Two manifests were present:

| | path | mtime | templates | `output_mappings` | `package_root` |
|---|---|---|---|---|---|
| root 1 (**chosen**) | `leafcutter-ai/.build_manifest.json` | Aug 26 | 61 | 154 | **absent** |
| root 2 (ignored) | `leafcutter/.build_manifest.json` | Aug 31 | 174 | 464 | `"leafcutter-ai"` |

The obsolete one won on position. There is no mtime comparison, no completeness check, and
no signal in the output naming which file was used.

*Second, the missing-field fallback degrades toward a known-wrong value.* Both manifests key
templates as `leafcutter-ai/templates/…`, but only the current one records the offset
`package_root: "leafcutter-ai"`. The hook reads it as:

```python
package_offset = manifest.get("package_root", "") or ""
```

with the comment *"Missing key degrades to `""` for manifests written before this field
existed."* That assumes a manifest lacking the field was written in a layout whose offset is
genuinely empty. The Aug 26 manifest simply **predates the field** — its true offset is
`leafcutter-ai`. So `templates_base` collapsed to the package root, lookup keys were computed
as `templates/agents/README.md`, and every one was compared against manifest keys spelled
`leafcutter-ai/templates/agents/README.md`.

Nothing matched. That is why the count is **170 and not 113** — 61 of those templates *are* in
the stale manifest, under a key spelling the hook never generated. A pure staleness bug would
have reported only the 113 genuinely-absent ones; reporting all 170 is the signature of a
total key-namespace miss.

**Why it went unnoticed until now.** Root 1 is the git toplevel of the *current process*. From
a worktree that is the worktree root, which holds no manifest, so the search falls through to
the workspace root and finds the good one. Nearly every commit in this repository is made from
a worktree. The defect only fires in the package's own main checkout — the one place least
often committed from, and the one place `.build_manifest.json` is gitignored so the stale file
never shows in `git status`.

**Why this is worse than a false negative.** The comment above the offset read says the
git-based heuristic it replaced *"failed open for any git-unavailable layout"* and that failing
open "is the failure mode this whole ticket exists to remove." The replacement does fail
closed — but at a **100% false-positive rate**, on a commit touching nothing it guards. A gate
that blocks every commit with a wall of findings about files the author did not touch is not
safer than one that stays quiet; it is the fastest way to teach everyone to reach for `SKIP=`,
and once that reflex exists the gate's real findings go with it.

**Remediation.** Three separable changes, in order of value:

1. **Validate the manifest before trusting it, and say which one was used.** A manifest whose
   key namespace does not intersect the paths about to be looked up is unusable — detect that
   and either continue the root search or emit a distinct diagnostic. `verified=0` with
   `gaps=N` should never be reported as a finding about the templates; it is a finding about
   the run. Print the resolved manifest path on every run.
2. **Refuse a manifest without `package_root` rather than guessing its offset.** The field is
   an offset that cannot be inferred; absent it, the honest states are "re-run `build.py`" or
   "keep searching", not "assume empty". A schema-version marker would make this explicit.
3. **Prefer the freshest usable manifest** over the first found, or have `build.py` remove a
   manifest it supersedes at another root so two can never coexist.

**Workaround in use.** Move the stale manifest aside
(`mv leafcutter-ai/.build_manifest.json /tmp/`) and re-run the canonical
`python scripts/build.py --target-dir <workspace-root>`. After that `check-build-drift` passed
with `verified=464`, and `check-output-drift` — which shares the resolution — surfaced 8
genuine unregistered workspace artifacts instead of 170 phantoms.

**Related.** `KI-BP-011` (the manifest is written to the package that ran the build rather than
the install it describes) is how two manifests come to exist at two roots in the first place;
this entry is what the *reader* of those manifests does about it. `KI-CG-034`
(`check_output_drift` keys paths in two namespaces that never intersect) is the same
key-namespace class of defect in the sibling hook.

**Pattern:** a backward-compatibility fallback that converts "I do not know this value" into a
specific wrong value, in a resolver that had already picked the wrong input — so two
independently-reasonable graceful degradations compose into a confident, precise, entirely
false report.

---
