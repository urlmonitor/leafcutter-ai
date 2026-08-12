---
title: "ADR-026: AC-Driven Build v2 — Phased, Dogfooded, Backward-Compatible Migration"
description: "Decision to roll out the single-source / AC-as-unit-of-work / thin-ticket redesign as a read-side-first phased migration behind a two-stage flag, dogfooded on self-host before any consumer cutover, rather than a big-bang."
type: "adr"
status: "active"
created: "2026-08-12"
last_updated: "2026-08-12"
deciders:
  - BrainCandy
components:
  - ac_driven_dev
  - ac_store
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - docs/architecture/adrs/ADR-012-retire-create-ticket-js.md
  - docs/architecture/agent_knowledge_plane.md
  - docs/roadmap.json
---

# ADR-026: AC-Driven Build v2 — Phased, Dogfooded, Backward-Compatible Migration

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-12 |
| Deciders | BrainCandy |
| Author | main-loop synthesis of a three-perspective (Fable-5) safety deliberation |
| Context ADRs | ADR-010 (AC store as authoritative backlog), ADR-012 (retire create-ticket.js) |

## Context

ADR-010 made the AC store the authoritative backlog and tickets *derived* artefacts;
ADR-012 retired hand-authored tickets in favour of `/plan-feature` + `/build-ac`. In
practice the generated ticket still **duplicates** the full AC content (criteria,
`it_requirements`, contracts) into its body, and phase agents read the **ticket body**
as their primary spec — not the store. Empirical comprehension tests (rendering the real
effective prompt for `python-coder` against real ACs) confirmed the gap and surfaced
several others.

The **target model** — captured as ACs under component `ac_driven_dev` — is:

- **ACD-1600 (single source, buildable):** thin tickets that *reference* their AC (no
  verbatim copy); phase agents *pull* their spec from the store via `source_ac`; every
  path an AC names points at **canonical source** (`templates/…`), never a build-output
  copy (`scripts/…`, `.claude/…`); an enrichment gate holds back ACs missing file targets
  or a test contract.
- **ACD-1700 (role-scoped, verifiable):** each agent's spawn context excludes other roles'
  content; `assigned_agent` matches the deliverable surface (a path-aware surface→craft
  map); an effective-prompt render tool previews an agent's brief before build.
- **ACD-1800 (AC is the unit of work):** each AC carries a **deliverable checklist**
  (code/tests/docs/diagrams/config) with **per-deliverable sign-offs recorded on the AC**;
  the AC is done when all deliverables are signed off; the **ticket becomes a grouping
  container** (bundles ACs into a value feature; no per-phase sign-offs of its own). This
  supersedes the fat-ticket generation model (ACD-400b family).

Two properties make a naive rollout unsafe:

1. **Deep interdependence ("big-bang risk").** Thinning the ticket before phase agents and
   gates learn to read the store hands them an empty spec — and, worse, several gates stay
   **green while verifying nothing** (`ac-fulfillment-gate` returns `status: ok` whenever
   `ac_traceability` is absent; `ac-validator` has nothing to check; `done_proof` loses its
   evidence anchors). That is system-level phantom-done — the exact failure this repo exists
   to prevent.
2. **Backward compatibility.** leafcutter-ai is a portable package installed into consumer
   projects. Existing consumer stores have ACs that **lack** the new fields, fat tickets in
   flight, and paths pointing at build outputs. A hard cutover breaks them. Compounding this:
   `config/ac_store_schema.json` declares `additionalProperties: false` but **nothing
   enforces it today** (the validator hand-checks four fields and its docstring is wrong) —
   a dormant tripwire that would reject the whole store the instant real enforcement is wired.

A three-perspective deliberation (sequencing, backward-compat, risk/rollback) converged on
the same conclusion, which this ADR records.

## Options Considered

### Option A — Big-bang cutover
Ship the whole redesign in one change and flip every consumer at once.

**Rejected.** Maximises blast radius, offers no safe rollback, and the interdependence means
any single missing piece (a gate that reads ticket-body sign-offs, an un-deployed hook
dependency) blocks **every merge** in this repo and in every consumer. The phantom-green
failure modes above would ship silently.

### Option B — Never migrate (keep fat tickets)
Leave the current model; treat ACD-1600/1700/1800 as aspirational.

**Rejected.** The fat-ticket model duplicates the spec, over-injects cross-role context, and
cannot enforce the AC-as-unit-of-work guarantees the roadmap outcome depends on.

### Option C — Read-side-first phased migration behind a flag, dogfooded on self-host (chosen)
Land the changes as additive/dormant increments and warn-then-enforce gates, gated by a
two-stage flag, in a strict order that keeps every phase a self-consistent green build.

**Accepted.** It is the only option that removes the phantom-green and consumer-breakage
risks while keeping the required CI gates green throughout and preserving a one-commit
rollback.

## Decision

**Roll out AC-Driven Build v2 as a read-side-first, flag-gated, dogfooded phased migration.**

### The load-bearing invariant

> **Read-side before write-side.** Every agent and gate must dual-read (store *or*
> ticket-body) **before** the ticket is thinned or sign-offs move. Reversing this order
> produces a build that is green while verifying nothing.

Note this is the *reverse* of the AC numbering: ACD-1600a ("thin ticket") is numbered before
ACD-1600b ("agents pull"), but 1600b ships first. **The migration plan — not the AC IDs — is
the ordering authority.**

### Control surface

A single two-stage flag plus a per-AC data-version field:

