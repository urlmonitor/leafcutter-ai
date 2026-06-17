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

## Step 3 — Look up routing per hook and classify tier

For each failing `hook_id`:

1. Find a matching `rules[]` entry by `hook_id`.
2. If the rule's `model` or `subagent_type` is `null` (e.g. `apply-sql-changes`), **skip** — no agent dispatch needed; report it.
3. If no matching rule, fall back to `defaults`.
4. Check whether the `hook_id` appears in `blocking_hook_ids` (from the config). If it does not appear in `blocking_hook_ids`, the hook is **non-gating** — skip it entirely, do not dispatch any fixer.
5. For hooks in `blocking_hook_ids`, classify the **tier** from the matching `rules[]` entry's `category` field (already loaded from `.claude/precommit-autofix.json` in Step 1 — no other file is read):
   - `category: structural` — judgment is required; use the **originator re-dispatch path** (see Step 4a below). Every hook in `blocking_hook_ids` ships as `category: structural`, so the seven gating hooks (`check-complexity`, `check-docstrings`, `check-exception-handling`, `check-file-size`, `check-ac-schema`, `check-ac-limits`, `check-contract-shrinking`) all route here.
   - `category: mechanical` — use the **generic light-model route** (see Step 4b below).
   - `category` absent / no matching rule — default to the **generic light-model route** (Step 4b); never block on an unclassified hook.

   > **Single source of truth.** Tier is derived from the `category` field on the rule you already loaded — the skill never opens `commit_guardian.json`. The hook-script `tier:` field in `commit_guardian.json` exists for the transform-vs-validator ordering of the pure-Python hooks (see the transform tier in `managing-pre-commit-hooks.md`); the autofix routing decision is governed solely by `category` here, so the two surfaces cannot drift the dispatch path.

**Agent frontmatter overrides the dispatch model.** Some specialized agents pin their own model (e.g. `code-refactoring-specialist`, `architecture-planner`, `smart-bug-resolver` all pin `model: opus`; `feature-dev:code-reviewer` pins `model: sonnet`). The rule's `effective_model` field documents what actually runs after that override. When deciding whether to escalate (Step 4b retry), compare against `effective_model`, not `model` — escalating from `effective_model: opus` is meaningless.

Group **non-judgment** hooks by `(effective_model, subagent_type)` so a single agent can fix multiple related failures in one dispatch instead of spawning one agent per hook.

## Step 4a — Originator re-dispatch (structural-category gating hooks)

For each failing hook whose rule `category` is `structural` (judgment-tier) and whose `hook_id` is in `blocking_hook_ids`:

### Step 4a.1 — Parse the originating agent

Scan the raw hook output for a line matching:

```
AUTOFIX_AGENT: <agent-id>
```

Extract `<agent-id>`. If no such line is present, fall through to the generic route (Step 4b) for this hook — do not block.

### Step 4a.2 — Read the context capsule from the ticket sign-off

Read the `ticket_path` file. Search the `## Comments` section for the most recent sign-off comment from `<agent-id>`. Within that comment, look for a `context_capsule:` YAML block.

- If found: extract the entire `context_capsule:` block verbatim.
- If absent: emit one warning line:
  ```
  context_capsule absent in <agent-id> sign-off — proceeding with empty capsule
  ```
  Continue with `context_capsule: {}` (empty). **Never block on an absent capsule.** Absence is treated identically to a missing `completion_manifest` — warn-and-proceed.

### Step 4a.3 — Dispatch the originating agent type

Use the `Agent` tool with:

- `subagent_type`: the same `<agent-id>` extracted in Step 4a.1
- `model`: `sonnet` (judgment-tier failures require structural reasoning)
- `description`: `"Originator re-dispatch: <agent-id> fixing <hook_id>"`
- `prompt`: the following re-dispatch prompt (fill in the bracketed values):

```
You are [<agent-id>] re-dispatched to fix a judgment-tier pre-commit hook failure.

## Context

ticket_path: [<ticket_path>]
failing_hook_ids: [<comma-separated list of failing judgment hook IDs>]
originating_hook: [<hook_id>]

## Hook output (verbatim — do not paraphrase)

[<full raw hook output for this hook>]

## Context capsule from your previous sign-off

[<context_capsule block verbatim, or "(empty — no prior capsule found)">]

## Your instructions (read carefully — these are hard constraints)

1. Fix ONLY what is needed to make the failing hooks pass. Do not refactor
   surrounding code, add features, or change behavior beyond the violation.

2. Honor the capsule rationale. If the capsule contains a `design_constraints`
   field, your fix must not contradict any constraint listed there.

3. Reuse `capsule.consumers_checked` — do NOT look up new consumers. The
   `consumers_checked` field in the capsule is the authoritative blast-radius
   record. Do not spawn `research-agent` to re-derive it.

4. **Spawn NO sub-agents.** You are running at depth 2 in the dispatch chain
   (ticket-supervisor → commit → you). Claude Code's hard depth-1 Agent-tool
   nesting limit means any `Agent` tool call you make will be silently dropped.
   Do not attempt to spawn `research-agent`, `python-coder`, or any other
   sub-agent. Doing so violates ADR-006-flatten-supervisor-chain.

5. If fixing the violation would require cross-file information that is NOT
   present in `capsule.consumers_checked`:
   - **Return `status: blocker`** immediately.
   - Describe exactly what information is missing and which file(s) you would
     need to inspect.
   - Do NOT guess. Do NOT make assumptions about files you have not read.
   - Do NOT spawn `research-agent`.
   - The commit will NOT be retried on this pass; the blocker will be surfaced
     to the user who will decide next steps.

6. After applying the fix, emit a one-line summary:
   `AUTOFIX_RESULT: fixed | blocker`
   followed by a one-sentence description.
```

