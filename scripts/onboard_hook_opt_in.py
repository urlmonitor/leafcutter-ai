"""
MODULE: onboard_hook_opt_in
GOAL: Offer interactive opt-in for optional pre-commit hooks (jscpd duplicate-code
    detection and diff-cover coverage gating) during the onboarding wizard flow.
BUSINESS CONTEXT: Both hooks ship disabled by default because they depend on
    external binaries (jscpd, diff-cover) that many adopters may not have installed.
    The wizard detects each binary and, when found, offers a yes/no prompt so the
    user can activate the hook without editing commit_guardian.json by hand.
ARCHITECTURE: Standalone stdlib-only module; no Claude Code imports, no external
    deps. Binary detection uses shutil.which(). Configuration mutation reads and
    writes JSON atomically via a temp-file-then-rename pattern. Consumed by both
    bootstrap_install.py (terminal fallback) and the onboard.md LLM agent template
    (which loads this module for script-based interactions). Returns a structured
    result dict so callers can incorporate unenabled tools into their own checklist.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JSCPD_BINARY = "jscpd"
DIFF_COVER_BINARY = "diff-cover"

_JSCPD_CHECKLIST_LABEL = "jscpd (duplicate code detection)"
_DIFF_COVER_CHECKLIST_LABEL = "diff-cover (test coverage gating)"


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def _detect_binary(name: str) -> str | None:
    """Return the path to a binary if it is on PATH, or None if absent.

    Args:
        name: The binary name to search for (e.g. ``"jscpd"``).

    Returns:
        str | None: Absolute path to the binary, or None when not found.
    """
    return shutil.which(name)


# ---------------------------------------------------------------------------
# Commit Guardian JSON read / write
# ---------------------------------------------------------------------------

def _load_commit_guardian(config_path: Path) -> dict[str, Any]:
    """Read commit_guardian.json from *config_path* and return the parsed dict.

    Args:
        config_path: Absolute path to commit_guardian.json.

    Returns:
        dict[str, Any]: The parsed configuration dictionary.

    Raises:
        FileNotFoundError: When the config file does not exist.
        OSError: When the file cannot be read.
        json.JSONDecodeError: When the file contains invalid JSON.
    """
    try:
        with open(config_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        raise


def _save_commit_guardian(config_path: Path, data: dict[str, Any]) -> None:
    """Write *data* to *config_path* atomically via a temp-file-then-rename.

    The indentation style (4 spaces) and trailing newline match the existing
    commit_guardian.json format.

    Args:
        config_path: Absolute path to commit_guardian.json.
        data: The configuration dictionary to serialise.

    Raises:
        OSError: When the temp file cannot be written or the rename fails.
    """
    serialised = json.dumps(data, indent=4, ensure_ascii=False) + "\n"
    parent = config_path.parent

    # Write to a temp file first; let OSError propagate to caller on failure.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=parent,
        prefix=".cg_tmp_",
        suffix=".json",
        delete=False,
    ) as tmp:
        tmp.write(serialised)
        tmp_path = Path(tmp.name)

    # Atomic rename; clean up the temp file on failure then re-raise.
    try:
        os.replace(tmp_path, config_path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise


def _set_section_enabled(
    data: dict[str, Any],
    section: str,
    enabled: bool,
) -> dict[str, Any]:
    """Return *data* with ``data[section]["enabled"]`` set to *enabled*.

    The section dict is created with minimal defaults when absent.

    Args:
        data: The commit_guardian config dict (not mutated).
        section: Top-level key in the config (e.g. ``"duplicate_code"``).
        enabled: The value to write to ``data[section]["enabled"]``.

    Returns:
        dict[str, Any]: A shallow copy of *data* with the section updated.
    """
    updated = dict(data)
    section_data = dict(updated.get(section, {}))
    section_data["enabled"] = enabled
    updated[section] = section_data
    return updated


# ---------------------------------------------------------------------------
# Interactive prompt helpers
# ---------------------------------------------------------------------------

def _ask_yes_no(prompt: str) -> bool:
    """Ask a yes/no question on stderr and return True when the user answers yes.

    Falls back to False (no) when stdin is not a TTY (non-interactive
    environments such as CI), so the hook is never silently enabled in
    automated pipelines.

    Args:
        prompt: The question text (without trailing space or newline).

    Returns:
        bool: True when the user answers ``y``/``yes``, False otherwise.
    """
    if not sys.stdin.isatty():
        return False

    while True:
        try:
            resp = input(f"{prompt} (y/n) [n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return False

        if not resp:
            resp = "n"

        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False

        print("Please answer 'y' or 'n'.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def run_hook_opt_in(
    config_path: Path,
    *,
    interactive: bool = True,
) -> dict[str, Any]:
    """Run the opt-in wizard for jscpd and diff-cover hooks.

    For each tool, this function:
    - Detects the binary on PATH.
    - When detected AND *interactive* is True: prompts the user yes/no.
    - When the user accepts: sets ``<section>.enabled = true`` in
      *config_path* (commit_guardian.json).
    - When the binary is absent: silently skips the prompt and records the
      tool in the returned ``optional_tools_checklist`` list.

    Args:
        config_path: Absolute path to the project's commit_guardian.json.
        interactive: Set to False to suppress all prompts (for dry-run or
                     non-interactive callers). When False, no hooks are
                     enabled — the function returns only detection results.

    Returns:
        dict[str, Any]: A structured result with the following keys:
        - ``jscpd_detected`` (bool) — True when the jscpd binary was found.
        - ``jscpd_enabled`` (bool) — True when the user opted in.
        - ``diff_cover_detected`` (bool) — True when diff-cover was found.
        - ``diff_cover_enabled`` (bool) — True when the user opted in.
        - ``optional_tools_checklist`` (list[str]) — Labels of tools the
          user should install later (binary not found on PATH).
        - ``config_path`` (str) — Absolute path of the config that was
          (potentially) updated.
    """
    result: dict[str, Any] = {
        "jscpd_detected": False,
        "jscpd_enabled": False,
        "diff_cover_detected": False,
        "diff_cover_enabled": False,
        "optional_tools_checklist": [],
        "config_path": str(config_path),
    }

    try:
        config_data = _load_commit_guardian(config_path)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(
            f"[onboard-hook-opt-in] Warning: could not load commit_guardian.json: {exc}\n"
            "  Hook opt-in step skipped.",
            file=sys.stderr,
        )
        return result

    config_dirty = False

    # ------------------------------------------------------------------
    # jscpd — duplicate code detection
    # ------------------------------------------------------------------
    jscpd_path = _detect_binary(JSCPD_BINARY)
    result["jscpd_detected"] = jscpd_path is not None

    if jscpd_path is not None:
        print(
            "\n--- Duplicate Code Detection (jscpd) ---",
            file=sys.stderr,
        )
        print(
            "jscpd is installed on your PATH. "
            "The check-duplicate-code hook ships disabled by default.",
            file=sys.stderr,
        )
        if interactive and _ask_yes_no(
            "Enable the duplicate code check (check-duplicate-code hook)?"
        ):
            config_data = _set_section_enabled(config_data, "duplicate_code", True)
            config_dirty = True
            result["jscpd_enabled"] = True
            print(
                "  → duplicate_code.enabled set to true in commit_guardian.json",
                file=sys.stderr,
            )
        else:
            print(
                "  duplicate_code hook left disabled.",
                file=sys.stderr,
            )
    else:
        # Binary not found — silently add to checklist
        result["optional_tools_checklist"].append(_JSCPD_CHECKLIST_LABEL)

    # ------------------------------------------------------------------
    # diff-cover — test coverage gating
    # ------------------------------------------------------------------
    diff_cover_path = _detect_binary(DIFF_COVER_BINARY)
    result["diff_cover_detected"] = diff_cover_path is not None

    if diff_cover_path is not None:
        print(
            "\n--- Diff Coverage Gating (diff-cover) ---",
            file=sys.stderr,
        )
        print(
            "diff-cover is installed on your PATH. "
            "The check-diff-coverage hook ships disabled by default.",
            file=sys.stderr,
        )
        if interactive and _ask_yes_no(
            "Enable the diff coverage check (check-diff-coverage hook)?"
        ):
            config_data = _set_section_enabled(config_data, "diff_coverage", True)
            config_dirty = True
            result["diff_cover_enabled"] = True
            print(
                "  → diff_coverage.enabled set to true in commit_guardian.json",
                file=sys.stderr,
            )
        else:
            print(
                "  diff_coverage hook left disabled.",
                file=sys.stderr,
            )
    else:
        # Binary not found — silently add to checklist
        result["optional_tools_checklist"].append(_DIFF_COVER_CHECKLIST_LABEL)

    # ------------------------------------------------------------------
    # Persist changes if any
    # ------------------------------------------------------------------
    if config_dirty:
        try:
            _save_commit_guardian(config_path, config_data)
        except OSError as exc:
            print(
                f"[onboard-hook-opt-in] Warning: could not save commit_guardian.json: {exc}\n"
                "  Your opt-in choices were NOT persisted.",
                file=sys.stderr,
            )

    return result


# ---------------------------------------------------------------------------
# CLI entry point (for manual testing or direct invocation)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Run the hook opt-in wizard from the command line.

    Usage::

        python scripts/onboard_hook_opt_in.py [--config-path PATH] [--dry-run]

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        int: Exit code (0 on success, 1 on argument error).
    """
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Interactive opt-in wizard for jscpd and diff-cover pre-commit hooks. "
            "Detects binaries on PATH and updates commit_guardian.json on user approval."
        )
    )
    parser.add_argument(
        "--config-path",
        metavar="FILE",
        default=None,
        help=(
            "Path to commit_guardian.json. Defaults to "
            "scripts/commit_guardian/commit_guardian.json relative to cwd."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect binaries and report results without prompting or writing any files.",
    )
    args = parser.parse_args(argv)

    if args.config_path:
        config_path = Path(args.config_path).resolve()
    else:
        config_path = (
            Path.cwd() / "scripts" / "commit_guardian" / "commit_guardian.json"
        )

    result = run_hook_opt_in(
        config_path,
        interactive=not args.dry_run,
    )

    # Print checklist items
    if result["optional_tools_checklist"]:
        print("\n--- Optional Tools (not installed) ---", file=sys.stderr)
        print(
            "The following tools were not found on your PATH.\n"
            "Install them later and re-run /onboard to enable their hooks:",
            file=sys.stderr,
        )
        for label in result["optional_tools_checklist"]:
            print(f"  - {label}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-06-18 [python-coder/TICKET-20260616-GE-100g]: Created module. Implements
#   AC GE-100g: onboarding wizard offers opt-in enablement for jscpd and diff-cover
#   hooks. Binary detection uses shutil.which(). Config mutation reads and writes
#   commit_guardian.json atomically (temp-file-then-rename). When a binary is absent,
#   the tool label is added to the returned optional_tools_checklist instead of
#   prompting. Non-interactive mode (dry-run or non-TTY stdin) skips all prompts and
#   makes no config changes. Entry point: run_hook_opt_in(config_path).
# ===========================================================================
