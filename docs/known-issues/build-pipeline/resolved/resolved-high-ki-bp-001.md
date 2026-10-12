---
title: "KI-BP-001 — The documented self-host build command destroys `docs/INDEX.md` on every run"
description: "KI-BP-001 — The documented self-host build command destroys `docs/INDEX.md` on every run"
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

# KI-BP-001 — The documented self-host build command destroys `docs/INDEX.md` on every run

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **DUPLICATE of KI-BP-016 — verified 2026-08-25. Fix there, delete this.**
> Same phase, same symptom, same fix direction; KI-BP-016 carries the correct root cause
> (the read root and the write root are computed differently at `build.py:1028-1030`, so
> `docs_root` is honoured when writing and ignored when reading). Kept for now only so the
> id is not silently reused; the register's own rule is to increment `Occurrences` rather
> than file twice. Reproduction and confirmation live under KI-BP-016.

- **Severity:** high
- **Status:** **RESOLVED** (AC BP-1500a-1, fix in `scripts/build.py::build_doc_index`; verified 2026-09-28 by a red/green/mutation-proof run of `unit_tests/build_guards/test_bp_1500a_1_doc_index_scan_root.py` and by replaying the self-host layout on a copy of the real docs tree, which left the tracked `docs/INDEX.md` byte-identical: 252 lines, 0 "No docs found.", `created:` preserved).
- **Occurrences:** 4
- **First seen:** 2026-08-17 · **Last seen:** 2026-08-18
- **Where:** `scripts/build.py` — the Doc-index phase (`generate_doc_index.py`,
  `repo_root = Path(__file__).resolve().parent.parent` default)

**Symptom.** `python leafcutter-ai/scripts/build.py --target-dir .` run from the
workspace parent — the exact command `CLAUDE.md` documents, and what `./build-self.sh`
runs — regenerates the doc index **from the workspace parent** (which has no `docs/`
tree) while **writing into the source repo** at `leafcutter-ai/docs/INDEX.md`. The build
prints `✓ wrote leafcutter-ai/docs/INDEX.md` and the file is replaced with `No docs
found.` in all nine sections.

The write target and the scan root disagree: it scans the deploy target and writes to
the package. Deploying into the repo root instead leaves the tree clean, which is why
this is invisible to consumer installs and only bites self-hosted development.

**Evidence.** Reproduced four times across two sessions. Each run leaves exactly
`docs/INDEX.md | 183 ++-----` — 11 insertions, 172 deletions — as the sole working-tree
modification, on an otherwise clean tree. Reverted with `git checkout -- docs/INDEX.md`
each time. Initially misdiagnosed as another author's stray commit before the build was
caught doing it in the act.

**Fix direction.** Resolve the doc-index scan root and the write target from the same
base. Either scan the package repo when writing into it, or write into the target
directory it scanned — but not one of each. Until then, `git checkout -- docs/INDEX.md`
after any self-host build, and never stage `docs/INDEX.md` from a build run.

**Trap.** Because the corruption is a *tracked file modification* produced by a routine
build, it is easy to commit by accident in a `git add -A` sweep — and easy to blame on a
concurrent author, since it appears in a tree you did not knowingly edit.

---

## Resolution (2026-09-28)

`build_doc_index` now builds the index from the repository that holds the `docs_root` folder: `generate_index(<target>/<docs_root>/.., <target>/<docs_root>)` when `docs_root` ends in a `docs` folder, so in the self-hosting layout it scans `leafcutter-ai/docs` instead of the workspace parent. The default `docs_root: docs/` resolves to the target root as before, so consumer installs are unchanged. A fail-safe refuses to replace an index that lists entries with one that lists none: it warns and returns 0 rather than exiting non-zero, so a mis-rooted scan cannot abort an otherwise good build (a deliberate difference from the exit-non-zero wording in KI-BP-016's fix direction). `generate_doc_index.py` is unchanged. KI-BP-001, KI-BP-016 and KI-BP-20260907-1620 were three entries for this one defect and are closed together. Still open and separate: KI-BP-20260907-0722, KI-BP-009 and the agent-card drift (KI-BP-002).
