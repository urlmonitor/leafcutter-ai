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
# ── Data layer & mock mode (ADR-022) ─────────────────────────────────────────
# APP-SPECIFIC bindings a frontend agent needs to build/extend "mock mode" — the
# real app running against bundled fixtures instead of live data. The mock-mode
# CONCEPT is universal (env default -> runtime override -> optional prod lock; ONE
# data-access seam swaps real->fixtures; a visible badge; a CI drift guard) and
# lives in the frontend-coder agent template. Only the bindings below are per-app.
# Unlike the design pointers above, these are FACTS/bindings (a seam file+function,
# a fixtures dir, exact env/flag names) — they ARE the contract the agent codes
# against, so NAME them here; do not point at token files for these.
#
# GRACEFUL ABSENCE: if these fields are left empty/TODO, an agent asked to build
# mock mode MUST say the bindings are missing and ask for them — it must NEVER
# guess a seam, invent a fixtures dir, or make up toggle names.
data_layer:
  # TODO: the SINGLE file+function where real-vs-mock data resolution happens.
  # One seam should swap the whole app; avoid per-page/per-loader mock branches.
  #   - Next.js/TS: e.g. lib/data/repo.ts -> repoRoot()/repoPath()
  #   - Flask:      e.g. app/data/source.py -> get_data_root()
  data_access_seam: TODO
  # TODO: how loaders resolve paths — state the convention that lets ONE seam swap
  # everything (e.g. "all loaders read through repoPath()"). If loaders each build
  # their own paths, say so: mock mode will need the seam pushed down first.
  loaders_convention: TODO
  # TODO: where the bundled mock fixture repo/dir lives, and the NATIVE on-disk
  # formats it must mirror so the SAME loaders parse it unchanged (do not invent a
  # bespoke mock format — mirror what the real loaders already read).
  fixtures_dir: TODO   # e.g. fixtures/ or tests/fixtures/mock-repo/
  fixtures_formats:
    - TODO   # e.g. "YAML — <which inputs>", "JSON — <which inputs>", "markdown — <which inputs>"
  # TODO: the mock toggle. Resolution order is FIXED and universal:
  #   production_lock > runtime_override > env_default.
  # Fill your app's concrete names/mechanisms for each rung (leave a rung blank
  # only if your app genuinely omits it — e.g. no production lock).
  mock_toggle:
    env_default: TODO       # server env var that sets the DEFAULT (e.g. APP_MOCK; =1 on, unset/0 off)
    badge_flag: TODO        # client-readable flag driving the visible badge ONLY (e.g. NEXT_PUBLIC_APP_MOCK). Never the authority.
    runtime_override: TODO  # per-session override mechanism (e.g. "cookie or ?mock query-param")
    production_lock: TODO    # opt-in lock that forbids overrides (e.g. APP_MOCK_LOCK=real)
    resolution_order: "production_lock > runtime_override > env_default"   # keep as-is; universal
  # TODO: the CI drift guard — how fixtures are kept shape-identical to real data
  # (validate against the real schemas + parse through the same native-format
  # loaders). Describe your app's check, or leave TODO if not yet built.
  drift_guard: TODO
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

## Data layer & mock mode (fill if you will build mock mode)

This section carries the **app-specific bindings** a frontend agent needs to build
or extend **mock mode** — per ADR-022, a mockup is the **real app running in mock
mode** (rendering from bundled fixtures instead of live data), not standalone HTML.
The mock-mode *concept* is universal and lives in the `frontend-coder` agent
template; only the bindings in the `data_layer:` frontmatter block above are
specific to your app. Fill them so the same agent that builds mock mode for the
leafcutter Atlas today builds it correctly for your app tomorrow — the agent must
NOT be hand-fed these details in its prompt.

Fill each `data_layer:` field with your app's real binding:

1. **`data_access_seam`** — the single file+function where real-vs-mock resolution
   happens. Aim for one seam that swaps the whole app; do not scatter mock branches
   across pages or loaders.
2. **`loaders_convention`** — how loaders resolve paths, so one seam swaps
   everything (e.g. "all loaders read through `repoPath()`"). If they don't, that is
   the first thing to fix before mock mode.
3. **`fixtures_dir` + `fixtures_formats`** — where the bundled fixture repo lives
   and the **native on-disk formats** it mirrors, so the same loaders parse it
   unchanged (mirror the real formats; do not invent a bespoke mock format).
4. **`mock_toggle`** — your concrete env default, badge flag, runtime override, and
   optional production lock. The **resolution order is fixed and universal**:
   `production_lock > runtime_override > env_default`. The badge flag is
   presentation-only — it reflects the resolved decision, it never decides it.

Then describe the same bindings in prose here, mirroring the filled example that
ships with the leafcutter-web Atlas at `docs/ui-context.md` in the leafcutter-ai
repository (its "Data layer & mock mode" section).

> **Graceful absence.** If the `data_layer:` fields are left empty/TODO, an agent
> asked to build mock mode will **stop and ask** for these bindings — it will not
> guess a seam, invent a fixtures dir, or make up toggle names. Leave them TODO
> until you are ready to build mock mode; fill them before you ask an agent to.

## Update protocol

When your design changes, update the **pointers** here — never paste new values in.
If a pointer target moves, fix the path. Re-run `/onboard` (the UI Context step) to
re-scaffold against the current tree if the app is restructured.
