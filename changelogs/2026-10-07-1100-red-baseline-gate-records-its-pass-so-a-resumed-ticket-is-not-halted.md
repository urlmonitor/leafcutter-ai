---
title: The red-baseline gate records its pass and a resumed ticket reuses it
date: '2026-10-07'
time: '11:00'
type: manual
components:
- build_orchestration
- testing_quality
summary: A passing red-baseline gate now writes a red_baseline_gate line into the
  ticket, and a later run reuses it instead of halting a ticket whose coder already
  turned the tests green.
description: 'heavy_lane_gate takes --ticket and records {passed, recorded_at, head,
  source_ac, red} as one frontmatter line on a pass (TQ-500f-3-ii). A resumed run
  reuses the record without running pytest when the source_ac matches and every recorded
  red test is still newly added; otherwise the reader runs as before. When the new
  tests are green and no record applies, the halt is classified green_at_baseline
  and its message says to set the coder phase not_needed and name the commit that
  delivered the behaviour. The record is written by the gate only, never by an agent.'
breaking: false
created: '2026-10-07'
last_updated: '2026-10-07'
status: active
---
## Entry
