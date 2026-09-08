---
title: "GE-127b-2 — merge-aware previous-length resolution stops an inherited file being judged as newly authored"
date: "2026-09-08"
time: "10:15"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - ac_store
summary: "Merging in a branch that already contains a long-standing oversized file no longer gets wrongly refused as if that file were brand new."
description: "Fixes the file-size ratchet's previous-length lookup (_file_size_ratchet.py) to also consult the merge's other parent (MERGE_HEAD) when a file has no HEAD history, not only the literal HEAD ref. Previously HEAD alone was checked, so during a merge a file long-standing on origin/main but absent from the branch's pre-merge tip resolved to no previous length, fell through to the absolute-limit branch, and was refused as newly authored even though the GE-127b-1 ratchet exists precisely to allow already-oversized files to persist. _read_head_blob_bytes was generalised to _read_ref_blob_bytes(ref, filepath), and new _merge_in_progress()/_merge_parent_shas() helpers detect an in-progress merge exclusively from git state (MERGE_HEAD), never from commit message or env flags. The ordinary non-merge path is unchanged, a file absent from BOTH parents is still refused as new, and a merge that itself edits a file into oversize is still caught. Verified behaviourally via a real merge in a fixture repository (unit_tests/commit_guardian/test_ge_127b_2.py), mutation-proved red-before/green-after under AC_ENFORCE_STRICT=1. AC docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127b-2.yaml added; GE-127b.yaml parent updated."
commits: 
  - 767b18a5136fed3639fdbf617044479269f45d40
breaking: false
---

## Entry
