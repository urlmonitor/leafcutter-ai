---
title: "The doc-length gate now actually refuses a commit instead of printing a warning"
date: "2026-09-14"
time: "20:20"
type: manual
components:
  - commit_guardian
  - doc_compliance
summary: "check-doc-length has printed advice and exited 0 since it shipped, because its severity was never set and defaulted to warn — which is how three known-issues registers reached ~4,500 lines against a 300-line limit unchallenged. It now blocks, and it blocks on a GE-127-style ratchet so the 59 docs already over the limit stay editable."
description: "Sets doc_length.severity to block in commit_guardian.json — the section did not exist at all, so DOC_LENGTH_SEVERITY took its warn default and main() returned 0 on every run. Blocking absolutely would have frozen the 59 tracked docs already over their limit, including the append-heavy known-issues registers, so the gate now ratchets exactly as check-file-size does for code: a doc is refused when it CROSSES its limit or GROWS while already over, and passes when it shrinks or holds steady. The ratchet reuses _file_size_ratchet.py's git plumbing (merge-parent resolution, INDETERMINATE floor, empty-history classification) via a new pluggable measure parameter rather than a second copy. Two fail-opens closed on the way, both previously unable to change an outcome and now able to: an unreadable doc was silently skipped, and a failed git invocation returned an empty staged set that main() read as nothing-to-check."
commits: []
breaking: true
---

## Entry

### What was wrong

`check-doc-length` was registered, running on every commit touching `docs/**.md`, and
printing well-formed violation reports naming the exact sections to extract. It also
returned `0` every single time.

`commit_guardian.json` had no `doc_length` section, so `DOC_LENGTH_SEVERITY` fell through
to its `"warn"` default, and `main()`'s blocking branch was unreachable. The gate's own
DECISION HISTORY described warn-only as a starting posture — one never left.

The result is measurable. Against a 300-line limit:

| file | lines |
|---|---|
| `docs/known-issues/build-pipeline.md` | 4,515 |
| `docs/known-issues/commit-guardian.md` | 4,388 |
| `docs/known-issues/build-orchestration.md` | 4,275 |

Not one commit that produced those was ever stopped.

### Why blocking alone was not the fix

59 of 339 tracked docs are already over their limit. A plain `severity: block` freezes
every one of them until it is split — including the registers that are appended to
constantly. A gate that makes ordinary work impossible gets switched off, and the warn
default comes back.

So the gate blocks on a **ratchet**, the same posture `check-file-size` took for code
under GE-127a-1 / GE-127b-1:

| situation | outcome |
|---|---|
| doc crosses its limit | refused |
| doc already over, grows | refused |
| doc already over, shrinks | passes — judged against its own previous size |
| doc already over, edited at the same length | passes |
| new doc arriving over the limit | refused — no previous size to be judged against |

Verified against the real 4,388-line `commit-guardian.md`: appending one entry is refused,
rewording in place passes, deleting forty lines passes.

### Two fail-opens closed

Both were harmless while the gate could only warn, and are not once it can refuse:

- `read_file_content()` returned `None` for a doc it could not decode, and the loop
  skipped it.
- `get_staged_files()` returned `{}` when git failed — which `main()` reads as "nothing
  staged, exit 0". A gate that could not look reported as a gate that looked and approved.

Both now raise and surface as `INDETERMINATE` (exit 2), reusing the verdict vocabulary
`check_file_size.py` already established. The second was caught by its own new test, not
by reading the code.

### Shape of the change

The doc-specific parts — counting rules, covered-set predicates, the pass/grew/over
verdict — live in a new `_doc_length_ratchet.py`. It owns no git plumbing. Merge-parent
resolution, the two-situation INDETERMINATE floor and empty-history classification all
come from `_file_size_ratchet.py`, which gained an optional `measure` callable and a
`resolve_head_matching_paths(predicate)` variant. Both default to existing behaviour, so
`check_file_size.py` — the only in-tree caller — is byte-for-byte unaffected.

The section dimension (25 `##` headings) blocks outright rather than ratcheting: it has
zero current violations, because the registers use `###` per entry.

### Scope note

`max_lines`, `max_lines_adr`, `max_sections` and `excluded_files` are now written
explicitly in the config at the values they previously took implicitly. This change
alters **enforcement only** — not which docs are judged, nor where the thresholds sit.

Marked breaking: a commit that grows an over-limit doc, or takes any doc over 300 lines
(400 for ADRs), now fails where it previously printed a warning and succeeded.
