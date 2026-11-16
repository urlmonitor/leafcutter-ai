"""MODULE: unit_tests/evals/tq200d5/_fake.py

GOAL: Stand in for the process start of the claude CLI so the TQ-200d-5 tests run the REAL harness
    (run_agent_eval's invokers, produced_tests_transcript, the shared launch builder) against a
    REAL child process that is a fake claude, and never call a model.
ARCHITECTURE: ``Fake`` replaces ``subprocess.run`` for the claude launch only (any other call, such as
    git in a produced-tests sandbox, goes to the real one). It records the argv, the keyword arguments,
    the module that called it, the prompt file named on the command line (read before the start) and
    what the child read from its stdin. It then starts ``_fake_claude_program.py`` with the real
    keyword arguments (stdin, text mode, encoding, cwd, env, timeout), so what the child reads is what
    a real claude would read. An outcome can instead raise at the start (the OS refusing it, a timeout).
"""

from __future__ import annotations

import _io
import base64
import builtins
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EVALS = REPO / "scripts" / "evals"
if str(EVALS) not in sys.path:
    sys.path.insert(0, str(EVALS))
from unit_tests.evals.tq200d5._fake_claude_program import FLAG_IN_TEXT, prompt_path  # noqa: E402

PROGRAM = Path(__file__).with_name("_fake_claude_program.py")
REAL_RUN = subprocess.run
LIMIT = 32_767
REPLACE_FLAG = "--system-prompt-file"
APPEND_FLAG = "--append-system-prompt-file"
PROMPT_FLAGS = (REPLACE_FLAG, APPEND_FLAG)
_FLAG_IN_TEXT = FLAG_IN_TEXT


def module(name: str):
    """Import a harness module (scripts/evals is on sys.path)."""
    return importlib.import_module(name)


def is_claude_launch(argv: object) -> bool:
    """The harness's agent launch is the only call with an --output-format option."""
    text = argv if isinstance(argv, str) else " ".join(str(a) for a in argv)
    return "--output-format" in text


def ok(stdout: str | None = None, *, stdout_file: Path | None = None) -> dict:
    """The fake exits 0 and prints *stdout* (or a file's bytes, or a minimal envelope)."""
    out: dict = {}
    if stdout is not None:
        out["stdout"] = stdout
    if stdout_file is not None:
        out["stdout_file"] = str(stdout_file)
    return out


def exits(code: int, stderr: str = "", stdout: str = "") -> dict:
    """The fake starts, then exits non-zero."""
    return {"exit": code, "stderr": stderr, "stdout": stdout}


def unreadable() -> dict:
    """The fake starts and exits 0 with a reply that is not the JSON envelope."""
    return {"stdout": "this is not json at all"}


def times_out(seconds: int = 5) -> dict:
    """The process start reports a timeout."""
    return {"raises": lambda: subprocess.TimeoutExpired(["claude"], seconds, output=b"")}


def cannot_start(exc: BaseException) -> dict:
    """The operating system refuses to start the program with *exc*."""
    return {"raises": lambda: exc}


@dataclass
class Call:
    """One launch of the fake claude, as the harness made it."""

    argv: object
    kwargs: dict
    caller: str
    prompt_path: str | None
    prompt_bytes: bytes | None
    sandbox_listing: list[str] | None
    stdin_bytes: bytes | None = None
    prompt_seen: bytes | None = None

    @property
    def parts(self) -> list[str]:
        return [str(self.argv)] if isinstance(self.argv, str) else [str(a) for a in self.argv]

    @property
    def cmdline(self) -> str:
        """The command line as the operating system would be given it."""
        return self.argv if isinstance(self.argv, str) else subprocess.list2cmdline(self.parts)

    @property
    def prompt_flag(self) -> str | None:
        for flag in PROMPT_FLAGS:
            if flag in self.parts:
                return flag
        found = _FLAG_IN_TEXT.search(self.cmdline)
        return found.group(1) if found else None

    def flags(self) -> set[str]:
        """Every token of the command line that starts with ``--``."""
        return {p for p in re.split(r"\s+", " ".join(self.parts)) if p.startswith("--")}


def _prompt_path(argv: object) -> str | None:
    return prompt_path([argv] if isinstance(argv, str) else list(argv))[1]


