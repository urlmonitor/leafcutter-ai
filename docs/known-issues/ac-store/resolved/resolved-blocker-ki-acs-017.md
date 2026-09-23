---
title: "KI-ACS-017 — `approve_acs.py` corrupts any record whose `amended_by` holds a multi-line entry, and returns success for the files it broke"
description: "KI-ACS-017 — `approve_acs.py` corrupts any record whose `amended_by` holds a multi-line entry, and returns success for the files it broke"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-017 — `approve_acs.py` corrupts any record whose `amended_by` holds a multi-line entry, and returns success for the files it broke

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../../ac-store.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** RESOLVED 2026-09-14 — both halves fixed; see "Resolution" at the end of this
  entry. Kept rather than deleted because the failure shape it documents — a writer whose
  success line and exit code are emitted before anything validates the write — is the
  general lesson, and `KI-ACS-018` was filed against the same shape elsewhere.
- **Occurrences:** 1 (5 files corrupted in a single run)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `scripts/ac_store/approve_acs.py` — `_promote_leaf()` and `_build_amended_by_block()`

**Symptom.** `_promote_leaf` appends the approval entry by rebuilding the `amended_by`
block as **text** rather than by round-tripping the parsed document. On a record whose
existing `amended_by` contains a multi-line entry, it emits YAML that no longer parses:

```
yaml.parser.ParserError: while parsing a block mapping
  in "<unicode string>", line 126, column 3:
    - action: approved
      ^
expected <block end>, but found '<scalar>'
```

**The dangerous part is not the corruption, it is the return code.** The run reported
`rc=0` for all 31 records **including the five it had just made unparseable**. Nothing in
the tool's own output distinguished a successful promotion from a destroyed file. It
surfaced only because the calling script re-read every file from disk afterwards and
asserted it still parsed — a check nobody is obliged to perform, and which the tool's
success-shaped output actively discourages.

**Evidence.** 2026-08-31, promoting the 31 records under `GE-123`. Five files were left
unparseable: `GE-123a-4`, `GE-123b-5`, `GE-123c-4`, `GE-123c-5`, `GE-123d-4-ii` — exactly
the five carrying the multi-line gating-correction entries added in #554 and #594. All five
were already committed, so nothing was lost; they were restored with `git checkout` and
their `readiness` set by hand. Had the promotion been run on uncommitted records, or
committed without the re-read, five acceptance criteria would have entered the store
unparseable — and `validate_ac_schema` would then have failed for every subsequent commit
touching that tree, with a cause several steps removed from the change that produced it.

**Detection.** After any `approve_acs.py` run, re-parse every file it touched. Do not trust
the exit code or the per-record `promoted …` lines; both are emitted before the write is
validated. `find <dir> -name '*.yaml' -exec python scripts/ac_store/validate_ac_schema.py {} +`
is sufficient and takes seconds.

**Workaround.** For a record with a multi-line `amended_by`, set `readiness` by hand — it is
a one-line edit — rather than letting the tool rewrite the block.

**Fix direction.** Stop rebuilding the block textually. Either round-trip through a YAML
library that preserves the document, or append the entry without re-emitting the entries
already there. Whatever the approach, `_promote_leaf` must re-read and parse the file it
just wrote before returning 0: a writer that cannot tell whether its own output is valid
has no business reporting success.

**Related.** `KI-ACS-018` (the sibling generator, same "output never validated against the
gates that will judge it" shape).

**Resolution — 2026-09-14, `ef2c63401` on `feature/approve-acs-amended-by-corruption`
(PR #789), covering `ACD-1200b-5-ii`.**

The trigger is narrower than "multi-line `amended_by`", and naming it precisely is the
useful part: it is a **blank line inside a multi-line scalar**. `_AMENDED_BY_RE` continued
over lines beginning with a space/tab or a dash, and a blank line is neither — so on
`GE-123a-4`, whose `entry:` scalar has blank lines at file lines 107, 113 and 120, the match
ended at 107. `_promote_leaf` then spliced the rebuilt block over lines 99-106 and left
108-126 in place as top-level text, which is the `expected <block end>, but found '<scalar>'`
above.

Both halves are fixed, as the Fix direction prescribed:

- `_AMENDED_BY_RE` is replaced by `_find_amended_by_block`, which delimits the block by
  locating its **end** — the next column-0 top-level key, or end of document — rather than by
  recognising the shape of every interior line. Blank lines, indented continuations and
  column-0 block-sequence dashes are then always interior by construction, whatever they
  contain. This is the load-bearing change: no per-line regex can recognise a blank line as
  "inside a scalar", so the boundary had to be found from the other direction.
- `_promote_leaf` re-reads and re-parses the file it just wrote **before** printing any
  success line or returning 0. On a parse failure it restores the original bytes exactly,
  names the file on stderr, and returns 1. The `promoted …` line is no longer reachable for a
  record left unparseable.

Five behavioral tests in `unit_tests/ac_store/test_acd_1200b_5_ii.py`, built from the real
on-disk `GE-123a-4` record rather than a hand-indented fixture — the synthetic-fixture bias
is what let this through originally, so the AC's `test_rationale` fixes the artifact shape
explicitly. One drives the CLI as a subprocess, because the second half of the defect (a
success-shaped exit code over a destroyed file) is only observable from outside the process.
Red baseline 5 failed under `AC_ENFORCE_STRICT=1`; 5 passed after; mutation-proven by
stashing the fix (5 red again) and restoring it (12 passed, including the 7 pre-existing
sibling tests).

**Detection above is now redundant for this tool, and deliberately left in place.** Re-parsing
every file after a run is still the right habit for any store-mutating script — this fix makes
`approve_acs.py` self-checking, it does not make the store's other writers so.

**Not fixed here, and narrower than the original defect:** the new block-end rule treats a
column-0 `#` comment sitting between the `amended_by` entries and the next top-level key as
interior to the block, so such a comment would be dropped on promotion. No record in the store
has one today — the two AC files carrying column-0 comments (`ACS-100a-6`, `BP-1100g`) place
them after `superseded_by:`, outside the span — so this is a latent shape, not a live defect.
It was left out rather than folded in silently, because hardening it without a test would
reintroduce the untested-write habit this entry is about.

---
