"""
MODULE: db_check
GOAL: Package marker for the shipped test-database checker module.
BUSINESS CONTEXT: db_check.checker is the ONE reader of
    testing_context.db_connection_test (INF-1100d-3-i / INF-1100d-3-ii) --
    the pre-run reachability CLI and the Step 2b DB-test pattern's resolver
    both live behind this single package so "blank means not configured"
    can only be decided in one place.
ARCHITECTURE: checker.py is the single module with public symbols
    (resolve_test_db_address, check_test_db, and a CLI entry point); this
    __init__.py is a pure package marker with no public symbols.
"""

# DECISION HISTORY
# ================================================================================
# - 2026-09-25 [python-coder]: Created db_check package for the shared test-
#   database checker/resolver module. (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
