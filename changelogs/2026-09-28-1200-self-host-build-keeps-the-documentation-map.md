---
title: "The self-hosting build no longer replaces the documentation map with an empty stub"
date: "2026-09-28"
time: "12:00"
type: manual
components:
  - build_pipeline
summary: "build.py's doc-index step now builds docs/INDEX.md from the repository that contains the configured docs_root folder, not from the build target. In the self-hosting layout (target = workspace parent, docs_root = leafcutter-ai/docs/) every build used to overwrite the tracked leafcutter-ai/docs/INDEX.md with a stub whose every section read 'No docs found.'. The step also refuses to replace a map that lists entries with one that lists none: it leaves the file unchanged, warns with the folder it scanned, and returns 0. Consumer installs (docs_root 'docs/') produce the same map as before. Covers BP-1500a-1."
description: "WHY. build_doc_index wrote to <target>/<docs_root>/INDEX.md but called generate_index(target_root). generate_doc_index's categories are 'docs/...' paths, so it scanned <target>/docs/. The workspace parent has no docs/ tree, so all nine categories came back empty, and the build reported 'wrote leafcutter-ai/docs/INDEX.md' and exited 0. Reproduced on 2026-09-27 as 11 insertions and 202 deletions. Recorded as KI-BP-016, KI-BP-001 and KI-BP-20260907-1620. FIX (scripts/build.py only). The scan root is now the parent of the docs_root folder when that folder is named 'docs'. That parent is the repository the generator's contract expects, so link text and the preserved created/last_updated dates come from the right index. For the default docs_root it is the target root, so consumer output is unchanged. If docs_root does not end in a 'docs' folder, the old scan root is kept and a warning is emitted. Fail-safe: if the generated map has no entry links and the existing map has at least one, nothing is written. A read or write OSError is warned about and never aborts the build. The counted line total of build.py is unchanged, so the check-file-size ratchet passes. EVIDENCE. unit_tests/build_guards/test_bp_1500a_1_doc_index_scan_root.py has 3 tests: self-host layout, consumer layout and fail-safe. Red on the unfixed code (2 failed, 1 passed), green after the fix. Reverting build.py to HEAD makes the same 2 fail again, and disabling only the fail-safe fails the fail-safe test. The existing doc-index tests all pass: 36 passed, 3 skipped for layout reasons. In a scratch copy of the self-hosting layout, the fixed step reproduces the tracked docs/INDEX.md byte for byte (252 lines, 0 'No docs found.', created 2026-08-11 preserved)."
commits: [ef0a633b]
breaking: false
---

## Entry

Running the documented self-hosting build no longer destroys the project's
documentation map.

- **Scan root fixed.** The doc-index step builds `INDEX.md` from the repository
  that holds the configured `docs_root` folder. Before, it used the build target.
  In the self-hosting layout, that is the workspace parent, which has no docs.
- **Fail-safe.** A map that lists entries is never replaced by one that lists
  none. The build leaves the file alone and warns, naming the folder it scanned.
- **Consumers unaffected.** With the default `docs_root: docs/`, the map is the
  same as before.

Covers BP-1500a-1. Addresses KI-BP-016, KI-BP-001 and KI-BP-20260907-1620.
