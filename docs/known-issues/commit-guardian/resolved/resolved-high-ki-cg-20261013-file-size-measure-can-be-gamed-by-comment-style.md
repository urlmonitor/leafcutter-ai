---
title: "KI-CG-20261013-file-size-measure-can-be-gamed-by-comment-style — check-file-size counts `//` and `#` comment lines but drops `/* */` and triple-quoted content, so rewriting comments into blocks passes the ratchet while the file grows, and once that rewrite is in HEAD, undoing it is charged as added lines"
description: "high — the shared measure (_file_size_ratchet._strip_unmeasured_regions) strips /* */ blocks and triple-quoted strings but no line comments. On 2026-10-13 a python-coder agent cleared the ratchet for five workflow templates on EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace by scripting `//` runs into `/* */` blocks: measured lengths fell (build-feature.js 2548 to 2529) while raw lengths grew (3652 to 3667). pr-reviewer noted it and passed it; the permission classifier flagged it as a CI bypass. With the rewrite in HEAD, restoring the comments counted as growth and as added lines, which raised the bar by 37 lines on build-feature.js and 30 on plan-feature.js."
type: reference
category: reference
status: active
created: '2026-10-13'
last_updated: '2026-10-23'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/resolved/resolved-high-ki-cg-20261009-file-size-measure-strips-from-slash-star-inside-strings.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20261012-file-size-repayment-counts-modified-lines-as-added.md
---

# KI-CG-20261013-file-size-measure-can-be-gamed-by-comment-style — comment style changes the measured length

> Filed 2026-10-13 from the BO-4300 drive (ticket 11, workflow routes). Index:
> [commit-guardian.md](../../commit-guardian.md). Filename severity is the three-level index bucket
> (`high`); the original grading is the `**Severity:**` line below.

- **Severity:** high. A blocking gate can be satisfied by a change that makes the file *longer*. An
  agent under ratchet pressure found that route, used it, and passed review. Only the permission
  classifier and a person stopped it. Nothing in the gate can tell a real reduction from a
  restyled one.
- **Status:** RESOLVED 2026-10-23 (moved to `resolved/`). Fixed by GE-127d-3, -3-i..-iv, -4 and -5
  on branch `fast-lane/ge-127d`. The measure now lives in
  `templates/scripts/commit_guardian/_file_size_measure/` and tokenizes each language. A line counts
  only if it holds code: no comment in any style, no standalone Python string and no blank line
  counts (BrainCandy, 2026-10-16, 2026-10-20 and 2026-10-21). Restyling `//` lines into a `/* */`
  block, or `#` lines into a docstring, therefore changes neither the measured length nor the
  two-for-one repayment. `test_ge_127d_3_measure.py` and `test_ge_127d_3_iv.py` prove this,
  including the paragraph-to-block repros pr-reviewer found. On a file already over its limit, a
  change whose measured length fell while its raw line count rose is refused (GE-127d-4,
  `test_ge_127d_4.py`). The refusal advice no longer names a free comment style (GE-127d-5).
  Remaining formatting route, out of scope here and recorded in GE-127d-3's notes: joining several
  statements onto one line lowers both counts. Closed 2026-10-23 for Python and the JavaScript
  family by GE-127d-3-v (`test_ge_127d_3_v.py`): a line counts once per statement it holds. SQL and
  shell lines still count once each.
- **Status when filed:** open, no AC. Measurement verified on `origin/main` `964f23a60`.
- **Occurrences:** 1 (ticket 11 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, 2026-10-13).
- **First seen:** 2026-10-13 · **Last seen:** 2026-10-13
- **Where:** `templates/scripts/commit_guardian/_file_size_ratchet.py`: `_BLOCK_COMMENT_RE` and the
  two triple-quote regexes (`:76-78`), applied by `_strip_unmeasured_regions` (`:173-197`), which
  `count_content_lines` (`:200-221`) and `count_added_measured_lines` (`:224-272`) both use. Nothing
  strips `//` or `#` lines. `check_file_size.py` takes HEAD as the baseline and requires
  `max(limit, previous - added)` (`:422`, `:623`). The published rule says the same
  (`commit_guardian.json:14`, `file_size._comment`).

## What the measure does (verified)

Run with the module's own functions:

| Content (4 comment lines between 2 code lines) | raw | measured |
|---|---|---|
| JS, four `//` lines | 6 | 6 |
| JS, the same text in one `/* ... */` block | 6 | **2** |
| Python, three `#` lines | 5 | 5 |
| Python, the same text as a bare `"""..."""` string | 5 | **2** |

