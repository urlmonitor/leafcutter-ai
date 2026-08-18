---
title: "Fix plan-feature pause persistence and dropped edit feedback"
date: "2026-08-17"
time: "18:42"
type: manual
components: 
  - ac_driven_dev
summary: "A paused /plan-feature run can now actually be resumed, and choosing edit keeps the feedback you typed instead of silently discarding it."
description: "Single commit c6087fae9 fixes two defects in templates/workflows-js/plan-feature.js: pauseAtGate now reads back the pause record before reporting a durable pause, returning a new pause_persist_failed status (recognised at all four gate call sites) when the write cannot be confirmed instead of claiming a resumable pause that does not exist; applyAnswerByType now carries the feedback field through so a resumed edit answer reaches the re-dispatched author instead of running with empty feedback. Adds two tests to unit_tests/workflows/test_bo_2300_pause_resume.py covering both fixes."
commits: 
  - c6087fae9
breaking: false
---

## Entry
