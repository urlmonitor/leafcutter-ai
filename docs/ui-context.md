---
title: UI Context — pointers to the app's real design system
components:
- frontend_coding
filled: true
stack:
  framework: next
  css: tailwind
stylesheets:
- leafcutter-web/app/globals.css
- leafcutter-web/tailwind.config.ts
component_library: leafcutter-web/components/ui/kit.tsx
fonts: leafcutter-web/app/layout.tsx
design_principles:
- templates/agents/frontend-coder.md
- templates/skills/frontend-design/SKILL.md
- docs/how-to/using-frontend-coder-with-design-integration.md
brand_links:
- leafcutter-web/README.md
data_layer:
  data_access_seam: leafcutter-web/lib/data/repo.ts
  loaders_convention: all loaders read paths through repoPath(); no loader carries
    its own mock branch
  fixtures_dir: leafcutter-web/fixtures/
  fixtures_formats:
  - YAML — AC store (docs/acceptance-criteria/**, index.yaml)
  - markdown — tickets (tickets/**)
  - JSON — docs/roadmap.json, docs/components.json, config/agent_registry.json, docs/product-truth/{flows,mock-data,mockups}/**
  mock_toggle:
    env_default: LEAFCUTTER_MOCK
    badge_flag: NEXT_PUBLIC_LEAFCUTTER_MOCK
    runtime_override: cookie or ?mock query-param
    production_lock: LEAFCUTTER_MOCK_LOCK
    resolution_order: production_lock > runtime_override > env_default
  drift_guard: CI validates each fixture against its real schema + parses it through
    its native-format loader
created: '2026-08-12'
last_updated: '2026-08-12'
type: tutorial
status: active
description: Overview of UI Context — pointers to the app's real design system.
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

## Data layer & mock mode

This section carries the **app-specific bindings** a frontend agent needs to build
or extend **mock mode** — per ADR-022, a mockup is not standalone HTML; it is the
**real Atlas running in mock mode**, rendering from a bundled fixture repo instead
of the live repo. The mock-mode *concept* is universal and lives in the agent
template; only the four bindings below are specific to the Atlas. Build against
**these** — never against hardcoded values baked into a prompt. The
`data_layer:` frontmatter block above is the machine-readable form of everything
described here.

**1 — Data-access seam.** `leafcutter-web/lib/data/repo.ts` is the single seam.
`repoRoot()` decides which repo the Atlas reads; `repoPath(...segments)` joins
against it. Mock mode is realised by making `repoRoot()` return the bundled
fixture repo root instead of the live repo root — one branch, ahead of the
existing `LEAFCUTTER_REPO_ROOT` / cwd-parent probing. Do **not** add a mock
branch anywhere else.

**2 — Loaders convention.** Every loader (`ac-store.ts`, `tickets.ts`,
`components.ts`, `roadmap.ts`, `agents.ts`, `tests.ts`, `flows.ts`,
`traceability.ts`, `activity.ts`) already resolves the paths it reads through
`repoPath()`. Because that is the one resolution point, swapping what `repoRoot()`
returns swaps **all 8 views at once** (home, `/atlas`, `/coverage`, `/flows`,
`/now`, `/pipeline`, `/roadmap`, `/architecture`) — the swap is whole-app by
construction, with **no per-page and no per-loader mock branch**. No loader is
edited to add mock mode.

**3 — Fixtures.** The bundled mock fixture repo lives at `leafcutter-web/fixtures/`.
Its subtree mirrors the paths every loader reads via `repoPath()`, each in the
real artifact's **native on-disk format** so the same loaders parse it unchanged:
**YAML** for the AC store (`docs/acceptance-criteria/**`, `index.yaml`),
**markdown** for tickets (`tickets/**`), and **JSON** for `docs/roadmap.json`,
`docs/components.json`, `config/agent_registry.json`, and
`docs/product-truth/{flows,mock-data,mockups}/**`. Fixtures are a small curated
snapshot (not a raw copy of the live repo) sufficient for every view to render
populated; the JSON entity mock-data records are shaped identically to the real
artifacts so they double as test fixtures. Fixtures are read-only.

**4 — Mock toggle.** The seam resolves whether to serve mock data in a **fixed
order — production lock > runtime override > env default**:

- **Env default** — the server env var **`LEAFCUTTER_MOCK`** sets the default
  (`=1` → mock on; unset or `0` → real).
- **Runtime override** — an in-app control (a **cookie** or a **`?mock`**
  query-param) overrides the default for the current session, so an on-page toggle
  can switch between mock and real.
- **Production lock** — **`LEAFCUTTER_MOCK_LOCK=real`** (opt-in, unset by default
  on dev/preview) forbids all runtime overrides and short-circuits to real data,
  so a real deployment can never leak fixtures from a stale mock cookie/query.
- **Badge flag** — **`NEXT_PUBLIC_LEAFCUTTER_MOCK`** is a client-readable flag that
  drives the visible "mock mode" badge in the app chrome. It is **presentation
  only** — it reflects the resolved decision and is **never** the authority for
  whether mock data is served.

**Drift guard.** A CI check validates every fixture against the same schema that
governs the real data and parses each through the same native-format loader, so
mock output can never silently drift from the real shape.

## Update protocol

When the Atlas design changes (a token renamed, a font swapped, a new primitive
added), update the **pointers** here — do not paste the new values in. If a
pointer target moves, fix the path. Re-run `/onboard` (the UI Context step) to
re-scaffold this file against the current tree if the app is restructured.
