---
# docs/ui-context.md — the host app's UI source-of-truth POINTER file. (SCAFFOLD)
#
# This is the UNFILLED scaffold that /onboard writes into a fresh host app. A human
# fills the pointers below, then flips `filled:` to true. Until then, mockup-author
# renders a labelled UNSTYLED placeholder (and frontend-coder falls back to the
# shipped design principles), so nothing invents a look.
#
# GOLDEN RULE: this file holds POINTERS, never token VALUES. Do NOT paste hex,
# HSL channels, font family names, or radius numbers here. Point at the app's live
# files; the agents open them and read the CURRENT values at run time so this file
# can never go stale.
filled: false          # TODO: set to true once every pointer below resolves.
stack:
  framework: TODO      # TODO: next | react | vue | svelte | flask | plain
  css: TODO            # TODO: tailwind | scss | css-modules | plain-css
# TODO: list the AUTHORITATIVE css/theme/token files, most-authoritative first.
# Discovery hits (global stylesheets, token files, tailwind/uno configs, SCSS
# variable partials) are pre-filled here by /onboard as candidate pointers —
# confirm, correct, or delete each. Examples of what to point at:
#   - app/globals.css / src/styles/theme.css   (CSS custom-property SSOT)
#   - tailwind.config.ts / uno.config.ts       (theme mapping + radius scale)
#   - design/tokens.json / *.tokens.json       (design-token export)
#   - src/styles/_variables.scss               (SCSS variables)
stylesheets:
  - TODO   # e.g. path/to/globals.css
# TODO: the dir (or index file) whose class/prop idiom your markup should echo —
# your components/ or ui/ directory, or a shared kit file within it.
component_library: TODO   # e.g. components/ui/ or components/ui/kit.tsx
# TODO: where the app declares/loads its fonts. Point at the file; the agent reads
# the real families + the CSS-variable names live. Do NOT copy the font names here.
#   - Next.js:  app/layout.tsx (next/font)   - plain CSS: the @font-face / @import block
fonts: TODO
# TODO: brand / style-guide / design-principle docs. LEAVE the first entry as the
# shipped Claude frontend-design convention (it is the default for everything the
# raw tokens do not encode); ADD any real design/brand doc your project has.
design_principles:
  - templates/agents/frontend-coder.md   # shipped frontend-design convention (embedded). Keep as the default.
  # - TODO: add your own design/brand/style-guide doc path(s) here, if any.
# TODO (optional): external references — Figma, a brand site. Advisory only; never
# a token source. Delete this key if you have none.
brand_links:
  - TODO
---

# UI Context — <YOUR APP NAME> (SCAFFOLD — not yet filled)

> This file was scaffolded by `/onboard`. Until a human fills the pointers in the
> frontmatter above and sets `filled: true`, the mockup/build/smoke agents will NOT
> style from your app — mockup-author renders a clearly-labelled **unstyled
> placeholder** and frontend-coder falls back to the shipped design principles.

## How to fill this file (discovery)

1. **Find your global stylesheet / token SSOT.** This is where your CSS custom
   properties (`--primary`, `--background`, `--radius`, …) or design tokens live —
   commonly `globals.css`, `app.css`, `theme.css`, a `styles/` dir, a `tokens.json`
   / `*.tokens.*` export, or a `_variables.scss` partial. List it (them) under
   `stylesheets:`, most-authoritative first.
2. **Find your theme/build config**, if any — `tailwind.config.*`, `uno.config.*`,
   a PostCSS/theme file that maps tokens onto utility classes. Add it to
   `stylesheets:` after the token SSOT.
3. **Point `component_library`** at the directory (or shared kit file) whose
   class/prop idiom new markup should echo — your `components/` or `ui/` folder.
4. **Point `fonts`** at the file that declares/loads your fonts (a `next/font`
   call in `layout.tsx`, an `@font-face` / `@import` block in a stylesheet, etc.).
5. **Confirm `design_principles`** — keep the shipped frontend-design convention as
   the default and add any brand / style-guide doc your project maintains.
6. **Set `filled: true`.**

## What to write in this body

Once filled, replace this section with prose that describes **where** your tokens
live and their **shape** — for example: "primary is a dark green HSL on `:root` in
`app/globals.css`", "radius is the `--radius` rem token wired into Tailwind's
`borderRadius`", "fonts are loaded in `app/layout.tsx` and exposed as CSS
variables". **Never copy the literal values** (no hex, no HSL channels, no font
names, no radius numbers) — the agents open the pointer targets and read them live.
See the filled example that ships with the leafcutter-web Atlas at
`docs/ui-context.md` in the leafcutter-ai repository for the target shape.

## Update protocol

When your design changes, update the **pointers** here — never paste new values in.
If a pointer target moves, fix the path. Re-run `/onboard` (the UI Context step) to
re-scaffold against the current tree if the app is restructured.
