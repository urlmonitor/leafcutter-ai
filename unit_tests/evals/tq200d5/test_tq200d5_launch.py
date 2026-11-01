"""MODULE: test_tq200d5_launch

GOAL: Prove that a live eval hands each agent its instructions and its input outside the command
    line, so the test writer's ~67,700-character template can be scored on Windows (32,767
    characters is the limit of one command line), for each of the three ways the harness starts an
    agent: label (run_agent_eval.invoke_via_cli), artifact and plain produced-tests
    (invoke_agent_writer) and recorded-commands (produced_tests_transcript.invoke_with_transcript).
    No model call: ``_fake.Fake`` starts a real fake claude process in place of the real program.

Target modules: scripts/evals/agent_launch/command.py, scripts/evals/run_agent_eval.py,
    scripts/evals/produced_tests_transcript.py
AC: TQ-200d-5
"""

from __future__ import annotations

import re
import subprocess

import pytest

import unit_tests.evals.tq200d5._fake as fk

TEMPLATE_SAMPLE = re.compile(r"[A-Za-z ,]{80}")
INSTRUCTIONS_TAIL = '\r\nwindows line "quoted" 中 \U0001F600\r\nlast line, no newline'


def _outcomes() -> dict:
    refused = FileNotFoundError(2, "The system cannot find the file specified", None, 2)
    return {"success": fk.ok(), "non-zero exit": fk.exits(1, "boom"), "timeout": fk.times_out(),
            "failed start": fk.cannot_start(refused)}


def test_long_instructions_and_input_keep_every_command_line_under_the_windows_limit(tmp_path, monkeypatch):
    # covers: TQ-200d-5
    # angle: boundary
    # must_catch: row input passed as the -p command-line argument
    # must_catch: transcript invoker passes the instructions with --append-system-prompt on the command line
    fake = fk.setup(tmp_path, monkeypatch)
    rendered = fk.rendered_test_writer()
    assert len(rendered) > 2 * fk.LIMIT, "precondition: the real template is more than twice the limit"
    assert len(fk.BIG_INPUT) >= 40_000 and fk.LONG_SANDBOX in rendered and "{{config.output_root}}" not in rendered
    sample = TEMPLATE_SAMPLE.search(rendered, 5000).group(0)
    marker = "ROW-INPUT-MARKER-7f3a"
    row_input = fk.BIG_INPUT[:20_000] + marker + fk.BIG_INPUT[20_000:]
    # control: the old way (both inline) is over the limit, so the measure below can fail
    inline = subprocess.list2cmdline(["claude", "-p", row_input, "--append-system-prompt", rendered, "--output-format", "json"])
    assert len(inline) > 2 * fk.LIMIT
    for name, run in fk.invokers(tmp_path).items():
        run(rendered, row_input)
        call = fake.calls[-1]
        assert len(call.cmdline) < fk.LIMIT, f"{name}: the command line is {len(call.cmdline)} characters"
        assert sample not in call.cmdline, f"{name}: template text is on the command line"
        assert marker not in call.cmdline, f"{name}: the row input is on the command line"
    assert len(fake.calls) == 3, "each invoker started the agent exactly once"


def test_agent_receives_instructions_and_input_byte_for_byte(tmp_path, monkeypatch):
    # covers: TQ-200d-5
    # angle: discrimination
    # must_catch: prompt file written with platform newline translation
    # must_catch: prompt file written in the locale encoding instead of UTF-8
    # must_catch: row input stripped or re-quoted on the way to stdin
    fake = fk.setup(tmp_path, monkeypatch)
    spy = fk.OpenSpy(monkeypatch, fk.private_tmp())
    instructions = fk.rendered_test_writer() + INSTRUCTIONS_TAIL
    wanted = instructions.encode("utf-8")
    assert b"\r\n" in wanted and b"\n" in wanted.replace(b"\r\n", b""), "precondition: both newline kinds"
    assert fk.LONG_SANDBOX.encode() in wanted and b"{{config.output_root}}" not in wanted
    for name, run in fk.invokers(tmp_path).items():
        spy.opens.clear()
        run(instructions, fk.BIG_INPUT)
        call = fake.calls[-1]
        assert call.prompt_bytes == wanted, f"{name}: the prompt file differs from the rendered instructions"
        assert call.prompt_seen == wanted, f"{name}: the agent read other instructions than were rendered"
        assert call.stdin_bytes == fk.BIG_INPUT.encode("utf-8"), f"{name}: the agent read another input than the row's"
        assert not isinstance(call.kwargs.get("input"), str), f"{name}: a text-mode input is newline-translated on Windows"
        for opened in spy.opens:
            assert opened["encoding"] and opened["encoding"].lower().replace("-", "") == "utf8", f"{name}: {opened}"
            assert opened["newline"] in ("", "\n"), f"{name}: text written with newline translation: {opened}"
    assert len(fake.calls) == 3


