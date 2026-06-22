---
description: Accumulated conventions for the build-pipeline AC namespace — naming, ID numbering, and scope boundaries for BP-series authoring agents.
---

# build-pipeline — Project Context for Authoring Agents

Accumulated conventions for the `build-pipeline` AC namespace. Read this before
authoring or decomposing ACs in this component.

## Folder vs. component-field naming (IMPORTANT)

- On-disk folder is `docs/acceptance-criteria/build_pipeline/` (UNDERSCORE).
- The canonical component **id** in `index.yaml` is `build-pipeline` (HYPHEN),
  prefix `BP`.
- The `component:` field value is INCONSISTENT across existing records:
  - BP-100 family and BP-800 family use `component: build-pipeline` (hyphen).
  - BP-900 family uses `component: build_pipeline` (underscore).
- Convention going forward: use the canonical hyphenated `build-pipeline` for
  the `component:` field (matches `index.yaml`), but write files into the
  underscore `build_pipeline/` folder. New BP-1000 family follows this.

## ID numbering

- L0s occupy hundreds: 100, 200, 300, 400, 500, 600, 700, 800, 810, 900, 1000.
- Next free L0 hundred after BP-900/901 was BP-1000 (assigned to the
  source↔template parity goal). Pick the next free hundred for any new L0.
- Deprecated/superseded IDs are reserved permanently — never reuse a numeric slot.

## Drift-detection scope distinction (avoid duplication)

Two SEPARATE drift concepts live here — do not conflate or duplicate:

- **BP-100k** — drift detection for COMPILED workflow OUTPUTS
  (`.claude/workflows/`) via hash manifests, at PRE-COMMIT time. Guards
  generated files against manual edits.
- **BP-1000 (a–d)** — SOURCE-to-shipped parity: every `scripts/` source script
  with a deployed `templates/scripts/` counterpart must be byte-identical, at
  the EPIC-MERGE GATE, via diff. Guards consumers against silently downgraded
  shipped copies. (Origin: EPIC-CodeQualityHooks retrospective KI-2 — the jscpd
  hook's templates/ copy drifted from its scripts/ canonical copy, lost the
  GE-100c measured%/threshold% logic, shipped broken, caught only post-merge.)

When authoring near either of these, cite the other to keep the boundary clean.

## BP-1000 family (source↔template parity) — for BA v3 decomposition

- BP-1000  (L0) — get exactly the tested behavior; no silent downgrade.
- BP-1000a (L1) — shipped scripts byte-identical to tested source. **This L1
  owns the core "scripts/ ↔ templates/scripts/ diff blocks merge on any drift"
  behavior** — decompose the diff/parity mechanism here.
- BP-1000b (L1) — parity runs as a merge gate (timing/enforcement point).
- BP-1000c (L1) — failure names the file and shows the difference (visibility).
- BP-1000d (L1) — only scripts with a deployed counterpart are checked (scope
  clarity, no false alarms on source-only tooling).
