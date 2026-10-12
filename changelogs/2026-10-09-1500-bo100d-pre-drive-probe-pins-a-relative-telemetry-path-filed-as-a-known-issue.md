---
title: "BO-100d's pre-drive probe pins a relative telemetry path: filed as a known issue"
date: "2026-10-09"
time: "15:00"
type: manual
components: 
  - build_orchestration
  - agent_telemetry
summary: "Ten approved BO-100d ACs name the telemetry sink by the relative path debugging/logs/agent_telemetry.jsonl. Once INF-500d-4 moves every log to one declared absolute root, a probe built to those ACs would pass against a file nobody writes to. Filed as a high, latent known issue for the build-orchestration owner."
description: "One content commit (2a48283b1), documentation only. Adds KI-BO-20261009-bo100d-probe-pins-a-relative-telemetry-path (severity high, latent) to the build-orchestration register, with its index row (open 57 -> 58, high 32 -> 33). BO-100d, -1, -1-i, -1-ii, -1a, -1b, -2, -2-i, -2a and -2b (all readiness approved, work_status todo) name the relative string debugging/logs/agent_telemetry.jsonl; the entry lists each with file:line on origin/main ed83d9f77 (BO-100d itself names it only in notes). INF-500d-4 (PR #1107) moves every log in debugging/logs/ to one absolute root declared at build time in config/knowledge_sink.json, so a probe that appends to the relative path inside a worktree would give a false green. The entry records the fix direction from INF-500d-4's IT PO (probe the declared operational_telemetry_stream through INF-500d-4-iii's location query; fail as blocked, remediation rebuild, when the declaration is missing; name the absolute path) and the undecided order in which BO-100d-1a and INF-500d-4 land. No AC was edited."
commits: 
  - 2a48283b1
breaking: false
---

## Entry

Ten approved BO-100d ACs name the agent-telemetry sink by the **relative** path
`debugging/logs/agent_telemetry.jsonl`, and their pre-drive probe appends to it from the
worktree. INF-500d-4 (PR #1107) moves every log in `debugging/logs/` to **one absolute root**
declared at build time. After that, a probe built to the BO-100d criteria passes against a
worktree-local file nobody writes to, while the real stream may be unwritable.

- **KI-BO-20261009-bo100d-probe-pins-a-relative-telemetry-path filed** (high, latent) in the
  build-orchestration register, with its index row. It lists all ten ACs with file:line, plus the
  existing prose probes that use the same relative path.
- **Fix direction recorded**, from INF-500d-4's IT PO: probe the declared
  `operational_telemetry_stream` through INF-500d-4-iii's location query, and fail as blocked when
  the declaration is missing. Changing the ten ACs is the build-orchestration owner's call. The
  landing order of BO-100d-1a and INF-500d-4 is undecided.

No AC was edited. No code changes.
