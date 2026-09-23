---
title: "Known issues — build-pipeline"
description: "Open, observed defects in the build-pipeline component: build.py, its deploy phases, and the self-hosting build that deploys this package into its own workspace. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-09-14
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

**Adding an issue.** Append a new section with a **date-and-slug id**:
`### KI-BP-YYYYMMDD-short-slug`. Nothing here is generated — edit it by hand. Fill in what
you actually know; an issue recorded with a thin `Evidence` line is far better than one not
recorded.

**Why not the next free number.** The sequential `KI-BP-NNN` form is retained for the
entries that already carry it, and must not be renumbered — inbound references would break.
But it is not usable for new entries. "Append the next free number" requires every author to
read the same file at the same moment and act on it before anyone else does, which fails the
moment two agents or two sessions work in parallel. On 2026-08-25 it produced **ten**
collisions in a single day, one of which reached `main`, and this register already carries
two renumbering notes as scar tissue (KI-BP-020, and the KI-CG-012 collision recorded in
`commit-guardian.md`). KI-BO-024 diagnosed this and named the remedy: *"Make the number
non-sequential. A date-plus-slug id cannot collide."* Two authors would have to pick the same
slug on the same day, and if they did they are describing the same defect anyway. Both id
forms sort and grep identically on the `KI-BP-` prefix.

**`Status: open` is a claim, not a fact — verify before acting on it.** On 2026-08-31 a
reader picking the next issue to fix checked four entries marked open and found **three
already resolved**: KI-BP-003, KI-BP-006 and KI-BP-020. Nothing had updated them, because
the fix landed in a PR that had no reason to touch this file. The cost is not cosmetic —
the next reader re-does finished work, or concludes the register is untrustworthy and
stops reading it, which is worse.

Two habits follow. When you fix something a register entry describes, **update the entry
in the same PR**. And when you pick work off this register, **confirm the defect is live
in the code before starting**.

**`Status: RESOLVED` is also only a claim, and it is the more dangerous one.** The
paragraph above cited KI-BP-003 as the cautionary example of a stale *open*. That reading
was itself wrong, and it was corrected on 2026-09-01: KI-BP-003 was never fixed. The
2026-08-31 closure was a desk-check that mistook a resolver change for a deploy fix, a
second reader endorsed it a day later without running anything, and a consumer hit the
defect the following morning. Full account in the entry.

The asymmetry is what matters. A stale `open` costs someone a wasted investigation and
they discover the truth immediately, because the first thing they do is go look. A stale
`RESOLVED` removes the entry from everyone's queue and is discovered by a user. So:

- **Never close an entry by reading code.** Run the thing. Paste the command and its
  output into the entry — every closure here that turned out to be wrong argued from
  source, and every one that held quoted a run.
- **Read the entry's own evidence before overriding it**, and check the dates. KI-BP-003
  carried a reproduction that post-dated the fix being credited, three lines above the
  status line that credited it.
- **Agreement between two readers is not verification** when neither of them executed
  anything. Two desk-checks are one desk-check.
