---
title: "Planned: the commit-time remedy checks judge the package's committed table, never a stale local copy (GE-132a-4)"
date: "2026-10-12"
time: "23:30"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "Acceptance criterion only, no code: a stale or absent gitignored local remedy table will no longer refuse a correct commit or let a defective committed table pass."
description: "Planned work only; no code changes. New AC GE-132a-4 (L2 under GE-132a, approved by BrainCandy 2026-10-12). The problem: GE-132a-2's validity rule judges the shared loader's merged view, which prefers the gitignored, write-if-absent .claude/precommit-autofix.json. A self-hosted checkout built before GE-132a-2 kept null agents there, so commits touching commit-guardian files were refused on nine checks that the committed table declared correctly, while a defect in the committed table was masked by a correct local copy. GE-132a-4: wherever the canonical manifest exists, the registration-parity and validity legs judge templates/scripts/precommit-autofix.json only. A missing committed table is could-not-check (exit 2, naming the path), never a fallback to the deployed or local copy. Run-time readers (check-complexity's refusal text, the BO-3800 run) keep the shared loader's local-first view unchanged, and docs/reference/remedy-declarations.md will say which table each reader judges. Four arms; arms 1 and 2 (including the absent-table subcase) fail on today's code."
commits: []
breaking: false
---

## Entry
