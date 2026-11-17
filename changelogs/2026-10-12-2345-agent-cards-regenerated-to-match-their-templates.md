---
title: "Agent cards regenerated to match their templates"
date: "2026-10-12"
time: "23:45"
type: manual
components: 
  - documentation_system
  - agent_registry
summary: "The committed agent cards are brought up to date with what the build generates from the current templates, so builds stop rewriting them in every worktree."
description: "Generated output only; no template or code change. docs/agents/cards/*.card.md (45 cards) were behind the card generator since AR-300 moved each agent's skills and sub-agents into its template's declaration: cards lacked the Skill tool row, showed old signoff modes, and omitted the written conditions on conditional skills. Every build in a fresh worktree therefore regenerated these 45 files, which leaked into unrelated commits and blocked three fast-lane runs on 2026-10-12 (the reviewer correctly refused the churn). This commit is the build's own output from origin/main 21672f15, produced by python scripts/build.py --target-dir on a clean worktree. docs/INDEX.md also changes: the pre-commit doc-index transform re-sorts two rows on commit, because the build and that hook sort them differently."
commits: []
breaking: false
---

## Entry
