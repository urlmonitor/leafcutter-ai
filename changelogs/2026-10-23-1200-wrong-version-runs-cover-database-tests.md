---
title: "Wrong-version runs now cover database tests: the configured test database is checked first, the catalogue proves which version was installed, and the database test writer runs its tests through the shared runner"
date: "2026-10-23"
time: "12:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "The shared wrong-version runner checks the configured test database once per run and reports database tests as not run, never caught, when it is not reachable. A pytest plugin reads the database catalogue after each test so a wrong version only counts when the database really held it, and the put-back re-checks the database and stops the drive when it cannot be verified. The database test writer (sql-test-writer) now runs its tests through the same runner, labels each answer observed or reasoned, and hands extra wrong versions on through a to-run-later file whose survivors never block."
description: "TQ-500g-2, TQ-500g-2-i, TQ-500g-2-ii. Runner: _wvr_db.py (one check_test_db call per run; every non-reachable status fails closed; no address handled or printed), _wvr_extras.py (one reader of <git-dir>/leafcutter/to-run-later/<ac-id>.json shared by wrong_version_writer.py list and the runner; extras never block; new always-present verdict key non_blocking_survivors), _wvr_db_plugin.py (-p plugin in the single pytest child: installs the SQL wrong version, one catalogue read per test on its own connection; invalid when the suite put the correct code back, not_run when no driver, unreadable or neither version), _wvr_sql_objects.py (CREATE FUNCTION/PROCEDURE outside comments and quoted text; body after AS; ASCII-only folding). Put-back re-installs and re-checks; a failed, differing or unverifiable put-back stops the drive. Prompt: templates/agents/sql-test-writer.md (database check first, runner call with no --alterations/--record, verify_red_baseline when test-first, # covers tags, resolve_test_db_address example, to-run-later file). User decisions OQ-1 to OQ-5 (2026-10-22). Known limits: the real catalogue query is not proven in CI; a re-install inside the test's own open transaction and a catch made only in setup read as not_run. Review findings fixed test-first; wrong-version gates passed for -ii (11 names) and -i (8 names)."
commits:
breaking: false
---

## Entry

Tests that need the database are now held to their wrong versions too. Before, a database
test could look like it caught a wrong version when the database never held it, or when no
database was configured at all. Now the runner checks the configured test database first,
reads the database catalogue to prove which version each test really ran against, and puts
the original code back and re-checks it after every run. The database test writer uses the
same runner, so its "the test caught it" claims are backed by a quoted run.
