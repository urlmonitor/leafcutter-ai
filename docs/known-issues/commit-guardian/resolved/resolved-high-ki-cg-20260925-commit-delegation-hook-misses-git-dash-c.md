---
title: "KI-CG-20260925-commit-delegation-hook-misses-git-dash-c — enforce_commit_delegation matches the literal substring 'git commit', so 'git -C <path> commit' is never blocked, and five prompts use that spelling"
description: "high — the under-inclusive half KI-CG-016 left unclaimed is confirmed: the matcher is `return \"git commit\" in command`. finalize-feature, build-single-ticket, quick-fix and plan-feature all commit via git -C."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-27'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260907-commit-delegation-is-a-password-not-an-identity.md
  - docs/known-issues/commit-guardian/resolved/resolved-low-ki-cg-016.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-CG-20260925-commit-delegation-hook-misses-git-dash-c — enforce_commit_delegation matches the literal substring 'git commit', so 'git -C <path> commit' is never blocked, and five prompts use that spelling

- **Severity:** high. CLAUDE.md's "Commit Delegation — MANDATORY" rule is enforced only on recipes that spell the command naively; the recipes that commit from inside worktrees bypass it.
- **Status:** **RESOLVED** (PR #915, merged as 6d7abd81; ACs BP-1100d-3 and BP-1100d-3-i; verified 2026-09-27 by running the merged detector on `git -C /tmp/wt commit`, `git -c user.name=a commit` and a compound `cd x && git commit`, all recognised as commits).
- **Where:** `templates/hooks/enforce_commit_delegation.py:39-55` (and its deployed copies under `.claude/hooks/`, `.gemini/hooks/`).

## Mechanism

```python
command = str(tool_input.get("command") or tool_input.get("cmd") or "")
return "git commit" in command
```

`git -C /path/to/worktree commit -m …` contains no `git commit` substring.

## Sites that commit with the unblocked spelling

- `templates/workflows-js/finalize-feature.js:1646` — status-checker runs `git -C ${WORKTREE_ROOT} commit`
- `templates/skills/build-single-ticket/SKILL.md:371`
- `templates/skills/quick-fix/SKILL.md:348`, `:1130` (the same file's `:1211` says "never call `git commit` directly")
- `templates/skills/plan-feature/SKILL.md:345`

Meanwhile bare-spelled sites without the token (`pull-request.md:196,258`, `changelog-agent.md:234`,
`glossary-bootstrap/SKILL.md:132`) *are* blocked.

## Relation to existing KIs

KI-CG-016 (L48-54) documented the over-inclusive half (PR bodies quoting "git commit" get blocked) and explicitly
did **not** claim the under-inclusive half. KI-CG-20260907 records that the rule is a password, not an identity.
This entry is the confirmed under-inclusive half.

## Resolution (2026-09-27)

The hook now splits the command into simple commands on unquoted shell operators, including `$(...)` and backtick bodies. It tokenises each simple command with shlex, skips `VAR=value` prefixes and git's global options (`-C`, `-c`, `--git-dir`, `--work-tree`, ...), and blocks when the subcommand is `commit`. Quoting it cannot parse fails closed. The five prompt sites that committed with `-C` were migrated in the same PR: the skill recipes now dispatch the commit agent, and finalize's closure commit carries the exemption fast-lane-ship already uses. A census test (`test_bp_1100d_3_i_no_recipe_newly_blocked.py`) runs the real detector over every recipe in `templates/` so a new `-C` recipe cannot land unnoticed.

## Fix direction

Parse argv (`shlex.split`), skip global options (`-C <dir>`, `-c k=v`, `--git-dir`, …) and test whether the
subcommand is `commit`. That fixes both halves at once. Longer term, route every commit through one
`commit_changes.py` (cluster 6 of the 2026-09-25 duplication analysis).
