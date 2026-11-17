"""
MODULE: unit_tests/workflows/test_tq500g1vi_route_bytes.py
GOAL: RED test for TQ-500g-1-vi, the test-breaker reply reaches the writer byte for byte through the
    finish command that EACH twin (templates/workflows-js/build-feature.js, build-ticket.js) records.
BUSINESS CONTEXT: Each twin carries its own copy of the here-document builder (the engine has no module
    loader), so the real-shell check is repeated per twin. The recorded finish command is run by a REAL shell
    (Git bash on Windows) in a temp git repo with a temp AC store, against the real wrapper; the fixtures are the
    TQ-500g-1-v ones. Today neither twin dispatches the finish step, so the test fails on an assertion about the
    recorded dispatches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx  # noqa: E402
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix  # noqa: E402
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g  # noqa: E402
import unit_tests.build_orchestration._tq500g1x_fixtures as x  # noqa: E402
import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402


def test_finish_command_carries_reply_byte_for_byte(tmp_path: Path):
    # covers: TQ-500g-1-vi
    # angle: real_artifact
    # must_catch: reply expanded by the shell
    # must_catch: reply cut off at a line equal to the here-document delimiter
    nasty = "if refresh_due:  # $HOME `whoami` it's \"q\" \\ $(id) ${HOME}\nWV_REPLY_EOF\n    # WV_REPLY_EOF"
    raw = "{\"entries\": []}\nWV_REPLY_EOF\nWV_REPLY_EOF_X\nEOF\nEND\n$HOME `id` it's \"q\" \\\\ tail"
    for route in fx.ROUTES:
        root = tmp_path / route.key
        root.mkdir()
        sb = x.build(root)
        gitfx.write_ac_yaml(sb.work / "docs" / "acceptance-criteria", ix.AC_ID, x.test_spec())  # the route's fixed store path
        proc, listed = x.run_list(sb, base_ref="HEAD")
        assert proc.returncode == 0 and listed["error"] is None, listed
        entries = g.full_entries()
        entries[0] = ix.prep(x.N1, ("refresh_config.py", x.COND, nasty))
        reply = json.dumps(ix.reply_obj(entries, work_key=fx.STEM), indent=2, ensure_ascii=False) + "\n"
        expected = (sb.work / "refresh_config.py").read_bytes().decode("utf-8").replace(x.COND, nasty, 1).encode("utf-8")
        wt = sb.work.as_posix()
        replies = fx.wv_replies(route, list_=v.ran(listed), breaker=reply)
        result = fx.run_route(route, replies, wt=wt, source_ac=(ix.AC_ID,))
        finishes = fx.calls(result, route.finish)
        assert len(finishes) == 1, f"{route.key}: expected one {route.finish!r} dispatch, recorded labels: {fx.labels_of(result)}"
        status_before = gitfx.run_git(["status", "--porcelain"], cwd=sb.work)
        done = v.run_recorded(finishes[0], g.GATE, sb.work)  # the recorded command, in a real shell, with the real wrapper
        out = json.loads(done.stdout.decode("utf-8") or "null")
        assert isinstance(out, dict) and out["writer"]["written"] is True, (route.key, done.returncode, done.stdout[-300:], done.stderr[-300:])
        manifest = json.loads(Path(out["writer"]["manifest_path"]).read_text(encoding="utf-8"))
        files = {e["name"]: e["files"] for e in manifest["entries"]}[x.N1]
        assert Path(files[0]["altered_copy"]).read_bytes() == expected, f"{route.key}: the altered copy differs from the reply's replacement"
        assert gitfx.run_git(["status", "--porcelain"], cwd=sb.work) == status_before, f"{route.key}: a reply file was left in the working tree"
        left = [p.name for p in (sb.git_dir / "leafcutter").rglob("*") if "reply" in p.name.lower()]
        assert not left, f"{route.key}: a reply file was left in the work folder: {left}"
        # A valid JSON reply cannot hold a raw line equal to a delimiter, so the cut-off is proven with raw text:
        # whatever delimiter the command picks, a stand-in wrapper must read every line of it on stdin.
        again = fx.run_route(route, fx.wv_replies(route, list_=v.ran(listed), breaker=raw), wt=wt, source_ac=(ix.AC_ID,))
        script, saved = v.stdin_capture_gate(root)
        assert v.run_recorded(fx.calls(again, route.finish)[0], script, root).returncode == 0 and saved.is_file(), route.key
        assert saved.read_bytes().decode("utf-8").rstrip("\n") == raw, f"{route.key}: finish read {saved.read_bytes()!r} instead of the reply"
