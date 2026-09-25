---
title: "A double-wrapped worktree-facts reply is unwrapped instead of dropped"
date: "2026-09-25"
time: "09:00"
type: manual
components:
  - build_orchestration
  - worktree_manager
summary: "repoFactsCall now unwraps a reply that is itself a complete {output, exit_code} envelope nested inside the outer envelope's output field, instead of returning that inner envelope as if it were the facts object. Every /build-feature epic run had aborted in Phase 0 with abort_reason worktree-base-unavailable, even though scripts/worktree_repo_facts.py returned correct JSON, because the extra nesting level made every expected field read as missing. A plain facts object is still returned unchanged, and input that cannot be parsed at either level still returns null so the guard keeps refusing rather than guessing a worktree location."
description: "Covers BO-4000d: facts read for the drive's worktree survive a reply nested one level too deep. Root cause: repoFactsCall parsed the agent's reply once. When the agent returned a complete {output, exit_code} envelope inside that envelope's own output field, the parse yielded the envelope instead of the facts, so every field read as missing and each /build-feature epic run aborted with worktree-base-unavailable having built nothing. The parse now unwraps one further level when the result is itself an envelope; a plain facts object is returned unchanged, and unparseable input still returns null so the guard still refuses rather than guessing a location. Reproduced twice on 2026-09-25 (runs wf_6d6f8dda-97e and wf_f898fd1a-412) against EPIC-TruthfulProjectRecord before the fix. A new regression test, unit_tests/workflows/test_bo4000d_facts_envelope_depth.py, exercises both the double-wrapped and correctly-shaped reply shapes plus the unparseable-input refusal path."
commits:
breaking: false
---

## Entry

`/build-feature` epic runs were aborting in Phase 0 with `abort_reason
'worktree-base-unavailable'` and building nothing, even though
`scripts/worktree_repo_facts.py` returned correct JSON for both the
`worktree-facts-resolved` and `worktree-base` reads. The reporting agent
relaying those reads was answering one level too deep — the value it put in
the envelope's `output` field was itself a complete envelope
(`{"output": "<raw stdout>", "exit_code": 0}`) rather than the raw stdout —
so `repoFactsCall`'s single parse yielded the inner envelope instead of the
facts object, and every expected field read as missing.

`repoFactsCall` now unwraps one further level when the parsed result is
itself an envelope shape. A plain facts object is returned unchanged, and
input that still cannot be parsed as facts after that unwrap returns `null`,
so the guard keeps refusing to proceed rather than guessing a worktree
location.
