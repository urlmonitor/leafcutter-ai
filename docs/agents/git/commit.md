---
title: "Agent Reference: commit"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/agents/coding/precommit-autofix-routing.md"
related_code:
  - ".claude/agents/commit.md"
  - ".agents/workflows/commit.md"
  - ".claude/precommit-autofix.json"
---

# Agent Reference: `commit`

Implementing agent: `commit` (Sonnet, confirmation-gated user-facing).
Family: `coding/`.

Produces a single git commit on the current branch. Always shows the planned
message and file list before issuing `git commit`. On pre-commit hook failure,
invokes `precommit-autofix` (Haiku for mechanical, Sonnet for structural) and
retries **once**.

---

## 1. Confirmation Flow

Every commit goes through:

1. Inspect staged change (`git status --short`, `git diff --cached --stat`).
2. Draft message following `git log -5` style.
3. **Show the user**: subject + body + file list + line-count changes.
4. Ask: **"Commit this? (yes / edit / cancel)"**
5. Proceed only on **yes** in the same turn.

Looking-ready is not enough — the agent never commits without explicit yes.

---

## 2. Retry Policy on Hook Failure

If `git commit` fails on pre-commit hooks:

1. Capture stderr verbatim.
2. Invoke `precommit-autofix` skill — routes per `.claude/precommit-autofix.json`:
   - Mechanical (frontmatter dates, formatting) → Haiku.
   - Structural (`check_complexity.py`, missing-ADR, SQL complexity) → Sonnet.
3. **Surface the autofix diff** when the route was Sonnet (structural fixes
   can change semantics). Mechanical fixes (single-line edits) apply silently.
4. Re-stage and retry `git commit` **once**.
5. If the second attempt fails, return the hook output to the user. Do not
   loop. Do not bypass with `--no-verify`.

See [precommit-autofix-routing.md](precommit-autofix-routing.md) for the full
hook-by-hook routing table.

---

## 3. Refusal Cases

| User asks | Response |
|---|---|
| "commit with --no-verify" | Refuse + cite Git Safety Protocol. Proceed only if user insists in the same turn. |
| "force push" | Out of scope — `pull-request` agent owns push. Force-push to main is forbidden. |
| "amend the last commit" | Default is to create a new commit. Amend only when user explicitly says "amend". |
| `git add -A` / `git add .` | Refuse — stage by name. Capture risk: `.env`, credentials, unintended large files. |

Sensitive-file commits (`.env`, `credentials.json`, etc.) are flagged before
the confirmation prompt.

---

## 4. Smoke-Test Recipe

To verify the precommit-autofix loop works:

1. Stage a ticket file with a wrong `created:` date in its frontmatter.
2. Run `/commit`.
3. Confirm the commit.
4. Observe: hook fails → precommit-autofix routes to Haiku → frontmatter date
   gets corrected → retry commit succeeds.

The agent's report names the autofix sub-agent that ran.

For a structural smoke check:
1. Stage a Python file that violates `check_complexity.py`.
2. Run `/commit`.
3. The agent surfaces the Sonnet-driven complexity refactor diff before
   retrying. User reviews the diff in the same turn.

---

## 5. Cross-Links

- [`.claude/agents/commit.md`](../../../.claude/agents/commit.md)
- [`.claude/precommit-autofix.json`](../../../.claude/precommit-autofix.json) — routing config.
- [`docs/agents/coding/precommit-autofix-routing.md`](precommit-autofix-routing.md) — audit + routing rationale.
- [`docs/agents/coding/pull-request.md`](pull-request.md) — chained via `/commit-push-pr`.
- [`CLAUDE.md`](../../../CLAUDE.md) § "Pre-commit Hooks", "Git Safety Protocol".
