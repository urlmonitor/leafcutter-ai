---
title: "A learning waiting for the next run can now be seen by asking"
date: "2026-10-09"
time: "10:00"
type: manual
components: 
  - knowledge_system
summary: "A new read-only `waiting` command lists the learnings still sitting in the sink, so a late-emitted record is visible even when no further work completes. INF-700a-5-ii stays todo: one of its five test descriptors is not yet covered."
description: "One content commit (6e3526c63). Adds a `waiting` subcommand to scripts/knowledge/completion_routing_cli.py, backed by completion_routing.waiting_learnings(). It prints one JSON line {case, waiting, records, note}, exits 0, needs no working directory, and creates and writes nothing: not the sink, state file, marker or lock. The count is the harvester's waiting figure, sink records with text whose hash is not in the state file, not a second counter. An unreadable sink or a missing sink declaration reports waiting as null, never 0. A record already carried by a merged commit still counts until the following run confirms it. Adds unit_tests/workflows/test_inf_700a_5_ii_waiting.py: the surface changes nothing, the count rises on a late record and returns to zero, and the late record is routed exactly once across runs. Documented in docs/reference/knowledge-routing-step.md. INF-700a-5-ii is not flipped to done: its second descriptor, that an unread record is not reported as routed, written or nothing-to-do, has no covers-tagged test asserting those three outcomes."
commits: 
  - 6e3526c63
breaking: false
---

## Entry

A record emitted after a run's routing step read the sink stays in the sink and waits for the
next completed unit of work. Until now nothing let a person see that tail when no further work
completed.

- **New command.** `completion_routing_cli.py waiting` prints the count and names each record.
  It writes nothing and exits `0`.
- **Unknown is not zero.** An unreadable sink or a missing sink declaration reports
  `waiting: null`.
- **Tests.** The surface is checked against a filesystem snapshot before and after. The count
  rises on a late record and returns to zero. The late record reaches its destination once.
- **Docs.** `docs/reference/knowledge-routing-step.md`, in the routing-run recency section.
- **Not done.** INF-700a-5-ii stays `todo`: its second descriptor is not covered.