def test_label_runs_replace_and_other_runs_append(tmp_path, monkeypatch):
    # covers: TQ-200d-5
    # angle: discrimination
    # must_catch: label runs switched to the append flag
    # must_catch: artifact or transcript runs switched to the replace flag
    fake = fk.setup(tmp_path, monkeypatch)
    instructions = "You are the agent.\nUse the tools.\n"
    for name, run in fk.invokers(tmp_path).items():
        run(instructions, "row input")
        call = fake.calls[-1]
        flags = call.flags()
        want, other = (fk.REPLACE_FLAG, fk.APPEND_FLAG) if fk.REPLACING[name] else (fk.APPEND_FLAG, fk.REPLACE_FLAG)
        assert want in flags and other not in flags, f"{name}: flags are {sorted(flags)}"
        assert "--append-system-prompt" not in flags and "--system-prompt" not in flags, f"{name}: inline flag {sorted(flags)}"
        assert call.prompt_flag == want and call.prompt_seen == instructions.encode("utf-8"), name
    builder = fk.module("agent_launch.command")
    assert (builder.REPLACE_FLAG, builder.APPEND_FLAG, builder.INPUT_ROUTE) == (fk.REPLACE_FLAG, fk.APPEND_FLAG, "stdin")


def _project_files() -> set[str]:
    out = subprocess.run(["git", "ls-files", "-o", "--exclude-standard"], cwd=fk.REPO, capture_output=True, text=True, check=True)
    return set(out.stdout.split("\n"))


@pytest.mark.parametrize("outcome", sorted(_outcomes()))
def test_no_prompt_file_left_after_any_outcome(tmp_path, monkeypatch, outcome):
    # covers: TQ-200d-5
    # angle: failure
    # must_catch: prompt file not removed when the process start raises
    # must_catch: prompt file written inside the row sandbox
    fake = fk.setup(tmp_path, monkeypatch, [_outcomes()[outcome]])
    ev = fk.module("run_agent_eval")
    project_before = _project_files()
    for name, run in fk.invokers(tmp_path).items():
        box = tmp_path / "row-sandbox"
        if outcome == "success":
            run("the instructions\n", "the row input")
        else:
            with pytest.raises(ev.ModelInvocationError):
                run("the instructions\n", "the row input")
        call = fake.calls[-1]
        path = call.prompt_path
        assert path and call.prompt_bytes == b"the instructions\n", f"{name}/{outcome}: no prompt file existed during the call"
        assert not fk.Path(path).exists(), f"{name}/{outcome}: {path} was left behind"
        assert list(fk.private_tmp().iterdir()) == [], f"{name}/{outcome}: the OS temp dir holds {list(fk.private_tmp().iterdir())}"
        resolved = fk.Path(path).resolve()
        assert not resolved.is_relative_to(box.resolve()), f"{name}/{outcome}: the prompt file was in the row sandbox"
        assert not resolved.is_relative_to(fk.REPO.resolve()), f"{name}/{outcome}: the prompt file was in the project tree"
        assert list(box.iterdir()) == [] and call.sandbox_listing in (None, []), f"{name}/{outcome}: sandbox {call.sandbox_listing}"
    assert _project_files() == project_before, "no file appeared in the project tree"


def test_all_three_invokers_go_through_the_shared_builder(tmp_path, monkeypatch):
    # covers: TQ-200d-5
    # angle: seam
    # must_catch: an invoker builds and starts its own command
    fake = fk.setup(tmp_path, monkeypatch)
    subprocess.run(["claude", "--output-format", "json"], capture_output=True, text=True, check=False)
    assert fake.calls[-1].caller == __name__, "control: the recorder names the module that called subprocess.run"
    fake.calls.clear()
    for name, run in fk.invokers(tmp_path).items():
        run("instructions", "input")
        caller = fake.calls[-1].caller
        assert "agent_launch" in caller.split("."), f"{name}: subprocess.run was called from {caller}, not the shared builder"
    assert len(fake.calls) == 3
