---
title: "ADR-050: The Runtime Reachability Guard Inventories the Built Surface and Refuses, Never Warns"
description: "A registered command-surface capability that no automation invokes refuses the change in both a pre-commit hook and a CI job. The capability set comes from the built argparse parser and never from source text, because a source scan false-alarms on registrations that never happen at build time."
type: "adr"
status: "active"
created: "2026-09-25"
last_updated: "2026-09-27"
deciders:
  - BrainCandy
components:
  - commit_guardian
  - build_orchestration
  - build_pipeline
related_docs:
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-1-i.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900c-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900c-4.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900e.yaml
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/diagrams/c3-009-reachability-guard-data-flow.md
  - docs/how-to/resolve-a-reachability-guard-finding.md
related_code:
  - templates/scripts/commit_guardian/check_reachability.py
  - templates/scripts/commit_guardian/_reachability_inventory.py
  - templates/scripts/commit_guardian/_reachability_invocation_collector.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - scripts/commit_guardian/commit_guardian.json
  - .github/workflows/ci.yml
  - config/reachability_exemptions.yaml
  - scripts/build_orchestration/fast_lane.py
---

# ADR-050: The Runtime Reachability Guard Inventories the Built Surface and Refuses, Never Warns

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-25 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded for ticket `BO-2900b-1` (epic `EPIC-ARegisteredCapabilityThatNoAutomation`) |
| Supersedes | None |

## Context

An operator-facing command surface can register an action that no automation ever
runs. The action then looks like working capability: it has a subcommand, it has
tests, and nothing uses it. This has already happened. The BO-2400f lifecycle functions
(`claim_build_set`, `release_claim`) were stranded this way. A prototype static
caller finder, run against 38 labelled leafcutter incidents, flagged 4 of 17 vacuous
tests with no false alarms. That result is recorded in
`docs/analysis/2026-09-25-jev-test-triage-leafcutter-replication.md`. The prototype's
first version counted a docstring and some log strings as callers. That is the failure
mode BO-2900b-3 warns about.

[`BO-2900b-1`](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-1.yaml)
asks for a check that connects the capabilities a surface registers to the automation
that runs them. The first concrete surface is `scripts/build_orchestration/fast_lane.py`
(`_build_cli_parser()`). Its automation is `templates/workflows-js/fast-lane-ship.js`.
The check has to settle four design questions. Without a recorded answer, each one
tends to drift in a predictable direction:

1. **Where the capability set comes from.** A regex over `add_parser(` is the cheapest
   option. It also misreports in both directions. It finds registrations inside
   branches that are false at build time, and it misses registrations made in a loop
   over a table.
2. **Whether a finding blocks.** A new guard is usually introduced as a warning "for
   now". An advisory run that nobody reads protects nothing. The epic's premise is that
   a guard that has never said no does not count as protection.
3. **What relief exists.** Without one named escape route, people disable the guard
   with `SKIP=` or `--no-verify`. Some tools even print that bypass in their own failure
   message.
4. **How many seams.** The reverse check (BO-2900c: an invocation that names a
   capability which does not exist) needs the same inventory and the same invocation
   collection. Two copies would drift apart.

A structural wrinkle surfaced during implementation. `_reachability_inventory.py`
already existed, holding BO-2900d-1's exemption registry (`load_exemptions`,
`exemptions_in_force`, `is_exempt`). Also, the invocation collector reads only Python
today, while this repository's real automation is JavaScript (BO-2900b-3's scope).
The decision below covers both points.

## Decision

### 1. The capability set MUST come from the built surface

`registered_capabilities(parser) -> set[str]` MUST read the keys of the argparse
`_SubParsersAction.choices` on a parser that the surface's own builder actually
returned (for `fast_lane.py`, `_build_cli_parser()`). The guard MUST NOT extract
capabilities from source text by regex or by an AST scan of `add_parser(`. It MUST NOT
add source-scanned extras to the built inventory. Loading a surface MUST import the
module and call only the named builder. It MUST NOT execute the module's `main()`.

As a result, a capability registered only under a condition that is false at build
time is not checked. A capability registered in a loop over a table is checked.

### 2. A caller is an executed invocation, not a mention