```yaml
ac_unit_of_work:
  emit:    false   # generator produces thin tickets + AC-side sign-offs
  enforce: false   # gates REQUIRE the new shape (else dual-read / advisory)
```

- **`schema_version`** on each AC (default `1` = legacy, `2` = new) is the *data* signal
  (reader shape); the flag is *store policy* (what to enforce). `enforce` may turn on only
  once zero `schema_version < 2` ACs remain.
- **Kill-switch:** `enforce:false` → gates fall back to dual-read/advisory (one commit, no
  code revert). **Generator rollback:** `emit:false` → fat tickets return (safe because
  gates dual-read).

### Roadmap phases (see `docs/roadmap.json`)

- **`phase_acbuild_1_foundation`** — additive-only: optional new AC fields + `schema_version`
  in `ac_store_schema.json`; productionised effective-prompt render tool (in the build
  deploy-manifest); canonical-source path resolution; universal agent/gate dual-read; new
  gates in warn mode; the flag introduced (both off). No behaviour change.
- **`phase_acbuild_2_cutover`** — dogfooded on self-host first: generator emits thin tickets
  behind `emit`; deliverable checklist + per-deliverable sign-offs on the AC; sign-offs
  dual-recorded then moved off the ticket in the single atomic cutover; store backfilled;
  gates promoted to required only after a green self-host window.
- **`phase_acbuild_3_migration`** — consumers: `build.py` deploys new artefacts and warns on
  `schema_version` skew; opt-in idempotent backfill; dual-readers retained ≥2 minor releases
  while in-flight fat tickets drain; only then remove fat-ticket generation and the
  legacy-derive path.

### Non-negotiable safety rules (from the deliberation)

1. **Additive schema first.** New AC fields land **optional**, in lockstep with the code
   that reads them; `additionalProperties` is never tightened until the store is 100%
   backfilled. Fix the false docstring on `validate_ac_schema.py`.
2. **Deploy-manifest-first.** No hook/gate script is made a *required* CI check until it is
   in the correct `build_phases.py` deploy_map and verified from the **deployed** layout
   (the `done_proof.py` `ModuleNotFoundError` precedent).
3. **Advisory before required.** New gates ship `enabled:true, strict:false` and are promoted
   to required only after ≥10 consecutive green self-host merges; new done-accounting gates
   are **diff-scoped** (like BO-2500b) so pre-existing ACs never retroactively fail.
4. **Tolerant readers / grandfathering.** Absence of a new field = legacy mode: derive, never
   fail. Already-`done` ACs are grandfathered so migration never mass-reverts them.
5. **The `ac-fulfillment-gate` silent-skip** ("absent `ac_traceability` → ok") stays until the
   generator stops emitting legacy tickets; its flip to "absent → blocker" happens only at the
   `enforce` stage after fat tickets drain.
6. **Self-host is a self-consistent build.** The thin generator and universal dual-read ship
   in the **same self-build**; each phase must pass this repo's own required CI (Lint,
   Component vocab, Test suite, Proof-of-done) before merge.
7. **Behavioral spot-check on a real on-disk ticket in a fresh process** before any cutover is
   called done — green sign-offs are not sufficient.

### Go / No-Go for the final cutover (removing the old path)

Cut over only when ALL hold: strict store validation = 0; all required CI gates green on ≥10
consecutive self-host merges under `enforce:true`; a full self-host epic driven end-to-end
thin + AC-sign-off and behaviorally spot-checked on a real ticket; render comprehension test
passes; every new gate script in the deploy_map with no `ModuleNotFoundError`; ≥1 consumer (or
consumer-sim) upgraded green; rollback rehearsed (`enforce:false` restores green in one commit).
No-go signal: any required gate red, any deployed-hook import error, or a shadow check showing a
gate that verified zero ACs.

## Consequences

### Positive
- No phantom-green window: verification always precedes thinning.
- One-commit rollback at every phase; required CI stays green throughout.
- Consumers upgrade on their own cadence; in-flight fat tickets drain rather than break.
- The redesign is dogfooded on leafcutter itself before any consumer sees it.

### Negative
- Longer calendar time and a sustained dual-read/dual-write compatibility window (≥2 minor
  releases), which is code that must later be removed (a scheduled second cutover).
- Temporary duplication (dual-recorded sign-offs; both ticket shapes co-existing).

### Neutral
- The AC store already models non-destructive supersession (`status: superseded_by` +
  carry-forward children), which the fat-ticket retirement reuses.

## Alternatives Summary

| Option | Outcome |
|---|---|
| A — Big-bang | Rejected: max blast radius, no safe rollback, phantom-green risk |
| B — Never migrate | Rejected: cannot deliver the AC-as-unit-of-work guarantees |
| C — Read-side-first phased, dogfooded, flag-gated | **Accepted** |

## References

- [ADR-010 — AC Store as Authoritative Backlog](ADR-010-ac-store-as-authoritative-backlog.md)
- [ADR-012 — Retire create-ticket.js](ADR-012-retire-create-ticket-js.md)
- [Agent Knowledge Plane](../agent_knowledge_plane.md) — the injection channels role-scoping applies to.
- `docs/roadmap.json` — phases `phase_acbuild_1_foundation` / `_2_cutover` / `_3_migration`.
- Target ACs: `docs/acceptance-criteria/ac-driven-dev/ACD-1600-*`, `ACD-1700-*`, `ACD-1800-*`.
- Superseded model: `docs/acceptance-criteria/ac-driven-dev/ACD-400b.yaml` (+ `-400b-1`, `-400b-5`).
