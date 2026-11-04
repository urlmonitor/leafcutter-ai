The `testing_context.db_connection_test` setting is indeed absent from `.claude/skills_config.json` — only `test_command` is set.

## Database Not Configured

`testing_context.db_connection_test` is not configured. Set it in this project's skills_config.json before running database tests.

I can't run the `refresh_totals()` SQL suite until that's added. Add a `db_connection_test` entry (host/port/database/credentials reference) to `.claude/skills_config.json`, and I can re-run the check and the suite right after.