A registered capability counts as "run by automation" if and only if its name is the
`capability` of at least one `Invocation` returned by
`collected_invocations(script_paths)`. An invocation is an executed call site. The
collector recognises calls such as `subprocess.run`, `call`, `check_call`,
`check_output` and `Popen` from their AST call nodes. A docstring, a comment, a log
string or any other text that mentions a capability MUST NOT count as a caller.

### 3. One shared seam serves both directions

`registered_capabilities()` and `collected_invocations()` MUST be exposed from
`scripts/commit_guardian/_reachability_inventory.py`. This is the same module that
already holds BO-2900d-1's exemption registry. The implementation is split into
`_reachability_invocation_collector.py` only to respect file size, and it is
re-exported from the seam. The forward check (BO-2900b) and the reverse check
(BO-2900c) MUST both consume this seam. A second inventory or collector MUST NOT be
written. The seam MUST be extended in place and MUST NOT be overwritten or forked.

### 4. A finding refuses the change; there is no advisory mode

Every `uncalled_capability` finding MUST make both the pre-commit hook and the CI job
exit non-zero. A finding names the capability, the surface module it is registered on,
and the two ways forward. The guard MUST NOT offer an advisory, warn-only or downgrade
flag, either global or per surface. The CI job MUST NOT carry `continue-on-error: true`.
If a job could never produce a real finding while carrying that flag, it would be
presented as enforcing the gate while being configured never to block.

### 5. The only sanctioned relief is a recorded exemption

The only way to pass with an uncalled capability is an entry in
`config/reachability_exemptions.yaml` that states a reason, following BO-2900d-1
([`BO-2900d`](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml)
is the parent AC: legitimate no-way-in work is recorded honestly, never waved through
silently). The guard MUST drop any capability for which `is_exempt()` returns true for
`exemptions_in_force(load_exemptions(...))`, and it MUST do so before emitting
findings.
[`BO-2900b-1-i`](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-1-i.yaml)
constrains this pass/refuse behavior further: it pins that a capability introduced
together with its caller in the *same* change passes (both `registered_capabilities()`
and `collected_invocations()` are read from the current working tree, never a prior
commit), and that a refusal's `ways_forward` names exactly these two options — adding
the invocation, or recording an exemption with a stated reason — and no third option
or bypass mention. This AC added no new code path; it added a pinned regression test
suite confirming the behavior above already conforms to this ADR.

### 6. The refusal never names its own bypass

The guard's output on a refusing run MUST NOT contain `SKIP=` or `--no-verify`.
Its two ways forward are to add the automation invocation in this change or to record
an exemption with a stated reason. The guard MUST NOT suggest any other route.
[`BO-2900e`](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900e.yaml)
governs refusal-message quality generally across all four of this guard family's
refusal causes; this section, and `BO-2900b-1-i`, constrain only which two options
*this* guard's message offers, not its prose.

### 7. Two layers, following the `check_done_proof.py` precedent

Enforcement consists of the `check-reachability` hook (`--mode precommit`) and a CI
job running `check_reachability.py --mode ci`. No third gate convention will be added.
The hook MUST be registered in `hooks_manifest` in both
`templates/scripts/commit_guardian/commit_guardian.json` and its deployed twin
`scripts/commit_guardian/commit_guardian.json`, with `n_location_rule: all`, as
required by [ADR-001](ADR-001-self-hosting-boundary.md) and enforced by
`check-hook-parity`. Every module the hook imports MUST reach the deployed layout in
the same change.

### 8. With no inputs, the guard says "nothing to check yet"; it does not relax

If no automation scripts are supplied, the guard has nothing to compare against. It
MUST report "nothing to check yet" and exit 0. It MUST NOT treat every capability as
uncalled. This is not a downgrade. The guard exits 0 because it received no inputs, and
it has no flag that suppresses a real finding. This is the only way the guard is inert
until the real JavaScript automation can be collected (BO-2900b-3) and the real set of
surfaces and automation scripts is derived rather than supplied (BO-2900c-4). When
those land, the hook and the CI job MUST start passing real inputs without any other
change to the refusal semantics.

## Consequences

### Positive

- The guard checks what the surface actually accepts at build time. Conditionally dead
  registrations produce no false alarms, and table-driven registrations are not missed.
- A stranded capability of the BO-2400f kind is caught when it is introduced, rather
  than discovered later by a test triage.
