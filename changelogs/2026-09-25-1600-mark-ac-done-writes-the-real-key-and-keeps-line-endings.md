---
title: "Marking an AC done now changes the record's own work_status key and nothing else"
date: "2026-09-25"
time: "16:00"
type: manual
components:
  - ac_store
summary: "mark_ac_done.py could report `marked <ID> work_status=done` and exit 0 after editing prose that quoted `work_status: todo`, leaving the real key `todo`. On Windows it also rewrote every line from LF to CRLF. It now changes only the top-level key, keeps each line's ending, and checks the result before reporting success."
description: "The done write in scripts/ac_store/mark_ac_done.py did an unanchored raw_text.replace('work_status: todo', 'work_status: done', 1). On a record whose notes or criteria block quoted that text above the real key, it edited the prose, left the key todo, and still printed success. read_text/write_text also applied default newline translation, so on Windows every LF line became CRLF. The new _set_work_status_done helper matches only a column-0 `work_status:` line and refuses more than one. It reads and writes with newline='' so each line keeps its own ending, and writes through a same-directory temp file and os.replace. It then re-parses the file with yaml.safe_load; if work_status does not read done, the tool exits 1 with an error. This mirrors _fl_lifecycle._update_ac_work_status and does not import it. AC ACS-200f-3; tests in unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py drive the real CLI against CRLF and LF records. Reverting the fix turns all three tests red. Resolves KI-ACS-20260925-mark-ac-done-reports-success-without-writing-the-key for mark_ac_done.py. approve_acs.py has the same unanchored pattern for readiness and is not changed here."
commits: [506dc074]
breaking: false
---

## Entry

`mark_ac_done.py` is the tool that CLAUDE.md and `build-ac` name for marking an
AC done. Its write edited the first `work_status: todo` it found anywhere in the file. When
a record's prose quoted that text above the real key, the tool changed the
prose, left the key `todo`, and printed `marked <ID> work_status=done` with
exit 0. On Windows the same write also changed every line ending from LF to CRLF.

The write now:

- edits only a top-level `work_status:` line at column 0, and refuses a file
  with more than one;
- keeps every other byte unchanged, including each line's own ending (a CRLF
  file stays CRLF, an LF file stays LF);
- writes through a temp file in the same directory and `os.replace`, so a failed
  write never truncates the record;
- re-parses the file and exits 1 with an error unless `work_status` reads
  `done`.

AC `ACS-200f-3` (an L3 under `ACS-200f`). Tests:
`unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py`.

Still open: `scripts/ac_store/approve_acs.py` has the same unanchored replace
for `readiness: reviewed`. The known issue's larger fix, one shared
`set_field` helper used by every AC writer, is also not done here.
