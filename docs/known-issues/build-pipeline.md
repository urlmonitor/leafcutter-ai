---
title: "Known issues — build-pipeline"
description: "Open, observed defects in the build-pipeline component: build.py, its deploy phases, and the self-hosting build that deploys this package into its own workspace. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
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

> **DUPLICATE of KI-BP-016 — verified 2026-08-25. Fix there, delete this.**
> Same phase, same symptom, same fix direction; KI-BP-016 carries the correct root cause
> (the read root and the write root are computed differently at `build.py:1028-1030`, so
> `docs_root` is honoured when writing and ignored when reading). Kept for now only so the
> id is not silently reused; the register's own rule is to increment `Occurrences` rather
> than file twice. Reproduction and confirmation live under KI-BP-016.

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

> **DUPLICATE of KI-BP-015 — verified 2026-08-25.** Both describe `docs/agents/cards/*.card.md`
> as tracked build outputs with no freshness gate that drift and get rewritten on every build;
> filed a week apart at different severities. Keep one and increment `Occurrences` on it.
>
> **Do not fix the cards themselves.** The mechanism wanted is a repo-wide generated-artifact
> ratchet, and BP-1500a already specifies it — including the trap that makes the naive version
> useless: the check must be computed over *every* tracked generated artifact, not the subset
> in the change under review, because the drifted artifact is by definition never in that
> subset.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py` — the agent-card generation phase; output at `docs/agents/cards/*.md`

**Third occurrence, 2026-08-25.** Reproduced again on a clean worktree cut from `origin/main`,
this time rewriting **four** cards with 68 insertions and zero deletions:
`architecture-diagram-author`, `documentation-expert`, `frontend-coder`, `python-coder`. The
build printed nothing about it — the drift was noticed only because `git status` was checked
immediately afterwards for an unrelated reason.

This occurrence is **purely the AC-store drift source**, with no template-description component:
every added line is a new AC-index entry, e.g. `frontend-coder` gaining
`GE-124b-3: The pin is stripped from production builds and retained in dev, test and the Atlas`
after `#535` landed that record. So the sources are independent and either alone is enough —
a PR that touches no agent template at all still leaves the cards stale.

Not committed with the run that found it: those four files belong with whichever PR lands the
ACs that caused the drift, and picking them up in an unrelated change invites a conflict. Which
is itself the point — the cost of this defect is paid by whoever happens to run a build next,
and it is always someone with no reason to care.

**Same finding as `KI-BP-015`, recorded twice on the same day by two sessions.** That entry
reports the same four cards and 63 lines against this occurrence's 68, from an independent
build. Per this file's own rule — *"Hitting an existing issue. Increment `Occurrences` and
update `Last seen`. Do not add a duplicate entry"* — the occurrence increment is the correct
form and `KI-BP-015` should be folded into this entry rather than kept alongside it. Left for
whoever consolidates: deleting another session's entry mid-flight is how the `KI-BO-019`/`020`
collision got worse. Worth noting that two independent observers filing the same defect within
hours is itself evidence of how often this fires.

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

### KI-BP-003 — `config/doc_types.json` is never deployed alongside the hooks that read it, so `check-doc-frontmatter` hard-crashes in the self-hosted workspace and in every adopter worktree

> **RE-VERIFIED 2026-08-25 — LIVE, and the entry's open contradiction is settled.**
> Reproduced against a fresh `git init` adopter repo built into `/tmp` (a real repo matters:
> several hooks resolve their root via `git rev-parse --show-toplevel` and pass vacuously
> outside one — two earlier probes returned a false green for exactly that reason).
> `_find_doc_types_json()` resolved to a path with `EXISTS: False` and
> `check_doc_frontmatter.py` raised `FileNotFoundError` at `doc_type_validators.py:113`,
> exit 1. A clean build leaves `.leafcutter/config/` holding only `commit_guardian/` and
> `feedback_categories.yaml`, against 21 files in source `config/`. `grep doc_types.json`
> across `build_phases.py`, `build.py` and `build_helpers.py` returns **zero hits** — there
> is no deploy site at all. The one config file that *is* deployed is `commit_guardian.json`
> at `build_phases.py:1450-1453`, which is exactly where this one should have gone.
>
> **The second-vs-third-occurrence disagreement was not a contradiction — the two reports
> were describing different layouts.** The discriminator is whether the checkout root
> contains `config/doc_types.json`. A *package-repo* checkout resolves (the ancestor walk
> finds the repo root, which has `config/`); an *adopter* repo root raises, on `main` as
> well as in worktrees; the self-hosted workspace parent raises and is masked here only by
> hand-copied files sitting in `.leafcutter/config/` dated Aug 18 and Aug 25. Any verdict
> taken from this workspace or its worktrees is vacuous. The title should say the adopter's
> `main` is affected, not only worktrees.
>
> **Do not close this by hand-copying the file into the deploy phase.** That is the fourth
> occurrence of the same shape; see KI-BP-018. Unblock adopters that way if you must, but
> the entry closes with BP-900g-8.

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 4
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
- **Where:** deploy layout vs `templates/scripts/commit_guardian/doc_type_validators.py:49` (`_find_doc_types_json`)

**Second occurrence, 2026-08-19 — reported from a consumer install, and it is worse there
than in the self-hosted workspace.** DIAGraph (`roche-sandbox/dia-graph`, pin `54356a92`)
hits the identical `FileNotFoundError` inside **any git worktree**. In their deployed
layout the only candidate that ever resolves is `<repo>/leafcutter/config/doc_types.json`
— the file inside the submodule — and in a worktree `leafcutter/` is an empty directory
(submodule contents are not populated, and they additionally gitignore it). Confirmed by
contrast: the main checkout resolves and proceeds (then hits KI-CG-008); the worktree
raises.

**Third occurrence, 2026-08-25 — and it contradicts the second on exactly one point.** A
further report describes the same unhandled `FileNotFoundError` but states it fires **on
`main` as well**, not only inside a worktree. That is directly at odds with the
"main resolves, worktree raises" contrast recorded above, and the disagreement is left
open here deliberately rather than resolved by picking the more recent account: the two
reports may simply be describing different deployed layouts, which is the whole substance
of this issue.

Only one thing distinguishes them, and it is cheap. In the failing checkout, run the
ancestor walk and print which candidate resolves:

```bash
python -c "import sys; sys.path.insert(0, '.leafcutter/scripts/commit_guardian'); import doc_type_validators as d; print(d._find_doc_types_json())"
```

If it names a path that exists, the layout resolves and any crash is a different defect
(likely KI-CG-008). If it names a path that does not exist, this issue is live on that
checkout. Whoever reproduces next should paste that one line into this entry and delete
this paragraph — do **not** widen the title to claim `main` is affected until it does,
since the deploy-layout fix below is scoped by which candidate actually resolves.

Raised to **blocker** on that evidence. This is not an edge case reachable only by
self-hosting: leafcutter ships a `/feature` skill and a `worktree-agent` whose whole job is
to create worktrees, and `building-epics` drives epics inside them. The hook is broken by
the package's own recommended workflow, for every adopter, and their standing workaround is
`SKIP=check-doc-frontmatter`.

**Fourth occurrence, 2026-08-25 — and it widens the defect from one file to the whole
`config/` directory.** Reproduced from a worktree freshly created from `origin/main` at
commit `73500600` and built via `python3 scripts/build.py --target-dir <that worktree>`.
`ls <worktree>/.leafcutter/config/` returns exactly two entries: `commit_guardian` and
`feedback_categories.yaml`. Absent from that deployed output, though all three exist in the
package source at `config/`: `agent_registry.json`, `doc_types.json`, and
`diagram_types.json`. `find <worktree> -name agent_registry.json` locates it only at
`<worktree>/config/agent_registry.json` — the package source copy, never deployed — and in a
web fixtures directory; never under the deployed `.leafcutter/`.

By contrast, the long-lived workspace parent `/home/henzeh/projects/leafcutter/.leafcutter/config/`
DOES contain all five files — `agent_registry.json`, `commit_guardian`, `diagram_types.json`,
`doc_types.json`, `feedback_categories.yaml`. That is the Masking trap above, restated for the
wider scope: two of those five (`doc_types.json`, `diagram_types.json`) were hand-copied in on
2026-08-18 specifically to work around this crash; the build never put them there. So the one
workspace where this package is developed is the one place the gap is invisible, which is why
it keeps being rediscovered from consumer installs rather than from self-hosted development.

`BP-900g-8-ii` ("the deployed-dependency closure covers the data and configuration files a
script reads, not only the modules it imports"), approved and merged 2026-08-19, already states
the general rule this violates. `doc_types.json`, `diagram_types.json`, and now
`agent_registry.json` (see KI-BP-012, which covers `agent_registry.json`'s non-deployment and
its knock-on validation gap in full) are three unfixed instances of that one rule, not three
separate defects.

**A concrete fix the reporter proposes, and it is the right one.** Emit the config into the
deployed tree at build time. `.leafcutter/config/` already exists and is git-tracked in a
consumer install (it holds `commit_guardian/` and `feedback_categories.yaml`), so copying
`config/doc_types.json` → `.leafcutter/config/doc_types.json` makes the **existing** ancestor
walk succeed at the `.leafcutter/` level: no change to `_find_doc_types_json()`, and it works
in worktrees because `.leafcutter/` is committed. Deploy `diagram_types.json` in the same
phase (see KI-CG-002).

**Masking trap — this workspace looks fixed and is not.** `/home/henzeh/projects/leafcutter/.leafcutter/config/`
currently contains `doc_types.json` and `diagram_types.json`, so the walk resolves here and
the hook passes. Neither file is deployed by any build phase: `grep -n "doc_types.json"
scripts/build_phases.py scripts/build.py` returns **nothing**. They were placed by hand, and
`.leafcutter/` is gitignored, so nothing records that. Any local verdict taken from this
workspace is therefore vacuous for the defect. Verify against a freshly-built target, or
against a consumer install.

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
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py` deploy step / `<worktree>/.leafcutter/scripts/commit_guardian/`; no staleness check anywhere in the commit path

**Second occurrence, 2026-08-25 — the false-block direction, observed end to end.**
Committing a merge of `origin/main` into a review branch, `check-contract-shrinking` blocked
with a list of deleted test functions. Every one of them was deleted **by main**, arriving
through the merge; the branch had deleted nothing. Main already carries the fix for exactly
this — the merge-scoping logic in `_merge_scoped_paths()`, whose changelog entry
(`2026-08-18-1920-merge-commits-no-longer-trip-the-contract-shrinking-guard-on-the-base-branch-s-history.md`)
was *inside the very merge being committed*. The worktree's deployed hook predated it.

Rebuilding the worktree's deploy (`python scripts/build.py --target-dir <worktree>`) made
`_merge_scoped_paths` present and the same commit passed on its own merits. Worth recording
because the tempting response is `SKIP=check-contract-shrinking`, which would have worked,
produced the same green, and told the author nothing — the fix was already written and
merely undeployed. A staleness check would have named that in one line.

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

---

### KI-BP-005 — Deleting a template leaves its deployed copy behind, and the build reports "no stale files found"

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

### KI-BP-006 — `build_ac_store`'s hardcoded deploy list omits the AC-store validator and both its helpers

> **RE-VERIFIED 2026-08-25 — PARTIALLY FIXED, consequence still LIVE (still a blocker).**
> `validate_ac_schema.py` **was** added to `deploy_map` by `912d3f2d` (*"deploy all 13
> ac_store scripts to consumer installs"*, #500, 2026-08-19) — one day after this entry was
> filed. The list is now 18 entries, not eleven; the cited line refs have moved to
> `build_phases.py:878-918` and `:923-928`.
>
> **Both helpers are still undeployed.** `grep "_ac_components\|_component_migration_map"
> scripts/build_phases.py` returns nothing. The consequence is unchanged, it just arrives as
> an import crash rather than a missing file: running the deployed
> `validate_ac_schema.py --help` in an adopter gives
> `ModuleNotFoundError: No module named '_ac_components'`, exit 1.
> `_component_migration_map.py` fails softer — a warning and an empty map.
>
> **Why patching the list will not close this, which the entry does not record.**
> `_manifest_ac_store_scripts` (`build.py:331-349`) derives the AC-store set with `iterdir()`
> over source while its docstring claims it matches what `build_ac_store` deploys. That
> derived set feeds the broken-reference guard — one of only six gates that can fail the
> build — so the guard treats `_ac_components.py` as deployable because it exists in source.
> The only hard gate that could catch this is fed by a set that contradicts the hand-list it
> polices. This is the fourth round of "add the missing module"; see KI-BP-018 and build
> BP-900g-8/-9 instead.

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build_phases.py:851-879` (`deploy_map`), `:884-889` (the skip branch)

**Symptom.** The `deploy_map` is a hand-maintained list of eleven `(source, dest)` pairs.
Three modules the AC store depends on are not in it:

- `_component_migration_map.py` — imported by `generate_ticket_from_ac.py`
- `_ac_components.py` — imported at module scope by `validate_ac_schema.py:40`
- `validate_ac_schema.py` itself

In a consumer repo that vendors the build output, the schema validator is therefore absent,
and the deriver that would populate the field it validates is absent too. The consequence
lands on the AC store as a hard block — see KI-ACS-007, where 972 of 973 ACs in one
consumer repo are invalid on a field the package computes for itself.

This is the **fourth** recurrence of one failure mode. `done_proof.py`, `test_enforcement.py`,
`ac_parent_id.py` and `ac_coverage_resolver.py` were each added to this same list after each
one shipped broken; five of the eleven entries now carry a comment explaining why that
specific module must not be forgotten. Those comments are evidence the mechanism does not
work — a list that needs a warning per entry is not a list, it is a trap with annotations.

**Evidence.** `grep -n "_component_migration_map" scripts/build_phases.py` returns nothing,
while `scripts/ac_store/generate_ticket_from_ac.py` imports it. The omission is silent by
construction: `:884-889` logs `build_ac_store: source script not found, skipping` at
WARNING and continues, so a mistyped or missing entry never fails the build — and a module
that was never listed produces no message at all.

**Fix direction.** Stop hand-maintaining the list. Deploy `scripts/ac_store/*.py` wholesale,
or derive the closure by walking the imports of the declared entry points. Failing that,
add a test that imports every deployed AC-store module **from the deployed layout** in a
fresh process — the existing unit tests import from source, which is precisely why all five
prior instances stayed green. Treat "add the module to `deploy_map`" as a fix for the
instance, never for the defect.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), missing-file form.

---

### KI-BP-007 — No gate validates a skill reference written in template prose, so six skills are loaded by name and none of them exist

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build_phases.py:1970-1990` — the `skills_invoked` resolution loop, the
  only skill-reference validator in the build

**Symptom.** Reported from a consumer install as "those knowledge-capture skills aren't
available in this consumer project." The report is accurate but its framing is not: nothing
is wrong with the packaging. `build_skills` copies `templates/skills/` wholesale, and
`route-knowledge` / `knowledge-query` deploy correctly. The skills the customer wanted were
never written. Six distinct skills are referenced **by path** in shipped templates and have
no directory in `templates/skills/`:

| Referenced skill | Referenced from | Reference is |
|---|---|---|
| `route-learning` | `signoff/SKILL.md`, PO v3, BA v3, IT PO v3, `retrospective-agent`, `skills/README.md` | `Load .claude/skills/route-learning/SKILL.md` |
| `capture-learning` | `signoff/SKILL.md`, PO v3, BA v3, IT PO v3 | `Load .claude/skills/capture-learning/SKILL.md` |
| `agent-telemetry` | `building-epics/SKILL.md` ×8 | `python .claude/skills/agent-telemetry/scripts/emit_event.py …` |
| `import-scanner` | `research-agent.md` | routing table — "invoke via `Bash`" |
| `find-context-candle` | `research-agent.md` | routing table — "invoke via `Bash`" |
| `trade-analysis` | `research-agent.md` | routing table — "invoke via `Bash`" |

None has ever been committed: `git log --all -- templates/skills/<name>` is empty for all
six, and `find … -name emit_event.py` returns nothing. The last three are not even from this
domain — `find-context-candle` and `trade-analysis` are trading-system skills, inherited when
`research-agent` was copied in from another project and never reconciled against this
package's skill set.

**Why this is the gate, not the artifacts.** Six independent authors, across at least three
epics, each wrote a reference to a skill that was not there, and the build printed a success
banner every time. `build_phases.py:1970-1990` *does* fail the build on an unresolvable skill
id — but it resolves only the `skills_invoked` **registry field** in `agent_registry.json`.
Every one of these six is declared in **Markdown prose inside a template body**, which no
validator reads. So the check covers the declaration form that is mechanically generated and
rarely wrong, and ignores the form a human hand-types — the one that actually rots.

The failure is uniform because the callers are uniform: each reference site treats "skill not
found" as a pass. `signoff` §7 is the widest blast radius, since every phase agent runs it on
every sign-off:

```text
This step is **mandatory** — skipping it is a protocol violation. If `route-learning` or
`capture-learning` are unavailable, log a warning and proceed (do not block sign-off).
```

Declared mandatory, then handed an unconditional escape hatch — so the escape hatch is the
only reachable path. PO v3, BA v3 and IT PO v3 each carry their own copy of the shape ("if
not found, log … and stop"). The eight `agent-telemetry` calls in `building-epics/SKILL.md`
fail per-command inside a supervisor that does not check their exit status. Net effect: the
post-execution half of `docs/architecture/agent_knowledge_system.md` has never run, and the
epic runbook has never emitted a telemetry event — while every agent reports a clean sign-off.

This is very likely the mechanism behind the pre-drive-checklist story in `CLAUDE.md`
("23 `submit-failed` events occurred without detection — the drive completed but zero
telemetry was captured, making the retrospective impossible"). That was diagnosed as an
unreachable sink; an `emit_event.py` that does not exist produces the same symptom.

**Evidence.** `scripts/check_skill_refs.py` resolves every prose skill path against the real
directory set. On the tree that recorded this issue:

```text
$ python3 scripts/check_skill_refs.py
FAIL: 21 imperative reference(s) to 6 skill(s) that do not exist in templates/skills/.
  'agent-telemetry'      (8 references)  templates/skills/building-epics/SKILL.md
  'capture-learning'     (4 references)  signoff/SKILL.md, PO v3, BA v3, IT PO v3
  'find-context-candle'  (1 reference)   templates/agents/research-agent.md
  'import-scanner'       (1 reference)   templates/agents/research-agent.md
  'route-learning'       (6 references)  signoff/SKILL.md, README.md, PO/BA/IT-PO, retrospective
  'trade-analysis'       (1 reference)   templates/agents/research-agent.md
```

A naive scan also flags a seventh name, `create-ac` — the control case worth keeping in mind.
It was correctly retired into `plan-feature` (#184, `3aeb9298`), and the surviving mention at
`plan-feature/SKILL.md:560` sits inside a `DECISION HISTORY` comment recording that migration.
A gate that fails on it would be failing on accurate history. Two discriminators separate the
classes, and `check_skill_refs.py` applies both: HTML comment blocks are stripped before
scanning, and a reference only fails if its line is **imperative** (`Load …`, `python …`,
"invoke via Bash") rather than descriptive.

**Fix direction.** The gate now exists — `scripts/check_skill_refs.py`, added with this entry.
It is not yet wired into CI or the build, so it currently only fails when run by hand. Wire it
in as a required check (or as a `build.py` validation phase alongside the `skills_invoked`
resolution it complements) — the same posture `skills_invoked` already has, applied to the
declaration form that is actually used. That is what converts all six from silent runtime
no-ops into a build error, and stops the seventh being written.

Then resolve the instances: retarget `route-learning` at `route-knowledge` (which exists and
already describes itself as the caller-friendly variant — see its `:474-511` table, written
as though both halves shipped), decide whether `capture-learning` and `agent-telemetry` are
authored or dropped, and delete the three trading-domain rows from `research-agent`. Remove
the fail-open clauses in the same change — a mandatory step that warns and proceeds is
indistinguishable from an absent one, and is what let this survive for the life of the
feature.

**Trap.** The complaint arrives as a consumer-install packaging bug and reads exactly like
KI-BP-006 — a module missing from a deploy list. Auditing `build_skills` and the deploy
manifest finds nothing, because nothing there is wrong. Confirm the artifact exists in
`templates/` before investigating why it did not arrive. And do not stop at the two skills the
customer named: the reporter sees whichever dangling reference their workflow happened to
touch, never the class.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2's inverse. Source and deployed
layout agree perfectly; both are missing the same file, and every consumer of it treats
absence as a pass.

---

### KI-BP-008 — A version gate can skip the entire workflow-install phase and still report a successful build, leaving every deployed workflow silently stale

> **RE-VERIFIED 2026-08-25 — LIVE.** On a scratch adopter I truncated
> `.leafcutter/workflows/fast-lane-ship.js` to one line (source: 1047) and rebuilt with
> `CLAUDE_CODE_VERSION=2.0.100`. Result: exit 0,
> `[WARNING] Claude Code >= 2.1.154 required for workflow scripts. Detected: 2.0.100. Skipping.`,
> then `Stale file cleanup: (no stale files found)` — and the file still one line. The gate
> was driven through the env var read at `build_phases.py:684`, which feeds the identical
> comparison as the `claude --version` probe, so the branch under test is the same one. The
> skip is `build_phases.py:708-713` (`print(...); return 0`).
>
> **Do not "fix the version parse" as the remedy.** The fragile last-token parse at `:693`
> currently falls through to the fail-open branch at `:715-719`
> (`[WARNING] Claude Code version unknown. Installing workflow scripts (fail-open).`), which
> fired on every unforced run in this workspace — it is the only reason workflows install
> here at all. Correcting the parse converts a working fail-open into a clean, silent skip
> and makes this defect *more* dangerous. The safe fix is content comparison (BP-1500c),
> which needs BP-1500d's manifest first. Fix the parse after that, or not at all.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 2
- **First seen:** 2026-08-24 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py` — the workflow-scripts install phase, lines ~683-720;
  and (second occurrence) the breaking-change gate in `scripts/build.py`

**Second occurrence, 2026-08-25 — same outcome, a completely different cause, and the cause is
arguably worse.** Before driving a ticket I checked the deployed driver against source:

```text
.leafcutter/workflows/build-feature.js   919 lines
templates/workflows-js/build-feature.js  2416 lines   (origin/main)
```

1497 lines behind — predating essentially a month of hardening. Had the drive run, it would
have executed that driver.

The version gate was not involved. `build.py` had been **halting on an unacknowledged
breaking-change gate since 2026-08-18** — the `GE-113c-3` security-allowlist entry — and
refusing to proceed without `--force-breaking`:

```text
  BREAKING CHANGES DETECTED — BUILD HALTED
  [2026-08-18] fix(security-scanner): allowlist basename matching over-suppressed ...
  To proceed after reviewing the steps above, re-run with:
    python build.py --force-breaking
```

That gate did its job: it stopped, loudly, and printed migration steps. The defect is that
**nothing connects "the build halted" to "the deployed tree is therefore now stale."** The halt
is a single event, noticed once by whoever ran it; the staleness is a standing condition that
then persists silently for a week while every workflow run uses the old code. A halted build
leaves exactly the same deployed state as a skipped phase, and neither is reported at *use*
time.

This widens the issue: the register's original framing is about one `return 0` in one phase.
The general statement is that **the deployed tree has no freshness signal of any kind** — not
after a skipped phase, not after a refused build, not after no build at all. Any fix scoped only
to the version gate leaves the breaking-gate route live, and vice versa.

Reproduced end to end: `--force-breaking` brought the deployed driver to 2416 lines, byte-equal
to source, and the subsequent drive ran the current code.

**First occurrence (version gate) follows.**

**Symptom.** The phase probes `claude --version` and compares against
`_MINIMUM_VERSION = "2.1.154"`. When a version is detected and is below the minimum, the
phase prints a `[WARNING]` and `return 0` — deploying nothing. `return 0` is the same
"files written" count a genuinely no-op build returns, so the overall build reports
success. Every deployed workflow keeps whatever content it had, indefinitely, while each
subsequent build says everything is fine. "Stale file cleanup" does not catch it: that
step looks for orphaned files, not out-of-date ones.

**Evidence.** Observed live. `.leafcutter/workflows/fast-lane-ship.js` was **620 lines
against 1047 in source** — 427 behind, with `grep -c "pr-reviewer"` returning `0` on the
deployed copy and `6` on the source. The deployed copy predated PR #485 entirely: no
review phase, no changelog phase. A fast-lane run launched against it therefore executed
the pre-#485 lane, resolved a five-AC set instead of one, and built two criteria against
a superseded spec. Re-running `build.py` from the main checkout in the same environment
installed the current file immediately, so the source was never the problem.

**Why the same environment behaved differently between runs.** The probe is
`subprocess.run(["claude", "--version"], timeout=2)` and parses
`result.stdout.strip().split()[-1]` — the **last** token. On output shaped like
`2.1.154 (Claude Code)` that yields `Code)`, which fails `Version()` parsing, sets
`version_known = False`, and takes the documented fail-open path that installs. So the
fragile parse fails *safe*. The dangerous branch is the one that works: a cleanly parsed
version below the minimum silently skips. A 2-second timeout on an external binary also
means the two paths can alternate between runs on the same machine.

**Why it matters beyond this workspace.** A consumer on an older Claude Code gets this
permanently and invisibly: every `build.py` reports success, and their agents keep running
whatever workflow scripts were deployed the day the gate started tripping. There is no
warning at *use* time, only at build time, in a line that reads like an advisory.

**Fix direction.** A skipped mandatory phase is not a successful build. At minimum,
distinguish "installed 0 because there was nothing to install" from "installed 0 because I
refused", and make the second non-zero or loudly summarised at the end of the build rather
than mid-scroll. Better: record the deployed workflow's source revision (the build manifest
already tracks output mappings) and have the build compare content, so a stale deployed
file is reported as drift regardless of why it was skipped — the same defence KI-BP-005
needs for orphans, in its out-of-date form. Also worth fixing the version parse to take the
first token rather than the last, though note that bug is currently what keeps this
workspace working.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in its stale form — the deployed tree holds an older
version of something the source has moved on from.

**Related.** KI-BP-010 is the cleanup-side counterpart for this same `workflows/` directory:
its `--clean` entry has never executed, so nothing reaps what this phase declines to rewrite.

KI-BP-20260826-1331 is the **write-side twin**: the identical stale-workflow symptom (same file, same
missing review and changelog phases) reached on 2026-08-25 by a build whose install phase ran
fail-open and wrote older bytes from a stale worktree, rather than by this entry's skip
branch. Counted separately because a skipped-phase alarm would not fire on it — but the
source-revision stamp proposed in the fix direction above resolves both, and is the reason to
prefer it over merely making the skip loud.

---

### KI-BP-009 — `.claude/skills/` is symlinked wholesale to the generated tree, so an adopter's own skills have nowhere to live and `--clean` targets them

> **RE-VERIFIED 2026-08-25 — LIVE, and worse than recorded. Severity should rise.**
> The entry marked the deletion as *code reading, not empirically confirmed*, because
> `--clean` has no dry-run path. It is now confirmed. On a scratch adopter I placed
> `adopter-prod-deploy/SKILL.md` under `.leafcutter/skills/` and ran a `--clean` build:
> `Removing stale artifact: .../.claude/skills/adopter-prod-deploy`, and the directory was
> gone. It deletes through the symlink via the `rmtree` branch, exactly as predicted.
>
> **The new finding is more serious than the `--clean` case.** I then tried the obvious
> adopter workaround — replace the symlink with a *real* `.claude/skills/` directory — and
> ran an **ordinary build with no flags**. Output: `✓ removed stale: .claude/skills`, then
> `shim: .claude/skills -> skills (symlink)`. The adopter's directory was gone. `.claude/skills`
> is in **both** `_PRE_CONSOLIDATION_PATHS` (`build.py:1189`) and `shim_map`
> (`build_helpers.py:331`), so `_cleanup_stale_paths` `rmtree`s any real directory there and
> the shim then replaces it — on every build, reported with a **green checkmark**.
>
> So the adopter has no safe placement at all: inside the symlink, `--clean` reaps it;
> outside it, the default path reaps it. This is no longer "nowhere good to put it" — it is
> "the build deletes your work and calls it success."
>
> Same constant confirms KI-BP-010: `_MANAGED_ARTIFACT_DIRS["workflows"] = ".claude/workflows"`
> is joined as `claude_dir / subdir_name`, yielding `<target>/.claude/.claude/workflows`. The
> `--clean` run touched no workflow.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** the shim-install step (`scripts/build.py` `_install_shims`) ·
  `scripts/build_phases.py:2820-2825` (`_MANAGED_ARTIFACT_DIRS`) and `:2828-2880`
  (`clean_stale_artifacts`) · `scripts/build.py:1202-1236` (`_build_source_manifests`)
- **Reported by:** adopter repo DIAGraph (`roche-sandbox/dia-graph`), against pin `54356a92`

**Symptom.** `build.py` installs `.claude/skills` as a **symlink into the package's own
output tree**:

```text
.claude/agents  -> ../.leafcutter/agents
.claude/hooks   -> ../.leafcutter/hooks
.claude/skills  -> ../.leafcutter/skills
```

Claude Code discovers project skills only at `.claude/skills/`. Because leafcutter owns that
entire directory, an adopter's own skills have **no location that is both discoverable and
outside the generated tree**. The only way to have a working project-local skill is to put
it somewhere the package documents as build output. DIAGraph did exactly that — four
adopter-owned skills (`prod-deploy`, `create-slides`, `diagraph-mcp`, `gen-ui-library`) live
in `.leafcutter/skills/` and exist in no `templates/skills/` anywhere.

**Why that placement is unsafe.** `clean_stale_artifacts` iterates `<target>/.claude/skills/`
— following the symlink into `.leafcutter/skills/` — and removes anything whose base name is
absent from the manifest:

```python
for item in sorted(managed_dir.iterdir()):
    if item.name not in expected_names:
        print(f"Removing stale artifact: {item}")
        if item.is_dir() and not item.is_symlink():
            _shutil.rmtree(item)
```

`_build_source_manifests` populates `skills` from `templates/skills/` subdirectory names
only, so every adopter skill matches the removal condition and is a real directory, not a
symlink — the `rmtree` branch. `--clean` should therefore delete all four.

**Confidence.** Code reading, **not empirically confirmed** — the reporter declined to run
it, and rightly: `clean_stale_artifacts` takes no `dry_run` parameter and `--clean`
(`build.py:1476`, dispatched at `:1684-1685`) has no dry-run path, so the only way to observe
the behaviour is to perform it. Confirm on a scratch copy before treating the mechanism as
settled. **The placement problem stands regardless of how the deletion question resolves.**

Mitigating factor: those files are git-tracked in the adopter repo, so a deletion shows up in
`git status` rather than vanishing. That is the only thing separating this from their
`site/middleware.ts` incident, where an untracked file disappeared silently and left
production ungated for two weeks.

**A second, independent defect in the same function, found while verifying** — a doubled path
segment that has made clean-mode's `workflows` entry unreachable since it was added. Filed
separately as **KI-BP-010**, where it can be picked up on its own.

**Correction, 2026-08-25.** An earlier revision of this paragraph claimed the typo was
"load-bearing" because `_build_source_manifests` returns no `"workflows"` key, so fixing the
path alone would delete every deployed workflow. **That is wrong.** The key exists —
`scripts/build.py:1246-1258` populates it from `templates/workflows-js/*.js`. The manifest
side is correct and the entry is simply never consulted, so repairing the path is safe and is
the fix, not a hazard. The mistake mattered in the one direction that costs something: it
argued for leaving a broken cleanup step alone. Corrected in KI-BP-010, which carries the
verified analysis.

**Confidentiality angle worth flagging.** `prod-deploy/SKILL.md` in the reporting repo holds
Roche sandbox infrastructure detail — subscription name, ACR name, Container App names,
FQDNs. Leafcutter ships an `add-skill-to-package` skill whose stated purpose is promoting
project-local skills *into* the shared package. Run against that skill, it would publish
that detail into a repo owned outside the adopter. Adopter skills need a home that is
structurally outside the promotion path, not merely one nobody has promoted yet.

**The concept already exists in the code; the layout contradicts it.**
`build_phases.py:1930` computes `project_skills_dir = target_root / ".claude" / "skills"` and
`:2020` uses it as `in_project = (project_skills_dir / skill_id).exists()` to decide whether
a skill is project-local. Under the symlink that predicate can never distinguish anything —
every package skill is "project-local" and every project skill is inside the package output.

**Fix direction.** Symlink **per skill** rather than symlinking the parent. `.claude/skills/`
becomes a real directory holding one symlink per package-provided skill; `clean_stale_artifacts`
then only removes symlinks it created, and adopter directories are structurally untouchable
rather than protected by a list someone has to maintain. It also makes the `in_project`
predicate at `:2020` mean what it says.

Smaller fallback if per-skill symlinking is too large: have `clean_stale_artifacts` read an
allowlist (e.g. `skills_config.json` → `project.owned_skills`) and never remove listed names.
That is strictly weaker — it protects skills someone remembered to declare — but it is a
same-day change.

Either way, give `--clean` a dry-run path. A destructive mode whose only observation method
is to run it destructively cannot be verified by the people most at risk from it.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2, in its ownership form: the
deployed tree and the adopter's tree are the same directory, so the package cannot tell its
own output from someone else's source.

---

### KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean`

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py:2820-2825` (`_MANAGED_ARTIFACT_DIRS`), `:2859-2864`
  (the join in `clean_stale_artifacts`)

**Symptom.** `_MANAGED_ARTIFACT_DIRS` mixes two path conventions in one dict. Three entries
are bare subdirectory names; the fourth carries a `.claude/` prefix:

```python
_MANAGED_ARTIFACT_DIRS = {
    "agents": "agents",
    "skills": "skills",
    "hooks": "hooks",
    "workflows": ".claude/workflows",
}
```

The consumer joins the value onto `claude_dir`, which is *already* `<target>/.claude`:

```python
claude_dir = target_dir / ".claude"
...
managed_dir = claude_dir / subdir_name        # <target>/.claude/.claude/workflows
if not managed_dir.exists():
    continue
```

That path never exists, so the loop `continue`s every time and clean-mode has **never**
cleaned workflows — silently, since the function only prints when it removes something or
when the total is zero.

**The manifest side is fine, and this correction matters.** `_build_source_manifests`
(`scripts/build.py:1246-1258`) *does* populate a `workflows` key, from
`templates/workflows-js/*.js`. An earlier draft of this finding — which reached `main` inside
KI-BP-009 via `#520` — asserted the opposite: that no such key exists, that `expected_names`
would therefore be empty, and that repairing the path would delete every deployed workflow on
the first `--clean`. That was wrong, and wrong in the expensive direction: it recommended
leaving a broken cleanup step in place. Repairing the path is safe.

**Evidence — there is a real orphan it should have caught.** In the self-hosted workspace
`.leafcutter/workflows/` holds **ten** files while `templates/workflows-js/` holds **nine**.
The extra one is `pause-resume-substrate.js`, which has no template and is claimed by
nothing:

```text
$ ls <package>/templates/workflows-js/ | wc -l
9
$ ls <workspace>/.leafcutter/workflows/ | wc -l
10
$ ls <package>/templates/workflows-js/pause-resume-substrate.js
No such file or directory
```

It is exactly the artifact the `workflows` entry was added to remove, and it survives every
`--clean` while the run reports success. This is a live instance of KI-BP-005 that the
mechanism intended to catch it cannot see.

Found while verifying KI-BP-009, not by any failure report — nothing surfaces it, because a
no-op cleanup and a genuinely clean tree produce identical output.

**Related — the other half of the workflows story.** KI-BP-008 records a *deploy* path that
can silently skip the workflow-install phase, leaving deployed workflows stale. This entry
records the *cleanup* path for the same directory never running at all. Between them,
`.leafcutter/workflows/` has neither a reliable writer nor a working reaper, and both failure
modes print success. Whoever fixes either should read the other first.

**Relationship to KI-BP-009.** Same function, same `--clean` invocation, distinct defects with
distinct fixes: BP-009 is about *whose files* clean-mode is entitled to touch; this is about a
path it cannot reach. Sequence them deliberately — repairing this one activates a code path
that BP-009 shows is unsafe for any directory an adopter also writes into. Workflows are not
currently such a directory, so the two are separable here, but only by accident of which trees
adopters happen to use.

**Fix direction.** Normalise the dict to one convention — all values relative to `.claude/`,
or all absolute from `target_dir` — and add a test that asserts every entry resolves to a real
directory in a freshly built target. A dict where three entries follow one rule and the fourth
follows another is the actual defect; the unreachable path is just where it surfaced first.
Then confirm the orphan is removed rather than assuming it: run `--clean` on a scratch target
and check `pause-resume-substrate.js` is gone.

While in there, decide whether `pause-resume-substrate.js` is dead or whether its template was
lost — clean-mode deleting it is only the right outcome if the answer is "dead".

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 — a step that checks less than it
claims to and reports success.

---

### KI-BP-011 — `.build_manifest.json` is written to the package that ran the build, not the target install it describes, so it is not portable to any consumer install

- **Severity:** high
- **Status:** open — AC: BP-1500d
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_helpers.py:185` (manifest write target); `:83`, `:95-96`
  (`output_mappings` keying); `:193-195` (manifest key relativization)

**Second occurrence, 2026-08-25 — reached from a git worktree, and it blocked a commit.** A
phase agent ran `build.py --target-dir <worktree>` inside a worktree whose `.leafcutter` was a
symlink to the workspace parent's, per the bootstrap `CLAUDE.md` recommends. Two things
followed. The deploy went *through* the symlink into the parent's `.leafcutter`, and the
manifest written carried **no `output_mappings` at all** — the target sits under
`.../worktrees/`, which is not a subpath of the package, so the same `UserWarning` this entry
already documents fired and the mapping was silently dropped.

The consequence was not theoretical. On the next commit, `check-build-drift` read that manifest
and reported **every template in the repository** as unregistered:

```text
UNCOMPARABLE: GAP templates/agents/README.md action=run build.py to register it
UNCOMPARABLE: GAP templates/agents/ac-validator.md action=run build.py to register it
... (one line per template)
```

The commit contained no template change whatsoever — only a changelog entry and two AC YAML
files. Recovery was to re-run the canonical `build.py --target-dir .` from the workspace parent,
which regenerates a manifest that does have `output_mappings`.

**What this adds to the entry.** The original framing is about portability to a *consumer*
install. This shows the same defect reached from the package's own recommended worktree
workflow, where it is not merely unportable but actively corrupting: a worktree-targeted build
overwrites the shared parent manifest with one that no gate can use. Any fix should treat
"target is a worktree of this repo" as a first-class case, not an exotic one — `/feature`,
`worktree-agent` and `building-epics` all create worktrees by design.

**Symptom.** The build's own record of what it wrote is not written to the install it
describes. `scripts/build_helpers.py:185` computes
`manifest_path = package_root / ".build_manifest.json"` — always the package's own
directory, never `--target-dir`. Running `python3 scripts/build.py --target-dir
/tmp/lc_probe2` printed `build manifest (61 template + 0 output_mappings entries) ->
/home/henzeh/projects/leafcutter/worktrees/bp900-deploy/.build_manifest.json`, and
`/tmp/lc_probe2` — the actual target — contained no manifest at all. Consequence:
`check_output_drift.py` and `check_build_drift.py`, which both read this file to detect
drift, have nothing to read in a consumer install. Both guardrails are **absent**, not
degraded, in that install.

**Evidence — a consumer build overwrites the package's own baseline, violating
BP-1500a.** Because the write target is always the package, building into another
project rewrites the package's own manifest with data about that OTHER build. Verified
immediately after the run above: the package's own `.build_manifest.json` then reported
`output_mappings: 0, templates: 0`. It is gitignored, so the corruption is invisible —
nothing shows in `git status`. BP-1500a is the existing acceptance criterion that "a
build leaves the repository it is run from exactly as it found it"; this is a live
violation of that guarantee, not a newly discovered one.

**Evidence — `output_mappings` cannot be computed for a foreign target, and the build
fails open.** `scripts/build_helpers.py` lines 83 and 95-96 key entries via
`output_path.relative_to(package_root.parent)`, which raises `ValueError` whenever the
target sits outside that parent — true of essentially any real consumer install.
Observed:

```text
[WARNING] could not compute output_mappings: '/tmp/lc_probe2/agents/README.md' is not
in the subpath of '/home/henzeh/projects/leafcutter/worktrees'. Direction B detection
will be unavailable until next build.
```

The build then reports success and exits 0 — it fails open, exactly the shape this file
already documents in KI-BP-008.

**Evidence — manifest keys carry a non-portable prefix.** Lines 193-195 key by the same
`relative_to(package_root.parent)`, so keys read `leafcutter-ai/templates/agents/x.md`
from the canonical checkout but `bp900-deploy/templates/agents/x.md` from a worktree
named `bp900-deploy`. Observed directly in this worktree's own manifest: every top-level
key is prefixed `bp900-deploy/templates/agents/...`, and the `templates` count reads 0
because the reader looks for a `templates` key in a shape the writer never produced in
this layout.

**Root cause.** All four symptoms above trace to one assumption: every path is resolved
relative to `package_root.parent`. That holds only inside this repo's own self-hosted
workspace layout (a `leafcutter/` workspace parent containing `leafcutter-ai/`) — it
breaks for any real consumer install, where the target sits outside that parent
entirely, and for any worktree not laid out identically to the canonical checkout.

**Why this matters — BP-1500c has no record to check.** BP-1500c ("report drift against
the record of what a build wrote") has this defect as a hard prerequisite: you cannot
report drift against a manifest that was never written to the install being checked.
Same failure family, one layer deeper, as BP-016 / BP-017.

**Fix direction.** Anchor the manifest write target, and every path computed relative to
it, to something that holds for an arbitrary consumer install — e.g. write
`.build_manifest.json` into the actual `--target-dir`, and key/relativize entries
against that target root (or the package root itself) rather than
`package_root.parent`.

**AC.** BP-1500d
(`docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500d.yaml`) is
authored against this defect.

---

### KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py:1928` (`registry_path` used by the self-description
  validator), `:1863` (docstring naming the same path), `:62` (`REGISTRY_PATH`, the
  source-side constant the build reads from) · `.leafcutter/workflows/plan-feature.js:1749`
  (the deployed workflow's own registry read)

**Symptom.** A consumer install has `agent_registry.json` at neither path the codebase
actually uses — and the build's own validation cannot detect that, because the only layout
it has ever run in is the one where the check is structurally incapable of failing.

**Mechanism.** `build_phases.py:1928` computes `registry_path = target_root / "config" /
"agent_registry.json"` and validates the registry there; the docstring at `:1863` describes
the same path as holding the required registry fields. Nothing in the build ever *copies*
`config/agent_registry.json` to `target_root / "config" /`. A grep of `build_phases.py` for
the filename returns only the source-side constant, the validation read, doc comments, and
error-hint strings — no write:

```text
$ grep -n "agent_registry.json" scripts/build_phases.py
10:    agent_registry.json and passes it + the skills_root to
62:REGISTRY_PATH = PACKAGE_ROOT / "config" / "agent_registry.json"
465:    Registry injection (ticket 29): loads ``agent_registry.json`` once and passes
1863:    in ``target_root / "config" / "agent_registry.json"`` for required registry
1928:    registry_path = target_root / "config" / "agent_registry.json"
2005:                        f"  Fix hint: Add '{field}' to the agent's entry in config/agent_registry.json."
2072:            "Set self_description_enforcement='error' in config/agent_registry.json "
2124:    registry entry from ``config/agent_registry.json``, calls
2907:#   agent_registry.json once per phase call and passes agents, registry_path,
```

In the self-hosted layout this validation passes trivially, because `target_root/config/` IS
the package's own source `config/` directory — the same file `REGISTRY_PATH` reads from. The
check has therefore never been meaningful in the one place it has ever run: it validates the
source against itself.

Meanwhile the deployed `/plan-feature` workflow reads the registry from a *different*
location. `.leafcutter/workflows/plan-feature.js:1749` runs
`"cat .leafcutter/config/agent_registry.json\n"`. So `build_phases.py` expects
`<target>/config/agent_registry.json` and the deployed workflow expects
`<target>/.leafcutter/config/agent_registry.json` — and nothing in the build populates
either path in a real consumer install (see KI-BP-003's fourth occurrence: `.leafcutter/config/`
deploys only `commit_guardian` and `feedback_categories.yaml`).

**Consequence.** A consumer install has the registry at neither path. The build's own
validation cannot catch this, because in the only layout where it runs — self-hosted — it is
reading the package's source copy, not a deployed one, so it reports success regardless of
whether either deployed path is populated.

**Relationship to other entries.** Same root-cause shape as KI-BP-003 (see that entry's
fourth occurrence): `config/` is not deployed. Both are unfixed instances of the rule
`BP-900g-8-ii` already states — "the deployed-dependency closure covers the data and
configuration files a script reads, not only the modules it imports." `KI-BO-018` (in
`docs/known-issues/build-orchestration.md`) is a related but distinct failure one layer up:
`/plan-feature`'s registry read there succeeds only *incidentally*, because the process
working directory happened to be the workspace parent that holds a populated `.leafcutter/`
— the same non-portable assumption, caught in the one case where it happens to resolve.

**Fix direction.** Anchor the validator's `registry_path` and the deployed workflow's read to
the same, actually-deployed location, and make the build copy `config/agent_registry.json`
there. Until then, do not trust a passing self-hosted validation run as evidence that a
consumer install's registry is reachable by anything that runs against deployed output.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in a validates-against-itself sub-form: the only layout
the check has ever run in is the one where target and source are the same directory, so it
has never been able to fail.

---

### KI-BP-013 — The mypy gate checks only changed files, so untouched debt is invisible until an unrelated edit drops a wall of it on whoever touched the file

- **Severity:** low
- **Status:** open — the gate is informational, so this costs attention rather than merges
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the `Type-check changed files (mypy, informational)` job in `.github/workflows/ci.yml`

**Symptom.** The job type-checks the files a PR changed. A file that has never been changed
since the job was introduced has never been checked, however much it violates. The first commit
to touch it — for any reason, of any size — inherits every accumulated error as a red check on
its own PR.

**Evidence.** PR #541 changed **two lines** in
`unit_tests/build_orchestration/test_bo2400f_lifecycle.py`: a `chmod` widened from a file to its
containing directory, plus the matching restore in `finally`. The mypy job went red with **22
errors**, all `"None" not callable`, at lines scattered from 324 to 1366 — nowhere near the
edit.

Confirmed pre-existing rather than introduced, by running mypy against `origin/main`'s
unmodified copy of the same file:

```
$ git show origin/main:unit_tests/build_orchestration/test_bo2400f_lifecycle.py > /tmp/main_copy.py
$ mypy /tmp/main_copy.py --ignore-missing-imports
Found 22 errors in 1 file (checked 1 source file)
```

Same 22. Meanwhile mypy is green on `main` itself, because `main` never changes that file.

**Why it matters more than the severity suggests.** The signal is anti-correlated with
responsibility: the person who least touched the file gets the whole report. The rational
response is to shrug, and shrugging at a red check is a habit worth not building — especially on
a job that would otherwise be a useful early warning. It also makes the gate useless as a ratchet:
debt cannot decrease, because nothing ever forces a file to be looked at.

**Related shape.** `KI-CG-015` and `KI-CG-012` describe the same "invisible until touched"
property in the AC-schema hooks, where the consequence is worse because those gates are blocking.
This is the same design choice with a softer landing.

**Fix directions.** Either run mypy over the whole tree with a baseline file (so existing errors
are recorded and only *new* ones fail — the standard ratchet), or keep changed-files scoping but
report pre-existing errors separately from ones the PR introduced, so the diff-attributable count
is visible at a glance. The second is cheaper and preserves the current signal; the first
actually retires the debt.

---

### KI-BP-014 — The commit agent can stall indefinitely waiting on the autofix agent it dispatched, leaving a fully-staged commit unmade and no error

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the pre-commit-failure → `precommit-autofix` → retry path in the `commit` agent template

**Symptom.** The commit agent hit a `check-ac-schema` failure, dispatched the autofix agent as
designed, and then never retried. It returned after **~76 minutes** with the message *"HEAD
confirmed unchanged (commit did not silently land). Waiting for the autofix agent to complete
before retrying."* — a status update, not a result. The autofix agent had in fact completed
successfully and applied a correct one-line fix.

**State it left behind.** Benign but easy to misread: all five intended files correctly staged,
`HEAD` unchanged, nothing lost. The agent's own report was accurate about what it had *not* done,
which is the reason nothing broke. But no commit existed, no error was raised, and the caller had
no signal other than the elapsed time.

**Why it is worth an entry.** The failure mode is a hang, not a crash, so nothing surfaces it —
no timeout, no failed status, no retry cap. From the caller's side it is indistinguishable from
"still working" for as long as you are willing to wait. Recovery was trivial once noticed
(re-run the hooks, confirm they pass, commit from the main loop with `COMMIT_AGENT_MODE=1`), but
noticing depended on a human wondering why it was taking so long.

**What this does NOT indicate.** The autofix path itself worked: the fix was correct and its
report was accurate and well-reasoned. The gap is purely in the parent's wait-and-retry step.

**Fix direction.** Bound the wait and make the outcome explicit. The parent should either
re-check the hooks and retry once the child reports completion, or return a `blocker` naming the
autofix agent and the hook that failed. "Waiting" is not a terminal state a caller can act on.

---

### KI-BP-015 — `docs/agents/cards/*.card.md` are committed build outputs with no freshness gate, so they drift from the AC store they describe

- **Severity:** low
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `docs/agents/cards/`, generated by `scripts/generate_agent_cards.py` and run as part of `build.py`

**Symptom.** The cards list the acceptance criteria each agent is assigned. They are generated
from the AC store, committed to the repo, and regenerated only when someone happens to run
`build.py`. A PR that adds ACs does not regenerate them, and no hook or CI job compares the
committed cards against the store — so `main`'s cards silently fall behind `main`'s own store.

**Evidence.** Running `build.py` into a fresh worktree taken from `origin/main` at `3f3a6a3e`
— changing nothing else — left four cards modified, 63 added lines, purely additive:

```
docs/agents/cards/python-coder.card.md              +52
docs/agents/cards/documentation-expert.card.md       +8
docs/agents/cards/architecture-diagram-author.card.md +2
docs/agents/cards/frontend-coder.card.md             +1
```

The additions are ACs that are already on `main`: `BO-2400c-6`, `-6-i`, `-6-ii` (merged in
#529/#536) and the `BO-2400f-12` and `BO-2400f-13` families (merged in #534). Their PRs added the
records without regenerating the cards, and every gate passed — including `Check Agent Diagrams`,
which validates card *structure* rather than card *currency*.

**Why it is low and not lower.** Nothing breaks. But these cards are a knowledge-plane surface:
they are what an agent reads to learn which criteria it owns. A card that omits three criteria an
agent is assigned is quietly wrong at exactly the moment it is being trusted, and the omission
grows with every AC-adding PR.

**Not fixed here deliberately.** Regenerating them is one `build.py` run, but doing it inside an
unrelated PR buries a 63-line generated diff in a review about something else — and it would
repair this instance without preventing the next one.

**Fix direction.** A CI check that regenerates the cards and fails if the working tree changes
(the standard generated-artifact ratchet, and the same shape as the existing
`Check Product-Truth Derived-Data Drift (generator --check)` job, which already does exactly this
for a different generated surface). Alternatively stop committing them and generate on demand —
but they are read by agents from the deployed tree, so the ratchet is the smaller change.

**Occurrences 2 and 3 (2026-08-25, later the same day).** Reproduced twice more at a newer
`origin/main`, in worktrees `knowledge-harvest-wiring` and `fastlane-ki-findings` — the same four
cards, dirty immediately after `setup_ticket_worktree.py` bootstrap with no agent having run. A
third instance in the `inf-400c-2-ii` fast-lane worktree carried seven files (the four cards plus
`llm-expert` and `test-writer`, plus `docs/INDEX.md`). So the drift is not a one-off snapshot: a
bootstrapped worktree is dirty from birth, every time.

**Raises the ceiling on this entry's severity via `KI-BO-029`.** The rating of `low` rests on
"nothing breaks, the cards merely drift". That holds for the drift itself, but the fast lane
stages with `git add -A`, so this churn is swept into fast-lane pull requests automatically —
under a generated commit message that cannot describe it. The drift then gets repaired at random
intervals by PRs that never mention it, which is harder to reason about than steady staleness.
See `docs/known-issues/build-orchestration.md` → `KI-BO-029`. Fixing either side defuses the
other; the cheapest single change is `git restore docs/agents/cards/` at the end of bootstrap,
which is already this file's prescribed manual workaround at line 162.

---

### KI-BP-020 — `_ac_components.py` is missing from the AC-store deploy map, so the deployed `validate_ac_schema.py` crashes on import — and it is the command CLAUDE.md tells consumers to run

> **Numbering note.** Filed as KI-BP-016 and renumbered to 020 at merge: `main` published its
> own KI-BP-016 (the `docs_root` index defect, below) plus 017-019 while this branch was in
> review. The free number was re-read against `origin/main` at the moment of landing, per the
> standing instruction — which is the only reason this was caught rather than shipped as a
> duplicate. `KI-BO-024` records the same collision class reaching `main` undetected on this
> date, and argues the convention needs a mechanical duplicate check rather than another
> paragraph. Physical position kept where the merge left it rather than moved to the end, so
> the surrounding history stays legible.

- **Severity:** high — the documented store-hygiene command is dead in every consumer layout
- **Status:** open
- **Occurrences:** 1 (second occurrence of this defect *class* — see below)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py` — `build_ac_store`'s hardcoded `deploy_map`, against
  `scripts/ac_store/validate_ac_schema.py:45`

**Symptom.** The deployed validator raises on import, before it can check anything:

```
$ python <target>/.leafcutter/scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/ac-store
Traceback (most recent call last):
  File ".../.leafcutter/scripts/ac_store/validate_ac_schema.py", line 45, in <module>
    from _ac_components import components_field_errors, load_registry_ids
ModuleNotFoundError: No module named '_ac_components'
```

**Evidence.** Reproduced by running the deployed copy, not inferred. `validate_ac_schema.py:45`
imports `_ac_components` at module scope; `grep -n "_ac_components" scripts/build_phases.py`
returns **nothing**, so the module is never deployed; and `ls` of a freshly built
`.leafcutter/scripts/ac_store/` lists 18 files with `validate_ac_schema.py` present and
`_ac_components.py` absent. The build was run from this repo at `origin/main` immediately
before the reproduction, so this is the current state of the shipped artifact.

**Why the repo's own CI does not catch it.** Nothing in `.github/workflows/` invokes
`validate_ac_schema.py` — the required "AC store valid" job runs the commit-guardian hook
`check_ac_schema.py`, which is deployed by a whole-directory rglob and therefore unaffected. In
*this* repo `scripts/` is source, so every local run imports the module that sits beside it and
succeeds. The failure is only reachable from the deployed tree, which this repo never exercises.

**Who it actually breaks.** In a consumer install `scripts/` **is** the deployed output. The
root `CLAUDE.md`, under "AC-store hygiene — bulk pre-flight before a finalization drive",
instructs precisely:

```bash
python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/<component>
```

So the documented defence against store rot is not merely unreliable in a consumer project — it
cannot start. That instruction has a history of being wrong in the other direction too: the same
section records that from 2026-08-10 to 2026-08-18 a bare directory argument matched nothing,
printed `No YAML files to validate.` and exited **0**. This is the second distinct way the same
prescribed command has failed to do what it says.

**This is the second occurrence of a documented defect class.** `CLAUDE.md` carries a whole
convention titled *"New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest"*, written
after `done_proof.py` was created in `scripts/ac_store/` and omitted from this same `deploy_map`,
crashing the deployed hook with `ModuleNotFoundError: done_proof`. `done_proof.py` is in the map
today; `_ac_components.py` — added later, by the change that gave the `components` field its
referential integrity — is not. The convention was written and then not applied to the next
module that needed it, which suggests the rule needs a mechanical check rather than another
paragraph.

**Found while** specifying `assigned_agent` referential integrity (`ACS-100i-9`), whose design
copies `_ac_components.py` into a sibling `_ac_agents.py`. Filing it separately because it is
live now, independent of that work, and because the new module would inherit the same omission:
**a fix for `ACS-100i-9` that adds `_ac_agents.py` to the map while leaving `_ac_components.py`
out would ship a validator that still cannot start.** Fix both in the same change.

**Fix direction.** Add `_ac_components.py` (and any future sibling helper) to `build_ac_store`'s
`deploy_map`. Then close the class rather than the instance: a test that runs `build.py` into a
temporary target and **executes** each deployed entry point — import-only is enough to catch this
— so a module added without its dependency fails at build time instead of at the consumer. A
grep for import statements is not sufficient; this defect is invisible to any check that reads
the source tree, because in the source tree the import resolves.

---

### KI-BP-016 — `build.py` honours `docs_root` when writing the doc index but ignores it when reading, and overwrites the real index with "No docs found."

> **RE-VERIFIED 2026-08-25 — LIVE. Absorbs KI-BP-001, which is the same defect.**
> Reproduced with the exact command CLAUDE.md documents (`--target-dir .` from the workspace
> parent, with the real `skills_config.json` and its `docs_root: "leafcutter-ai/docs/"`):
> `docs/INDEX.md` went from 221 lines with zero `"No docs found"` to 57 lines with nine, and
> the build printed `✓ wrote leafcutter-ai/docs/INDEX.md` and exited 0. Isolating
> `generate_doc_index.py` reproduced the numbers exactly: repo root → 221 lines / 0 stubs,
> workspace root → 57 lines / 9 stubs.
>
> Root cause confirmed at `build.py:1028-1030` — `output_path` is built from
> `target_root / config["docs_root"]` while `content` comes from `generate_index(target_root)`.
> Write honours `docs_root`; read ignores it.
>
> One precision on "every run": the *second* consecutive build is a no-op, because the stub it
> wrote now matches what it reads. It destroys the index every time the index is in its
> correct state — i.e. immediately after every `git checkout -- docs/INDEX.md`, which is
> exactly the loop that made it look like "every run".
>
> **The build does not merely fail to reveal this — it reports it as a green success**, on a
> tracked file that CLAUDE.md points agents at, in a form trivially committed by accident.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py` — the doc-index build phase (`~:1026-1051`);
  `scripts/generate_doc_index.py` (`generate_index`, and the `No docs found.` emitter at
  `:259`, `:284`, `:294`)

**Symptom.** Running the documented self-hosting build

```
python3 scripts/build.py --target-dir /home/henzeh/projects/leafcutter --force-breaking
```

rewrote `leafcutter-ai/docs/INDEX.md` from a populated 221-line index to a 57-line stub whose
every section reads `No docs found.` — **172 table rows deleted**, all nine categories emptied.
The build printed `wrote leafcutter-ai/docs/INDEX.md` and exited 0.

**Root cause — the read root and the write root are computed differently.** In the build phase:

```python
docs_dir = config.get("docs_root", "docs/").rstrip("/")   # "leafcutter-ai/docs"
output_path = target_root / docs_dir / "INDEX.md"          # <ws>/leafcutter-ai/docs/INDEX.md
content = generate_index(target_root)                      # scans <ws>/docs/
```

The **write** path applies `docs_root` from `skills_config.json`, which in this workspace is
`"leafcutter-ai/docs/"` — so it correctly targets the repo's index. The **read** path passes
`target_root` straight to `generate_index`, which hardcodes `<root>/docs` and never consults
`docs_root`. In the self-hosting layout `<workspace>/docs/` is a five-entry deployed stub
(`INDEX.md`, `how-to/`, `product-truth/`, `reference/`, `ui-context.md`), not the repo's docs
tree. So the generator scans the stub, finds nothing in nine of its categories, and the result
is written over the index of a tree it never looked at.

**Reproduced directly**, which isolates it from the rest of the build:

```text
$ generate_doc_index.py --repo-root .../leafcutter-ai       --output /tmp/idx_repo.md
$ generate_doc_index.py --repo-root .../leafcutter          --output /tmp/idx_workspace.md
$ grep -c "No docs found" /tmp/idx_repo.md /tmp/idx_workspace.md
/tmp/idx_repo.md:0
/tmp/idx_workspace.md:9
$ wc -l /tmp/idx_repo.md /tmp/idx_workspace.md
221 /tmp/idx_repo.md
 57 /tmp/idx_workspace.md
```

The 9-section stub is exactly what landed in the repo.

**Why this is worse than a stale artifact.** `No docs found.` is not an error state the
generator reports — it is the ordinary rendering of an empty category, so an empty scan and a
genuinely empty docs tree are indistinguishable in the output and in the exit code. The
destination file is tracked, so the damage is a committable 172-row deletion of the index that
CLAUDE.md points agents at for doc discovery. It was noticed here only because `git status`
was checked immediately after the build; a build run as part of a larger flow would have
carried it into the next commit.

Correcting an earlier misattribution: a dirty `docs/INDEX.md` observed in this workspace on
2026-08-25 was initially blamed on a concurrent agent. It was this build phase.

**Fix direction.** Pass the resolved docs root into the generator rather than the target root —
`generate_index` should take the same `target_root / docs_dir` the writer uses, or accept
`docs_root` and apply it. Independently, the generator should refuse to overwrite a non-empty
index with an all-empty scan: a run that resolves zero documents in every category has almost
certainly resolved the wrong directory, and should exit non-zero saying which directory it
scanned rather than rendering the emptiness as content.

> **Review note, 2026-08-26 — the first half of that fix direction is wrong as written; the
> second half is the one to build.**
>
> "`generate_index` should take the same `target_root / docs_dir`" would reproduce this exact
> bug rather than fix it. Every entry in `_CATEGORIES` (`generate_doc_index.py:64-74`) already
> carries the `docs/` prefix — `("Components", "docs/architecture/components", True)`,
> `("How-To Guides", "docs/how-to", True)`, and so on for all nine. Hand the generator a root
> that already ends in `docs/` and it scans `<root>/docs/docs/architecture/components`, which
> exists nowhere, so every category comes back empty and it writes the identical nine-section
> `No docs found.` stub. The failure would look like no fix had been applied at all. It would
> also break every link the index renders, since those are built from the same prefixed paths.
>
> Whoever picks this up has to choose one of two coherent shapes, not mix them:
>
> 1. **Keep `_CATEGORIES` prefixed and pass the repo root.** The generator's contract stays
>    "give me the root that *contains* `docs/`". The build phase's bug is then simply that it
>    passes `target_root` where it should pass the root implied by `docs_root` — strip the
>    trailing `docs/` from `docs_root` and pass that. Smallest change; the generator is
>    untouched.
> 2. **Strip the `docs/` prefix from all nine `_CATEGORIES` entries and pass the docs root.**
>    Then `target_root / docs_dir` is correct. But this changes the generator's contract and
>    every rendered link path, so the link-rendering code has to be audited in the same commit.
>
> Option 1 is smaller and safer, and it is the one that matches how the generator already
> behaves when invoked directly — the reproduction recorded in this entry passes
> `--repo-root .../leafcutter-ai`, a root *containing* `docs/` rather than a docs root, and
> gets a correct 221-line index. That invocation is the working contract; the build phase is
> what disagrees with it.
>
> The refuse-to-overwrite-on-an-all-empty-scan guard is independently correct and worth landing
> on its own, ahead of either option. It is the part that turns this from a silent 175-line
> deletion into a loud failure, and unlike the path fix it cannot itself be got subtly wrong.

**Pattern:** a resolver that reads one tree and writes another, with the failure rendering as
ordinary output.

---

### KI-BP-017 — `scripts/feedback/` is never provisioned into a worktree, so the documented signoff feedback call crashes and every affected phase records `(submit-failed)`

> **RE-VERIFIED 2026-08-25 — LIVE, on a real worktree rather than a fixture.** Running the
> documented call in `worktrees/ge122-acs` gives
> `can't open file '.../scripts/feedback/submit_feedback.py': [Errno 2] No such file or directory`,
> exit 2 — byte-identical to the recorded evidence. **14 of 54 live worktrees are in this
> state**, including `EPIC-DeploymentCompleteness`, `ci-ac-gate`, `consumer-install` and
> `ge122-acs`.
>
> **Root cause refined, and it changes the fix.** The entry says the directory is never
> provisioned. In fact `setup_ticket_worktree._bootstrap` *does* run `build.py` at step 5, and
> when that succeeds `install_shims` creates the shim — which is why the other 40 worktrees
> have it. So the real defect is that **a skipped or failed bootstrap build is
> indistinguishable from a successful one** (KI-BP-018). Adding the symlink to
> `setup_ticket_worktree.py` is still worth doing, but it treats the symptom.
>
> *Naming trap for anyone checking coverage:*
> `unit_tests/build_guards/test_bp017_shim_relative_targets.py` is about **AC BP-017**
> (relative symlink targets), which is a different thing from this register entry
> **KI-BP-017**. It is not coverage for this.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/setup_ticket_worktree.py` (no `feedback` reference anywhere);
  `scripts/build_phases.py:1642-1676` (deploys `scripts/feedback/` to the target root only);
  `templates/skills/signoff/SKILL.md:180` and the agent templates that repeat its literal

**Symptom.** Caught live during the GE-120 epic drive — the running agents left their own
stderr on disk:

```text
python3: can't open file '/home/henzeh/projects/leafcutter/worktrees/
  EPIC-TrustThatAGreenCheckActuallyChecked/scripts/feedback/submit_feedback.py':
  [Errno 2] No such file or directory
```

Python exits 2 before the script runs — no config read, no id minted, empty stdout — so the
signoff skill's fallback writes `feedback-id: (submit-failed)` into the ticket. Reproduced
independently with the same command shape: byte-identical message, exit code 2.

**Root cause — this is the deployed-dependency-closure rule violated for an executable.**
`scripts/feedback/` is a build output: `build_phases.py:1642-1676` writes it to
`<target_root>/scripts/feedback/`, and `install_shims` realizes it in the **project root
only** (`/home/henzeh/projects/leafcutter/scripts/feedback -> ../.leafcutter/scripts/feedback`).
It is gitignored (`.gitignore:14`; `git ls-files scripts/feedback` is empty), so it cannot
arrive with the checkout either. `setup_ticket_worktree.py` provisions `.leafcutter` and
`.pre-commit-config.yaml` symlinks and contains **zero** references to `feedback`. The
worktree's `scripts/` therefore exists and is fully populated — 74 entries — with no
`feedback/` subdirectory.

Meanwhile `signoff/SKILL.md:180` prescribes the **CWD-relative** literal
`python3 scripts/feedback/submit_feedback.py ...`, repeated verbatim in
`_signoff_block.md:21`, `python-coder.md:643`, `documentation-verifier.md:465`,
`user-surface-smoker.md:300`, `live-surface-tester.md:358` and
`build-single-ticket/SKILL.md:293`.

**Same family as the entries above.** This register already documents the deployed-dependency
closure failing for `.leafcutter/config/` contents (lines 171-194, 937, citing `BP-900g-8-ii`:
"the deployed-dependency closure covers the data and configuration files a script reads, not
only the modules it imports"). This is the identical rule broken for an executable rather than
a config file, and the register's own "Masking trap" note explains why it stayed invisible:
the workspace root **has** the shim, so the relative call works everywhere except a worktree
— and worktrees are where epics are driven.

**Why high rather than medium.** It is silent by design — `SKILL.md:706` instructs agents not
to abort signoff on feedback failure — so it mints an unfalsifiable `(submit-failed)` that
reads as an environment hiccup. Every phase agent on an affected ticket loses its feedback for
the whole drive. In this run, all three `(submit-failed)` entries were on the one ticket whose
agents followed the documented literal each time; agents on other tickets improvised a working
path. That is the same shape as the 23-lost-events incident CLAUDE.md's pre-drive checklist
was written for, and the pre-drive check does not detect it.

**Fix direction — two independent changes, both needed.** (a) Provision it: have
`setup_ticket_worktree.py` create the `scripts/feedback` symlink alongside the `.leafcutter`
one it already makes. (b) Stop prescribing a relative path: change `SKILL.md:180` and the six
agent templates to invoke `.leafcutter/scripts/feedback/submit_feedback.py`, which resolves in
both layouts. (b) alone stops the crash but routes the write to the install-tree sink, which
is `KI-FC-001` — so it must land together with that fix, not before it.

> **Review note, 2026-08-26 — the KI-FC-001 condition belongs on (a) as well, not only (b).**
>
> As written, the "must land together with that fix" condition is attached only to (b), which
> reads as though (a) were safe to ship alone. It is not, and for the same underlying reason.
>
> `_find_project_root()` (`templates/scripts/feedback/submit_feedback.py:65-77`) starts from
> `Path(__file__).resolve().parent`, and `.resolve()` follows symlinks. So the moment
> `scripts/feedback` in a worktree becomes a **symlink** into the shared install tree — which
> is precisely what (a) creates — `__file__` resolves into the install tree, the six-level
> walk-up finds the install tree's `.claude/`, and `_JSONL_DEFAULT` becomes
> `<install-tree>/debugging/logs/feedback.jsonl`. Same destination as (b). Either way the crash
> stops and the feedback lands somewhere nobody is looking, which is arguably worse than the
> loud `(submit-failed)` it replaces, because it reads as success.
>
> So the accurate statement is: **KI-FC-001 gates both (a) and (b)**, since both route through
> a `__file__` resolved into the install tree. Fix the sink resolution first and (a) and (b)
> become interchangeable in ordering.
>
> One thing to check before reproducing: that symlink now **exists** in the GE-120 worktree,
> created after this entry was filed. A fresh attempt to reproduce the original
> `(submit-failed)` crash there will not reproduce it — it will silently exercise the
> install-tree-sink path instead. Confirm whether `scripts/feedback` is a symlink before
> concluding which of the two failure modes you are looking at.

**Pattern:** a build output that reaches the project root and not the worktrees, called
through a path that only resolves at the project root.

---

### KI-BP-018 — No build phase can fail the build, the deploy set is hand-listed in ~26 places, and nothing verifies the deployed tree is complete

- **Severity:** blocker
- **Status:** open — ACs exist and are approved but unbuilt: BP-900g-8 (derive the closure) and BP-900g-9 (fail closed)
- **Occurrences:** 1 (structural; it is the mechanism behind KI-BP-003, 005, 006, 008, 009, 012, 016 and 017)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py` `_run_phases` (~:1097-1184), `main` return at ~:1714, `_manifest_ac_store_scripts` (~:331-349); `scripts/build_referential_integrity.py:270`

**Why this entry exists.** The register holds fifteen distinct build defects and the great
majority are instances of one thing. Filing them individually has produced four rounds of the
same fix. This entry records the mechanism so the next one is not filed as a sixteenth
symptom.

**Three findings, each reproduced against a real build into a scratch adopter repo
(`git init`, target under `/tmp`, never under the package's own parent — a target under
`package_root.parent` relativizes cleanly and is not representative).**

**1. No build phase can fail the build.** `_run_phases` sums *file-write counts*. A phase that
deployed 0 of its 18 scripts and a phase with nothing to do return the same integer. `main()`
prints the sum and returns 0. The `_install_shims` result list and the `_install_hooks` return
string are both discarded — so `pre-commit install` can fail, print a red `ERROR: pre-commit
install failed`, and the build still reports success **with no git hooks installed**.

Exactly six things can exit non-zero: config-schema validation (skipped when `jsonschema` is
absent and under `--dry-run`), agent-registry validation (skipped under `--dry-run`), the
broken-script-reference guard, the untracked-source guard (no-ops without git), self-description
enforcement (**defaults to `warning`, i.e. off**), and the deploy-path collision guard. Plus
uncaught exceptions — a `shutil.copy2` failure aborts, but a *missing source* does not.

Fifteen fail-open sites were catalogued; none changes exit status. The highest-consequence:

| Site | Effect | Signal |
|---|---|---|
| `build_helpers.py:651-661` | `pre-commit install` failed, no hooks installed | red text, discarded |
| `template_compiler.py:33-37` | see KI-BP-019 — every agent loses its frontmatter | **none, any stream** |
| `build.py:1590-1599` | corrupt `agent_registry.json` downgrades `error` → `warning`, disarming the gate that exists to catch it | bare `except … pass` |
| `build_halt_guard.py:61-69, 89-101` | corrupt lock or no git permanently disarms the breaking-change gate | unlogged |
| `build_referential_integrity.py:198-202, 241-245` | an unreadable template's broken references pass a **hard** gate | DEBUG |
| `build_ac_store_scaffold.py:75-90` | template read failure prints `"already present, skipping"` | success-shaped |
| `build_phases.py:89-105`, `injection_builders.py:275-282, 349-356` | unreadable `components.json` / `doc_types.json` / `paths.json` rendered as apology strings **injected into shipped agent prompts** | the prompt itself |

**2. The deploy set is hand-listed in ~26 independent places and derived in none.** Sixteen
deploy sources, plus six *mirrors* of those lists living in other files — `build.py:416` and
`:657` are the second and third copies of the seven-entry workflow-tools list; `build.py:576`,
`:582`, `:702` and `build_phases.py:916-917` are **four** copies of the
`goal_to_epic.py`/`build_ac_mode_detection.py` pair. Plus two shim maps, two clean-target lists
and three phase registries. Roughly fourteen `glob`/`rglob`/`iterdir` scans do exist — but they
feed the *manifest and guard* side, never the deploy side.

That asymmetry is the whole defect. `_manifest_ac_store_scripts` (`build.py:331-349`) derives the
AC-store set by `iterdir()` over source, and its docstring claims it "match[es] what
`build_ac_store` deploys." It does not. That derived set feeds the broken-reference guard — one
of the six gates that *can* fail the build — so the guard believes `_ac_components.py` is
deployable because it exists in source. **The only hard gate that could catch a deploy omission
is fed by a set that contradicts the hand-list it is supposed to police.** Adding entries to
`deploy_map` cannot close this; it is why KI-BP-006 recurred.

**3. Nothing verifies the deployed tree is complete.** `main()` runs two post-build passes and
both only print: `scan_for_placeholders` greps three hardcoded files for TODO markers, and
`check_referential_integrity` validates the ten path-valued keys of `skills_config.json` — its
own docstring calls it "a post-build warning phase (non-blocking)". `return 0` follows
immediately.

The function that would do the job — `build_referential_integrity.extract_compiled_script_path_refs()`,
which scans the **compiled output tree** — exists, is unit-tested, and has **no production call
site**. Verified: the only references are its own module, a docstring cross-link in
`build_propagation_audit.py`, and `unit_tests/test_bp_900b_1.py`. Its docstring says the wiring
was "intentionally out of this ticket's `files_touched` scope."

The nearest live check is the *pre-build* reference guard, blind here by construction: it scans
source templates rather than the deployed tree, matches only `python scripts/<path>` and
`sys.path.insert(...)` forms so a plain `import` of an undeployed sibling is invisible, and
cannot model a caller's CWD — which is why `scripts/feedback/submit_feedback.py` passes while
failing in every worktree (KI-BP-017).

**Evidence.** One adopter build finished with `_ac_components.py` missing, `doc_types.json`
missing, an orphaned `check_eval_staleness.py` whose template had been deleted, and a **1-line**
`fast-lane-ship.js` (source: 1047 lines). Exit 0. Stale cleanup printed `(no stale files found)`.
A grep of the build log for `PLACEHOLDER`, `INTEGRITY` and `SCRIPT-REF` returned nothing.

**Fix direction.** Build BP-900g-8 and BP-900g-9 — both already `readiness: approved`,
`priority: high`, `work_status: todo`. Derive the closure (including the config and data files a
script reads, not only the modules it imports, per BP-900g-8-ii) and make an incomplete deploy
exit non-zero. Wiring `extract_compiled_script_path_refs()` is a large part of the work already
written. Do **not** fix this by adding to `deploy_map`.

**Pattern:** a build whose report is a count of what it wrote, in a system where the failure
mode is not writing something.

**Related.** KI-BP-20260826-1331 is a different defect with the same consequence: many worktrees write a
shared `.leafcutter/` output root last-writer-wins, so a deployed file may carry any worktree's
revision. This entry explains why an *absent* artifact is never noticed; that one explains why a
*present* artifact cannot be attributed to a commit. Together they mean the deployed tree does
not correspond to any revision. The fixes are complementary, not overlapping — BP-900g-8/9
derive the deploy closure and fail closed; a source-revision stamp on each deployed artifact
makes provenance checkable.

---

### KI-BP-019 — A missing `pyyaml` strips the frontmatter from every deployed agent, silently, with no output on any stream

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/template_compiler.py:33-37`

**Symptom.** The `yaml` import is wrapped in `except ImportError`, which sets a module flag and
prints **nothing** — not a warning, not a log line, not a stderr byte. `parse_frontmatter` then
returns `{}` for *every* template it is given.

**Consequence.** Every compiled agent loses `name`, `description`, `model` and `tools`. The
sign-off and verification blocks are never appended because the fields that trigger them are
absent. `build_skills` cannot see `internal` or `deprecated`, so skills that should be withheld
ship. The build prints `Total files written: N` — the same N as a correct run, because the files
*are* written — and exits 0.

**Why it is worth an entry of its own.** This is the largest single silent degradation in the
pipeline and it is invisible in the one place anyone would look: the build's own output. Every
other fail-open site in KI-BP-018 leaves at least a warning or a wrong file; this one leaves a
complete, plausible, populated output tree in which every agent has been quietly lobotomised.

**Fix direction.** It should not be caught at all — `pyyaml` is a hard requirement of the
compiler, and an environment without it cannot produce a correct build. Let the `ImportError`
propagate, or re-raise with a message naming the missing dependency. If the catch must stay for
some caller, it must at minimum print to stderr and set a non-zero exit path. Subsumed by
BP-900g-9's fail-closed principle but worth fixing on sight; it is one line.

**Pattern:** an exception handler that makes a missing dependency indistinguishable from a
satisfied one.

*The changelog-entry validation gap first drafted here as `KI-BP-021` was refiled as
`KI-CL-001` in `docs/known-issues/changelog.md`: the `changelog` component owns entry emission
and the `changelogs/` corpus, whereas this register covers the template compiler. That draft
was never published. **Do not read a citation of `KI-BP-021` as pointing here** — the number
was later taken on `main` by an unrelated closure-guard entry. The changelog gap is
`KI-CL-001`.*

---

### KI-BP-20260826-1331 — a shared deployed `.leafcutter/` is a per-file collage of whatever each writing worktree last wrote — no single commit produces the tree the gates actually run

> **This id is a timestamp, not a sequence number — and that is deliberate.**
> `KI-<COMPONENT>-<YYYYMMDD>-<HHMM>`, minted at authoring time.
>
> This entry was first authored as `KI-BP-018`, renumbered to `KI-BP-021` when 018/019/020
> were taken mid-review, and would have had to move a **third** time: `KI-BP-021` was itself
> claimed on `main` before this PR could land. Across two rounds, **four ids collided twice**
> — eight collisions in one day, all while the PR sat open being reviewed. Renumbering is a
> race the reviewer always loses, because review is exactly the interval during which `main`
> moves.
>
> `KI-BO-024` predicted this and proposed a duplicate-heading check. That check is still worth
> building, but it detects collisions rather than preventing them. A timestamp prevents them:
> two entries collide only if authored in the same component register in the same minute,
> which no observed workflow does. Cost is a longer id; the benefit is that an id, once
> written down and cited, never has to move.
>
> **Existing sequential ids are not being renumbered.** Mass-renaming would break every
> citation in the repo to fix a problem only new entries have. The convention is
> forward-only: sequential ids stay valid and stay cited, new entries are timestamped. Both
> forms will coexist indefinitely, and that is fine — the id's only job is to be unique and
> stable.
>
> Worth an ADR rather than a note buried in one entry; recorded here because the convention
> was adopted to unblock this PR.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py --target-dir <workspace-root>` · the workflow-scripts install
  phase in `scripts/build_phases.py` · the single shared output root
  `/home/henzeh/projects/leafcutter/.leafcutter/`

**Symptom.** Caught during a pre-flight parity check before launching a fast-lane run.
The deployed `.leafcutter/workflows/fast-lane-ship.js` had an **mtime of 22:15 today** —
newer than every source file — while its **content was seven days old**. It predated both
PR #485 (2026-08-18) and PR #510 (2026-08-24):

```text
grep -c "exclude-structural-parent|Phase 4.6 — Changelog|
         fastlane-context-bundle|fastlane-review"  ->  0
```

Zero occurrences of all four markers. No review phase, no changelog phase, no context
bundle, no `--exclude-structural-parent`.

It was not one file. A substitution-neutral comparison — building current `origin/main` to a
scratch target and diffing that against the deployed tree, so `{{config.output_root}}`
expansion could not be mistaken for drift — found **six of nine workflows regressed,
4,114 drifted lines**:

| workflow | drifted lines |
|---|---|
| `build-feature.js` | 1631 |
| `build-ticket.js` | 1110 |
| `quick-fix.js` | 781 |
| `fast-lane-ship.js` | 467 |
| `plan-feature.js` | 64 |
| `finalize-feature.js` | 61 |

**Root cause — a mutable shared surface with many writers and no ownership.**
`build.py --target-dir` is last-writer-wins: it compares deployed content against *its own*
templates and rewrites whatever differs, in either direction. It has no notion of which
revision the deployed tree came from, so it cannot tell "this file is older than mine" from
"this file is newer than mine" — it only sees "different", and makes it match. A build run
from a worktree behind `origin/main` therefore *downgrades* the shared surface for every
worktree pointing at it.

**Correction, 2026-08-26 — the first draft of this entry said "58 worktrees, all resolving
`.leafcutter` to the same workspace-root directory". That is false, and the entry contradicted
itself three paragraphs later.** Measured:

Resolving each worktree's `.leafcutter` with `readlink -f` rather than reading the link text:

```text
symlink, resolving to leafcutter/.leafcutter   ->  ~20   (one shared inode)
private real directory                         ->  ~47
no .leafcutter at all                          ->    5
```

A few of the symlinks are transient, created by one session on 2026-08-26 and pointing at a
scratch build under `/tmp`. Absolute counts drift by the hour as worktrees come and go — two
probes minutes apart returned 72 and 73 — so **treat the shape as the finding and re-measure
the numbers before relying on them**.

The distribution matters more than the total:

- **The symlinked population really does share one root.** `leafcutter-ai/.leafcutter` is
  itself a symlink to `leafcutter/.leafcutter`, so link text that appears to name two roots
  resolves to a single inode. "Rebuild the shared tree" is unambiguous and reaches all of them.
- **The larger group (~47) are private real directories**, not shares. Those cannot be
  corrected by any rebuild of a shared root; each holds whatever the build wrote when that
  worktree was created. That is KI-BP-004, and it is the *more common* case rather than the
  exception this entry originally implied — though "frozen indefinitely" overstates it for the
  roughly one-third created within the last two days.
- **Five have no `.leafcutter` at all** — including `deploy-main2`, which this entry names
  further down as a plausible overwrite source. A worktree with no deployed tree cannot have
  written one, which weakens that particular attribution.

So a remedy aimed at the shared root fixes the shared population and silently misses the
private one. The collage claim below is unaffected — it concerns what happens *within* the
shared root, and was verified directly against it.

**How the error happened — twice, which is the instructive part.** The "58" came from a
`git worktree list` count, and "all resolving to the same directory" was assumed rather than
measured, while the very next section of this entry described a worktree with a private frozen
copy the author had found by hand. A counter-example sat three paragraphs from a claim it
falsifies and neither was checked against the other.

**The first correction then introduced a second false claim, in the same shape.** It reported
"not one shared root but **two**", derived from counting the *raw link text* of each symlink —
which really does split into two spellings. One `readlink -f` shows both resolve to a single
inode, because `leafcutter-ai/.leafcutter` is itself a symlink to `leafcutter/.leafcutter`.
The correction fixed the magnitude and broke the mechanism, and it argued the remedy was
harder than it is.

Both errors are the same move: **a property established on part of a set, asserted of the
whole**, where the discriminating command is about one line long. Worth stating plainly in an
entry whose subject is deployed trees that are not what they appear to be — the register is
not exempt from the failure it documents, and this one has now demonstrated that twice.

The install accounting confirms the write happened rather than being skipped. Today's
corrective build reported `6 installed (3 unchanged)` — exactly matching the observed mtime
split, where the same six carried 22:15 stamps and `build-epic.js`, `create-ticket.js` and
`fast-lane-build.js` kept stamps from July and August 18. The phase writes only files whose
content differs, so the six that were stale are precisely the six some earlier build wrote.

**It is not staleness. It is a collage — and that is the finding.** The first pass through
this called the deployed tree "seven days old", which is wrong in a way worth correcting,
because a coherent older revision is something you can reason about and this is not that.
Rebuilding `origin/main` to a scratch target and diffing the whole `commit_guardian/`
directory against the deployed one shows the deployed tree holds **more** files than
`origin/main`, not fewer:

```text
Only in <deployed>: check_presence_only_assertions.py   _presence_only_scanner.py
Only in <deployed>: check_identifier_uniqueness.py      _uniqueness_scanners.py
Only in <deployed>: check_outcome.py                    check_hook_trigger_reachability.py
Only in <deployed>: _work_items_scanner.py              repair_work_item_duplicates.py   (+6 more)
```

None of those exist on any merged branch. They come from unmerged feature worktrees
(`EPIC-BuildPipelinePhantomRemediation`, `epic/ge122-registration`) that ran a build at some
point. So at the same instant the deployed tree was **behind** `origin/main` on six workflows
and **ahead** of it on a dozen guardian modules — while also *missing* content those same
guardian files should have (see below).

The right mental model is not "the deployed tree is at revision X". It is: **each file is at
whatever revision the last worktree to write that file happened to be at.** There is no X.
Anything that reasons about the deployed tree as a version — a drift check, a manifest, a
human — is reasoning about something that does not exist.

**The same build left a guardian module missing a rule its own source has.** After the
corrective build, `_ac_schema_validators.py` in the deployed tree had **0** occurrences of
`declares_side_effect`, against **12** in both the template and a scratch build from the same
source in the same run:

```text
template                         12
scratch target (fresh dir)       12
workspace root (existing tree)    0
```

One `build.py` invocation, one source, two targets, different results — so writing into an
existing deployment does not converge it on the source the way writing into an empty one
does. The consequence was immediate and load-bearing: `check_ac_schema` ran locally over 16
staged AC records and exited **0**, while calling `validate_declares_side_effect` directly
against the same records returned real errors on two of them. CI, which builds fresh, would
have failed the required `AC store valid` check on a change that passed every local gate.

That run also printed `WARNING: config/ac_store_schema.json not found at
/home/henzeh/projects/leafcutter; falling back to manual field validation` — the hook had
resolved its root to the workspace root rather than the worktree being committed, and
degraded to a weaker check rather than refusing. Exit 0 from a gate that never saw the files
it was asked about.

**This is not KI-BP-008, though the symptom is identical.** That entry's cause is the
version gate *refusing* to install (`return 0` on a parsed-and-too-old `claude --version`).
Here the gate ran its documented **fail-open** path — `[WARNING] Claude Code version
unknown. Installing workflow scripts (fail-open).` — and the install proceeded and wrote
stale bytes. KI-BP-008 is "the phase declined to run"; this is "the phase ran, from the
wrong source". Its occurrence count is deliberately **not** incremented, because the two
have different fixes: a skipped-phase alarm would not have fired on this event.

Worth recording that KI-BP-008's own fix direction already anticipates this case — *"record
the deployed workflow's source revision … so a stale deployed file is reported as drift
regardless of why it was skipped"*. A source-revision stamp is the one fix that covers both.

**Consequence, had the pre-flight check not run.** The fast-lane launch that prompted this
would have executed the pre-#485 lane, which has **no changelog phase**. Its PR would then
have failed the required `Changelog entry present` CI check — the exact defect #485 was written
to fix, reappearing not through a regression in the source but through the deployment layer
serving an older copy of the fix. It would also have run without
`--exclude-structural-parent` (#510), resolving a larger build set than the operator aimed
at, and without the pr-reviewer gate — committing unreviewed. Three separate protections,
all present in `main`, all absent at the point of use.

**Why high.** The failure is invisible from every angle an operator would normally check.
The source tree is correct. `git status` is clean. The build reports success. The deployed
file's mtime is *newer* than the source, so every freshness heuristic based on timestamps
reports it as current — the one signal an operator would trust is actively inverted. And
because the surface is shared, a worktree that never runs a build at all still inherits
another worktree's regression.

The collage shape makes it worse than plain staleness in one specific way: a *missing* rule
and an *extra* module are indistinguishable from a correct tree by inspection. A guardian
directory holding twelve modules that main does not have looks like a tree that is ahead, not
one that is broken — so the natural reading of the evidence is the reassuring one.

**A second, independent copy problem sits underneath it.** Not every worktree even shares the
surface. `worktrees/ac-pipeline-work/.leafcutter` is a **real directory dated 2026-08-18**,
not a symlink — a frozen private copy that the workspace-root rebuild cannot reach. So the
population splits into worktrees that share one incoherent tree and worktrees pinned to a
private snapshot of an arbitrary past build, with nothing distinguishing the two from inside.
That is KI-BP-004 observed live, and it means "rebuild and re-run" is not a reliable remedy:
it fixes the shared tree and silently misses the frozen ones.

**Fix direction.** Stamp provenance and check it. Record the source revision alongside each
deployed artifact (the build manifest already tracks output mappings) and have `build.py`
refuse — or at minimum loudly report — a write that would replace an artifact built from a
descendant commit with one built from an ancestor. That single change turns this from silent
to blocking, and covers KI-BP-008's skip case in the same mechanism.

Two cheaper mitigations worth having regardless: (a) a pre-flight parity check in the
fast-lane and build-feature entry points, comparing deployed workflow content against the
invoking worktree's templates before dispatching anything — the check that caught this,
promoted from ad-hoc to automatic; (b) stop deploying from arbitrary worktrees, or give each
worktree its own output root so the surface stops being shared. Note `deploy-main2` is
pinned detached at `93dfba23` (2026-08-17), a commit predating all four missing markers, and
is a plausible source for this particular overwrite — but the mechanism does not depend on
which worktree it was, and naming a culprit is not the fix.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in its stale form — here reached by an install that ran
successfully rather than one that was skipped.

**Related.** KI-BP-018 — a different defect with the same consequence, and the two should be
read together. That entry is about what the build *never verifies*: no phase can fail the
build, the deploy set is hand-listed in ~26 places, and nothing checks the deployed tree is
complete. This entry is about what the build *overwrites*: many worktrees write a shared output
root last-writer-wins. Between them the deployed tree cannot be trusted to correspond to any
revision — 018 explains why a missing file is never noticed, 021 explains why a present file
may be from anywhere. The fixes are complementary: BP-900g-8/9 make the deploy set derived and
fail-closed; a source-revision stamp makes each deployed artifact's provenance checkable.
Neither alone gives you a tree you can name a commit for.

Also KI-BP-008 (same symptom, skip-side cause). KI-BP-004 (a worktree's deployed hooks frozen
at build time — the same shared-surface staleness for hooks rather than workflows).
KI-BP-011 (`.build_manifest.json` written to the package that ran the build rather than the
target it describes — which is precisely why the deployed tree carries no usable provenance
today).

**A dangling id, noted in passing.** Earlier drafts of this entry cited **`KI-BO-001`** for the
changelog-presence gate. That id has **no definition anywhere in the registers** — it is cited
seven times across the repo, including in `fast-lane-ship.js`'s own source comments and in two
other register entries, and defined zero times. The citations here have been replaced with
plain description. Whoever owns `build-orchestration.md` should either write the entry or
retire the id; a reference that resolves to nothing is indistinguishable from one whose target
was deleted, and readers cannot tell which they are looking at.
