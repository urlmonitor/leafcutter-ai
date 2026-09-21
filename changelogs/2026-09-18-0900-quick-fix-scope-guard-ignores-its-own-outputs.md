---
title: "The quick-fix scope guard no longer halts on the workflow's own outputs"
date: "2026-09-18"
time: "09:00"
type: manual
components:
  - build_pipeline
summary: "A /quick-fix run used to halt with 'scope expansion' although only the target file had changed, because the fix agent reported the workflow's own new AC, its parent AC and the new test as extra files. Those three paths are now excluded, the workflow also snapshots which files were already dirty before the fix agent runs, and a genuinely unexpected path still halts."
description: "In templates/workflows-js/quick-fix.js, the Fix phase asks the fix agent to report everything git status shows, and the scope-expansion guard then trusted that list verbatim. By the time the phase runs, the AC written in the AC Creation phase, the parent AC it was back-linked into, and the test written in the Red Phase are always dirty, so every run halted on them: a real run on 2026-09-17 halted naming INF-1300c.yaml, INF-1300c-5.yaml and test_adr_index_frontmatter_preserved.py while python-coder had touched only the target file. The prompt now names those three paths as expected additions, and the guard normalises paths (separator, leading ./, worktree-absolute against repo-relative) and filters the same three out of both extra_files and modified_files, excluding target_file too. The halt condition is the union of what survives, so an agent that claims expansion without naming an unexpected path no longer halts the run, while an unnamed expansion visible in modified_files still does. SKILL.md, the other surface of this workflow, already specified this behaviour and now cites the AC. AC BP-600e-1-ii; four tests in unit_tests/workflows/test_quick_fix_scope_guard_artifact_exclusion.py drive the workflow through the engine harness rather than grepping the script, covering both that the artifacts do not halt and that a genuine third-party file and an unnamed expansion still do. quick-fix.js stays under its 1000-line limit at 995 content lines."
commits:
breaking: false
---

## Entry

`/quick-fix` no longer stops itself. The scope-expansion guard used to count the AC, the
parent AC and the test file that the workflow had just written as unexpected changes, so
every run halted before the green phase. Those paths are now excluded from the check,
while a file the workflow did not create still halts the run.
