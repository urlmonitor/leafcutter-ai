"""
MODULE: _config
GOAL: Locate and read a project's ``skills_config.json`` for the shipped
    test-database checker/resolver (``checker.py``), surfacing any I/O or
    parse failure as one domain exception rather than a raw traceback.
BUSINESS CONTEXT: INF-1100d-3-i / INF-1100d-3-ii's checker and resolver both
    need to read the SAME on-disk config file the same way -- this module is
    the one place that walks the platform-directory auto-detect order and
    turns "file missing / unreadable / not UTF-8 / not JSON" into a single,
    caller-friendly exception, so ``checker.py`` never has to special-case
    three different stdlib exception types itself.
ARCHITECTURE: Split out of ``checker.py`` (pr-reviewer/GE-127a-1
    file-size-ratchet follow-up: checker.py exceeded the 400-line
    check-file-size limit) alongside its sibling ``_address.py``. Two
    private functions -- ``_find_project_config()`` (pure filesystem lookup)
    and ``_read_project_testing_context()`` (the I/O boundary: file read +
    JSON parse) -- plus the ``DbConnectionTestConfigError`` exception class
    they raise. ``checker.py`` imports both functions and the exception via
    a ``sys.path`` push to its own directory (see ``checker.py``'s module
    docstring for why: it must resolve identically whether ``checker.py``
    runs as a standalone CLI script or is imported as ``db_check.checker``).
    Deployed as part of the whole ``scripts/db_check/`` directory (already
    declared in ``AGENT_SUPPORT_SCRIPT_DIRS``, ``build_phases_script_deploy.
    py`` -- no new deploy-manifest entry needed; the existing directory
    entry sweeps every ``.py`` file under it, this one included).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Same platform-directory auto-detection order and "first match wins"
# semantics as config_loader.load_config()'s project-config auto-detect
# branch, kept in sync deliberately (see checker.py's own module docstring
# for why this module does not import config_loader.py directly).
_PLATFORM_CONFIG_DIRS: tuple[str, ...] = (".claude", ".gemini", ".cursor", ".github", ".cline")


class DbConnectionTestConfigError(RuntimeError):
    """Raised by ``resolve_test_db_address()`` (in ``checker.py``) when the
    project's ``skills_config.json`` exists but cannot be read or parsed as
    JSON."""


def _find_project_config(target_root: Path) -> Path | None:
    """Return the first existing ``skills_config.json`` under *target_root*.

    Pure filesystem lookup (existence checks only, no content read); walks
    ``_PLATFORM_CONFIG_DIRS`` in order, mirroring
    ``config_loader.load_config()``'s own auto-detect precedence.

    Args:
        target_root: Absolute path to the project root to search.

    Returns:
        The first matching ``Path``, or ``None`` when no platform directory
        has a ``skills_config.json``.
    """
    for platform_dir in _PLATFORM_CONFIG_DIRS:
        candidate = target_root / platform_dir / "skills_config.json"
        if candidate.is_file():
            return candidate
    return None


def _read_project_testing_context(config_path: Path) -> dict[str, Any]:
    """Read and return the ``testing_context`` object from *config_path*.

    This is the module's I/O boundary for config reads: file I/O and JSON
    parsing both happen here, and both of their expected failure modes are
    handled here rather than left to propagate from a pure helper.

    Args:
        config_path: Path to an existing ``skills_config.json``.

    Returns:
        The ``testing_context`` dict, or ``{}`` when the key is absent or
        not a dict.

    Raises:
        DbConnectionTestConfigError: When *config_path* cannot be read
            (``OSError``), is not valid UTF-8 (``UnicodeDecodeError`` --
            H-5), or does not parse as JSON (``json.JSONDecodeError``) --
            surfaced to the caller rather than silently treated as "not
            configured", so a malformed project config is not misreported
            as a missing setting.
    """
    try:
        text = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DbConnectionTestConfigError(  # noqa: TRY003
            f"could not read {config_path}: {exc}"
        ) from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DbConnectionTestConfigError(  # noqa: TRY003
            f"{config_path} is not valid JSON: {exc}"
        ) from exc

    testing_context = data.get("testing_context") if isinstance(data, dict) else None
    return testing_context if isinstance(testing_context, dict) else {}


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-25 [python-coder/GE-127a-1-split]: Extracted from checker.py
#   verbatim (_PLATFORM_CONFIG_DIRS, DbConnectionTestConfigError,
#   _find_project_config, _read_project_testing_context -- including the
#   H-5 UnicodeDecodeError handling already fixed there) to bring
#   checker.py back under the 400-line check-file-size limit
#   (GE-127a-1/pr-reviewer). No behaviour change: checker.py re-imports
#   these three names via a sys.path push to its own directory (see
#   checker.py's module docstring) so `resolve_test_db_address()` calls
#   them exactly as before the split. (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
# ===========================================================================
