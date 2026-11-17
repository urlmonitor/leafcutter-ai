"""
MODULE: test_tq_500g_1_ix_review
GOAL: TQ-500g-1-ix regressions found in review: duplicate in-scope files listed once,
    and replies the JSON reader or the writer cannot handle (a lone surrogate, extreme
    nesting) stopping the step with the named error and the JSON shape.
BUSINESS CONTEXT: Real sandbox repo + real AC store + json replies
    (_tq500g1ix_fixtures); the writer is driven through its CLI only.
"""

from __future__ import annotations

import json

import unit_tests.ac_store.test_tq_500g_1_ix_in_scope_files as scope_t
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix

_UNREADABLE = "the preparer's reply could not be read:"


def _dup_spec(sb) -> None:
    """Rewrite the TQ-9101 store so one entry lists refresh_config.py twice."""
    spec = ix.ac_test_spec()
    spec[0]["in_scope_files"] = ["refresh_config.py", "refresh_config.py", ix.TEST_FILE]
    ix.gitfx.write_ac_yaml(sb.ac_root, ix.AC_ID, spec)


def test_duplicate_in_scope_file_and_duplicate_ac_id_are_listed_once(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: boundary
    # Catches: duplicate in_scope_files entries listed twice
    sb = ix.build_sandbox(tmp_path)
    _dup_spec(sb)
    for ids in (ix.AC_ID, f"{ix.AC_ID},{ix.AC_ID}"):
        proc, out = ix.run_writer(sb, "list", ac_ids=ids)
        assert proc.returncode == 0 and out["error"] is None, out
        files = {o["name"]: o["files"] for o in out["owed"]}
        assert len(files) == 9
        assert files[ix.N1] == ["refresh_config.py"], f"{ids}: {files[ix.N1]}"
        assert files[ix.N7] == ["refresh_config.py", "settings.py"], f"{ids}: {files[ix.N7]}"


def _assert_stopped(sb, proc, out) -> None:
    assert proc.returncode == 1, (proc.returncode, proc.stderr[-300:])
    assert list(out) == ix.EXPECTED_KEYS, out
    assert out["written"] is False and out["manifest_path"] is None, out
    assert out["error"] is not None and out["error"].startswith(_UNREADABLE), out["error"]
    assert not sb.manifest_path.exists() and ix.copy_files(sb) == []


def test_lone_surrogate_reply_is_unreadable_not_a_traceback(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: failure
    # Catches: UnicodeEncodeError escaping the write step
    sb = ix.build_sandbox(tmp_path)
    bad = ix.prep(ix.N1, ("refresh_config.py", ix.COND, "\ud800"))
    path = ix.write_reply(sb, json.dumps(ix.reply_obj([bad])))
    _assert_stopped(sb, *ix.run_writer(sb, "write", reply=path))
    reason = ix.cnp(ix.N2, "bad \ud800 reason")
    path = ix.write_reply(sb, json.dumps(ix.reply_obj([reason])), "r2.json")
    _assert_stopped(sb, *ix.run_writer(sb, "write", reply=path))


def test_deeply_nested_reply_is_unreadable_not_a_traceback(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: failure
    # Catches: RecursionError escaping the JSON reader
    sb = ix.build_sandbox(tmp_path)
    path = ix.write_reply(sb, "[" * 200000)
    _assert_stopped(sb, *ix.run_writer(sb, "write", reply=path))


def test_schema_refuses_duplicate_in_scope_files_items(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: boundary
    # Catches: in_scope_files accepted with a repeated path
    assert scope_t._validate(tmp_path, "unique", in_scope_files=["a.py", "b.py"]) == 0
    assert scope_t._validate(tmp_path, "dup", in_scope_files=["a.py", "a.py"]) == 1
