---
title: "Changelog 9d2a38be6 — the fast lane reads its wrong-version step JSON and runs every script from the workspace"
date: "2026-10-25"
time: "01:38"
type: manual
components: 
  - build_orchestration
summary: "The fast lane no longer halts at the wrong-version list step when a log line precedes the JSON, and its scratch and knowledge-routing steps run the workspace install, not the parent one."
description: "One commit (9d2a38be6, fix). wvStep now takes the last stdout line that parses as a JSON object and, on failure, halts quoting the received reply instead of null; the scratch-item and knowledge-routing commands name their script by the workspace absolute path (BO-4300a-1-ib). The eleven duplicated release-on-halt dispatches in fast-lane-ship.js were collapsed into one helper (releaseClaimed) to meet the file size ratchet. Found by /fast-lane-build FIN-100c-15. New AC BO-2400f-3-vii."
adrs: []
commits: 
  - 9d2a38be6
breaking: false
---

## Entry
