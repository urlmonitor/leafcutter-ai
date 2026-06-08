---
title: "How to use frontend-coder with design integration"
type: how-to
status: active
created: 2026-06-08
last_updated: 2026-06-08
components:
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-005-frontend-coder-agent.md
  - docs/how-to/creating-an-agent-template.md
  - docs/how-to/inject-project-knowledge-into-agents.md
---

# How to use frontend-coder with design integration

This guide explains how `frontend-coder` applies design principles automatically,
how to override those defaults for your project, and how this unified agent differs
from the older `frontend-coder + frontend-design skill` arrangement.

**Prerequisites:**

- leafcutter-ai installed and `build.py` run against your project (so `frontend-coder`
  appears in `.claude/agents/`).
- A ticket with `frontend-coder: needed` in its `agents:` frontmatter (set by
  `business-analyst` at refinement time for any ticket whose `files_touched` list
  contains `.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, `.css`, or `.scss` files).

---

## How the unified agent applies design principles automatically

`frontend-coder` embeds a set of design principles directly in its agent template.
These principles apply on every invocation — no extra configuration is needed.

The embedded defaults are:

| Principle | Default value |
|-----------|---------------|
| Primary colour | Neutral mid-grey (`#6b7280`) |
| Heading typeface | System sans-serif stack |
| Body typeface | System sans-serif stack |
| Spacing scale | 8 px base grid (multiples of 4 px at small sizes) |
| Accessibility contrast | WCAG 2.1 AA minimum (4.5:1 body, 3:1 large text) |
| Interactive states | Explicit `:hover`, `:focus-visible`, `:disabled` on every interactive element |
| Component structure | Single-responsibility; props over internal state where possible |
| Performance | No render-blocking resources; lazy-load images and heavy components |

The agent reads these principles at the start of every ticket run (Pre-Flight Reads
step) and applies them when generating or editing frontend files. You do not need to
mention "use accessible colour contrast" or "follow the spacing grid" in your ticket
— those constraints are always active.

The design principles section of the agent template also contains a
`### Project Design System Override` block (see the next section), which is where
project-level customisation happens.

---

## How to override defaults via PROJECT_CONTEXT.md

To enforce your project's brand colours and typefaces, add a `design_system` block
to `PROJECT_CONTEXT.md` (create the file if it does not exist):

```markdown
<!-- PROJECT_CONTEXT.md -->
## design_system

primary_colour: "#1d4ed8"       # Tailwind blue-700
font_heading: "Inter"           # Google Fonts
font_body: "Inter"
```

**What gets overridden:**

| Key | Embedded default that it replaces |
|-----|-----------------------------------|
| `primary_colour` | The default neutral mid-grey primary colour |
| `font_heading` | The system sans-serif heading typeface |
| `font_body` | The system sans-serif body typeface |

**What does NOT change:**

Every principle not listed in the table above (spacing scale, contrast ratio,
interactive states, component structure, performance) continues to use the
embedded defaults. `PROJECT_CONTEXT.md` narrows the customisation surface to
brand-identity values; quality guardrails are intentionally non-overridable.

**Override precedence chain (highest → lowest):**

1. `PROJECT_CONTEXT.md` `design_system` values — project brand constraints.
2. Embedded design principles — package-level quality defaults.
3. Browser/framework defaults — last resort, never intentional.

**Steps to apply an override:**

1. Create or edit `PROJECT_CONTEXT.md` in your project root (or the path
   configured in `skills_config.json` under `frontend.project_context_path`).
2. Add the `## design_system` section with the keys you want to override.
3. Run `build.py` if you have not already; no rebuild is needed for
   `PROJECT_CONTEXT.md` changes — the agent reads the file at invocation time.
4. Dispatch a ticket with `frontend-coder: needed`. The agent will read
   `PROJECT_CONTEXT.md` during Pre-Flight Reads and apply your overrides.

**Verification:** After `frontend-coder` signs off, inspect the generated UI
files for your `primary_colour` value (e.g. `#1d4ed8` for Tailwind blue-700).
The sign-off comment's `completion_manifest` will include
`design_principles_applied: true`, confirming the override path was exercised.

---

## How the agent differs from the previous frontend-coder + skill split

Before EPIC-Oneagenthandlesboththelookandthecodefor, the frontend workflow used two
separate artifacts:

| Artifact | Role | Location |
|----------|------|----------|
| `frontend-coder` agent template | Implementation logic | `.claude/agents/frontend-coder.md` |
| `frontend-design` skill | Design principles | `.claude/skills/frontend-design/SKILL.md` |

The agent loaded the skill at runtime via a conditional `Read` in its Pre-Flight Reads
step: "if `.claude/skills/frontend-design/SKILL.md` exists, load it." This meant:

- Projects that had not installed the skill got no design enforcement at all.
- Projects that installed the skill got design principles applied — but the skill
  and agent were versioned independently, causing drift when one was updated without
  the other.
- The agent's sign-off log showed only `frontend-coder: signed_off`, with no record
  of whether design principles were applied.

**What changed:**

The design principles are now **embedded directly in the `frontend-coder` agent
template**. The agent no longer loads `frontend-design/SKILL.md`, even if the
file is present on disk. Every project that has `frontend-coder` installed
automatically gets design enforcement — there is no optional-install step.

Key behaviour changes:

| Behaviour | Old (skill split) | New (unified) |
|-----------|-------------------|---------------|
| Design principles active | Only when skill installed | Always (embedded) |
| Skill file checked | Yes (`ls .claude/skills/frontend-design/`) | No (file ignored) |
| `design_principles_applied` in sign-off | Missing or conditional | Always `true` |
| Brand override mechanism | None | `PROJECT_CONTEXT.md` `design_system` key |

**Compatibility note:** If your project still has `.claude/skills/frontend-design/SKILL.md`
from a previous install, the file is harmless — `frontend-coder` does not load it and
no error is produced. You may delete it during your next `build.py` run or leave it in
place; behaviour is identical either way.

---

## Before/after example: same ticket under old vs new setup

**The ticket:**

```yaml
# Ticket excerpt
title: Add primary action button to dashboard
files_touched:
  - src/components/DashboardActionButton.tsx
agents:
  frontend-coder: needed
```

### Old setup (frontend-coder + frontend-design skill split)

**Scenario A: `frontend-design` skill NOT installed**

```
ticket-supervisor dispatches frontend-coder
  → Pre-Flight: checks .claude/skills/frontend-design/SKILL.md — not found
  → No design principles loaded
  → Writes DashboardActionButton.tsx with no colour or typography constraints
  → Sign-off comment:
     completion_manifest:
       code_implemented: true
       ui_verified: true
       design_principles_applied: false   # skill not installed
```

The button is rendered, but uses the framework's unstyled defaults. No brand
colour, no accessible contrast guarantee.

**Scenario B: `frontend-design` skill installed**

```
ticket-supervisor dispatches frontend-coder
  → Pre-Flight: checks .claude/skills/frontend-design/SKILL.md — found, loads it
  → Design principles from skill applied
  → Writes DashboardActionButton.tsx with skill-defined colour (#333)
  → Sign-off comment:
     completion_manifest:
       code_implemented: true
       ui_verified: true
       design_principles_applied: true   # skill loaded
```

The button gets the skill's embedded defaults, but if `frontend-design/SKILL.md`
drifted from the agent template, the principles may conflict.

### New setup (unified frontend-coder with embedded design)

```
ticket-supervisor dispatches frontend-coder
  → Pre-Flight: reads PROJECT_CONTEXT.md — finds design_system.primary_colour: "#1d4ed8"
  → Embedded principles active; PROJECT_CONTEXT.md values override primary_colour
  → Writes DashboardActionButton.tsx:
      - Uses bg-blue-700 / #1d4ed8 for primary action
      - WCAG AA contrast verified (white text on blue-700 = 4.6:1)
      - Explicit :hover, :focus-visible states present
      - Inter font applied to button label (from font_body override)
  → Sign-off comment:
     completion_manifest:
       code_implemented: true
       ui_verified: true
       design_principles_applied: true   # always true; embedded + overrides applied
```

The button is brand-consistent, accessible, and interactive-state complete —
regardless of whether any skill file is installed.

---

## Troubleshooting

**Q: The agent signed off but `design_principles_applied` is `false` in the manifest.**

This should not happen with the unified agent — `design_principles_applied` is always
`true` because design principles are embedded, not conditional. If you see `false`:
- Check that you are running the updated `frontend-coder` template (post-EPIC-Oneagenthandlesboththelookandthecodefor).
- Run `build.py --target-dir .` to redeploy the agent template from the package.

**Q: My `PROJECT_CONTEXT.md` overrides are not being applied.**

1. Confirm the file exists at the path configured in `skills_config.json` under
   `frontend.project_context_path` (default: `.agents/agents/frontend-coder/PROJECT_CONTEXT.md`).
2. Confirm the `design_system` block uses the exact key names: `primary_colour`,
   `font_heading`, `font_body`.
3. Confirm the block is under the `## design_system` heading (not inside a code fence).

**Q: I still have `.claude/skills/frontend-design/SKILL.md` from an old install. Should I delete it?**

It is safe to delete. `frontend-coder` does not load the file and will not error if
it is absent. Keeping it wastes a few kilobytes but causes no functional change.
