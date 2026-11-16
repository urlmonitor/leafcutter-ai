"""MODULE: test_tq200d5_review1

GOAL: Review round 1 of TQ-200d-5. Prove that (H-1) the timeout is enforced on the whole launcher tree, so a
    ``.cmd`` (or sh) launcher whose child outlives the timeout cannot hold the run; (H-2) a failure of the
    temp-file cleanup after a run is not a launch failure and never replaces the run's real result, while a
    working directory that does not exist is one; (Low 2) a harness failure of a score-gold or self-test run
    is written to the suffixed results file and never over the live receipt; (Low 3) the README and the
    how-to say the run stops and that the launch text is in ``harness_failure.detail``, not in a row's error.

    H-1 starts a REAL child process tree (a fake claude that sleeps), so it is the one place the process start
    is not replaced.

Target modules: scripts/evals/agent_launch/command.py, scripts/evals/agent_launch/harness_failure.py,
    scripts/evals/README.md, docs/how-to/run-a-live-agent-eval.md
AC: TQ-200d-5-ii, TQ-200d-5-i, TQ-200d-5-iii
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

import unit_tests.evals.tq200d5._docs as docs
import unit_tests.evals.tq200d5._fake as fk
import unit_tests.evals.tq200d5._runs as rn

PREFIX = "agent CLI could not be launched"
SLEEP_SECONDS = 12
TIMEOUT_SECONDS = 2
PROMPT_RETURNS = {"label": "ok", "artifact": "ok", "transcript": "done"}
AFTER_START = {
    "exit": (fk.exits(1, "boom"), {"label": "claude CLI exited 1: boom", "artifact": "agent CLI exited 1: boom",
                                   "transcript": "agent CLI exited 1 without a usable result: boom"}),
    "timeout": (fk.times_out(30), {"label": "claude CLI timed out after 30s", "artifact": "agent CLI timed out after 30s",
                                   "transcript": "agent CLI timed out after 30s; partial stdout: "}),
}


# ---------------------------------------------------------------------------
# H-1: the timeout reaches the whole tree
# ---------------------------------------------------------------------------
def _tree_launchers(tmp_path: Path, monkeypatch, route: str) -> Path:
    """A PATH whose claude is a launcher that starts the sleeping fake as a CHILD; returns the call-log folder."""
    fk.setup(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, "run", fk.REAL_RUN)  # the real process start: a real tree is needed
    calls = tmp_path / "tree_calls"
    calls.mkdir()
    cli = fk.make_real_cli_dir(tmp_path / "tree_cli", shell_wrapper=route == "posix")
    monkeypatch.setenv("PATH", str(cli) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("FAKE_CLAUDE_DIR", str(calls))
    monkeypatch.setenv("FAKE_CLAUDE_OUTCOME", json.dumps({"sleep": SLEEP_SECONDS}))
    return calls


def _running(psutil, pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


@pytest.mark.parametrize("invoker", ["label", "transcript"])
def test_timeout_reaches_the_launcher_tree_promptly(tmp_path, monkeypatch, invoker):
    # covers: TQ-200d-5-ii
    # angle: failure
    # must_catch: timeout waits for the grandchild that holds the pipes open
    # must_catch: grandchild of the launcher left running after the timeout
    import psutil  # noqa: PLC0415 - a dev requirement; the test never skips

    route = "cmd" if sys.platform == "win32" else "posix"  # each platform exercises its own launcher: .cmd, or an sh wrapper
    calls = _tree_launchers(tmp_path, monkeypatch, route)
    ev, tx = fk.module("run_agent_eval"), fk.module("produced_tests_transcript")
    box = tmp_path / "box"
    box.mkdir()
    run = {"label": lambda: ev.invoke_via_cli("instructions", "input", "haiku", TIMEOUT_SECONDS),
           "transcript": lambda: tx.invoke_with_transcript("instructions", "input", "sonnet", TIMEOUT_SECONDS, box, "Read",
                                                            ev.ModelInvocationError)}[invoker]
    started = time.monotonic()
    pid = None
    try:
        with pytest.raises(ev.ModelInvocationError, match=f"timed out after {TIMEOUT_SECONDS}s"):
            run()
        elapsed = time.monotonic() - started
        pidfile = calls / "pid-000.txt"
        assert pidfile.is_file(), "the fake program never started, so the tree was never built"
        pid = int(pidfile.read_text(encoding="utf-8"))
        assert elapsed < TIMEOUT_SECONDS + 3, f"the timeout of {TIMEOUT_SECONDS}s took {elapsed:.1f}s (the child sleeps {SLEEP_SECONDS}s)"
        deadline = time.monotonic() + 3
        while _running(psutil, pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _running(psutil, pid), f"the launcher's child (pid {pid}) is still running after the timeout"
        assert not (calls / "done-000.txt").exists()
    finally:
        if pid is not None and _running(psutil, pid):
            psutil.Process(pid).kill()


# ---------------------------------------------------------------------------
# H-2: only a failure to START is a launch failure
# ---------------------------------------------------------------------------
class _Refusal:
    """Makes removing the harness's stdin temp file raise PermissionError (it is 'in use'); counts the refusals."""

    def __init__(self, monkeypatch) -> None:
        self.hits = 0
        real = {"Path.unlink": Path.unlink, "os.unlink": os.unlink, "os.remove": os.remove}

        def refused(target) -> bool:
            return Path(str(target)).name.startswith("agent_eval_input_")

        def path_unlink(path, *a, **k):
            if refused(path):
                self.hits += 1
                raise PermissionError(13, "The process cannot access the file because it is being used by another process", str(path))
            return real["Path.unlink"](path, *a, **k)

        def os_remove(name, *a, **k):
            if refused(name):
                self.hits += 1
                raise PermissionError(13, "The process cannot access the file because it is being used by another process", str(name))
            return real["os.remove"](name, *a, **k)

        monkeypatch.setattr(Path, "unlink", path_unlink)
        monkeypatch.setattr(os, "unlink", os_remove)
        monkeypatch.setattr(os, "remove", os_remove)


