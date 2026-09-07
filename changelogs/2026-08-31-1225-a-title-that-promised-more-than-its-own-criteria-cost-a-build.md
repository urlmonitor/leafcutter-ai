---
title: A title that promised more than its own criteria cost a build
date: "2026-08-31"
time: "12:25"
type: manual
components: 
  - build_orchestration
  - agent_telemetry
summary: "BO-2400d-1's title claimed every agent invocation records telemetry, which its own Gherkin never required. A fast-lane coder read the title, concluded a cleanup would regress it, and refused to build."
description: "No criteria, work_status, covered_by or implemented_by changed anywhere; both records remain correctly done and todo respectively. BO-2400d-1 is retitled to match its own conditional criteria. BO-2400c-1-v records that the telemetry half of its blocker was examined and does not hold, with the evidence, so the next run does not re-derive it. The genuine gap - that no criterion requires any lane to emit telemetry at all - is KI-BO-012 and needs its own AC rather than a reset of these."
---

## Entry

A fast-lane run reached `BO-2400c-1-v` (delete the orphaned second runner) and the coder refused to build it. Its reason was careful and its facts were right: deleting `fast-lane-build.js` would regress `BO-2400d-1`, `-1-i` and `-3`, all `work_status: done`, because the only fast-lane telemetry emission lives inside that orphan.

Every supporting fact re-verified true. The live lane contains **zero** telemetry references, the orphan contains **six**, and all three records are `done` with an empty `amended_by`.

The conclusion still does not follow — and finding that out required reading the three records rather than their titles.

**All three are written with a conditional Given/When:**

| | |
|---|---|
| `d-1` | "*When its telemetry **is recorded**,* Then exactly one record is appended…" |
| `d-1-i` | "*Given the sink is unreachable, When an invocation **attempts** to record*…" |
| `d-3` | "*Given telemetry records **exist** for both lanes, When the report is generated*…" |

Not one of them obliges any lane to emit. They specify what the sink does when called, and what the report looks like when fed. And none cites the orphan as its implementation — `d-1` and `d-1-i` cite `scripts/agent-health/agent_telemetry.py`, `d-3` adds `generate_health_report.py`. Those exist and do what the records literally require.

So deleting the orphan regresses no criterion's stated behaviour, and `BO-2400c-1-v` is not blocked by the telemetry family.

### What actually misled the coder

`BO-2400d-1`'s title read:

> Each agent invocation records duration and token counts to the telemetry sink

That is an unconditional claim its own Gherkin does not make. Read the title, and the coder's inference is sound. Read the criteria, and it isn't.

Titles are what scanners, roadmap views and readers surface. An honest record with a dishonest title cost a build, and would have cost every future one that came near it. Retitled to **"A recorded agent invocation carries its duration and token counts"**, which is what the criteria say.

### What was deliberately *not* done

The obvious-looking move was to reset all three records to `todo` on the grounds that fast-lane telemetry is missing. That would have been wrong: it marks three correctly-satisfied records as unfinished, which is not honesty but its opposite.

The real gap is that **no acceptance criterion anywhere requires a lane to emit telemetry.** The BO-2400d family specifies the sink and the report, both conditionally, and nothing feeds them — which is exactly why `BO-2400d-3`'s comparison report can never contain fast-lane data. That is `KI-BO-012`, and it is an *unwritten requirement*, not a false `done`. It needs an AC of its own.

### Recorded where it will be found

`BO-2400c-1-v` now carries the examination in its `amended_by`: the coder's facts, why the inference fails, and that the telemetry half of its blocker is discharged. Without that, the next run re-derives the same refusal from the same true facts.

Its *other* blocker — the 2026-08-18 entry about the `BO-2500d` family — is untouched and was separately resolved when `BO-2500d-1`/`-1-i`/`-3` were amended on 2026-08-18/19.

**Nothing's `work_status` changed.** `BO-2400d-1` stays `done` because it is; `BO-2400c-1-v` stays `todo` because it has not been built yet.
