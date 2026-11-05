"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_round2_scanner.py
GOAL: Second-review tests of the CREATE-statement scanner of TQ-500g-2-i, in process.
BUSINESS CONTEXT: ``_wvr_sql_objects.parse_objects`` decides which database objects a SQL file
    defines; E'' strings, DEFAULT $$..$$ values, DO blocks and identifier folding must not fool it.
"""

from __future__ import annotations

import pytest

import unit_tests.build_orchestration._tq500g2i_fixtures as fx


@pytest.fixture
def parse(monkeypatch):
    monkeypatch.syspath_prepend(str(fx.fx2.SCRIPTS / "build_orchestration"))
    import _wvr_sql_objects  # noqa: PLC0415 -- importable only once the directory is on the path

    return _wvr_sql_objects.parse_objects


def test_escape_string_before_create_does_not_break_parsing(parse):
    # covers: TQ-500g-2-i
    # angle: boundary
    # Catches: a scanner treating E'...\'...' as ending at the escaped quote, leaving a '$$' in the
    # string to open a phantom dollar region that swallows the real CREATE.
    text = "SELECT E'it\\'s $$ not a body';\nCREATE FUNCTION real_fn() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$;\n"
    assert parse(text) == {"real_fn": "SELECT 1"}


def test_default_dollar_quoted_in_signature_is_not_the_body(parse):
    # covers: TQ-500g-2-i
    # angle: boundary
    # Catches: taking the first dollar-quoted text after CREATE (the DEFAULT) as the body.
    text = "CREATE FUNCTION f(a text DEFAULT $$d$$) RETURNS text LANGUAGE sql AS $$ SELECT a $$;\n"
    assert parse(text) == {"f": "SELECT a"}


def test_following_do_block_is_never_the_function_body(parse):
    # covers: TQ-500g-2-i
    # angle: discrimination
    # Catches: the body search running on to a later DO block and taking its body as the function's.
    # Control: the same function WITH its own dollar-quoted body next to a DO block parses to that body.
    own = "CREATE FUNCTION g() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$;\nDO $$ BEGIN PERFORM 1; END $$;\n"
    assert parse(own) == {"g": "SELECT 1"}
    quoted_body = "CREATE FUNCTION g() RETURNS int LANGUAGE sql AS 'SELECT 1';\nDO $$ BEGIN PERFORM 1; END $$;\n"
    with pytest.raises(ValueError):  # ObjectsError: a body that is not dollar-quoted is not identifiable
        parse(quoted_body)


def test_unquoted_identifiers_fold_ascii_only_and_allow_dollar(parse):
    # covers: TQ-500g-2-i
    # angle: boundary
    # Catches: str.lower() folding non-ASCII letters (A-grave) and \w-only names cutting 'f$1' at '$'.
    text = ("CREATE FUNCTION ÀBc() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$;\n"
            "CREATE FUNCTION f$1() RETURNS int LANGUAGE sql AS $$ SELECT 2 $$;\n")
    assert parse(text) == {"Àbc": "SELECT 1", "f$1": "SELECT 2"}
