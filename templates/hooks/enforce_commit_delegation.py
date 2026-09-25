"""
MODULE: enforce_commit_delegation.py
GOAL: PreToolUse hook that blocks a ``git commit`` call unless
    ``COMMIT_AGENT_MODE=1`` is present in the environment. This enforces
    the rule that only the ``commit`` agent template is authorised to call
    ``git commit`` directly; all other agent contexts must dispatch the
    ``commit`` agent via the Agent tool instead.
BUSINESS CONTEXT: The main Claude agent occasionally calls ``git commit``
    directly, bypassing the confirmation gate (Step 3 of commit.md), the
    pre-commit hook failure → autofix path (Step 5), the sign-off recording,
    the background-commit safety check, and the anomaly reporting — the entire
    value of having a dedicated commit agent. This hook mechanically enforces
    the delegation contract: every ``git commit`` call must originate from
    within the ``commit`` agent template, which sets ``COMMIT_AGENT_MODE=1``
    before its own call. Any other context is blocked with an actionable error.
ARCHITECTURE: PreToolUse hook on ``Bash`` tool calls that run git's
    ``commit`` subcommand. The command is split into simple commands on shell
    control operators (quote-aware, including ``$(...)``/backtick bodies),
    each is tokenised with ``shlex``, and a segment counts as a commit when
    its program is ``git`` and its first non-option argument, after git's
    global options (``-C <dir>``, ``-c <k=v>``, ``--git-dir`` ...), is
    ``commit``. Text inside a quoted argument never triggers; unparseable
    quoting fails closed. Checks ``COMMIT_AGENT_MODE`` env var (set only within the commit agent
    template's Step 4). If the env var is absent or not exactly ``"1"``, emits
    a JSON block decision. Fail-open on any exception, malformed stdin, or
    missing command key — identical to the fail-open contract used by
    ``check_commit_ticket_staged.py``.
DOC_LINKS:
  - docs/how-to/agent-commit-discipline.md
  - templates/agents/commit.md

PreToolUse hook contract (Bash tool):
- Exit 0 with no output = silently allow
- Exit 0 with {"decision": "block", "reason": "..."} = block the tool call
- Exit 1 = allow (non-zero exit is not blocking for PreToolUse on Bash)

This hook emits JSON and exits 0 to leverage the block-decision contract.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys

# Characters that end a simple command when they appear outside quotes.
_SEPARATORS = frozenset("&|;\n()")

# git global options that consume the following argv word as their value.
_GIT_VALUE_OPTIONS = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
)

# Leading words that run the command that follows them (or are shell syntax
# in front of it). Any later ``git ... commit`` in such a segment is checked.
_WRAPPERS = frozenset({"env", "command", "exec", "nohup", "sudo", "nice", "time", "timeout",
                       "xargs", "{", "!", "if", "then", "do", "else", "elif", "while", "until"})

_SHELLS = frozenset({"sh", "bash", "zsh", "dash"})

_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Word boundaries for the fail-closed fallback: whitespace and shell syntax.
_FALLBACK_SPLIT_RE = re.compile(r"[\s$()`;&|<>{}]+")


def _command_text(payload: dict) -> str:
    """Return the payload's ``command`` (or legacy ``cmd``) field, ``""`` when absent."""
    tool_input = payload.get("tool_input") or {}
    return str(tool_input.get("command") or tool_input.get("cmd") or "")


def _program_name(word: str) -> str:
    """Return the lower-cased basename of an argv word (``/usr/bin/git`` -> ``git``)."""
    return re.split(r"[\\/]", word)[-1].lower()


def _is_git_program(word: str) -> bool:
    """Return True when the argv word's basename is ``git`` or ``git.exe``."""
    return _program_name(word) in ("git", "git.exe")


def _substitution_span(command: str, index: int) -> tuple[int, int] | None:
    """Return ``(body_start, body_end)`` of a ``$(...)``/backtick opening at ``index``.

    An unterminated substitution runs to the end of the text. Returns None
    when no substitution opens at ``index``.
    """
    if command.startswith("$(", index):
        depth, pos = 1, index + 2
        while pos < len(command) and depth:
            depth += {"(": 1, ")": -1}.get(command[pos], 0)
            pos += 1
        return index + 2, pos - 1 if depth == 0 else pos
    if command[index] == "`":
        close = command.find("`", index + 1)
        return index + 1, close if close != -1 else len(command)
    return None


