---
title: "feat/debug-skill — Add /debug multi-angle investigation skill"
date: "2026-06-01"
time: "23:26"
type: feature
components: 
  - build_pipeline
summary: "Added a new /debug slash command that spawns three parallel investigative agents (database, backend, and frontend/docs) to diagnose issues from different angles, synthesizes findings, creates a fix ticket, and drives it through the build pipeline."
description: "1 commit (275a482) introduced via PR #29. New artifacts: templates/skills/debug/SKILL.md (full 5-step investigation protocol: parallel spawn, synthesis, user clarification, create-ticket agent, /build-feature handoff) and templates/workflows/debug.md (thin dispatcher that reads the SKILL.md). Category: Features."
pr: 29
commits: 
  - 275a482
breaking: false
migration_steps: []
---

## Entry

PR #29 adds the `/debug` slash command — a structured, multi-angle issue investigation workflow that automates the diagnostic triage step before fix implementation begins.

### What was delivered

**`templates/skills/debug/SKILL.md`**

The primary skill file defining the full five-step investigation protocol:

1. **Spawn** — three investigative agents are launched in parallel, each holding a distinct mandate:
   - Agent 1 (Database & Data Layer): searches models, schemas, migrations, ORM code, and data-integrity constraints.
   - Agent 2 (Backend & Logic): traces code paths, checks business logic, error handling, and API contracts.
   - Agent 3 (Frontend, Config & Documentation): inspects frontend components, configuration files, and the `docs/` folder for discrepancies between documentation and the actual code.

2. **Synthesize** — after all three agents return, their findings are merged into a structured summary covering agreed findings, conflicts, uncertain areas, documentation discrepancies, and a consolidated root-cause assessment.

3. **Clarify** — when agent confidence is high and there are no conflicts, the skill presents the diagnosis and asks for brief user confirmation before proceeding. When agents disagree or report low confidence, the skill asks the user targeted questions (not vague open-ended prompts) to resolve the ambiguity.

4. **Ticket** — once the diagnosis is confirmed, the `create-ticket` agent is invoked with the issue description, confirmed root cause, files to touch, and any documentation discrepancies to address.

5. **Build** — the skill invokes `/build-feature` to drive the fix ticket through the standard build pipeline, handing off to the normal ticket execution flow from that point.

**`templates/workflows/debug.md`**

A thin workflow dispatcher that routes the `/debug` invocation to `templates/skills/debug/SKILL.md`. Follows the same pattern as other workflow dispatchers in the project.

### Adaptation rules

The three default investigation angles (database, backend, frontend/docs) are replaceable when a project's architecture differs: projects without a database layer should substitute an infrastructure/deployment investigator for Agent 1; projects without a frontend should substitute a testing/CI investigator for Agent 3. The `docs/` discrepancy check is mandatory for all three agents regardless of adaptation.

### Breaking changes

None. The skill and workflow are new additions; no existing templates or configuration files were modified.
