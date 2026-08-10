---
# docs/ui-context.md — the host app's UI source-of-truth POINTER file.
#
# This file holds NO token VALUES (no hex, no HSL channels, no font names, no
# radius numbers). It holds POINTERS to the app's live sources so it can never go
# stale: mockup-author, frontend-coder, and user-surface-smoker FOLLOW these
# pointers to the real files and read the CURRENT values at run time.
#
# Host app: the Leafcutter Atlas (leafcutter-web/) — a Next.js (App Router) +
# Tailwind app. This repo IS the host app (dogfooding).
filled: true
stack:
  framework: next        # next | react | vue | svelte | flask | plain
  css: tailwind          # tailwind | scss | css-modules | plain-css
# The AUTHORITATIVE css/theme/token files, in priority order. Open each and read
# the REAL current values (custom properties, theme mappings). Never snapshot.
stylesheets:
  - leafcutter-web/app/globals.css        # token SSOT — :root CSS custom properties + base layer
  - leafcutter-web/tailwind.config.ts     # maps the custom properties onto Tailwind theme keys + radius scale
# The dir whose class/prop idiom your markup should echo. kit.tsx is the shared
# presentational primitive set (Panel / SectionHeader / Badge …).
component_library: leafcutter-web/components/ui/kit.tsx
# Where the app declares/loads its fonts (follow the pointer to read the actual
# families and the CSS-variable names they are exposed under).
fonts: leafcutter-web/app/layout.tsx
# Brand / style-guide / design-principle docs. Defaults to the shipped Claude
# frontend-design convention (now embedded in the frontend-coder agent template).
# Read for rules the raw tokens do not encode (density, states, brand voice).
design_principles:
  - templates/agents/frontend-coder.md                                  # the shipped frontend-design convention (embedded "Design Principles")
  - templates/skills/frontend-design/SKILL.md                           # the same convention as a standalone reference doc
  - docs/how-to/using-frontend-coder-with-design-integration.md         # how the convention is applied + overridden in this project
# Optional external references (advisory only — never a token source).
brand_links:
  - leafcutter-web/README.md   # the Atlas' own identity/overview + which repo it reads
---

# UI Context — Leafcutter Atlas

This is the single human-curated entry point to the Atlas' real design system.
Everything below describes **where** the design lives and the **shape** of what
you will find there — it deliberately copies **no** literal values. Open the
pointer targets in the frontmatter and read the current values live; that is what
keeps a mockup, a built screen, and a smoke assertion all consistent with the app
as it actually looks today.

## Where the tokens live

`leafcutter-web/app/globals.css` is the token source-of-truth. The design tokens
are declared as **CSS custom properties on a single `:root` block** inside an
`@layer base`. They are authored as **HSL channel triples with no `hsl()` wrapper**
(so Tailwind opacity modifiers like `bg-primary/40` work) — read the file for the
exact channels; never transcribe them into a mockup as constants.

Shape of the palette you will find there:

- A dark, botanical **canopy-green** canvas (`--background`) with a crisp
  near-white text colour (`--foreground`), and a raised **card** surface a step
  above the canvas.
- A single signature **green primary** (`--primary`, a chlorophyll/leaf green)
  plus a **teal accent** (`--accent`); a muted/secondary fill for hover states.
- Semantic signal tokens: `--destructive`, `--warning` (amber, in-flight work),
  `--success`, `--info`.
- A 7-stop categorical **data-viz ramp** (`--chart-1` … `--chart-7`).
- Line/focus tokens: `--border`, `--input`, `--ring`.
- A single corner-radius token, **`--radius`** (a `rem` value); the `sm`/`md`/`lg`
  radii are derived from it in Tailwind.

The `body` base rule in the same file also carries the base **font-family stack**,
a subtle radial "canopy vignette" `background-image`, custom scrollbars, and a
`::selection` tint keyed off `--primary`. The `@layer components` block defines the
app's signature surface classes — **`.panel`**, `.panel-hover`, `.eyebrow`,
`.veins` — which are the real idiom for a raised surface; prefer echoing them over
inventing generic card styling.

## How the tokens reach Tailwind

`leafcutter-web/tailwind.config.ts` maps every custom property onto a Tailwind
theme colour key (e.g. `primary` → `hsl(var(--primary))`) under
`theme.extend.colors`, wires the `--radius` token into the `borderRadius` scale,
and registers the `sans` / `mono` font families against the font CSS variables.
`darkMode: "class"` — the app runs dark by default (the `<html>` element carries
the `dark` class; see the layout). Read this file to know which utility class
resolves to which token before hand-writing any colour.

## Fonts

`leafcutter-web/app/layout.tsx` loads the app's two font families via
`next/font/google` and exposes them as the CSS variables **`--font-geist-sans`**
and **`--font-geist-mono`** (the variable names are historical; follow the pointer
to read the actual families currently loaded — do not assume from the variable
name). Those variables are what `globals.css` `body` and the Tailwind `fontFamily`
config consume. The sans family is the humanist UI face; the mono family is used
for code/IDs. The `<html>` element is where the `dark` class and the font-variable
classes are applied.

## Component idiom

`leafcutter-web/components/ui/kit.tsx` holds the shared, server-safe presentational
primitives — `Panel`, `SectionHeader` (eyebrow + title + optional action), `Badge`
(tone-driven), and friends. The broader `leafcutter-web/components/` tree is
organised per Atlas view (`atlas/`, `coverage/`, `flows/`, `pipeline/`, `now/`,
`roadmap/`, `architecture/`, `shell/`). Markup you draft should read like these:
Tailwind utility classes plus the bespoke `.panel` / `.eyebrow` classes, tones
resolved through the shared `Badge`, not ad-hoc inline styles.

## Design principles

The shipped Claude **frontend-design convention** is the default rule-set for
anything the raw tokens do not encode (type hierarchy, negative space, interactive
states, component-level detail, accessibility contrast). It now lives **embedded**
in `templates/agents/frontend-coder.md`; `templates/skills/frontend-design/SKILL.md`
documents the same convention as a standalone reference, and
`docs/how-to/using-frontend-coder-with-design-integration.md` explains how it is
applied and overridden in this project. Apply these on top of the real tokens —
never in place of them.

## Update protocol

When the Atlas design changes (a token renamed, a font swapped, a new primitive
added), update the **pointers** here — do not paste the new values in. If a
pointer target moves, fix the path. Re-run `/onboard` (the UI Context step) to
re-scaffold this file against the current tree if the app is restructured.
