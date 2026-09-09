---
title: "EPIC: What your project says about itself is true, and stays true as the code changes"
type: epic
status: todo
components:
  - ux_prototyping
  - build_pipeline
  - ac_store
created: 2026-09-09
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: What your project says about itself is true, and stays true as the code changes

## Problem

leafcutter ships product-truth machinery — a generator, a validator, and schemas —
but nothing that makes the record it produces trustworthy over time. Four gaps,
each found by inspection rather than by any check:

- A fresh install receives `scripts/` and `schemas/` and **no store**: no README,
  no `index.json`, no scaffold. Validators arrive with nothing to validate.
- `validate_product_truth.py` exits 0 on a zero-artifact store, reporting
  `OK: 0 flows, 0 mock-data, 0 mockups`. A pass over nothing is indistinguishable
  from a pass over everything.
- The store detects only *internal* drift — derived fields against authored ones.
  Nothing ties a claim to `path:lines`, so the record can describe a workflow
  deleted last month and stay green.
- Nothing bounds size. `summary` has no cap, `steps` no limit, `tags` no pattern,
  `component` is free text. Every flow already carries a hand-written short summary
  in `index.json` that diverges from the real one, because the real one was too long.

A fifth was live rather than theoretical: `scan_ac_store.py` offered the
`fern-and-fig` example plant shop as ready backlog work, so a drain could have
dispatched an agent to build a fictional shop inside leafcutter.

## Goal

After this epic, a project that installs leafcutter has a record of what it is and
what it does — honest on day one when it is empty, still correct months later when
it is large. The record cannot drift from the code without someone hearing about
it, example content can never be mistaken for the real product, and the record
never grows past what a person can still review.

## Structure

Five L1s, cut by **failure mode** rather than by activity. "Produce / maintain /
bound size" describes what someone does; these describe what goes wrong, and two of
the five fall outside that list entirely:

| L1 | Failure mode | Tickets |
|---|---|---|
| `UXP-700a` | A new project has no record, or a fake one | 9 |
| `UXP-700b` | An empty or missing check passes as a real one | 8 |
| `UXP-700c` | The record drifts from the code without anyone hearing | 10 |
| `UXP-700d` | Example content poses as the real product | 9 |
| `UXP-700e` | The record outgrows the people who must review it | 8 |
| `UXP-300` | Store layout and one-canonical-dataset-per-entity (re-parented under `UXP-700e`) | 1 |

45 tickets, dependency-ordered `01_` through `45_`.

## Work already landed

Part of `UXP-700d` shipped in `42684dcb` before this epic was generated, and the
generated tickets do **not** reflect it — a ticket's `status` is `todo` regardless
of the underlying AC's `work_status`. Check the AC records before starting any of
these five:

- `UXP-700d-2`, `UXP-700d-2-i`, `UXP-700d-2-ii` — the dispatchability fence is
  **done**: `product` field on the AC schema, `_is_example_content()` in both the
  ready-leaf scanner and the `check_done_proof` template, 19 example records marked.
- `UXP-700d-1` — AC records landed; the `product_root` module and its tests did not.
- `UXP-300` — re-parented only.

## Deferred by a known issue

`UXP-700d-1`'s remaining work, and anything else touching `docs/product-truth/`,
trips `check-eval-staleness`. That gate cannot currently be satisfied: the eval
harness invokes the `claude` CLI as bare `"claude"`, which `subprocess` cannot
resolve on Windows, so every row is scored as an unanswered non-prediction and the
aggregate reports an outage as a 22% quality result. Filed as
`KI-TQ-20260908-0900`; `shutil.which` gets the CLI to launch, after which it
returns non-JSON — likely the `--tools ""` empty argument through the `.cmd` shim.

Resolve that before driving the `docs/product-truth/` tickets, or they will each
stall at the same gate.

## Sequencing

`UXP-700b` (a vacuous check passing as real) is worth taking early regardless of
ticket order: it is the failure that hides the other four. A check that cannot fail
will report the seeding, the drift detection and the size bounds as working
whether or not they are.
