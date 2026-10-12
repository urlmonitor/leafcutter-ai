---
title: "Skills: the complexity-reduction skill the complexity checks tell you to use now ships with the package"
date: "2026-10-09"
time: "12:00"
type: manual
components: 
  - skills_system
  - commit_guardian
  - review_system
summary: "Projects now receive a complexity-reduction skill that explains what the Python and SQL complexity checks count, how to measure a score, and which refactorings lower it, with every example score checked against the real checker."
description: "The check-complexity and check-folder-density refusals, and the python-coder instructions, all told authors to use a complexity-reduction skill that the package never shipped. It is now a portable template at templates/skills/complexity-reduction/SKILL.md, registered in config/skill_registry.json and deployed to .claude/skills/. Ported from the Bybit-Trader project's skill, with every score re-measured against the shipped checkers. Errors corrected: guard clauses do not lower the score, a comprehension's if filter is not counted, a nested def does not reset the count, and IF ... IS NULL to COALESCE saves 1 point, not 2. Hard-coded limits were replaced by the commit_guardian.json settings: the source said SQL 65, the package ships 75. The skill states that check-complexity is not in the default hook manifest. AC CR-100b-2, with unit_tests/test_complexity_reduction_skill.py recomputing every labelled score."
commits: []
---

## Entry

### What you get

When `check-sql-complexity` refuses a commit, or a refusal tells you to "use the complexity-reduction skill", that skill is now installed at `.claude/skills/complexity-reduction/SKILL.md`. It gives:

- what each checker counts: Python per function, SQL per file, including keywords that count where you might not expect them (`END IF`, `CREATE OR REPLACE`, `BETWEEN ... AND`, words inside a `RAISE NOTICE` message);
- commands that print this project's limits and measure a function's or a file's score;
- six Python and seven SQL techniques, each before/after pair labelled with the score the real checker gives it.

### Not changed

- `check-complexity` (Python) is still not in the default hook manifest. The skill says so.
- The folder-density refusal still names this skill. The skill does not cover crowded folders and says so; whether that refusal should keep naming it is GE-120h-5's call.
