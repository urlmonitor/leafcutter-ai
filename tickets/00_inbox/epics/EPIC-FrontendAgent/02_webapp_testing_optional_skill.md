---
title: "Author the webapp-testing optional skill template"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_frontend_coder_agent_template.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/webapp-testing/SKILL.md
agents:
  architect-review: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02: Author the webapp-testing optional skill template

## Actor / Goal

In order to give `frontend-coder` verifiable feedback on its UI changes, we need a `webapp-testing` skill template so that the agent can take Playwright screenshots, capture browser console logs, and interact with the running app before signing off.

## Context

This is an optional skill — it is only installed when the user opts in during `/onboard` (or manually copies the skill file). The skill template lives in `leafcutter-ai/templates/skills/webapp-testing/SKILL.md` and is deployed to `.claude/skills/webapp-testing/SKILL.md` by `build.py`.

The `webapp-testing` skill is consumed exclusively by `frontend-coder`. When `frontend-coder` detects the skill is installed (i.e. `.claude/skills/webapp-testing/SKILL.md` exists), it invokes the skill after making UI changes to capture a screenshot and verify no console errors.

The skill should:
- Document the Playwright-based operations available (screenshot, console-log capture, click/type interactions)
- Specify the entry contract (what the calling agent passes: URL or app startup command, test steps)
- Specify the exit contract (what the skill returns: screenshot path, console-log summary, pass/fail verdict)
- Include a note for Antigravity adopters: skip this skill (Antigravity uses its internal browser)
- Include a fallback for projects where Playwright is not installed: log a warning and exit gracefully

Depends on ticket 01 because the skill's entry/exit contracts are defined jointly with the frontend-coder agent's optional-skill integration section.

## Acceptance Criteria

```gherkin
Given leafcutter-ai/templates/skills/webapp-testing/SKILL.md is created
When build.py --target-dir . is run
Then .claude/skills/webapp-testing/SKILL.md exists and passes the skill frontmatter guard

Given a frontend-coder agent loads the webapp-testing skill
When it calls the skill with a URL and a list of test steps
Then the skill returns a screenshot path and a console-log summary

Given Playwright is not installed in the adopter's environment
When webapp-testing skill is invoked
Then it logs a one-line warning and exits without blocking the agent

Given an Antigravity adopter installs this skill
When they read the skill header
Then a clearly visible note instructs them to skip this skill (Antigravity provides its own browser)
```

## Sign-offs

- [ ] architect-review
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert

- [ ] Create `leafcutter-ai/templates/skills/webapp-testing/SKILL.md` with: YAML frontmatter (name: webapp-testing, allowed-tools: Bash Read Write), an Antigravity skip note at the top, an Input Contract section (URL or app-start command + test steps), an Operations section (screenshot, console-log capture, click/type interactions using Playwright CLI or npx playwright), an Output Contract section (screenshot path, console-log summary, pass/fail verdict), a Playwright-not-installed fallback (warn + exit 0), and a Constraints section.

## Risk & Safety

- Touches money? No.
- Touches data? No — skill is a markdown template; no runtime side effects until installed and invoked.
- Reversibility? Fully reversible. The skill file can be removed without affecting other agents.
- Shared contract? The skill's entry/exit contracts are referenced by frontend-coder. Changes to them after ticket 01 is merged must be backward-compatible or coordinated with a frontend-coder update.
