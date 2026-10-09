---
title: "Planned: every guardrail refusal says what happens next, and a complexity refusal summons a restructuring specialist (GE-132, INF-800f-1, BO-3800)"
date: "2026-10-09"
time: "22:00"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "Acceptance criteria only, no code: they plan that each commit check declares what to do when it refuses, and that a complexity refusal hands the work to a new restructuring-specialist agent."
description: "Planned work only; no code changes. New AC records: GE-132 (L0), GE-132a (L1), GE-132a-1, -2, -3; INF-800f-1 (restructuring-specialist agent); BO-3800a-2, b-3, c-2, d-3. GE-132a-1 requires every pre-commit judgment check to have a remedy declaration in precommit-autofix.json, read through one shared loader that falls back to the package seed for old installs, and renames the stale check-ac-limits rule to check-ticket-ac-limits and removes check-docstrings. GE-132a-2 gives every declaration a disposition (author-clears, mechanical-autofix or engage-specialist); check-complexity is engage-specialist. GE-132a-3 makes the complexity refusal state the score, the ceiling and the declared next step, identically for every committer. INF-800f-1 adds the restructuring-specialist agent, which applies the complexity-reduction skill for complexity demands. BO-3800a-2, b-3, c-2 and d-3 make a drive or interactive commit that hits an engage-specialist refusal engage that specialist once with a brief naming file, function, score and ceiling, then re-judge at full strength. Amended with BrainCandy's approval: BO-3800a, b, c criteria; BO-3800b-3 criteria; GE-132a-3 and BO-3800a-2 depends_on; BO-210a-2 criteria drop the two stale hook ids. All records are draft or todo; 27 planned tests."
commits: []
breaking: false
---

## Entry
