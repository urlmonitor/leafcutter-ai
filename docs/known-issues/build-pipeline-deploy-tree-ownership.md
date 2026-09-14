---
title: "Known issues — build-pipeline: deploy-tree ownership"
description: "Open, observed defects in which the build and the drift gates disagree about which files the build owns: orphaned deploy output the cleanup phase never removes, a breaking-change halt that looks like a no-op, and agent cards regenerated as drift on every bootstrap. Split out of build-pipeline.md, which is over its length limit."
type: reference
category: reference
status: active
created: 2026-09-14
last_updated: 2026-09-14
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
---

# Known issues — build-pipeline: deploy-tree ownership

A focused sibling of [`build-pipeline.md`](build-pipeline.md), holding the defects in which
`build.py` and the two drift gates (`check-build-drift`, `check-output-drift`) disagree
about which files the build owns. They are collected here because they read as one story
and because the parent register is over its length limit.

Same conventions as the parent: append a new `### KI-BP-YYYYMMDD-HHMM` section using the
UTC time you filed it (`date -u "+%Y%m%d-%H%M"`), and do not renumber existing ids.

### KI-BP-20260914-2012 — stale-file cleanup prints "(no stale files found)" while leaving orphaned deploy output in place, and the drift gate then blocks every commit made from that tree

- **Severity:** high — each orphan blocks every commit from the affected tree until someone finds and removes it by hand
- **Status:** open
- **Occurrences:** 4 distinct orphans on 2026-09-14, across 3 different trees
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `scripts/build.py` — the "Stale file cleanup" phase

**Symptom.** `build.py --force` prints `Stale file cleanup: (no stale files found)` on a
run that leaves behind deployed files whose templates no longer exist. Those files are then
reported by `check-output-drift` as `UNCOMPARABLE: GAP <path> action=run build.py to
register it` — advice that cannot work, because no template exists to register them from.
`gaps` is non-zero, so the hook exits 1 and **blocks every commit made from that tree**,
whatever the commit's diff contains. The only resolution is to find each orphan by hand and
delete it.

**The four observed on one day.**

| Orphan | Tree | Age |
|---|---|---|
| `.claude/workflows/fast-lane-build.js` | `leafcutter-ai/` install tree | dated 2026-08-18 — four weeks |
| `scripts/commit_guardian/_doc_length_ratchet.py` | epic worktree | minutes |
| `scripts/commit_guardian/_file_description.py` | epic worktree | minutes |
| `scripts/commit_guardian/check_pytest_style.py`, `check_sql_dependencies.py` | quick-fix worktree | unknown |

Two mechanisms produce them, and the cleanup phase misses both:

