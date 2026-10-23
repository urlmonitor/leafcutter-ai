"""
MODULE: unit_tests/workflows/test_tq500g1vi_review.py
GOAL: Regression tests for two pr-reviewer findings on TQ-500g-1-vi: the wrong-version commands of
    templates/workflows-js/build-feature.js and build-ticket.js quote every interpolated value (M-1), and a
    ticket driven inside a parallel chunk halts when its own planner read shows a source requirement (M-2).
BUSINESS CONTEXT: M-1: a worktree path with a space ("Bybit-Trader Live") broke every build, and an id holding
    ';' or '$(...)' injected a command. M-2: the epic planner's per-ticket source_ac decides serial vs parallel; if
    it wrongly reports [] the ticket's driver would run test-breaker beside its siblings in the shared worktree.
    The path test runs the recorded commands in a REAL shell against the real wrapper and writer.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import tempfile
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

SCRIPTS = g.GATE.parent
HOSTILE_IDS = ("TQ-1;touch pwned", "$(id)", "`id`", "a b", "TQ-1\ntouch pwned", "x|y")


def _run_in_shell(call, cwd: Path) -> subprocess.CompletedProcess:
    """Run a recorded command in a real shell, with the repo's own script in place of the worktree copy."""
    command = fx.command_of(call)
    head, sep, tail = command.partition("<<")
    tokens = shlex.split(head)
    script = SCRIPTS / Path(tokens[1]).name
    assert tokens[0] == "python" and script.is_file(), f"script path is not one intact argument: {tokens[:3]}"
    matched = re.match(r'python\s+(?:"[^"]*"|[^\s"]+)+', head)
    assert matched, head
    swapped = f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}"' + head[matched.end():] + sep + tail
    with tempfile.TemporaryDirectory() as scratch:
        sh = Path(scratch) / "step.sh"
        sh.write_bytes((swapped + "\n").encode("utf-8"))
        return subprocess.run([v._bash(), sh.as_posix()], cwd=cwd, capture_output=True, timeout=900)


def test_paths_with_a_space_reach_the_real_wrapper_intact(tmp_path: Path):
    # covers: TQ-500g-1-vi
    # angle: real_artifact
    # must_catch: unquoted worktree path in a wrong-version command
    for route in fx.ROUTES:
        root = tmp_path / f"{route.key} Repo With Space"
        root.mkdir()
        sb = x.build(root)
        gitfx.write_ac_yaml(sb.work / "docs" / "acceptance-criteria", ix.AC_ID, x.test_spec())
        wt = sb.work.as_posix()
        assert " " in wt
        proc, listed = x.run_list(sb, base_ref="HEAD")
        assert proc.returncode == 0 and listed["error"] is None, listed
        entries = g.full_entries()
        entries[0] = ix.prep(x.N1, ("refresh_config.py", x.COND, "if refresh_due:  # spaced"))
        reply = json.dumps(ix.reply_obj(entries, work_key=fx.STEM), indent=2, ensure_ascii=False) + "\n"
        result = fx.run_route(route, fx.wv_replies(route, list_=v.ran(listed), breaker=reply), wt=wt, source_ac=(ix.AC_ID,))
        list_call, finish_call = fx.calls(result, route.list)[0], fx.calls(result, route.finish)[0]
        for call in (list_call, finish_call):
            tokens = shlex.split(fx.command_of(call).partition("<<")[0])
            assert tokens[tokens.index("--ac-root") + 1] == f"{wt}/docs/acceptance-criteria", (route.key, tokens)
            assert tokens[tokens.index("--test-root") + 1] == wt, (route.key, tokens)
            assert tokens[1].startswith(wt) and tokens[1].endswith(".py"), (route.key, tokens[:2])
        listing = _run_in_shell(list_call, sb.work)
        assert [o["name"] for o in json.loads(listing.stdout.decode("utf-8"))["owed"]] == [o["name"] for o in listed["owed"]], (route.key, listing.stdout[-300:], listing.stderr[-300:])
        done = _run_in_shell(finish_call, sb.work)
        out = json.loads(done.stdout.decode("utf-8") or "null")
        assert isinstance(out, dict) and out["writer"]["written"] is True, (route.key, done.returncode, done.stdout[-300:], done.stderr[-300:])


def test_hostile_source_ac_id_or_work_key_halts_with_no_command():
    # covers: TQ-500g-1-vi
    # angle: failure
    # must_catch: an id with a shell metacharacter reaches a command
    # must_catch: a work key outside the plain-segment pattern reaches a command
    for route in fx.ROUTES:
        cases = [({"source_ac": (bad,)}, bad) for bad in HOSTILE_IDS] + [({"source_ac": (fx.AC,), "stem": "07 bad;touch pwned"}, "pwned")]
        for kwargs, marker in cases:
            result = fx.run_route(route, **kwargs)
            where, labels = f"{route.key}/{marker!r}", fx.labels_of(result)
            commands = [fx.command_of(c) for c in result.agent_calls if c.agent_type == v.EXECUTOR]
            assert not [c for c in commands if marker.strip() and marker.strip() in c], f"{where}: hostile value in a command: {commands}"
            assert not fx.calls(result, route.list) and not fx.calls(result, route.breaker) and not fx.calls(result, route.finish), f"{where}: ran on: {labels}"
            assert not fx.calls(result, fx.COMMIT), f"{where}: reached commit: {labels}"
            keys = fx.halt_keys(result)
            assert keys["status"] == "blocked" and keys["gate"] == "wrong_version_gate" and keys["wrong_version_step"], (where, keys)
            assert keys["classification"] == "halt", (where, keys)


def _drive_epic_with_planner_reads(reads: list[dict]):
    items = [fx.epic_item(1, []), fx.epic_item(2, [])]  # the epic planner says "no source requirement" for both
    labels = fx.epic_labels(items, phases=("commit",), ticket_source_ac=())
    labels[fx.PLANNER] = {"__sequence__": reads}
    return fx.run_script(fx.BF.script, labels, {"target": fx.EPIC})


def _serial_halts(result) -> list:
    """The epic's halted tickets whose halt is the parallel-chunk check (the epic summary keeps the message)."""
    return [t for t in (result.result or {}).get("halted_tickets", []) if "batch ran in parallel" in str(t.get("error"))]


def test_parallel_chunk_ticket_with_its_own_source_ac_halts_before_any_wv_step():
    # covers: TQ-500g-1-vi
    # angle: failure
    # must_catch: serial rule trusts the epic planner's source_ac over the ticket's own read
    empty = fx.planner_reply(fx.WT, ("commit",), ())
    owing = fx.planner_reply(fx.WT, ("commit",), (fx.AC,))
    result = _drive_epic_with_planner_reads([empty, owing])
    labels = fx.labels_of(result)
    assert not fx.calls(result, fx.BF.breaker) and not fx.calls(result, fx.BF.list), f"an owing ticket ran in a parallel chunk: {labels}"
    assert len(_serial_halts(result)) == 1, f"the owing ticket was not halted by the batch check: {result.result.get('halted_tickets')}"
    assert labels.count(fx.COMMIT) == 1, f"the sibling should proceed alone, the owing ticket must not commit: {labels}"
    control = _drive_epic_with_planner_reads([empty, empty])
    assert not _serial_halts(control), f"control halted: {control.result.get('halted_tickets')}"
    assert fx.labels_of(control).count(fx.COMMIT) == 2, fx.labels_of(control)
