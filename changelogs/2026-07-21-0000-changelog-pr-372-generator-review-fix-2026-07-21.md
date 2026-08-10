---
title: "Changelog PR #372 — generator review-fix — 2026-07-21"
date: "2026-07-21"
time: "00:00"
type: manual
components: 
  - ac_store
  - ac_driven_dev
summary: "Fixed generator robustness issues in generate_ticket_from_ac.py: scalar-string components no longer shatter per-character, kebab IDs normalise to underscore graph IDs, unresolvable values warn-once and pass through, the kebab-to-graph-id map loads from a new side-effect-free data module, implemented_by back-references are canonicalised to repo-relative paths via git rev-parse, and source-code extension filtering now covers Go/Rust/MJS and excludes HTML/CSS/shell."
description: "1 commit (PR #372, fix prefix): scripts/ac_store/generate_ticket_from_ac.py and new scripts/ac_store/_component_migration_map.py. Bug Fixes. 10 ACs covered (ACD-1200a-13/14/14-i, TKT-500f-14-ii/15/16/17/17-i/18/18-i). 11 new unit-test files added."
pr: 372
commits: 
  - 439b74007
breaking: false
---

## Entry
