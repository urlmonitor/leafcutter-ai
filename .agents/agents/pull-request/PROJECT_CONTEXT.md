# Project Context — pull-request agent (leafcutter-ai repo)

This file is loaded by the pull-request agent at startup (Pre-Flight step) when
running inside the leafcutter-ai repository. It provides project-specific context
that overrides or augments the portable template defaults.

Reference: `docs/conventions/PROJECT_CONTEXT-injection.md`

---

## EMU Account Restriction

This repository is owned by an Enterprise Managed User (EMU) GitHub account. EMU
accounts cannot create pull requests via `gh pr create` — GitHub returns:

```
Unauthorized: As an Enterprise Managed User, you cannot access this content (createPullRequest)
```

**Before any `gh pr create` call, you MUST:**

1. Check the active GitHub CLI account:
   ```bash
   gh auth status
   ```
2. If the active user is NOT `urlmonitor`, switch accounts:
   ```bash
   gh auth switch --user urlmonitor
   ```
3. Warn the user that the account was switched:
   > "Switched GitHub CLI auth to urlmonitor account before creating PR."
4. Then proceed with `gh pr create`.

**SSH host alias:** This repo uses `github.com-urlmonitor` as the SSH host alias
(key: `~/.ssh/id_urlmonitor`). Git remote operations use this alias automatically
if the remote URL is set to `git@github.com-urlmonitor:urlmonitor/leafcutter-ai.git`.

**Repo path:** `/home/henzeh/projects/leafcutter/leafcutter-ai/`

This EMU guard automates what was previously a manual pre-drive step described in
`CLAUDE.md` §Pre-Drive Checklist (EMU account section). See also feedback entry
`fb_2026-06-03_80dafa72` which captured the original exhausted-adjudication-ladder
failure mode.

---

## PR Writing Standards

### Title

- **Mood**: imperative mood, present tense (e.g. "Add X", "Fix Y", "Update Z")
- **Length**: 70 characters maximum — hard limit enforced by GitHub UI display
- **Punctuation**: no trailing period
- **Example (good)**: `Add PROJECT_CONTEXT.md support to pull-request agent`
- **Example (bad)**: `Added PROJECT_CONTEXT.md support to the pull-request agent.`

### Description Body

Use this exact structure (matches the project's base `gh pr create` template):

```markdown
## Summary
- <bullet 1>
- <bullet 2>
- <bullet 3 — up to 3 bullets, no more>

## Test plan
- [ ] <testing step 1>
- [ ] <testing step 2>

Generated with [Claude Code](https://claude.com/claude-code)
```

**Summary rules:**
- Maximum 3 bullets — do not exceed this count
- Each bullet is one sentence describing a concrete change or outcome
- Use past tense in bullets ("Added X", "Fixed Y") since the commits already exist

**Test plan rules:**
- List concrete manual verification steps as checkboxes
- Include at least one step the reviewer can run themselves
- Reference the test file(s) introduced by the ticket when applicable

**Footer:**
- Always include the `Generated with [Claude Code](https://claude.com/claude-code)` footer
- Place it after the Test plan section, separated by a blank line

---

## Key References

- `docs/conventions/PROJECT_CONTEXT-injection.md` — full convention for PROJECT_CONTEXT injection
- `docs/how-to/inject-project-knowledge-into-agents.md` — step-by-step adoption guide
- `CLAUDE.md` §Pre-Drive Checklist — EMU account section (manual pre-drive steps)