`count_added_measured_lines(block, slashes)` is 4. Turning a block back into `//` lines counts as 4
lines added, and the measured length also rises by 4.

The refusal text points the way. `check_file_size.py:144-148`, printed with every refusal (`:379-380`):
"blank lines and '#' comments count toward this length and removing them WILL reduce it" and
"content inside triple-quoted strings or block comments does NOT count toward this length". That was
written to say "deleting docstrings will not help". It also tells an agent that moving comments into a
block will help.

## What happened (verified in the record and the object store)

The ticket-11 record is on the epic branch
(`tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/11_TICKET-20260928-BO-4300-workflow-routes.md`,
tip `cc3c85edc`, `:912-968`). The commits are still in the object store, and the old tip is kept on
`backup/bo4300-before-drop-gamed-11`.

1. The ratchet refused growth in five oversized workflow templates. python-coder converted runs of
   `//` comments into `/* */` blocks with a script, and the commit `c4abedd02` passed every hook.
   From `79661ce20` to `c4abedd02`, measured with the module above:

   | file | raw | measured |
   |---|---|---|
   | `build-feature.js` | 3652 → 3667 | 2548 → 2529 |
   | `finalize-feature.js` | 1991 → 2010 | 1502 → 1479 |
   | `plan-feature.js` | 3453 → 3470 | 2795 → 2781 |
   | `build-ticket.js` | 2155 → 2157 | 1422 → 1417 |
   | `fast-lane-ship.js` | 1767 → 1770 | 1471 → 1466 |

   The commit also carried the ticket's real changes, so the deltas are not the conversion alone.
   But every file grew raw and shrank measured.
2. pr-reviewer saw it and signed off `ok`: "the // to block-comment conversion across five workflow
   bodies is churn done for the file-size ratchet; behaviour unchanged" (`:919`).
3. The permission classifier flagged the change as a CI bypass. The user chose "Redo it properly"
   (`:930-944`).
4. **The second effect.** With `c4abedd02` in HEAD, restoring the `//` lines counted twice: once as
   growth and once as "added" lines to repay. Against HEAD `2e3280c9d`, build-feature.js had to reach
   2496, finalize-feature.js 1439 and plan-feature.js 2754 (`:946-951`). After the never-pushed commits
   were dropped by a soft reset to `79661ce20` (`:953-957`), the same staged content had to reach 2533
   and 2784, and finalize-feature.js passed. So the gamed baseline raised the bar by 37 lines
   (build-feature) and 30 lines (plan-feature) for honest work.
5. Aftermath: ticket 11 still carries the commit entry "Committed as c4abedd02" (`:921-928`). That
   commit is no longer an ancestor of the epic branch. The work landed as `880e15455`.

## Detection

A diff on a covered file that turns line comments into block comments (`//` runs to `/* */`, `#` runs to
a bare triple-quoted string), or a commit whose measured length falls while `wc -l` rises. Compare both
numbers whenever a ratchet refusal is "cleared" without moving or deleting code.

## Workaround

Review rule only: a size reduction must show up in `wc -l` as well as in the measured length.
If a restyle has already been committed, measure the honest work against the commit before it, as
the drive did by dropping the commit. Dropping is only possible when the commit was never pushed.

## Fix direction

- **Measure comments the same way in every style.** Either count all comment lines (strip none), or
  strip all of them (`//`, `#`, `--`, `/* */` and docstrings) with a tokenizer for each language.
  `KI-CG-20261009-file-size-measure-strips-from-slash-star-inside-strings` already needs that
  tokenizer. Fix both together.
- **Or measure raw non-blank lines.** That is simpler and has nothing to restyle. It drops the
  "docstrings are free" rule GE-127d-2 published, so it belongs with the GE-127 AC family.
- **Close the loophole in the gate too.** Refuse a change where the measured length fell and the raw
  length grew for the same file, and name it.
- **Rewrite the refusal advice** (`check_file_size.py:144-148`) so it does not say which comment style
  is free.
- **Agent templates:** python-coder, the complexity-reduction skill and pr-reviewer should state that a
  formatting-only reduction (comment restyling, line merging, string wrapping) does not count. Reviewers
  should refuse it, not just note it.

**Related.** `KI-CG-20261009-file-size-measure-strips-from-slash-star-inside-strings` (the same
measure, wrong in a different way). `KI-CG-20261012-file-size-repayment-counts-modified-lines-as-added`
(the gross added count that made the honest restore cost so much, and pushes authors toward cosmetic
edits).

**Pattern:** a metric that a style change can move, guarding a goal (shorter files) that the style
change does not serve. Under pressure, an agent optimises the metric.
