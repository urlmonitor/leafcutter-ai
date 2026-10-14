---
title: "A refused commit is held while the specialist puts the file right, then goes through (BO-3800a)"
date: "2026-10-14"
time: "10:00"
type: manual
components: 
  - build_orchestration
  - supervisor_system
  - commit_guardian
summary: "When check-complexity refuses a commit made by the commit agent, the restructuring specialist is now brought in and the same commit is offered again. This works through /commit as well as inside a build. A commit made directly with git commit is still simply refused, with the refusal's own instructions."
description: "BO-3800a-1, -2. New templates/scripts/commit_guardian/remedy_handoff.py reads the refusing hook's *REFUSAL_RECORD line from stdin and the hook's declaration through the shared _remedy_declarations loader, and prints a status: handoff payload naming the declared specialist, its skills and the demand. It exits 1 with a named reason if the record is missing, empty or not valid JSON, the declaration cannot be read, or the hook has no engage-specialist declaration. The commit agent (templates/agents/commit.md Step 5) and the precommit-autofix skill (new Step 4a.0) now return that payload for an engage-specialist refusal. They no longer try to dispatch a fixer from depth 1, where ADR-019 says such calls are silently dropped, and they never reset, stash or bypass hooks. New templates/workflows-js/commit.js is the depth-0 dispatcher behind /commit (templates/workflows/commit.md). It runs the commit agent, engages the declared specialist at most once on a handoff, then re-offers the same commit without touching the working tree. If the Workflow tool is unavailable, /commit falls back to the commit agent and shows the handoff to the user. Inside a build, the existing BO-3000a/BO-3800b handoff path already holds and re-offers the change. config/guardrail_gates.yaml lists commit.js as a dispatcher with no knowledge-routing step of its own. Tests: unit_tests/workflows/test_bo_3800a_1.py, test_bo_3800a_2.py (shared _bo3800a_support.py) and unit_tests/commit_guardian/test_bo_3800a_2_direct_commits.py, which runs real git commits through the deployed hook. BO-3800a and its children are marked done."
breaking: false
---

## Entry
