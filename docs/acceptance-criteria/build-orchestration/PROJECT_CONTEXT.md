---
title: "build-orchestration — AC store context"
description: Accumulated conventions for the build-orchestration AC namespace — L0
  numbering, scope boundaries vs. neighbouring components, and concurrency/parity/registry
  distinctions for BO-series authoring agents.
created: '2026-07-17'
last_updated: '2026-09-14'
type: tutorial
status: active
components:
  - build_orchestration
  - ac_store
---
# build-orchestration — Project Context for Authoring Agents

Accumulated conventions for the `build-orchestration` AC namespace (prefix `BO`).
Read this before authoring or decomposing ACs in this component.

## ID numbering

- L0s occupy hundreds: 100, 200, 201, 202, 300, 400, 500, 700, 800, 900, 1100,
  1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400,
  2500, 2600, 2700, 2800, 2900, 3100, 3200, 3500, 3600, 3800. Slots 3000, 3700
  and 3701 are occupied by loose `BO-NNNN.yaml` L2/L3 records sitting at the
  component root — a loose file reserves its slot exactly as a folder does.
- Next free L0 hundred is **BO-4200** (correct as of 2026-09-21, when BO-4100 was
  added; BO-3900 and BO-4000 are loose L2 records that reserve their slots). Pick
  the next free hundred for any new L0.
- **This line has now gone stale four times** — it has previously claimed
  BO-1900, BO-2300, BO-3300 and BO-3900 while the store had already moved past each.
  Treat the number above as a hint, never as an answer: `ls` the component
  directory (folders AND loose `BO-*.yaml` files) and confirm the highest
  existing slot before assigning, then update this line in the same pass.
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

## Sound workspace by construction — BO-4100 family (the BO-1700 sibling, and why)

