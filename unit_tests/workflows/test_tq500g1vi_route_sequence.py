"""
MODULE: unit_tests/workflows/test_tq500g1vi_route_sequence.py
GOAL: RED tests for TQ-500g-1-vi, the ORDER and CONTENT of the wrong-version dispatches that
    templates/workflows-js/build-feature.js and build-ticket.js make right before the commit dispatch:
    list step, test-breaker, one finish call; and what a passing or failing finish decides.
BUSINESS CONTEXT: Every test runs the TEMPLATE under unit_tests/_workflow_engine_harness.py and asserts on
    the recorded dispatches, never on the source text. Today neither twin dispatches any of the new steps, so
    each test fails on an assertion about the recorded dispatches. The pinned labels are in _tq500g1vi_fixtures.py.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402

AC_STORE = f"{fx.WT}/docs/acceptance-criteria"
OWED = [v.owed_item(v.WRONG, ["scripts/refresh.py"])]


def _once(result, label: str):
    found = fx.calls(result, label)
    assert len(found) == 1, f"expected exactly one {label!r} dispatch, recorded labels: {fx.labels_of(result)}"
    return found[0]


def test_build_feature_runs_wrong_version_sequence_right_before_commit_dispatch():
    # covers: TQ-500g-1-vi
    # angle: reachability
    # must_catch: runner placed after the commit phase
    # must_catch: list step called without --base-ref
    # must_catch: command step dispatched to status-checker
    route = fx.BF
    result = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply(OWED)))
    labels = fx.labels_of(result)
    listing, breaker, finish = _once(result, route.list), _once(result, route.breaker), _once(result, route.finish)
    order = [labels.index(x) for x in (fx.REVIEWER, route.list, route.breaker, route.finish, fx.COMMIT)]
    assert order == sorted(set(order)), f"wrong dispatch order, recorded labels: {labels}"
    assert labels[labels.index(route.list):labels.index(route.finish) + 1] == [route.list, route.breaker, route.finish], labels
    assert (listing.agent_type, finish.agent_type, breaker.agent_type) == (v.EXECUTOR, v.EXECUTOR, "test-breaker")
    assert {c.phase_name for c in (listing, breaker, finish)} == {fx.PHASE}, "each step carries phase 'Wrong-Version Runs'"
    list_cmd, finish_cmd = fx.command_of(listing), fx.command_of(finish)
    assert re.search(r"wrong_version_writer\.py\s+list\b", list_cmd), list_cmd
    assert re.search(r"wrong_version_gate\.py\s+finish\b", finish_cmd), finish_cmd
    for cmd in (list_cmd, finish_cmd):
        assert fx.flag(cmd, "ac-ids") == fx.AC, cmd
        assert fx.flag(cmd, "ac-root") == AC_STORE, cmd
        assert fx.flag(cmd, "test-root") == fx.WT, cmd
        assert fx.flag(cmd, "base-ref") == "HEAD", f"--base-ref HEAD must be passed explicitly: {cmd}"
    assert fx.flag(finish_cmd, "work-key") == fx.STEM and fx.flag(finish_cmd, "reply") == "-", finish_cmd
    for call, step in ((listing, route.list), (finish, route.finish)):
        req = fx.request_of(call)
        assert (req["step"], req["target"]["workspace"], req["target"]["run_id"]) == (step, fx.WT, fx.STEM), req
    assert result.result and result.result.get("gate") != "wrong_version_gate", result.result


def test_owed_list_reaches_test_breaker_unchanged():
    # covers: TQ-500g-1-vi
    # angle: seam
    # must_catch: owed entries filtered or re-spelled before the test-breaker dispatch
    # must_catch: scope key stripped from owed items before the dispatch
    owed = [  # unsorted names and files, odd spelling and trailing space: any tidy-up shows
        v.owed_item("Zeta wrong VERSION ", ["z_second.py", "a_first.py"], "declared"),
        v.owed_item("alpha wrong version", ["m_only.py"], "derived"),
    ]
    ids = ("BO-STUB-0", fx.AC)
    for route in fx.ROUTES:
        result = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply(owed)), source_ac=ids)
        sent = fx.breaker_input(_once(result, route.breaker))
        assert sent is not None, f"{route.key}: the test-breaker dispatch carries no wrong_versions input"
        assert sent["wrong_versions"] == owed, f"{route.key}: {sent['wrong_versions']}"
        assert [list(i) for i in sent["wrong_versions"]] == [list(i) for i in owed], f"{route.key}: key sets or order differ"
        assert sent["requirement_ids"] == list(ids) and sent["work_key"] == fx.STEM, f"{route.key}: {sent}"
        assert sent["repo_root"] == fx.WT and v.ROOT_RE.match(sent["repo_root"]), f"{route.key}: {sent['repo_root']}"
        assert fx.flag(fx.command_of(_once(result, route.list)), "ac-ids") == ",".join(ids), route.key


def test_k2_survivor_never_reaches_commit():
    # covers: TQ-500g-1-vi
    # angle: criterion
    # must_catch: runner verdict ignored
    # must_catch: a refused finish reply read as a pass
    survivor = v.finish_reply(v.verdict_f2())
    for route in fx.ROUTES:
        k2 = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply(OWED), finish=survivor))
        assert len(fx.calls(k2, route.finish)) == 1, f"{route.key}: finish was not dispatched: {fx.labels_of(k2)}"
        assert not fx.calls(k2, fx.COMMIT), f"{route.key}: a survivor reached commit: {fx.labels_of(k2)}"
        assert not fx.calls(k2, fx.STAGE) and not fx.calls(k2, fx.OBSERVE), f"{route.key}: routing ran: {fx.labels_of(k2)}"
        out = k2.result or {}
        assert out.get("status") == "blocked" and out.get("gate") == "wrong_version_gate", f"{route.key}: {out}"
        assert out.get("wrong_version_step") == "finish" and out.get("classification") == "halt", f"{route.key}: {out}"
        assert out.get("wrong_version_detail") == json.loads(survivor["stdout"]), f"{route.key}: {out.get('wrong_version_detail')}"
        assert v.TEST in out.get("message", "") and v.WRONG in out.get("message", ""), f"{route.key}: {out.get('message')}"
        k1 = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply(OWED)))
        assert len(fx.calls(k1, route.finish)) == 1 and len(fx.calls(k1, fx.COMMIT)) == 1, f"{route.key}: {fx.labels_of(k1)}"
        assert (k1.result or {}).get("gate") != "wrong_version_gate", f"{route.key}: {k1.result}"
        for refused in (v.declined(), None):  # a refused finish is not a pass either
            r = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply(OWED), finish=refused))
            assert not fx.calls(r, fx.COMMIT) and (r.result or {}).get("gate") == "wrong_version_gate", f"{route.key}: {fx.labels_of(r)}"


def test_nothing_owed_skips_test_breaker_and_still_runs_finish(tmp_path: Path):
    # covers: TQ-500g-1-vi
    # angle: boundary
    # must_catch: runner skipped when nothing is owed
    # must_catch: test-breaker dispatched with an empty wrong_versions list
    for route in fx.ROUTES:
        result = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply([])))
        labels = fx.labels_of(result)
        assert not fx.calls(result, route.breaker), f"{route.key}: test-breaker was dispatched with nothing owed: {labels}"
        finish = _once(result, route.finish)
        assert labels.index(route.list) < labels.index(route.finish) < labels.index(fx.COMMIT), labels
        assert (result.result or {}).get("gate") != "wrong_version_gate", f"{route.key}: {result.result}"
        scratch = tmp_path / route.key
        scratch.mkdir()
        script, saved = v.stdin_capture_gate(scratch)
        done = v.run_recorded(finish, script, scratch)  # the recorded command, in a real shell
        assert done.returncode == 0 and saved.is_file(), (route.key, done.returncode, done.stderr[-300:])
        assert saved.read_bytes().strip() == b"", f"{route.key}: finish was given stdin {saved.read_bytes()!r} with nothing owed"
