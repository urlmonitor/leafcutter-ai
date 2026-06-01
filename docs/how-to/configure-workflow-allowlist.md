---
title: "How to configure the workflow shell-command allowlist"
type: how-to
status: active
created: 2026-06-01
last_updated: 2026-06-01
components:
  - build_pipeline
related_docs:
  - "docs/reference/workflow-constraints.md"
  - "templates/settings.json"
  - "docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md"
---

# How to configure the workflow shell-command allowlist

Leafcutter's Claude Code Workflow scripts (`build-ticket.js`, `build-epic.js`,
`create-ticket.js`) dispatch phase agents in `acceptEdits` mode. While agents
accept file edits without prompting, Bash commands still trigger a permission
prompt each time the agent runs a command that is not in the pre-approved list.

This guide shows you how to configure the `allowedTools` key in
`.claude/settings.json` to minimise permission prompts during workflow
execution.

## Prerequisites

- Claude Code >= 2.1.154 installed (workflow scripts are enabled).
- The leafcutter package built and installed in your project (`build.py` has
  run at least once, creating `.claude/settings.json`).
- You understand which Bash commands your phase agents regularly invoke.

---

## Step 1 — Locate your settings.json

The allowlist lives in `.claude/settings.json` at the root of your project.
This file is per-project; it is not shared across repos.

```bash
cat .claude/settings.json
```

If the file does not exist, create it:

```json
{
  "allowedTools": []
}
```

---

## Step 2 — Add the recommended allowlist entries

The leafcutter template ships a recommended allowlist at
`templates/settings.json`. The entries cover the commands that phase agents
most frequently invoke:

```json
{
  "allowedTools": [
    "Bash(git status*)",
    "Bash(git diff*)",
    "Bash(git log*)",
    "Bash(git add *)",
    "Bash(git commit*)",
    "Bash(git fetch*)",
    "Bash(git branch*)",
    "Bash(git checkout *)",
    "Bash(git mv *)",
    "Bash(git worktree *)",
    "Bash(gh pr create*)",
    "Bash(gh pr view*)",
    "Bash(gh pr list*)",
    "Bash(gh issue*)",
    "Bash(python -m pytest*)",
    "Bash(python scripts/*)",
    "Bash(pip install*)",
    "Bash(npm test*)",
    "Bash(npm run*)",
    "Bash(ls *)",
    "Bash(find . *)",
    "Bash(cat *)",
    "Bash(echo *)"
  ]
}
```

Copy these entries into your `.claude/settings.json`. If your project uses
additional tools (e.g. `cargo`, `make`, `docker`), add the relevant patterns.

---

## Step 3 — Understand allowedTools vs dangerouslyAllowTools

There are two allowlist keys in Claude Code settings:

### `allowedTools` (recommended)

- Allows specific tool invocations that match the pattern without prompting.
- Each entry is scoped: `"Bash(git status*)"` only pre-approves commands that
  start with `git status`, not all Bash commands.
- **Use this key** for the pre-approved list. It is the safe default.

### `dangerouslyAllowTools`

- Allows entire tool categories without any pattern restriction.
- Example: `"Bash"` (bare, no pattern) pre-approves every Bash command,
  including destructive ones (`rm -rf`, `git reset --hard`).
- **Avoid this key** unless you fully trust the agent's Bash usage and have
  reviewed the complete set of commands it might run.

For the workflow allowlist, always use `allowedTools` with specific patterns.

---

## Step 4 — Verify the allowlist is active

Restart Claude Code (close and reopen the session). Run a workflow command,
e.g.:

```
/build-ticket tickets/01_todo/my-ticket.md
```

Observe whether permission prompts appear for the listed commands. If a prompt
appears for a command you expected to be pre-approved, check:

1. The pattern in `allowedTools` — make sure it matches the exact command
   string the agent invokes (use `*` as a suffix wildcard).
2. Whether `.claude/settings.json` is in the correct location (repo root,
   not a subdirectory).

---

## Verification

After restarting Claude Code and running a workflow command, confirm that the
pre-approved commands no longer trigger permission prompts. You should see the
workflow proceed without any "Allow this action?" interruptions for the listed
commands.

To confirm `.claude/settings.json` is being read correctly:

```bash
cat .claude/settings.json | python -m json.tool
```

Expected output: well-formed JSON with an `allowedTools` array containing your
configured entries. If the command fails with a JSON parse error, fix the
syntax in `settings.json` before restarting Claude Code.

---

## Where to place the allowlist

The `allowedTools` key belongs in `.claude/settings.json` at the **project
root**. This is the per-project settings file that Claude Code reads on
session start.

Do not place it in:
- `~/.claude/settings.json` (user-global — affects all projects, not
  recommended for project-specific tool scopes).
- A nested subdirectory — Claude Code reads only the settings file at the
  repo root.

---

## Cross-References

- `docs/reference/workflow-constraints.md` — full description of workflow
  script constraints including the no-mid-run-steering constraint and
  crash-resume mechanism.
- `templates/settings.json` — the canonical template with the recommended
  `allowedTools` entries and pre-commit hook wiring.
- `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` — the
  architectural decision that introduced the workflow scripts.
