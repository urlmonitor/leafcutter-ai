---
title: "The knowledge reference states which records are eligible and what the waiting count means"
date: "2026-09-22"
time: "12:00"
type: manual
components:
  - knowledge_system
  - documentation_system
summary: "A reader judging whether the knowledge loop works had the artefacts — a sink, a waiting count, a set of destinations — but no stated rule to read them against. The reference now gives the eligibility rule, defines the waiting count, lists the exit codes, and records what was decided about the 28 textless records, with every figure checkable against the artefact it names."
description: "One new section, §5, in docs/architecture/agent_knowledge_system.md: eligibility rule, waiting count, exit codes, and the disposition of the 2026-08-26 retained corpus. Sections §1-§4 and everything below are untouched, belonging to INF-700b-4 and INF-700b-5. Two figures the AC quoted no longer reproduce and were corrected against the artefacts: the corpus end date is 2026-08-12, not an unqualified 2026-08, and destination sizes now span 3,608 B to 40,100 B rather than the audited 3.6-23 KB. The AC's citation of harvest_learnings.py line 409 is stale — INF-400c-5 moved default-sink resolution to sink_resolution.py's resolve_default_sink()."
commits:
  - 1055cbb3
breaking: false
---

## Entry

### What a reader could not find out

The loop exposes two things people read to judge whether it is working: the
content of a knowledge surface, and the count of knowledge waiting to be
written. Neither had a stated rule behind it. You could read the number and not
know what it counted.

### The rule, stated as a rule

A record is eligible to be written only if it carries non-empty `text`. A record
without it is **ineligible** — not deferred, not outstanding.

That framing is deliberate and the AC insisted on it. Describing the 28 retained
records as "excluded" without stating the general rule invites the next reader to
add a second exclusion list; stating the rule means the disposition of those 28
follows from it rather than being a special case.

The waiting count is then exactly: records carrying non-empty text that have not
yet been written. Two things zero a contribution — no text, or already written —
and nothing else adjusts the figure. The section says explicitly that this counts
**records**, not agent runs, so it is not summed with the capture-health report.

### Two of the AC's own figures no longer held

The AC's closing clause is that every claim be checkable against the artefact
named, so nothing was copied from it on trust. Two did not survive that:

| claim | AC | measured |
|---|---|---|
| corpus date range | "2026-06-16 to 2026-08" | **2026-08-12T12:13:00Z** |
| destination sizes | 3.6–23 KB | **3,608 B – 40,100 B** |

`docs/acceptance-criteria/ac-store/PROJECT_CONTEXT.md` has grown well past the
audited ceiling since 2026-08-26. The document gives the measured range and names
the outlier rather than restating a stale closed interval as fact.

Independently re-checked before the doc was staged: that file is 40,100 B;
`git log --all -- memory/feedback_itpo_bo1700_worktree_gate_parity.md` returns
nothing, confirming the tenth destination has never been committed; and
`resolve_default_sink()` sits at `scripts/knowledge/sink_resolution.py:95-105`.

### A stale citation, corrected

The AC points at `harvest_learnings.py` line 409 for the default sink. That line
is gone — `INF-400c-5` split the file on 2026-09-14, moving CLI parsing to
`harvest_cli.py` (`--sink` defaults to `None`) and resolution to
`sink_resolution.py`. That function prefers the build-time
`config/knowledge_sink.json` declaration and only falls back to the literal
`debugging/logs/knowledge_emissions.jsonl`. The section cites what is there now,
and warns against reading that fallback as "the sink" — a built install's
declaration can point elsewhere.

### Doc length: one line of margin

| | before | after | limit |
|---|---:|---:|---|
| lines | 225 | **299** | 300 |
| sections | 8 | 9 | 25 |

Measured with `_doc_length_ratchet.count_lines_and_sections`, the function the
gate itself calls. `INF-700b-4` and `INF-700b-5` both amend this same document
and are both still `todo`; neither can add a line without crossing. Flagged
rather than trimming another criterion's content to make room.

### The criterion is still todo, deliberately

`INF-700c-3` is `test_required: false`, and the done-proof gate demanded a
`# covers:` tag that could not exist without writing a fake test to carry it. The
store was left honest rather than forced through. `BO-2500a-1-ii` fixes the gate;
once that lands this can be flipped.
