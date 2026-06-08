---
title: "ADR-005: frontend-coder as a First-Class Sibling Implementation Agent"
type: "adr"
status: "active"
created: "2026-05-28"
last_updated: "2026-06-08"
components:
  - build_pipeline
---

# ADR-005: frontend-coder as a First-Class Sibling Implementation Agent

## Status

Accepted (2026-05-28)

## Context

The leafcutter-ai ticket pipeline dispatches implementation work through phase agents: `python-coder` handles Python code, `sql-coder` handles SQL migrations and queries. As leafcutter is adopted by teams building web applications, tickets involving React, Vue, HTML/CSS, and TypeScript components appear with increasing frequency. Without a dedicated agent, these tickets are either routed incorrectly to `python-coder` (wrong skill set) or left unrouted (no agent picks them up).

Two architectural patterns were considered for adding frontend support:

1. **Sub-agent of python-coder**: `python-coder` spawns a `frontend-coder` child when it detects frontend file extensions in `files_touched`. Keeps the dispatch loop unchanged.
2. **Sibling implementation agent**: `frontend-coder` is a peer to `python-coder` and `sql-coder`, dispatched directly by `ticket-supervisor` at a defined priority slot.

The sub-agent pattern was rejected for three reasons:

- It breaches the **depth-3 agent cap**: `epic-supervisor (1) → ticket-supervisor (2) → python-coder (3) → frontend-coder (4)`. The cap exists because agent nesting past depth 3 degrades observability, makes retry logic brittle, and complicates the commit-phase serialization lock.
- It **overloads `python-coder`** with frontend concerns. `python-coder` has no Stop-and-Ask rule for HTML/CSS/JS files, no awareness of framework tooling (Vite, webpack, esbuild), and no optional-skill integration contract. Augmenting it would require forking its prompt into a multi-persona agent — harder to maintain and test.
- It **obscures the dispatch log**: a ticket with both backend and frontend work would show `python-coder: signed_off` as the only record, hiding that frontend sub-work was done and preventing the BA from assigning `frontend-coder: needed` at refinement time.

The optional-skill integration contract (webapp-testing, frontend-design) also needed a home. The sibling pattern gives `frontend-coder` its own agent template where the skill-loading logic is self-contained, rather than burying it inside a sub-spawn branch of `python-coder`.

## Decision

`frontend-coder` is added as a **first-class sibling implementation agent** at **priority 8** in the `ticket-supervisor` dispatch order (between `sql-coder` at priority 7 and `test-runner` at priority 9). It is registered in `agent_registry.json` with `is_ticket_phase: true`, `default_status: "not_needed"`, and selection criteria scoped to frontend file extensions (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, `.css`, `.scss`).

### Optional-skill integration contract

`frontend-coder` detects installed optional skills by checking file existence at the expected path. The detection logic is:

- **webapp-testing**: if `.claude/skills/webapp-testing/SKILL.md` exists, invoke the skill after making UI changes to capture a screenshot and verify no console errors.
- **frontend-design (legacy)**: the `frontend-design` skill is **no longer loaded** by `frontend-coder`, regardless of whether `.claude/skills/frontend-design/SKILL.md` exists on disk. Design principles are embedded directly in the agent template (see `## Embedded Design Principles` section). If a project still has `.claude/skills/frontend-design/SKILL.md` from a previous install, `frontend-coder` ignores it entirely.

This change was introduced to satisfy AC `BP-700a-1-i`: when the unified frontend agent template is deployed, it uses only its embedded design principles, preventing the agent from applying design constraints twice (once from the embedded principles and once from the external skill file).

To satisfy AC `BP-700a-2`, the `frontend-coder` agent always reports `design_principles_applied: true` in the `### Optional skills` block of its completion report. This entry is unconditional — design principles are always embedded and always applied, so no conditional flag or "not installed" message is needed or produced.

### Project design system override (AC BP-700a-3)

