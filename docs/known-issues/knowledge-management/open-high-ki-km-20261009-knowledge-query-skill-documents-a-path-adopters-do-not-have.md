---
title: "KI-KM-20261009-knowledge-query-skill-documents-a-path-adopters-do-not-have — the shipped knowledge-query skill tells adopters to run python scripts/knowledge_query.py, a path that does not exist in a deployed install"
description: "high — templates/skills/knowledge-query/SKILL.md hardcodes `python scripts/knowledge_query.py` on twelve lines. The build deploys the script to <project>/.leafcutter/scripts/knowledge_query.py, and <project>/scripts/ holds only three symlinks (commit_guardian, doc_compliance, feedback), so every documented command fails with file-not-found in an adopter's project. It works in this repository only because the source copy happens to sit at scripts/knowledge_query.py. Measured 2026-10-09 on the shared reference layout. A second failure sits behind the first: run from its deployed location, the script looks for <project>/config/paths.json, which that layout also lacks."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - knowledge_management
  - build_pipeline
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
  - templates/skills/knowledge-query/SKILL.md
  - docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-20260921-worktree-base-resolver-defaults-to-cwd.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-031.md
---

# KI-KM-20261009-knowledge-query-skill-documents-a-path-adopters-do-not-have — the shipped knowledge-query skill tells adopters to run `python scripts/knowledge_query.py`, a path that does not exist in a deployed install

> **Why this register.** The defect is in the knowledge-query skill's own instructions, and both
> fixes touch either that skill or the deploy layout it depends on. `components:` names
> `build_pipeline` too, because one of the two fix directions is a new consumer-layout shim.
> Index: [knowledge-management.md](../knowledge-management.md).

- **Severity:** high. Every command in the skill fails for every adopter, and nothing reports it.
  The maintainers of this repository cannot see it, because in this repository the documented
  command works.
- **Status:** open, no AC.
- **Occurrences:** 1. Found because a GE-118f deployed-layout test copied the skill's documented
  path and failed (2026-10-08).
- **First seen:** 2026-10-08 · **Last seen:** 2026-10-09
- **Where:** `templates/skills/knowledge-query/SKILL.md`, lines 25, 28, 31, 34, 37, 40, 43, 46,
  77, 98, 203 and 213. Each one is the literal text `python scripts/knowledge_query.py ...`, with
  no `{{config.output_root}}` placeholder. The consumer-layout shims are declared in
  `scripts/build_helpers.py:80-96` (`shim_map`). Only three entries go under `scripts/`.

## What was measured (2026-10-09, worktree at origin/main `5caa16ca`)

1. **The twelve lines.** `grep -n knowledge_query templates/skills/knowledge-query/SKILL.md`
   returned exactly the twelve lines listed above, all with the bare `scripts/` prefix.
2. **The deployed skill is unchanged.** In the shared reference layout
   (`/tmp/leafcutter-shared-reference-layout-<id>/published`, produced by
   `get_or_produce_shared_layout()`), `.claude/skills/knowledge-query/SKILL.md` has the same
   twelve `python scripts/knowledge_query.py` lines. The build did not rewrite them. Skills
   *are* config-injected: the same layout's `ac-scanner/SKILL.md` shows `.leafcutter/scripts/...`
   where its template says `{{config.output_root}}/scripts/...`. So the knowledge-query skill
   just never asked for the substitution.
3. **Where the script really is.** `find <layout> -name knowledge_query.py` returned only
   `<layout>/.leafcutter/scripts/knowledge_query.py`.
4. **What `<project>/scripts/` holds.** `ls -la <layout>/scripts/` in two separately built
   layouts listed exactly three symlinks: `commit_guardian -> ../.leafcutter/scripts/commit_guardian`,
   `doc_compliance -> ...`, and `feedback -> ...`. These match the three `scripts/*` entries in
   `shim_map`.
5. **The documented command fails.** From the layout root,
   `python3 scripts/knowledge_query.py --query roadmap` exited **2** with
   `can't open file '<layout>/scripts/knowledge_query.py': [Errno 2] No such file or directory`.
