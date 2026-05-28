---
name: frontend-design
allowed-tools: Read
description: |
  Optional skill for frontend-coder. Provides design principles that counteract
  generic AI aesthetics — strong typographic hierarchy, intentional negative space,
  distinctive colour choices, and component-level personality. Installed by the
  /onboard wizard when the user opts in.

  Load this skill BEFORE writing any markup, CSS, or component code. Apply its
  principles to produce UI output that is visually distinct from default
  Tailwind/MUI/Bootstrap scaffolds. Platform-agnostic: applies to React, Vue,
  Svelte, and plain HTML/CSS equally.
---

# frontend-design

This is an optional skill for `frontend-coder`. Load it **before** writing any
markup, CSS, or component code. Apply the principles below to produce UI that has
a distinctive visual personality — not the generic AI-generated aesthetic.

---

## §1 Purpose

AI-generated UI tends to converge on the same patterns: the same blue primary
colour (#3B82F6 or similar), the same card-shadow pattern, the same Tailwind
`text-gray-600` for body copy. The result is visually indistinguishable from a
thousand other scaffolds.

This skill provides principles to break that convergence. The goal is not novelty
for its own sake — it is intentionality. Every visual choice should be deliberate,
not a default.

---

## §2 Project Context Hook (load first)

Before applying the principles below, check for a project-specific design system:

```bash
# Check for frontend PROJECT_CONTEXT.md with design_system key
[ -f ".agents/agents/frontend-coder/PROJECT_CONTEXT.md" ] && grep -q "design_system" ".agents/agents/frontend-coder/PROJECT_CONTEXT.md" && echo "found" || echo "not found"
```

**If a project design system is found:**
Read the `design_system` key from `PROJECT_CONTEXT.md`. The project design system
**takes precedence** over all principles below. Apply the project's brand colours,
fonts, and component conventions first, then use the principles below to fill
gaps where the design system is silent.

**If no project design system is found:**
Apply all principles below without modification.

---

## §3 Design Principles

Apply all of the following principles when the project design system does not
override them.

### Principle 1 — Custom font pairing, not the browser default

Do NOT use `font-family: sans-serif` or `font-family: system-ui` without specifying
a preferred font. Always define a clear type hierarchy:

```css
/* Example: pick a Google Font pair with personality */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;500&display=swap');

body { font-family: 'Inter', system-ui, sans-serif; }
h1, h2, h3 { font-family: 'Playfair Display', Georgia, serif; }
```

The headline font should have a different visual weight or character from the
body font. Avoid using the same font family for both.

### Principle 2 — A primary colour with deliberate personality

Do NOT default to `#3B82F6` (Tailwind `blue-500`) unless it is the project's
documented brand colour. Choose a primary colour that conveys the product's
character:

- A financial dashboard might use deep teal (`#0D9488`) for trust and precision.
- A creative tool might use warm amber (`#D97706`) for energy.
- A data-heavy tool might use slate blue (`#475569`) for authority.

State the chosen primary colour and its rationale in a comment at the top of the
stylesheet or in the component file:

```css
/* Primary: #0D9488 (deep teal) — chosen for trust and precision in a financial context */
```

### Principle 3 — Intentional negative space

Do NOT pack every available pixel with content. White space (or dark space in
dark-theme UIs) is an active design choice — it gives the eye a place to rest
and signals hierarchy.

Rules:
- Heading-to-body margin should be at least 0.5em above and below.
- Card padding should be at least 1.5rem on all sides; do not use less than 1rem.
- Between major sections, use a `gap` or `margin` of at least 2rem.
- Do NOT use `p-2` as the default card padding in Tailwind (that's 8px — too tight).

### Principle 4 — Deliberate interactive states

Every interactive element (button, link, input, card-with-click) MUST have
explicit `:hover`, `:focus`, and `:active` styles. Do NOT rely on browser defaults.

```css
/* Bad: browser default outline only */
button:focus { outline: auto; }

/* Good: deliberate, visible, on-brand focus ring */
button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 3px;
}
```

If using Tailwind, use `focus-visible:ring-2 focus-visible:ring-teal-500` (or
your primary colour).

### Principle 5 — Component-level personality through detail

Small details make a design feel finished. Apply at least one of the following
per component:

- A subtle border-radius that is either clearly sharp (0px, 2px) or clearly rounded (12px+). Avoid the default 4px generic rounding.
- A carefully chosen icon size (20px for inline, 24px for standalone) — do not mix sizes randomly.
- A micro-animation on state change (200ms ease-out transform or opacity), not a jarring instant switch.
- A deliberate text-transform choice (uppercase tracking for labels, not for body).

Example of a "finished" button vs a generic one:

```css
/* Generic */
.btn { background: #3B82F6; color: white; padding: 8px 16px; border-radius: 4px; }

/* Finished */
.btn {
  background: var(--color-primary);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: background 180ms ease-out, transform 120ms ease-out;
}
.btn:hover { background: var(--color-primary-dark); transform: translateY(-1px); }
.btn:active { transform: translateY(0); }
```

---

## §4 Pre-Write Checklist

Before writing any markup, CSS, or component output, answer each question aloud
(in a comment or in your reasoning):

1. **Font pairing**: have I specified a custom font pair, or am I using the browser default?
2. **Primary colour**: have I chosen a primary colour with a stated rationale, or did I default to Tailwind blue?
3. **Negative space**: does the layout have deliberate breathing room, or did I pack every available pixel?
4. **Interactive states**: do all clickable/focusable elements have `:hover`, `:focus-visible`, and `:active` styles?
5. **Component detail**: does each component have at least one deliberate design detail that sets it apart from a scaffold default?
6. **Distinctiveness**: if I imagine 100 other AI-generated UIs, would this one look different? If not, what can I change?

Do not produce output until all 6 questions have an answer you are satisfied with.

---

## §5 Constraints

- This skill is **advisory** — the principles guide judgment, they are not
  algorithmic rules. Use your judgment to apply them appropriately to the
  specific component or page.
- This skill is **platform-agnostic**: the principles apply to React, Vue,
  Svelte, and plain HTML/CSS equally. Do not assume a specific framework.
- If the project design system specifies a value that conflicts with a principle
  here (e.g. the brand is deliberately the default Tailwind blue), **defer to
  the project design system**. The principles here are defaults, not overrides.
- Do NOT import CSS frameworks or fonts that the project does not already use.
  If the project uses Tailwind, express these principles through Tailwind utilities.
  If it uses plain CSS, write plain CSS. Check the project's `package.json` or
  existing stylesheets to determine what is in use before importing anything new.
- This skill has `allowed-tools: Read` only. It does not write any files.
  `frontend-coder` writes the files; this skill only provides design guidance.
