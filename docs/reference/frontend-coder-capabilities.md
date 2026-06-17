---
title: "frontend-coder Unified Agent — Preserved Capabilities Reference"
type: reference
status: active
created: "2026-06-18"
source_ac: BP-700c-5
components:
  - build-pipeline
---

# frontend-coder Unified Agent — Preserved Capabilities Reference

This document catalogues every capability preserved when the `frontend-design` skill
and the legacy `frontend-coder` agent template were unified into the single
`frontend-coder` template. Use it to verify that no design principle or behavioral
rule was lost during the consolidation, and to understand where each capability now
lives.

See [ADR-005](../architecture/adrs/ADR-005-frontend-coder-agent.md) for the full
design rationale behind the sibling-agent architecture and the unification decision.

---

## 1. Design Principles (from the old frontend-design skill)

All five design principles originally provided by the `frontend-design` optional skill
are now **embedded directly in the agent template** under the `## Embedded Design
Principles` section. They apply on every invocation without requiring the skill to
be installed or loaded.

### Principle 1 — Custom font pairing, not the browser default

Never use `font-family: sans-serif` or `font-family: system-ui` without a named
preferred font. Always define a clear type hierarchy with a heading font and a body
font that have different visual weights or character.

```css
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;500&display=swap');
body { font-family: 'Inter', system-ui, sans-serif; }
h1, h2, h3 { font-family: 'Playfair Display', Georgia, serif; }
```

State the chosen fonts in a comment at the top of the stylesheet. If `PROJECT_CONTEXT.md`
defines `font_heading` and `font_body` under a `design_system` key, those values
override this principle (see §2 — Project Design System Override).

### Principle 2 — A primary colour with deliberate personality

Never default to `#3B82F6` (Tailwind `blue-500`) unless it is the project's documented
brand colour. Choose a primary colour that conveys the product's character and state
the rationale in a comment:

```css
/* Primary: #0D9488 (deep teal) — chosen for trust and precision in a financial context */
```

If `PROJECT_CONTEXT.md` defines `primary_colour` under `design_system`, use that value
without modification.

### Principle 3 — Intentional negative space

White space (or dark space in dark-theme UIs) is an active design choice. Rules:

- Heading-to-body margin: at least `0.5em` above and below.
- Card padding: at least `1.5rem` on all sides; never less than `1rem`.
- Between major sections: `gap` or `margin` of at least `2rem`.
- Do NOT use `p-2` as the default card padding in Tailwind (8px is too tight).

Prefer CSS custom properties (`--spacing-sm`, `--color-primary`) over hard-coded pixel
values. Use CSS Grid or Flexbox for layout. Target WCAG 2.1 AA contrast ratios
(4.5:1 for normal text, 3:1 for large text).

### Principle 4 — Deliberate interactive states

Every interactive element (button, link, input, card-with-click) MUST have explicit
`:hover`, `:focus`, and `:active` styles. Do NOT rely on browser defaults.

```css
/* Good: deliberate, visible, on-brand focus ring */
button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 3px;
}
```

Every interactive element must be keyboard-reachable with a visible focus indicator.
Images require an `alt` attribute; decorative images use `alt=""`. Form inputs require
an associated `<label>`.

### Principle 5 — Component-level personality through detail

Apply at least one of the following per component:

- A border-radius that is clearly sharp (0–2px) or clearly rounded (12px+). Avoid the
  generic 4px default.
- A carefully chosen icon size (20px for inline, 24px for standalone) — no mixed sizes.
- A micro-animation on state change (200ms ease-out transform or opacity).
- A deliberate `text-transform` choice (uppercase tracking for labels, not for body).

### Pre-Write Checklist (preserved from §4 of the old skill)

Before writing any markup, CSS, or component output, answer all six questions:

1. **Font pairing**: custom pair specified, or browser default?
2. **Primary colour**: deliberate choice with rationale, or default Tailwind blue?
3. **Negative space**: deliberate breathing room, or pixel-packed?
4. **Interactive states**: `:hover`, `:focus-visible`, and `:active` on all interactive elements?
5. **Component detail**: at least one deliberate design detail per component?
6. **Distinctiveness**: would this look different from 100 other AI-generated UIs?

Do not produce output until all six questions have a satisfactory answer.

---

## 2. Project Design System Override

When `PROJECT_CONTEXT.md` (at the path configured by `frontend.project_context_path`)
contains a `design_system` key, those values **override** the corresponding embedded
principle defaults:

| `design_system` key | Overrides |
|---|---|
| `primary_colour` | Principle 2 — primary colour choice |
| `font_heading` | Principle 1 — heading font in the custom font pair |
| `font_body` | Principle 1 — body font in the custom font pair |
| Any other key (e.g. `border_radius`, `spacing_unit`) | Honoured as a project-level constraint |

The embedded principles remain active for every aspect **not** covered by the project
design system (negative space, accessibility contrast, interactive states, component
structure, performance). The precedence chain is:

