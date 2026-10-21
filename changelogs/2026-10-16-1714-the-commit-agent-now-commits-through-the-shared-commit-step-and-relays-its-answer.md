---
title: The commit agent now commits through the shared commit step and relays its answer
date: "2026-10-16"
time: "17:14"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
  - llm_authoring
summary: "The commit agent now hands every commit to the shared commit step and passes that step's answer back unchanged, instead of staging and committing by hand."
description: "1 commit (926f7775, BO-4500a-5-v). templates/agents/commit.md runs the shared commit step once and relays its answer verbatim in a {status, commit_answer, earlier_answers} envelope; handoff keys are copied to the top level only when commit_answer.handoff is non-null, so commit.js and the build phase loop read the reply as before. Removed: the test-process kill, the git stash recipe, the hardcoded Co-Authored-By footer and model names, and the Agent tool. A caller-supplied message and trailer are passed as given. docs/agents/cards/commit.card.md regenerated; two new test files added."
commits: 
  - 926f7775091907317ac947133f119a3b64239461
breaking: false
---

## Entry
