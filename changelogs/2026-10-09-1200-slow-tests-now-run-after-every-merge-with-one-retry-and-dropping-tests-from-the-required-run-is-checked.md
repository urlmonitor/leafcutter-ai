---
title: "Slow tests now run after every merge, with one retry, and dropping tests from the required run is checked"
date: "2026-10-09"
time: "12:00"
type: manual
components: 
  - testing_quality
summary: "The slow tests left out of the required pull-request check now run after every merge to main and twice a day, failures get one retry on a fresh machine, and CI refuses any change that drops tests from the required run without a schedule that still runs them."
description: "A new Post-merge suite workflow runs the tests excluded from the required pull-request check after every merge to main and on a 12-hour heartbeat. Only tests that fail the first run are retried, once, on a fresh machine; a test that fails then passes is green but is named in the run summary and the verdict file. A separate verdict job decides the run's conclusion and refuses to report green when the run did not really happen: aborted, truncated, nothing passing, or mostly skipped all count as did not complete. A new check in the lint job refuses any change where the test configuration deselects tests that no automatically triggered workflow runs, including workflows triggered only by tags, jobs switched off by a condition, or a wrapped test step with no failing verdict step after it. This does not yet hold pull requests while the post-merge suite is red; that comes in later work."
---

## Entry
