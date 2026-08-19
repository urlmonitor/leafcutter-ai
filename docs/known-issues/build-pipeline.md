---
title: "Known issues — build-pipeline"
description: "Open, observed defects in the build-pipeline component: build.py, its deploy phases, and the self-hosting build that deploys this package into its own workspace. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-19
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

Note this is fail-**closed** and loud, which is the right choice (GE-120 deliberately
removed the silent fallback to a narrower built-in list). The defect is the unreachable
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
narrowing GE-120 removed from `doc_types` on 2026-08-18, still live in the file GE-120
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

The deployed copy predated GE-120 entirely — it did not contain the resolver function at
all, so it was falling back to the narrow constant that GE-120 had already deleted from the
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

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in its orphan form — the deployed tree holds something the
source no longer has.

---

### KI-BP-007 — No gate validates a skill reference written in template prose, so six skills are loaded by name and none of them exist

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
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

**Trap.** The complaint arrives as a consumer-install packaging bug and reads exactly like a
module missing from a deploy list — the recurrence this register already records more than
once. Auditing `build_skills` and the deploy manifest finds nothing, because nothing there is
wrong. Confirm the artifact exists in `templates/` before investigating why it did not arrive.
And do not stop at the two skills the customer named: the reporter sees whichever dangling
reference their workflow happened to touch, never the class.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2's inverse. Source and deployed
layout agree perfectly; both are missing the same file, and every consumer of it treats
absence as a pass.
