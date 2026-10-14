---
title: "The set-aside population is exactly the declared locations, so a document a person writes is still judged however it is named or wherever it sits"
date: "2026-10-14"
time: "12:10"
type: manual
components:
  - commit_guardian
  - doc_compliance
summary: "Added tests proving that a hand-written document is still length-checked whatever it is called or wherever it sits, with no change to how the doc-length gate behaves."
description: "Closes GE-127g-3 as done with evidence only; no gate code changes and no behaviour change ships. The behaviour was already delivered by GE-127g-1 (merged in #1190): doc-length set-aside membership is by declared repo-relative path (a path ending / covers everything beneath it, otherwise one exact document), and the old basename-matched excluded_files key is gone. New unit_tests/commit_guardian/test_ge_127g_3.py adds four tests that each run the real check_doc_length.py against a throwaway git repo and assert the commit is refused and which documents are named. The tests passed before any code change, so they were checked by deliberately breaking the gate."
breaking: false
---

## Entry

Evidence for GE-127g-3. No behaviour change is shipped.

- The behaviour was already delivered by GE-127g-1 (merged in #1190). Doc-length set-aside membership is by declared repo-relative path. A path ending `/` covers everything beneath it, and any other path is one exact document. The old basename-matched `excluded_files` key is gone. No gate code changes in this entry.
- `unit_tests/commit_guardian/test_ge_127g_3.py` adds four tests. Each runs the real `check_doc_length.py` against a throwaway git repo and asserts the commit is refused and which documents are named:
  1. A hand-authored document carrying the generated `.card.md` suffix, outside the declared directory, is still judged.
  2. A `README.md` outside the declared locations is judged, even though a `README.md` inside one is set aside.
  3. One over-limit document per hand-authored directory under `docs/` (derived from the real tree at run time) is refused, and all are named.
  4. The judged population falls by exactly the number of staged documents inside the declared locations, and every reported set-aside document lies inside one.
- The tests passed before any code change, so they were checked by deliberately breaking the gate. Suffix-based membership, basename matching, setting aside all of `docs/`, and a hand-kept deny-list each turn at least one of the four tests red. The population test fails by its count, not by a crash, under basename matching and the deny-list.
- GE-127g-3 is marked `work_status: done`, with `implemented_by` filled by hand. The parent GE-127g stays `todo` because GE-127g-4 is unbuilt.
