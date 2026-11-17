---
title: "Knowledge-durability requirements reopened: the code exists but nothing runs it"
date: "2026-10-08"
time: "19:00"
type: manual
components: 
  - knowledge_system
summary: "INF-700a-5 and its three sub-requirements go back from done to todo. The modules they name are tested but are not deployed and no completion path calls them, so the behaviour does not run in production."
description: "One content commit (1691c82ec), AC store only. Flips work_status done -> todo on INF-700a-5, INF-700a-5-i, INF-700a-5-ii and INF-700a-5-iii; no other field changes. The implemented_by modules scripts/knowledge/completion_routing.py and completion_routing_state.py are referenced only by each other and their tests: they are in no build deploy list and none of build-epic.js, fast-lane-ship.js or quick-fix.js calls them. The ACs return to done when the wiring lands."
commits: 
  - 1691c82ec
breaking: false
---

## Entry

INF-700a-5 says a routed learning must survive the removal of the working directory it was
written in. Its code exists and its tests pass, but nothing in production uses it: the two
modules are not deployed by the build and no completion path calls them. The four ACs were
marked done on the strength of tests that prove the modules work in isolation.

- **Reopened**: INF-700a-5, INF-700a-5-i, INF-700a-5-ii, INF-700a-5-iii (`done` to `todo`).
- Nothing else changed. Wiring the modules in is follow-up work.
