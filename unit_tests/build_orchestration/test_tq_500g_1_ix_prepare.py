"""
MODULE: test_tq_500g_1_ix_prepare
GOAL: TQ-500g-1-ix, first scenario, replies R1..R9: how the writer's ``write`` step
    turns the preparer's reply into entries, altered copies and diffs.
BUSINESS CONTEXT: Real sandbox repo + real AC store + json.dump replies
    (_tq500g1ix_fixtures); the writer is driven through its CLI only.
"""

from __future__ import annotations

import json

import unit_tests.build_orchestration._tq500g1ix_fixtures as ix


def test_r1_prepared_copy_is_code_as_written_but_the_one_replacement(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: criterion
    # Catches: altered copy re-serialised, with whitespace, quotes or the final newline changed
    # Catches: replacement applied to the working-tree file instead of a copy
    sb = ix.build_sandbox(tmp_path)
    as_written = sb.as_written("refresh_config.py")
    proc, out = ix.write_default(sb)
    assert proc.returncode == 0 and out["written"] is True, out
    e = ix.entry(ix.load_manifest(sb), ix.N1)
    assert e["status"] == "prepared" and e["reason"] is None
    assert [f["path"] for f in e["files"]] == ["refresh_config.py"]
    copy = ix.Path(e["files"][0]["altered_copy"])
    assert copy.is_absolute() and sb.copies_dir in copy.parents, f"copy {copy} not under {sb.copies_dir}"
    expected = as_written.replace(ix.COND.encode(), ix.COND_ALT.encode())
    assert expected != as_written, "fixture: the replacement must change the file"
    assert copy.read_bytes() == expected
    assert sb.as_written("refresh_config.py") == as_written, "the working-tree file was changed"
    assert len(ix.copy_files(sb)) == 1, "only R1 may leave a copy"


def test_r1_diff_is_computed_and_reply_diff_ignored(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: discrimination
    # Catches: the reply's own diff copied into the manifest
    sb = ix.build_sandbox(tmp_path)
    as_written = sb.as_written("refresh_config.py")
    proc, out = ix.write_default(sb)
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    e = ix.entry(m, ix.N1)
    copy_bytes = ix.Path(e["files"][0]["altered_copy"]).read_bytes()
    want = ix.expected_diff("refresh_config.py", as_written, copy_bytes)
    assert want.startswith("--- a/refresh_config.py\n+++ b/refresh_config.py\n")
    assert e["diff"] == want
    assert "WRONGDIFFMARK" not in json.dumps(m), "the reply's diff reached the manifest"
    assert e["diff"] != ix.WRONG_DIFF


def test_r2_r3_ambiguous_or_missing_old_text_is_could_not_prepare(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: boundary
    # Catches: the first of several matches replaced
    # Catches: missing old text skipped and the entry recorded prepared
    sb = ix.build_sandbox(tmp_path)
    assert sb.as_written("refresh_config.py").count(b"retry_due") == 3, "fixture: R2's old text occurs 3 times"
    proc, out = ix.write_default(sb)
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    ix.assert_refused(m, ix.N2, "old text found 3 times in refresh_config.py")
    ix.assert_refused(m, ix.N3, "old text not found in refresh_config.py")
    assert ix.entry(m, ix.N1)["status"] == "prepared", "control: the unambiguous R1 is prepared"
    assert len(ix.copy_files(sb)) == 1, "R2 and R3 left a copy"


def test_r4_r5_r6_refused_paths_leave_no_copy_at_all(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: failure
    # Catches: partial copy of refresh_config.py kept for R4
    # Catches: a path escaping the repository resolved and copied
    # Catches: a .git path accepted as a source file
    sb = ix.build_sandbox(tmp_path)
    outside = (tmp_path / "shared" / "refresh_config.py").read_bytes()
    hook = (sb.work / ".git" / "hooks" / "pre-commit").read_bytes()
    assert sb.as_written("refresh_config.py").count(b'return "skip"') == 1, "fixture: R4's old text occurs once"
    proc, out = ix.write_default(sb)
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    ix.assert_refused(m, ix.N4, "tests/test_refresh_config.py is a test file")
    ix.assert_refused(m, ix.N5, "../shared/refresh_config.py is outside the repository")
    ix.assert_refused(m, ix.N6, ".git/hooks/pre-commit is inside the version-control folder")
    assert [f.name for f in ix.copy_files(sb)] == ["refresh_config.py"], "only R1's copy may exist"
    assert ix.entry(m, ix.N1)["status"] == "prepared", "control: R1 is still prepared"
    assert (tmp_path / "shared" / "refresh_config.py").read_bytes() == outside
    assert (sb.work / ".git" / "hooks" / "pre-commit").read_bytes() == hook


def test_r9_out_of_scope_file_refused_and_no_copy_for_the_name(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: failure
    # Catches: any ordinary non-test file inside the repository accepted for every name
    # Catches: a file in scope for another name accepted for this name
    # Catches: in-scope files taken from the reply or the route instead of the test entries
    # Catches: partial copy of refresh_config.py kept for R9
    sb = ix.build_sandbox(tmp_path)
    assert sb.as_written("refresh_config.py").count(b'return "refresh"') == 1, "fixture: R9's old text occurs once"
    entries = [e for e in ix.default_entries() if e["name"] != ix.N7]
    entries.append(ix.prep(ix.N7, ("settings.py", "TIMEOUT = 5", "TIMEOUT = 0")))
    for e in entries:
        if e["name"] == ix.N9:
            e["in_scope_files"] = ["refresh_config.py", "settings.py"]
    proc, out = ix.write_default(sb, entries, in_scope_files={ix.N9: ["settings.py"]})
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    ix.assert_refused(m, ix.N9, 'settings.py is not in scope for "refresh from the settings file"')
    e7 = ix.entry(m, ix.N7)
    assert e7["status"] == "prepared" and [f["path"] for f in e7["files"]] == ["settings.py"]
    assert ix.Path(e7["files"][0]["altered_copy"]).read_bytes() == sb.as_written("settings.py").replace(
        b"TIMEOUT = 5", b"TIMEOUT = 0")
    assert sorted(f.name for f in ix.copy_files(sb)) == ["refresh_config.py", "settings.py"], (
        "exactly R1's refresh_config.py copy and R7's settings.py copy may exist")


def test_r7_reason_verbatim_and_r8_no_alteration_returned(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: criterion
    # Catches: an unanswered owed name dropped from the manifest
    sb = ix.build_sandbox(tmp_path)
    assert ix.N8 not in [e["name"] for e in ix.default_entries()], "fixture: R8 is unanswered"
    proc, out = ix.write_default(sb)
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    ix.assert_refused(m, ix.N7, "refresh_config.py has no timeout handling")
    ix.assert_refused(m, ix.N8, "no alteration returned")
    assert len(m["entries"]) == 9, f"{len(m['entries'])} entries for 9 owed names"