BO-4100 ("The workspace you are given is sound, and what you are told about it is
true", added 2026-09-21, origin BrainCandy) is the SIBLING of BO-1700, authored
after an overlap audit of a six-item worktree incident report. Five L1s:
BO-4100a (baseline freshness at creation), b (supporting material is the
workspace's own), c (disposability is knowable), d (the account of what was made
is truthful), e (the set of workspaces is complete and every leftover is clearable
— added 2026-09-21 on operator ruling, after the BA's first decomposition pass).

**BO-4100e is NOT part of BO-4100c, and the reason generalises.** All four of
BO-4100c's L2 children presuppose the workspace APPEARS in the live set: c-1
assesses that set, c-2/c-3/c-4 each act on an entry within it. A workspace the
listing cannot see (KI-BO-20260831-1331) is outside the domain of all four, and
folding it in would force every one of them to carry a weaker precondition ("for
workspaces the listing can see…"). Different promises, too: c promises the
disposability VERDICT is right; e promises the listing is COMPLETE and that
something unlistable is still recoverable. BO-4100e is scoped to the RECOVERY half
only — prevention is already BO-4100a-3-i ("a refused creation leaves no branch,
directory or registration behind").

**Every L1 in this family carries `documentation_triggers: []`.** That is deliberate
and follows from the framing decision below, not from oversight. Two were cleared on
operator ruling 2026-09-21 after the BA declined to author documentation ACs to
satisfy them. BO-4100b's is recorded as a DEFERRAL — the shared-versus-own topology
may deserve a component diagram as architecture documentation later — and BO-4100c's
as a denial on the merits, since a how-to telling an operator to judge ~150
workspaces by hand is the instrument that already failed. When adding to this family,
a documentation trigger is the exception that needs arguing, not the default.

**Why it is a sibling and not four more BO-1700 children — read before adding
anything worktree-shaped.** Two independent reasons, and the second is the real one:

1. BO-1700 sits at its 8-child cap under `child_limit_override: 8`, whose own
   amendment record says the waiver is temporary and must be REMOVED by folding
   into a sibling L0 — not widened. Raising it again is not an authoring agent's
   call to make silently.
2. The SUBJECT differs. BO-1700 makes exactly one promise: quality gates cannot be
   switched off. BO-4100's four properties are not gate-shaped — freshness,
   independence, disposability, truthful naming. Only BO-4100b touches gates at
   all, and from the opposite side. Folding them in would turn BO-1700 into
   "everything about worktrees" and cost it a tight, falsifiable goal.

**The three freshness ACs are all needed and none implies another.** This is the
single most likely thing to be got wrong near here:

- **BO-4100a** — freshness AT CREATION. What commit the workspace is rooted at.
- **BO-900a** — divergence DURING a long drive, measured in commits ahead, with a
  configurable threshold and a pause.
- **BO-1800f** — freshness AT DELIVERY, before finished work leaves its copy.

**Polarity warning on BO-4100b.** It concerns a check that wrongly REFUSES over
material the workspace borrowed from a shared install tree. BO-1700's entire family
concerns a check that wrongly stays SILENT. BO-1700h's phrase "a stale workspace is
flagged rather than trusted" reads like a match and is not one — that is the guard
staying CORRECT under drift. Also distinct from BO-1700e (guard portability across
layouts) and BO-1700f (standing aside where a project genuinely has no checks — a
true negative, not a false positive).

**BO-4100c vs BO-1800d.** BO-1800d was rejected as the host. It is the do-no-harm
constraint on background tidying against a drive that is STILL RUNNING, and it
presupposes tidying exists. It is silent on accumulation, on how a finished
workspace is recognised, and on a workspace that is idle yet still holds work that
never reached the shared line. Both records are needed.

**Framing decision, settled at PO stage — do not re-open at L2.** The request
arrived as "a skill that TELLS an agent how to create, verify and clean up a
workspace" and was deliberately reframed as enforcement. Guidance that must be read
to help is a weaker instrument than a property that holds by construction: the
incident that prompted the request happened to an operator who had not read the
guidance, in a repository whose own CLAUDE.md documented the symptom and pointed at
the broken remedy rather than naming the canonical script. No child of BO-4100 may
be decomposed into "a document explains how to...".

## Refusal-triggered specialist handoff — BO-3800 family (placement + the BO-210 seam)

BO-3800 ("When a standard turns work away, the right craft is brought in to finish
it", added 2026-09-14) is the supervisor-side half of a capability whose guardrail
half is GE-127f. It lives here for the usual reason: a commit-time gate can only
REFUSE — it cannot summon anyone — so the RULE belongs in guardrail-engine and the
HANDOFF (hold the change, ask the specialist, retry delivery, stop and report when it
still fails) belongs in the layer that drives the work. Five L1s, each separately
failable; keep them distinct when decomposing:

- **BO-3800a** — the change's FATE: held, not lost and not forced through, and
  re-offered afterwards. Hold and retry are one record on purpose.
- **BO-3800b** — WHO does the tidying: a restructuring craft, never the author
  mid-change. The user's requirement, and the only structural answer to line-shuffling.
- **BO-3800c** — the BRIEF: the named file and the named demand are CARRIED, never
  reconstructed. Same split as BO-2200c (dispatch vs. brief).
- **BO-3800d** — the GIVE-UP path: bounded, and reported with what was asked, done and
  outstanding. No infinite retry, no quiet pass.
- **BO-3800e** — the NEGATIVE promise: everything a standard does not ask a specialist
  for is unchanged. Without it, the cheapest implementation summons a specialist on
  every refusal, which passes every positive arm and is a serious regression.

**BO-3800a is bounded to work being DRIVEN — decided 2026-09-14, do not re-open.** The
hold-and-re-offer promise applies inside a drive only. A refusal outside one — a hand-run
`git commit` at a terminal — is simply refused, with the refusing standard's own message as
the whole of what the author gets; nothing is held and no specialist is summoned. The reason
is ADR-019's depth-1 cap: holding a change and re-offering it need a party that outlives the
refusal, which is the depth-0 driver, and the delivery step itself runs at depth 1 where an
agent cannot invoke the Agent tool at all — such calls are silently dropped. The alternative
was rejected because no design for it exists under that constraint. BO-3800a-1's "Given a
ticket is being driven" Givens are correct under this decision and must not be widened.

**Hard precondition: INF-800f** (infrastructure). The restructuring craft is a slash
command today, reachable by hand and by nothing else. Nothing in BO-3800 is buildable
until INF-800f makes it askable. Do not re-specify or decompose it under BO.

**The BO-210 seam — the thing most likely to be got wrong.** BO-210 is the nearest
neighbour and was rejected as the HOST. Its promise is that a hook-failure fix is done
by the SAME agent type that authored the work, holding its original context; BO-3800's
promise is that for one class of refusal the author is the WRONG party. Both are right
in their own population and the boundary is the disposition the refusing standard
itself states — it is not judged by either record. BO-210 now carries a
`narrowed-by-later-sibling` audit entry pointing at BO-3800 (criteria untouched), in
the same shape GE-127b carries for GE-127f. Reconcile BO-210a and BO-210c with the
carve-out in the change that implements BO-3800.

**Reuse, do not rebuild: BO-3000 / BO-3000a.** Handoff routing already ships — target
re-dispatched before any later phase, handing-off phase not recorded complete, refusal
diagnosable, and the target NEVER inferred from prose. What it cannot supply is the
trigger, because a standard that refuses emits no handoff and names no target. That
missing trigger is BO-3800's whole subject, and BO-3000a's no-inference decision is the
reason BO-3800c insists the demand is carried rather than reconstructed.

**What is provable here, and what is not** (settled at PO stage; do not widen at L2):
separation of duties is invisible in a delivered change — one change, one identity — and
anti-shuffling is invisible in a diff, since moving NEW work out is desired and moving
EXISTING content out to make a number fall is the failure. No criterion may assert that
the restructuring WAS performed by the specialist. What is provable is the SEQUENCING:
that the specialist is actually asked on the refusal path before delivery is retried.
That is a reachability-shaped claim, and `fast-lane-build.js` is this repo's scar on
what happens when such a claim is covered by a grep-only test instead.

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
