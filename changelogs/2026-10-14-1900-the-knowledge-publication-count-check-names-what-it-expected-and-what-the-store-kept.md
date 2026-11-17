---
title: "The knowledge publication count check names what it expected and what the store kept"
date: "2026-10-14"
time: "19:00"
type: manual
components: 
  - knowledge_management
summary: "The count check that guards a knowledge publication now expects the number of distinct relationships, reports expected and kept figures for nodes and relationships in the sync result, and on a shortfall fails naming each mismatched kind with both figures."
description: "After a publication stores its generation, a count check compares what the store kept against what was expected. It used to fail with a bare 'generation count validation failed' and report nothing on success. The expected relationship count is now the number of distinct relationships left after identical copies are collapsed, which is what the store keys on, so a repeated entry in a source record no longer fails every publication. The figure is never taken from what the store reports. On success, python -m knowledge sync returns counts with expected and kept for nodes and for relationships; counts is null when the generation was already ready and nothing was built. On a shortfall the publication fails with a message naming each mismatched kind, for example 'relationships expected 28814 kept 28813', the new generation is marked failed, and the previously active generation stays active. The how-to for running knowledge retrieval describes the collapse diagnostics, the counts and the failure message."
---

## Entry
