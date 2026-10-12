---
title: "The build reads the Claude Code version correctly again (BP-300d-3-ii)"
date: "2026-10-12"
time: "21:00"
type: manual
components: 
  - build_pipeline
summary: "The build no longer warns that the Claude Code version is unknown when the CLI is installed, and an older CLI below the workflow-script minimum is now actually detected."
description: "build_workflow_scripts() read the last word of `claude --version`, which prints '2.1.294 (Claude Code)', so it saw 'Code)' and treated the version as unknown: every build printed 'Claude Code version unknown. Installing workflow scripts (fail-open).' and the minimum-version gate never fired with the CLI present. It now reads the first dotted version number; output with no version still warns and installs, as before."
commits: 
  - 79eab751a
breaking: false
---

## Entry
