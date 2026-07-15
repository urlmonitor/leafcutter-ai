---
description: Accumulated conventions for the build-orchestration AC namespace — L0 numbering, scope boundaries vs. neighbouring components, and concurrency/parity/registry distinctions for BO-series authoring agents.
---

# build-orchestration — Project Context for Authoring Agents

Accumulated conventions for the `build-orchestration` AC namespace (prefix `BO`).
Read this before authoring or decomposing ACs in this component.

## ID numbering

- L0s occupy hundreds: 100, 200, 201, 202, 300, 400, 500, 700, 800, 900, 1100,
  1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200.
- Next free L0 hundred after BO-2200 is **BO-2300**. Pick the next free hundred
  for any new L0. (BO-1700 = worktree-quality-gate-guard, added 2026-07-01;
  BO-1800 = isolated-parallel-delivery, added 2026-07-06 from ADR-018;
  BO-1900 = dispatch-preflight; BO-2000 = correct-prompts-by-construction;
  BO-2100 = live-app-proof; BO-2200 = documentation-coverage-guarantee, added
  2026-07-15.)
- The earlier "next free is BO-1900" note was stale — always confirm the highest
  existing L0 folder on disk before assigning, not just this file.
- Deprecated/superseded IDs are reserved permanently — never reuse a numeric slot.

## Documentation-coverage guarantee — BO-2200 family (placement rationale + boundary)

