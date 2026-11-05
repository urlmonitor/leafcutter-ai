"""
MODULE: scripts/evals/produced_tests_commands.py
GOAL: The assertion kinds that read the Bash commands of a recorded agent transcript: the shipped
    checker was really run, no command carries a database address of its own, and the tests were run.
BUSINESS CONTEXT: TQ-200d-4. The test runner writes no files, so its use of the project's
    ``testing_context.db_connection_test`` is judged on its commands. A mention of the checker is not
    a run, a failed run is not a run, and an address can hide in a libpq keyword string, an inline
    environment assignment, a positional database name, a ``python -c`` driver call or a ``bash -c``
    string. The checker exits non-zero unless the database is reachable, so a correct run comes back
    as an error result whose content is still the checker's JSON report.
ARCHITECTURE: Pure functions over ``RowContext.calls`` (None when no transcript was recorded, which
    fails every kind here). Each call is split (quote-aware) into simple commands (``&&``, ``||``,
    ``;``, ``|``, newlines; comment lines dropped; ``bash -c`` / ``cmd /c`` strings recursed into) and
    judged command by command, after transparent wrappers (``env``, ``timeout``, ``uv run``, ...) are
    skipped. Registered through produced_tests_db.KINDS into produced_tests_scoring.KINDS.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Callable
from pathlib import Path

from produced_tests_runs import RowContext

QUOTED_OR_SEPARATOR_RE = re.compile(r"""'[^']*'|"(?:\\.|[^"\\])*"|&&|\|\||[;|]""")
PATH_BACKSLASH_RE = re.compile(r"(?<=[\w.:])\\(?=[\w.])")
SHELL_C_RE = re.compile(r"-[A-Za-z]*c[A-Za-z]*")
LAUNCHER_RE = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|py)$")
ASSIGN_RE = re.compile(r"^[A-Za-z_]\w*=")
DB_LITERAL_RE = re.compile(r"postgres(?:ql)?://", re.IGNORECASE)
LIBPQ_RE = re.compile(r"\b(?:host|port|dbname|hostaddr|service)\s*=", re.IGNORECASE)
ENV_ADDRESS_RE = re.compile(r"^(?:PG\w+|\w*(?:DATABASE|DB)_?(?:URL|DSN)\w*)=", re.IGNORECASE)
PG_FLAG_RE = re.compile(r"^(?:-[hpd]\S*|--(?:host|port|dbname|database)(?:=\S*)?)$")
PG_TOOLS = frozenset({"psql", "pg_isready", "pg_dump", "pg_restore", "createdb", "dropdb", "pg_dumpall"})
PG_VALUE_OPTIONS = frozenset({"-c", "-f", "-o", "-U", "-L", "-v", "-P", "-F", "-R", "-T", "-w", "-j", "-t", "-n", "-N", "-Z",
                              "--command", "--file", "--output", "--username", "--set", "--variable", "--jobs"})
POSIX_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
BARE_WRAPPERS = frozenset({"nohup", "time", "command", "exec", "sudo", "nice"})
RUNNER_VALUE_OPTIONS = frozenset({"--with", "--python", "-p", "--project", "--directory", "--env-file", "--extra", "--group"})
PYTHON_VALUE_FLAGS = "cmWX"
HELP_FLAGS = frozenset({"--help", "-h"})


def _split_unquoted(line: str) -> list[str]:
    """*line* cut at every unquoted ``&&``, ``||``, ``;`` and ``|``."""
    parts: list[str] = []
    start = 0
    for match in QUOTED_OR_SEPARATOR_RE.finditer(line):
        if match.group()[0] not in "'\"":
            parts.append(line[start : match.start()])
            start = match.end()
    parts.append(line[start:])
    return parts


def _tokens(part: str) -> list[str]:
    """The shell words of one simple command (a plain whitespace split when the quoting is broken)."""
    try:
        return shlex.split(part)
    except ValueError:
        return part.split()


def _inner_command(tokens: list[str]) -> str | None:
    """The command string handed to ``bash -c`` / ``sh -lc`` / ``cmd /c``, else None."""
    program = _program(tokens)
    args = tokens[_program_index(tokens) + 1 :]
    for i, arg in enumerate(args):
        if program in POSIX_SHELLS and SHELL_C_RE.fullmatch(arg):
            return args[i + 1] if i + 1 < len(args) else None
        if program == "cmd" and arg.lower() in ("/c", "/k"):
            return " ".join(args[i + 1 :])
    return None


