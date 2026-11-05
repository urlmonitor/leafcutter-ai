# Test report

The test database check used the shipped checker against the project. It reported status `not_configured`:
no test database connection is configured, because testing_context.db_connection_test is not set.
The database tests for the stored procedure refresh_totals() were not run.

Set testing_context.db_connection_test in the project's skills_config.json, then run them again.
