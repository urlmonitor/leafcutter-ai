---
name: debug
description: >-
  Multi-angle debugging workflow. Spawns three parallel investigative agents
  (database, backend, frontend/docs) to diagnose an issue from different
  perspectives, synthesizes findings, creates a fix ticket via create-ticket
  agent, and builds it via build-feature. Asks the user for clarification
  when investigators are uncertain.
allowed-tools: Bash(git *), Bash(find *), Bash(grep *), Bash(ls *), Read, Agent
---

# /debug — Multi-Angle Issue Investigation & Fix

Diagnose and fix: **$ARGUMENTS**

If `$ARGUMENTS` is empty, ask the user to describe the issue they want
investigated and stop.

## Overview

This skill orchestrates a three-pronged investigation of a reported issue,
then automatically creates and drives a fix ticket. The workflow:

1. **AC Lookup** — query the AC store for declared expected behaviour of the
   components implied by the issue description
2. **Investigate** — spawn 3 parallel agents, each examining the issue from
   a different angle
3. **Synthesize** — merge findings, identify agreement and uncertainty
4. **Clarify** — if agents disagree or are uncertain, ask the user
5. **Ticket** — create a fix ticket via `create-ticket` agent
6. **Build** — drive the ticket via `/build-feature`

---

## Step 0 — AC Store Query

Before spawning the investigative agents, perform a lightweight AC lookup to
ground each investigator with the system's declared expected behaviour.

1. **Check for the AC store.** Test whether `docs/acceptance-criteria/` exists
   in the target project.
   - If it does NOT exist: log the message below and skip to Step 1.
     ```
     AC store not found — investigators will work without declared expected behaviour.
     ```
   - If it exists: proceed to component inference (step 2 below).

2. **Infer 1–3 component slugs** from the issue description:
   - If the description contains a file path (e.g.
     `templates/agents/business-analyst.md`), extract the enclosing directory or
     module name and normalise to a lowercase-hyphenated slug
     (e.g. `business-analyst`).
   - If the description mentions a recognisable component name directly (e.g.
     "finalize", "business-analyst"), use that slug.
   - If the description is ambiguous and no specific component is identifiable:
     - Log: "component inference ambiguous"
     - Use all component slugs that have a directory under
       `docs/acceptance-criteria/`.

3. **Load active ACs.** For each inferred component slug, read all `.yaml` files
   under `docs/acceptance-criteria/{slug}/` where `status: active`. Extract the
   `id`, `title`, and `criteria` fields for each.

4. **Cap and build the injection block.**
   - If no ACs are found across all inferred components: set `AC_CONTEXT` to an
     empty string and proceed — do NOT add the section to investigator prompts.
   - If ACs are found: cap the total at **10 ACs** (take the first 10 by
     filename sort if more exist). Build `AC_CONTEXT` using this format:

     ```
     ## Declared Expected Behaviour

     The following active Acceptance Criteria govern the components most likely
     involved in this issue. Use them as ground truth when evaluating whether
     observed behaviour is a regression or an intended design:

     AC-{ID}: {title}
       {criteria (indented, verbatim from YAML)}

     AC-{ID}: {title}
       {criteria}
     ```

5. Store the result in `AC_CONTEXT`. Pass it to Step 1.

---

## Step 1 — Spawn Three Investigative Agents

Spawn all three agents **in parallel** using the `Agent` tool. Each agent
receives the issue description from `$ARGUMENTS`, the `AC_CONTEXT` built in
Step 0 (empty string when the AC store was absent or no ACs were found), plus
its specific investigation mandate below.

### Agent 1: Database & Data Layer Investigator

Prompt template (fill in `$ARGUMENTS` as the issue):

```
You are investigating a reported issue from the DATABASE and DATA LAYER
perspective.

**Issue:** {$ARGUMENTS}

{AC_CONTEXT}

Your investigation mandate:
1. Search for relevant database models, schemas, migrations, SQL files,
   and ORM code. Look for tables, columns, constraints, indexes that
   relate to the issue.
2. Check for data integrity issues — missing foreign keys, nullable
   columns that shouldn't be, missing indexes on queried columns.
3. Look at any database-related configuration (connection strings,
   pool sizes, timeouts).
4. Check the docs/ folder for any documentation about the data model
   or database architecture. Flag discrepancies between docs and code.
5. Search git log for recent changes to database-related files that
   might have introduced the issue.

**Output format:**
Return a structured report:
- FINDINGS: numbered list of concrete findings with file paths and line numbers
- DOCS_DISCREPANCIES: any mismatches between docs/ and actual code/schema
- ROOT_CAUSE_HYPOTHESIS: your best guess at the root cause from this angle
- CONFIDENCE: high / medium / low
- UNCERTAINTY: what you couldn't determine and why
- SUGGESTED_FIX: specific changes you'd recommend
```

### Agent 2: Backend & Logic Investigator

Prompt template:

