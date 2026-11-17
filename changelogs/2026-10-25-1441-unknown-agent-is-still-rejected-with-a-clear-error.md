---
title: Unknown agent is still rejected with a clear error
date: "2026-10-25"
time: "14:41"
type: manual
components: 
  - infrastructure
summary: "A feedback submission from an agent that is not an allowed writer is still rejected, naming the agent and category, and is now logged at WARNING; the error no longer lists the category's allowed writers."
description: "INF-100c-3-i. validate_writer() in templates/scripts/feedback/feedback_validation.py logs the rejection at WARNING and prints 'Phase <agent> is not an allowed writer for category <category>.' The 'Allowed writers: ...' suffix was removed, as the AC's it_requirements ask (information exposure). Anyone who relied on that list in the error should read config/feedback_categories.yaml instead."
breaking: false
---

## Entry
