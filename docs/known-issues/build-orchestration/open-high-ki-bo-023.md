---
title: "KI-BO-023 — `_update_ac_work_status` raises `ValueError`, all three call sites catch only `OSError`, and the escape strands acceptance criteria in `in_progress` permanently"
description: "KI-BO-023 — `_update_ac_work_status` raises `ValueError`, all three call sites catch only `OSError`, and the escape strands acceptance criteria in `in_progress` permanently"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-023 — `_update_ac_work_status` raises `ValueError`, all three call sites catch only `OSError`, and the escape strands acceptance criteria in `in_progress` permanently

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Renumbered 2026-08-25 from KI-BO-020**, for the same collision described on KI-BO-022.
> Note the coincidence worth reading: main's KI-BO-020, landed by PR #538 seventeen minutes
> earlier, describes the *same consequence* — aborted runs stranding their claims — by a
> different mechanism (its release path dispatches `status-checker`, which refuses the
> role). Two independent branches found two independent causes of one symptom on the same
> day. Both are real; neither supersedes the other.

- **Severity:** high
- **Status:** open — latent, zero live instances today
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** raise at `scripts/build_orchestration/fast_lane.py:180-185`; call sites catch `except OSError` only at `:289` (`claim_build_set`), `:347` (`release_claim`), `:462` (`mark_done_built_acs`)

**Symptom.** When a record contains more than one column-0 `work_status:` line the
function raises `ValueError` — deliberately, rather than guess which is the real key. But
no caller catches it. Confirmed by execution; observed disk state after the escape:

```
claim_build_set:      ESCAPED ValueError ...  A left at: ['work_status: in_progress']
release_claim:        ESCAPED ValueError ...  C left at: ['work_status: in_progress']
mark_done_built_acs:  ESCAPED ValueError ...
```

**Two consequences, the second much worse.**

*Lost claim payload.* `claim_build_set` flips records to `in_progress` on disk as it goes,
then loses its return value to the exception. `fast-lane-ship.js:391-437` builds
`claimedIdsCsv` from exactly that payload to feed every `release-on-*-fail` path, so the
records it already flipped are never released.

*The un-sticking mechanism is the thing that breaks.* `release_claim` is what returns a
stranded AC to `todo`, and it aborts mid-loop on the same exception. Everything after the
offending record stays `in_progress` **forever** and is then permanently excluded from
future runs by `filter_already_claimed`. Recovery is a hand edit.

**The docstring's justification is falsifiable.** It claims column-0 anchoring means an
occurrence of `work_status` inside block-scalar prose is never mistaken for the real key.
Two constructions defeat it, both confirmed:

- A legal multi-line double-quoted scalar whose continuation begins at column 0. PyYAML
  parses this correctly as one `work_status: todo`; the function counts two matches and
  raises:

  ```yaml
  id: B-1
  notes: "the release step resets it back to
  work_status: todo when the run fails"
  work_status: todo
  ```

- `U+2028` or `U+0085` inside a block scalar. `str.splitlines()` splits on `U+2028`,
  `U+2029`, `U+0085`, `\x0b`, `\x0c` and `\x1c`-`\x1e`; YAML's line-break set is narrower.
  The phantom second match raises on a perfectly valid record.

**Exposure.** 0 of 3,257 records currently have more than one column-0 match, so no run is
failing this way today.

**Fix sketch.** Two independent halves, and the second matters more than the first. Narrow
the detection (parse-aware, or at minimum split on YAML's line-break set rather than
Python's) *and* widen the three call sites to catch `ValueError` alongside `OSError`, so
that a raise can never leave claims stranded regardless of what triggers it. The release
path in particular should be failure-tolerant per record rather than aborting the loop.

---
