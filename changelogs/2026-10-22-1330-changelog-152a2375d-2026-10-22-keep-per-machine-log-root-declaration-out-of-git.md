---
title: "Changelog 152a2375d — 2026-10-22: keep per-machine log-root declaration out of git"
date: "2026-10-22"
time: "13:30"
type: manual
components: 
  - build_pipeline
  - infrastructure
summary: "The build now keeps each machine's log-location setting out of version control, so repositories that commit their install no longer pass one machine's paths to other checkouts."
description: "1 commit (152a2375d, fix). build_knowledge_sink_declaration() now ensures config/.gitignore holds a knowledge_sink.json rule (created if absent, appended if missing, never duplicated, skipped in dry-run; a failed write logs a WARNING and does not stop the build). The declaration (.leafcutter/config/knowledge_sink.json, absolute paths by design under ADR-069) is unchanged. Adds AC INF-500d-4-x and test unit_tests/portability/test_inf_500d_4_x.py."
adrs: 
  - ADR-069
commits: 
  - 152a2375d
breaking: false
---

## Entry

The build now writes a `config/.gitignore` rule for `knowledge_sink.json`, so the per-machine log-root declaration stays out of git.

Upgrade note: a copy already committed in a consumer repository needs a one-time `git rm --cached .leafcutter/config/knowledge_sink.json`. The new rule does not untrack a file git already tracks.
