---
title: "KI-BP-20260907-1620 — The doc-index phase derives the index from the target tree and writes it into the package tree, so every self-hosting build truncates `docs/INDEX.md` by 75%"
description: "KI-BP-20260907-1620 — The doc-index phase derives the index from the target tree and writes it into the package tree, so every self-hosting build truncates `docs/INDEX.md` by 75%"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-28'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260907-1620 — The doc-index phase derives the index from the target tree and writes it into the package tree, so every self-hosting build truncates `docs/INDEX.md` by 75%

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED** (AC BP-1500a-1, fix in `scripts/build.py::build_doc_index`; verified 2026-09-28 by a red/green/mutation-proof run of `unit_tests/build_guards/test_bp_1500a_1_doc_index_scan_root.py` and by replaying the self-host layout on a copy of the real docs tree, which left the tracked `docs/INDEX.md` byte-identical: 252 lines, 0 "No docs found.", `created:` preserved).
- **Occurrences:** 2 (2026-09-07, twice in one session)
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** the `Doc index` phase of `scripts/build.py` · `scripts/generate_doc_index.py` (`generate_index`) · triggered by any `build.py --target-dir <other-root>`, which is precisely what `build-self.sh` runs

**Symptom.** After `python scripts/build.py --target-dir <workspace>` run from inside the package
repo, `docs/INDEX.md` **in the package repo** is rewritten from 230 lines to 57, losing the
Components table and most of the index, and its `created:` stamp is reset from the real creation
date to today:

```text
HEAD:     230 lines        working:   57 lines
created:  2026-08-11   →   2026-09-07
1 file changed, 11 insertions(+), 184 deletions(-)
```

**Mechanism.** The index is derived from one root and written to another. Run in-process against
each root, writing nothing:

```text
generate_index(<package repo>)  -> 230 lines
generate_index(<workspace>)     ->  57 lines
```

The 57-line output is the workspace's own small `docs/` tree. The build computes the index for the
`--target-dir` it was given and then persists it over the package repo's `docs/INDEX.md`. Both
halves are individually correct; only the pairing is wrong.

**Why this is worse than an ordinary wrong-file write.** `build-self.sh` is documented as the
package's own development build and does exactly `build.py --target-dir <parent workspace>`. So
the corruption is not an edge case reached by an unusual flag — it is what the sanctioned
self-hosting build does every time it runs.

**Detection.**

```bash
git diff --stat docs/INDEX.md      # after any build.py --target-dir <other-root>
grep -c '^## Components' docs/INDEX.md   # 1 when intact, 0 when truncated
grep '^created:' docs/INDEX.md           # a reset to today is the signature
```

The `created:` reset is the most reliable tell: a regenerated index stamps today, so a `created:`
that matches the run date rather than the file's real history means the file was replaced rather
than updated.

**Confidence.** Empirically confirmed, twice in one session, and the root mismatch is reproduced
by the two `generate_index` calls above without writing anything. An earlier report of this
symptom was investigated and wrongly dismissed as unreproducible, because the check ran
`generate_index` against the package root only — which returns the correct 230 lines and looks
like a clean bill of health. Reproducing it requires passing the *other* root, which is the whole
defect. Recorded here because that near-miss is the more useful lesson: a one-root check cannot
falsify a two-root bug.

**Fix direction.** Make the phase's read root and write root the same value, and assert it: the
index written to `<X>/docs/INDEX.md` must be the index derived from `<X>/docs/`. A regression test
should build into a scratch target from inside the package repo and assert the package's own
`docs/INDEX.md` is byte-identical afterwards — that test fails today and cannot pass vacuously,
since it names a specific file that must not change. Preserving `created:` across regeneration is
a separate, smaller fix worth taking at the same time: an auto-generated file that resets its own
creation date destroys the one field that would otherwise reveal it had been replaced.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2, the deployed layout differing from
the source being read, in its cross-root form. **Related:** `KI-BP-20260907-0722` and `KI-BP-009`
are the same family — a build step whose target is computed from one root and applied to another,
reported as success.

---

## Resolution (2026-09-28)

`build_doc_index` now builds the index from the repository that holds the `docs_root` folder: `generate_index(<target>/<docs_root>/.., <target>/<docs_root>)` when `docs_root` ends in a `docs` folder, so in the self-hosting layout it scans `leafcutter-ai/docs` instead of the workspace parent. The default `docs_root: docs/` resolves to the target root as before, so consumer installs are unchanged. A fail-safe refuses to replace an index that lists entries with one that lists none: it warns and returns 0 rather than exiting non-zero, so a mis-rooted scan cannot abort an otherwise good build (a deliberate difference from the exit-non-zero wording in KI-BP-016's fix direction). `generate_doc_index.py` is unchanged. KI-BP-001, KI-BP-016 and KI-BP-20260907-1620 were three entries for this one defect and are closed together. Still open and separate: KI-BP-20260907-0722, KI-BP-009 and the agent-card drift (KI-BP-002).
