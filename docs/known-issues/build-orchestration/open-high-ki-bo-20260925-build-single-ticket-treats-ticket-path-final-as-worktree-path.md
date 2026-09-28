---
title: "KI-BO-20260925-build-single-ticket-treats-ticket-path-final-as-worktree-path — setup_ticket_worktree emits the input ticket path as ticket_path_final, but build-single-ticket documents it as the ticket inside the worktree"
description: "high — the script deliberately reports the unmoved input path (usually the main checkout's copy); build-single-ticket Step 1 maps it to TICKET_PATH 'inside the worktree', so later sign-off and status edits are likely aimed at main. worktree-agent still parses the pre-rename field ticket_path_new."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - build_orchestration
  - worktree_manager
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-BO-20260925-build-single-ticket-treats-ticket-path-final-as-worktree-path — setup_ticket_worktree emits the input ticket path as ticket_path_final, but build-single-ticket documents it as the ticket inside the worktree

- **Severity:** high. If the caller passes a main-checkout ticket path (the normal case), every ticket edit in the drive targets the main checkout rather than the branch — the "work lands on main" class.
- **Status:** open — no AC. Field semantics verified in code 2026-09-25; the downstream write location is **inferred**.
- **Where:** `templates/scripts/setup_ticket_worktree.py:1766`, `:1804` (`"ticket_path_final": str(ticket_path)`, resolved from `args.ticket_path`), decision note `:2273`; `templates/skills/build-single-ticket/SKILL.md:79`; `templates/agents/worktree-agent.md:112`.

## Mechanism

The script's decision history (`:2273`) renamed `ticket_path_new` → `ticket_path_final` "to make clear the file was
not moved" — the value is the resolved *input* path. `build-single-ticket/SKILL.md:79`:

```
- `ticket_path_final` → `TICKET_PATH` (the ticket's path inside the worktree)
```

That description is false whenever the input was outside the worktree. `worktree-agent.md:112` still tells the
agent to parse `ticket_path_new`, which the script no longer emits.

## Detection

Run `setup-ticket` with a main-checkout ticket path and compare `ticket_path_final` with `worktree_path`: the
ticket path is not under the worktree.

## Fix direction

The worktree component proposed in `docs/analysis/2026-09-25-worktree-creation-consolidation.md` §5.3 should emit
an explicit `ticket_path_in_worktree` (the input path re-rooted under `worktree_path`, verified to exist), and
callers take the path only from that field. Fix the two prompt sites in the same change.