1. `PROJECT_CONTEXT.md` `design_system` values — highest priority.
2. Embedded design principles — package-level defaults.
3. Browser / framework defaults — last resort, never intentional.

---

## 3. Behavioral Rules (from the old frontend-coder agent)

All behavioral rules from the previous `frontend-coder` template are preserved in the
unified template.

### Stop-and-Ask Rule for Python

If the implementation task requires creating or modifying any `.py` file, halt
immediately without writing the file. Tell the user:

> "This task requires a Python change. Python files are owned by `python-coder`.
> Please invoke `python-coder` for the Python portion and return to `frontend-coder`
> for the frontend portion."

Writing TypeScript/JavaScript that calls API endpoints (e.g. `fetch('/api/data')`)
is permitted — the rule applies only to raw `.py` file authoring.

### Stop-and-Ask Rule for SQL

If the implementation task requires creating or modifying any `.sql` file (including
Alembic migrations), halt immediately. Tell the user:

> "This task requires a SQL change. SQL files are owned by `sql-coder`.
> Please invoke `sql-coder` for the SQL portion and return to `frontend-coder`
> for the frontend portion."

### Pre-Flight Reads (required before any edit)

On every invocation, before touching any file:

1. Read the ticket file at the path provided.
2. Read any ADRs cited by the ticket (`docs/architecture/adrs/ADR-*.md`).
3. Read `PROJECT_CONTEXT.md` (at `{{frontend.project_context_path}}`) if it exists.
   Extract the `design_system` key if present. Log one debug line and continue if
   the file is absent.
4. Detect installed optional skills (webapp-testing only — see §4).

### Research Delegation

