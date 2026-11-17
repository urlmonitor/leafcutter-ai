---
title: "A set-aside location is still a bounded place: each declares the size beyond which its documents are reported, and no location may be set aside without one"
date: "2026-10-14"
time: "09:48"
type: manual
components: 
  - commit_guardian
  - doc_compliance
summary: "Generated documents that are exempt from the document length limit can no longer grow unnoticed: each exempt location now declares a size above which every commit that stages a document there reports it, though the commit still completes."
description: "GE-127g-5 complete; GE-127g-2 only partly delivered (child GE-127g-2-i not built, so GE-127g-2 is recorded in_progress). Builds on GE-127g-1, which replaced doc_length.excluded_files with declared set_aside_locations of {path, ground}. Changes: new helper templates/scripts/commit_guardian/_doc_length_set_aside.py, edits to check_doc_length.py and commit_guardian.json, plus tests under unit_tests/commit_guardian/."
breaking: false
---

## Entry

**Can generated documents grow without limit? No, in the sense that they are reported.**
A document in a set-aside location that is above that location's declared ceiling is named
on every commit that stages it. This is a report, not a refusal: the commit still completes.
Nothing here blocks a commit.

### GE-127g-5 (complete): a set-aside location is still bounded

`GE-127g-1` (already merged) replaced the basename list `doc_length.excluded_files` with
declared `set_aside_locations`, each a `{path, ground}`, so generated documents are not
judged by a limit written for hand-authored ones. That left those locations with no bound
at all. Now:

- Every `set_aside_locations` entry must also declare `report_above_lines`, a per-document
  size above which the run reports the document.
- The report gives the document's size, the ceiling, the headroom, and the source its
  ground names.
- An entry without `report_above_lines` is rejected, never given a default.
- It is named `report_above_lines` and not `max_lines` because it is a report threshold,
  not a refusal limit.

Declared ceilings: `docs/agents/cards/` 1500, `docs/roadmap.md` 1500, `docs/INDEX.md` 2000.

### GE-127g-2 (partial): what was set aside is reported

A run now states the judged and the set-aside documents as separate counts, names each
set-aside document with its declared ground, and no longer reports a set-aside document as
"within its limit". When everything staged is set aside, it says 0 judged rather than
implying compliance.

### Not done

`GE-127g-2-i` was not built, so `GE-127g-2` is recorded as `in_progress`, not `done`.
That child is the rule that an unreadable set-aside declaration is judged rather than
exempted. Until it is built, **a set-aside declaration that cannot be read is not yet
guaranteed to be judged**; it may still be exempted.

### Files

- New: `templates/scripts/commit_guardian/_doc_length_set_aside.py`
- Changed: `templates/scripts/commit_guardian/check_doc_length.py`,
  `templates/scripts/commit_guardian/commit_guardian.json`
- Tests: `unit_tests/commit_guardian/test_ge_127g_5.py`, `test_ge_127g_2.py`, and the
  shared fixture `_ge_127g_5_fixture.py`
