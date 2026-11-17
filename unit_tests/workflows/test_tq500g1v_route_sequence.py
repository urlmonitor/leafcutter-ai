"""
MODULE: unit_tests/workflows/test_tq500g1v_route_sequence.py
GOAL: RED tests for TQ-500g-1-v, the ORDER and CONTENT of the wrong-version dispatches that
    templates/workflows-js/fast-lane-ship.js makes between the Review phase and the commit dispatch:
    list step, test-breaker, one finish call.
BUSINESS CONTEXT: Every test runs the TEMPLATE under unit_tests/_workflow_engine_harness.py and
    asserts on the recorded dispatches, never on the source text. Today the workflow dispatches none
    of the new steps, so each test fails on an assertion about the recorded dispatches. The labels
    these tests pin are in _tq500g1v_fixtures.py.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx  # noqa: E402
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix  # noqa: E402
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g  # noqa: E402
import unit_tests.build_orchestration._tq500g1x_fixtures as x  # noqa: E402
import workflows._tq500g1v_fixtures as fx  # noqa: E402

AC_STORE = f"{fx.WORKTREE}/docs/acceptance-criteria"


def _once(result, label: str):
    """The single dispatch recorded under *label*; an AssertionError naming the recorded labels otherwise."""
    found = fx.calls(result, label)
    assert len(found) == 1, f"expected exactly one {label!r} dispatch, recorded labels: {fx.labels_of(result)}"
    return found[0]


def test_fast_lane_wrong_version_sequence_runs_after_green_and_review_before_commit():
    # covers: TQ-500g-1-v
    # angle: reachability
    # must_catch: runner placed after the commit dispatch
    # must_catch: test-breaker dispatched before the list step
    # must_catch: list step called without --base-ref
    result = fx.run_lane({fx.LIST: fx.list_reply([fx.owed_item(fx.WRONG, ["scripts/refresh.py"])])})
    labels = fx.labels_of(result)
    listing, breaker, finish = _once(result, fx.LIST), _once(result, fx.BREAKER), _once(result, fx.FINISH)
    order = [labels.index(label) for label in (fx.CODER, fx.REVIEW, fx.LIST, fx.BREAKER, fx.FINISH, fx.COMMIT)]
    assert order == sorted(set(order)), f"wrong dispatch order, recorded labels: {labels}"
    assert (listing.agent_type, finish.agent_type, breaker.agent_type) == (fx.EXECUTOR, fx.EXECUTOR, "test-breaker")
    list_cmd, finish_cmd = fx.command_of(listing), fx.command_of(finish)
    assert re.search(r"wrong_version_writer\.py\s+list\b", list_cmd), list_cmd
    assert re.search(r"wrong_version_gate\.py\s+finish\b", finish_cmd), finish_cmd
    for cmd in (list_cmd, finish_cmd):
        assert fx.flag(cmd, "ac-ids") == fx.AC, cmd
        assert fx.flag(cmd, "ac-root") == AC_STORE, cmd
        assert fx.flag(cmd, "test-root") == fx.WORKTREE, cmd
        assert fx.flag(cmd, "base-ref") == "HEAD", f"--base-ref HEAD must be passed explicitly: {cmd}"
    assert fx.flag(finish_cmd, "work-key") == fx.AC and fx.flag(finish_cmd, "reply") == "-", finish_cmd
    assert result.result["status"] == "ok" and fx.calls(result, fx.PR), result.result


def test_owed_list_reaches_test_breaker_unchanged():
    # covers: TQ-500g-1-v
    # angle: seam
    # must_catch: owed entries filtered, reordered or re-spelled before the dispatch
    # must_catch: in-scope files dropped from the dispatch
    # must_catch: scope key stripped from owed items before the dispatch
    # must_catch: repo_root passed as a relative path
    owed = [  # unsorted names and files, odd spelling and trailing space: any tidy-up shows
        fx.owed_item("Zeta wrong VERSION ", ["z_second.py", "a_first.py"], "declared"),
        fx.owed_item("alpha wrong version", ["m_only.py"], "derived"),
    ]
    ids = ("BO-STUB-0", fx.AC)
    result = fx.run_lane({fx.LIST: fx.list_reply(owed)}, ac_ids=ids)
    sent = fx.breaker_input(_once(result, fx.BREAKER))
    assert sent is not None, "the test-breaker dispatch carries no wrong_versions input"
    assert sent["wrong_versions"] == owed, sent["wrong_versions"]
    assert [list(item) for item in sent["wrong_versions"]] == [list(item) for item in owed], "key sets or order differ"
    assert sent["requirement_ids"] == list(ids) and sent["work_key"] == fx.AC, sent
    assert sent["repo_root"] == fx.WORKTREE and fx.ROOT_RE.match(sent["repo_root"]), sent["repo_root"]


def test_test_breaker_reply_reaches_writer_byte_for_byte(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: real_artifact
    # must_catch: reply expanded by the shell
    # must_catch: reply cut off at a line equal to the here-document delimiter
    sb = x.build(tmp_path)
    gitfx.write_ac_yaml(sb.work / "docs" / "acceptance-criteria", ix.AC_ID, x.test_spec())  # the lane's fixed store path
    proc, listed = x.run_list(sb, base_ref="HEAD")
    assert proc.returncode == 0 and listed["error"] is None, listed
    nasty = "if refresh_due:  # $HOME `whoami` it's \"q\" \\ $(id) ${HOME}\nEOF\n    # EOF"
    entries = g.full_entries()
    entries[0] = ix.prep(x.N1, ("refresh_config.py", x.COND, nasty))
    reply = json.dumps(ix.reply_obj(entries, work_key=ix.AC_ID), indent=2, ensure_ascii=False) + "\n"
    expected = (sb.work / "refresh_config.py").read_bytes().decode("utf-8").replace(x.COND, nasty, 1).encode("utf-8")
    result = fx.run_lane({fx.LIST: fx.ran(listed), fx.BREAKER: reply}, worktree=sb.work.as_posix(), ac_ids=(ix.AC_ID,))
    finish = _once(result, fx.FINISH)
    status_before = gitfx.run_git(["status", "--porcelain"], cwd=sb.work)
    done = fx.run_recorded(finish, g.GATE, sb.work)  # the recorded command, in a real shell, with the real wrapper
    out = json.loads(done.stdout.decode("utf-8") or "null")
    assert isinstance(out, dict) and out["writer"]["written"] is True, (done.returncode, done.stdout[-300:], done.stderr[-300:])
    manifest = json.loads(Path(out["writer"]["manifest_path"]).read_text(encoding="utf-8"))
    files = {e["name"]: e["files"] for e in manifest["entries"]}[x.N1]
    assert Path(files[0]["altered_copy"]).read_bytes() == expected, "the altered copy differs from the reply's replacement"
    assert gitfx.run_git(["status", "--porcelain"], cwd=sb.work) == status_before, "a reply file was left in the working tree"
    left = [p.name for p in (sb.git_dir / "leafcutter").rglob("*") if "reply" in p.name.lower()]
    assert not left, f"a reply file was left in the work folder: {left}"
    # A valid JSON reply cannot hold a raw line equal to a delimiter, so the cut-off is proven with raw text:
    # whatever delimiter the command picks, a stand-in wrapper must read every line of it on stdin.
    raw = "{\"entries\": []}\nEOF\nEOT\nEND\nREPLY\nEOF_REPLY\nWVEOF\nHEREDOC\n$HOME `id` it's \"q\" \\\\ tail"
    again = fx.run_lane({fx.LIST: fx.ran(listed), fx.BREAKER: raw}, worktree=sb.work.as_posix(), ac_ids=(ix.AC_ID,))
    script, saved = fx.stdin_capture_gate(tmp_path)
    assert fx.run_recorded(_once(again, fx.FINISH), script, tmp_path).returncode == 0 and saved.is_file()
    assert saved.read_bytes().decode("utf-8").rstrip("\n") == raw, f"finish read {saved.read_bytes()!r} instead of the reply"


def test_nothing_owed_skips_test_breaker_and_still_runs_finish(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: boundary
    # must_catch: runner skipped when nothing is owed
    # must_catch: test-breaker dispatched with an empty wrong_versions list
    result = fx.run_lane({fx.LIST: fx.list_reply([])})
    assert not fx.calls(result, fx.BREAKER), f"test-breaker was dispatched with nothing owed: {fx.labels_of(result)}"
    finish = _once(result, fx.FINISH)
    assert fx.labels_of(result).index(fx.FINISH) < fx.labels_of(result).index(fx.COMMIT), fx.labels_of(result)
    assert result.result["status"] == "ok" and fx.calls(result, fx.PR), result.result
    script, saved = fx.stdin_capture_gate(tmp_path)
    done = fx.run_recorded(finish, script, tmp_path)  # the recorded command, in a real shell
    assert done.returncode == 0 and saved.is_file(), (done.returncode, done.stderr[-300:])
    assert saved.read_bytes().strip() == b"", f"finish was given stdin {saved.read_bytes()!r} with nothing owed"
