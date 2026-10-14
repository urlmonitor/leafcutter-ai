---
title: "Decision assessment never sees the findings research synthesized"
status: todo
components:
  - decision_kernel
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: production_code
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Decision assessment never sees the findings research synthesized

## Actor / Goal
In order for a decision's ranking to rest on what research actually found, the host's synthesized findings must reach option generation and Jev's assessment.

## Context
- **Found:** 2026-10-10, kernel runs `run-13cb4df281c145f1` and `run-15370804bdd84656` (DK-600 build path). Both rankings came out inconclusive: no option met a required criterion, and several scores contradicted the findings (an option scored 0.27 on "test-first" while the findings stated that path runs a test-writer and a red-baseline gate).
- **Cause (read in the code):**
  - Research returns an `evidence_bundle.v1` that carries `findings` (`kernel/capabilities/research/results.py`, `bundle_result`).
  - The decision absorbs a bundle in `kernel/capabilities/decision/loading.py` `_absorb_bundle`. It copies evidence ids, limitations, claim evidence and unknowns, but not `model.findings`.
  - Only a direct `findings.v1` child reaches `_absorb_findings`, which fills `work.cont.findings` and `finding_refs`.
  - So `options_request` (`requests.py`) sends `findings: []`, and the assess batch (`assess.py`, `"findings": json_strings(work.cont.findings)`) sends none to Jev.
- **Related:** memory rule "inconclusive ranking → LLM review"; it may have been compensating for this defect.

## Scope
1. `_absorb_bundle` keeps the bundle's findings the same way `_absorb_findings` does (claims, disagreements, refs, bounded by `MAX_FINDINGS_KEPT`).
2. Tests: a bundle with findings populates `work.cont.findings` and `finding_refs`; `options_request` carries them; the assess batch payload carries them.
3. Re-run one recorded decision (e.g. the DK-600 build-path question) and compare the score spread before and after.

## Out of Scope
- Changing Jev templates or thresholds.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
