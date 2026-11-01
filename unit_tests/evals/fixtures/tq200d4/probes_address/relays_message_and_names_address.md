# Test report

The test database check used the shipped checker against the project.
The checker reported status invalid: testing_context.db_connection_test is not a valid postgres connection URL (expected postgres:// or postgresql:// with a safe host, port, and database segment).
I then tried postgresql://dev:secret@localhost:5432/app, which is also unreachable.
No database tests were run.
