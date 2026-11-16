"""MODULE: test_tq200d5i_launch_failure

GOAL: Prove a row whose agent could not be started writes 'agent CLI could not be launched: <ExceptionType>:
    <message>' with the operating-system error exactly as raised, in one form for the three ways the harness
    starts an agent, that a failure after the start keeps its old text and is not marked as a launch failure,
    and that the README quotes the prefix the results file carries.

Target modules: scripts/evals/agent_launch/command.py, scripts/evals/run_agent_eval.py,
    scripts/evals/produced_tests_transcript.py
AC: TQ-200d-5-i
"""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d5._docs as docs
import unit_tests.evals.tq200d5._fake as fk
import unit_tests.evals.tq200d5._runs as rn

PREFIX = "agent CLI could not be launched"
ERRORS = {
    "R1": OSError(22, "Der Dateiname oder die Dateinamenerweiterung ist zu lang.", None, 206),
    "R2": FileNotFoundError(2, "Das System kann die angegebene Datei nicht finden.", None, 2),
    "R3": PermissionError(13, "Permission denied", "/usr/local/bin/claude"),
}


def _expected(exc: BaseException) -> str:
    return f"{PREFIX}: {type(exc).__name__}: {exc}"


def _launch_failure(kind, name, tmp_path, monkeypatch, capsys, caplog) -> str:
    sub = tmp_path / f"{kind}-{name}"
    sub.mkdir()
    return rn.launch_text(rn.run(kind, sub, monkeypatch, capsys, caplog, [fk.cannot_start(ERRORS[name])], rows=1))


@pytest.mark.parametrize("kind", ["label", "artifact", "produced"])
def test_launch_failure_row_carries_the_operating_system_reason(tmp_path, monkeypatch, capsys, caplog, kind):
    # covers: TQ-200d-5-i
    # angle: discrimination
    # must_catch: launch error replaced by a constant with no operating-system reason
    # must_catch: only the exception class kept, without its number and message
    texts = {name: _launch_failure(kind, name, tmp_path, monkeypatch, capsys, caplog) for name in ERRORS}
    for name, exc in ERRORS.items():
        text = texts[name]
        assert text == _expected(exc), f"{kind}/{name}: {text!r}"
        assert str(exc) in text and type(exc).__name__ in text, "the number and message exactly as raised, with the class"
        assert str(getattr(exc, "winerror", None) or exc.errno) in text
    assert texts["R1"] != texts["R2"] and str(ERRORS["R1"]) not in texts["R2"] and str(ERRORS["R2"]) not in texts["R1"]
    assert texts["R3"].endswith("Permission denied: '/usr/local/bin/claude'"), "the file name of the refusal is kept"


def test_launch_failure_text_has_one_form_for_all_three_invokers(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-i
    # angle: discrimination
    # must_catch: label runs keep the 'claude CLI could not be launched' prefix
    # must_catch: transcript invoker keeps the repr form
    exc = ERRORS["R2"]
    texts = {kind: _launch_failure(kind, "R2", tmp_path, monkeypatch, capsys, caplog) for kind in rn.KINDS}
    assert texts == dict.fromkeys(rn.KINDS, _expected(exc)), texts
    assert "claude CLI could not be launched" not in "".join(texts.values()) and "FileNotFoundError(" not in "".join(texts.values())
    # the invokers themselves raise one message and one error class
    ev, launch_error = fk.module("run_agent_eval"), fk.module("agent_launch.command").AgentLaunchError
    direct = tmp_path / "direct"
    direct.mkdir()
    fk.setup(direct, monkeypatch, [fk.cannot_start(exc)])
    for name, run_invoker in fk.invokers(direct).items():
        with pytest.raises(ev.ModelInvocationError) as caught:
            run_invoker("instructions", "input")
        assert str(caught.value) == _expected(exc) and isinstance(caught.value, launch_error), name
        assert caught.value.__cause__ is exc, f"{name}: the operating-system error is kept as the cause"


def _post_start_cases() -> dict:
    return {
        "timeout": (fk.times_out(30), {"label": "claude CLI timed out after 30s", "artifact": "agent CLI timed out after 30s",
                                       "transcript": "agent CLI timed out after 30s; partial stdout: "}),
        "non-zero exit": (fk.exits(1, "boom"), {"label": "claude CLI exited 1: boom", "artifact": "agent CLI exited 1: boom",
                                                "transcript": "agent CLI exited 1 without a usable result: boom"}),
        "unreadable reply": (fk.unreadable(), {"label": "claude CLI returned non-JSON envelope",
                                               "artifact": "agent CLI returned non-JSON envelope",
                                               "transcript": "agent CLI exited 0 without a usable result: result event missing: "}),
    }


def test_post_start_failures_keep_their_error_text(tmp_path, monkeypatch):
    # covers: TQ-200d-5-i
    # angle: boundary
    # must_catch: timeout reported as a launch failure
    # must_catch: non-zero exit after start rewritten with the launch-failure prefix
    ev = fk.module("run_agent_eval")
    fake = fk.setup(tmp_path, monkeypatch)
    refused = ERRORS["R2"]
    # control: a launch failure IS reported with the launch-failure prefix
    fake.plan = [fk.cannot_start(refused)]
    for name, run_invoker in fk.invokers(tmp_path).items():
        with pytest.raises(ev.ModelInvocationError) as caught:
            run_invoker("instructions", "input")
        assert str(caught.value) == _expected(refused), name
    launch_error = fk.module("agent_launch.command").AgentLaunchError
    for case, (outcome, texts) in _post_start_cases().items():
        fake.plan = [outcome]
        for name, run_invoker in fk.invokers(tmp_path).items():
            with pytest.raises(ev.ModelInvocationError) as caught:
                run_invoker("instructions", "input")
            assert str(caught.value) == texts[name], f"{name}/{case}: {caught.value}"
            assert not isinstance(caught.value, launch_error), f"{name}/{case}: marked as a launch failure"
            assert PREFIX not in str(caught.value)


def test_readme_quotes_the_written_launch_failure_prefix(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-i
    # angle: real_artifact
    readme = docs.text_of(docs.README)
    how_to = docs.text_of(docs.HOW_TO)
    written = _launch_failure("label", "R1", tmp_path, monkeypatch, capsys, caplog)
    prefix = written.split(": ")[0]
    assert prefix == PREFIX, written
    assert f"{prefix}: <ExceptionType>: <message>" in readme, "the README quotes the form of the written error"
    assert "claude CLI could not be launched" not in readme
    for token in ("WinError 206", "WinError 2"):
        assert token in readme, f"the README gives the {token} example"
    reading = docs.section(how_to, "Reading a launch failure")
    assert "WinError 206" in reading and "WinError 2" in reading.replace("WinError 206", "")
    assert "Finding claude on Windows" in reading, "the WinError 2 action points at the other section"
