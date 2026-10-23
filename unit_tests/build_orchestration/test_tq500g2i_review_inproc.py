"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_review_inproc.py
GOAL: Review-fix tests M-3, M-4 and the deterministic credentials check of TQ-500g-2-i, all in
    process: the session's temp files, the CREATE-statement reader and the plugin's written output.
BUSINESS CONTEXT: Each of these is decided by one function of ``_wvr_db`` / ``_wvr_db_plugin``, so
    the module is imported from the runner's directory and called with real inputs (a real git
    project for the credentials test, the stand-in driver imported as ``psycopg2``).
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import types
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500g2i_fixtures as fx
import unit_tests.build_orchestration._tq500g2i_review_fixtures as rv

RUNNER_DIR = fx.fx2.SCRIPTS / "build_orchestration"
SQL_FILE = "db/fn.sql"


@pytest.fixture
def modules(monkeypatch):
    """``(_wvr_db, _wvr_db_plugin, _wvr_scope, NodeSpec)`` imported from the runner's directory."""
    monkeypatch.syspath_prepend(str(RUNNER_DIR))
    monkeypatch.syspath_prepend(str(fx.fx2.SCRIPTS))
    import _wvr_db  # noqa: PLC0415 -- importable only once the directory is on the path
    import _wvr_db_plugin  # noqa: PLC0415
    import _wvr_scope  # noqa: PLC0415
    from _wvr_pytest import NodeSpec  # noqa: PLC0415

    return _wvr_db, _wvr_db_plugin, _wvr_scope, NodeSpec


def test_m3_second_temp_file_failure_removes_the_first_and_installs_nothing(tmp_path, monkeypatch, modules):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'the config temp file is left behind (and handed to the pytest child as the plugin config)
    # when the output temp file cannot be created'. Control: the first mkstemp call really succeeded
    # (the call count is 2) and the private temp directory ends empty.
    db_mod, _plugin, scope, node_spec = modules
    root = tmp_path / "repo"
    (root / "db").mkdir(parents=True)
    (root / SQL_FILE).write_text(fx.AS_WRITTEN, encoding="utf-8")
    private = tmp_path / "private_tmp"
    private.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(private))
    real, seen = tempfile.mkstemp, []

    def second_fails(*args, **kwargs):
        seen.append(1)
        if len(seen) == 2:
            msg = "no space left on device"
            raise OSError(msg)
        return real(*args, **kwargs)

    monkeypatch.setattr(tempfile, "mkstemp", second_fails)
    test = scope.ScopedTest(node_spec(file=root / "t.py", chain=("test_x",)), "t.py::test_x", "test_x")
    session = db_mod.begin(root, {SQL_FILE: fx.WRONG_DROP.encode("utf-8")}, [test], {"test_x"})
    assert len(seen) == 2, f"expected the config and the output file to be asked for, got {len(seen)} calls"
    assert session.problem and session.active, "the session must report a problem"
    assert session.child is None, "a session with a problem must not hand a plugin config to the pytest child"
    assert list(private.iterdir()) == [], f"temp files left behind: {[p.name for p in private.iterdir()]}"


def test_m4_create_inside_comments_and_dollar_bodies_is_not_an_object(modules):
    # covers: TQ-500g-2-i
    # angle: boundary
    # Catches: 'every textual CREATE FUNCTION is an object' (a line comment, a block comment and an
    # EXECUTE 'CREATE FUNCTION ...' inside a dollar-quoted body each made a phantom object or an error).
    # Control: the two real functions are found, with their whole bodies.
    _db, plugin, _scope, _node = modules
    text = (
        "-- CREATE FUNCTION commented_out() RETURNS int AS $$ SELECT 0 $$ LANGUAGE sql;\n"
        "/* CREATE OR REPLACE FUNCTION in_a_block_comment() RETURNS int\n   AS $$ SELECT 0 $$ LANGUAGE sql; */\n"
        "CREATE OR REPLACE FUNCTION real_one() RETURNS text LANGUAGE plpgsql AS $body$\nBEGIN\n"
        "    EXECUTE 'CREATE FUNCTION made_at_run_time() RETURNS int AS $$ SELECT 1 $$ LANGUAGE sql';\n"
        "    RETURN 'x';\nEND\n$body$;\n"
        "CREATE FUNCTION real_two() RETURNS int LANGUAGE sql AS $$ SELECT 2 $$;\n"
    )
    try:
        found = plugin.parse_objects(text)
    except plugin.ObjectsError as exc:
        pytest.fail(f"the real objects of the source were refused as ambiguous (ObjectsError {exc})")
    assert sorted(found) == ["real_one", "real_two"], f"objects found: {sorted(found)}"
    assert "made_at_run_time" in found["real_one"] and found["real_one"].endswith("END"), found["real_one"]
    assert found["real_two"] == "SELECT 2"


class _Imports:
    """Put the stand-in driver dir first on the import path, and give back every module afterwards."""

    NAMES = ("psycopg2", "standin_pg")

    def __init__(self, driver_dir: Path) -> None:
        self.driver_dir = str(driver_dir)

    def __enter__(self) -> None:
        self.saved = {n: sys.modules.pop(n) for n in self.NAMES if n in sys.modules}
        self.path = list(sys.path)
        sys.path.insert(0, self.driver_dir)

    def __exit__(self, *_exc: object) -> None:
        for name in self.NAMES:
            sys.modules.pop(name, None)
        sys.modules.update(self.saved)
        sys.path[:] = self.path


def test_plugin_output_file_never_holds_credentials_in_process(tmp_path, monkeypatch, modules, caplog):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'driver error text (it holds the address and the password) copied into the findings file'.
    # Deterministic: no poller, no timing -- the plugin session runs here, the stand-in raises on the
    # catalogue read (event logged), and the file the plugin wrote is read back and scanned.
    _db, plugin, _scope, _node = modules
    address = fx.address_for(5999)
    proj = rv.build(tmp_path / "proj", address=address)
    config, output = tmp_path / "config.json", tmp_path / "output.json"
    wrong, original = plugin.parse_objects(fx.WRONG_DROP), plugin.parse_objects(fx.AS_WRITTEN)
    objects = {n: {"original": original[n], "wrong": wrong[n]} for n in original}
    ident = Path(proj.work / fx.TEST_FILE).resolve().as_posix() + "::" + fx.TEST
    config.write_text(json.dumps({"root": str(proj.work), "install": [fx.WRONG_DROP], "objects": objects,
                                  "restore": [fx.AS_WRITTEN], "read": True, "db_tests": [ident]}), encoding="utf-8")
    for key, value in {**proj.extra_env, "TQ_G2I_EVENTS": proj.events, "TQ_G2I_CATALOG": proj.catalog, "TQ_G2I_FAIL_READ": "1",
                       plugin.CONFIG_ENV: config, plugin.OUTPUT_ENV: output}.items():
        monkeypatch.setenv(key, str(value))
    item = types.SimpleNamespace(path=proj.work / fx.TEST_FILE, nodeid=f"{fx.TEST_FILE}::{fx.TEST}")
    caplog.set_level(logging.DEBUG)
    with _Imports(proj.driver_dir):
        session = plugin._Session()  # noqa: SLF001 -- the plugin's own session object
        session.start()
        session.capture(item)
    written = output.read_text(encoding="utf-8")
    assert any(e.get("ev") == "read_raised" for e in fx.events(proj)), "the stand-in never raised on the read"
    assert json.loads(written)["tests"][ident][0]["state"] == "unreadable", written
    assert not rv.leaked(address, 5999, written, caplog.text), f"credentials in the plugin output or log: {written}"
