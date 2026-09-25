---
title: "Duplication analysis and a verified known-issue sweep"
date: "2026-09-25"
time: "15:00"
type: manual
components:
  - build_orchestration
  - commit_guardian
  - ac_store
summary: "A new analysis traces twelve concerns that the package re-implements per site (proving done, workflow shell dispatch, human gates, root and path resolution, hook change sets, commit/push/PR, test running, deploy set, schema validation, ticket status, sub-agent depth, feedback sinks) to the known issues each one caused. Seventeen new known issues record findings reproduced or read in code, and a one-agent-per-issue sweep verified fifteen stale open entries as fixed, updated four as partially fixed, corrected one, and reopened one."
description: "Documentation only. Adds docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md, a follow-up to the worktree consolidation analysis, which finds the same failure shape across all three layers: a shared helper exists but few callers use it, a 'could not check' result reads as a pass, and a known-issue fix lands in one copy while sibling copies keep the bug. Files 17 new known issues (ac-store 7, commit-guardian 5, build-orchestration 5). A sweep that checked each candidate against current code, tests and probes moved 15 entries to resolved/ with their fixing commits, recorded what remains on 4 partially fixed entries, corrected KI-CG-032 (the code is on main and still reproduces) and reopened KI-BP-20260910-1240 (most build writers still emit CRLF). Component index links are updated for the moved files."
commits:
breaking: false
---

## Entry

A new analysis page shows that duplicated worktree creation is one case of a
wider pattern. Twelve concerns are each implemented in several places, and the
known issues they produced share three shapes. A shared helper exists but few
callers use it. A check that could not look reports success. A known-issue fix
reaches one copy while its siblings keep the bug.

The known-issue register gains 17 entries for findings reproduced or read in
code on 2026-09-25, and a per-issue verification sweep brings 21 stale entries
in line with the code: 15 resolved, 4 partially fixed, 1 corrected and 1
reopened.
