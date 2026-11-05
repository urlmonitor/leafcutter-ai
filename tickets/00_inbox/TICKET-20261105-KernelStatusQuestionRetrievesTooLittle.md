---
title: "Kernel: a \"what is still to be done\" question retrieves the component's backlog, and a run with unresolved unknowns does not report completed"
status: todo
components:
  - decision_kernel
created: 2026-11-05
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
  - synthesis
last_updated: 2026-11-05
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: a "what is still to be done" question retrieves the component's backlog, and a run with unresolved unknowns does not report completed

## Actor / Goal
In order to answer "what is still to be done about <area>" from the kernel alone, we need
retrieval to reach the sources that hold the remaining work (the area's AC store, its
known-issue register and the roadmap), and the run to go back for more evidence, or end
`partial`, when its own synthesis lists what it could not find.

## Context
Observed 2026-11-05 on Windows 11, run `run-b77fc79f09c44cdd`. Kernel code: runtime checkout
`worktrees/leafcutter-runtime` at origin/main `b7b8943bf`. Scope `repository_root` =
`C:/Users/Hendrik/Code/leafcutter/leafcutter-ai`.

Goal (verbatim): "so what is still to be done regarding test quality?". The input's
`context.observations` named the two places the answer lives:
`docs/acceptance-criteria/testing-quality/` and `docs/known-issues/testing-quality.md`.

### Defect 1 - retrieval returns six known-issue excerpts and nothing else
The run went straight to `synthesize_evidence` with six evidence items: five open
testing-quality known-issue files (KI-TQ-007, -011, -005, -20260901-1655,
-20261024-...) and the register's "How this register is stored" section. It returned no AC
from `docs/acceptance-criteria/testing-quality/` (about 200 not-done ACs on origin/main), no
other open known issue (41 are open; 35 were never seen) and nothing from `docs/roadmap.json`.
The observations named the AC store path, and it was still not read. A question about
remaining work cannot be answered from a fixed handful of the best-scoring excerpts.

### Defect 2 - the run reports `completed` although its synthesis lists three unknowns
The host's findings listed three `unknowns`: the not-done ACs, the unseen known issues, and
the roadmap. The kernel turned them into `unresolved: ...` limitations and ended the run
`completed`, with no second research round aimed at them. The host had to read origin/main
itself to answer the user.

### Defect 3 - the stale repository root again (occurrence of an open ticket)
The `repository_root` checkout was 93 commits behind origin/main, so the register line it
read said Open 44 / Resolved 5 (2026-11-01) against the current Open 41 / Resolved 16. The
report did not say its view was old. This is AC-6 of
`TICKET-20261102-KernelDecisionGoalRoutingAndRetrievalTimeout.md`, still open; it is noted
here as a second occurrence, not a new requirement.

## Expected behaviour
1. A goal asking what remains to be done in an area retrieves from that area's AC store
   (not-done records), its known-issue register (open entries) and the roadmap, or says in a
   limitation which of these it could not reach.
2. A path named in `context.observations` is read, or a limitation says why not.
3. When the synthesis returns `unknowns` that a further retrieval could settle, the kernel
   runs one more research round aimed at them before reporting; if they stay unsettled, the
   run ends `partial`, not `completed`.

## Acceptance Criteria
- [ ] AC-1: Given a fixture repository with an AC store, a known-issue register and a
  roadmap for one component, and the goal "what is still to be done regarding <component>?",
  when the run retrieves, then the evidence includes at least one not-done AC record, the
  register's open entries and the roadmap, or a limitation names each source not reached.
- [ ] AC-2: Given `context.observations` naming a directory, when retrieval runs, then
  evidence from that directory is returned or a limitation names the directory and the reason.
- [ ] AC-3: Given a host synthesis whose `unknowns` is non-empty, when the run continues,
  then a second retrieval round is issued with queries derived from those unknowns, and at
  most one such round runs.
- [ ] AC-4: Given unknowns that remain after that round, when the run ends, then its status
  is `partial` and the report lists them; a run with unresolved unknowns is never `completed`.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Suggested direction
- Treat status / "what is left" questions as a known retrieval need with structured sources
  (AC store records filtered by `work_status`, known-issue files by `open-` prefix, the
  roadmap) rather than free-text excerpt ranking; `kernel/capabilities/retrieval/executor.py`
  `select_sources` and `_collect` (`top_k` cap) are where the excerpt count is set.
- Turn caller-supplied paths in observations into explicit locators, as supplied evidence
  ids already are.
- Feed synthesis `unknowns` back as the next round's needs, bounded to one extra round.

## Risk & Safety
- Touches money? No.
- Touches data? No; kernel run behaviour only. More retrieval raises run time; the extra
  round must stay inside `max_active_seconds`.
- Reversibility: code-only, revertible.

## Comments
