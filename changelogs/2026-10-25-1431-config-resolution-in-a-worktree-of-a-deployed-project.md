---
title: Config resolution in a worktree of a deployed project
date: "2026-10-25"
time: "14:31"
type: manual
components: 
  - infrastructure
summary: "submit_feedback.py finds its config in the invoking worktree's .leafcutter/ even when the deployed script is a symlink."
description: "INF-100c-1-i. _find_config_root() now anchors on the invoked path (os.path.abspath) instead of Path.resolve(), so a deployed submit_feedback.py that is a symlink to a copy elsewhere no longer follows the link out of the worktree's .leafcutter/ and missing feedback_categories.yaml. Changed: templates/scripts/feedback/submit_feedback.py."
breaking: false
---

## Entry
