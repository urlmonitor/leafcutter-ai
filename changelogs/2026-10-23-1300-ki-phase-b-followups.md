---
title: "Known issues filed: no-op wrong versions, load-sensitive gate verdicts, and PR #1316 leftovers"
date: "2026-10-23"
time: "13:00"
type: manual
components:
  - build_orchestration
summary: "Three known issues from the TQ-500g-2 / TQ-500g-3 drives. KI-BO-20261023-test-breaker-no-op-alterations (medium): test-breaker can prepare a wrong version that changes text but not behaviour, and the runner reports the sound test as a blocking survivor. KI-BO-20261023-gate-verdicts-sensitive-to-machine-load (medium): under two heavy pytest lanes on one Windows machine, mark_done and wrong_version_gate.py finish stop on tests that pass alone, and mark_done prints no reason. KI-BO-20261023-g2-followups (low): three mypy errors in PR #1316's new code and sql-test-writer's stale read-only declaration."
description: "Docs only. Three new files under docs/known-issues/build-orchestration/ (all in the low index bucket; two graded medium) and three register rows; open count 71 to 74. Sites at origin/main 212a126bf: test-breaker.md:140-171, wrong_version_runner.py:171-186, _wvr_verdict.py:44-72; fast_lane.py:564-581, done_proof.py:324-326/:336-375/:1356-1370, _wvr_pytest.py:178-186, wrong_version_runner.py:247-255; wrong_version_runner.py:274, _tq500g2i_standin_pg.py:90, _tq500g2i_review_fixtures.py:76, sql-test-writer.md:29-32. Remediation directions recorded, not applied."
commits:
breaking: false
---

## Entry

Three problems seen while building the wrong-version checks are now recorded as known issues.

The agent that prepares deliberately broken versions of the code sometimes changes something
the code never reads, so a good test looks like it missed the break. Two of the build's checks
also give wrong answers when the machine is busy running other test suites, and one of them
does not say why it stopped. And the last change left three type-checker errors and an agent
description that wrongly says the agent writes no files. Each entry names the affected lines
and the suggested fix; none of the fixes is applied yet.
