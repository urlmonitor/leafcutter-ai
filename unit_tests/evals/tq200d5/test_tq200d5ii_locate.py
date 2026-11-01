"""MODULE: test_tq200d5ii_locate

GOAL: Prove the harness finds the claude CLI the way the Windows command shell does (PATH and PATHEXT, a
    ``.cmd`` launcher started through the command processor), that LEAFCUTTER_EVAL_CLAUDE_CLI names the
    program to start on every platform and never falls back to PATH, that Linux is unchanged, and that the
    README and the how-to name the setting the code reads.

    ``_fake.as_platform`` makes the machine count as Windows or Linux for the lookup (sys.platform, PATHEXT,
    shutil.which); the process start is the fake of ``_fake.py``, so nothing here starts a real program.

Target modules: scripts/evals/agent_launch/locate.py, scripts/evals/agent_launch/command.py
AC: TQ-200d-5-ii
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import unit_tests.evals.tq200d5._docs as docs
import unit_tests.evals.tq200d5._fake as fk
import unit_tests.evals.tq200d5._runs as rn

PREFIX = "agent CLI could not be launched"
SETTING = "LEAFCUTTER_EVAL_CLAUDE_CLI"
PREFIX_PATH = re.compile(r"prefix(?:ing|es)?\s+(?:your\s+|the\s+)?PATH", re.I)
TEMPLATE_SAMPLE = re.compile(r"[A-Za-z ,]{80}")


def _folder(tmp_path: Path, name: str, *files: str) -> Path:
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    for file in files:
        (folder / file).write_text("dummy launcher, never run\r\n", encoding="utf-8")
        (folder / file).chmod(0o755)
    return folder


def _env(platform: str, path_folder: Path, setting: Path | None = None):
    """A ``before`` hook: the machine counts as *platform*, PATH holds only *path_folder*, the setting is *setting*."""
    def before(monkeypatch) -> None:
        fk.as_platform(monkeypatch, platform)
        fk.only_path(monkeypatch, path_folder)
        if setting is not None:
            monkeypatch.setenv(SETTING, str(setting))
    return before


def _one_row(tmp_path, monkeypatch, capsys, caplog, before, name="run"):
    sub = tmp_path / name
    sub.mkdir()
    result = rn.run("label", sub, monkeypatch, capsys, caplog, [rn.ok_reply("label")], rows=1, before=before)
    return result


def test_cmd_only_path_on_windows_starts_the_installed_launcher(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-ii
    # angle: discrimination
    # must_catch: bare name 'claude' passed to the process start on Windows
    # must_catch: resolved .cmd started directly without the command processor
    # must_catch: extensionless npm shell script picked instead of claude.cmd
    npm = _folder(tmp_path, "npm", "claude", "claude.cmd", "claude.ps1")
    result = _one_row(tmp_path, monkeypatch, capsys, caplog, _env("win32", npm))
    assert result.fake.calls, "the agent was never started"
    call = result.fake.calls[0]
    assert result.code == 0 and result.rows[0]["score"]["passed"] is True, "the row was scored"
    assert fk.norm(npm / "claude.cmd") in fk.norm(call.cmdline), f"claude.cmd of the PATH folder is not what was started: {call.cmdline[:200]}"
    assert fk.norm(call.parts[0]) != "claude", "the bare name was handed to the process start"
    assert ".ps1" not in call.cmdline.lower()
    through_shell = bool(re.match(r'^"?(?:[^"]*[\\/])?cmd(?:\.exe)?"?\s', call.cmdline.lower())) or call.kwargs.get("shell") is True
    assert through_shell, "a .cmd must be started through the command processor, not directly"


@pytest.mark.parametrize("platform", ["win32", "linux", "win32-cmd"])
def test_cli_location_setting_wins_on_every_platform(tmp_path, monkeypatch, capsys, caplog, platform):
    # covers: TQ-200d-5-ii
    # angle: discrimination
    # must_catch: setting ignored when a claude is on the path
    # must_catch: setting honoured only on Windows
    # must_catch: missing program in the setting silently replaced by the PATH lookup
    system = platform.split("-")[0]
    on_path = _folder(tmp_path, "on-path", "claude", "claude.cmd")
    suffix = {"win32": "my-tool.exe", "linux": "my-tool", "win32-cmd": "my-tool.cmd"}[platform]
    named = _folder(tmp_path, "tools", suffix) / suffix
    result = _one_row(tmp_path, monkeypatch, capsys, caplog, _env(system, on_path, named))
    assert result.fake.calls, "the agent was never started"
    call = result.fake.calls[0]
    assert result.code == 0 and result.rows[0]["score"]["passed"] is True
    assert fk.norm(named) in fk.norm(call.cmdline), f"{platform}: the setting's program was not started: {call.cmdline[:200]}"
    assert fk.norm(on_path / "claude") not in fk.norm(call.cmdline), f"{platform}: the PATH claude was started"
    # a setting that names no program is a launch failure with the operating-system reason, never a fall back
    missing = tmp_path / "nowhere" / ("missing-claude" if system == "linux" else "missing-claude.exe")
    failed = _one_row(tmp_path, monkeypatch, capsys, caplog, _env(system, on_path, missing), "run-missing")
    text = rn.launch_text(failed)
    assert text.startswith(PREFIX) and "FileNotFoundError" in text, text
    assert all(fk.norm(on_path / "claude") not in fk.norm(c.cmdline) for c in failed.fake.calls), "fell back to the PATH claude"
    assert all(c.stdin_bytes is None for c in failed.fake.calls), "a program that does not exist was started"


def test_linux_without_setting_starts_claude_from_path_as_before(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-ii
    # angle: boundary
    # must_catch: Linux start routed through a shell
    on_path = _folder(tmp_path, "usr-bin", "claude", "claude.cmd")
    result = _one_row(tmp_path, monkeypatch, capsys, caplog, _env("linux", on_path))
    assert result.fake.calls, "the agent was never started"
    call = result.fake.calls[0]
    assert result.code == 0 and isinstance(call.argv, list), "a list, not a command string"
    assert call.kwargs.get("shell") in (None, False), "no shell"
    program = call.parts[0]
    assert fk.norm(program) in ("claude", fk.norm(on_path / "claude")), f"program is {program!r}, not claude from PATH"
    assert not program.lower().endswith((".cmd", ".bat", "cmd.exe"))
    assert call.stdin_bytes == b"request 1", "the row input travels on stdin on Linux too"


@pytest.mark.parametrize("folder", ["plain", "spaced & caret^ folder", "amp&caret^"])
def test_cmd_launch_keeps_instructions_off_the_command_line(tmp_path, monkeypatch, folder):
    # covers: TQ-200d-5-ii
    # angle: boundary
    # must_catch: instructions inlined when the launcher is a .cmd
    # must_catch: prompt-file path left unquoted for the command processor
    npm = _folder(tmp_path, "npm", "claude.cmd")
    fake = fk.setup(tmp_path, monkeypatch)
    _env("win32", npm)(monkeypatch)
    weird = tmp_path / folder
    weird.mkdir()
    monkeypatch.setattr(fk.tempfile, "tempdir", str(weird))
    instructions = fk.rendered_test_writer()
    sample = TEMPLATE_SAMPLE.search(instructions, 5000).group(0)
    for name, run in fk.invokers(tmp_path).items():
        run(instructions, fk.BIG_INPUT)
        call = fake.calls[-1]
        assert fk.norm(npm / "claude.cmd") in fk.norm(call.cmdline), name
        assert len(call.cmdline) < fk.LIMIT and sample not in call.cmdline, f"{name}: instructions are on the command line"
        path = call.prompt_path
        assert path and str(weird) in path, f"{name}: the prompt file is not in the temp dir ({path})"
        at = call.cmdline.find(path)
        assert at > 0 and call.cmdline[at - 1] == '"' and call.cmdline[at + len(path)] == '"', f"{name}: {path} is not quoted: {call.cmdline[-300:]}"
        assert call.prompt_bytes == instructions.encode("utf-8"), name


def test_all_three_invokers_use_the_one_lookup(tmp_path, monkeypatch):
    # covers: TQ-200d-5-ii
    # angle: seam
    # must_catch: one invoker still starts the bare name 'claude'
    fake = fk.setup(tmp_path, monkeypatch)
    fk.as_platform(monkeypatch, "linux")
    sentinel = _folder(tmp_path, "sentinel", "sentinel-claude") / "sentinel-claude"
    # the setting is the lookup's first answer: every invoker must start what it names (this reaches the code as it is today)
    monkeypatch.setenv(SETTING, str(sentinel))
    for name, run in fk.invokers(tmp_path).items():
        run("instructions", "input")
        started = fake.calls[-1].parts[0]
        assert fk.norm(started) == fk.norm(sentinel), f"{name} started {started!r} instead of the program the lookup names"
    # and the lookup itself, replaced, is what all three ask
    monkeypatch.delenv(SETTING)
    other = _folder(tmp_path, "other", "other-claude") / "other-claude"
    locate, command = fk.module("agent_launch.locate"), fk.module("agent_launch.command")
    monkeypatch.setattr(locate, "find_claude", lambda *a, **k: str(other))
    monkeypatch.setattr(command, "find_claude", lambda *a, **k: str(other), raising=False)
    for name, run in fk.invokers(tmp_path).items():
        run("instructions", "input")
        started = fake.calls[-1].parts[0]
        assert fk.norm(started) == fk.norm(other), f"{name} started {started!r} instead of the looked-up program"
    assert len(fake.calls) == 6


def test_docs_name_the_setting_the_harness_reads():
    # covers: TQ-200d-5-ii
    # angle: real_artifact
    readme, how_to = docs.text_of(docs.README), docs.text_of(docs.HOW_TO)
    finding = docs.section(readme, "How the harness finds claude")
    windows = docs.section(how_to, "Finding claude on Windows")
    name = fk.module("agent_launch.locate").CLI_ENV_VAR
    assert name == SETTING
    for where, text in (("README section", finding), ("how-to section", windows)):
        assert name in text, f"the {where} does not name {name}"
    assert re.search(rf"{name}\s*=\s*\S+|setx?\s+{name}\s+\S+|\$env:{name}\s*=", finding), "the README gives one example"
    for needle in ("PATHEXT", ".cmd", "command processor"):
        assert needle in finding, f"the README section does not mention {needle}"
    assert "PATHEXT" in windows and ".cmd" in windows
    assert not PREFIX_PATH.search(how_to) and not PREFIX_PATH.search(readme), "the prefix-PATH workaround is still documented"
    assert PREFIX_PATH.search("First prefix PATH with the folder of claude.exe.") and not PREFIX_PATH.search("Set the CLI location instead.")
    other = set(re.findall(r"LEAFCUTTER_EVAL_[A-Z_]+", how_to + readme)) - {name, "LEAFCUTTER_EVAL_USE_API"}
    assert not other, f"setting names the code does not read: {sorted(other)}"