BO-2200 ("Documentation stays correct and complete, automatically", added
2026-07-15) is the documentation-specific hardening of the computed quality
gates. It lives in build-orchestration — NOT build-pipeline (build.py/parity)
and NOT guardrail-engine — because it is a drive-time gate concern, per the
component-choice rule in the BO-1700 section below ("does the gate FIRE during a
drive" belongs here). Four L1s, each a distinct benefit; keep them distinct when
decomposing at L2:

- **BO-2200a** — broadened, accurate REQUIREMENT: docs are demanded for
  user-facing / flow / data / security / auth / privacy changes, and NOT for
  purely internal refactors. This is the change-classification → required-doc
  mapping. Cite BO-500/BO-610 (computed gates derive WHICH gates apply); BO-2200a
  hardens the documentation trigger specifically — do NOT re-derive BO-500's
  general gate-selection engine here.
- **BO-2200b** — ENFORCEMENT: a change that requires docs cannot reach `done`
  unless docs were genuinely produced (no phantom docs; a doc step can't "pass"
  writing nothing). This is the doc analogue of BP-1100 phantom-done, applied to
  documentation — cite the parallel but do not fold into BP-1100.
- **BO-2200c** — precise BRIEF to the writer: kind (how-to/reference/diagram/
  explanation), location, required contents, and which existing docs to
  update/cross-link. This is the documentation-expert dispatch contract.
- **BO-2200d** — TIMING: docs are authored AFTER the change is built so they
  match reality (drive phase ordering).

Boundary vs BO-500: BO-500 = "the right gates happen automatically from the kind
of change" (general engine); BO-2200 = "the documentation gate is broad enough,
enforced, and precise enough to be trusted" (one gate, hardened). They are
complementary, not duplicative.

## Concurrency / atomicity scope boundaries (avoid duplication)

Four SEPARATE concurrency-adjacent concepts live across build-orchestration —
do not conflate or duplicate when authoring near any of them:

- **BO-100c** — file-conflict ISOLATION: separates tickets whose `files_touched`
  sets overlap into sequential rounds BEFORE dispatch (scheduling concern).
- **BO-200** — atomic delivery of a SINGLE ticket's commit (all-or-nothing,
  clean rollback of one supervisor's commit; does not address shared-store races).
- **BO-1600** — git-OBJECT-STORE / index protection when MULTIPLE supervisors
  commit CONCURRENTLY into ONE shared worktree (origin: EPIC-FinalizeFeatureHardening
  retro KI-1 — parallel ticket-supervisors produced a 0-byte loose object that
  corrupted the worktree index). PREVENTION ONLY by design — no recovery L1.
- **BO-1800** — isolation TOPOLOGY from ADR-018: give every drive its own
  independent copy (no shared store at all) + make main changeable only through
  the gated review/merge workflow (server-side guarantee) + cap agents-per-feature
  not features-in-flight + background housekeeping can't corrupt an active drive +
  no direct-to-shared-main commits. Five L1s BO-1800a..e. origin BrainCandy.

BO-100c = "don't let same-file tickets run together" (pre-dispatch scheduling).
BO-200  = "make one ticket's commit atomic" (single-supervisor).
BO-1600 = "don't let concurrent commits corrupt the shared git store" (multi-supervisor, storage layer).
BO-1800 = "remove the sharing entirely + gate main" (topology; supersedes the
          shared-workspace ASSUMPTION behind BO-1600).

### BO-1600 vs BO-1800 relationship (read before touching either)

BO-1800 is the ADR-018 topology change. It is INTENDED to supersede the
shared-worktree model that BO-1600 protects: BO-1600 hardens ONE shared store
against concurrent committers; BO-1800 eliminates the shared store (per-drive
isolated copies) so that whole corruption class is structurally impossible.
Per ADR-018 §"Impact on in-flight ACs", BO-1600a/b/c (prevention) are largely
obsoleted by the topology and BO-1600d (guided recovery) survives as a
de-prioritised safety net. The formal supersession bookkeeping (status flips,
`superseded_by` pointers) is handled SEPARATELY — do NOT edit BO-1600 as a
side-effect of BO-1800 authoring.

## Worktree quality-gate boundaries (avoid duplication) — BO-1700 family

BO-1700 ("Code can never ship from a workspace with its quality gates switched
off", added 2026-07-01) closes the fresh-worktree silent-hook-skip hole:
`.pre-commit-config.yaml` is a gitignored `.leafcutter` symlink, so a worktree
checked out from origin/main has neither symlink nor dir → pre-commit exits 0
running ZERO hooks. Six L1s: BO-1700a (execution/canary probe, not file-exists),
b (fail closed), c (self-healing shared hook), d (dual gate at create-time +
pre-drive), e (portable self-build + installed), f (graceful no-op where no
gates exist). Keep these DISTINCT from the adjacent trees:

- **Upstream of BO-210** — the pre-commit safety net (re-dispatch original coder
  on a hook FAILURE) assumes hooks FIRE. BO-1700 guarantees they fire first.
  Do not fold BO-1700 into BO-210 or vice versa.
- **Distinct from BO-1500e** — BO-1500e is the AC-authoring workflow's OWN
  worktree robustness (start-from-main / installed-copy). BO-1700 is general
  epic/feature BUILD-DRIVE worktrees. Same portability instinct, different path.
- **Distinct from BP-100k / BP-1000** (build-pipeline) — those govern hook
  CONTENT / source↔template parity. BO-1700 governs hook EXECUTION in a worktree.

Component-choice rationale (for future similar features): a "does the hook chain
actually FIRE during a drive" concern belongs in build-orchestration (drive /
worktree / pre-drive-gate territory), NOT build-pipeline (build.py / parity) or
infrastructure (hook content / conventions). By the same rationale the ADR-018
isolation-topology capability landed in build-orchestration (drive isolation +
main-branch gating during drives), not build-pipeline or infrastructure. The
BO-2200 documentation-coverage guarantee (2026-07-15) followed the same rule: a
drive-time documentation GATE belongs here, alongside BO-500 computed gates.

## Cross-component placement notes (parity & registry — NOT build-orchestration)

Two EPIC-FinalizeFeatureHardening retro items deliberately did NOT land here —
they extend existing trees in other components. Record this so future agents
don't recreate them under BO:

- **Workflow-script mirror parity (KI-3)** → `BP-1000e` (build-pipeline). It is
  the SAME byte-parity mechanism as BP-1000a (source ↔ shipped) applied to the
  `templates/workflows-js/*.js` ↔ `scripts/workflows/*.js` pair set. Added as a
  sibling L1 under BP-1000, NOT a new BO goal.
- **Registry tolerates workflow spawners (KI-4)** → `INF-600k` (infrastructure).
  Refines the registry validator (INF-600g family) to accept non-agent external
  callers (workflow `*.js` filenames, `user`) in `spawned_by` without "unknown
  agent" errors.

## Authored-but-prevention-only convention

When a retrospective Known-Issue is framed as PREVENTION ONLY by the user
(e.g. BO-1600), do NOT add a "detect-and-recover" sibling L1 on your own
initiative — recovery is a separate capability that must be explicitly requested.
The goal text should state the prevention scope and cite the neighbouring ACs it
is distinct from.
