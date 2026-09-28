---
title: "KI-KM-011 — A valid-JSON non-object line crashes the harvester with an unhandled `AttributeError`, and the sink already contains junk lines the repo's own checklist puts there"
description: "KI-KM-011 — A valid-JSON non-object line crashes the harvester with an unhandled `AttributeError`, and the sink already contains junk lines the repo's own checklist puts there"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-011 — A valid-JSON non-object line crashes the harvester with an unhandled `AttributeError`, and the sink already contains junk lines the repo's own checklist puts there

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../../knowledge-management.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** **PARTIALLY RESOLVED 2026-08-31.** The crash is fixed — `INF-700c-1-i`
  (PR #650) added the `isinstance(event, dict)` guard and 1-based malformed-line
  reporting, so a bare JSON scalar is now counted as malformed instead of killing the
  run, and a reader can tell a whole-file read from a truncated one. Verified: 53 tests
  green, including a case built from the real 33-line sink.
  **The other half is still open, and is why this entry is narrowed rather than deleted:**
  `CLAUDE.md`'s Pre-Drive Checklist still prescribes
  `echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl`, so the
  documented check keeps writing non-event lines into the stream the harvester reads.
  The harvester now tolerates them; nothing has stopped producing them. Remaining fix:
  change the probe to a non-appending writability check (`test -w`) or point it at a
  scratch path.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/knowledge/harvest_learnings.py` — the per-line loop, at
  `event.get("event")`; `CLAUDE.md` → Pre-Drive Checklist → "Feedback sink reachable"

**Symptom.** The harvester catches `json.JSONDecodeError` and continues, so a malformed
line is survivable. A line that is **valid JSON but not an object** — `"done"`, `42`,
`[]` — passes `json.loads` and then raises `AttributeError: 'str' object has no attribute
'get'`, which is outside the caught type. The run dies with an unhandled traceback and
exit `1`, a code documented as "sink file not found or unreadable". Every well-formed
record after the offending line is never processed.

Reproduced directly against the production entry point with a two-line sink whose first
line is `"just a string"`: the valid `knowledge_captured` record on line 2 was not routed.

**This is not hypothetical — the sink is already dirty.** `debugging/logs/agent_telemetry.jsonl`
is 33 lines: 28 knowledge records, **4 probe lines**, and 1 malformed line (line 19 is the
bare string `</content>`, a fragment from an agent hand-writing its JSON append — itself
corroboration of `INF-400c-5`'s claim that free-hand appends caused the vocabulary sprawl).

**The repo instructs people to write the probe lines.** `CLAUDE.md`'s Pre-Drive Checklist
prescribes `echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl` as
a writability test. Lines 1, 21, 31 and 33 are that probe. So the documented pre-drive
check is itself a producer of non-event lines in the shared stream the harvester reads —
a small instance of the same shape as `KI-BP-007`: an instruction that quietly creates the
condition another component must tolerate.

**Fix direction.** ~~Widen the guard to `isinstance(event, dict)` before `.get()`, and count
skipped lines with their line numbers rather than dropping them silently~~ — **done in
PR #650**, with no sixth exit code added, as prescribed. **Still outstanding:** change the
checklist's probe to a `test -w` style check that does not append, or point it at a scratch
path. Until that lands the sink keeps accruing probe lines; they are now counted and
reported rather than fatal, which is a smaller problem but not the absence of one.

**Related.** `INF-700c-1-i` (owns the resilience-and-reporting behaviour, with test specs
authored). `INF-400c-4-iii` (owns filtering the harvester's own stream out of the shared
telemetry file). `KI-BP-007` (documented instruction, silent consequence).

---
