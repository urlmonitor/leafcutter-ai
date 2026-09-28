---
title: "KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent — _resolve_root.find_project_root() has no 'no repository' outcome and returns the workspace parent, so the fix direction of five open KIs would not fix them"
description: "high — from the workspace parent, git fails, the __file__ walk accepts the empty .git/ and CLAUDE.md there, and the answer is cached module-wide. ~30 hand-written root resolvers use 6 strategies; the shared one is also wrong."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260914-ac-hooks-resolve-root-from-cwd.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-009.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-018.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent — _resolve_root.find_project_root() has no 'no repository' outcome and returns the workspace parent, so the fix direction of five open KIs would not fix them

- **Severity:** high. Several open KIs prescribe "route through `_resolve_root`" as the fix; that would move the defect, not remove it.
- **Status:** open — no AC. Reproduced 2026-09-25 (`scratchpad/root_probe.py` against the deployed `<ws>/.leafcutter/scripts/commit_guardian`).
- **Where:** `templates/scripts/commit_guardian/_resolve_root.py:18-58`.

## Symptom

Run from `C:\Users\Hendrik\Code\leafcutter` (the ADR-001 workspace parent, not a git repository), every resolver
variant — including `find_project_root()` — returns `C:\Users\Hendrik\Code\leafcutter`. A hook then checks a
non-repository, typically finds zero files, and exits 0.

## Mechanism

```python
proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], ...)   # fails: not a repo
...
for ancestor in [here, *here.parents]:
    if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
        _PROJECT_ROOT = ancestor          # workspace has an empty .git/ (hooks/ only) and a CLAUDE.md
        return _PROJECT_ROOT
_PROJECT_ROOT = here.parent.parent        # final fallback: also never "no repo"
```

Three problems: a marker walk that accepts a `.git` directory that is not a repository; no failure outcome at all;
and a module-global cache (`:18`, `:32`) that pins the first answer for the process.

## The duplication around it

A classifier over tracked `scripts/` and `templates/` found ~30 hand-written root resolvers using six strategies
(`--show-toplevel` only; the shared resolver; `__file__` walk; cwd walk; marker walk; mixed), with five different
failure behaviours (wrong root, `None`, cwd, `""`, raise). `_ac_store_locator.py:30-60` documents "never cwd"; the
seven AC hooks walk from cwd. From `leafcutter-ai/docs` the variants give three different answers. Linked open KIs:
KI-CG-20260914-ac-hooks-resolve-root-from-cwd (fix direction at L38), KI-CG-009, KI-CG-018, KI-CG-027, KI-CG-024,
KI-CG-20260909-gate-ticket-ac-limits-and-the-three-inert, KI-CG-20260831-hook-parity-legs-alias-and-fail-open.

## Fix direction

Replace with a module offering two explicit questions: `subject_root(cwd) -> Path | NO_REPO` (`HOOK_ROOT` →
`git rev-parse --show-toplevel`/`--git-common-dir` → `NO_REPO`; never `__file__`, never a marker walk) and
`install_root()` (unresolved `__file__`, not followed through a `.leafcutter` symlink). On `NO_REPO` a hook emits
`could_not_check` and exits non-zero. No module-level cache. The worktree component proposed in
`docs/analysis/2026-09-25-worktree-creation-consolidation.md` §5.4 needs the same resolution rules and should share
the implementation.
