---
title: "Agent Reference: worktree-agent"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
related_code:
  - ".claude/agents/worktree-agent.md"
  - ".agents/workflows/worktree.md"
  - ".claude/skills/feature/SKILL.md"
  - ".agents/workflows/close-worktree.md"
---

# Agent Reference: `worktree-agent`

Implementing agent: `worktree-agent` (Haiku, confirmation-gated user-facing).
Family: `coding/`.

Routes worktree lifecycle operations (create + remove) through one Haiku-tier
entry point. Wraps the existing `feature` skill (create) and `close-worktree`
workflow (remove). Owns the `/worktree` slash command.

---

## 1. When to Use

- **Start of work**: `/worktree create <branch-or-ticket-path>` — creates a
  new worktree, or reuses the existing epic worktree if the path is a ticket
  under `tickets/01_todo/EPIC-<NAME>/`.
- **After PR merges**: `/worktree remove <branch-or-worktree-path>` — runs
  safety checks, requires explicit "yes" confirmation, then removes the
  worktree and deletes the local branch.

Don't use this agent for:
- Bulk-pruning `[gone]` branches — use `/clean_gone` (commit-commands plugin).
- Resolving merge conflicts — use `conflict-resolver`.
- Pruning stale worktrees the user did not name — only acts on a named target.

---

## 2. Two Actions

### `create`

Delegates entirely to `.claude/skills/feature/SKILL.md`.

The skill:
- Detects epic ticket paths (`tickets/.../EPIC-<NAME>/...`) and **reuses** the
  existing `EPIC-<NAME>` worktree rather than creating a duplicate.
- For free-form branch names: creates a new worktree at the project's standard
  worktree root, copies `.env` and `.mcp.json`, and runs `poetry install`.

Creation is non-destructive — no confirmation required.

### `remove`

Delegates to `.agents/workflows/close-worktree.md` with a confirmation gate
applied **before Phase 4 (Remove the Worktree)**:

1. Phases 1–3 of the workflow run automatically (identify, check uncommitted
   changes, check merge status).
2. If uncommitted changes are found → **refuse**, show the dirty state, do not
   proceed.
3. Otherwise → display the safety-check report (worktree path, branch name,
   unmerged-commits flag, what will be deleted).
4. Ask: **"Confirm removal of worktree `<branch>` and deletion of the local
   branch? (yes / no)"**
5. Proceed to Phases 4–6 only on **yes** in the same turn.

---

## 3. Epic-Worktree-Reuse Rule

When a ticket lives under `tickets/01_todo/EPIC-<NAME>/`, the project convention
(per the user's memory) is to work on the matching `EPIC-<NAME>` worktree, not
on `main`. The `feature` skill honours this automatically — it checks
`git worktree list` for an existing `EPIC-<NAME>` branch and reuses it.

`worktree-agent` does not reimplement this logic; it is provided by the skill.

---

## 4. Confirmation Rule

| Action | Confirmation required |
|---|---|
| `create` | No — fully reversible (`git worktree remove`) |
| `remove` | Yes — explicit "yes" after safety-check report |

The gate covers the entire remove path (worktree removal + branch deletion).
No sub-step re-prompts.

---

## 5. Tool Allowlist

`Bash, Read` — the Haiku floor per [ADR-006 §2.6](../../architecture/ADR-006-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation).
No `Grep`, `Glob`, or MCP tools.

The agent reads skill and workflow files by absolute path; no open-ended search
is needed for any worktree operation.

---

## 6. Underlying Skills (Do Not Modify)

- [`.claude/skills/feature/SKILL.md`](../../../.claude/skills/feature/SKILL.md) — worktree creation logic, epic-reuse detection, environment bootstrap.
- [`.agents/workflows/close-worktree.md`](../../../.agents/workflows/close-worktree.md) — safety-check sequence, merge check, worktree removal, branch cleanup.

`worktree-agent` wraps these; it does not duplicate their logic.

---

## 7. Cross-Links

- [`.claude/agents/worktree-agent.md`](../../../.claude/agents/worktree-agent.md)
- [`docs/agents/conventions.md`](../conventions.md) — Haiku tier, tool allowlist, visibility classes.
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) — Haiku tier policy.