- **Zero grep hits are not evidence of anything.** They were read as "the fix is elsewhere"
  when they meant "there is no deploy site at all."

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`build-pipeline/`](build-pipeline/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/build-pipeline/open-blocker-*   # anything critical open?
ls docs/known-issues/build-pipeline/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`build-pipeline/resolved/`](build-pipeline/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 47** (1 blocker, 24 high, 22 low) · **Resolved: 8**

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-BP-018 — No build phase can fail the build, the deploy set is hand-listed in ~26 places, and nothing verifies the deployed tree is complete | [open-blocker-ki-bp-018.md](build-pipeline/open-blocker-ki-bp-018.md) |
| `high` | KI-BP-001 — The documented self-host build command destroys `docs/INDEX.md` on every run | [open-high-ki-bp-001.md](build-pipeline/open-high-ki-bp-001.md) |
| `high` | KI-BP-004 — A worktree's deployed hooks are frozen at build time, so after merging `main` the gates enforce the previous ruleset | [open-high-ki-bp-004.md](build-pipeline/open-high-ki-bp-004.md) |
| `high` | KI-BP-005 — Deleting a template leaves its deployed copy behind, and the build reports "no stale files found" | [open-high-ki-bp-005.md](build-pipeline/open-high-ki-bp-005.md) |
| `high` | KI-BP-007 — No gate validates a skill reference written in template prose, so six skills are loaded by name and none of them exist | [open-high-ki-bp-007.md](build-pipeline/open-high-ki-bp-007.md) |
| `high` | KI-BP-008 — A version gate can skip the entire workflow-install phase and still report a successful build, leaving every deployed workflow silently stale | [open-high-ki-bp-008.md](build-pipeline/open-high-ki-bp-008.md) |
| `high` | KI-BP-009 — `.claude/skills/` is symlinked wholesale to the generated tree, so an adopter's own skills have nowhere to live and `--clean` targets them | [open-high-ki-bp-009.md](build-pipeline/open-high-ki-bp-009.md) |
| `high` | KI-BP-011 — `.build_manifest.json` is written to the package that ran the build, not the target install it describes, so it is not portable to any consumer install | [open-high-ki-bp-011.md](build-pipeline/open-high-ki-bp-011.md) |
| `high` | KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely | [open-high-ki-bp-012.md](build-pipeline/open-high-ki-bp-012.md) |
| `high` | KI-BP-016 — `build.py` honours `docs_root` when writing the doc index but ignores it when reading, and overwrites the real index with "No docs found." | [open-high-ki-bp-016.md](build-pipeline/open-high-ki-bp-016.md) |
| `high` | KI-BP-017 — `scripts/feedback/` is never provisioned into a worktree, so the documented signoff feedback call crashes and every affected phase records `(submit-failed)` | [open-high-ki-bp-017.md](build-pipeline/open-high-ki-bp-017.md) |
| `high` | KI-BP-019 — A missing `pyyaml` strips the frontmatter from every deployed agent, silently, with no output on any stream | [open-high-ki-bp-019.md](build-pipeline/open-high-ki-bp-019.md) |
| `high` | KI-BP-20260826-1331 — a shared deployed `.leafcutter/` is a per-file collage of whatever each writing worktree last wrote — no single commit produces the tree the gates actually run | [open-high-ki-bp-20260826-1331.md](build-pipeline/open-high-ki-bp-20260826-1331.md) |
| `high` | KI-BP-20260826-1331-addenda — (addenda to KI-BP-20260826-1331) | [open-high-ki-bp-20260826-1331-addenda.md](build-pipeline/open-high-ki-bp-20260826-1331-addenda.md) |
| `high` | KI-BP-20260826-worktree-hooks-only-on-one-path — A worktree made with plain `git worktree add` has no hooks, and nothing at commit time says so | [open-high-ki-bp-20260826-worktree-hooks-only-on-one-path.md](build-pipeline/open-high-ki-bp-20260826-worktree-hooks-only-on-one-path.md) |
| `high` | KI-BP-20260831-1333 — `check-output-drift` blocks a commit on a gitignored cache file, so the gate fails on something no commit could ever contain | [open-high-ki-bp-20260831-1333.md](build-pipeline/open-high-ki-bp-20260831-1333.md) |
| `high` | KI-BP-20260831-generator-emits-unparseable-doc-contract — the ticket generator writes the documentation contract in a shape its own consumer rejects, and every epic has fixed it by hand instead of at source | [open-high-ki-bp-20260831-generator-emits-unparseable-doc-contract.md](build-pipeline/open-high-ki-bp-20260831-generator-emits-unparseable-doc-contract.md) |
| `high` | KI-BP-20260901-0812 — A hook was registered on `main` without the surface declaration its own gate requires, and the gate now refuses the next person to touch it | [open-high-ki-bp-20260901-0812.md](build-pipeline/open-high-ki-bp-20260901-0812.md) |
| `high` | KI-BP-20260901-0914 — `ac-store-valid`'s per-PR diff scope means a schema-invalid AC record can sit on `main` indefinitely, invisible to CI, while the documented whole-component pre-flight that would catch it is optional, manual, and never wired in | [open-high-ki-bp-20260901-0914.md](build-pipeline/open-high-ki-bp-20260901-0914.md) |
| `high` | KI-BP-20260907-0722 — The pre-consolidation migration deletes a consumer's root `.pre-commit-config.yaml` without migrating its project-local hooks, and reports the deletion as success | [open-high-ki-bp-20260907-0722.md](build-pipeline/open-high-ki-bp-20260907-0722.md) |
| `high` | KI-BP-20260907-1120 — 409 reads the closure guard cannot resolve statically, none of them triaged, each one a potential KI-BP-003 | [open-high-ki-bp-20260907-1120.md](build-pipeline/open-high-ki-bp-20260907-1120.md) |
| `high` | KI-BP-20260907-1620 — The doc-index phase derives the index from the target tree and writes it into the package tree, so every self-hosting build truncates `docs/INDEX.md` by 75% | [open-high-ki-bp-20260907-1620.md](build-pipeline/open-high-ki-bp-20260907-1620.md) |
| `high` | KI-BP-20260907-bootstrap-swallows-build-failure — `_bootstrap()` catches `build.py`'s own `CalledProcessError` and prints a WARNING instead of failing, so a now-loud build failure still ships a half-deployed worktree | [open-high-ki-bp-20260907-bootstrap-swallows-build-failure.md](build-pipeline/open-high-ki-bp-20260907-bootstrap-swallows-build-failure.md) |
| `high` | KI-BP-20260907-no-gitignore-for-consumers — `build.py` deploys no `.gitignore` to consumers, so a deployed module's compiled bytecode gets tracked and every import re-fails the next commit | [open-high-ki-bp-20260907-no-gitignore-for-consumers.md](build-pipeline/open-high-ki-bp-20260907-no-gitignore-for-consumers.md) |
| `high` | KI-BP-20260921-1630 — the clean-mode provenance ledger can only ever learn about artifacts the build still produces, so every orphan that predates it is permanently unremovable | [open-high-ki-bp-20260921-1630.md](build-pipeline/open-high-ki-bp-20260921-1630.md) |
| `low` | KI-BP-002 — Generated agent cards are tracked but never regenerated, so every build dirties six of them | [open-low-ki-bp-002.md](build-pipeline/open-low-ki-bp-002.md) |
| `low` | KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean` | [open-low-ki-bp-010.md](build-pipeline/open-low-ki-bp-010.md) |
| `low` | KI-BP-013 — The mypy gate checks only changed files, so untouched debt is invisible until an unrelated edit drops a wall of it on whoever touched the file | [open-low-ki-bp-013.md](build-pipeline/open-low-ki-bp-013.md) |
| `low` | KI-BP-014 — The commit agent can stall indefinitely waiting on the autofix agent it dispatched, leaving a fully-staged commit unmade and no error | [open-low-ki-bp-014.md](build-pipeline/open-low-ki-bp-014.md) |
| `low` | KI-BP-015 — `docs/agents/cards/*.card.md` are committed build outputs with no freshness gate, so they drift from the AC store they describe | [open-low-ki-bp-015.md](build-pipeline/open-low-ki-bp-015.md) |
| `low` | KI-BP-20260826-1421 — a worktree provisioned with a `/tmp` hook tree loses every package gate when `/tmp` is cleared, and pre-commit's own error message recommends disabling the gates to make it go away | [open-low-ki-bp-20260826-1421.md](build-pipeline/open-low-ki-bp-20260826-1421.md) |
| `low` | KI-BP-20260831-0620 — The mypy CI job's `scripts/**/*.py` pathspec matches no file directly in `scripts/`, so 59 of 107 tracked scripts have never been type-checked and the job reports SUCCESS for checking nothing | [open-low-ki-bp-20260831-0620.md](build-pipeline/open-low-ki-bp-20260831-0620.md) |
| `low` | KI-BP-20260831-0728 — The hook-script integrity check strips the `hooks/` segment off every declared entry, so it reports three real scripts as missing on every build | [open-low-ki-bp-20260831-0728.md](build-pipeline/open-low-ki-bp-20260831-0728.md) |
| `low` | KI-BP-20260831-0940 — `derive_declares_side_effect` is negation-blind, so a refusal criterion is forced to declare the side effect whose absence is its entire content | [open-low-ki-bp-20260831-0940.md](build-pipeline/open-low-ki-bp-20260831-0940.md) |
| `low` | KI-BP-20260831-1014 — Seven declared package sources are skipped with no log at all, and BP-900g-9's scope line used "does it warn" as the boundary the AC says is not the observable | [open-low-ki-bp-20260831-1014.md](build-pipeline/open-low-ki-bp-20260831-1014.md) |
| `low` | KI-BP-20260831-1334 — Every fast-lane worktree bootstrap regenerates ten agent cards as drift, and the lane stages with `git add -A` | [open-low-ki-bp-20260831-1334.md](build-pipeline/open-low-ki-bp-20260831-1334.md) |
| `low` | KI-BP-20260901-1345 — A tempdir-cleanup race in the portability suite fails the REQUIRED pytest check at random, on a PR that touched nothing near it | [open-low-ki-bp-20260901-1345.md](build-pipeline/open-low-ki-bp-20260901-1345.md) |
| `low` | KI-BP-20260907-0852 — `build.py` deploys `tickets/README.md` and never records it, so the drift gate blocks the commit and prescribes the one action that cannot clear it | [open-low-ki-bp-20260907-0852.md](build-pipeline/open-low-ki-bp-20260907-0852.md) |
| `low` | KI-BP-20260907-0940 — There is no orphan sweep, and the step called "Stale file cleanup" says "no stale files found" while one sits in the tree | [open-low-ki-bp-20260907-0940.md](build-pipeline/open-low-ki-bp-20260907-0940.md) |
| `low` | KI-BP-20260907-1125 — a warning that fires 409 times on a green build is not a warning, and the 410th is the one that matters | [open-low-ki-bp-20260907-1125.md](build-pipeline/open-low-ki-bp-20260907-1125.md) |
| `low` | KI-BP-20260908-1140 — `declares_side_effect` derives FALSE for an AC whose Then clause says a file "is gone", because the deriver only recognises engineering vocabulary | [open-low-ki-bp-20260908-1140.md](build-pipeline/open-low-ki-bp-20260908-1140.md) |
| `low` | KI-BP-20260909-declaring-files-helper-wrapped-import — only an import written lexically inside `try/except ImportError` is treated as optional, so guarding the *call* instead of the *import* reads as a hard dependency | [open-low-ki-bp-20260909-declaring-files-helper-wrapped-import.md](build-pipeline/open-low-ki-bp-20260909-declaring-files-helper-wrapped-import.md) |
| `low` | KI-BP-20260909-declaring-files-tempdir-path — the declaring-files scanner treats any `<anything> / "_name.py"` as a deployed sibling-module load, so a runtime-generated file written into a tempdir is demanded in the deployed tree | [open-low-ki-bp-20260909-declaring-files-tempdir-path.md](build-pipeline/open-low-ki-bp-20260909-declaring-files-tempdir-path.md) |
| `low` | KI-BP-20260909-injector-falls-back-to-a-literal-400 — the build's file-size injector swallows every read failure and tells every agent 400, whatever the config actually declares | [open-low-ki-bp-20260909-injector-falls-back-to-a-literal-400.md](build-pipeline/open-low-ki-bp-20260909-injector-falls-back-to-a-literal-400.md) |
| `low` | KI-BP-20260909-standards-declare-no-applicability — only one of four configured guardrails says which kinds of file it governs; for the rest it lives in the script's filename | [open-low-ki-bp-20260909-standards-declare-no-applicability.md](build-pipeline/open-low-ki-bp-20260909-standards-declare-no-applicability.md) |
| `low` | KI-BP-20260914-build-crashes-on-a-cp1252-stdout — build.py dies with UnicodeEncodeError when its output is piped on Windows, so every test that runs the build as a subprocess fails locally | [open-low-ki-bp-20260914-build-crashes-on-a-cp1252-stdout.md](build-pipeline/open-low-ki-bp-20260914-build-crashes-on-a-cp1252-stdout.md) |
| `low` | KI-BP-20260914-1415 — a test asserts a literal string appears exactly twice in `build.py`'s source text, so relocating either function fails a fixture premise far from the cause | [open-low-ki-bp-20260914-1415.md](build-pipeline/open-low-ki-bp-20260914-1415.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-BP-003 — `config/doc_types.json` is never deployed alongside the hooks that read it, so `check-doc-frontmatter` hard-crashes in the self-hosted workspace and in every adopter worktree | [resolved-blocker-ki-bp-003.md](build-pipeline/resolved/resolved-blocker-ki-bp-003.md) |
| `blocker` | KI-BP-006 — `build_ac_store`'s hardcoded deploy list omits the AC-store validator and both its helpers | [resolved-blocker-ki-bp-006.md](build-pipeline/resolved/resolved-blocker-ki-bp-006.md) |
| `high` | KI-BP-020 — `_ac_components.py` is missing from the AC-store deploy map, so the deployed `validate_ac_schema.py` crashes on import — and it is the command CLAUDE.md tells consumers to run | [resolved-high-ki-bp-020.md](build-pipeline/resolved/resolved-high-ki-bp-020.md) |
| `low` | KI-BP-021 — The closure guard's reference lens misses four import idioms, each yielding an empty closure the build reports as clean | [resolved-low-ki-bp-021.md](build-pipeline/resolved/resolved-low-ki-bp-021.md) |
| `high` | KI-BP-022 — A deployable script that fails to parse gets an empty closure and a clean bill of health — and 107 of the 152 scripts the guard parses are in `templates/`, which CI's ruff run excludes | [resolved-high-ki-bp-022.md](build-pipeline/resolved/resolved-high-ki-bp-022.md) |
| `low` | KI-BP-023 — The closure guard's "every script this build will deploy" covers eight deploy families and the build has ten | [resolved-low-ki-bp-023.md](build-pipeline/resolved/resolved-low-ki-bp-023.md) |
| `high` | KI-BP-20260907-0812 — `generate_product_truth.py` builds index paths with the platform separator, so on Windows the validator can never pass and every commit touching an AC YAML is blocked | [resolved-high-ki-bp-20260907-0812.md](build-pipeline/resolved/resolved-high-ki-bp-20260907-0812.md) |
| `high` | KI-BP-20260910-1240 — build.py writes CRLF on Windows and then cannot see that it did, so every deployed script silently diverges from its template and a plain re-run never repairs it | [resolved-high-ki-bp-20260910-1240.md](build-pipeline/resolved/resolved-high-ki-bp-20260910-1240.md) |
