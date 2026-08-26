---
title: "The 28 stranded learnings were never stranded, and the harvester stops reporting broken runs as clean"
date: "2026-08-26"
time: "11:25"
type: manual
components:
  - knowledge_system
  - infrastructure
summary: "Two harvester failure paths that exited 0 now exit 4 and name what failed. An investigation into the 28 'stranded' knowledge_captured events found the learnings already on disk in nine curated files -- the events are write receipts, not payloads -- so the two ACs specifying their recovery are withdrawn rather than built, and two replacement L1 features are authored in their place."
description: "Three things happened, and the middle one reframes the other two. (1) CODE: scripts/knowledge/harvest_learnings.py swallowed two OSErrors. A run where every destination write failed printed '0 learnings routed: none' and exited 0 -- textually identical to a run with nothing to do -- and a failed state-file save was swallowed with a bare `pass`, so the next run silently re-routed and re-appended every learning. Both now surface: HarvestResult gains write_failures, failed_by_kind and state_persist_failed; the summary names each; and a new exit code 4 outranks 3. Failed writes are NOT added to the idempotency record, so they stay retryable -- the same retention rule INF-400c-2-ii established for unroutable events. A no-op state write (nothing new to record) is deliberately NOT treated as a failure, because doing so raised the exit code to 4 and masked the exit-3 backlog signal on precisely the all-unroutable run that most needs it. Six new tests, five verified red against the unfixed code by reverting only the production file. (2) INVESTIGATION: the 28 knowledge_captured events in debugging/logs/agent_telemetry.jsonl were believed to be stranded learnings awaiting recovery. They are not. All 28 share one key set -- event, timestamp, agent, component, destination, entry_kind -- with no `text` field, because signoff SKILL.md section 7 step 4 specifies a receipt of a write, not a payload. Resolving all 10 distinct destinations found 9 present in the repo at 3.6-23 KB holding real content; the busiest opens 'Captured 2026-06-16 during BO-210 / GE-102', matching event #1 exactly. The learnings were written inline by the agents and were never lost. Recovering the events would have appended 28 content-free placeholders of the form '[agent-assignment-pattern] Learning from ' on top of nine curated files. (3) STORE: INF-400c-5-ii (map the legacy entry_kind vocabulary) and INF-400c-4-ii (carry the 28 into the emission sink) are therefore withdrawn as superseded, not deferred -- both premises are false. Two replacement L1 features are authored under INF-700 with 14 enriched L2/L3 children: INF-700b (a learning an agent has today actually gets written down) and INF-700c (nothing enters the knowledge record that is not real knowledge). The capture path is dead at the source -- signoff section 7 still loads route-learning and capture-learning, both of which have never existed, behind a fail-open -- and emissions went from 25 in June to 1 in August. Four known issues are filed: KI-KM-009 (ADR-034 section 1 asserts the loop has never closed; nine files disprove it, and its rejection of inline capture rests on that premise), KI-KM-010 (the receipt-shaped schema, plus _event_hash keying on `ticket`, a field empty in all 28 records, with 17 of 28 timestamps at day resolution), KI-KM-011 (a valid-JSON non-object sink line crashes with an unhandled AttributeError, and CLAUDE.md's own pre-drive checklist writes 4 of the sink's 33 lines), and KI-ACS-014 (no retired work_status, so a superseded child stays in its parent's covered_by and the parent can never be proved done). NOT IN THIS CHANGE: the harvester's default sink path is still knowledge_emissions.jsonl, which has never existed (INF-400c-4 owns it); the AttributeError crash is filed and specified as INF-700c-1-i but not fixed; and ADR-034's premise correction is recommended, not made."
breaking: false
---

## Entry

Three things, and the middle one reframes the other two.

### The harvester reported broken runs as clean

Two `OSError` branches in `scripts/knowledge/harvest_learnings.py` were swallowed.

A run in which **every** destination write failed printed:

```
0 learnings routed: none
```

and exited **0** — textually identical to a run that had nothing to do, on a code the operator documentation defines as "drained cleanly". Separately, a failed state-file save was caught with a bare `pass`, so the next run re-routed every learning and appended each one to its destination a second time, silently.

Both now surface, with a new exit code:

```
0 learnings routed: none; 2 write failures: 1 adr, 1 claude-md          exit 4
```

`4` outranks `3` — a broken run needs attention before a retained backlog does. Failed writes are **not** added to the idempotency record, so they stay retryable, matching the rule `INF-400c-2-ii` established for unroutable events.

One deliberate exception: when there is nothing new to record, the state write is a no-op, and treating its failure as a failed run raised the exit code to `4` and **masked the exit-3 backlog** on exactly the all-unroutable run that most needs the signal. That case now stays `3`.

### The 28 "stranded" learnings were never stranded

The 28 `knowledge_captured` events on disk were believed to be learnings awaiting recovery. They are receipts.

All 28 carry one key set — `event, timestamp, agent, component, destination, entry_kind` — and **no `text` field**, because `signoff` §7 step 4 specifies a record of a write that already happened. Resolving all 10 distinct `destination` paths found **9 present in the repo**, 3.6–23 KB each, full of real content. The busiest opens *"Captured 2026-06-16 during BO-210 / GE-102"* — matching the first event's timestamp, agent and destination exactly.

Recovering them would have appended 28 placeholders of the form `[agent-assignment-pattern] Learning from ` on top of nine curated files.

### So two ACs are withdrawn, and two features replace them

`INF-400c-5-ii` (map the legacy vocabulary) and `INF-400c-4-ii` (carry the 28 into the emission sink) are **superseded, not deferred** — both premises are false.

In their place, under `INF-700`: **`INF-700b`** — *a learning an agent has today actually gets written down* — and **`INF-700c`** — *nothing enters the knowledge record that is not real knowledge*, with 14 enriched L2/L3 children.

The real defect is that capture is dead at the source: §7 still instructs agents to load `route-learning` and `capture-learning`, neither of which has ever existed, behind a fail-open. Emissions went **25 in June → 2 in July → 1 in August**. The loop did not fail loudly; it went quiet eight weeks ago.

### Filed

| KI | What |
|---|---|
| `KI-KM-009` | ADR-034 §1 says the loop "has never closed"; nine files disprove it, and §2's rejection of inline capture rests on that premise |
| `KI-KM-010` | The receipt-shaped schema, and `_event_hash` keying on `ticket` — empty in all 28 records, with 17 of 28 timestamps at day resolution |
| `KI-KM-011` | A valid-JSON non-object sink line crashes with an unhandled `AttributeError`; `CLAUDE.md`'s own pre-drive checklist writes 4 of the sink's 33 lines |
| `KI-ACS-014` | No retired `work_status`, so a superseded child stays in its parent's `covered_by` and the parent can never be proved done |

### Not in this change

The harvester's default sink is still `knowledge_emissions.jsonl`, which has never existed — `INF-400c-4` owns it. The `AttributeError` crash is specified as `INF-700c-1-i` but not fixed. ADR-034's premise correction is recommended, not made.
