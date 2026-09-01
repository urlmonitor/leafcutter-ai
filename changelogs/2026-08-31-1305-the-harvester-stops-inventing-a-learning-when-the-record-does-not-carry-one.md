---
title: "The harvester stops inventing a learning when the record does not carry one"
date: "2026-08-31"
time: "13:05"
type: manual
components:
  - knowledge_system
  - infrastructure
summary: "The placeholder substitution that synthesised a learning body out of a record's own metadata is deleted outright, and textlessness is now classified before entry_kind so the real 28-record corpus can reach a resting state instead of pinning exit 3 forever. A JSON scalar on a sink line no longer crashes the run."
description: "INF-700c-1 and INF-700c-1-i. The harvester's write path read `learning_text = event.get(\"text\", f\"[{entry_kind}] Learning from {ticket}\")`. With no `text` on any real record and no `ticket` either, that default synthesised content-free strings like '[agent-assignment-pattern] Learning from ' and appended them to curated knowledge files. The AC required the default be REMOVED -- not narrowed, not flag-guarded, not moved behind a toggle -- because a default that still exists anywhere on the write path is a defect waiting for the next caller. It is deleted; `learning_text = event.get(\"text\")` is now reached only after eligibility confirms real text is present. WHAT COUNTS AS TEXTLESS: key absent, value null, value empty after whitespace normalisation, or a value that merely restates the record's own descriptive fields -- the last clause exists so deleting the harvester-side default cannot be undone by an emitter inlining the same string. CLASSIFICATION ORDER IS THE LOAD-BEARING PART: the textless test now runs BEFORE the `entry_kind not in _KNOWN_ENTRY_KINDS` test. All 28 retained records are simultaneously textless AND unknown-kinded (15 distinct kinds on disk, none among the 11 known), so kind-first classification would put every one into skipped_unknown and return exit 3 forever -- the permanently non-zero backlog INF-700c exists to end. A fourth counter, no_learning_text with a per-entry_kind breakdown, joins routed / previously_processed / skipped_unknown / write_failures, and participates in the total: a bucket that does not participate in a total is a bucket that can silently drop records. Ineligible records are never added to the idempotency record, so they are re-derived every run rather than being marked processed in a gitignored file. INF-700c-1-i adds malformed-line reporting with 1-based line numbers matching the file on disk, and an isinstance(event, dict) guard after json.loads -- a line that is valid JSON but not an object (a bare scalar such as \"done\") previously raised an unhandled AttributeError, killed the run with exit 1 (documented as 'sink file not found'), and skipped every record after it. That is KI-KM-011, fixed here. No new exit code was introduced; 0/3/4 are unchanged. The sink is never rewritten and the loop never stops early. TEST FALLOUT, recorded because it was large and deliberate: deleting the placeholder broke 16 previously-green tests, because the shared _make_event() helper never populated `text` and those tests silently relied on the synthesised default to produce written content. Each was given a real, scenario-appropriate `text` value rather than a blanket default on the helper -- a helper-level default would have recreated the deleted placeholder one layer up and every future test would have inherited it. Two required judgement rather than a mechanical edit. TestExtendedRoutingRulesReroutesPreviouslyUnroutable asserted that written content contained the literal entry_kind string, which only ever passed because the placeholder embedded entry_kind verbatim; it now asserts a verbatim round-trip of the record's own real text, which is what its docstring always claimed to be about. TestFullCorpusAllUnroutable uses the verbatim 28-record fixture, which was NOT edited -- those records genuinely have no text, so only the expectation moved, from skipped_unknown 28 to no_learning_text 28 with the same 15-kind distribution in the correct bucket. 53 tests pass under AC_ENFORCE_STRICT=1."
breaking: false
---

## Entry

The harvester invented learnings. Its write path read:

```python
learning_text = event.get("text", f"[{entry_kind}] Learning from {ticket}")
```

No real record carries `text`, and none carries `ticket` either — so that default produced content-free strings like `[agent-assignment-pattern] Learning from ` and appended them to curated knowledge files.

**The default is deleted outright**, as the AC required: not narrowed, not flag-guarded, not moved behind a toggle. A default that still exists anywhere on the write path is a defect waiting for the next caller.

### Classification order is the load-bearing part

The textless test now runs **before** the `entry_kind` test.

All 28 retained records are *simultaneously* textless and unknown-kinded. Under kind-first classification every one lands in `skipped_unknown` and the run returns exit 3 — forever. That is precisely the permanently non-zero backlog `INF-700c` exists to end.

A fourth counter, `no_learning_text`, joins the existing three and **participates in the total**. A bucket that does not participate in a total is a bucket that can silently drop records.

### A JSON scalar no longer kills the run

A sink line that is valid JSON but not an object — a bare `"done"` — passed `json.loads` and then raised an unhandled `AttributeError`, exiting 1 (documented as *"sink file not found"*) and skipping every record after it. That is `KI-KM-011`, fixed here with an `isinstance` guard and 1-based malformed-line reporting.

### The test fallout was large, and deliberate

Deleting the placeholder broke **16 previously-green tests**. The shared `_make_event()` helper never set `text`, so they had been quietly relying on the synthesised default to produce written content.

Each got a real, scenario-appropriate value — **not** a blanket default on the helper, which would have recreated the deleted placeholder one layer up and let every future test inherit it silently.

Two needed judgement:

- `TestExtendedRoutingRulesReroutesPreviouslyUnroutable` asserted the written content contained the literal `entry_kind` string — which only ever passed because the placeholder embedded it verbatim. It now asserts a verbatim round-trip of the record's own real text, which is what its docstring always claimed.
- `TestFullCorpusAllUnroutable` uses the verbatim 28-record fixture, **not edited**. Those records genuinely have no text. Only the expectation moved: `skipped_unknown` 28 → `no_learning_text` 28, same 15-kind distribution, correct bucket.

53 tests pass under `AC_ENFORCE_STRICT=1`.
