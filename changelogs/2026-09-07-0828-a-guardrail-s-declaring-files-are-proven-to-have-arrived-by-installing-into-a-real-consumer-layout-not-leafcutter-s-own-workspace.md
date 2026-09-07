---
title: "A guardrail's declaring files are proven to have arrived by installing into a real consumer layout, not leafcutter's own workspace"
date: "2026-09-07"
time: "08:28"
type: manual
components: 
  - build_pipeline
summary: "Added a check that installs the software into a separate, realistic customer-style project layout and confirms every file a safety guardrail depends on actually arrived, catching the exact kind of missing-file bug that has quietly broken an adopter's commits five times before."
description: "Implements BP-900h-4 and BP-900h-4-i, the consumer-simulation half of the deployment-completeness work. Every build test to date installed into leafcutter's own self-hosted workspace, where the package source tree sits beside the deployed output root, so a missing declaring file resolves anyway -- that layout, not the checks, is what let five declaring files go missing unnoticed on 2026-08-18 and let an adopter hit KI-BP-003 for a fifth time. Adds scripts/ci/_declaring_files_scan.py (AST recognition primitives: a file-anchored ancestor-walk config-literal scan, and an underscore-prefixed helper-module import scan) and scripts/ci/_declaring_files_derivation.py (file-walk orchestration -- parse, derive_inventory, merge_inventory, find_missing), backing the new scripts/ci/check_declaring_files.py CLI that CI invokes with --deployed-root for a single-layout inspection and --layout-set for a sweep across real adopter layouts. The inventory is derived from what the deployed guardrails actually read, not hand-typed -- a typed list is the defect this AC exists to remove, since it would pass its own tests the day it was written and rot immediately after. scripts/build_phases.py gains _deploy_commit_guardian_config_files, shipping config/doc_types.json, config/diagram_types.json and config/agent_registry.json, three of the five files missing since 2026-08-18. The layout fixtures build real consumer installs with a real git clone --local and a real git worktree add rather than a copied tree, because a copied tree reproduces neither the trigger nor the defect."
commits: 
  - 159d1fb66
breaking: false
---

## Entry

### The layout under test was the thing that was wrong

A guardrail is only useful if the files it depends on actually arrive in the project
that installed it. Until now, every build test proved that by installing into
leafcutter's **own** workspace — where the package source tree sits right beside the
deployed output, so a file the build forgot to ship resolves anyway, from the source
copy next door.

That is not an install. It is the one layout in which the bug cannot appear. Five
declaring files were confirmed missing from a deployed output root on 2026-08-18 with
every build test green, and an adopter hit the same class of failure a fifth time when
`config/doc_types.json` never shipped and the document-frontmatter guardrail crashed on
every commit touching a doc with frontmatter.

### What now runs

CI installs the package into a scratch project that is **not** a descendant of the
package checkout, then walks a declaring-file inventory against it and reports each
missing file together with the guardrail that reads it and the location it was expected
at. `check_declaring_files.py` runs it in two modes: a single-layout inspection, and a
sweep across several real adopter layouts — because the same lookup fails differently
depending on what the package directory is called, which is why two earlier field
reports appeared to contradict each other and were in fact both correct.

The inventory is **derived** from what the deployed guardrails actually read. A
hand-written list would pass its own tests on the day it was written and begin rotting
immediately, which is the failure this replaces rather than repeats.

### Two details worth keeping

The layout fixtures build their consumer installs with a real `git clone --local` and a
real `git worktree add`, never a copied directory. A copy reproduces neither the trigger
nor the defect — the submodule-in-a-worktree case in particular only exists because git
populates worktrees differently from checkouts.

`build_phases.py` also now ships `config/doc_types.json`, `config/diagram_types.json`
and `config/agent_registry.json`. Those three are the regression set this inspection has
to be able to catch, not the point of it: deploying named files fixes the instance,
while the derived inventory is what stops the next one.