To satisfy AC `BP-700a-3`, `frontend-coder` supports a project-level design system override via `PROJECT_CONTEXT.md`. When the file at `{{frontend.project_context_path}}` contains a `design_system` key, the agent uses those values to override the corresponding embedded defaults:

- `design_system.primary_colour` overrides the "primary colour" embedded principle.
- `design_system.font_heading` overrides the heading typeface in the "custom font pairing" embedded principle.
- `design_system.font_body` overrides the body typeface in the "custom font pairing" embedded principle.

The embedded principles remain active for every aspect **not** covered by the project design system (negative space, accessibility contrast, interactive states, component structure, performance). This gives adopters a way to enforce brand consistency without sacrificing the quality guardrails that the embedded principles provide.

**Override precedence chain (highest → lowest):**

1. `PROJECT_CONTEXT.md` `design_system` values — project-specific brand constraints.
2. Embedded design principles — package-level quality defaults.
3. Browser/framework defaults — last resort, never intentional.

The override is read during the Pre-Flight Reads step and applied in the Embedded Design Principles / Project Design System Override section of the agent template. No additional configuration is required beyond populating `design_system` in PROJECT_CONTEXT.md.

File-existence detection is chosen over a registry lookup because:
- It requires zero infrastructure beyond the filesystem.
- It is consistent with how `build.py` deploys skills: if the skill directory exists, the skill is installed.
- It makes the detection logic verifiable with a single `ls` invocation.

### Delegation boundaries (Stop-and-Ask rules)

`frontend-coder` MUST NOT write Python or SQL code. When a ticket's implementation requires backend logic, `frontend-coder` appends a `(status: handoff)` comment naming `python-coder` or `sql-coder` as the recipient. This mirrors the delegation pattern used between existing sibling agents.

### Priority slot rationale

Priority 8 (after `sql-coder` at 7, before `test-runner` at 9) is chosen because:
- Frontend implementation must complete before tests run (test-runner needs the rendered output or component to exist).
- SQL schema changes may inform the frontend data model, so SQL work should complete first.
- The slot is symmetric with `sql-coder`'s position relative to `python-coder`, making the dispatch table easy to read.

## Consequences

**Positive:**
- Tickets involving `.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, `.css`, `.scss` files are correctly routed at BA/refinement time without manual intervention.
- The `frontend-coder` agent template is self-contained: all frontend conventions, stop-and-ask rules, and optional-skill integration live in one file.
- Optional skills (webapp-testing, frontend-design) compose cleanly without changing the `ticket-supervisor` dispatch loop.
- The commit-phase serialization lock continues to work correctly — `frontend-coder` is a leaf agent, not a spawner.

**Negative:**
- Full-stack tickets (Python backend + React frontend) require two agents: `python-coder` at priority 6 and `frontend-coder` at priority 8. Both `agents: needed` entries must be set by the BA. This is slightly more ceremony than a single-agent route, but it gives precise sign-off granularity.
- Adopters must run `build.py` after the EPIC-FrontendAgent branch merges to deploy the new agent template. Existing installs do not auto-update.

**Neutral:**
- The `business-analyst` archetype table gains a "Frontend / UI feature" row. This is an additive change; all existing archetype rows are unaffected (they receive `frontend-coder: not_needed`).
- `skills_config.default.json` gains a `frontend` key. The key is ignored by adopters who do not install `frontend-coder`.

## Alternatives Considered

1. **Overload python-coder with a `--mode frontend` flag**: Rejected. Adds a code-path branch to a stable, well-tested agent. Mode flags are not part of the leafcutter agent protocol; agents are identified by name, not invocation flags.

2. **Separate `frontend-coder` repo / package**: Rejected. The leafcutter package is distributed as a single unit; a separate package would fragment the install story and require adopters to manage two build scripts.

3. **BA-side routing only (no template change)**: Rejected. Without a dedicated agent template, `ticket-supervisor` has no dispatch slot for frontend work. The BA could assign `python-coder: needed` as a fallback, but this loses the Stop-and-Ask rules, the optional-skill integration, and the frontend-specific pre-flight reads.
