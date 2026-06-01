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
- Exit 2 with text on stdout         = block the next step and show the text
  (Claude Code treats any non-zero exit from a PostToolUse hook as a blocking
  feedback message injected into the active turn; exit 2 is the conventional
  "block with content" exit code used by Claude Code hooks.)

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


def _run_ruff(path: str) -> tuple[int, str]:
    """Run ruff check on *path* and return ``(returncode, combined_output)``.

    Raises:
        FileNotFoundError: When ruff is not found on PATH.

    Args:
        path: Absolute or relative path to the Python file to check.

    Returns:
        A ``(returncode, output)`` tuple where ``output`` is ruff's combined
        stdout (violations) and stderr (diagnostic messages) joined with a
        newline. Return code is 0 when no violations are found, 1 when
        violations exist.
    """
    result = subprocess.run(
        [
            "ruff",
            "check",
            "--select",
            RUFF_SELECT,
            "--output-format",
            "concise",
            path,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output_parts = []
    if result.stdout.strip():
        output_parts.append(result.stdout.strip())
    if result.stderr.strip():
        output_parts.append(result.stderr.strip())
    return result.returncode, "\n".join(output_parts)


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
    except Exception:
        # Malformed payload — silently allow, do not block Claude
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
    except Exception:
        sys.exit(0)
    if not resolved.exists():
        # File not on disk yet (dry-run or cancelled write) — silently allow
        sys.exit(0)

    # 5. Run ruff.
    try:
        returncode, ruff_output = _run_ruff(str(resolved))
    except FileNotFoundError:
        # ruff is not installed — inject the install instruction and block
        print(_build_ruff_not_found_message(file_path))
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
    print(_build_block_message(file_path, ruff_output))
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
====================================================================
"""
