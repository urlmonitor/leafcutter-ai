---
title: Feedback config is found from the source repo, and a missing config names every path checked
date: "2026-11-16"
time: "13:00"
type: manual
components: 
  - infrastructure
summary: "submit_feedback.py run through the source repo's scripts/feedback shim falls back to leafcutter-ai/config/feedback_categories.yaml, and when no copy exists the error lists every absolute path it tried."
description: "INF-100c-2, INF-100c-4. In the source repo scripts/feedback/ is the build shim into .leafcutter/scripts/feedback/, so the script looked only in .leafcutter/config/ and never in the repo's own config/. It now looks in the deployed config first, as before, then in config/ two levels above the invoked script path. When neither can be read it prints one 'Checked path: <absolute>' line per location tried. The sink declaration lookup is unchanged. Changed: templates/scripts/feedback/submit_feedback.py. Tests: unit_tests/feedback/test_inf_100c_2_4_source_repo_config.py."
breaking: false
---

## Entry
