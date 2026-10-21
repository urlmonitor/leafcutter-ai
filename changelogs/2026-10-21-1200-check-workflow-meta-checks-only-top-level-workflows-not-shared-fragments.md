---
title: "check-workflow-meta checks only top-level workflows, not shared fragments"
date: "2026-10-21"
time: "12:00"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "The workflow meta check now looks only at top-level workflow files, so a shared fragment that the build inlines into workflows is no longer refused for lacking a meta block."
description: "Ported from 4af1bd65d (epic branch), without its epic ticket. check_workflow_meta.py's staged-file filter and the check-workflow-meta files: pattern in templates/scripts/commit_guardian/commit_guardian.json now match only direct children of templates/workflows-js/, agreeing with the hook's full scan, which already listed the top level only. Files under templates/workflows-js/_shared/ carry no meta block by design. Three tests added to unit_tests/commit_guardian/test_check_workflow_meta.py: a staged _shared/ module without meta exits 0, a staged top-level workflow without meta is still refused, and the registered pattern skips _shared/ and matches a top-level .js."
breaking: false
---

## Entry
