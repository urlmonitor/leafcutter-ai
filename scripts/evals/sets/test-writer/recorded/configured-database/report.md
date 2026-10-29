# Completion report

Tests written: test_refresh_totals_returns_the_totals_rows, in test_configured_database.py.

The test takes its connection from the project's setting through resolve_test_db_address, and names
no host, port or database of its own. It rolls back in tearDown.
