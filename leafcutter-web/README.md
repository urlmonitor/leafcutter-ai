# Leafcutter Atlas

A living map of the Leafcutter project — acceptance criteria, roadmap, build
pipeline, product-truth flows, and architecture — **read live from the repo on
every request**. The Atlas is the read surface over both the AC store
(`docs/acceptance-criteria/`) and the product-truth store (`docs/product-truth/`).
See [ADR-020](../docs/architecture/adrs/ADR-020-product-truth-flow-first-upstream-layer.md)
and the [UX Prototyping component](../docs/architecture/components/ux-prototyping.md).

It is a [Next.js](https://nextjs.org) (App Router) app. Nothing is precomputed or
cached to disk: each page reads the repo's YAML/JSON/Markdown at request time, so
the site always reflects the current working tree.

## Run it

```bash
npm install
npm run dev -- -p 4319
```

Then open [http://localhost:4319](http://localhost:4319).

The dev server defaults to port 3000; the Atlas is conventionally run on
**4319** (`-p 4319`, or `PORT=4319 npm run dev`). Production build:

```bash
npm run build
npm run start -- -p 4319
```

> **WSL note:** if `npm install` stalls, use
> `npm install --prefer-offline --ignore-scripts`.

## Which repo it reads

`lib/data/repo.ts` resolves the repo root it renders, in priority order:

1. `LEAFCUTTER_REPO_ROOT` env var (absolute path) — the seam that lets the Atlas
   host **any** project's data later.
2. The parent of the app directory (`process.cwd()/..`) — the default, since the
   site lives as `leafcutter-web/` inside the repo/worktree it documents.
3. The current working directory (when run from a repo root directly).

Each candidate is verified by probing for `docs/roadmap.json`.

## The views

| Route | Nav label | What it shows |
|---|---|---|
| `/` | Pulse | Project health at a glance — AC/ticket/component/agent counts, work-status donut, the L0–L3 pyramid, delivery throughput, phase progress, and what's approved & ready to build. |
| `/now` | Now & Next | What is in flight plus what builds next. |
| `/atlas` | AC Atlas | How acceptance criteria connect — the AC graph and drill-downs. |
| `/flows` | Flows | Product truth, coloured by live build status — the product-truth Flows, with each step's derived `impl_status` resolved from its ACs' `work_status`. |
| `/roadmap` | Roadmap | Phases, exit criteria, and what's next. |
| `/coverage` | Coverage | How many tests guard each AC. |
| `/pipeline` | Pipeline | How Leafcutter builds software — the phase-agent pipeline. |
| `/architecture` | Architecture | The component map read from `docs/components.json`. |

There is also an internal `/api/diag` route for data-resolution diagnostics.

## How it reads the repo

- `lib/data/repo.ts` — repo-root resolution and safe file/dir helpers.
- `lib/data/*.ts` — one loader per surface: `ac-store`, `tickets`, `flows`
  (product-truth Flows + Mock Data), `components`, `roadmap`, `agents`, `tests`,
  `traceability`, and the `atlas` aggregator.
- The Flows loader resolves each step's `implements` AC ids to their **live**
  `work_status` and rolls them up into the displayed `impl_status`; the stored
  `impl_status` in the flow JSON is used only as a fallback for AC ids that do
  not resolve. Flows are read-only views — edit the `.flow.json` in the store,
  never the rendering.

## Stack

Next.js 14 (App Router, server components), React 18, Tailwind CSS, Recharts and
React Flow for visualizations, Framer Motion for reveal animations, and
`gray-matter` / `yaml` for reading the repo's frontmatter and YAML.
