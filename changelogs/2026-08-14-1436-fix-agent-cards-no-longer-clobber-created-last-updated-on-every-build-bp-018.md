---
title: "Fix: agent cards no longer clobber created/last_updated on every build (BP-018)"
date: "2026-08-14"
time: "14:36"
type: manual
components: 
  - build_pipeline
  - precommit_hooks
summary: "Rebuilding the project no longer erases the creation date and last-edited timestamp on every one of the 60 agent reference cards."
description: "Fixes BP-018: generate_card() in scripts/generate_agent_cards.py rebuilt each card frontmatter from scratch, hardcoding created to today and dropping last_updated, which also meant the compare-before-write guard in build_agent_cards() could never match so all 60 cards were rewritten on every run. Fix reads existing created/last_updated off disk (falling back to today only for new cards) and serialises frontmatter via the identical yaml.dump() call used by the transform-doc-frontmatter commit hook, so generated output is a fixed point of the hook's transform. Verified against the real 60 on-disk cards: a no-op rebuild now writes nothing; only cards with genuine AC Assignments changes are regenerated."
breaking: false
---

## Entry
