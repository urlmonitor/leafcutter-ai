---
title: "An untestable acceptance criterion can be marked done, and one with no stated reason no longer slips past CI"
date: "2026-09-22"
time: "11:30"
type: manual
components:
  - build_orchestration
  - testing_quality
summary: "The done-proof gate demanded a '# covers:' tag from every acceptance criterion marked done — including the ones whose own record says a test here would prove nothing. The tag could not exist without writing a fake test to carry it, so real work shipped while the store kept saying todo. Three layers decided this question and all three disagreed; they now share one rule, and the CI layer's habit of exempting any criterion claiming to need no test — whether or not it said why — is closed."
description: "New shared predicate is_covers_tag_waived in scripts/ac_store/_done_proof_phase_helpers.py waives the covers-tag requirement iff test_required is exactly False AND test_rationale is non-empty after stripping. Consulted by all three deciding layers: check_staged_done_proofs (pre-commit, which ran its own static scan and never called the oracle), verify_done_eligible via _handle_no_direct_tests, and check_all_done_acs / check_changed_done_acs (CI, which previously skipped on test_required alone). The change self-funds the GE-127b-1 ratchet by relocating code rather than skipping the gate: done_proof.py 1329 to 1307, check_done_proof.py 663 to 594, both below their own HEAD baselines."
commits:
  - 6ca906e5
breaking: false
---

## Entry

### The shape of the bug

Marking `INF-700c-3` done — a documentation criterion whose own `test_rationale`
explains that a test there would be a grep over prose passing on a document
describing the rule backwards — produced this:

```
[check-done-proof] INF-700c-3: no '# covers: INF-700c-3' or
'// covers: INF-700c-3' tag found anywhere under .
[check-done-proof] exemptions in force: 0
```

The tag the gate wanted could not exist without writing a fake test to carry it.
The only exemption seam available was `config/reachability_exemptions.yaml`,
whose schema is units and capabilities with no runtime entry point — a criterion
id is neither, so using it would have recorded a false statement to buy a pass.
So the documentation shipped and the store kept saying `todo`.

### Three layers, three different answers

| layer | what it did |
|---|---|
| `check_staged_done_proofs` (pre-commit) | ran its **own** static covers-tag scan, never called the oracle, refused outright |
| `verify_done_eligible` (the oracle) | returned "no linked test found", unaware of either field |
| `check_all_done_acs` / `check_changed_done_acs` (CI) | skipped on `test_required is False` **alone**, ignoring `test_rationale` entirely |

The third is a hole in the opposite direction. A criterion claiming
`test_required: false` with **no recorded reason** was being waved through by CI
while pre-commit refused it. So the fix is as much a tightening as a relaxation,
and the tightening is the more important half.

### The rule

A criterion waives the covers-tag requirement **iff** `test_required` is exactly
`False` **and** `test_rationale` is non-empty after stripping. Either half alone
still refuses; `test_required` true or absent is untouched. One predicate, in
one place, consulted by all three layers — three hand-written copies of a
conjunction is how they drifted apart, and that divergence *was* the bug.

### The ratchet was paid, not skipped

The first implementation grew two already-oversized files and `check-file-size`
would have refused it. Rather than reach for a skip, the code was relocated so
both files finish **below** where they started:

| file | before | after |
|---|---:|---:|
| `scripts/ac_store/done_proof.py` | 1329 | **1307** |
| `templates/scripts/commit_guardian/check_done_proof.py` | 663 | **594** |
| `scripts/ac_store/_done_proof_phase_helpers.py` | 260 | 325 (under 400) |

No pre-existing comment or docstring was deleted. What moved was code.

**Worth knowing for next time:** `count_content_lines` strips docstrings before
counting, so relocating a docstring-heavy function buys almost nothing — moving
`is_covers_tag_waived` alone, 30 of whose 36 lines were docstring, netted about
one line once the re-export was added. Only relocating code-heavy functions
moved the number.

### Two tests updated, and why that is not weakening

`test_done_proof_test_required_exemption.py` had two methods pinning the old CI
loosening. They went red, correctly. Each **fixture** gained a real
`test_rationale`; the assertions are untouched. The fixture was incomplete, not
the assertion — each docstring now says so.

### Verification

| check | result |
|---|---|
| the new gate suite | 10 passed |
| `test_done_proof_test_required_exemption.py` | 5 passed |
| `unit_tests/commit_guardian` (done_proof / reachability / 2500 / 2900) | 98 passed |
| `unit_tests/ac_store/` | 691 passed, 3 skipped, 22 subtests |
| `validate_ac_schema.py build-orchestration` | OK, all 1061 valid |
| `check-file-size` at commit time | **Passed** |

All pytest runs under `AC_ENFORCE_STRICT=1` — without it `pytest_ac_enforcement`
downgrades a failure covering a not-yet-done criterion to `xfail`, and the red
baseline for a brand-new one reads as green.

The reachability test drives the real `check_done_proof.py --mode precommit` CLI
as a subprocess and asserts the **process exit code** — the value a `git commit`
actually sees. A test written only against the oracle would have passed while
commits stayed blocked, because the pre-commit path never calls it.

### Still open

`INF-700c-3` itself is still `work_status: todo`. It can be flipped once this
lands; it was deliberately left honest rather than forced through.
