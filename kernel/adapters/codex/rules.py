"""
MODULE: kernel.adapters.codex.rules
GOAL: Render the Codex `.rules` file that pre-approves exactly `<python> -m kernel run`,
    `resume` and `status`.
BUSINESS CONTEXT: The default Codex sandbox has no network, and the kernel needs it. A matched
    `prefix_rule(decision="allow")` runs the command outside the sandbox with no prompt, so the
    rule must be as narrow as Claude Code's `allowed-tools`: never a bare interpreter, never
    `cancel`, `gaps`, `decisions` or `install-skill`.
ARCHITECTURE: One `prefix_rule` per subcommand. The first pattern token is a list of
    alternatives holding the interpreter in its native form and, when different, its
    forward-slash form, because the model may type either on Windows (PowerShell-wrapped
    commands are parsed into plain commands before matching). Each rule carries `match` and
    `not_match` examples that Codex checks when it loads the file. Strings are written with
    `json.dumps`, which is valid Starlark.
"""

from __future__ import annotations

import json
from pathlib import Path

from kernel.adapters.skill_common import MARKER, shell_path

ALLOWED_SUBCOMMANDS = ("run", "resume", "status")
REFUSED_SUBCOMMANDS = ("cancel", "gaps", "decisions", "install-skill")


def _literal(items: list[str]) -> str:
    """Return a Starlark list literal of strings."""
    return "[" + ", ".join(json.dumps(item) for item in items) + "]"


def interpreter_forms(python: str) -> list[str]:
    """Return the interpreter spellings to match: as given, then forward-slash if different."""
    forms = [str(python)]
    posix = Path(python).as_posix()
    if posix != forms[0]:
        forms.append(posix)
    return forms


def _rule(forms: list[str], command: str, subcommand: str) -> str:
    """Return the `prefix_rule` for one allowed subcommand."""
    first = _literal(forms) if len(forms) > 1 else json.dumps(forms[0])
    refused = [f"{command} {other}" for other in REFUSED_SUBCOMMANDS]
    example = json.dumps(f"{command} {subcommand} --json")
    return "\n".join([
        "prefix_rule(",
        f'    pattern = [{first}, "-m", "kernel", "{subcommand}"],',
        '    decision = "allow",',
        f'    justification = "Leafcutter kernel {subcommand}: transport only, needs network",',
        f"    match = [{example}],",
        f"    not_match = {_literal(refused)},",
        ")",
    ])


def render_rules(name: str, python: str) -> str:
    """Return the rules file text allowing only run, resume and status for `python`.

    Args:
        name: Skill name, used in the header comment.
        python: Interpreter path the skill invokes.
    """
    forms = interpreter_forms(python)
    command = f"{shell_path(forms[-1])} -m kernel"
    header = [f"# {MARKER}",
              f"# Installed with the `{name}` skill by `python -m kernel install-skill --host codex`.",
              "# Loads only in a trusted project. Allows the kernel run, resume and status",
              "# commands to run outside the sandbox (network); nothing else is allowed.", ""]
    rules = [_rule(forms, command, sub) for sub in ALLOWED_SUBCOMMANDS]
    return "\n".join(header) + "\n" + "\n\n".join(rules) + "\n"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: The interpreter is matched in its native and forward-slash form
#   because Codex matches the first token literally and a Windows model may type either; the
#   skill tells the host to use the forward-slash form. The examples use the forward-slash form
#   so `shlex` does not eat backslashes when Codex checks them. (#KernelCodexSkill)
# ====================================================================