def test_cleanup_failure_after_a_run_is_not_a_launch_failure(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-i
    # angle: failure
    # must_catch: a temp-file cleanup error after a run is reported as a launch failure
    # must_catch: a cleanup error replaces the run's own result or post-start error
    fake = fk.setup(tmp_path, monkeypatch)
    refusal = _Refusal(monkeypatch)
    ev, launch_error = fk.module("run_agent_eval"), fk.module("agent_launch.command").AgentLaunchError
    for name, run in fk.invokers(tmp_path).items():
        fake.plan = [fk.ok()]
        before = refusal.hits
        assert run("instructions", "input") == PROMPT_RETURNS[name], f"{name}: the real result was thrown away"
        assert refusal.hits > before, f"{name}: the cleanup was never refused, so this proves nothing"
        for case, (outcome, texts) in AFTER_START.items():
            fake.plan = [outcome]
            with pytest.raises(ev.ModelInvocationError) as caught:
                run("instructions", "input")
            assert str(caught.value) == texts[name], f"{name}/{case}: {caught.value}"
            assert not isinstance(caught.value, launch_error), f"{name}/{case}: the cleanup error became a launch failure"
    # a whole run: every row is still scored, and there is no harness failure
    sub = tmp_path / "whole"
    sub.mkdir()
    result = rn.run("label", sub, monkeypatch, capsys, caplog, [rn.ok_reply("label")], rows=2)
    assert result.code == 0 and len(result.rows) == 2 and "harness_failure" not in (result.payload or {}), (result.code, result.payload)


def test_missing_working_directory_is_a_launch_failure(tmp_path, monkeypatch):
    # covers: TQ-200d-5-i
    # angle: boundary
    # must_catch: a working directory the operating system refuses is not reported as a launch failure
    # The AC calls a launch failure the operating system refusing to START the agent CLI; a working
    # directory that is gone is refused at the start, so it is one (with the operating-system reason).
    fk.setup(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, "run", fk.REAL_RUN)  # the real start is what refuses the directory
    ev, launch_error = fk.module("run_agent_eval"), fk.module("agent_launch.command").AgentLaunchError
    gone = tmp_path / "sandbox-that-is-gone"
    with pytest.raises(ev.ModelInvocationError) as caught:
        ev.invoke_agent_writer("instructions", "input", "opus", 30, gone, "Read")
    assert isinstance(caught.value, launch_error) and str(caught.value).startswith(f"{PREFIX}: "), str(caught.value)
    assert isinstance(caught.value.__cause__, OSError) and str(caught.value.__cause__) in str(caught.value)
    assert list(fk.private_tmp().iterdir()) == [], "no temp file is left behind"


# ---------------------------------------------------------------------------
# Low 2: the suffixed results file
# ---------------------------------------------------------------------------
def _judge_cannot_launch(monkeypatch, kind: str) -> None:
    """Make the run that needs no model call (score-gold, self-test) start the agent anyway, as a judge would."""
    ev, pm = fk.module("run_agent_eval"), fk.module("produced_tests_mode")

    def start(*_a, **_k):
        return ev.invoke_via_cli("judge instructions", "artifact text", "haiku", 5)

    target = {"artifact": (ev, "_score_gold_row"), "label": (ev, "run_label_eval"), "produced": (pm, "score_one")}[kind]
    monkeypatch.setattr(target[0], target[1], start)


@pytest.mark.parametrize(("kind", "flag", "suffix"), [("artifact", "--score-gold", "-scoregold"), ("label", "--self-test", "-selftest"),
                                                      ("produced", "--score-gold", "-scoregold")])
def test_offline_run_harness_failure_does_not_overwrite_the_live_receipt(tmp_path, monkeypatch, capsys, caplog, kind, flag, suffix):
    # covers: TQ-200d-5-iii
    # angle: failure
    # must_catch: the harness-failure file of a score-gold or self-test run is written over the live results file
    root = tmp_path / "fake-repo"
    results = root / "scripts" / "evals" / "results"
    results.mkdir(parents=True)
    live = results / "agent-x.json"
    live.write_text(json.dumps({"agent": "agent-x", "live": "receipt"}), encoding="utf-8")
    before = live.read_bytes()
    sub = tmp_path / "run"
    sub.mkdir()
    refused = rn.run(kind, sub, monkeypatch, capsys, caplog, [fk.cannot_start(FileNotFoundError(2, "no such program", None, 2))],
                     rows=2, repo_root=root, args=(flag,), before=lambda mp: _judge_cannot_launch(mp, kind))
    assert refused.code == 3, f"{kind}: exit status {refused.code}"
    assert live.read_bytes() == before, f"{kind}: the live results file was overwritten by a {flag} run"
    written = json.loads((results / f"agent-x{suffix}.json").read_text(encoding="utf-8"))
    assert written["harness_failure"]["cause"] == "agent_launch_failed" and "live" not in written
    assert sorted(p.name for p in results.iterdir()) == sorted(["agent-x.json", f"agent-x{suffix}.json"])


# ---------------------------------------------------------------------------
# Low 3: the docs say where the launch text is
# ---------------------------------------------------------------------------
_ROW_ERROR = re.compile(r"`(?:parse_)?error`")
_LAUNCH_TEXT = re.compile(r"could not be (?:started|launched)|launch failure|launch text", re.I)
_AFTER_START = re.compile(r"after the agent started|after (?:the )?start|not a launch failure|started and then", re.I)


def claims_row_error_carries_launch_text(sentence: str) -> bool:
    """True for a sentence that puts the launch-failure text in a row's ``error`` or ``parse_error``."""
    return bool(_ROW_ERROR.search(sentence) and _LAUNCH_TEXT.search(sentence) and not _AFTER_START.search(sentence)
                and not re.search(r"\b(never|no longer|instead of|is not|are not|does not|do not)\b", sentence, re.I))


def test_docs_say_the_run_stops_and_the_text_is_in_harness_failure_detail():
    # covers: TQ-200d-5-i
    # covers: TQ-200d-5-iii
    # angle: real_artifact
    # must_catch: the README or the how-to still says a launch-failure row carries the text in error or parse_error
    readme = docs.section(docs.text_of(docs.README), "When the agent cannot be started")
    how_to = docs.section(docs.text_of(docs.HOW_TO), "Reading a launch failure")
    for name, body in (("README section", readme), ("how-to section", how_to)):
        assert "harness_failure.detail" in body, f"the {name} does not say the text is in harness_failure.detail"
        assert re.search(r"\bstops?\b|\bstopped\b", body, re.I), f"the {name} does not say the run stops"
        claims = [s for s in docs.sentences(body) if claims_row_error_carries_launch_text(s)]
        assert claims == [], f"the {name} still says a row's error carries the launch text: {claims}"
    # the check sees the two sentences the docs had, and lets the right ones through
    for bad in ("A row whose agent could not be started records, in its `error` (label rows: `parse_error`):",
                "A row whose agent could not be started carries this text in its `error`:"):
        assert claims_row_error_carries_launch_text(bad), bad
    for good in ("The text is in `harness_failure.detail`; a row's `error` is only for a failure after the agent started.",
                 "A timeout is not a launch failure: the row's `error` keeps its own text."):
        assert not claims_row_error_carries_launch_text(good), good
