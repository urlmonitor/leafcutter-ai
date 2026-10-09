---
title: "Plan: generated documents bounded not judged, and hooks resolve their own repo (GE-127g, GE-118g) — planned work only, no code changes"
date: "2026-10-09"
time: "14:20"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "Planned, not built: this adds only the approved acceptance-criteria plan for letting the doc-length check set aside generated documents within a stated size bound, and for making the ADR numbering tools find their repository correctly, and changes no code or behaviour."
description: "PLANNED WORK ONLY. NOTHING BEHAVES DIFFERENTLY YET: no code, gate or hook changes in this PR, so the doc-length gate still refuses generated documents and the ADR tools still resolve the repository from the directory they were started in. It adds 13 acceptance-criteria records (commit 044459c67, 16 files, all work_status todo, readiness approved) plus one authoring-convention memory file. GE-127g (5 children): the doc-length gate currently refuses generated documents (agent cards, the roadmap mirror, docs/INDEX.md) with a two-for-one removal remedy nobody can act on, because nobody authors them. The records declare set-aside locations as a class with stated grounds (by directory, not filename suffix), require set-aside documents to be reported rather than silently skipped (judged and set-aside counts reported separately), keep the exemption from leaking to hand-authored documents, and keep each set-aside location bounded: every entry declares a ceiling (planned: 10000 lines for the cards directory, 1500 for the roadmap mirror, 2000 for the doc index), a document above it is reported while the commit still completes, and an entry declaring no ceiling is rejected. GE-118g (3 children): check_adr_collision.py and scripts/adr_refs.py resolve the repository from the directory they were started in rather than from what the project declares, so they misreport from anywhere but the repo root (collision pre-flight reads the wrong pending changes; the reference audit walks sibling worktrees from the workspace parent); where no repository can be established both tools must refuse and name what they were asked about instead of returning an empty result. Parents GE-118 and GE-127 gain the new goals in covered_by and amended_by, and are now at 7 of 7 L1 children. WATCH FOR WHEN THIS IS BUILT: replacing the current basename-only excluded_files matching brings the 12 hand-authored README.md files under docs/ into scope for the first time. Two are already over the 300-line limit (docs/agents/README.md at 569 lines, docs/testing/README.md at 342) and are grandfathered by the growth ratchet, so they should not block commits, but they will start being reported; that is intended, not a regression."
commits: 
  - 044459c67
breaking: false
---

## Entry
