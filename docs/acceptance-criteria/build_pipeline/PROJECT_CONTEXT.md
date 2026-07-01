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

- L0s occupy hundreds: 100, 200, 300, 400, 500, 600, 700, 800, 810, 900, 1000,
  1100, 1200.
- Next free L0 hundred after BP-1100 was BP-1200 (assigned to the CI test-gate
  goal). Pick the next free hundred for any new L0.
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

## CI-quality concepts in this namespace — keep them DISTINCT (boundary map)

Four separate quality-gate concepts now live in BP. Do NOT conflate or
duplicate behavior across them when authoring or decomposing:

- **BP-100k** — drift detection for COMPILED workflow OUTPUTS (pre-commit).
- **BP-1000** — SOURCE↔shipped-template parity (epic-merge gate, byte diff).
- **BP-1100** — PHANTOM-DONE prevention: per-ticket, during a drive, proves a
  behavioral feature actually executes (files_touched + outside-in exercise)
  before a ticket may reach `status: done`.
- **BP-1200** — standing CI TEST GATE: on every pull request, the full test
  suite runs and must pass before merge. Distinct from BP-1100 (which is
  per-ticket runtime proof inside a drive) — BP-1200 is a persistent,
  repository-level PR check anchored in branch protection.

BP-1100 = "did THIS ticket's feature run?" (drive-time, per-change).
BP-1200 = "does the WHOLE suite stay green on EVERY PR?" (standing CI gate).

## BP-1100 family (phantom-done prevention) — internal scope boundary (for BA v3)

Phantom-done (a ticket passes every gate while the feature is absent) is OWNED
by BP-1100 — do NOT create a new L0 for any "files_touched accuracy" / "work
reported as done is genuinely done" request; attach it here as a BP-1100 sibling.
The two files_touched-accuracy angles are split across DISTINCT L1s — keep them
distinct when decomposing:

- **BP-1100a** — PRE-DISPATCH scope completeness: a behavioral ticket whose
  declared `files_touched` omits the executable surface (lists only docs) is
  flagged BEFORE any coder runs (refinement lens BP-1100a-1 + supervisor
  read-step BP-1100a-2). "Did the ticket declare the right scope up front?"
- **BP-1100e** — POST-CHANGE reconciliation (added 2026-07-01, PO run KI-2):
  before a ticket reaches `status: done`, the files ACTUALLY changed are
  compared against the declared `files_touched`, and a mismatch is flagged so
  it cannot mask missing work (e.g. coder edited docs when source was needed).
  "Did what actually got changed match what was declared?" BP-1100e is the
  opposite-end bookend to BP-1100a — decompose the declared-vs-actual diff
  comparison + the pre-`done` gate point here; do NOT re-derive BP-1100a's
  pre-dispatch behavior.

Cross-cutting benefit invariant for BP-1100e (and all portable guardrails):
state the benefit in PORTABLE terms — any project that installs leafcutter and
runs build.py must get the check; it must NOT rely on the leafcutter repo's own
root CLAUDE.md (not deployed to consumers per ADR-001).

## BP-1200 family (CI test gate) — for BA v3 decomposition

- BP-1200  (L0) — every PR gets trustworthy proof it didn't break the suite.
- BP-1200a (L1) — the full suite passes deterministically on a FRESH clone with
  no local build artifacts. **This is the prerequisite L1.** HOW the fresh-clone
  gap is closed (build step + shim_map extension, repointing tests, or tracking
  outputs) is deferred to an ADR — do NOT bake a mechanism into the AC text;
  decompose the OUTCOME (suite green + deterministic on clean checkout) here.
- BP-1200b (L1) — a blocking required check fails any PR whose tests fail
  (enforcement point + fast author signal).
- BP-1200c (L1) — the gate is enforced via branch protection on main and cannot
  be bypassed (unbypassable enforcement).
- Fresh-clone background (why the gate didn't already exist): ~36 tests fail at
  IMPORT on a clean checkout because they depend on gitignored build outputs
  (scripts/commit_guardian/, scripts/doc_compliance/, scripts/feedback/) absent
  after a plain clone; developer checkouts only pass on stale local artifacts.
