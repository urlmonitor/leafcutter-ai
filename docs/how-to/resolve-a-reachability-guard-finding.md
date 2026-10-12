---
title: "How to resolve a check-reachability guard finding"
description: "Task-oriented guide for what to do when the check-reachability pre-commit hook or CI job reports an uncalled_capability finding: reading the message, choosing between wiring up the caller or recording an exemption, and running the check locally."
type: how_to
status: active
created: 2026-09-25
last_updated: 2026-09-27
components:
  - build_orchestration
  - commit_guardian
related_docs:
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/diagrams/c3-010-reachability-guard-data-flow.md
  - docs/how-to/managing-pre-commit-hooks.md
  - docs/how-to/done-proof-enforcement.md
  - docs/reference/workflow-authoring-contract.md
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900e.yaml
related_code:
  - templates/scripts/commit_guardian/check_reachability.py
  - templates/scripts/commit_guardian/_reachability_inventory.py
  - templates/scripts/commit_guardian/_reachability_invocation_collector.py
  - scripts/build_orchestration/fast_lane.py
  - config/reachability_exemptions.yaml
---

# How to resolve a check-reachability guard finding

`check-reachability` (BO-2900b-1) is the forward direction of the runtime-reachability
guard: every action a command surface's **built** argparse parser registers must have at
least one real automation invocation naming it, or the change is **refused** — never
downgraded to an advisory note. This guide covers what to do when you see its finding.

## What the finding looks like

```
[check-reachability] uncalled_capability: capability 'report' registered on surface
scripts/build_orchestration/fast_lane.py:_build_cli_parser is never invoked by any
automation. Ways forward: (1) add the automation invocation in this change; (2) record
an exemption for the capability with a stated reason.
```

`capability` is the exact subcommand name (the argparse `_SubParsersAction` choice —
e.g. one of `fast_lane.py`'s `claim`, `release`, `mark_done`, `select_batch`, and so on);
`surface` names the module the capability is registered on. The check exits non-zero
whenever at least one finding exists, both at the pre-commit layer (`--mode precommit`)
and the CI layer (`--mode ci`).

## Adding the capability and its caller in the same change passes

Both sides of the check are read from the **current working-tree state**, not from
what was already committed: `registered_capabilities()` reads the just-built parser
and `collected_invocations()` reads the automation scripts as they sit right now. This
means a change that registers a new capability and wires its automation invocation in
that same change produces **no finding** for that capability — the guard never compares
a new registration against the previous commit's callers, which would refuse the
ordinary case of introducing a capability together with the code that calls it
(`BO-2900b-1-i`). Only a capability that is registered with no caller anywhere in the
current working tree is reported.

## Two ways forward — nothing else is sanctioned

The finding always names exactly these two options — never a third, and never a skip
or bypass flag (`BO-2900b-1-i` pins this exact content as a permanent regression
contract). There is no global advisory or downgrade flag, and the check's own output
never names a skip mechanism. [`BO-2900d`](../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml)
governs the exemption route named as the second option below; [`BO-2900e`](../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900e.yaml)
governs refusal-message quality generally — this guard's own AC family only
constrains *which two* options the message offers, not prose style.

### Option A — add the automation invocation

Wire a real caller for the capability into the automation script that drives builds
(the concrete example is `templates/workflows-js/fast-lane-ship.js` invoking
`fast_lane.py`'s `claim` / `release` / `mark_done`). This is the right choice whenever
the capability is genuinely meant to be used — the finding means the wiring is missing,
not that the capability is wrong.

### Option B — record an exemption

When a capability deliberately has no runtime way in of its own (for example, an
operator-only diagnostic subcommand), record it in `config/reachability_exemptions.yaml`
with a non-empty `reason` (BO-2900d-1):

```yaml
exemptions:
  - item: 'scripts/build_orchestration/fast_lane.py:report'
    kind: capability
    reason: 'Operator-invoked diagnostic subcommand; no automation script calls it by design.'
    recorded: '2026-09-25'
    recorded_by: 'your-name'
```

`item` is matched by **exact string equality only** — no globs, prefixes, or
naming-convention inference. A blank `reason` records nothing and grants no pass.

## Running the check locally

```bash
python scripts/commit_guardian/check_reachability.py \
  --mode precommit \
  --surface scripts/build_orchestration/fast_lane.py:_build_cli_parser \
  --automation templates/workflows-js/fast-lane-ship.js
```

- `--surface MODULE_PATH:BUILDER` (repeatable) — a `.py` file and the name of a zero-arg
  callable in it returning a built `argparse.ArgumentParser`. Defaults to
  `scripts/build_orchestration/fast_lane.py:_build_cli_parser` when omitted — the
  minimum surface this guard covers.
- `--automation SCRIPT_PATH` (repeatable) — an automation script to scan for capability
  invocations. **No default is derived.** Omitting it entirely means nothing is checked
  this run (exit 0, with a stderr note explaining why) — never "every capability is
  uncalled".

The inventory always comes from the **built** parser (`registered_capabilities()` reads
the parser's own `_SubParsersAction.choices`), never a source-text scan — a capability
registered only under a condition that is false when the surface is built is correctly
never checked.

## Current rollout status for this repository's real surfaces

The registered `check-reachability` hook and its CI job pass **no** `--surface` /
`--automation` override, so today they report "nothing to check yet" and exit 0 against
this repository's real `fast_lane.py` capabilities — not because those capabilities are
reachable, but because `collected_invocations()` currently recognises only Python
automation scripts (AST-based), and this repository's real driver,
`templates/workflows-js/fast-lane-ship.js`, is JavaScript. Running the CLI above with the
real `--surface`/`--automation` pair today reports **every** real capability — including
`claim`, `release`, and `mark_done` — as uncalled, because the collector cannot yet read
JS command construction, not because they are genuinely unreached. Wiring the hook/CI
job to run with real inputs before that gap closes would false-refuse every commit or PR
touching `scripts/build_orchestration/` or `templates/workflows-js/`.

This is a deliberate, documented sequencing gap, not a bug: JavaScript invocation
collection and the derived real surface/automation-script set land in a later change
(tracked separately from BO-2900b-1). Until then, you will only see a real finding when
you invoke the CLI yourself with explicit `--surface`/`--automation` flags — for example
against a fixture surface — or once that follow-on work lands and the hook/CI job's
`continue-on-error` is removed.

## What this check will never do

- It never passes with an advisory note. A finding is always a non-zero exit.
- Its own failure output never names `SKIP=check-reachability` or `--no-verify` — the
  only sanctioned relief is the exemption registry above.

## See also

- [Commit Guardian — Pre-Commit Hook System](../architecture/components/commit-guardian.md)
- [Reachability Guard — Data Flow](../architecture/diagrams/c3-010-reachability-guard-data-flow.md)
- [How to manage pre-commit hooks in leafcutter](managing-pre-commit-hooks.md)
- [How to understand proof-of-done enforcement (pre-commit and CI)](done-proof-enforcement.md) — the two-layer precedent this guard mirrors
- [ADR-050 — Runtime Reachability Guard Refuses, Never Warns](../architecture/adrs/ADR-050-runtime-reachability-guard-refuses-not-warns.md) — the decision record covering the same-change adoption case and the two ways forward
- [BO-2900d — legitimate exceptions are recorded honestly](../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml) — the exemption route
- [BO-2900e — the guard names exactly what is unreachable](../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900e.yaml) — governs refusal-message quality generally
