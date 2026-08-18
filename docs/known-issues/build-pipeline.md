---
title: "Known issues — build-pipeline"
description: "Open, observed defects in the build-pipeline component: build.py, its deploy phases, and the self-hosting build that deploys this package into its own workspace. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - build_pipeline
related_docs:
  - docs/build-pipeline.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
---

# Known issues — build-pipeline

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-BP-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-BP-001 — The documented self-host build command destroys `docs/INDEX.md` on every run

- **Severity:** high
- **Status:** open
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

### KI-BP-002 — Generated agent cards are tracked but never regenerated, so every build dirties six of them

- **Severity:** medium
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build.py` — the agent-card generation phase; output at `docs/agents/cards/*.md`

**Symptom.** The cards are generated from two sources that change constantly — each
agent's template `description`, and the AC store — but they are **tracked files**, and the
PRs that change those sources do not regenerate them. So the committed cards drift out of
date silently, and the next `build.py` run rewrites them, leaving a tracked-file diff on an
otherwise clean tree that has nothing to do with the work in hand.

**Evidence.** Reproduced twice on 2026-08-18 in a clean worktree at `origin/main`. The
second run (after `#474` merged) rewrote **six** cards, 99 insertions / 36 deletions:
`ac-fulfillment-gate`, `architecture-diagram-author`, `documentation-expert`, `llm-expert`,
`python-coder`, `test-writer`.

The two drift sources are both visible in that diff:

- **Template description drift.** `#474` changed `ac-fulfillment-gate`'s agent template
  description and did not regenerate its own card. The committed card still described the
  pre-fix behaviour (`status: ok if all ACs pass`) after the fix had shipped the stricter
  contract (`ok only when at least one AC was resolved`).
- **AC-store drift.** `llm-expert`'s card was missing the five `BO-2400g-*` entries merged
  in `#452`, still listed `BO-530-3-i` (since removed), and carried a superseded title for
  `BO-2400a-3-i`.

**Fix direction.** Pick one and hold it: either stop tracking the cards and generate them
on demand, or make card regeneration a required part of any PR that touches an agent
template or the AC store — a CI drift check that fails when a rebuild would change a card,
in the same spirit as the existing `check-build-drift` hook (which does not catch this,
because it only inspects files already staged).

**Trap.** Same shape as KI-BP-001 — a routine build silently modifies tracked files you
did not edit, so the diff is easy to sweep into an unrelated commit with `git add -A`. It
is also easy to mistake for another author's work. Restore with
`git restore docs/agents/cards/` after any build you did not intend to include them in.

---

### KI-BP-003 — A hook deployed into the self-hosted workspace cannot find `config/doc_types.json` and hard-crashes

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** deploy layout vs `templates/scripts/commit_guardian/doc_type_validators.py:49` (`_find_doc_types_json`)

**Symptom.** `check-doc-frontmatter` aborts with an unhandled `FileNotFoundError` naming
`<root>/.leafcutter/scripts/commit_guardian/config/doc_types.json`. The hook is deployed;
the declaring file it must read is not, and no ancestor of the deployed location contains
it.

`_find_doc_types_json()` walks up from its own `__file__` checking two candidates at each
level: `config/doc_types.json` and `leafcutter/config/doc_types.json`. Neither resolves in
the self-hosted workspace layout:

- `<workspace>/config/` **does not exist** — the workspace parent is a deploy target
  holding only `.claude/`, `scripts/` and `.leafcutter/`.
- `<workspace>/leafcutter/config/` does not exist either, because **this package installs
  as `leafcutter-ai/`, not `leafcutter/`** — the directory name the consumer-layout
  candidate is hardcoded against. `CLAUDE.md` documents the install directory as
  `leafcutter-ai/`.

The walk then falls through to the filesystem root and returns its first candidate purely
so the error can name a path.

**Evidence.** Hit live on 2026-08-18 committing in a worktree whose `.leafcutter` was a
symlink to the workspace parent's — the bootstrap `CLAUDE.md` → "Worktree pre-commit
config" explicitly recommends. `find /home/henzeh/projects/leafcutter -maxdepth 4 -name
doc_types.json` returns only `leafcutter-ai/config/doc_types.json`, inside the package
repo. Running `build.py --target-dir <worktree>` so the worktree had its own deployed
layout fixed it, because the walk then reaches `<worktree>/config/doc_types.json`.

Note this is fail-**closed** and loud, which is the right choice (GE-118c — renumbered
from `GE-120` on 2026-08-18 — deliberately removed the silent fallback to a narrower
built-in list). The defect is the unreachable
file, not the raised error.

**Fix direction.** Either deploy `config/doc_types.json` alongside the hooks that read it —
this is the failure class `CLAUDE.md` → "New Hook / Gate Dependencies Must Be in the Build
Deploy-Manifest" already documents — or stop hardcoding the package directory name in the
candidate list and derive it.

**The same resolution gap exists in the sibling resolver, with a worse outcome.**
`diagram_type_validators._find_diagram_types_json()` (`:35-55`) uses the identical
two-candidate walk with the same hardcoded `leafcutter/` directory name, so it is equally
unreachable in this layout — but it returns `None` and `_load_diagram_types()` falls back
**silently** to the `DOC_FM_DIAGRAM_TYPE_VALUES` constant. That is precisely the silent
narrowing GE-118c removed from `doc_types` on 2026-08-18, still live in the file GE-118c
copied its pattern from. Fixing the path resolution must cover both; see
`docs/known-issues/commit-guardian.md` → KI-CG-002 for the fallback half.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (a hook dependency missing
from the deployed layout), though this one crashes rather than passing falsely.

---

### KI-BP-004 — A worktree's deployed hooks are frozen at build time, so after merging `main` the gates enforce the previous ruleset

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build.py` deploy step / `<worktree>/.leafcutter/scripts/commit_guardian/`; no staleness check anywhere in the commit path

**Symptom.** `build.py` copies hook code into `.leafcutter/`. Nothing re-runs it and nothing
compares it against the source tree, so the deployed copy is a snapshot of whenever the
worktree was built. Merge `origin/main` into a long-lived branch and the *source* advances
while the *running gates* do not: every commit afterwards is judged by the older ruleset.
Both directions are wrong. A rule fixed on `main` still fails here; a rule *added* on `main`
does not run at all, and its absence is indistinguishable from a pass.

**Evidence.** A worktree built on 2026-08-17 19:38, then merged with `origin/main` on
2026-08-18. `check-doc-frontmatter` failed on seven generated agent cards with
`unknown doc type: card; valid values: adr, architecture, explanation, how-to, reference,
retro, tutorial` — a seven-value list. But `config/doc_types.json` at that same commit
contains **ten** entries including `card`, and the file the hook is supposed to read was
right there in the worktree.

The deployed hook was simply old:

```text
$ grep -c "_find_doc_types_json" <worktree>/.leafcutter/scripts/commit_guardian/doc_type_validators.py
0
$ python <worktree>/scripts/build.py --target-dir <worktree> --force-breaking
$ grep -c "_find_doc_types_json" <worktree>/.leafcutter/scripts/commit_guardian/doc_type_validators.py
4
$ HOOK_ROOT=<worktree> python <worktree>/.leafcutter/scripts/commit_guardian/check_doc_frontmatter.py \
    docs/agents/cards/python-coder.card.md
✅ PASSED: 1 doc(s) passed frontmatter validation
```

The deployed copy predated GE-118c entirely — it did not contain the resolver function at
all, so it was falling back to the narrow constant that GE-118c had already deleted from the
source. Rebuilding fixed it outright.

**Why this is not KI-BP-003.** BP-003 is a *path-resolution* gap: current code that cannot
find a reachable file. This is a *staleness* gap: code that is not current. They present
almost identically — a hook complaining about something the source says is fine — and the
first was mistaken for the second during this session. The distinguishing check is to diff
the deployed file against its template, not to reason about paths.

**Fix direction.** Make staleness detectable rather than relying on discipline. A cheap
version: have the pre-commit entrypoint compare `.build_manifest.json` against the source
templates' hashes and refuse (or warn loudly) when they diverge. `check_build_drift` already
exists and already reasons about deploy parity — extending it to guard the hooks' own
freshness is the natural home. Until then, treat `build.py --target-dir <worktree>` as a
mandatory step immediately after every `git merge origin/main`, and distrust any hook
verdict — pass or fail — taken from a worktree built before the merge.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in its staleness form rather than its missing-file form.