def simple_commands(command: str) -> list[list[str]]:
    """The tokens of every simple command in *command*; comment lines and empty commands are dropped.

    A ``bash -c`` / ``sh -c`` / ``cmd /c`` string is read as commands of its own.
    """
    found: list[list[str]] = []
    for line in command.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for part in _split_unquoted(PATH_BACKSLASH_RE.sub("/", line)):
            tokens = _tokens(part)
            inner = _inner_command(tokens) if tokens else None
            if inner:
                found.extend(simple_commands(inner))
            elif tokens:
                found.append(tokens)
    return found


def _base(token: str) -> str:
    """A command token as a program name: lower-cased, without directory and ``.exe``."""
    name = Path(token.replace("\\", "/")).name.lower()
    return name[: -len(".exe")] if name.endswith(".exe") else name


def _skip_options(tokens: list[str], i: int, value_options: frozenset[str]) -> int:
    """Index after the leading ``-x`` options (and the values of *value_options*) starting at *i*."""
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in value_options else 1
    return i


def _skip_wrapper(tokens: list[str], i: int) -> int:
    """Index after the transparent wrapper at *i* (``env``, ``timeout N``, ``uv run`` ...), else *i* itself."""
    name = _base(tokens[i])
    if name in BARE_WRAPPERS:
        return i + 1
    if name == "env":
        j = _skip_options(tokens, i + 1, frozenset({"-u", "-C", "-S"}))
        while j < len(tokens) and ASSIGN_RE.match(tokens[j]):
            j += 1
        return j
    if name == "timeout":
        j = _skip_options(tokens, i + 1, frozenset({"-s", "-k", "--signal", "--kill-after"}))
        return j + 1 if j < len(tokens) and tokens[j][:1].isdigit() else j
    if name in ("uv", "poetry") and tokens[i + 1 : i + 2] == ["run"]:
        return _skip_options(tokens, i + 2, RUNNER_VALUE_OPTIONS)
    return i


def _program_index(tokens: list[str]) -> int:
    """Index of the program token: the first one that is neither a ``NAME=value`` assignment nor a transparent wrapper."""
    i = 0
    while i < len(tokens):
        after = i + 1 if ASSIGN_RE.match(tokens[i]) else _skip_wrapper(tokens, i)
        if after == i:
            return i
        i = after
    return len(tokens)


def _program(tokens: list[str]) -> str:
    """The program name of a simple command, lower-cased, without directory and ``.exe``."""
    i = _program_index(tokens)
    return _base(tokens[i]) if i < len(tokens) else ""


def _value_flag(arg: str) -> tuple[str, str]:
    """For a short-flag cluster such as ``-Im`` / ``-Xutf8``: the python flag that takes a value and its inline value."""
    for pos, char in enumerate(arg[1:], start=1):
        if char in PYTHON_VALUE_FLAGS:
            return char, arg[pos + 1 :]
    return "", ""


def _python_target(args: list[str]) -> tuple[str, str, list[str]]:
    """What python is told to run: ``(kind, name, rest)`` with kind ``s`` script, ``m`` module, ``c`` code or ``""``."""
    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("-") or arg == "-":
            return "s", arg, args[i + 1 :]
        flag, inline = _value_flag(arg) if not arg.startswith("--") else ("", "")
        step = 1 if inline or not flag else 2
        if flag in ("c", "m"):
            return flag, inline or (args[i + 1] if i + 1 < len(args) else ""), args[i + step :]
        i += 2 if arg == "--check-hash-based-pycs" else step
    return "", "", []


def _python_run(tokens: list[str]) -> tuple[str, str, list[str]]:
    """``_python_target`` of a python-launcher command, else ``("", "", [])``."""
    if not LAUNCHER_RE.match(_program(tokens)):
        return "", "", []
    return _python_target(tokens[_program_index(tokens) + 1 :])


def _is_checker_run(tokens: list[str]) -> bool:
    """A python launcher run of db_check/checker.py with ``--target-dir`` (separate or ``=``) and no ``--help``."""
    kind, name, rest = _python_run(tokens)
    if kind != "s" or not name.replace("\\", "/").endswith("db_check/checker.py"):
        return False
    has_target = any(a == "--target-dir" or a.startswith("--target-dir=") for a in rest)
    return has_target and not HELP_FLAGS.intersection(rest)