6. **The right path fails too, for a different reason.** From the same root,
   `python3 .leafcutter/scripts/knowledge_query.py --query roadmap` exited **1** with
   `ERROR: paths.json not found at <layout>/config/paths.json.`. The script resolves
   `project_root / "config" / "paths.json"` (`scripts/knowledge_query.py:1359-1362`, where
   `project_root` defaults to the working directory). The layout has `paths.json` only at
   `.leafcutter/config/paths.json`.

**Inferred, not measured:** that a real adopter's install looks like the shared reference layout
here. The reference layout is a plain `build.py --target-dir` output. An adopter who keeps their
own `config/paths.json` at the project root would get past step 6, but not past step 5.

## Why it survives

In this repository the source copy is at `scripts/knowledge_query.py` (`git ls-files` confirms
it), and `config/paths.json` is at the repository root. So the documented command works for
everyone who maintains the package and fails only for the people it ships to. That is the same
layout-dependent shape as `KI-BO-20260921-worktree-base-resolver-defaults-to-cwd` (resolved) and
`KI-BO-031`: an instruction that is correct only in the tree it was written in.

## Does the "Shipped address check (INF-1100d-4)" CI job cover this class? No.

Checked by reading `scripts/portability/check_shipped_addresses.py` (295 lines) and its CI step
(`.github/workflows/ci.yml:284-300`). It matches exactly one pattern: a
`postgresql://`, `postgres://` or `mysql://` connection address with a concrete host and a numeric
port (`_ADDRESS_RE`, `:94-100`). It does not look at script paths, command lines, or any
reference to a file that might be missing. The nearest other check, the consumer-install job's
`check_declaring_files.py`, proves that files read by deployed *guardrails* resolve under the
deployed output root. Its docstring does not mention skill documentation or command examples.
That last point comes from reading its docstring only. No CI check found here verifies that a
command a shipped skill tells the reader to run resolves in a deployed layout.

## Detection

From the root of any consumer install:

```bash
ls scripts/knowledge_query.py              # absent
ls .leafcutter/scripts/knowledge_query.py  # present
```

Across all shipped skills, the general symptom is a `python scripts/<name>.py` line in a
`templates/skills/*/SKILL.md` where `<name>` is not under one of the three `shim_map` script
directories. Nobody has run that sweep yet. This entry covers knowledge-query only.

## Workaround

None verified. Calling the deployed copy (`python .leafcutter/scripts/knowledge_query.py`) gets
past the missing file, but then stops at the missing `config/paths.json` (step 6).
`--project-root` changes both where `paths.json` is looked for and where every surface path is
resolved from, so pointing it at `.leafcutter` is unlikely to give correct results. Not tested.

## Fix directions (not chosen here)

1. **Template the path.** Replace `scripts/knowledge_query.py` with
   `{{config.output_root}}/scripts/knowledge_query.py` on all twelve lines, the way
   `templates/skills/ac-scanner/SKILL.md` does. Skills are injected at deploy time (measured in
   step 2), so in a SKILL.md the substitution is the intended behaviour. The inject-config trap
   (a contiguous `{{config.*}}` literal inside a deployed `.py` is rewritten at deploy time) does
   not apply to a markdown skill body. Not checked: what the placeholder resolves to in this
   repository's own self-hosted build, where the command works today.
2. **Add a fourth shim.** Add `("scripts/knowledge_query.py", "scripts/knowledge_query.py")` (or
   an equivalent file-level link) to `shim_map`, next to the three existing `scripts/*` bridges,
   so the documented path exists in every consumer layout. That keeps the skill text unchanged,
   but every current `shim_map` entry is a directory and `_create_shim`
   (`scripts/build_ownership.py:596`) is documented as creating a directory shim, so a
   single-file entry is a new shape for it.

Neither direction fixes step 6 alone. The script's `paths.json` lookup also has to find
`.leafcutter/config/paths.json` in a deployed layout, or the skill has to tell the reader to pass
`--project-root`. A test that runs the skill's own documented command from a built layout's root,
rather than a hand-copied path, would catch both.

**Pattern:** an instruction that is true in the repository that wrote it and false in every
repository it ships to. Every check here runs in the first kind of tree.
