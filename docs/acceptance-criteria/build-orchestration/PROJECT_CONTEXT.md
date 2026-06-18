# build-orchestration — PROJECT_CONTEXT

Specification-relevant conventions for agents authoring/decomposing ACs in this
component. (Captured by product-owner during BO-1500 authoring, 2026-06-18.)

## Component registration quirk

- The entire `BO-####` series uses `component: build-orchestration`, but
  `docs/acceptance-criteria/index.yaml` does NOT contain a `build-orchestration`
  entry. The closest registered entry is `build-pipeline` (prefix `BP`).
- This is an established, intentional convention — match the existing BO files
  (e.g. BO-1400). Do NOT switch new BO ACs to `build-pipeline`/`BP`. Component
  registration in `index.yaml` is the IT PO's call during technical enrichment.

## Folder + ID convention (mirror BO-1400)

- One feature lives in `BO-####-<slug>/` containing the L0 (`BO-####.yaml`) and
  its L1 children (`BO-####a.yaml`, ...). L2/L3 leaves are added by the BA.
- L0 = `level: L0`, single-sentence benefit title + tagline + value narrative.
- L1 = `level: L1`, one benefit tagline + 1-2 sentence expansion. `depends_on`
  includes the parent L0; parent's `covered_by` lists the L1 (same write batch).
- `status: active`, `req_status: draft`, `work_status: todo`, `roadmap_phase: phase_1`.
- New BO-series numbers advance by hundreds; BO-1400 was the prior max, BO-1500 next.

## BO-1500 decomposition note for the BA

- BO-1500a is intended to split into TWO L2 leaves, one per guardrail:
  (1) self-hosting verification must be EVIDENCE-BASED — the implementing agent
  must actually RUN the changed guard/linter/hook over the repo and record the
  real command + output as proof, never just assert "verified" in a sign-off;
  (2) build output must NOT clobber a worktree — coding agents must never run
  build.py / build-self.sh inside a feature/epic worktree (it deploys over the
  working tree and corrupts the drive); edits go to `templates/` source, and any
  deploy test targets a throwaway `--target-dir`, never the worktree root.
- Both originate from the EPIC-Exceptionhandlingguardenforcestheerror retrospective
  (GE-108 / GE-108a). Keep L2 Gherkin focused on observable evidence/safety, not
  on prescribing exact tooling internals.
