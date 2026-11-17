## sql-test-writer Report

**SQL object**: sql_functions/functions/fn_refresh_due.sql
**Test file**: unit_tests/sql_functions/test_fn_refresh_due.py
**Framework**: unittest
**Slow-test marker**: _MANUAL

**Test cases authored**:
- test_case - the guarding test

**Database check**: {"status": "invalid", "setting": "testing_context.db_connection_test", "host": null, "port": null, "database": null, "message": "testing_context.db_connection_test is not a valid postgres connection URL (expected postgres:// or postgresql:// with a safe host, port, and database segment)."}
**Base ref used**: git merge-base HEAD origin/main
**Pre-fix run**: not run: the database check reported invalid, so no run was made; the setting is testing_context.db_connection_test
**Post-fix run**: not run: the database check reported invalid, so no run was made; the setting is testing_context.db_connection_test

**Three questions** (per guarding test; every answer labelled `observed` or `reasoned`):
- test_case - Q1: the smallest wrong change is dropping the retry_due condition; the test seeds retry_due false so it fails. [reasoned]
  Q2: a retry_due-false row makes fn_refresh_due return false, and the fixture seeds it. [reasoned]
  Q3: the control row passes for a different reason than the negative row fails: no. [reasoned]
- Vacuity checklist: exact count done / control row done / distinct new inputs done / collaborator call-count not applicable: a SQL function has no collaborator
- Wrong versions the tests now catch: fn_refresh_due without the retry_due condition [reasoned]

**To run later**: fn_refresh_due without the retry_due condition (test_retry_due_gate)

**Syntax check**: OK
