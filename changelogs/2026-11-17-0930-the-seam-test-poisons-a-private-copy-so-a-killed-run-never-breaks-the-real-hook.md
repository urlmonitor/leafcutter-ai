---
title: "The GE-120e-1 seam test poisons a private copy, so a killed run never leaves the real hook broken"
date: "2026-11-17"
time: "09:30"
type: manual
components:
  - testing_quality
summary: "Test D of the GE-120e-1 suite used to write an always-raising stub into the real templates/scripts/commit_guardian/_authored_change.py and put the original back in a finally block, which a SIGKILL, an OOM kill or a crashed xdist worker never reaches. It now poisons a private copy of the checks in a temporary directory and runs the copied checks, so it writes nothing into the repository. New AC GE-120e-1-iii is covered by three new tests, including one that kills test D while the stub is in place and checks the real file and git status are unchanged."
description: "Test-only change, no production code. make_private_guardian_copy() in test_ge_120e_1_boundary_and_seam.py copies templates/scripts/commit_guardian/ (real files, no __pycache__) to <tempdir>/scripts/commit_guardian/ and puts scripts/frontmatter_path_resolver.py beside it, because frontmatter_validators.py looks for that module next to commit_guardian/ first and a temporary directory has no project root to fall back to. Test D writes its stub into the copy and runs the copied check_contract_shrinking.py and check_doc_frontmatter.py from the same merge fixture; each check imports _authored_change as a sibling, so the copies load the poisoned copy. Test D keeps its name, its covers tag and its four assertions. The new test_ge_120e_1_iii_test_d_isolation.py runs test D as a separate process with a private TMPDIR: once to completion while polling, asserting the stub was only ever in the copy, test D passed, and the real module's sha256 and mtime_ns and git status of templates/ did not change; and once killed with SIGKILL at the moment the stub is in place, asserting the same. A third test runs both checks from the unpoisoned copy and from the repository and requires identical exit status and output, so test D's could-not-check evidence can only come from the poison. Before the fix the two process tests were red: the killed run left _authored_change.py modified in the working tree. GE-120e-1 lists the new AC in covered_by. test_tq100a_2.py's identity-write scan also reads the new file."
adrs: []
commits: []
breaking: false
---

## Entry
