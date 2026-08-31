# PO learnings — TQ-500 (a passing test shown able to fail) framing

Captured 2026-08-31 (product-owner) authoring a new L0 + 5 L1s in testing-quality
from known issue KI-TQ-010. For BA (L2/L3 decomposition) and IT-PO (enrichment).

## Placement: new L0, not an attachment — and why the search mattered

Searched the whole store before creating TQ-500. Nearest neighbours and why each
was rejected as a host:

- TQ-100 (which tests gate main) — signal/noise in the gate; says nothing about a
  test with no failure mode.
- TQ-300 (tooling has tests at all) — coverage existence, not coverage strength.
- TQ-400 (does the proof still hold later) — presupposes the proof was worth
  something on day one.
- BO-2500c ("tests check the real thing, not convenient fakes") — closest in the
  store, but its subject is fixture realism. The recorded defect had perfect
  fixture realism (real on-disk artifacts, real entry point, explicit
  anti-vacuity assertions) and was still inert.
- BO-2900 ("work counts as done when it is reachable when the product runs") —
  reachability of the code, not sensitivity of the test.

## The FOURTH honesty axis — LOAD-BEARING, do not merge

TQ-400's notes name three axes (BO-2500 mark time / BP-1100 ticket-level during a
drive / TQ-400 over time). TQ-500 is a fourth and is orthogonal to all three: a
test that cannot fail satisfies every one of them perfectly and permanently — it
is present, it passes, the code it names runs, and it will still pass at every
future re-check. Keep the TQ-500 L0 `notes` block intact when amending.

## Non-goal a downstream author will be tempted to reintroduce

Do NOT specify automatic detection of the affected family of work from the text
of a requirement. The source entry is explicit that every candidate signal is
suggestive and none is dependable. The obligation is DECLARED by whoever does the
work (TQ-500a). An L2 that makes classification automatic has reopened the defect.

## The axis that actually found the bug

TQ-500c (per-test results, never one aggregate). In the recorded case three of
four sibling tests objected to the injected fault and the fourth — carrying the
headline clause — did not. A single boolean would have reported "the suite caught
it" and left the inert test in place indefinitely. This is not a presentation
preference; treat it as load-bearing at L2.

## Severity signal is understated at source

The register records 1 occurrence. Three are known, same day, the last two AFTER
the issue was filed and by someone actively looking for the pattern. Do not treat
the recorded count as a rarity measure. Correcting the register was out of scope.

## Handed to the BA as out-of-scope-for-L0/L1

Named mechanisms, field semantics, per-phase contracts, and the specific worked
evidence table all belong at L2/L3. They are deliberately absent from the L0/L1
criteria text and are cited only through the `doc_links` entry pointing at the
known-issues register.

## Field convention (matched TQ-100 / TQ-300 / TQ-400 siblings)

`components` list uses graph ids (testing_quality plus build_orchestration or
ac_store); scalar `component` is `testing-quality`. status: active, req_status:
draft, work_status: todo, readiness: draft, priority: medium, roadmap_phase:
phase_1, origin_agent: BrainCandy, created: 2026-08-31. change_target and
risk_surface set on every record; documentation_triggers non-empty on all five
L1s, so no documentation_rationale needed. validate_ac_schema.py on the folder
reported "OK: all 6 AC YAML files are valid".
