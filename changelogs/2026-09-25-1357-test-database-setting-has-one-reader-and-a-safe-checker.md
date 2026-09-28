---
title: "The test database setting has one reader and a checker that never shows a password"
date: "2026-09-25"
time: "13:57"
type: manual
components:
  - infrastructure
  - testing_quality
summary: "New scripts/db_check/checker.py is the only code that reads testing_context.db_connection_test. An unset or blank setting is an error that names the setting, never a guess or a skip. The checker CLI reports not_configured, invalid, config_error, unreachable or reachable as JSON, and never prints a password, userinfo or the raw configured value."
description: "Fast-lane build of INF-1100d-3-i and INF-1100d-3-ii (branch fast-lane/inf-1100d-3-ii), orchestrated manually after the fast-lane workflow's own dispatches were refused. resolve_test_db_address() raises a named error for unset or blank values before any driver import or connection; check_test_db() calls it (one reader) and does a bounded TCP probe. Addresses are accepted only through an allowlist (postgres scheme, safe host with RFC 1035 length limits or IPv6 literal, port 1-65535, plain database name); anything else is reported as invalid with a fixed message. Invalid JSON or non-UTF-8 skills_config.json is reported as config_error, not a traceback. db_check is added to the build's deployed script dirs. Four review rounds closed credential leaks for scheme-less, doubled-scheme and ;password= suffix values and crashes for invalid JSON, non-UTF-8 config and over-long DNS labels; each has a regression test."
commits:
breaking: false
---

## Entry

Leafcutter now has exactly one place that reads the test database setting. If a project has
not set it, a database test stops with an error that says which setting is missing, instead
of connecting to an address that belongs to someone else. A small checker reports whether
the setting is missing, malformed, unreadable, unreachable or working, and it never prints
the password or the address as written.