### Step 4a.4 — Retry commit once

After the re-dispatched agent returns:

- If the agent returned `AUTOFIX_RESULT: blocker`: surface the blocker to the user immediately. **Do NOT retry the commit.** Stop here and present the agent's blocker explanation.
- If the agent returned `AUTOFIX_RESULT: fixed`: stage the changed files, then retry the commit once (see Step 5).

## Step 4b — Generic light-model route (mechanical-category and unclassified hooks)

For each failing hook whose rule `category` is **not** `structural` (i.e. `mechanical`, absent, or no matching rule) and is in `blocking_hook_ids`, use the existing generic dispatch:

Use the `Agent` tool with:

- `subagent_type`: from the rule (or `defaults.subagent_type`)
- `model`: from the rule (or `defaults.model`) — typically `haiku` for mechanical fixes
- `description`: short, human-readable, e.g. `"Auto-fix: check-doc-frontmatter"`
- `prompt`: include
  - the exact failing hook IDs and their `description` from the config (so the agent knows the rule it is satisfying)
  - the **full raw pre-commit output** for those hooks (so it sees file paths and error specifics — do not paraphrase)
  - the working directory and the explicit instruction: "Fix only what is needed to satisfy these hooks. Do not refactor surrounding code. Do not add features. Re-run the failing hook locally to verify."
  - the verification command, e.g.:
    ```
    pre-commit run check-doc-frontmatter --files <files>
    ```

No capsule read is performed for mechanical-tier hooks. No originator lookup is needed.

If `len(groups) >= 2`, dispatch them **in parallel** (multiple `Agent` tool calls in one message) — they touch independent issues.

## Step 5 — Re-stage and retry commit (once)

After any fixer (mechanical route or originator re-dispatch) returns successfully (not blocker):

```bash
git add -u
```

Then retry the commit once.

- **All green** → commit succeeds. Done.
- **Still failing on the second attempt** → **stop immediately**. Surface the full hook output to the user. Do not retry further. Do not bypass with `--no-verify`. The user decides next steps.

**The retry cap is exactly one.** A second hook failure after the retry is always surfaced — never silently re-dispatched.

If the fixer returned a blocker (Step 4a.4), do NOT execute this step — the commit is not retried on a blocker pass.

## Step 6 — Optional: Sonnet pre-commit review (proactive mode)

When invoked **before** `git commit` (not in response to a failure), and `commit_review.enabled` is `true`:

1. Capture the working diff: `git diff HEAD`.
2. Dispatch `Agent` with the `commit_review.subagent_type` and `commit_review.model`.
3. Prompt the reviewer with the diff and the project conventions in `CLAUDE.md`. Ask for blocking issues only — bugs, missing tests, convention drift. Tell it to skip nits.
4. Surface the reviewer's findings to the user before committing. If blocking issues are reported, fix them or get user approval to proceed anyway.

## Context Capsule — absence handling

When reading a sign-off comment to gather context for re-dispatch (e.g. to
pass the originating coder's design context to a re-dispatched fixer), a
`context_capsule:` block may or may not be present.

**Treat an absent `context_capsule:` block as backward-compatible-absent:**

- Emit one warning line: `context_capsule absent in <agent-name> sign-off — proceeding without design context`.
- Continue the re-dispatch path with whatever context is available.
- **Never block** a fix attempt or a commit retry because the capsule is absent.

This mirrors the existing `completion_manifest` legacy-compatibility behavior
(see signoff SKILL.md §2b). An absent capsule is not an error — it means
the originating coder's pre-completion checks emitted no warn-tier signals.

## Constraints

- **Never bypass hooks** with `--no-verify`. The whole point is to satisfy them, not skip them.
- **Never escalate beyond one bump** without telling the user — if Sonnet can't fix it after Haiku tried, that signals a real problem worth surfacing.
- **Trust the JSON.** If a routing decision feels wrong, edit the JSON and reload — don't hardcode overrides in this skill.
- **Don't dispatch for `apply-sql-changes` or other `category: auto` rules** — those are auto-applied by the guardian.
- **Don't block on absent `context_capsule`** — treat it as warn-and-proceed per the Context Capsule — absence handling section above.

## Example invocations

### Mechanical-tier example

```
git commit -m "..."
# pre-commit fails with check-doc-frontmatter (tier: mechanical, blocking)

# Skill flow:
# 1. Load config
# 2. failing = [check-doc-frontmatter]
# 3. blocking_hook_ids contains check-doc-frontmatter; tier is not judgment
# 4b. Dispatch haiku/general-purpose fixer
# 5. git add -u, retry commit once
# 6. Commit succeeds
```

### Judgment-tier example

```
git commit -m "..."
# pre-commit fails with check-exception-handling (tier: judgment, blocking)
# Hook output contains: AUTOFIX_AGENT: python-coder

# Skill flow:
# 1. Load config
# 2. failing = [check-exception-handling]
# 3. blocking_hook_ids contains check-exception-handling; tier is judgment
# 4a.1. Parse AUTOFIX_AGENT: python-coder
# 4a.2. Read ticket_path → find python-coder sign-off → extract context_capsule
# 4a.3. Dispatch python-coder (sonnet) with capsule + hook output
# 4a.4. Agent returns AUTOFIX_RESULT: fixed
# 5. git add -u, retry commit once
# 6. Commit succeeds
```