1. **A template is deleted upstream.** `fast-lane-build.js` is the clearest case: the
   repository's own source comments in three separate files already call it an orphan
   (`build_phases.py`, `injection_builders.py`, `fast_lane.py` — "fast-lane-build.js, an
   orphan"). The template was removed; the deployed copy survived four weeks of builds,
   each reporting no stale files.
2. **A tree is built twice from different template versions.** Building a worktree with a
   NEWER tree's `build.py` deploys files the worktree's own templates do not have;
   rebuilding with its own `build.py` then does not remove them. Both epic-worktree orphans
   were created exactly this way, in minutes, by two successive builds.

**Evidence.** With only those files removed and nothing else changed, `check-output-drift`
goes from `gaps=2 ... exit 1` to `gaps=0 drifted=0 ... exit 0` in the same tree. A freshly
created worktree reports `gaps=0` immediately, which is why this stays invisible until a
tree has been built more than once.

**Why the message is the defect, not just the miss.** A cleanup phase that finds nothing and
a cleanup phase that is not looking produce identical output. `(no stale files found)` reads
as a clean result, so nobody investigates — and the symptom surfaces much later, in a
different tool, as a commit-blocking drift failure whose suggested fix (`run build.py to
register it`) is the very command that just declined to remove the file. This is the same
shape as three defences already recorded in `CLAUDE.md`: the `feedback_categories.yaml` path
that reported missing on every worktree, the AC validator's bare-directory glob that exited
0 having checked nothing, and the stale `origin/main` ref in the merge audit. A check that
examined nothing must not look like a check that found nothing.

**Detection.**

```bash
# Any deployed file with no backing template is an orphan. From a built tree:
python3 scripts/commit_guardian/check_output_drift.py
# then, for each reported GAP path, confirm no template backs it:
ls templates/scripts/commit_guardian/<name>.py
```

**Fix direction.** The cleanup phase should compare the deployed set against the manifest it
just wrote and remove — or at minimum NAME — every deployed file the current template set
cannot account for. Report the count it actually examined, so "nothing to remove" is
distinguishable from "did not look". Removing is the better default given these files are
gitignored build output, but naming them would be enough to stop the multi-week survival
seen with `fast-lane-build.js`.

Worth fixing alongside: `check-output-drift`'s remediation string. For a genuine orphan,
`action=run build.py to register it` is impossible advice and sends the reader in a circle.
An orphan (deployed, no template) and an unregistered output (deployed, template exists,
manifest stale) need different messages.

**Pattern:** a cleanup step whose "nothing to do" and "did not look" are the same sentence,
whose omission surfaces days later in a different tool, as advice that cannot be followed.

### KI-BP-20260914-2013 — `build.py --force` halts on the breaking-change gate and exits 1 with the reason buried, so a build that did nothing is easily read as a build that succeeded

- **Severity:** medium — costs a debugging detour, and a stale deployed tree in the meantime
- **Status:** open
- **Occurrences:** 1 (2026-09-14)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `scripts/build.py` — the breaking-change gate, interacting with `--force`

**Symptom.** `build.py --force` in a worktree rebased onto a commit carrying a breaking
change halts before any deploy phase and exits 1. The deployed tree is left exactly as it
was, with no file written. The halt is correct and deliberate — it exists so a human reads
the migration notice — but three things make it easy to misread as success:

- `--force` does not cover it. The flag most people reach for to mean "just do it" is not
  the one required; `--force-breaking` is.
- The notice sits ~30 lines from the end, followed by a full re-print of the config-load
  banner and 25 lines of unrelated `[WARNING]` skill-declaration noise. `tail` shows the
  warnings; `head` shows the banner. Neither shows the halt.
- Nothing in the deployed tree changes, so the next command that reads it sees stale content
  with no indication why.

**Evidence.** Observed while regenerating a quick-fix worktree after rebasing onto
`cf270586b` ("the doc-length gate now actually refuses a commit"). The deployed
`.leafcutter/agents/python-coder.md` kept a 15:34 timestamp across three separate `--force`
runs at 18:48 and later. The templates had changed; `check-build-drift` reported them as
drifted; every rebuild intended to fix that silently did nothing. The cause was found only
by capturing the full output to a file and reading the middle of it. Re-running with
`--force-breaking` deployed normally and took drift to `0 drifted, 0 gaps`.

**Fix direction.** Print the halt reason LAST, after the warning block, so `tail` shows it.
Say explicitly that no files were written. Consider a distinct exit code for "halted at a
gate" versus "failed", so an automated caller can tell a refusal from a crash. The gate
itself should stay — a human reading the migration notice is the point.

**Pattern:** a deliberate, correct refusal that is indistinguishable from a no-op to everyone
who reads the output the way people actually read it.

### KI-BP-20260831-1334 — Every fast-lane worktree bootstrap regenerates ten agent cards as drift, and the lane stages with `git add -A`

> Relocated here from `build-pipeline.md` on 2026-09-14, unchanged, because it is the same
> deploy-tree-ownership family as the two entries above and the parent register is over its
> length limit.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 3 (three separate worktrees in one afternoon, identical ten files)
- **Where:** worktree bootstrap's `build.py` run; `templates/workflows-js/fast-lane-ship.js`
  Step 2 staging

**Symptom.** Immediately after `create-fastlane-worktree` completes — before any agent has
done any work — `git status` in the new worktree shows exactly ten modified files:

```
docs/agents/cards/{architecture-diagram-author, business-analyst, documentation-expert,
documentation-verifier, it-po, knowledge-harvester, llm-expert, product-owner,
python-coder, reference-author}.card.md
```

Reproduced in three independent worktrees created hours apart, same ten files each time. So
the committed cards and the cards `build.py` generates from the current templates do not
agree, and every bootstrap surfaces it afresh.

**The reason it matters is the staging rule.** The fast lane's commit step stages with
`git add -A` (`KI-BO-029`). Any lane that reaches commit therefore sweeps ten unrelated
regenerated cards into its PR, attributed to whatever AC it was building. In three runs this
was caught and reverted by hand each time; a run that is not watched will ship them.

**Two defects, and the second is the durable one.** The card/template disagreement is a
content bug someone can fix by regenerating and committing. The `git add -A` is a
*mechanism* bug: it guarantees that any pre-existing drift, from any source, is silently
adopted by the next PR to pass through the lane. Fixing the cards without fixing the staging
just waits for the next drift.

**Fix direction.** Stage explicitly — the lane knows which files its build set touches, and
`files_touched` already exists for exactly this. Separately, regenerate and commit the ten
cards so a fresh bootstrap is clean, and add a bootstrap assertion that a newly created
worktree has an empty `git status`: a provisioning step that leaves the tree dirty has not
finished.

**Related.** `KI-BO-029` (the `git add -A` itself). `KI-BP-20260831-1333` (the other
build-output-state defect found the same day — that one blocks a commit, this one silently
enlarges it; opposite failure directions, same underlying confusion about which files the
build owns). `KI-BP-20260914-2012` above is the third: that one leaves files behind rather
than regenerating them, and blocks the commit rather than enlarging it.
