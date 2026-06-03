---
title: "Fix build system to respect config-driven folder paths complete"
date: "2026-06-03"
time: "13:30"
type: ticket_completion
components: 
  - build_pipeline
  - config_loader
summary: Build system now derives ticket and doc paths from skills_config.json instead of hardcoding them.
description: "Fixed three bugs where build_ticket_lifecycle() hardcoded tickets/ path, build_project_paths_table() ignored config overrides, and template_compiler did not thread config to path table builder. Self-hosting builds now use config-driven paths and agents receive accurate path information."
pr: 37
commits: 
  - cf8f6f6
  - a29519e
ticket: "TICKET-20260603-ConfigDrivenBuildPaths"
---

## Entry