class Fake:
    """Replaces subprocess.run for the claude launch; the plan lists one outcome per launch (the last repeats)."""

    def __init__(self, tmp_path: Path, monkeypatch, plan: list[dict] | None = None) -> None:
        self.dir = tmp_path / "fake_claude_calls"
        self.dir.mkdir(exist_ok=True)
        self.plan = plan or [ok()]
        self.calls: list[Call] = []
        monkeypatch.setattr(subprocess, "run", self._run)

    def _run(self, argv, **kw):
        if not is_claude_launch(argv):
            return REAL_RUN(argv, **kw)
        number = len(self.calls)
        path = _prompt_path(argv)
        cwd = kw.get("cwd")
        listing = sorted(str(p) for p in Path(cwd).rglob("*")) if cwd and Path(cwd).is_dir() else None
        call = Call(argv, dict(kw), sys._getframe(1).f_globals.get("__name__", "?"), path,
                    Path(path).read_bytes() if path and Path(path).is_file() else None, listing)
        self.calls.append(call)
        outcome = self.plan[min(number, len(self.plan) - 1)]
        if "raises" in outcome:
            raise outcome["raises"]()
        program = argv if isinstance(argv, str) else str(argv[0])
        shell_program = Path(program.replace("\\", "/")).name.lower() in ("cmd", "cmd.exe")
        if not isinstance(argv, str) and not shell_program and (os.sep in program or "/" in program) and not Path(program).exists():
            raise FileNotFoundError(2, "No such file or directory", program)
        argv_file = self.dir / f"argv-{number:03d}.json"
        argv_file.write_text(json.dumps([argv] if isinstance(argv, str) else [str(a) for a in argv]), encoding="utf-8")
        env = dict(kw.get("env") or os.environ)
        env.update(FAKE_CLAUDE_DIR=str(self.dir), FAKE_CLAUDE_ARGV_FILE=str(argv_file), FAKE_CLAUDE_CALL=str(number),
                   FAKE_CLAUDE_OUTCOME=json.dumps(dict(outcome)))
        real_kw = dict(kw, env=env)
        real_kw.pop("shell", None)
        if "input" not in real_kw and real_kw.get("stdin") is None:
            real_kw["stdin"] = subprocess.DEVNULL
        done = REAL_RUN([sys.executable, str(PROGRAM)], **real_kw)
        logged = json.loads((self.dir / f"call-{number:03d}.json").read_text(encoding="utf-8"))
        call.stdin_bytes = base64.b64decode(logged["stdin_b64"])
        call.prompt_seen = base64.b64decode(logged["prompt_b64"]) if logged["prompt_b64"] is not None else None
        return done


class OpenSpy:
    """Records every text-mode write open of a file in the private temp dir (or by descriptor)."""

    def __init__(self, monkeypatch, private_tmp: Path) -> None:
        self.opens: list[dict] = []
        real = io.open

        def spy(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, *args, **kwargs):
            writing = any(c in mode for c in "wax+") and "b" not in mode
            if writing and (isinstance(file, int) or str(file).startswith(str(private_tmp))):
                self.opens.append({"mode": mode, "encoding": encoding, "newline": newline})
            return real(file, mode, buffering, encoding, errors, newline, *args, **kwargs)

        def text_encoding(encoding, stacklevel=2):
            """Without UTF-8 mode, an unnamed encoding is the locale's: the spy must see that, whatever mode the tests run in."""
            return "locale" if encoding is None else encoding

        for target in (io, builtins, _io):
            monkeypatch.setattr(target, "open", spy)
        for target in (io, _io):
            monkeypatch.setattr(target, "text_encoding", text_encoding)


