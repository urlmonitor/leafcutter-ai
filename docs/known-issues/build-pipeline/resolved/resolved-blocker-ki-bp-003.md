---
title: "KI-BP-003 — `config/doc_types.json` is never deployed alongside the hooks that read it, so `check-doc-frontmatter` hard-crashes in the self-hosted workspace and in every adopter worktree"
description: "KI-BP-003 — `config/doc_types.json` is never deployed alongside the hooks that read it, so `check-doc-frontmatter` hard-crashes in the self-hosted workspace and in every adopter worktree"
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

# KI-BP-003 — `config/doc_types.json` is never deployed alongside the hooks that read it, so `check-doc-frontmatter` hard-crashes in the self-hosted workspace and in every adopter worktree

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

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

- **Severity:** was blocker.
- **Status:** **RESOLVED 2026-09-07 — and this time the evidence is a run, not a reading.**

  > Fixed by two merged changes, deliberately split because they fail independently:
  > **PR #694** (`078b862b`) widened the deployed-dependency closure so a non-code file a
  > deployed script READS is a dependency on the same terms as a module it imports, and
  > **PR #708** (`0b765b3c`) added the consumer-simulation inspection that proves, in a
  > real adopter-layout install, that the declaring files actually arrived.
  >
  > **The evidence, stated as commands and outputs rather than as a conclusion** — because
  > the previous closure of this entry argued from source and was wrong:
  >
  > - A clean `python scripts/build.py --target-dir /tmp/<scratch>` exits 0 and
  >   `.leafcutter/config/` now contains `doc_types.json` alongside `diagram_types.json`,
  >   `skill_registry.json`, `agent_registry.json`, `guardrail_gates.yaml`, `paths.json`,
  >   `phase_deferral.yaml` and `ac_store_schema.json`. Before this it held three files.
  > - `env -u PYTHONPATH python <scratch>/.leafcutter/scripts/commit_guardian/check_doc_frontmatter.py <doc>.md`
  >   runs clean. That is the adopter's exact reproduction, executed from the deployed
  >   tree, and it no longer raises `FileNotFoundError`.
  > - CI on both PRs is green, including `Consumer install simulation (BP-900h-1)`.
  >
  > **What the fix was NOT.** Deploying `doc_types.json` alone would have closed the
  > symptom and left the mechanism — that is what this entry warned against for four
  > occurrences. The closure guard is now derived: it reads what deployed guardrails
  > actually read. Turning it on surfaced five further undeclared dependencies nobody had
  > noticed — `config/diagram_types.json`, `config/skill_registry.json` (present in source,
  > deployed nowhere), `docs/components.json`, `docs/roadmap.json`, and
  > `config/phase_deferral.yaml` (deployed by TKT-600b but never declared). Each was fixed,
  > none by hand-listing.
  >
  > **A defect it caught on contact.** Merging `origin/main` into the fix branch made the
  > build abort on `config/phase_deferral.yaml` — shipped but undeclared. The guard found
  > a real gap in main the first time it met one, which is the behaviour this entry has
  > wanted since 2026-08-18.
  >
  > **Residual, so this closure is not read as wider than it is.** A clean build emits
  > ~409 `unresolvable data-file read` warnings. Those are the guard's blind spots made
  > visible, which the AC requires — but each is a dependency static analysis cannot see.
  > `submit_feedback.py` reaching `config/feedback_categories.yaml` through
  > `_find_config_root()` is the same shape as the defect fixed here and remains
  > underivable. Tracked as `KI-BP-20260907-1120` and `KI-BP-20260907-1125` below, not
  > folded into this closure.
  > `diagram_type_validators`'s silent fallback to a built-in constant (KI-CG-002) is also
  > untouched: shipping the file fixes the symptom, not the silence.

  > **THE FALSE CLOSURE, recorded rather than deleted.** From 2026-08-31 to 2026-09-01 this
  > entry read `RESOLVED — verified 2026-08-31`. The closure argued that
  > `_find_doc_types_json()`'s `__file__`-relative ancestor walk removed the need for any
  > deploy location, and explicitly explained away the zero `grep doc_types` hits in
  > `build_phases.py` as a misreading. Both claims were made by desk-check, neither by
  > running anything.
  >
  > Two facts available at the time refute it. The resolver change landed **2026-08-18**
  > (`160d4f47a`, PR #466) — *seven days before* the `RE-VERIFIED 2026-08-25 — LIVE`
  > reproduction that still sits three lines above the status line. And the ancestor walk
  > cannot help a consumer at all: it only ever checks `config/doc_types.json` and
  > `leafcutter/config/doc_types.json` per ancestor, and in a real adopter install neither
  > `<consumer>/config/` nor `<consumer>/leafcutter/` exists. A submodule directory named
  > `leafcutter-ai/` matches neither candidate.
  >
  > A second commit then added a `Re-verified 2026-09-01` line endorsing the closure. That
  > re-verification was not performed either. **Two independent readers agreed with each
  > other instead of with the code**, and the entry's own contradicting evidence sat
  > unread between their two edits.
  >
  > Refuted by running it: a clean `python scripts/build.py --target-dir /tmp/<scratch>`
  > off current `origin/main` deploys **three** of the 23 files in `config/`
  > (`feedback_categories.yaml`, `ac_store_schema.json`, `commit_guardian.json`);
  > `find <target> -name doc_types.json` returns nothing; and the deployed hook raises
  > `FileNotFoundError` with `_DOC_TYPES_JSON` resolved to `candidates_checked[0]` — the
  > walk ran to the filesystem root and matched nothing.
- **Occurrences:** 5
- **First seen:** 2026-08-18 · **Last seen:** 2026-09-01
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

**Fifth occurrence, 2026-09-01 — reported by DIAGraph again, and it settles the
second-versus-third disagreement above.** The adopter reports `check-doc-frontmatter`
raising `FileNotFoundError` at `doc_type_validators.py:113` on **every** doc carrying
frontmatter, blocking doc commits for everyone on their `main`, and reproduced against an
untouched `ADR-012`. `--no-verify` was the only route through; it was the sole failing hook
across `--all-files`.

That resolves the open question in the third occurrence: with the package directory named
`leafcutter-ai/` the lookup fails **everywhere**, main checkout included, because neither
hardcoded candidate can ever match — `<consumer>/config/` does not exist and the submodule
is not named `leafcutter/`. With it named `leafcutter/` the second candidate resolves in a
main checkout and fails inside a worktree, which is the second occurrence exactly. **Both
earlier reports were correct; they were describing different package-directory names.** The
title may now be widened to say the adopter's `main` is affected — the condition the third
occurrence set for doing so is met. The one-line probe above stays useful and is unchanged.

Confirmed independently against current `origin/main` by clean-build reproduction (see the
reopening note at the top of this entry), so this is a property of the code today and not
of the reporter's install.

The reporter's one wrong detail is worth keeping, because it misdirects the fix: they wrote
that "the build just puts it somewhere else." It does not. The file is not deployed at all,
so there is nothing to relocate — an entry has to be added, and per the fix direction above
that entry must come from a derived closure rather than another hand-added line.

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
