---
title: "Three GE-120 tickets close with every phase actually run, and the parity check finds what the claims did not"
date: "2026-09-07"
time: "10:50"
type: manual
components:
  - ac_store
  - commit_guardian
  - feedback_collector
summary: "Re-dispatches the six phases that had never run on GE-120 tickets 01, 28 and 30, closes all three on verified evidence rather than on resolved blockers, repairs a placeholder string that fail-closed a documentation gate, and reconciles seven duplicate seam answers plus one missing."
description: "Three tickets whose code was already merged were left open on purpose in the previous change, because phases had been skipped rather than passed. This closes them by running those phases. documentation-verifier on ticket 01 parsed the repaired pipe-delimited contract line and then verified by reading HEAD — stating that method explicitly, the diff algorithm being inapplicable on a branch level with origin/main — confirming the architecture doc documents the could-not-check output naming both the unreachable prerequisite and the unverified scope. pr-reviewer on ticket 28 recovered ticket 36's naming contract from commit 98797e669, the enforcing test file having been deliberately removed as a deferred red baseline, and confirmed _authored_change.py matches it with no surviving functional references to the old names. ac-validator on 28 reversed its own earlier AC-5 block on fresh evidence, reading all 822 lines of the test file and confirming the fault-injection seam test poisons the shared module to prove both consumers degrade together. pr-reviewer on 30 verified its dead-exception-branch finding behaviourally by feeding the CLI a malformed manifest rather than by reading the reordered clauses. ac-validator on 30 confirmed 9 of the 10 tests drive disposable fixture manifests of varying size rather than the installed one, which that AC's coverage note specifically demands because a test pinned to today's manifest passes forever and cannot fail on the day the next self-deriving check is added. Two corrections came out of it. First, pr-reviewer on 30 caught a false claim of mine: I had written that check_ticket_signoff_parity reported clean after fixing the adr-author row, having never re-run it — it was still reporting cross_layer_seam_answer answered_more_than_once, warn-only and exit 0, so nothing contradicted the claim. The stray key is removed, the checker re-run, and the original sentence marked false when written. Second, documentation-verifier on 30 blocked on a bare-brace placeholder hit at commit_guardian.json line 691 — a filename-convention example inside an unrelated check-diagram-naming hook's comment field dating from 2026-06-02, three months before the ticket existed. Because that manifest is the required doc named by the ticket's AC-1, the hit landed on a required doc and the contract says block; the agent declined to waive it and named the remediation as editing the string rather than widening the detector. Applied exactly that: the convention now reads with angle brackets and carries an inline instruction not to restate the rule using braces, since the first attempt at the fix re-triggered the scanner by quoting them. The manifest was re-verified as valid JSON with 61 hooks and the 59/2 change_set_source split intact, and the agent re-dispatched and passed. Running the parity check across all three tickets before making any claim about it — the discipline whose absence produced the correction above — then surfaced two more defects that no phase had reported: ticket 28 carried SEVEN cross_layer_seam_answer keys where exactly one is permitted, the key being test-writer-only while six other agents had written one, two of them during this very session; and ticket 01 carried none at all despite having a completion_manifest, a condition that had gone unnoticed since 2026-08-25 because the check is warn-only. The six strays on 28 are renamed to seam_note, preserving their content rather than deleting it, and ticket 01's is reconstructed from evidence already present in its own comment and explicitly labelled as reconstructed by the closing session rather than attributed to a test-writer that never wrote one. All three tickets now report parity-clean, verified by running the check. Finally, KI-FC-003 is extended to two occurrences: ac-fulfillment-gate is also absent from every allowed_writers list in feedback_categories.yaml, independently verified at zero occurrences alongside ac-validator's zero, against nineteen for pr-reviewer — so both AC-coverage gates record (submit-failed) on every run, which means the two phases whose judgement is most worth capturing are precisely the two the feedback corpus has never received."
breaking: false
---

## Entry

### Closed, with every phase run rather than assumed

| Ticket | AC | Phases re-dispatched |
|---|---|---|
| 01 | `GE-120a-1` | `documentation-verifier` |
| 28 | `GE-120e-1` | `pr-reviewer`, `ac-validator`, `ac-fulfillment-gate` |
| 30 | `GE-120e-2` | `pr-reviewer`, `ac-validator`, `ac-fulfillment-gate`, `documentation-verifier` ×2 |

Epic now stands at **4 done, 33 todo**. AC store: all 457 guardrail-engine records valid.

### Found by checking rather than claiming

- A false "reports clean" claim of mine, caught by `pr-reviewer` actually running the checker.
- A placeholder string from June that fail-closed a documentation gate — remediated at the
  string, not by widening the detector.
- **Seven** `cross_layer_seam_answer` keys on one ticket, and **zero** on another.
- `ac-fulfillment-gate` joins `ac-validator` in `KI-FC-003` — neither can write feedback.
