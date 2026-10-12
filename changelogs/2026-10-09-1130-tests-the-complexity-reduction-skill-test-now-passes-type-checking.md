---
title: "Tests: the complexity-reduction skill test now passes type-checking"
date: "2026-10-09"
time: "11:30"
type: manual
components: 
  - skills_system
summary: "The test that checks the complexity-reduction skill no longer fails the informational type-check job; what it checks is unchanged."
description: "unit_tests/test_complexity_reduction_skill.py (added in #1072, AC CR-100b-2) read .items() on a value mypy could only see as dict | int | None, so the informational mypy job reported two union-attr errors. The comparison loop now branches on the claim type (dict for Python labels, int for SQL labels) rather than the code-fence language. Behaviour is unchanged: a mutation check confirmed both branches still catch a wrong label."
commits: []
---

## Entry
