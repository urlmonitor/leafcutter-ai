---
title: "Kernel retrieval: a growing analysis folder no longer cuts the parent design document while its parts are offered"
status: todo
components:
  - decision_kernel
created: 2026-10-08
depends_on: []
priority: medium
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - decision-kernel
  - retrieval
  - source-cap
  - fairness
  - design-question
last_updated: 2026-10-08
files_touched:
  - kernel/capabilities/retrieval/repository.py
  - config/kernel_config.default.json
  - tests/kernel/retrieval/test_retrieval_sections.py
  - tests/kernel/grounding/test_retrieval_live_misses.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel retrieval: a growing analysis folder no longer cuts the parent design document while its parts are offered

## Actor / Goal
In order that the decision kernel grounds design questions in the document that states the
design, we need `repo.analysis` retrieval to keep a series' parent document in the candidate set
when the folder outgrows the per-source cap. Then a question about the kernel's design sees the
design document itself, not only its later parts and short notes that happen to be dense in the
query's words.

## Context
- **Observed 2026-10-06.** `docs/analysis` has grown to 108 files (58 when the per-source cut was
  designed). For "What fields must a decision record hold?" the cut note read: "234 lower-ranked
  section(s) cut at the source cap of 60 candidates (108 files scanned, max_candidates=60); 48
  matching file(s) had no section offered and 59 more lost sections to a sibling".
  `docs/analysis/2026-09-30-decision-kernel-design.md` is among the 48. Its parts 2 to 6
  (`...-design-2-contracts-registry-config.md` to `...-design-6-tests-phases-risks.md`) are
  offered.
- **Why.** `source_cap()` (`kernel/capabilities/retrieval/repository.py:94-101`) is
  `min(max_candidates=60, max(source_candidate_floor=20, ceil(files * source_candidate_ratio=1.5)))`
  (`config/kernel_config.default.json:109-118`). `_select()` (`repository.py:252-263`) gives every
  file its best section before any file gets a second one. Files are ordered by
  `(not pinned, -score, path)` (:240-249), that is by their best section's score alone. Short
  documents dense in query words outscore the long parent document, so even with one section per
  file the parent is ranked out.
- **Already noted, not ticketed.** `tickets/00_inbox/TICKET-20261006-RetrievalLiveMissesAssertsFairness.md`
  (section "Follow-up") records this as a separate design question: recency, path diversity or
  per-subfolder fairness. That ticket only makes the real-tree replay test assert a fair cut. It
  does not change retrieval, so it does not cover this.
- **The decision needed.** Which property decides what survives the cut when more files match
  than the cap allows:
  - recency (newer analyses first);
  - path or name diversity (one representative per filename series, so `X.md` and `X-2-...md` to
    `X-6-...md` do not take six slots before another series gets one);
  - per-subfolder fairness;
  - or a parent-of-series rule (a series' unnumbered head is offered whenever any of its parts is).

  Each changes what other questions see, so the choice and its trade-offs go into an ADR
  measured against the retrieval benchmark (`tests/kernel/retrieval/benchmark_cases.json`, pinned
  corpus commit `2bb82cf9`, see TICKET-20261001-KernelBenchmarkPinnedCorpus).

## Acceptance Criteria
- [ ] AC-1: An ADR under `docs/architecture/adrs/` records the policy `repo.analysis` uses when
  more files match than the source cap allows. It compares at least recency, series diversity,
  per-subfolder fairness and the parent-of-series rule on the benchmark and on the 2026-10-06
  question, and states the chosen rule and why.
- [ ] AC-2: On the real tree, for "What fields must a decision record hold?", `repo.analysis`
  offers at least one section of `docs/analysis/2026-09-30-decision-kernel-design.md`, and still
  offers `...-design-2-contracts-registry-config.md` within the existing 10-second bound.
- [ ] AC-3: A hermetic test with a synthetic folder of more matching files than the cap holds a
  long parent document outscored by many short documents dense in the query's words. The parent
  is offered under the chosen rule, and the test fails when the rule is disabled.
- [ ] AC-4: The retrieval benchmark's ratchets stay green on the pinned corpus. A ratchet that
  moves is re-recorded only with the justification the ADR gives.
- [ ] AC-5: The per-file fairness the existing tests prove still holds: no file gets a second
  section before every offered file has its first (`TestAFolderOfFortySixFiles` and the
  real-tree replay pass unchanged).

## Test Requirements

```yaml
tests:
  - name: test_parent_of_a_series_is_offered_when_the_folder_exceeds_the_cap
    location: tests/kernel/retrieval/test_retrieval_sections.py
    type: unit
    covers: [AC-3, AC-5]
    description: |
      Synthetic folder with more matching files than source_cap, one long parent doc and many
      short dense docs: the parent is offered; with the rule switched off it is not; per-file
      first-section fairness still holds.
  - name: test_the_kernel_design_parent_doc_is_offered_on_the_real_tree
    location: tests/kernel/grounding/test_retrieval_live_misses.py
    type: integration
    covers: [AC-2]
    description: |
      Real-tree replay of the 2026-10-06 question: the parent design doc and DESIGN_2 are both
      offered from repo.analysis within 10 seconds.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | ADR review | | |
| AC-2 | test_the_kernel_design_parent_doc_is_offered_on_the_real_tree | | |
| AC-3 | test_parent_of_a_series_is_offered_when_the_folder_exceeds_the_cap | | |
| AC-4 | tests/kernel/retrieval/test_retrieval_benchmark.py | | |
| AC-5 | existing section-fairness tests | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Measure the four candidate rules on the benchmark and the 2026-10-06 question; write the
  ADR.
- [ ] Implement the chosen rule in `_select()` or the ordering key, behind a config value if
  the ADR asks for one.
- [ ] Tests above; benchmark run.

## Risk & Safety
- Touches money? No.
- Touches data? No. Read-only retrieval ranking.
- Reversibility: revert the commit; the benchmark shows any regression.

## Out of Scope
- Raising `max_candidates` as the fix. The cap bounds the rerank batch. The ADR may still
  conclude it should move, but only as a measured choice.
- Excluding files or subfolders from `repo.analysis`.
