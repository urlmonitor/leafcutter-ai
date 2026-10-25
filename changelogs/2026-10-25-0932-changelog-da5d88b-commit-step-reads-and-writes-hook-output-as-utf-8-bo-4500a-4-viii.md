---
title: "Changelog da5d88b — commit step reads and writes hook output as UTF-8 (BO-4500a-4-viii)"
date: "2026-10-25"
time: "09:32"
type: manual
components: 
  - build_orchestration
summary: Fixed the shared commit step on Windows so hooks that print unusual characters no longer crash it or make it hang.
description: "1 commit (fix). On Windows the shared commit step now reads and writes hook output as UTF-8. Before, a hook printing a non-cp1252 character crashed the step after committing, with no answer and a stale index entry. When the check failed instead, the step hung handing the output to remedy_handoff."
commits: 
  - da5d88b5aa4b90cfef091b49eab56da72e0ace50
breaking: false
---

## Entry