```
You are investigating a reported issue from the BACKEND and BUSINESS LOGIC
perspective.

**Issue:** {$ARGUMENTS}

{AC_CONTEXT}

Your investigation mandate:
1. Search for relevant Python/backend code — functions, classes, API
   endpoints, middleware, services, utilities that relate to the issue.
2. Trace the code path that the issue touches. Follow imports, function
   calls, and data flow.
3. Look for logic errors — wrong conditionals, missing edge cases,
   incorrect transformations, race conditions.
4. Check error handling — are exceptions caught and handled properly?
   Are there silent failures?
5. Check the docs/ folder for any documentation about the backend
   architecture, API contracts, or business rules. Flag discrepancies
   between docs and code.
6. Search git log for recent changes to backend files that might have
   introduced the issue.

**Output format:**
Return a structured report:
- FINDINGS: numbered list of concrete findings with file paths and line numbers
- DOCS_DISCREPANCIES: any mismatches between docs/ and actual code
- ROOT_CAUSE_HYPOTHESIS: your best guess at the root cause from this angle
- CONFIDENCE: high / medium / low
- UNCERTAINTY: what you couldn't determine and why
- SUGGESTED_FIX: specific changes you'd recommend
```

### Agent 3: Frontend, Config & Documentation Investigator

Prompt template:

```
You are investigating a reported issue from the FRONTEND, CONFIGURATION,
and DOCUMENTATION perspective.

**Issue:** {$ARGUMENTS}

{AC_CONTEXT}

Your investigation mandate:
1. Search for relevant frontend code — components, templates, styles,
   client-side logic, API calls from the UI layer.
2. Check configuration files — settings, environment variables, feature
   flags, build config. Look for misconfigurations or missing values.
3. Thoroughly review the docs/ folder:
   - Are there docs that describe the feature/area related to this issue?
   - Do the docs match the current code behavior?
   - Are there outdated instructions, wrong file paths, or missing docs?
   - Check architecture docs, how-to guides, and READMEs for accuracy.
4. Check for integration issues — mismatched API contracts between
   frontend and backend, wrong URL paths, missing CORS config.
5. Search git log for recent changes to frontend, config, or doc files
   that might have introduced the issue.

**Output format:**
Return a structured report:
- FINDINGS: numbered list of concrete findings with file paths and line numbers
- DOCS_DISCREPANCIES: any mismatches between docs/ and actual code/config
- ROOT_CAUSE_HYPOTHESIS: your best guess at the root cause from this angle
- CONFIDENCE: high / medium / low
- UNCERTAINTY: what you couldn't determine and why
- SUGGESTED_FIX: specific changes you'd recommend
```

Use `subagent_type: "Explore"` for all three agents so they have full
read-only search capability. Label them clearly:
- Agent 1: `description: "Debug: database investigation"`
- Agent 2: `description: "Debug: backend investigation"`
- Agent 3: `description: "Debug: frontend/docs investigation"`

---

## Step 2 — Synthesize Findings

After all three agents from Step 1 return, synthesize their reports:

1. **Collect all findings** — merge the numbered lists from all three agents.
2. **Identify agreement** — where do 2+ agents point to the same root cause
   or the same files? Agreement is strong signal.
3. **Identify conflicts** — where do agents disagree on the root cause?
4. **Identify uncertainty** — where did agents report low confidence or
   could not determine something?
5. **Check docs discrepancies** — compile all docs vs code mismatches
   found across all three investigations.

Build a synthesis summary with these sections:
- **Agreed findings** (2+ agents concur)
- **Conflicting findings** (agents disagree)
- **Uncertain areas** (low confidence from any agent)
- **Documentation issues** (all docs discrepancies)
- **Consolidated root cause** (your best assessment)
- **Consolidated fix plan** (merged suggested fixes)

---

## Step 3 — Clarify with User (if needed)

Present the synthesis summary to the user. Then:

**If confidence is high across all agents and there are no conflicts:**
Tell the user the diagnosis and proposed fix. Ask for a brief confirmation
before proceeding: "The investigation points to [X]. Shall I create a
ticket and fix it?"

**If there are conflicts, low confidence, or significant uncertainty:**
Present the specific areas of disagreement or uncertainty to the user.
Ask targeted questions — do NOT ask vague "what do you think?" questions.
Example: "Agent 1 thinks the issue is a missing index on `user_id`, but
Agent 2 thinks it's a logic error in the query filter. Which area should
we focus on?"

Wait for the user's response before proceeding.

---

## Step 4 — Create Fix Ticket

Once the diagnosis is confirmed (either by high-confidence agreement or
user clarification), spawn the `create-ticket` agent:

```
Agent(
  subagent_type: "create-ticket",
  description: "Debug: create fix ticket",
  prompt: "<issue summary and confirmed root cause, consolidated fix plan,
           files to touch, docs discrepancies to fix>"
)
```

Include in the prompt to `create-ticket`:
- The original issue description
- The confirmed root cause
- The specific files that need changes (from the investigation)
- Any documentation discrepancies that should be fixed in the same ticket
- The suggested fix approach
- **AC origin tracking instruction:** "Instruct the BA/wiring step to set
  `origin_agent: debug` on any AC YAML files created as part of this fix
  ticket." This ensures compliance auditing can identify debug-workflow-
  generated ACs (which differ from BA-generated or human-authored ACs).

---

## Step 5 — Build the Ticket

After `create-ticket` returns with the ticket path, invoke `/build-feature`
to drive it:

```
Skill(skill: "build-feature", args: "<ticket-path>")
```

If `/build-feature` encounters blockers, surface them to the user as
normal — the debug workflow hands off to the standard build pipeline
from this point.

---

## Adaptation Rules

The three investigation angles (database, backend, frontend/docs) are
defaults. If the project clearly has no database layer, replace agent 1
with an infrastructure/deployment investigator. If the project has no
frontend, replace agent 3 with a testing/CI investigator. Use judgment
based on what exists in the repo.

The docs/ check is mandatory for ALL three agents regardless of
adaptation — every investigator must check docs for discrepancies
in their area.
