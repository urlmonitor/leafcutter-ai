---
title: "KI-BP-20260909-injector-falls-back-to-a-literal-400 — the build's file-size injector swallows every read failure and tells every agent 400, whatever the config actually declares"
description: "medium — the failure is silent and the wrong value is plausible, which is what makes it worse than a crash. It cannot corrupt a commit (the GATE still reads the real config), but it can make every agent's brief disagree with the gate that j"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260909-injector-falls-back-to-a-literal-400 — the build's file-size injector swallows every read failure and tells every agent 400, whatever the config actually declares

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — the failure is silent and the wrong value is plausible, which is what makes it worse than a crash. It cannot corrupt a commit (the GATE still reads the real config), but it can make every agent's brief disagree with the gate that judges it, with nothing anywhere reporting a discrepancy.
- **Status:** open. Specified but not built: `INF-1200f-1` ("the figure in your brief is the figure your work is judged against") is authored against exactly this shape and records it as must-not-reproduce; `INF-1200b-2`'s derived-delivery mechanism is where the real fix lands.
- **Occurrences:** 1 (structural — true of every build since the injector was added)
- **First seen:** 2026-09-09, found while enriching `INF-1200` · **Last seen:** 2026-09-09
- **Where:** `scripts/build.py:272-285` (`_inject_file_size_limit`)

**Symptom.** There is none. That is the entry.

**Mechanism.** The injector reads `file_size.line_limits['.py']` out of `templates/scripts/commit_guardian/commit_guardian.json` and publishes it to agent templates as `{{config.file_size_limit_py}}`. Its whole body is wrapped:

```python
py_limit: int = 400  # ultimate fallback
try:
    ...
    py_limit = int(py_limit)
except (OSError, json.JSONDecodeError, TypeError, ValueError):
    pass  # Fallback already set to 400
config["file_size_limit_py"] = py_limit
```

If the config is unreadable, malformed, or holds a non-integer, every agent template is compiled telling its reader the limit is **400** — with no warning, no build failure, and no marker in the output. The gate itself is unaffected: `check_file_size.py` reads the config directly at commit time. So the two surfaces silently disagree, and the direction of the disagreement is unbounded — if the declared limit were 600, every agent would be told 400 and would split files that never needed splitting.

**Why this is a Rule 3 violation and not a judgement call.** `CLAUDE.md`'s Error Handling Policy Rule 3 requires every `except` block to log at WARNING or higher, or re-raise. `pass` with a comment is neither. Note the precise reading, because it matters for the fix: Rule 2 is NOT violated — exception types are named. The defect is that a failed measurement is converted into a successful-looking value, which is the same shape as `KI-CG-034` (a scanner that examined 169 files, compared none, exited 0) and `GE-127a-1-i` (an unreadable file reported as "0 lines - OK").

**Fix direction.** The fallback constant is the problem, not the try/except. A build that cannot read the declared limit must not publish a number: either fail the build, or publish an explicit unavailability marker the template can render as such. A second literal `400` living in `build.py` is, in `INF-1200f-1`'s terms, a second figure by another name — and note it is a *third* copy, since `file_size.default_limit` is also 400. Whatever replaces it, the number must appear in exactly one place.

**Related.**
- `INF-1200f-1` and `INF-1200b-2` — the criteria that own this; this entry should be closed by their implementation rather than separately.
- `KI-CG-034`, `GE-127a-1-i` — same shape (unmeasured reported as measured) on other surfaces.
- `KI-BP-20260909-standards-declare-no-applicability` (below) — found in the same pass, and the two together are why a generic injector cannot simply be written over the existing config.

**Pattern:** a fallback constant that is indistinguishable, downstream, from a real measurement.

---
