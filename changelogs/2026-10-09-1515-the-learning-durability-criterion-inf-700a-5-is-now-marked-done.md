---
title: "The learning-durability criterion INF-700a-5 is now marked done"
date: "2026-10-09"
time: "15:15"
type: manual
components: 
  - knowledge_system
summary: "INF-700a-5 now reads done. It requires a captured learning to still be readable in the merged tree after the working directory it was written in is gone. Its three children are done, and each of its five test descriptors has a passing test that runs the production CLI."
description: "One AC-store commit (f4f565e2c), store data only. Flips INF-700a-5 work_status from todo to done. Its children INF-700a-5-i, INF-700a-5-ii (landed in #1100) and INF-700a-5-iii are all done on main, and covered_by lists exactly those three. Each of the five test_spec descriptors is covered by a passing test tagged covers: INF-700a-5 in unit_tests/workflows/test_inf_700a_5_cli.py, which runs scripts/knowledge/completion_routing_cli.py in a real subprocess. Adds completion_routing_cli.py, completion_routing_git.py, fast-lane-ship.js, quick-fix.js, finalize-feature.js and building-epics SKILL.md to implemented_by, and keeps the two existing entries. The parent INF-700a is not changed."
commits: 
  - f4f565e2c
breaking: false
---

## Entry

**INF-700a-5 now reads `done`.** It requires a learning written during a unit of work to
still be readable in the merged tree after that unit's working directory is removed.

- **Children:** INF-700a-5-i, INF-700a-5-ii (landed in #1100) and INF-700a-5-iii are all
  `done`.
- **Evidence:** each of the five `test_spec` descriptors has a passing `# covers: INF-700a-5`
  test in `unit_tests/workflows/test_inf_700a_5_cli.py`. The tests run the production CLI in
  a real subprocess.
- **`implemented_by`** now lists the CLI, the git helper, the three workflow callers
  (`fast-lane-ship.js`, `quick-fix.js`, `finalize-feature.js`) and building-epics `SKILL.md`.

The parent INF-700a is not changed. No code changes.
