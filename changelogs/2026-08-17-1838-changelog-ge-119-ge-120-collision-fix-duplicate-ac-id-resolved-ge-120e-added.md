---
title: "Changelog GE-119/GE-120 collision fix — duplicate AC id resolved, GE-120e added"
date: "2026-08-17"
time: "18:38"
type: manual
components: 
  - ac_store
  - commit_guardian
summary: "Fixed two different acceptance-criteria records that had silently ended up sharing the same id, and wrote down a check-attribution bug found while doing that work, so the tracking store stays trustworthy. No hooks, scripts, or tests were changed."
description: "1 commit (fc2316fdf), AC store only, no production code or tests. main carried two unrelated ACs both titled GE-119 at different paths, so git never conflicted and both merged silently: guardrail-engine/GE-119.yaml (L2 leaf, 'the contract-shrinking guard distinguishes an edited test from a deleted one') keeps GE-119, since it has 16 live '# covers: GE-119' tags across two test files plus a check_contract_shrinking.py reference and renaming would break done-proof linkage. The 32-file L0 tree at guardrail-engine/GE-119-green-means-checked/ (authored hours earlier, no code/test/ticket references) is renumbered to GE-120 across all ids, covered_by, depends_on, in-prose references, files and the folder, with cross-reference updates in ACS-1200, ACS-1200a, ACS-1200a-2 and both PROJECT_CONTEXT.md files. Also adds a new L1 GE-120e ('A block is always about something you actually did') plus 10 L2/L3 children, specifying a defect observed while merging origin/main during the PR #445 run: check_contract_shrinking.py:180 and check_doc_frontmatter.py:287 both derive their change set via `git diff --cached` under pass_filenames: false, which is HEAD-to-index — on a merge commit this returns the incoming branch's entire changeset attributed to whoever is merging, so contract-shrinking blocked over tests only main deleted and doc-frontmatter blocked over main's tickets diff, both needing SKIP= on a commit that introduced neither problem. GE-120e is deliberately a false-positive axis (a check blames the wrong author), distinct from GE-120a-d's false-negative axis (a check passes silently). Tree is now 43 records (1 L0 + 5 L1 + 25 L2 + 12 L3), all readiness: approved, priority: high, all carrying a test contract. Specifications only — the git diff --cached attribution defect is described by the new ACs, not fixed. The two prior changelog entries mentioning GE-119 (PR #445 and earlier) are left untouched as historical records of what shipped under the old id."
commits: 
  - fc2316fdf
breaking: false
---

## Entry