def _split_simple_commands(command: str) -> list[str]:
    """Split shell text into simple commands, respecting quotes.

    Separators (``&&``, ``||``, ``;``, ``|``, ``&``, newline, parentheses)
    only split outside quotes. The body of every ``$(...)`` or backtick
    substitution outside single quotes (including inside double quotes,
    where the shell still executes it) is split recursively and returned as
    additional commands; the substitution itself is replaced by ``_`` in the
    surrounding command.

    Args:
        command: Full Bash command text.

    Returns:
        Non-blank simple-command strings, still carrying their quotes.
    """
    segments: list[str] = []
    current: list[str] = []
    quote = ""
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'":
            current.append(command[index : index + 2])
            index += 2
            continue
        span = None if quote == "'" else _substitution_span(command, index)
        if span is not None:
            segments.extend(_split_simple_commands(command[span[0] : span[1]]))
            current.append("_")
            index = span[1] + 1
            continue
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char in _SEPARATORS:
            segments.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    segments.append("".join(current))
    return [segment for segment in segments if segment.strip()]


def _git_subcommand(args: list[str]) -> str | None:
    """Return the first argv word after ``git`` that is not a global option or its value."""
    index = 0
    while index < len(args):
        word = args[index]
        if word in _GIT_VALUE_OPTIONS:
            index += 2
        elif word.startswith("-"):
            index += 1
        else:
            return word
    return None


def _shell_script_runs_git_commit(args: list[str]) -> bool:
    """Return True when shell args (``-c <script>``, ``-lc <script>``) run a git commit."""
    for position, word in enumerate(args):
        if word.startswith("-") and not word.startswith("--") and "c" in word[1:]:
            return position + 1 < len(args) and _command_runs_git_commit(args[position + 1])
    return False


def _argv_runs_git_commit(tokens: list[str]) -> bool:
    """Return True when one tokenised simple command runs git's commit.

    Leading ``VAR=value`` assignments are skipped. After a wrapper (``env``,
    ``sudo``, ``xargs`` ...) every later non-wrapper word is tried as the
    program (wrappers are never re-entered, so chained wrappers stay
    linear); a shell ``-c`` script and an ``eval`` body are parsed
    recursively.

    Args:
        tokens: ``shlex``-split argv of one simple command.

    Returns:
        True when the command's program is git and its subcommand is commit.
    """
    words = list(tokens)
    while words and _ASSIGNMENT_RE.match(words[0]):
        words.pop(0)
    if not words:
        return False
    program = _program_name(words[0])
    if _is_git_program(words[0]):
        return _git_subcommand(words[1:]) == "commit"
    if program in _WRAPPERS:
        return any(
            _argv_runs_git_commit(words[start:])
            for start in range(1, len(words))
            if _program_name(words[start]) not in _WRAPPERS
            and not _ASSIGNMENT_RE.match(words[start])
        )
    if program in _SHELLS:
        return _shell_script_runs_git_commit(words[1:])
    if program == "eval":
        return _command_runs_git_commit(" ".join(words[1:]))
    return False


def _fallback_runs_git_commit(segment: str) -> bool:
    """Fail-closed check for text ``shlex`` cannot tokenise (unbalanced quotes).

    Returns True when a ``commit`` word follows a git-program word, splitting
    on whitespace and shell metacharacters and stripping quote characters.
    """
    seen_git = False
    for word in (raw.strip("'\"") for raw in _FALLBACK_SPLIT_RE.split(segment)):
        if _is_git_program(word):
            seen_git = True
        elif seen_git and word == "commit":
            return True
    return False


