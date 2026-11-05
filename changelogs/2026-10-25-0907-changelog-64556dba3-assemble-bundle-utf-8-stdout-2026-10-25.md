---
title: "Changelog 64556dba3 — assemble-bundle UTF-8 stdout (2026-10-25)"
date: "2026-10-25"
time: "09:07"
type: manual
components: 
  - build_orchestration
summary: "The assemble-bundle command no longer crashes on Windows when the bundle contains characters outside the console code page."
description: "1 commit (fix): assemble-bundle writes the bundle to stdout as UTF-8 regardless of the Windows console code page (BO-2400c-1-xi). Previously a non-cp1252 character crashed it unless PYTHONUTF8=1 was set."
commits: 
  - 64556dba3a1d78377c50b224f83d7b17e93ca742
breaking: false
---

## Entry
