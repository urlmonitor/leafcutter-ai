"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_review_scope.py
GOAL: RED regression tests for the review findings on the wrong-version runner's
    scope and wrong-version preparation (TQ-500g-1-i): a declared test that cannot
    be found, manifest paths that escape the worktree, caught rows as evidence, and
    "the fix undone" covering every non-test file except the AC store.
BUSINESS CONTEXT: Each test pins one finding and goes red on an ASSERTION today;
    behaviour that raises today is caught and asserted on, never left to escape.
ARCHITECTURE: Real git sandboxes (see _tq500g1_review_fixtures.py); the CLI is driven
    as a subprocess where the finding is about the CLI contract, the private modules
    in-process where it is about one function.
"""

from __future__ import annotations

import os

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1_review_fixtures as rv

ESCAPES = ["/Windows/win.ini", "\\Windows\\win.ini", "D:foo/x.py", "../outside.py", ".git/config",
           "sub/.git/config", ".GIT/config"]


def _declare(sb, entries):
    fx.gitfx.write_ac_yaml(sb.ac_root, fx.AC_ID, entries)


def test_declared_test_not_found_does_not_pass(tmp_path):
    # covers: TQ-500g-1-i
    # angle: failure
    # Catches: 'a declared must_catch entry whose test is missing (tag lost or function
    # renamed) is silently dropped, so the work passes with applicable false'.
    # Control: an AC naming no must_catch / discrimination entry stays applicable false, passed.
    sb = fx.build_sandbox(tmp_path / "a", tests=("T1",))
    _declare(sb, [{"name": "test_x", "must_catch": [fx.WV_DROP]}])
    proc, verdict = fx.run_runner(sb)
    invalid = [r for r in verdict["results"] if r["result"] == "invalid"]
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished", verdict
    assert proc.returncode == 1
    assert any("declared test not found" in r["detail"] and "test_x" in r["detail"] for r in invalid), invalid
    ctl = fx.build_sandbox(tmp_path / "ctl", tests=("T1",))
    _declare(ctl, [{"name": fx.T1}, {"name": fx.T3}])
    _proc, ctl_verdict = fx.run_runner(ctl)
    assert ctl_verdict["applicable"] is False and ctl_verdict["gate_passed"] is True


def test_safe_rel_rejects_rooted_drive_relative_and_git_paths(tmp_path):
    # covers: TQ-500g-1-i
    # angle: boundary
    # Catches: '_safe_rel only checks Path.is_absolute()/".."', which on Windows lets a rooted
    # path with no drive ("/Windows/win.ini"), a drive-relative path ("D:foo/x.py") and a path
    # through .git/ resolve outside the worktree or into git's own data.
    accepted = [raw for raw in ESCAPES if rv.scope_mod._safe_rel(tmp_path, raw) is not None]
    assert accepted == [], f"_safe_rel let these through: {accepted}"
    outside = tmp_path.parent / "sibling_dir_for_safe_rel"
    assert rv.scope_mod._safe_rel(tmp_path, str(outside / "x.py")) is None
    assert rv.scope_mod._safe_rel(tmp_path, "pkg/mod.py") == "pkg/mod.py"


def test_is_test_path_is_case_insensitive():
    # covers: TQ-500g-1-i
    # angle: boundary
    # Catches: 'test-directory guard compares case-sensitively', so "Unit_Tests/helpers.py"
    # or "Tests/data.json" on a case-insensitive filesystem is an editable non-test file.
    wrong = [p for p in ("Unit_Tests/helpers.py", "Tests/data.json", "TESTS/x.py", "__Tests__/y.js")
             if not rv.scope_mod.is_test_path(p, None)]
    assert wrong == [], f"treated as non-test files: {wrong}"
    assert rv.scope_mod.is_test_path("fx_tests/helpers.py", "FX_Tests") is True
    assert rv.scope_mod.is_test_path("src/app.py", None) is False


def test_manifest_path_outside_worktree_is_invalid_and_untouched(tmp_path):
    # covers: TQ-500g-1-i
    # angle: failure
    # Catches: 'a manifest path that resolves outside the worktree is applied', which alters (and
    # restores, bumping mtime) a file belonging to someone else. Uses the drive-less form of a
    # real sibling file, which is_absolute() accepts as relative on Windows.
    sb = fx.build_sandbox(tmp_path, tests=("T1",), t1_must_catch=(fx.WV_DROP,), new_file_only=True)
    outside = tmp_path / "outside_dir" / "victim.py"
    outside.parent.mkdir()
    outside.write_bytes(b"victim = 1\n")
    os.utime(outside, ns=(10**18, 10**18))
    before = (outside.read_bytes(), outside.stat().st_mtime_ns)
    raw = outside.as_posix()
    raw = raw[2:] if len(raw) > 2 and raw[1] == ":" else raw
    altered = tmp_path / "altered_victim.py"
    altered.write_bytes(b"victim = 2\n")
    rv.write_manifest(sb, fx.WV_DROP, [{"path": raw, "altered_copy": str(altered)}])
    _proc, verdict = fx.run_runner(sb)
    drop = fx.rows(verdict, fx.T1, fx.WV_DROP)
    assert [r["result"] for r in drop] == ["invalid"], drop
    assert (outside.read_bytes(), outside.stat().st_mtime_ns) == before, "a file outside the worktree was altered"
    assert verdict["gate_passed"] is False


def test_manifest_alteration_of_cased_test_dir_is_refused(tmp_path):
    # covers: TQ-500g-1-i
    # angle: failure
    # Catches: 'a manifest alteration of Unit_Tests/helpers.py passes the test-file guard and
    # is applied'. The real dir is lower-case; a case-insensitive filesystem resolves both.
    sb = fx.build_sandbox(tmp_path, tests=("T1",), t1_must_catch=(fx.WV_DROP,), new_file_only=True)
    helper = sb.work / "unit_tests" / "helpers.py"
    helper.parent.mkdir()
    helper.write_bytes(b"x = 1\n")
    rv.gitfx.commit_all(sb.work, "helper")
    altered = tmp_path / "altered_helper.py"
    altered.write_bytes(b"x = 2\n")
    rv.write_manifest(sb, fx.WV_DROP, [{"path": "Unit_Tests/helpers.py", "altered_copy": str(altered)}])
    _proc, verdict = fx.run_runner(sb)
    drop = fx.rows(verdict, fx.T1, fx.WV_DROP)
    assert [r["result"] for r in drop] == ["invalid"], drop
    assert "test file" in drop[0]["detail"], drop[0]["detail"]
    assert helper.read_bytes() == b"x = 1\n"


def test_all_caught_under_fix_undone_leaves_caught_rows_as_evidence(tmp_path):
    # covers: TQ-500g-1-i
    # angle: criterion
    # Catches: 'caught rows are dropped for tests that are not holders of the wrong version
    # being run', leaving results empty so verified is false although the gate passed.
    # Literal finding scenario (T1 names only the fix undone) plus the non-holder variant
    # (T1 names only a manifest wrong version and is ALSO caught by the fix undone, which runs
    # every in-scope test): in both, the fix undone must leave one caught row per test.
    for label, names, entries in (("alias", (fx.WV_ALIAS,), ()), ("non_holder", (fx.WV_DROP,), ("drop",))):
        sb = fx.build_sandbox(tmp_path / label, tests=("T1",), t1_must_catch=names, entries=entries)
        proc, verdict = fx.run_runner(sb)
        undone = [r for r in verdict["results"] if r["wrong_version"] == fx.WV_UNDONE]
        got = sorted(str(r["test"]).rsplit("::", 1)[-1] for r in undone if r["result"] == "caught")
        assert got == [fx.T1], f"{label}: one caught row per in-scope test for the fix undone: {verdict['results']}"
        assert verdict["gate_passed"] is True and verdict["verified"] is True, (label, verdict)
        assert proc.returncode == 0


_MD_TEST = '''\
import json
from pathlib import Path
WORK = {work!r}
LOG = {log!r}


def test_md_is_read():
    # covers: TQ-9101
    ac = Path(WORK, "docs", "acceptance-criteria", "c", "AC.yaml").read_bytes().decode()
    ctl = Path(WORK, "unit_tests", "ctl.txt").read_bytes().decode()
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"ac": ac, "ctl": ctl}}) + "\\n")
    assert Path(WORK, "templates", "agents", "x.md").read_bytes().decode() == "v2\\n"
'''


def test_fix_undone_covers_non_test_markdown_but_not_ac_store(tmp_path):
    # covers: TQ-500g-1-i
    # angle: discrimination
    # Catches: 'the fix undone skips every .md/.rst/.txt and docs/ file' (a test reading
    # templates/agents/x.md is then never caught), and the opposite wrong version, 'the fix undone
    # also reverts the AC store under --ac-root'. Control: a changed test file is never altered.
    state = tmp_path / "state"
    state.mkdir()
    log = state / "seen.jsonl"
    sb = rv.plain_sandbox(
        tmp_path, ac_rel="docs/acceptance-criteria",
        base={"templates/agents/x.md": "v1\n", "docs/acceptance-criteria/c/AC.yaml": "v: 1\n",
              "unit_tests/ctl.txt": "c1\n"},
        final={"templates/agents/x.md": "v2\n", "docs/acceptance-criteria/c/AC.yaml": "v: 2\n",
               "unit_tests/ctl.txt": "c2\n"},
        tests={"test_md.py": _MD_TEST.format(work=str(tmp_path / "work"), log=str(log))},
        must_catch={"test_md_is_read": [fx.WV_ALIAS]})
    proc, verdict = fx.run_runner(sb)
    rows = fx.rows(verdict, "test_md_is_read", fx.WV_UNDONE)
    assert [r["result"] for r in rows] == ["caught"], f"md not undone: {verdict['results']}"
    seen = fx.jsonl(log)
    assert seen and all(s == {"ac": "v: 2\n", "ctl": "c2\n"} for s in seen), f"AC store or test file altered: {seen}"
    assert (sb.work / "templates/agents/x.md").read_bytes() == b"v2\n"
    assert proc.returncode == 0 and verdict["gate_passed"] is True