def make_cli_dir(directory: Path) -> Path:
    """A folder holding a dummy ``claude`` (and ``claude.cmd``); nothing in it is ever run."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "claude").write_text("#!/bin/sh\n", encoding="utf-8")
    (directory / "claude").chmod(0o755)
    (directory / "claude.cmd").write_text("@echo off\r\n", encoding="utf-8")
    return directory


def setup(tmp_path: Path, monkeypatch, plan: list[dict] | None = None) -> Fake:
    """Private OS temp dir, a PATH that finds a dummy claude, no CLI-location setting, the fake in place."""
    private = tmp_path / "ostemp"
    private.mkdir(exist_ok=True)
    for name in ("TMP", "TEMP", "TMPDIR"):
        monkeypatch.setenv(name, str(private))
    monkeypatch.setattr(tempfile, "tempdir", str(private))
    monkeypatch.setenv("PATH", str(make_cli_dir(tmp_path / "cli_on_path")) + os.pathsep + os.environ.get("PATH", ""))
    for name in ("LEAFCUTTER_EVAL_CLAUDE_CLI", "LEAFCUTTER_EVAL_USE_API"):
        monkeypatch.delenv(name, raising=False)
    return Fake(tmp_path, monkeypatch, plan)


def private_tmp() -> Path:
    return Path(tempfile.gettempdir())


# ---------------------------------------------------------------------------
# The three ways the harness starts an agent, and the real inputs
# ---------------------------------------------------------------------------
LONG_SANDBOX = "C:/Users/some.person/AppData/Local/Temp/produced-tests-abcd1234/score/" + "deeply-nested-folder-name/" * 6 + "sandbox"
_LINE = "Row \"quoted\" line\r\nwith 'single' \\ backslash \u00b7 \u00e9 \u4e2d \U0001F600\nand a % sign & a ^ caret\n"
BIG_INPUT = "  \n" + (_LINE * 700)[: 40_000 - 5] + "\n  "
INVOKER_NAMES = ("label", "artifact", "transcript")
REPLACING = {"label": True, "artifact": False, "transcript": False}


def rendered_test_writer() -> str:
    """The real test-writer template, rendered for a row over a long Windows-style sandbox path."""
    ev, pm = module("run_agent_eval"), module("produced_tests_mode")
    body = ev.load_system_prompt(REPO / "templates" / "agents" / "test-writer.md")
    return pm.render_prompt(body, Path(LONG_SANDBOX))


def invokers(tmp_path: Path) -> dict:
    """name -> callable(instructions, row_input) running that invoker once (raises what it raises)."""
    ev, tx = module("run_agent_eval"), module("produced_tests_transcript")
    box = tmp_path / "row-sandbox"
    box.mkdir(exist_ok=True)
    return {
        "label": lambda s, u: ev.invoke_via_cli(s, u, "haiku", 30),
        "artifact": lambda s, u: ev.invoke_agent_writer(s, u, "opus", 30, box, "Read,Write"),
        "transcript": lambda s, u: tx.invoke_with_transcript(s, u, "sonnet", 30, box, "Read,Bash", ev.ModelInvocationError)[0],
    }


def make_real_cli_dir(directory: Path, *, shell_wrapper: bool = False) -> Path:
    """A folder whose ``claude`` (posix script) and ``claude.cmd`` (Windows) really run the fake claude program.

    With *shell_wrapper* the posix ``claude`` is an sh script that starts the program as a child (as the npm
    launchers do), so the program is a grandchild of the harness.
    """
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "claude"
    if shell_wrapper:
        body = f'#!/bin/sh\n"{sys.executable}" "{PROGRAM}" "$@"\n'
    else:
        body = f"#!{sys.executable}\nimport runpy\nrunpy.run_path({str(PROGRAM)!r}, run_name='__main__')\n"
    script.write_text(body, encoding="utf-8", newline="\n")
    script.chmod(0o755)
    cmd_body = f'@echo off\r\n"{sys.executable}" "{PROGRAM}" %*\r\n'
    (directory / "claude.cmd").write_text(cmd_body, encoding="utf-8", newline="")
    return directory


def norm(path: object) -> str:
    """A path or token compared the way Windows compares it: separators and case folded, quotes stripped."""
    return str(path).strip('"').replace("/", "\\").lower()


def win_which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """shutil.which as Windows does it: PATH folders in order, PATHEXT extensions, case-insensitive names."""
    folders = (path if path is not None else os.environ.get("PATH", "")).split(os.pathsep)
    exts = [e for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
    names = [cmd] if any(cmd.lower().endswith(e.lower()) for e in exts) else [cmd + e for e in exts]
    for folder in folders:
        listing = {f.lower(): f for f in os.listdir(folder)} if folder and Path(folder).is_dir() else {}
        for name in names:
            if name.lower() in listing:
                return str(Path(folder) / listing[name.lower()])
    return None


def posix_which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """shutil.which as Linux does it: the exact name in a PATH folder."""
    for folder in (path if path is not None else os.environ.get("PATH", "")).split(os.pathsep):
        candidate = Path(folder) / cmd
        if folder and candidate.is_file():
            return str(candidate)
    return None


def as_platform(monkeypatch, platform: str) -> None:
    """Treat the machine as Windows (``win32``) or Linux for the program lookup: sys.platform, PATHEXT, shutil.which."""
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    monkeypatch.setattr(shutil, "which", win_which if platform == "win32" else posix_which)


def only_path(monkeypatch, *folders: Path) -> None:
    """PATH holds just these folders (the fake child is started by absolute path, so nothing else is needed)."""
    monkeypatch.setenv("PATH", os.pathsep.join(str(f) for f in folders))
