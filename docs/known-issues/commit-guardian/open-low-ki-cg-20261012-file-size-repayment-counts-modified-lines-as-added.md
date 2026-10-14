---
title: "KI-CG-20261012-file-size-repayment-counts-modified-lines-as-added — check-file-size's GE-127f two-for-one repayment counts every changed line as added, so a one-line edit to an oversized file forces a far larger restructure, and merging two lines into one never pays for itself"
description: "medium — the measured added count is gross: every inserted or rewritten line counts, and the required length is previous length minus that count. Adding one phaseOrder entry to build-feature.js (2569 lines, limit 1000) was refused; compacting lines to pay for it counted each rewritten line as added again. Merging two lines into one is net -1 and raises the bar by 1, so it never closes the gap. Same day: a 3-line build.py change needed a whole function moved out, and a 2-line test edit needed six unrelated comment lines deleted."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/resolved/resolved-low-ki-cg-20261007-file-size-refusal-understates-the-shrink-obligation.md
  - docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127f.yaml
---

# KI-CG-20261012-file-size-repayment-counts-modified-lines-as-added — the file-size repayment counts modified lines as added

> One known issue, filed on sight during the INF-800f-1 and GE-132a-1 builds (PR #1155,
> merged as `08879303`). Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. It is not a correctness defect: the gate refuses what its rule says to
  refuse, and the files did shrink. The cost is friction. Touching a line in an oversized file
  costs far more than the change itself, and the rule pushes authors toward cosmetic
  line-golfing to pay for it.
- **Status:** open, no AC. The gross count is deliberate: GE-127f-2's Implementation Notes, quoted
  in the `count_added_measured_lines` docstring, say "gross, never net".
- **Occurrences:** 4 refusals on 2026-10-12 (see Evidence).
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** `templates/scripts/commit_guardian/check_file_size.py` on origin/main `b68d29679`,
  `required = max(limit, previous_length - added)` (:421-422); and
  `templates/scripts/commit_guardian/_file_size_ratchet.py`, `count_added_measured_lines` (:224),
  which sums the target side of every `insert` *and* `replace` opcode from
  `difflib.SequenceMatcher`, and `resolve_added_measured_lines` (:833).

## The rule as measured

For a file already over its limit, the required length is the previous length minus the measured
lines the change added. "Added" is gross. A rewritten line counts as added, in full. So:

- A pure addition of A lines must be paid for by removing 2A other lines (the obligation recorded
  in `KI-CG-20261007-file-size-refusal-understates-the-shrink-obligation`).
- Modifying k lines in place, with no net change in length, still counts k as added. It must be
  paid for by removing k other lines.
- Merging two lines into one adds 1 and removes 2. The file gets 1 line shorter, and the required
  length also drops by 1. The merge leaves the deficit exactly where it was, so no number of
  two-into-one merges can ever pay for anything.

## Evidence

All on 2026-10-12:

1. **One `phaseOrder` entry.** Adding one `"restructuring-specialist"` entry to the `phaseOrder`
   array in `templates/workflows-js/build-feature.js` (2569 lines, limit 1000) was refused:

   ```text
   This change added 1 measured line(s).
   Required length: 2568 lines or below
   ```

   The same entry went into `templates/workflows-js/build-ticket.js` (1453 lines).
2. **Compacting to pay for it.** Putting same-priority entries onto one line counted each
   rewritten line as added again. It was refused at 2567 against a required 2566, with "added 3".
   Only folding 5 entries onto one line, or moving whole functions out, passed. The folded line
   is visible on origin/main at `build-feature.js:434`.
3. **`scripts/build.py` (1564 lines).** A 3-line addition required moving a whole function into
   `scripts/build_deploy_manifest_helpers.py`.
4. **`unit_tests/commit_guardian/test_check_hook_parity.py` (1132 lines).** A 2-line
   test-assertion change required deleting six unrelated comment lines.

## Detection

A `FILE GREW WHILE ALREADY OVER ITS LIMIT` refusal whose `This change added N measured line(s)`
figure is larger than the lines the author meant to add, because it includes lines that were only
rewritten.

## Workaround

Pay the required length in whole removals, not merges: move a function out to a helper module,
delete dead lines, or fold several (at least three) lines into one so the fold removes more than
it adds back.

## Suggested fix (options, not decided)

- Count only net-new lines as added: lines inserted minus lines removed within the change.
- Exempt line-for-line modifications: a `replace` opcode of equal length on both sides adds
  nothing.
- Allow a small absolute allowance per change, below which no repayment is required.

Any of these reverses or relaxes the "gross, never net" choice that GE-127f-2's Implementation
Notes made on purpose (to stop a same-length rewrite from reading as zero added), so the choice
belongs with the GE-127f AC family.

**Related.**

- `KI-CG-20261007-file-size-refusal-understates-the-shrink-obligation` (resolved): the refusal
  used to tell authors that removing as many lines as they add was enough, when the rule needs
  twice that. This entry is about what counts as "added" in the first place.
- The GE-127f AC family: `docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/`
  `GE-127f.yaml`, `GE-127f-1.yaml`, `GE-127f-2.yaml`, `GE-127f-2-i.yaml`, `GE-127f-3.yaml`,
  `GE-127f-4.yaml`.

**Pattern:** a ratchet whose unit of cost (lines touched) is not the quantity it constrains
(file length), so cheap edits get expensive and the cheapest compliant edit is cosmetic.