def _command_runs_git_commit(command: str) -> bool:
    """Return True when any simple command in ``command`` runs a git commit."""
    for segment in _split_simple_commands(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            if _fallback_runs_git_commit(segment):
                return True
            continue
        if _argv_runs_git_commit(tokens):
            return True
    return False


def _is_git_commit_call(payload: dict) -> bool:
    """Return True when the Bash tool input runs git's ``commit`` subcommand.

    Intercepts ``git commit``, ``git commit --amend`` and every spelling
    with git global options in front (``git -C <dir> commit``,
    ``git -c k=v commit``, ``git --git-dir=... commit``), in any simple
    command of a compound line. A command that merely mentions the words
    inside a quoted argument (``echo "git commit"``) is not a commit call.

    Args:
        payload: Parsed PreToolUse JSON payload.

    Returns:
        True when the command runs a git commit. Pathologically deep nesting
        that exhausts recursion fails closed via the word-order fallback.
    """
    command = _command_text(payload)
    try:
        return _command_runs_git_commit(command)
    except RecursionError:
        return _fallback_runs_git_commit(command)


def _is_commit_agent_mode(payload: dict | None = None) -> bool:
    """Return True when the call originates from the commit agent.

    Two detection paths are supported:

    1. **Process environment**: ``os.environ["COMMIT_AGENT_MODE"] == "1"``.
       This is set when the harness injects the variable into the Claude Code
       process before spawning the commit agent.

    2. **Inline command prefix**: the Bash command string starts with the
       token ``COMMIT_AGENT_MODE=1`` (shell inline-assignment syntax).  The
       commit agent template uses this form (``COMMIT_AGENT_MODE=1 git …``)
       which sets the variable for the shell child but not for the hook's own
       process (spawned before the shell runs).  Checking the raw command
       covers that case.

    Either path is sufficient — the check is OR-logic.

    Args:
        payload: Optional PreToolUse JSON payload.  When provided, the
            ``command`` field is inspected for the inline prefix.

    Returns:
        True when either detection path matches; False otherwise.
    """
    if os.environ.get("COMMIT_AGENT_MODE", "") == "1":
        return True
    if payload is not None:
        tool_input = payload.get("tool_input") or {}
        command = str(tool_input.get("command") or tool_input.get("cmd") or "")
        # Accept "COMMIT_AGENT_MODE=1 git commit …" (inline env prefix)
        tokens = command.lstrip().split()
        if "COMMIT_AGENT_MODE=1" in tokens:
            return True
    return False


def _build_block_message() -> str:
    """Build the human-readable blocking reason.

    Returns:
        Multi-line string injected back to the agent as a blocking reason,
        covering: (a) what was blocked, (b) why, and (c) the exact corrective
        action.
    """
    return (
        "PreToolUse blocked: direct git commit is not allowed.\n"
        "\n"
        "What was blocked: a `git commit` call was intercepted outside the "
        "commit agent context (COMMIT_AGENT_MODE is not set to '1').\n"
        "\n"
        "Why: calling `git commit` directly bypasses the confirmation gate "
        "(Step 3 of commit.md), the pre-commit hook failure → autofix path "
        "(Step 5), the sign-off recording, and the background-commit safety "
        "checks. These safeguards only run when commits flow through the "
        "dedicated `commit` agent template.\n"
        "\n"
        "Corrective action: Dispatch the commit agent via the Agent tool "
        "instead of calling git commit directly."
    )


def main() -> None:
    """Entry point. Reads the PreToolUse payload from stdin and emits a decision."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, UnicodeDecodeError):
        # Malformed or undecodable payload — fail-open, do not block
        sys.exit(0)

    # Only intercept Bash tool calls that actually run git's commit subcommand
    if not _is_git_commit_call(payload):
        sys.exit(0)

    # Allow when the commit agent has set its sentinel env var (either via
    # process environment or via the inline COMMIT_AGENT_MODE=1 prefix in
    # the command string — the commit agent template uses the latter form).
    if _is_commit_agent_mode(payload):
        sys.exit(0)

    # Block: direct git commit from a non-commit-agent context
    print(json.dumps({"decision": "block", "reason": _build_block_message()}))
    sys.exit(0)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 09:30 [TICKET-20260605-EnforceCommitAgentDelegation]:
  Initial implementation. PreToolUse hook on Bash tool calls containing
  "git commit". Blocks unless COMMIT_AGENT_MODE=1 is present in the
  environment — a sentinel set only within the commit agent template's
  Step 4 before its own git commit call. Fail-open on all exceptions,
  malformed stdin, and missing command key. Mirrors the structure of
  check_commit_ticket_staged.py: same module docstring sections, same
  JSON block-decision contract, same fail-open exit(0) pattern.
  (#TICKET-20260605-EnforceCommitAgentDelegation)
- 2026-06-08 12:00 [commit]: Add inline command-prefix detection path.
  The hook previously only checked os.environ["COMMIT_AGENT_MODE"], but
  the commit agent template uses the shell inline-assignment form
  "COMMIT_AGENT_MODE=1 git commit …", which sets the var for the shell
  child process but NOT for the hook's own Python process (spawned before
  the shell runs). Added a second detection path that inspects the raw
  command string tokens for the inline prefix, so the hook correctly
  passes commits from the commit agent template.
  (#TICKETLESS reason=hook-correctness-fix-no-ticket-needed)
- 2026-09-25 16:00 [python-coder]: Replace the substring match
  ("git commit" in command) with argv parsing. The substring missed
  "git -C <dir> commit" and every other global-option spelling (five prompt
  sites commit that way) and blocked commands that only quoted the phrase
  (KI-CG-016). Now: quote-aware split into simple commands (substitution
  bodies included), shlex per segment, skip VAR=value prefixes and git
  global options, match subcommand == "commit"; wrappers, sh -c and eval
  are followed; unbalanced quoting fails closed. COMMIT_AGENT_MODE
  exemption unchanged. Covers BP-1100d-3.
  (#TICKETLESS reason=quick-fix-BP-1100d-3-commit-delegation-argv)
====================================================================
"""
