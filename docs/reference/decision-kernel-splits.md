---
title: "Reference: When a Kernel Request Is Split, Left Whole or Recorded as a Capability Gap"
description: "Short lookup for the decision kernel's routing-time outcomes for a request that may hold several questions: the four outcomes with an example each, the fewer-than-two-parts rule, what a rejected or too-small split falls back to, and gap accounting."
type: reference
status: active
created: 2026-10-10
last_updated: 2026-10-10
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md
  - docs/architecture/components/decision-kernel.md
  - docs/reference/kernel-request-splitting.md
  - docs/reference/kernel-request-splitting-2-conversion-gate-runs-config.md
  - docs/how-to/run-the-decision-kernel.md
related_code:
  - kernel/split/detect.py
  - kernel/split/convert.py
  - kernel/split/gate.py
  - kernel/split/text.py
  - kernel/scheduler/nodes_split.py
  - config/kernel_config.default.json
---

# Kernel splits: routing-time outcomes and gap accounting

Lookup for what the decision kernel does with a request that may hold several questions, and
when that request is split, left whole or recorded as a capability gap. The full rules are in
[ADR-067](../architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md)
and the two specification pages linked under [See also](#see-also). The container overview is
[decision-kernel.md](../architecture/components/decision-kernel.md).

## Build status

| Part | Status in this build |
|---|---|
| Detection, the `host.decompose_goal` proposal, conversion and the opening of the split gate | Built (DK-400a, DK-400c) |
| Fewer-than-two-parts handling and the fallbacks below | Built (DK-400c-3) |
| The gate's approve and reject outcomes, and the rule that an approved split records no gap | Arrive with DK-400d (DK-400d-1, DK-400d-3, DK-400a-1-ii) |
| Part runs | Arrive later (DK-400e) |

`split.enabled` ships `false` in `config/kernel_config.default.json` in this release and the
next, so none of the behaviour below runs on a default install. With it `false`, the kernel
behaves exactly as before: no bundle question, no split record, today's gap and clarification
paths ([specification section 11](kernel-request-splitting-2-conversion-gate-runs-config.md#11-configuration-the-off-switch-and-the-staged-rollout)).
Rules marked "arrives with DK-400d" are decided in ADR-067 and the AC records; no code applies
them yet.

## The four routing-time outcomes

Detection asks one "one question or several?" judgement per eligible root request. The request
counts as bundled only at or above `split.bundle_threshold` (0.8). The deterministic gates that
decide whether it is asked at all are in
[specification section 2](kernel-request-splitting.md#2-detection-gates-first-then-one-jev-question-that-adds-no-provider-call).
The example requests are illustrative.

| Outcome | When | Trigger value | Example request |
|---|---|---|---|
| Offered as a split because routing turned it away | Bundled, and routing ended `no_match` with reason `jev_none` (no capability could meet it) | `jev_none` | "Compare our CI providers and also draft a migration plan for the data warehouse." |
| Offered as a split because routing turned it away | Bundled, and routing could not decide (`insufficient_context`) | `ambiguous` | "Which queue should we use, and are we ready to launch in March?" |
| Offered as a split although routing would accept it as one decision | Bundled, and routing selected one capability for the root | `bundled_accepted` | "Should we adopt trunk-based development, and should we move our docs to a wiki?" |
| Left whole as one decision | Not bundled: below the threshold, a gate is closed, or the answer kind is ideas, change or out_of_domain | none | "Should we use Postgres or MySQL for the audit log, given our reporting needs and a small team?" |
| Recorded as a capability gap | A single question no capability can meet (`jev_none`, not bundled) | none | "Translate the handbook into Japanese." |

Notes:

- The first two rows are the two ways routing turns a request away, so they make up one outcome
  with two trigger values. Together with the other three rows they are the four outcomes.
- Alternatives joined by "or" and constraints joined by "and" make one question, not several
  (bundle question template `kernel.split.bundled`, revision 2).
- A caller-supplied `leafcutter.decision_request.v1` is never checked for bundling. It goes
  ahead as the one decision the caller named.
- `bundled_accepted` keeps the accepted routing on the split record (`kept_routing`), so a
  kept-whole ending resumes from it without routing again.

## Fewer than two parts

When the host's proposal for a split comes back with fewer than two usable parts, the request is
treated as one question and no split gate opens (DK-400c-3). This also applies when the host's
repair attempts for the proposal run out.

- A proposal counts as too small when fewer than two parts survive conversion, after parts that
  fail the quote check or cannot be placed are set aside
  ([specification section 5](kernel-request-splitting-2-conversion-gate-runs-config.md#5-conversion-is-total-and-deterministic)).
- The split record is closed (state `closed`). It never reaches the envelope, the output or
  `report.md`, and a run event (`split.not_offered`, `split.closed`) names the reason.
- The request's `split_checked` flag stays set, so it is never offered a split again in the run.
- The request then goes on by its trigger, as in the next section.

## Fallbacks when no split goes ahead

The same fallback applies when the person rejects the split of a request routing turned away
(arrives with DK-400d-3) and when fewer than two parts come back (built).

| Trigger | Fewer than two parts (built) | Person rejects the split (arrives with DK-400d-3) |
|---|---|---|
| `jev_none` | Today's capability gap is recorded and the run ends `blocked` with today's blocked report | State `rejected`; the same: today's `unsupported` gap, run ends `blocked` |
| `ambiguous` | Today's clarification question opens and the run waits for the person | State `rejected_clarify`; the same clarification question |
| `bundled_accepted` | Goes ahead from `kept_routing` as one decision | State `rejected_kept_whole`; the same |

- An `ambiguous` request falls back to today's `insufficient_context` path unchanged. Today's
  ambiguous gap is recorded only if the request ends unresolved (the person cannot be asked, or
  the follow-up limit is reached).
- A request that fell back to the clarification question is not offered a second split in the
  same run.
- Full table: [specification section 7](kernel-request-splitting-2-conversion-gate-runs-config.md#7-endings-are-keyed-on-the-trigger).

## Gap accounting

A split request is not counted as a capability gap. A single question no capability can meet
still is. The kernel decides the gap when the split's outcome is known, never at detection: when
a `jev_none` root is offered a split, the detection step starts the split instead of recording a
gap.

| Case | Gap recorded for the request | Status |
|---|---|---|
| Split started, gate open | None yet | Built |
| Split approved | None | Arrives with DK-400d (DK-400a-1-ii) |
| `jev_none`, fewer than two parts or proposal refused | Today's gap, `fallback_outcome` `blocked` | Built |
| `jev_none`, split rejected | Today's `unsupported` gap | Arrives with DK-400d-3 |
| `ambiguous`, any fallback | None while the clarification question is open; the ambiguous gap only if it ends unresolved | Built for fewer than two parts; for rejection arrives with DK-400d-3 |
| `bundled_accepted` | Never | Built |
| Single question no capability can meet | Today's gap, unchanged (`gap_key`, `gap_type`, `normalized_need`, `fallback_outcome`) | Built, unchanged |

Gaps from a part's own work are attributed to that part, never to the split's subject
([specification section 10](kernel-request-splitting-2-conversion-gate-runs-config.md#10-gap-accounting-keeps-counts-honest-in-both-directions)).

## See also

- [ADR-067: the kernel splits bundled requests into approved parts](../architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md)
- [Kernel request splitting specification, part 1](kernel-request-splitting.md) (sections 1 to 4: detection, `host.decompose_goal`, schemas)
- [Kernel request splitting specification, part 2](kernel-request-splitting-2-conversion-gate-runs-config.md) (sections 5 to 11: conversion, gate, endings, gap accounting, configuration)
- [Decision kernel container overview](../architecture/components/decision-kernel.md)
- [How to run the decision kernel](../how-to/run-the-decision-kernel.md)
