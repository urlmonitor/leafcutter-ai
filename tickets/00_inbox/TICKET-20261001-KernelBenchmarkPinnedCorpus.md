---
title: "Kernel: the retrieval benchmark scores a pinned corpus, not the live checkout"
status: in_progress
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - retrieval
  - benchmark
last_updated: 2026-10-01
agents:
  python-coder: needed
  commit: needed
---

# Kernel: the retrieval benchmark scores a pinned corpus, not the live checkout

## Actor / Goal
In order to keep the retrieval benchmark's ratchets meaningful while other sessions add documents, we need it to score the files of one recorded commit, so that only ranking code and parameters move its results and new content enters only through a deliberate re-pin.

## Context
- **What broke.** At `feature/decision-store` @ 19c2ba96 (the merge of #977), the benchmark failed 6 subtests in three cases: `goal5_how_kernel_stores_decisions`, `decision_records_existing_patterns` and `lessons_approval_provenance`.
  - The failures were identical on Linux at CI's checkout path and on Windows.
  - No ranking code had changed. Ablation showed that the branch's new documents and modules displaced the must-haves: ADR-059..061, the file-and-reuse how-to, `kernel/memory/`, and design-2's new "As built (decision store)" section.
  - They were genuine answers, but two of the cases could only have gone green by editing their round E baselines.
- **Decision (user, 2026-10-01):** pin the benchmark's corpus. This is standard test-collection practice: a fixed corpus plus queries and judgements. Docs-only PRs from any session can then no longer break the benchmark.
- **What it replaces.** The harness's git-ignored filter from #977 is removed, because the pinned archive holds only tracked files.
  - Production retrieval is unchanged; it is covered by TICKET-20261001-KernelRetrievalHonourGitignore.
  - That ticket's out-of-scope note, which says the harness reads the git file list, is now outdated.

## Scope (no acceptance criteria by user decision)
- **Pin.** A top-level `corpus_commit` in `tests/kernel/retrieval/benchmark_cases.json`, set to `2bb82cf98df721c489d38c1fc52c638cffaced20`.
  - That is #977's head, where the `current` values were recorded.
  - All assertions, round E (`baseline`) and round F (`current`), run on that corpus.
- **Corpus.** The pinned tree is materialised once per test session with `git archive` into `<temp>/corpus`, a neutral name.
  - Only files under the configured sources' roots are extracted, which also keeps Windows paths short.
  - Code and config (sources, parameters, deny globs) come from HEAD.
- **Availability.**
  - A missing pin skips locally, with the `git fetch` command in the message.
  - Under CI (`CI` or `GITHUB_ACTIONS` true), a missing pin fails, so the ratchet cannot go silent.
- **CI.** The "Test suite (pytest)" job fetches only that commit before pytest: `git fetch --no-tags --depth=1 origin <sha>`, with the SHA read from `benchmark_cases.json`. The checkout stays at `fetch-depth` 1.
- **Re-pin procedure.** It is documented in the harness module docstring (RE-PIN):
  1. Change `corpus_commit`.
  2. Run `python -m tests.kernel.retrieval.benchmark_support` at CI's checkout path; it prints the values to record.
  3. Re-record each case's `current`.
  4. Treat any round E break as an explicit, documented decision.
- **Revert.** The uncommitted re-record of `decision_records_existing_patterns` and its new must-have are reverted. New decision-store cases arrive with a later, deliberate re-pin.
- **Tests:**
  - a missing pin skips locally and fails under CI;
  - the corpus holds only the pinned commit's files;
  - the pin is a full SHA.

## Out of Scope
- **Production retrieval's file policy:** TICKET-20261001-KernelRetrievalHonourGitignore.
- **New cases or must-haves for the decision store:** they come with the next deliberate re-pin.
- **A per-machine cache of the materialised corpus.** On Windows, on-access scanning makes the first read of freshly extracted files slow, about one extra minute per session. A cache keyed by SHA is a possible follow-up.

## Risk & Safety
- **Touches money?** No.
- **Touches data?** No. The test harness and CI only.
- **Reversibility:** revert the commit.
- **The pin must stay fetchable from `origin`.** If #977 is squash-merged, 2bb82cf9 is not reachable from main. In that case, re-pin to the commit main gets for it and follow the re-pin procedure: re-record `current` if that tree differs.

## Sign-offs
- [ ] python-coder
- [ ] commit

## Comments