def _checker_reported(content: str) -> bool:
    """True when a result holds the checker's JSON report (an object with a ``status`` key), amid any noise."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", content):
        try:
            report, _end = decoder.raw_decode(content, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(report, dict) and "status" in report:
            return True
    return False


def commands_run_checker(ctx: RowContext, _spec: dict) -> dict:
    """The agent really ran the shipped checker against the project, and the run did not crash.

    The exit code proves nothing (the checker exits non-zero unless the database is reachable, and a pipe
    or trailing command can mask it), so a run counts only when its result holds the checker's own JSON
    report; a traceback or a usage error is not a run.
    """
    if ctx.calls is None:
        return {"passed": False, "detail": "no command transcript was recorded, so the checker run cannot be shown"}
    runs = [c for c in ctx.calls if any(_is_checker_run(t) for t in simple_commands(c.command))]
    good = [c for c in runs if _checker_reported(c.content)]
    if good:
        return {"passed": True, "detail": f"ran the checker: {good[0].command[:80]}"}
    why = "the checker run left no JSON report: it crashed or was misused" if runs else "no command runs db_check/checker.py with --target-dir"
    return {"passed": False, "detail": f"the checker was never run successfully against the project ({why}; {len(ctx.calls)} command(s) seen)"}


def _positional_database(tokens: list[str]) -> str | None:
    """The first positional argument of a Postgres client command (a database name), else None."""
    args = tokens[_program_index(tokens) + 1 :]
    for i, arg in enumerate(args):
        if not arg.startswith("-") and (i == 0 or args[i - 1] not in PG_VALUE_OPTIONS):
            return arg
    return None


def _pg_problem(tokens: list[str]) -> str | None:
    """What a Postgres client command names as an address: a host/port/database flag or a database argument."""
    flags = [t for t in tokens if PG_FLAG_RE.match(t)]
    if flags:
        return f"a host/port/database flag {flags[0]!r} for {_program(tokens)}"
    database = _positional_database(tokens)
    return f"an address of its own: the positional database {database!r} for {_program(tokens)}" if database else None


def _command_problem(command: str) -> str | None:
    """Why one call's command names an address of its own, else None."""
    if DB_LITERAL_RE.search(command):
        return f"a postgresql:// literal: {command[:80]}"
    if LIBPQ_RE.search(command):
        return f"an address of its own (a host=/port=/dbname= setting): {command[:80]}"
    for tokens in simple_commands(command):
        if any(ENV_ADDRESS_RE.match(t) for t in tokens):
            return f"an address of its own (an inline environment assignment): {command[:80]}"
        problem = _pg_problem(tokens) if _program(tokens) in PG_TOOLS else None
        if problem:
            return problem
    return None


def commands_no_db_address(ctx: RowContext, _spec: dict) -> dict:
    """No command carries a postgresql:// literal, a libpq keyword string, an address variable or a host/port/database flag."""
    if ctx.calls is None:
        return {"passed": False, "detail": "no command transcript was recorded, so the commands cannot be checked for an address"}
    for call in ctx.calls:
        problem = _command_problem(call.command)
        if problem:
            return {"passed": False, "detail": f"a command carries {problem}"}
    return {"passed": True, "detail": f"none of {len(ctx.calls)} command(s) carries an address of its own"}


def _is_pytest_run(tokens: list[str]) -> bool:
    """``pytest ...``, ``python -m pytest ...`` or ``python -Im pytest ...`` (behind any transparent wrapper)."""
    if _program(tokens) in ("pytest", "py.test"):
        return True
    kind, name, _rest = _python_run(tokens)
    return kind == "m" and name == "pytest"


def commands_ran_pytest(ctx: RowContext, _spec: dict) -> dict:
    """At least one simple command runs pytest (the runner actually ran the requested tests)."""
    if ctx.calls is None:
        return {"passed": False, "detail": "no command transcript was recorded, so no pytest run can be shown"}
    ran = [c for c in ctx.calls if any(_is_pytest_run(t) for t in simple_commands(c.command))]
    return {"passed": bool(ran), "detail": f"pytest was run: {ran[0].command[:80]}" if ran else f"no command runs pytest ({len(ctx.calls)} command(s) seen)"}


KINDS: dict[str, Callable[[RowContext, dict], dict]] = {
    "commands_run_checker": commands_run_checker,
    "commands_no_db_address": commands_no_db_address,
    "commands_ran_pytest": commands_ran_pytest,
}