- One seam means the forward and reverse verdicts cannot disagree about what is
  registered or what is called.
- Operators get one documented escape route, a reasoned exemption, instead of learning
  about `--no-verify` from the gate's own error text.

### Negative

- Loading the built surface means importing arbitrary surface modules at check time.
  Import-time side effects and import errors become the guard's problem. They are
  converted to a `SurfaceLoadError` finding, which fails closed.
- The invocation collector sees only one hop of direct Python calls. Until BO-2900b-3
  lands, the real JavaScript driver cannot be checked. The guard therefore protects
  fixtures and explicitly supplied inputs, not this repository's live surface.
- Section 4 forbids `continue-on-error`, but the `reachability-guard` job was first
  shipped with it. The job must be changed to exit 0 honestly under §8, or the job
  stays out of compliance with this ADR.
- Exemptions become a second list that has to be maintained, and reasons given there
  can go stale.

### Operational

- Changes under `scripts/build_orchestration/**.py` or `templates/workflows-js/**.js`
  trigger the hook. Resolution steps are in
  [How to resolve a check-reachability guard finding](../../how-to/resolve-a-reachability-guard-finding.md).
- The data flow is drawn in
  [c3-009](../diagrams/c3-009-reachability-guard-data-flow.md). It shows the built-parser
  inventory, the invocation collection, the comparison, the exemption check and the
  refusal.
- A new module the guard depends on must be deployable from `templates/scripts/commit_guardian/`
  (a wholesale copy by `build_commit_guardian`) or registered in the build deploy
  manifest in the same change. Otherwise the gate crashes with `ModuleNotFoundError`
  once it is required.
- The move to live enforcement (BO-2900b-3 and BO-2900c-4) is a change to inputs only.
  It needs no review of the refusal semantics.

## Alternatives

- **Regex or AST scan of `add_parser(` in the surface source.** Rejected. It cannot
  evaluate the branch a registration sits in, so it reports capabilities that are never
  registered at build time. It also misses capabilities registered in a loop over a
  table, which is exactly the false-alarm and blind-spot pair the AC's
  conditional-registration clause forbids.
- **Built inventory topped up with source-scanned extras.** Rejected. Adding source
  results back to the built set brings back every false alarm §1 exists to remove.
  The union is never more accurate than the built set alone.
- **Ship as advisory first, promote to blocking later.** Rejected. An advisory result
  does not stop a stranded capability from merging, and in practice the promotion step
  gets deferred indefinitely. The ticket's constraint says "refuses, not warns". §8
  provides an honest inert state that needs no downgrade flag.
- **`continue-on-error: true` on the CI job during rollout.** Rejected. The job then
  claims to enforce the gate while being configured never to block. It is a global
  downgrade flag in all but name. Exiting 0 on missing inputs (§8) gives the same
  rollout safety without that contradiction.
- **Wire the real JavaScript automation now, against the Python-only collector.**
  Rejected. Measured empirically, it reports every real `fast_lane.py` capability,
  including `claim`, `release` and `mark_done`, as uncalled. Every commit and every PR
  touching those paths would then be refused for a reason that has nothing to do with
  reachability.
- **Separate inventory module for the reverse direction (BO-2900c).** Rejected. Two
  inventories can disagree about what is registered, so one direction could pass while
  the other refuses on the same fact.
- **Count any textual mention of a capability as a caller.** Rejected. The prototype
  finder's first version did this and counted docstrings and log strings as callers,
  which hid genuinely uncalled capabilities.

## References

- Originating ticket: `tickets/00_inbox/epics/EPIC-ARegisteredCapabilityThatNoAutomation/01_TICKET-20260925-BO-2900b-1.md`
- Follow-up ticket: `tickets/00_inbox/epics/EPIC-ARegisteredCapabilityThatNoAutomation/02_TICKET-20260925-BO-2900b-1-i.md` (pins the same-change adoption pass and the exact `ways_forward` content as a regression contract; landed, no functional code change was needed — the behavior above already conformed)
- [ADR-001: Self-Hosting Boundary](ADR-001-self-hosting-boundary.md): governs `scripts/` and `templates/scripts/` parity for the hook registration
- [Build Orchestration component](../components/build-orchestration.md): the component that owns the surface and automation
