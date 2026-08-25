---
title: "Known issues — build-pipeline"
description: "Open, observed defects in the build-pipeline component: build.py, its deploy phases, and the self-hosting build that deploys this package into its own workspace. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-25
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

### KI-BP-003 — `config/doc_types.json` is never deployed alongside the hooks that read it, so `check-doc-frontmatter` hard-crashes in the self-hosted workspace and in every adopter worktree

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

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-24 · **Last seen:** 2026-08-24
- **Where:** `scripts/build_phases.py` — the workflow-scripts install phase, lines ~683-720

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

---

### KI-BP-009 — `.claude/skills/` is symlinked wholesale to the generated tree, so an adopter's own skills have nowhere to live and `--clean` targets them

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
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_helpers.py:185` (manifest write target); `:83`, `:95-96`
  (`output_mappings` keying); `:193-195` (manifest key relativization)

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
