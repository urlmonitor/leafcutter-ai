---
title: "Four commit-guardian gates that reported success while seeing nothing"
date: "2026-09-14"
time: "15:19"
type: manual
components:
  - commit_guardian
  - build_pipeline
  - roadmap
summary: "Fixed four automated safety checks that had been passing on every commit without actually checking anything, and confirmed the fix by catching a real problem the checks had been missing."
description: "1 commit (cb77b8069). Category: Bug Fixes. Fixed clean-mode's workflow sweep (a doubled path segment meant the target directory never existed, so orphaned workflows were never removed), a ticket sign-off gate that silently skipped one of its six checks on every commit (agent registry loaded 0 entries before the fix, 60 after), the mypy CI job (a git pathspec pattern excluded every top-level script including build.py itself, so the job reported success while type-checking nothing), and the roadmap schema validator (never validated anything; the schema itself had to be extended in the same commit or the repo's own roadmap.json would have become uncommittable). Fixing the sign-off gate immediately surfaced a test fixture that had only passed because the check it exercises was being skipped. A fifth known gap (the glossary-coverage detector) is deliberately not included -- its file already exceeds the project's file-size limit, so fixing it requires a refactor rather than a quick patch."
commits:
  - cb77b8069
breaking: false
---

## Entry