`frontend-coder` does not have `Grep`, `Glob`, or MCP search tools. Any cross-file or
symbol-level question (e.g. "every caller of component X", "current props interface
for Y") MUST be delegated to `research-agent` via the `Agent` tool. Use the
`research-agent`'s structured findings directly — do not re-derive them.

### Contract-Aware Mode

Activates automatically when the ticket body contains an `## Agent Contracts` section
with a `### frontend-coder` sub-heading. When active:

1. Verify `Depends on:` upstream deliverables are present in the working tree before
   writing any UI code. If any are absent, halt with `(status: blocker)`.
2. Implement against each `Delivers to:` item exactly (component names, props interface,
   rendered fields, user behavior).
3. Invoke the AC sign-off recipe from the `signoff` skill §2c after completing work.

### File-Size Limit

New frontend files must stay within:

- Component files (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`): ≤ 300 lines.
- Stylesheets (`.css`, `.scss`): ≤ 500 lines.

Plan component splits upfront.

### Pre-Completion Checks

Before declaring the task complete:

1. Run `git status --short` and confirm only frontend file extensions appear in the diff.
2. Run any configured frontend linter (ESLint, Stylelint) on touched files. Fix errors;
   warnings are advisory.
3. Verify optional-skill results are documented in the response payload.

### Response Payload

Every invocation must end with a structured `## Completion Report` section covering:
files changed, design principles applied (always `true`), optional-skill status
(webapp-testing installed / not installed / screenshot path), test results, and notes.
The ticket-supervisor refuses to mark the ticket done if this section is missing.

### Sibling-Agent Status

`frontend-coder` is a **first-class sibling agent** — a peer to `python-coder` and
`sql-coder`, dispatched directly by `ticket-supervisor` at priority 8. It is NOT a
sub-agent of `python-coder`. See ADR-005 for the full rationale.

### Component Structure Conventions

- One component per file. No anonymous default exports — name every component.
- Every prop must have a type annotation (TypeScript) or PropTypes declaration (JavaScript).
- Side effects (data fetching, subscriptions) belong in lifecycle hooks or custom hooks,
  not in render functions.

### Performance Conventions

- Lazy-load routes and heavy components (`React.lazy` / dynamic import).
- Avoid inline function definitions in JSX that cause unnecessary re-renders — hoist or
  memoize where the diff shows a real render cost.

---

## 4. webapp-testing Integration Status

The `webapp-testing` integration is **optional and uses the same file-existence detection
as before** (no registry lookup required).

**Detection command (unchanged):**
```bash
[ -f ".claude/skills/webapp-testing/SKILL.md" ] && echo "installed" || echo "not installed"
```

**If installed:** After making UI changes, invoke the skill by reading
`.claude/skills/webapp-testing/SKILL.md` and following its protocol to:
- Capture a screenshot of the affected page/component.
- Check for browser console errors.
- Return the screenshot path and console-log summary in the response payload.

**If not installed:** Proceed without browser verification. Note the absence in the
response payload so the reviewer can decide whether manual verification is needed.

**Antigravity exception:** If the `ANTIGRAVITY` environment variable is set, skip the
webapp-testing skill entirely. Antigravity provides its own browser verification.
The embedded design principles always apply regardless of environment.

---

## 5. frontend-design Legacy Skill Handling

The `frontend-design` skill (`templates/skills/frontend-design/SKILL.md`) is preserved
as a **legacy artefact** and remains in the package for projects that were installed
before this unification. However:

- `frontend-coder` **never reads or loads** `.claude/skills/frontend-design/SKILL.md`,
  even if the file exists on disk.
- Applying both the embedded principles and the external skill file simultaneously would
  duplicate constraints and may introduce conflicting guidance.
- The `frontend.optional_skills` config key documents that `frontend-design` is no
  longer an optional skill — design principles are embedded in the template.

Adopters who still have `.claude/skills/frontend-design/SKILL.md` from a previous
install can leave it in place; it is silently ignored.

---

## 6. Comparison Table: Old Artifact → New Location

| Old artifact | Old location | New location in unified template |
|---|---|---|
| §2 Project Context Hook (detect design system) | `frontend-design/SKILL.md §2` | `frontend-coder.md` → `## Embedded Design Principles` → `### Project Design System Override` |
| §3 Principle 1 — Custom font pairing | `frontend-design/SKILL.md §3 Principle 1` | `frontend-coder.md` → `## Embedded Design Principles` → `### Principle 1` |
| §3 Principle 2 — Primary colour | `frontend-design/SKILL.md §3 Principle 2` | `frontend-coder.md` → `## Embedded Design Principles` → `### Principle 2` |
| §3 Principle 3 — Negative space | `frontend-design/SKILL.md §3 Principle 3` | `frontend-coder.md` → `## Embedded Design Principles` → `### Principle 3` |
| §3 Principle 4 — Deliberate interactive states | `frontend-design/SKILL.md §3 Principle 4` | `frontend-coder.md` → `## Embedded Design Principles` → `### Principle 4` |
| §3 Principle 5 — Component-level personality | `frontend-design/SKILL.md §3 Principle 5` | `frontend-coder.md` → `## Embedded Design Principles` → `### Principle 5` |
| §4 Pre-Write Checklist (6 questions) | `frontend-design/SKILL.md §4` | `frontend-coder.md` → `## Embedded Design Principles` → `### Pre-Write Checklist` |
| §5 Constraints (advisory, platform-agnostic) | `frontend-design/SKILL.md §5` | `frontend-coder.md` → `## Embedded Design Principles` → `### Design Principles Constraints` |
| Stop-and-Ask Rule for Python | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Stop-and-Ask Rule for Python` (unchanged) |
| Stop-and-Ask Rule for SQL | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Stop-and-Ask Rule for SQL` (unchanged) |
| Pre-Flight Reads (4 steps) | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Pre-Flight Reads` (step 4 updated: no longer loads frontend-design) |
| Optional-Skill Integration — webapp-testing detection | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Optional-Skill Integration` → `### webapp-testing skill` (unchanged detection logic) |
| Optional-Skill Integration — frontend-design loading | `frontend-coder.md` (prior version) | Removed. Design principles are embedded. Legacy file is explicitly ignored. |
| Contract-Aware Mode (Depends on / Delivers to) | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Contract-Aware Mode` (unchanged) |
| Research Delegation via research-agent | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Research Delegation` (unchanged) |
| File-Size Limit (300 / 500 lines) | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## File-Size Limit` (unchanged) |
| Pre-Completion Checks | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Pre-Completion Checks` (unchanged) |
| Response Payload (Completion Report) | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Response Payload` (unchanged) |
| Implementation Sequence (10 steps) | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Implementation Sequence` (updated: step 3 reads embedded principles; step 4 detects webapp-testing only) |
| Component structure conventions | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Embedded Design Principles` → `### Component structure` (preserved) |
| Performance conventions | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Embedded Design Principles` → `### Performance` (preserved) |
| Antigravity exception for webapp-testing | `frontend-coder.md` (prior version) | `frontend-coder.md` → `## Optional-Skill Integration` (unchanged) |

---

## 7. What Changed (Summary)

1. **Design principles moved in-template.** All five design principles from the
   `frontend-design` skill are now embedded in `frontend-coder.md`. No skill loading
   is required or permitted.

2. **frontend-design skill is ignored.** The agent explicitly skips
   `.claude/skills/frontend-design/SKILL.md` even if it exists on disk. This prevents
   duplicate constraint application.

3. **`design_principles_applied` is always `true`.** The `## Completion Report` block
   unconditionally reports design principles as applied. There is no "not installed"
   case — principles are always embedded and always active.

4. **webapp-testing detection is unchanged.** The file-existence check, the invocation
   protocol, and the Antigravity exception are identical to the prior version.

5. **All behavioral rules are unchanged.** Stop-and-Ask rules, Pre-Flight Reads,
   Contract-Aware Mode, Research Delegation, File-Size Limit, Pre-Completion Checks,
   and the Response Payload format are all preserved verbatim from the prior template.

6. **Sibling-agent status is unchanged.** `frontend-coder` remains at priority 8 in the
   `ticket-supervisor` dispatch order, between `sql-coder` (7) and `test-runner` (9).
