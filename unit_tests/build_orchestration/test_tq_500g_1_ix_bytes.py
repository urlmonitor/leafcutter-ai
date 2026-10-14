"""
MODULE: test_tq_500g_1_ix_bytes
GOAL: TQ-500g-1-ix, byte-level rules of the writer's ``write`` step (CRLF checkouts,
    sequential replacements) and the CLI reaching the shared runner end to end.
BUSINESS CONTEXT: Real sandbox repo + real AC store + json.dump replies
    (_tq500g1ix_fixtures); the writer and the runner are driven through their CLIs.
"""

from __future__ import annotations

import subprocess
import sys

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix


def test_crlf_checkout_lf_old_matches_and_copy_keeps_crlf(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: boundary
    # Catches: CRLF file rewritten with LF line endings
    # Catches: LF old text refused as not found on a CRLF checkout
    sb = ix.build_sandbox(tmp_path, crlf=True)
    as_written = sb.as_written("refresh_config.py")
    assert as_written.count(b"\n") == as_written.count(b"\r\n") > 3, "fixture: a uniformly CRLF checkout"
    old = ix.COMMENT_LINE + "    if refresh_due and retry_due:\n"
    new = ix.COMMENT_LINE + "    if refresh_due:\n"
    proc, out = ix.write_default(sb, [
        ix.prep(ix.N1, ("refresh_config.py", old, new)),
        ix.prep(ix.N8, ("refresh_config.py", 'return "skip"', 'return "skip."'))])
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    e1, e8 = ix.entry(m, ix.N1), ix.entry(m, ix.N8)
    assert e1["status"] == "prepared" and e8["status"] == "prepared", (e1, e8)
    copy1 = ix.Path(e1["files"][0]["altered_copy"]).read_bytes()
    want1 = as_written.replace(old.replace("\n", "\r\n").encode(), new.replace("\n", "\r\n").encode())
    assert want1 != as_written and copy1 == want1, "the CRLF copy must differ from as-written only by the replaced text"
    assert copy1.count(b"\n") == copy1.count(b"\r\n"), "a bare LF crept into the CRLF copy"
    copy8 = ix.Path(e8["files"][0]["altered_copy"]).read_bytes()
    assert copy8 == as_written.replace(b'return "skip"', b'return "skip."'), "control: a one-line old keeps CRLF too"
    assert "\r" not in e1["diff"] and e1["diff"] == ix.expected_diff("refresh_config.py", as_written, copy1)
    assert sb.as_written("refresh_config.py") == as_written


def test_sequential_replacements_in_one_file_all_or_nothing(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: boundary
    # Catches: second replacement matched against the code as written instead of the first result
    sb = ix.build_sandbox(tmp_path)
    as_written = sb.as_written("refresh_config.py")
    ok = ix.prep(ix.N8, ("refresh_config.py", 'return "refresh"', 'return "refresh_a"'),
                 ("refresh_config.py", 'return "refresh_a"', 'return "refresh_b"'))
    broken = ix.prep(ix.N3, ("refresh_config.py", 'return "refresh"', 'return "skip"'),
                     ("refresh_config.py", 'return "skip"', 'return "x"'))
    assert as_written.count(b'return "skip"') == 1 and as_written.count(b'return "refresh_a"') == 0
    proc, out = ix.write_default(sb, [broken, ok])
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    e8 = ix.entry(m, ix.N8)
    assert e8["status"] == "prepared" and e8["reason"] is None, f"the second old exists only after the first: {e8}"
    assert ix.Path(e8["files"][0]["altered_copy"]).read_bytes() == as_written.replace(
        b'return "refresh"', b'return "refresh_b"')
    ix.assert_refused(m, ix.N3, "old text found 2 times in refresh_config.py")
    assert len(ix.copy_files(sb)) == 1, "the failed name must leave no copy, not even its first replacement"


def test_writer_cli_end_to_end_feeds_the_runner(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: reachability
    # surface_invoked: python scripts/build_orchestration/wrong_version_writer.py write
    sb = ix.build_sandbox(tmp_path)
    reply = ix.write_reply(sb, ix.reply_obj(ix.default_entries()))
    proc, out = ix.run_writer(sb, "write", reply=reply)
    assert proc.returncode == 0, proc.stderr
    assert list(out) == ix.EXPECTED_KEYS and out["written"] is True and out["error"] is None, out
    assert [(e["name"], e["status"]) for e in out["entries"]][0] == (ix.N1, "prepared")
    assert all(set(e) == {"name", "status", "reason"} for e in out["entries"])
    assert ix.Path(out["manifest_path"]).is_absolute() and ix.Path(out["manifest_path"]).is_file()
    runner = subprocess.run(
        [sys.executable, str(ix.RUNNER), "run", "--ac-ids", ix.AC_ID, "--test-root", str(sb.work),
         "--ac-root", str(sb.ac_root), "--base-ref", "HEAD", "--alterations", out["manifest_path"]],
        cwd=sb.work, capture_output=True, text=True, timeout=420, env=ix._env())
    verdict = ix.parse_one_json(runner, "runner")
    r1 = fx.rows(verdict, ix.CLAIM_TEST, ix.N1)
    assert [r["result"] for r in r1] == ["caught"], f"the runner did not apply the written R1 copy: {r1}"
    r2 = fx.rows(verdict, wv=ix.N2)
    assert r2 and all(r["result"] == "invalid" for r in r2), r2
    assert all("old text found 3 times in refresh_config.py" in r["detail"] for r in r2), r2
    assert verdict["gate_passed"] is False, "could_not_prepare names leave the work unfinished"
