---
title: "Build orchestration: /plan-feature reads the workspace setup reply from its last line"
date: "2026-10-07"
time: "09:00"
type: manual
components: 
  - build_orchestration
summary: "/plan-feature no longer halts with 'named no workspace directory' when the setup step prints progress lines before its JSON reply."
description: "The worktree setup script answers with one JSON line, and since the stdout fix its progress lines go to stderr, but the agent that runs the setup step reports both streams together, so the workflow still saw progress lines before the JSON and halted every run. The workflow now parses the last non-empty line of the reported output, the script's documented single-line reply, so progress lines on either stream cannot break setup; a reply with no JSON line still halts as before. The change shrinks the oversized workflow file. AC BO-1500a-5-iii."
commits: []
---

## Entry
