"""
MODULE: test_tq_500g_1_x_write
GOAL: TQ-500g-1-x, the writer's ``write`` step and the runner: the derived scope is
    enforced on replacements and manifest entries, one function gives every name the same
    files, a missing base ref stops the steps, and at most one git diff runs.
BUSINESS CONTEXT: Real git sandbox + real AC store + json.dump replies; the writer and
    the runner are CLIs driven as subprocesses. Git invocations are counted from git's own
    trace2 event log (GIT_TRACE2_EVENT), never by mocking the code under test.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1x_fixtures as x

SCRIPTS = Path(ix.WRITER).parent
REPL_N2 = (("refresh_config.py", x.COND, "if refresh_due and True"),)
OUT_OF_SCOPE = 'settings.py is not in scope for "ignore retry_due"'


def _prep_all(sb, listed: dict[str, dict]) -> list[dict]:
    """One replacement per file the list shows for each name (the files the write step must accept)."""
    edit = {"refresh_config.py": (x.COND, x.COND_ALT), "settings.py": ("RETRY_LIMIT = 3", "RETRY_LIMIT = 1"),
            "retry_policy.py": ("RETRY_ATTEMPTS = 3", "RETRY_ATTEMPTS = 1")}
    return [ix.prep(name, *((f, *edit[f]) for f in item["files"])) for name, item in listed.items()]


def test_write_refuses_a_replacement_outside_the_derived_scope(tmp_path):
    # covers: TQ-500g-1-x
    # angle: failure
    # Catches: any non-test file of the repository accepted for a name with derived scope
    # Catches: the write step ignoring --base-ref and deriving scope against HEAD
    sb = x.build(tmp_path)
    entries = [ix.prep(x.N2, ("refresh_config.py", x.COND, "if refresh_due and True")),
               ix.prep(x.N9, ("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1"))]
    proc, out = x.run_write(sb, entries)
    assert proc.returncode == 0 and out["written"] is True, (proc.returncode, out)
    assert list(out) == ix.EXPECTED_KEYS and all("scope" not in e for e in out["entries"]), out
    manifest = ix.load_manifest(sb)
    assert all("scope" not in e for e in manifest["entries"]), "the manifest carries no scope key"
    prepared = ix.entry(manifest, x.N2)
    assert prepared["status"] == "prepared" and [f["path"] for f in prepared["files"]] == ["refresh_config.py"]
    ix.assert_refused(manifest, x.N9, 'settings.py is not in scope for "refresh from the settings file"')
    assert [p for p in ix.copy_files(sb) if "refresh-from-the-settings-file" in p.as_posix()] == []


def test_derived_scope_still_refuses_test_outside_and_vcs_paths(tmp_path):
    # covers: TQ-500g-1-x
    # angle: failure
    # Catches: a test file the work changed accepted for a name with derived scope
    # Catches: the path checks skipped when the scope is derived
    sb = x.build(tmp_path)
    cases = [(x.TEST_FILE, f"{x.TEST_FILE} is a test file", "def test_retry_limit_stays_three"),
             (x.SHARED_REL, f"{x.SHARED_REL} is outside the repository", x.COND),
             (x.HOOK_REL, f"{x.HOOK_REL} is inside the version-control folder", "exit 0")]
    for path, reason, old in cases:
        proc, out = x.run_write(sb, [ix.prep(x.N2, (path, old, "changed"))])
        assert proc.returncode == 0 and out["written"] is True, (path, proc.returncode, out)
        ix.assert_refused(ix.load_manifest(sb), x.N2, reason)
        assert ix.copy_files(sb) == [], f"a copy was made for {path}"


def test_list_write_and_runner_give_every_name_the_same_files(tmp_path):
    # covers: TQ-500g-1-x
    # angle: seam
    # Catches: the runner applying a manifest entry whose file is outside the name's scope
    # Catches: the write step reusing an earlier list output for scope
    # Catches: the runner deriving scope against HEAD instead of its --base-ref
    sb = x.build(tmp_path)
    shown = x.listed(sb)
    proc, out = x.run_write(sb, _prep_all(sb, shown))
    assert proc.returncode == 0, (proc.returncode, out)
    manifest = ix.load_manifest(sb)
    for name, item in shown.items():
        got = ix.entry(manifest, name)
        assert got["status"] == "prepared", (name, got)
        assert sorted(f["path"] for f in got["files"]) == sorted(item["files"]), (name, got["files"], item["files"])
    x._wb(sb.work / "late_change.py", "LATE = 1\n")  # the work changes between the list and the write
    proc, out = x.run_write(sb, [ix.prep(x.N2, ("late_change.py", "LATE = 1", "LATE = 2"))])
    late = ix.entry(ix.load_manifest(sb), x.N2)
    assert late["status"] == "prepared", f"the write step reused the earlier list: {late}"
    hand = x.hand_manifest(sb, {x.N2: [("refresh_config.py", x.COND, x.COND_ALT),
                                       ("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")]})
    proc, verdict = x.run_runner(sb, hand)
    rows = [r for r in verdict["results"] if r["wrong_version"] == x.N2]
    assert verdict["gate_passed"] is False and rows, verdict
    assert all(r["result"] == "invalid" for r in rows), rows
    assert all(OUT_OF_SCOPE in r["detail"] and "not prepared" in r["detail"] for r in rows), rows
    assert all("refresh_config.py is not in scope" not in r["detail"] for r in rows), "scope derived against HEAD"


def test_empty_derived_scope_refuses_and_the_gate_does_not_pass(tmp_path):
    # covers: TQ-500g-1-x
    # angle: failure
    # Catches: a name with an empty derived scope treated as owing nothing so the gate passes
    control = x.build(tmp_path / "control")
    proc, ok = x.run_runner(control, x.full_manifest(control))
    assert ok["gate_passed"] is True, f"control: a complete in-scope manifest must pass: {ok['reason']} {ok['unfinished']}"
    sb = x.build(tmp_path / "t", shape="test_only")
    entries = [ix.prep(x.N1, ("refresh_config.py", x.COND, x.COND_ALT)),
               ix.prep(x.N3, ("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")),
               ix.prep(x.N2, *REPL_N2),
               ix.prep(x.N9, ("refresh_config.py", 'return "refresh"', 'return "skip"'))]
    proc, out = x.run_write(sb, entries)
    assert proc.returncode == 0 and out["written"] is True, (proc.returncode, out)
    manifest = ix.load_manifest(sb)
    ix.assert_refused(manifest, x.N2, 'refresh_config.py is not in scope for "ignore retry_due"')
    assert ix.entry(manifest, x.N1)["status"] == "prepared" and ix.entry(manifest, x.N3)["status"] == "prepared"
    proc, verdict = x.run_runner(sb, sb.manifest_path)
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished", verdict
    assert x.N2 in [u["wrong_version"] for u in verdict["unfinished"]], verdict["unfinished"]
    assert proc.returncode == 1


def test_missing_base_ref_stops_list_and_write_with_an_error_naming_it(tmp_path):
    # covers: TQ-500g-1-x
    # angle: failure
    # Catches: a missing base ref read as no changed files
    # Catches: a missing base ref read as the whole repository
    # Catches: names with declared scope still listed when the base ref is missing
    sb = x.build(tmp_path)
    proc, out = x.run_list(sb, base_ref=x.NO_REF)
    assert proc.returncode == 1 and out["owed"] == [], (proc.returncode, out)
    assert x.NO_REF in out["error"] and "does not exist" in out["error"], out["error"]
    sb.work_dir.mkdir(parents=True)
    sb.manifest_path.write_text("{}", encoding="utf-8")  # a stale manifest an earlier preparation left
    entries = [ix.prep(x.N1, ("refresh_config.py", x.COND, x.COND_ALT)), ix.prep(x.N2, *REPL_N2)]
    proc, out = x.run_write(sb, entries, base_ref=x.NO_REF)
    assert proc.returncode == 1 and out["written"] is False and out["manifest_path"] is None, (proc.returncode, out)
    assert x.NO_REF in out["error"] and "does not exist" in out["error"], out["error"]
    assert not sb.manifest_path.exists(), "no manifest may be left on disk"


def test_at_most_one_git_diff_per_invocation(tmp_path):
    # covers: TQ-500g-1-x
    # angle: boundary
    # Catches: one git diff per unscoped name
    # Catches: the runner diffing once for the fix undone and again for the scope check
    sb = x.build(tmp_path / "full")
    trace = tmp_path / "list.trace"
    out = x.listed(sb, trace=trace)  # two unscoped names: N2 and N9
    assert out[x.N2]["files"] == out[x.N9]["files"] == ["refresh_config.py", "retry_policy.py"]
    assert x.git_commands(trace).count("diff") == 1, x.git_commands(trace)
    declared = x.build(tmp_path / "declared", declared_only=True)
    trace = tmp_path / "declared.trace"
    out = x.listed(declared, base_ref=x.NO_REF, trace=trace)  # succeeds although the ref does not resolve
    assert sorted(out) == sorted([x.N1, x.N3])
    seen = x.git_commands(trace)
    assert seen and "diff" not in seen, f"trace must show git ran, and no diff: {seen}"
    trace = tmp_path / "runner.trace"
    hand = x.hand_manifest(sb, {x.N2: [("refresh_config.py", x.COND, x.COND_ALT),
                                       ("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")]})
    proc, verdict = x.run_runner(sb, hand, trace=trace)
    assert any(OUT_OF_SCOPE in r["detail"] for r in verdict["results"]), "the scope check must have run"
    assert any(r["wrong_version"] == "the fix undone" for r in verdict["results"]), "the fix undone must have run"
    assert x.git_commands(trace).count("diff") == 1, x.git_commands(trace)


def test_fix_undone_unchanged_by_the_shared_diff_helper(tmp_path):
    # covers: TQ-500g-1-x
    # angle: seam
    # Catches: the fix undone treating untracked files as changed files to restore
    # Catches: the fix undone dropping a deleted file once deletions leave the shared helper's output
    snippet = ("import json, sys\nfrom pathlib import Path\nfrom _wvr_scope import prepare_fix_undone\n"
               "files, state, detail = prepare_fix_undone(Path(sys.argv[1]), sys.argv[2], None, None)\n"
               "print(json.dumps({'files': {k: v.decode() for k, v in files.items()}, 'state': state, 'detail': detail}))\n")

    def undone(sb) -> dict:
        proc = subprocess.run([sys.executable, "-c", snippet, str(sb.work), sb.base_sha], cwd=SCRIPTS,
                              capture_output=True, text=True, timeout=120, env=x.env())
        assert proc.returncode == 0, proc.stderr[-400:]
        return json.loads(proc.stdout.strip().splitlines()[-1])

    sb = x.build(tmp_path / "full")
    got = undone(sb)
    assert got == {"files": {"refresh_config.py": x.BASE_SRC, "legacy_refresh.py": x.LEGACY}, "state": "ready",
                   "detail": ""}, got
    assert (sb.work / "retry_policy.py").read_bytes() == x.RETRY_POLICY.encode(), "the added file stays in place"
    new = undone(x.build_all_new(tmp_path / "new"))
    assert new["state"] == "not_applicable" and new["files"] == {}, new
    assert new["detail"] == "every changed non-test file is new (2 created); the fix undone does not apply", new
    derived = set(x.listed(sb)[x.N2]["files"])  # the derived scope reads the same changes
    assert derived & set(got["files"]) == {"refresh_config.py"}, (derived, sorted(got["files"]))
    assert "legacy_refresh.py" not in derived and "retry_policy.py" in derived


def test_write_cli_takes_base_ref_and_feeds_the_runner(tmp_path):
    # covers: TQ-500g-1-x
    # angle: reachability
    sb = x.build(tmp_path)
    entries = [ix.prep(x.N1, ("refresh_config.py", x.COND, x.COND_ALT)),
               ix.prep(x.N3, ("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")),
               ix.prep(x.N2, *REPL_N2),
               ix.prep(x.N9, ("refresh_config.py", 'return "refresh"', 'return "skip"'))]
    proc, out = x.run_write(sb, entries)
    assert proc.returncode == 0 and list(out) == ix.EXPECTED_KEYS and out["written"] is True, (proc.returncode, out)
    assert [e["status"] for e in out["entries"]] == ["prepared"] * 4, out["entries"]
    proc, verdict = x.run_runner(sb, Path(out["manifest_path"]))
    assert verdict["gate_passed"] is True and proc.returncode == 0, (verdict["reason"], verdict["unfinished"])
    status = gitfx.run_git(["status", "--porcelain"], cwd=sb.work).splitlines()
    # exact path match: tests/test_refresh_config.py is always modified in this sandbox
    assert not [ln for ln in status if ln[3:].strip() == "refresh_config.py"], status
