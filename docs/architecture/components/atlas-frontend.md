---
title: "Atlas — The Leafcutter Frontend"
description: "The Leafcutter frontend, called the Atlas: a Next.js web app in leafcutter-web/ that reads the repo live on every request and renders ACs, product-truth flows, roadmap, pipeline and architecture; run locally on http://localhost:4319."
flight_level: L2-Container
status: active
type: reference
created: 2026-10-02
last_updated: 2026-10-02
components:
  - atlas_frontend
  - ux_prototyping
  - ac_store
related_docs:
  - leafcutter-web/README.md
  - docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md
  - docs/architecture/adrs/ADR-025-first-class-flow-decisions.md
  - docs/architecture/adrs/ADR-066-kernel-resolves-named-terms-and-finds-its-own-root.md
  - docs/architecture/components/ux-prototyping.md
---

# Atlas — The Leafcutter Frontend

## Overview

**Atlas** (the Leafcutter Atlas) is the project's frontend: a Next.js 14 (App Router)
web app in `leafcutter-web/`. It is a living map of the project, read live from the repo
on every request; nothing is precomputed or cached to disk. It is the read surface over
the AC store (`docs/acceptance-criteria/`) and the product-truth store
(`docs/product-truth/`). When someone says "a page in Atlas", they mean a new route in
this app.

## Run it

`npm run dev -- -p 4319` inside `leafcutter-web/`, then open http://localhost:4319.
Port 4319 is the convention. Full instructions: `leafcutter-web/README.md`.

## Views

| Route | Nav label | What it shows |
|---|---|---|
| `/` | Pulse | Project health at a glance |
| `/now` | Now & Next | What is in flight plus what builds next |
| `/atlas` | AC Atlas | The acceptance-criteria graph and drill-downs (not the whole app) |
| `/flows` | Flows | Product-truth flows, coloured by live build status |
| `/roadmap` | Roadmap | Phases, exit criteria, and what's next |
| `/coverage` | Coverage | How many tests guard each AC |
| `/pipeline` | Pipeline | The phase-agent build pipeline |
| `/architecture` | Architecture | The component map from `docs/components.json` |

## Entry Points

- `leafcutter-web/app/` — one folder per route (page components)
- `leafcutter-web/lib/data/repo.ts` — resolves which repo it renders (`LEAFCUTTER_REPO_ROOT`,
  else the parent of `leafcutter-web/`, verified by probing for `docs/roadmap.json`)
- `leafcutter-web/lib/data/*.ts` — one loader per surface (`ac-store`, `flows`, `tickets`,
  `components`, `roadmap`, `agents`, `tests`, `traceability`, `atlas`)
- `leafcutter-web/lib/data/mock.ts` — mock mode: renders bundled fixtures instead of the live repo
