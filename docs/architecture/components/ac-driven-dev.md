---
title: "AC-Driven Development — AC-First Build Pipeline"
description: "The AC-driven development pipeline: /plan-feature authoring, /build-ac selection and ticket generation, and the AC-first build loop that treats the AC store as the authoritative backlog."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-08-31
components:
  - ac_driven_dev
---

# AC-Driven Development

## Overview

AC-Driven Development is the pipeline that treats the acceptance-criteria store as the authoritative backlog. Feature intent is first authored as ACs via `/plan-feature` (PO → BA → IT-PO), then `/build-ac` selects the next highest-priority ready AC, generates a fully-wired ticket from it, and hands off to the build loop. This replaces ad-hoc ticket creation with an AC-first flow where every unit of work traces back to a criterion in the store (per ADR-010).

## Responsibilities

- Author ACs from a feature request through the PO/BA/IT-PO stages (`/plan-feature`)
- Rank ready ACs and generate implementable tickets with back-references (`/build-ac`)
- Maintain the AC store as the single authoritative backlog for what ships next

## Entry Points

- `templates/workflows-js/plan-feature.js` — AC authoring workflow. Its authoring-worktree
  creation step resolves the [worktree-manager](worktree-manager.md)'s
  `scripts/setup_ticket_worktree.py` to an absolute, repository-anchored location rather
  than a session-cwd-relative one (`buildRepoAnchoredResolutionCommand` /
  `resolveRepoAnchoredScriptPath`), so the copy invoked is always the one inside the
  repository being operated on, never the deployed copy outside it under the
  [ADR-001](../adrs/ADR-001-self-hosting-boundary.md) self-hosting layout. See
  [`docs/known-issues/ac-driven-dev.md`](../../known-issues/ac-driven-dev.md) → `KI-ACD-004`
  for the failure this fixes and the sibling sites still open against the same mechanism.
  Independent of that caller-side fix, `setup_ticket_worktree.py`'s `create-only`
  subcommand also hardens the resolution site itself with a bounded-search fallback for
  when the script is invoked from outside any git repository at all (AC `ACD-2100a-2`)
  — see [worktree-manager](worktree-manager.md) for the resolution contract.
- `templates/skills/build-ac/SKILL.md` — AC selection and ticket generation

## Integration

AC-Driven Development produces the tickets that Build Orchestration dispatches. It reads and writes the `ac_store` component (`docs/acceptance-criteria/`) as its backing store. See ADR-010 (AC store as authoritative backlog) for the design rationale.

## Coverage Resolution — `ac_coverage_resolver`

Every ticket `/build-ac` generates carries an `ac_traceability` frontmatter block that names
the source AC(s) it was generated from (`generate_ticket_from_ac.py`, `_build_frontmatter`).
The generator emits the **two-key form** — `{id, path}`, naming the exact store file — on
every generated ticket. A separate, previously-accepted **list form** —
`{l2, l3, ac_path}`, naming a base directory plus L2/L3 id lists — is the shape [BO-201](../../acceptance-criteria/build-orchestration/BO-201.yaml)
originally specified.

`scripts/ac_store/ac_coverage_resolver.py` is the single, importable, side-effect-free
resolution seam both shapes funnel through, consumed by the `ac-fulfillment-gate` agent
template (Step 1) at commit-gate time:

- `resolve_coverage(ticket_path)` — interprets the block block-first (two-key, then list
  form), falling back to the ticket's `source_ac` field only when the block itself yields
  nothing. A block present with unrecognised keys is reported as **uninterpretable**, never
  silently treated as "nothing to verify" — even when `source_ac` goes on to rescue the
  resolution, the unrecognised keys are still surfaced.
- `verify_ticket_coverage(ticket_path)` — loads each resolved AC's `work_status`,
  `implemented_by`, and `covered_by`, and returns a verdict with a `verified_count`.
- `compute_verdict(resolved_acs, ac_results)` — the load-bearing invariant: `ok` can never be
  `True` when `resolved_acs` is empty, regardless of `ac_results`. This closes a vacuous-truth
  gap where a generator-produced ticket's `ac_traceability` block (two-key form) was invisible
  to a gate that only ever extracted the list form — its "working list" was always empty, and
  "every AC in the working list passed or skipped" was vacuously true over that empty list, so
  the gate signed off green having verified nothing (`ACD-1900b-5-i`).

Resolution is read-only and deterministic — it never mutates the ticket or any AC YAML file;
auto-fix remains downstream in the gate template's own Step 3. The module is registered in
`build_ac_store`'s `deploy_map` (`scripts/build_phases.py`) so the deployed `.claude/agents/`
copy of the gate template can invoke it via its CLI (`--ticket <path>`, only Bash/Read/Edit
tools are available to the template itself).

Per [ADR-026](../adrs/ADR-026-ac-driven-build-v2-phased-migration.md) rule 5, the gate's
silent-skip is scoped to an **absent** `ac_traceability` block only ("absent → ok" stays
until the generator stops emitting legacy tickets); a **present-but-uninterpretable** block is
not covered by that carve-out and must return a non-ok verdict. Per
[ADR-001](../adrs/ADR-001-self-hosting-boundary.md), `templates/agents/ac-fulfillment-gate.md`
is the canonical source and the deployed `.claude/agents/` copy is build output — the fix must
land in the template and be verified in the deployed layout after a rebuild, since the running
gate reads the deployed copy. See also
[Phantom-Done Prevention](phantom-done-prevention.md) for the broader class of defect this
closes: a gate reporting a pass it never earned.
