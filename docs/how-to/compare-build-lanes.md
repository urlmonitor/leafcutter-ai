---
title: "How to generate and read the build-lane comparison report"
description: "Step-by-step guide to generating and interpreting the fast-lane vs heavy-pipeline cost and time comparison report from agent telemetry data."
type: how-to
category: how-to
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
related_docs:
  - docs/reference/build-telemetry.md
  - docs/how-to/fast-lane-build.md
  - docs/how-to/choose-build-path.md
  - docs/architecture/components/build-orchestration.md
---

# How to generate and read the build-lane comparison report

The build-lane comparison report answers the question: "Is the fast lane actually
faster and cheaper than the heavy pipeline, and by how much?" It reads the agent
telemetry sink (`debugging/logs/agent_telemetry.jsonl`) and groups every recorded
invocation by the `lane` field each phase agent wrote at emission time. For each
lane it computes invocation count, total and average duration, and total and
average token consumption — giving you a side-by-side cost and time comparison
across all lanes that have been used.

This guide covers three tasks:

1. [Generating the report](#1-generating-the-report)
2. [Reading and interpreting the metrics](#2-reading-and-interpreting-the-metrics)
3. [Edge cases and what they mean](#3-edge-cases-and-what-they-mean)

---

## Prerequisites

Before you begin, confirm the following:

- **The telemetry sink exists and has data.** Agent phase completions append
  records to `debugging/logs/agent_telemetry.jsonl`. If no tickets have been
  driven yet, the sink will be absent or empty (see [Edge cases](#3-edge-cases-and-what-they-mean)).

- **Python 3.9+ is available.** The report function is in the standard library
  only — no third-party packages are required for the comparison report itself.

- **You are running from the repo root.** The default sink path
  (`debugging/logs/agent_telemetry.jsonl`) is relative to the repo root. Pass
  an explicit absolute path when calling from a different working directory.

---

## 1. Generating the report

The comparison report is produced by the `build_lane_comparison_report` function
in `scripts/agent-health/generate_health_report.py`. There is no standalone
CLI wrapper for this function — you either call it directly from Python or read
the underlying JSONL file yourself.

### Option A — Python API (recommended for scripting)

```python
from pathlib import Path
from scripts.agent-health.generate_health_report import build_lane_comparison_report

sink = Path("debugging/logs/agent_telemetry.jsonl")
report = build_lane_comparison_report(sink)

# report is a dict keyed by lane name, e.g.:
# {
#   "fast": {
#     "count": 14,
#     "total_duration_ms": 18200,
#     "avg_duration_ms": 1300.0,
#     "total_tokens_in": 7000,
#     "total_tokens_out": 4200,
#     "total_cache_read_tokens": 3500,
#     "avg_total_tokens": 1050.0,
#   },
#   "heavy": {
#     "count": 6,
#     "total_duration_ms": 42000,
#     "avg_duration_ms": 7000.0,
#     ...
#   },
# }
```

Pass an absolute path to avoid working-directory dependence:

```python
sink = Path("/home/henzeh/projects/myproject/debugging/logs/agent_telemetry.jsonl")
report = build_lane_comparison_report(sink)
```

The return value is a plain dict — print it, format it as a table, or pass it to
a downstream analysis script. If the sink is absent or empty the function returns
`{}` without raising.

### Option B — Read the raw JSONL directly

Each record in the sink is a JSON object on a single line. You can inspect the
raw data with any JSONL reader:

```bash
python -m json.tool --no-indent debugging/logs/agent_telemetry.jsonl
```

Or filter to a specific lane:

```bash
grep '"lane": "fast"' debugging/logs/agent_telemetry.jsonl
```

Each record has the following fields:

| Field | Type | Description |
|---|---|---|
| `lane` | string | Build lane the agent was invoked under (e.g. `"fast"`, `"heavy"`) |
| `agent` | string | Agent identifier (e.g. `"python-coder"`, `"pr-reviewer"`) |
| `duration_ms` | int | Wall-clock milliseconds from invocation start to completion |
| `tokens_in` | int | Input tokens consumed in this invocation |
| `tokens_out` | int | Output tokens generated in this invocation |
| `cache_read_tokens` | int | Tokens served from the prompt cache (not billed at full rate) |
| `ts` | string | ISO-8601 UTC timestamp written by the emitter |
| `unit_id` | string | Optional identifier for the unit of work (e.g. AC id or ticket slug) |

---

## 2. Reading and interpreting the metrics

`build_lane_comparison_report` produces one aggregate sub-dict per lane. Each
sub-dict has seven numeric fields. This section explains what each field means
and how to compare lanes side by side.

### `count` — invocation volume

```
fast["count"]  = 14
heavy["count"] = 6
```

The number of agent invocations recorded for this lane. A high count relative to
the other lane means this lane is being chosen more often by the routing logic.
Comparing counts tells you the lane-selection ratio, not per-invocation efficiency
(use the `avg_*` fields for that).

### `total_duration_ms` and `avg_duration_ms` — time per invocation

```
fast["avg_duration_ms"]  = 1 300 ms
heavy["avg_duration_ms"] = 7 000 ms
```

`avg_duration_ms` is the single most important time metric. A lower value means
the lane completes faster on average. The fast lane should have a materially lower
`avg_duration_ms` than the heavy pipeline because it makes fewer LLM round-trips
per unit of work.

Use `total_duration_ms` only when you need to compare total elapsed wall-clock
time across all recorded invocations (useful for estimating drive cost, not for
per-AC comparisons).

**Interpretation rule:** "Time per unit of work" = `avg_duration_ms`. Lower is better.

### `total_tokens_in`, `total_tokens_out`, `total_cache_read_tokens` — token volumes

These three fields represent aggregate token volumes across all invocations in the
lane. Use them to understand the raw traffic volumes, but they scale with `count`
— a lane with twice as many invocations will naturally have higher totals even if
each invocation is cheaper.

| Field | What it represents |
|---|---|
| `total_tokens_in` | Prompt tokens sent to the model across all invocations |
| `total_tokens_out` | Completion tokens received across all invocations |
| `total_cache_read_tokens` | Tokens served from the cache across all invocations |

A high `total_cache_read_tokens` relative to `total_tokens_in` signals that
context reuse is working well — cached tokens are cheaper than freshly processed
input tokens, so high cache utilization lowers cost per invocation.

### `avg_total_tokens` — cost per invocation

```
fast["avg_total_tokens"]  =  1 050
heavy["avg_total_tokens"] = 12 400
```

`avg_total_tokens` is the mean of `(tokens_in + tokens_out + cache_read_tokens)`
per invocation. It is the single most important cost metric. A lower value means
each invocation of this lane consumes fewer tokens on average.

The fast lane should show a materially lower `avg_total_tokens` than the heavy
pipeline because it uses simpler prompts, fewer agent hops, and less accumulated
context per AC.

**Interpretation rule:** "Cost per unit of work" = `avg_total_tokens`. Lower is cheaper.

### Side-by-side reading template

When comparing two lanes, read the metrics in this order:

1. **Was the fast lane chosen often enough to be meaningful?**
   Check `fast["count"]` and `heavy["count"]`. If the fast lane has fewer than
   5 invocations the averages may not be stable yet.

2. **Is the fast lane actually faster?**
   Compare `fast["avg_duration_ms"]` vs `heavy["avg_duration_ms"]`. Expect a
   ratio of 3x–10x in a healthy configuration.

3. **Is the fast lane actually cheaper?**
   Compare `fast["avg_total_tokens"]` vs `heavy["avg_total_tokens"]`. Expect a
   similar or larger ratio than the duration comparison.

4. **Is context caching working in the fast lane?**
   Check `fast["total_cache_read_tokens"]` relative to `fast["total_tokens_in"]`.
   A cache-read ratio above 30% suggests good prompt reuse.

5. **Are totals consistent with the counts?**
   Spot-check: `total_duration_ms / count` should equal `avg_duration_ms`
   (within floating-point rounding). A mismatch indicates corrupted records in
   the sink.

---

## 3. Edge cases and what they mean

### The sink is absent or empty

If `debugging/logs/agent_telemetry.jsonl` does not exist or is empty,
`build_lane_comparison_report` returns `{}` without raising an exception.

```python
report = build_lane_comparison_report(Path("debugging/logs/agent_telemetry.jsonl"))
if not report:
    print("No telemetry data — no tickets have been driven yet, or the sink is unreachable.")
```

The sink is created on first write by `emit_agent_telemetry`. If the directory
`debugging/logs/` is absent it is created automatically at that point. Check the
pre-drive sink-reachability probe in CLAUDE.md if the file remains absent after
a completed drive.

### Only one lane appears in the result

If every recorded invocation used the same lane (e.g. all tickets were driven
through the heavy pipeline and the fast lane was never triggered), the result dict
will have only one key:

```python
{"heavy": {...}}
```

A lane with zero records is absent from the result — it is not represented as an
empty sub-dict. This lets callers detect the single-lane case:

```python
if len(report) < 2:
    print("Only one lane in the data — cannot produce a side-by-side comparison.")
```

### Malformed records in the sink

`build_lane_comparison_report` calls the internal `_load_jsonl` helper, which
skips malformed lines and logs a WARNING to stderr. Records without a `lane` field
are also silently skipped (they contribute to neither lane's aggregate). Numeric
fields that are missing from a record default to `0` via `dict.get("field", 0)`,
so a record with no `duration_ms` is counted in `count` but contributes 0 to
`total_duration_ms`.

To find malformed or lane-less records in the sink:

```python
import json
from pathlib import Path

sink = Path("debugging/logs/agent_telemetry.jsonl")
for i, line in enumerate(sink.read_text().splitlines(), 1):
    try:
        rec = json.loads(line)
        if "lane" not in rec:
            print(f"Line {i}: missing 'lane' field — {line[:80]}")
    except json.JSONDecodeError as exc:
        print(f"Line {i}: malformed JSON — {exc}")
```

---

## See Also

- [docs/reference/build-telemetry.md](../reference/build-telemetry.md) —
  full field reference for the telemetry JSONL schema and sink configuration.
- [docs/how-to/fast-lane-build.md](fast-lane-build.md) —
  how to configure and trigger the fast-lane build path.
- [docs/how-to/choose-build-path.md](choose-build-path.md) —
  decision guide for choosing between the fast lane and the heavy pipeline.
- [docs/architecture/components/build-orchestration.md](../architecture/components/build-orchestration.md) —
  component-level architecture for the build orchestration subsystem.
- `scripts/agent-health/generate_health_report.py` — source of
  `build_lane_comparison_report`; also produces the per-agent quality table
  (invocations, success rate, top failure archetypes) from the same telemetry sink.
- `scripts/agent-health/agent_telemetry.py` — the emitter that phase agents call
  after each invocation to append a record to the sink.
