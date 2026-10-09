"""
MODULE: check_exception_handling_hook.py
GOAL: PostToolUse hook that runs ruff's exception-handling rules on any .py
    file created or modified via Edit or Write, and injects a blocking feedback
    message when a violation is found so Claude corrects the issue in the same
    turn.
BUSINESS CONTEXT: Ticket 02 of EPIC-ErrorHandlingEnforcement. Claude Code
    frequently writes bare ``except:`` clauses (E722) or catches blind
    exceptions (BLE001) that silence errors and make debugging impossible. A
    PostToolUse hook provides the tightest feedback loop: the violation is
    surfaced before the next tool call, not at commit time. This complements
    the pre-commit rule set in ticket 01.
ARCHITECTURE: PostToolUse hook on Edit|Write tool calls. Reads the file path
    from the hook payload (stdin JSON), skips non-.py files silently, runs
    ``ruff check --select E722,BLE001,TRY --output-format concise <path>``,
    and exits 2 (blocking) when violations are found. Ruff-not-found is caught
    and surfaced as an install instruction rather than a silent crash.

PostToolUse hook contract (Claude Code):
- Exit 0 with no output              = silently allow (pass)
- Exit 2 with text on stderr         = block the next step and show the text
  (Claude Code treats any non-zero exit from a PostToolUse hook as a blocking
  feedback message injected into the active turn, but only reads that text
  from the hook's STDERR — anything written to stdout is discarded; exit 2 is
  the conventional "block with content" exit code used by Claude Code hooks.)

Self-contained: this script must NOT import any leafcutter-internal modules.
Ruff is located via PATH only.

PORTABILITY NOTE: This script is installed from templates/hooks/ into the
target project's .claude/hooks/ directory by build.py during the build phase.
It must work in any Python ≥ 3.8 environment without leafcutter being installed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ruff configuration
# ---------------------------------------------------------------------------

#: Rules to check for — same set as the pre-commit config (ticket 01).
#: E722: bare ``except:`` clause.
#: BLE001: caught blind exception (``except Exception:`` with no narrowing).
#: TRY: tryceratops rule family (broad try blocks, reraise, etc.).
RUFF_SELECT = "E722,BLE001,TRY"


# ---------------------------------------------------------------------------
# Hook payload parsing
# ---------------------------------------------------------------------------


def _extract_file_path(payload: dict) -> str | None:
    """Extract the edited file path from the PostToolUse hook payload.

    Claude Code's PostToolUse payload shape varies slightly between tool types:

    - **Write** sets ``tool_input.file_path`` (the path written to).
    - **Edit** sets ``tool_input.path`` or ``tool_input.file_path``.
    - Some versions surface the path in ``tool_response`` as well.

    We check all known locations in precedence order and return the first
    non-empty string found.

    Args:
        payload: Parsed PostToolUse JSON payload from stdin.

    Returns:
        The file path string, or ``None`` when the payload carries no path.
    """
    # tool_input: primary source for both Edit and Write
    tool_input = payload.get("tool_input") or {}
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if value and isinstance(value, str) and value.strip():
            return value.strip()

    # tool_response: fallback for some hook variants
    tool_response = payload.get("tool_response") or {}
    if isinstance(tool_response, dict):
        for key in ("path", "file_path"):
            value = tool_response.get(key)
            if value and isinstance(value, str) and value.strip():
                return value.strip()
    elif isinstance(tool_response, str) and tool_response.strip():
        # Rare: some hook implementations pass the path as a bare string
        return tool_response.strip()

    return None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _is_python_file(path: str) -> bool:
    """Return True when *path* has a ``.py`` extension (case-insensitive).

    Args:
        path: The file path string to check.

    Returns:
        True for ``.py`` files; False for all other extensions.
    """
    return Path(path).suffix.lower() == ".py"


#: Substring ruff's own CLI prints to stderr when `python -m ruff` runs
#: under an interpreter that cannot import the `ruff` package at all. This
#: is the ONLY signal that disambiguates "ruff module is absent" (exits
#: non-zero, does not raise) from "ruff ran and found a real violation"
#: (also exits non-zero) -- the two cases cannot be told apart by exit code
#: alone. See GE-108e.
_RUFF_MODULE_MISSING_MARKER = "No module named ruff"


def _run_ruff_subprocess(argv: list[str], path: str) -> tuple[int, str]:
    """Run *argv* (a ruff invocation, module or executable form) on *path*.

    Shared by both lookup forms in `_run_ruff` so the output-joining and
    OSError re-raise behaviour is defined once.

    Raises:
        FileNotFoundError: When the invoked interpreter/executable itself
            cannot be found (an OSError subclass).
        OSError: Any other failure launching the subprocess.

    Args:
        argv: The full argv to run (interpreter + "-m" + "ruff" + ... , or
            the bare "ruff" executable + ...).
        path: Absolute or relative path to the Python file to check — used
            only for the docstring's own cross-reference, the real value is
            already baked into `argv`.

    Returns:
        A ``(returncode, combined_output)`` pair, stdout and stderr joined
        with a newline (whichever are non-empty).
    """
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        # Deliberate re-raise, not a swallow. This boundary is handled by the
        # CALLER (main()), which distinguishes FileNotFoundError -- ruff is not
        # installed, a blocking condition with its own install instruction --
        # from every other OSError, which fails open. Deciding either here
        # would duplicate that routing and put the exit-code choice in two
        # places. FileNotFoundError is an OSError subclass, so both travel
        # this path untouched.
        raise
    output_parts = []
    if result.stdout.strip():
        output_parts.append(result.stdout.strip())
    if result.stderr.strip():
        output_parts.append(result.stderr.strip())
    return result.returncode, "\n".join(output_parts)


def _run_ruff(path: str) -> tuple[int, str]:
    """Run ruff check on *path* and return ``(returncode, combined_output)``.

    Locates ruff the same way the rest of the project does: the MODULE form
    (``python -m ruff``) first, falling back to the bare ``ruff`` executable
    only when the module form proves absent. This matters on a machine where
    ruff is importable but exposes no console script on PATH -- the bare
    executable alone would wrongly report ruff as not installed (GE-108e).

    A missing `ruff` MODULE does not raise: `python -m ruff` with the module
    absent exits non-zero and prints "No module named ruff" to stderr. A
    real E722 violation ALSO exits non-zero, so the two cases are
    disambiguated on that stderr text, never on exit code alone -- treating
    any non-zero exit as module-absent would make every genuine violation
    fall through to the second invocation.

    Raises:
        FileNotFoundError: When neither the module form nor the fallback
            bare executable can be found. Deliberately left to propagate so
            `main()`'s existing branch turns it into the install
            instruction on stderr (GE-108d's routing).

    Args:
        path: Absolute or relative path to the Python file to check.

    Returns:
        A ``(returncode, output)`` tuple where ``output`` is ruff's combined
        stdout (violations) and stderr (diagnostic messages) joined with a
        newline. Return code is 0 when no violations are found, 1 when
        violations exist.
    """
    ruff_args = ["check", "--select", RUFF_SELECT, "--output-format", "concise", path]
    returncode, output = _run_ruff_subprocess([sys.executable, "-m", "ruff", *ruff_args], path)
    if _RUFF_MODULE_MISSING_MARKER in output:
        # The module form answered (did not raise) but ruff is not
        # importable under this interpreter -- fall through to the bare
        # executable. A FileNotFoundError here (executable also absent)
        # propagates untouched, per this function's own contract.
        return _run_ruff_subprocess(["ruff", *ruff_args], path)
    return returncode, output


def _build_block_message(path: str, ruff_output: str) -> str:
    """Build the human-readable blocking message for Claude.

    Args:
        path: File path that was checked.
        ruff_output: The raw ruff output (violations found).

    Returns:
        Multi-line string injected back to Claude as a blocking feedback entry.
    """
    return (
        "EXCEPTION HANDLING VIOLATION — ruff found issues in:\n"
        f"  {path}\n"
        "\n"
        f"{ruff_output}\n"
        "\n"
        "Fix the violation(s) above before proceeding. Rules:\n"
        "  E722 = bare except: clause (must name the exception type)\n"
        "  BLE001 = blind exception catch (too broad; narrow the exception)\n"
        "  TRY   = tryceratops family (restructure the try/except block)\n"
        "\n"
        "Correct pattern:\n"
        "  try:\n"
        "      <operation>\n"
        "  except <SpecificError> as exc:\n"
        "      <handle or re-raise>\n"
    )


def _build_ruff_not_found_message(path: str) -> str:
    """Build the install instruction message when ruff is not on PATH.

    Args:
        path: File path that was attempted.

    Returns:
        Multi-line string instructing the user how to install ruff.
    """
    return (
        "EXCEPTION HANDLING HOOK: ruff not found on PATH.\n"
        f"  File: {path}\n"
        "\n"
        "The exception-handling hook could not run because ruff is not installed\n"
        "or not on the system PATH.\n"
        "\n"
        "Install ruff with one of:\n"
        "  pip install ruff\n"
        "  uv add ruff\n"
        "  brew install ruff\n"
        "  pipx install ruff\n"
        "\n"
        "After installing, re-run the tool call that triggered this hook.\n"
        "Until ruff is available, exception-handling violations will not be\n"
        "caught at authoring time. They will still be caught at commit time\n"
        "by the pre-commit ruff hook."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point. Reads the PostToolUse payload from stdin and emits output."""
    # 1. Parse the JSON payload from stdin. Fail-open on malformed input.
    try:
        raw = sys.stdin.read() or "{}"
        payload = json.loads(raw)
    except (ValueError, OSError):
        # Malformed payload — silently allow, do not block Claude.
        # ValueError covers json.JSONDecodeError and the UnicodeDecodeError a
        # non-UTF-8 stdin raises; OSError covers the read itself failing.
        # Staying silent is the point: this hook must never turn a payload it
        # cannot parse into a block, and a message here would fire on every
        # malformed payload without telling the author anything actionable.
        sys.exit(0)

    # 2. Extract the file path from the payload.
    file_path = _extract_file_path(payload)
    if not file_path:
        # No path in payload — silently allow
        sys.exit(0)

    # 3. Skip non-.py files silently (markdown, JSON, YAML, etc.)
    if not _is_python_file(file_path):
        sys.exit(0)

    # 4. Verify the file exists on disk (Write may have created it;
    #    Edit always modifies an existing file — both should be on disk now).
    try:
        resolved = Path(file_path).resolve()
    except (OSError, ValueError, RuntimeError):
        # Unresolvable path — silently allow, for the same reason as the
        # payload parse above. OSError covers the filesystem refusing the
        # lookup, ValueError an embedded null byte, RuntimeError a symlink
        # loop on the Python versions that still raise it there.
        sys.exit(0)
    if not resolved.exists():
        # File not on disk yet (dry-run or cancelled write) — silently allow
        sys.exit(0)

    # 5. Run ruff.
    try:
        returncode, ruff_output = _run_ruff(str(resolved))
    except FileNotFoundError:
        # ruff is not installed — inject the install instruction and block
        print(_build_ruff_not_found_message(file_path), file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        # Other OS-level error (permission denied, etc.) — fail-open
        print(f"  [hook warning] could not run ruff on {file_path}: {exc}", file=sys.stderr)
        sys.exit(0)

    # 6. Route on ruff's return code.
    if returncode == 0:
        # Clean — silently allow
        sys.exit(0)

    # Violations found — block and show the output to Claude
    print(_build_block_message(file_path, ruff_output), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-01 [EPIC-ErrorHandlingEnforcement/02]: Initial implementation.
  PostToolUse hook on Edit|Write. Reads file path from the hook payload,
  skips non-.py files, runs ruff check --select E722,BLE001,TRY, exits 2
  (block) on violations, exits 0 (pass) when clean, and handles
  ruff-not-found with an install instruction rather than a silent crash.
  Self-contained: no leafcutter-internal imports. Ruff is located via PATH.
  Installed by build.py from templates/hooks/ into .claude/hooks/ of the
  target project. Complements the pre-commit rule set from ticket 01.
- 2026-10-07 [GE-108d]: Routed both blocking messages (ruff-not-found and
  ruff-violations-found) from stdout to stderr via ``file=sys.stderr``.
  Claude Code reads PostToolUse blocking feedback from stderr only; a
  message on stdout is discarded, so the agent saw a block with no visible
  reason. The OSError fail-open branch already used stderr correctly — this
  change brings the two blocking branches in line with it. Corrected the
  module docstring's hook-contract line, which previously documented stdout
  as the right channel and was the reason the bug was written this way.
  Channel-only change: exit codes, message text, RUFF_SELECT, and skip
  conditions are unchanged.
- 2026-10-07 [GE-108d]: Cleared three Error Handling Policy violations this
  file had carried unflagged. They are PRE-EXISTING, not introduced by the
  channel fix above: GE-108a taught the commit-time guard to treat
  subprocess as an I/O boundary on 2026-06-17, after this file was last
  staged, so the guard first saw them when the channel fix re-staged it.
  Narrowed the payload-parse handler to ``(ValueError, OSError)`` and the
  path-resolve handler to ``(OSError, ValueError, RuntimeError)`` -- both
  stay deliberately silent and keep failing open, since a hook that cannot
  read its own payload must never turn that into a block. Wrapped
  ``subprocess.run`` in ``_run_ruff`` and re-raised: the install-vs-fail-open
  routing for that boundary belongs to main(), which already distinguishes
  FileNotFoundError from every other OSError, and duplicating it here would
  put the exit-code choice in two places. No observable behaviour changed --
  the suite is green across all seven tests before and after.
- 2026-10-07 [GE-108e]: `_run_ruff` invoked only the bare `ruff` executable,
  so a machine where ruff is importable as a module but exposes no console
  script on PATH took the not-installed branch and blocked every Python
  write, while `python -m ruff` answered fine two lines away. Split the
  subprocess call into `_run_ruff_subprocess` (shared argv runner, same
  output-joining and OSError re-raise as before) and made `_run_ruff` try
  the MODULE form first (`[sys.executable, "-m", "ruff", ...]`), falling
  back to the bare executable only when the module form proves absent.
  `python -m ruff` with the module genuinely missing does NOT raise -- it
  exits non-zero and prints "No module named ruff" to stderr, which is
  indistinguishable from a real E722 violation's exit code alone, so the
  fallback decision is made on that literal stderr substring
  (`_RUFF_MODULE_MISSING_MARKER`), never on exit code. When the fallback
  bare executable is also absent, `subprocess.run` raises
  FileNotFoundError and `_run_ruff` lets it propagate unchanged --
  `main()`'s existing branch still turns that into the install instruction
  on stderr (GE-108d's routing, left untouched). RUFF_SELECT, every exit
  code, every message string, and every skip condition are unchanged; no
  leafcutter-internal import was added.
====================================================================
"""
