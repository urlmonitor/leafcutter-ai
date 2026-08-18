---
title: "TKT-600a-1 — fix files_touched over-extraction and depends_on passthrough in ticket generator"
date: "2026-08-18"
time: "09:44"
type: ticket_completion
components: 
  - ac_store
summary: "Fixed the automated ticket-generation tool so it stops mistaking illustrative example file paths for real edits and no longer produces invalid ticket dependency links, delivered as the first acceptance criterion built fully end-to-end by the new automated fast-lane build pipeline."
description: "1 commit (feat) fixing two independent defects in scripts/ac_store/generate_ticket_from_ac.py, both observed live during the BO-2600 build: (1) files_touched over-extraction now gates prose-derived path tokens on real on-disk existence via new _resolve_worktree_root_or_none/_is_real_prose_path helpers, so illustrative example paths in it_requirements bullets no longer pollute files_touched; (2) depends_on now drops the AC structural parent and translates remaining sibling AC-id dependencies into co-located ticket filenames (or [] otherwise) via _build_ticket_depends_on, so ticket_frontmatter_guard no longer rejects verbatim AC-id passthrough. Covered by 4 new tests in tests/ac_store/test_tkt_600a_1_depends_on_and_files_touched.py. Also notable: this is the first AC built end-to-end by the /fast-lane-build automated pipeline (worktree, resolve, claim, test-writer, red-baseline gate, coder, green/coverage gate, commit, PR), made possible by the BO-2400a-3 red-baseline amendment shipped in v4.0.0."
pr: 465
commits: 
  - 19eca859a
breaking: false
ticket: "TKT-600a-1"
---

## Entry
