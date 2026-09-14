---
title: "A documentation-coverage check that crashed on every run now runs, and two files that were never hooks stop being counted as missing ones"
date: "2026-09-14"
time: "17:05"
type: manual
components: 
  - commit_guardian
summary: "Second pass on the KI-TQ-007 registration inventory: baseline 16 to 14. check_doc_coverage.py died with NameError on every invocation and now exits 0; check_outcome.py and check_v2_ac_store_alignment.py are recorded in hook_parity.excluded_scripts because neither is a pre-commit gate. Five further gates are verified ready but wait on a package-surface acceptance criterion."
description: "check_doc_coverage.py referenced an undefined _project_root at two call sites while the module binds project_root, so it raised NameError on every invocation regardless of input — one more than the single site previously reported. Fixed and verified exit 0 from the repository root and from a nested working directory; it stays unregistered because its output is advisory and lands on the passing path where a hook's stdout is discarded. check_outcome.py has no main() and no __main__ block at all: it is the GE-120 outcome vocabulary imported by run_hook.py, the dispatcher every registered hook runs through, plus three registered hooks, so it is the most-executed file in the directory and was flagged only because of its check_ prefix. check_v2_ac_store_alignment.py is invoked by the ac-validator agent with --ticket, not by pre-commit. Both are now listed in hook_parity.excluded_scripts with the reasoning recorded beside them. Five gates needing no code work — folder density, test fixture bloat, SQL complexity, debug scripts and post-merge AC closure — were built, deployed and exercised through the real entry point against a real staged set, all exit 0, with the reachability gate reporting no unreachable hooks; folder density was confirmed to classify the 109-file and 142-file directories in its own commit as pre-existing warnings rather than blocks. They are deferred rather than shipped because registering them adds package-registry entries, which the package-surface declaration gate refuses without a citing acceptance criterion that does not yet exist."
commits: 
  - c5e0a9c62
breaking: false
---

## Entry
