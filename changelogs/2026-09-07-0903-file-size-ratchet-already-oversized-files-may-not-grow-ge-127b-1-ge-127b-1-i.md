---
title: "File-size ratchet: already-oversized files may not grow (GE-127b-1, GE-127b-1-i)"
date: "2026-09-07"
time: "09:03"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "The file-size guardrail gains a rule that a file already over its length limit can be shrunk or left alone but never made bigger, though this check is still not switched on for real commits yet."
description: "Adds templates/scripts/commit_guardian/_file_size_ratchet.py and extends check_file_size.py: a covered files previous length is read from its HEAD git blob with the same line-counting function used on the staged content, so the two cannot drift, and no baseline is persisted. Growth beyond that previous length is refused; a file with no previous length is out of scope. Unreachable or uninterpretable history refuses with a named reason and exit 2 (INDETERMINATE); a history with no covered file yet, or a commit staging only newly-added covered files, completes and is named distinctly (EMPTY HISTORY) from those two refusals. The outcome always states how many files were compared, including zero. Also fixes get_staged_files(), which previously died with an uncaught error in a non-git working copy and now reports the unreachable-source verdict instead. The check-file-size gate is still not registered in the pre-commit config and does not yet run on real commits; this change implements the ratchet behaviour and its tests only."
breaking: false
---

## Entry

Implements `GE-127b-1` and `GE-127b-1-i`, the growth ratchet for the `check-file-size`
commit gate.

**Behaviour added.** A covered file that already stands above its permitted length may
not be made longer by a staged change: growth is refused, while leaving the file the
same length or shorter — even while it remains over the limit — is allowed. The file's
previous length is read from its blob at `HEAD` in the repository's own history, measured
with the exact same shared function (`count_content_lines`) used to measure the staged
content, so the two measurements cannot drift apart. Nothing is persisted as a baseline
anywhere, so nothing can go stale. A file with no previous length (newly added) is out of
scope for the ratchet and is never treated as having previously stood at zero lines.

**Two named refusals, one exit code.** When the previous-length history cannot be
reached at all, or is reached but cannot be interpreted, the run refuses with a distinct
named reason and exit code 2 (`INDETERMINATE`).

**Two completions, named apart from the refusals and from each other.** A history that
holds no covered file yet, and a commit that stages only newly-added covered files, both
complete — the first is named `EMPTY HISTORY` in the outcome, in wording distinct from
both refusals, so an empty history can never be mistaken for a broken lookup. The outcome
always states how many files were compared against a previous length, including when
that count is zero, and a count of zero does not by itself refuse.

**Also fixed while implementing this:** `get_staged_files()` previously had no exception
handling around its `git diff --cached` call and died with an uncaught
`CalledProcessError` in a non-git working copy; it now reports the unreachable-source
`INDETERMINATE` verdict instead.

New file `templates/scripts/commit_guardian/_file_size_ratchet.py`; `check_file_size.py`
extended to use it. Covered by `unit_tests/commit_guardian/test_ge_127b_1.py` and
`test_ge_127b_1_i.py`.

**Not shipped by this change:** the `check-file-size` gate itself is still not
registered in the pre-commit config and still does not run on real commits — that is a
separate acceptance criterion (`GE-127a-1`) not yet built. This entry is the ratchet
behaviour and its tests only; no file is protected from growth on a real commit yet. The
`GE-127` AC tree itself is not new here either — it and its criteria merged separately in
PR #688.
