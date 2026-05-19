---
name: precommit-autofix
description: Use when a `git commit` fails because of pre-commit hooks, or when you want a Sonnet review pass before staging. Reads `.claude/precommit-autofix.json` to route each failing hook to the right model+agent (haiku for mechanical fixes like frontmatter dates, sonnet for structural work like complexity refactors or missing ADRs). Also runs the optional Sonnet pre-commit review.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Agent
---

# Pre-commit Auto-fix

Routes pre-commit failures to the right model so that mechanical fixes are cheap (haiku) and structural / design work goes to a more capable model (sonnet). Configuration lives in `.claude/precommit-autofix.json` — edit that file to change routing without touching this skill.

## When to invoke

- A `git commit` failed with `pre-commit` output. Parse the failing hook IDs, dispatch fixers, retry.
- Before running `git commit` (and after the user has asked for a thorough commit), run the optional Sonnet review pass over the staged + working diff.
- The user runs `/precommit-autofix` explicitly.

## Inputs

- The full pre-commit failure output (from the most recent `git commit` attempt).
- The config file: `.claude/precommit-autofix.json`.

## Step 1 — Load the routing config

```bash
cat .claude/precommit-autofix.json
```

Parse the JSON. The shape is:

```jsonc
{
  "defaults":      { "model": "...", "subagent_type": "..." },
  "commit_review": { "enabled": bool, "model": "...", "subagent_type": "...", "description": "..." },
  "rules": [
    { "hook_id": "...", "category": "...", "model": "...", "subagent_type": "...", "description": "..." }
  ]
}
```

If the file is missing or invalid JSON, **stop** and report it to the user — do not silently fall back, since the whole point is that this is the editable knob.

## Step 2 — Identify failing hooks

From the pre-commit output, extract every failing `id:` line. pre-commit prints them as:

```
Check Documentation Frontmatter........Failed
- hook id: check-doc-frontmatter
- exit code: 1
```

Build the unique list of failing `hook_id` values, in failure order.

## Step 3 — Look up routing per hook

For each failing `hook_id`:

1. Find a matching `rules[]` entry by `hook_id`.
2. If the rule's `model` or `subagent_type` is `null` (e.g. `apply-sql-changes`), **skip** — no agent dispatch needed; report it.
3. If no matching rule, fall back to `defaults`.

**Agent frontmatter overrides the dispatch model.** Some specialized agents pin their own model (e.g. `code-refactoring-specialist`, `architecture-planner`, `smart-bug-resolver` all pin `model: opus`; `feature-dev:code-reviewer` pins `model: sonnet`). The rule's `effective_model` field documents what actually runs after that override. When deciding whether to escalate (Step 5), compare against `effective_model`, not `model` — escalating from `effective_model: opus` is meaningless.

Group hooks by `(effective_model, subagent_type)` so a single agent can fix multiple related failures in one dispatch instead of spawning one agent per hook.

## Step 4 — Dispatch the fix agent(s)

For each `(model, subagent_type)` group, use the `Agent` tool with:

- `subagent_type`: from the rule
- `model`: from the rule (`haiku` / `sonnet` / `opus`)
- `description`: short, human-readable, e.g. `"Auto-fix: check-doc-frontmatter"`
- `prompt`: include
  - the exact failing hook IDs and their `description` from the config (so the agent knows the rule it is satisfying)
  - the **full raw pre-commit output** for those hooks (so it sees file paths and error specifics — do not paraphrase)
  - the working directory and the explicit instruction: "Fix only what is needed to satisfy these hooks. Do not refactor surrounding code. Do not add features. Re-run the failing hook locally to verify."
  - the verification command, e.g. `pre-commit run check-doc-frontmatter --files <files>`

If `len(groups) >= 2`, dispatch them **in parallel** (multiple `Agent` tool calls in one message) — they touch independent issues.

## Step 5 — Re-run pre-commit and decide

After the agents return:

```bash
git add -u   # pick up their fixes (only files already tracked / staged)
pre-commit run --all-files
```

- **All green** → continue with the original commit.
- **Same hook still failing** → escalate: re-dispatch with a more capable model than the rule's `effective_model` (haiku → sonnet, sonnet → opus). If `effective_model` is already `opus`, do not escalate — surface the failure to the user instead. Cap escalations at one per hook to avoid loops.
- **Different hook failing now** → restart from Step 2.
- **Two consecutive failures with no progress** → stop, summarize for the user, ask before continuing. Do not silently churn.

## Step 6 — Optional: Sonnet pre-commit review (proactive mode)

When invoked **before** `git commit` (not in response to a failure), and `commit_review.enabled` is `true`:

1. Capture the working diff: `git diff HEAD`.
2. Dispatch `Agent` with the `commit_review.subagent_type` and `commit_review.model`.
3. Prompt the reviewer with the diff and the project conventions in `CLAUDE.md`. Ask for blocking issues only — bugs, missing tests, convention drift. Tell it to skip nits.
4. Surface the reviewer's findings to the user before committing. If blocking issues are reported, fix them or get user approval to proceed anyway.

## Constraints

- **Never bypass hooks** with `--no-verify`. The whole point is to satisfy them, not skip them.
- **Never escalate beyond one bump** without telling the user — if Sonnet can't fix it after Haiku tried, that signals a real problem worth surfacing.
- **Trust the JSON.** If a routing decision feels wrong, edit the JSON and reload — don't hardcode overrides in this skill.
- **Don't dispatch for `apply-sql-changes` or other `category: auto` rules** — those are auto-applied by the guardian.

## Example invocation

```
git commit -m "..."
# → pre-commit fails with check-doc-frontmatter + check-complexity

# Skill flow:
# 1. Load config
# 2. failing = [check-doc-frontmatter, check-complexity]
# 3. Routes to (haiku, general-purpose) and (sonnet, code-refactoring-specialist)
# 4. Dispatch both agents in parallel
# 5. pre-commit run --all-files → green
# 6. Retry the commit
```
