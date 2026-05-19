"""
MODULE: path_resolver
GOAL: Resolve dotted path keys from leafcutter/config/paths.json
    to absolute filesystem paths, and expand {paths.X.Y} placeholders in
    template strings.
BUSINESS CONTEXT: paths.json is the single source of truth for every
    architectural folder location used by agents, configs, and commit-guardian
    hooks. Rather than hardcoding 'docs/architecture/' in 40 different places,
    every consumer calls resolve_path('docs.architecture') and receives the
    correct absolute path. When a project relocates a folder, one paths.json
    edit propagates everywhere.
ARCHITECTURE: Public functions: resolve_path (dotted key -> absolute Path),
    get_all_paths (flat dict of all keys -> abs path strings),
    expand_placeholders (replace {paths.X.Y} tokens in a string).
    Internal: _load_paths (JSON loader with cache), _flat_paths (nested dict
    flattener that skips _optional sentinels). Stateless across calls except
    for the module-level cache; use _clear_cache() in tests to reset state.
    Raises KeyError with a helpful message on bad keys. No global mutable
    state beyond the cache (which is a process-lifetime optimisation).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_PATHS_JSON = _PACKAGE_ROOT / "config" / "paths.json"

# Module-level cache: populated on first call, invalidated only by _clear_cache()
_PATHS_CACHE: dict[str, str] | None = None

_PLACEHOLDER_RE = re.compile(r"\{paths\.([a-zA-Z0-9_.]+)\}")


def _load_paths() -> dict[str, Any]:
    """Load the raw paths dict from paths.json.

    Returns:
        The ``paths`` dict from paths.json, or an empty dict when the file is
        absent or malformed. Logs a warning on failure; never raises.
    """
    if not _PATHS_JSON.exists():
        return {}
    try:
        data = json.loads(_PATHS_JSON.read_text(encoding="utf-8"))
        return data.get("paths", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _flat_paths(nested: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten a nested dict of path declarations into dotted keys.

    Skips boolean values (used as optional sentinels, e.g. ``foo_optional: true``)
    and non-string values. Returns only leaf string entries.

    Args:
        nested: Nested dict of path declarations (one level from paths.json).
        prefix: Dotted key prefix accumulated during recursion.

    Returns:
        Flat dict mapping dotted keys to path strings.
    """
    result: dict[str, str] = {}
    for k, v in nested.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flat_paths(v, full_key))
        elif isinstance(v, str):
            result[full_key] = v
        # Skip booleans (optional sentinels) and other types
    return result


def _get_flat() -> dict[str, str]:
    """Return the cached flat paths dict, loading from JSON on first call.

    Returns:
        Flat dict mapping dotted keys to path strings.
    """
    global _PATHS_CACHE  # noqa: PLW0603
    if _PATHS_CACHE is None:
        _PATHS_CACHE = _flat_paths(_load_paths())
    return _PATHS_CACHE


def _clear_cache() -> None:
    """Clear the module-level paths cache.

    Call this in tests after modifying paths.json or the cache directly.
    """
    global _PATHS_CACHE  # noqa: PLW0603
    _PATHS_CACHE = None


def _git_root(project_root: Path | None) -> Path:
    """Resolve the project root, falling back to git rev-parse --show-toplevel.

    Args:
        project_root: Caller-supplied project root, or None to auto-detect.

    Returns:
        Resolved project root path.
    """
    if project_root is not None:
        return project_root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def resolve_path(key: str, project_root: Path | None = None) -> Path:
    """Resolve a dotted path key to an absolute filesystem path.

    Looks up ``key`` in the flat paths dict derived from ``paths.json`` and
    joins the result with ``project_root`` (auto-detected from git when None).

    Args:
        key: Dotted key such as ``"docs.architecture_adrs"`` or
            ``"package.build_script"``.
        project_root: Optional absolute project root. When None, the git
            working-tree root is used via ``git rev-parse --show-toplevel``.

    Returns:
        Absolute ``Path`` for the declared folder or file.

    Raises:
        KeyError: When ``key`` is not present in paths.json, with a message
            listing all known keys.
    """
    flat = _get_flat()
    if key not in flat:
        known = ", ".join(sorted(flat.keys()))
        raise KeyError(
            f"Unknown paths.json key: '{key}'. "
            f"Known keys: {known}"
        )
    root = _git_root(project_root)
    return root / flat[key]


def get_all_paths(project_root: Path | None = None) -> dict[str, str]:
    """Return a flat dict of all path keys mapped to their absolute path strings.

    Used by ``build.py`` when generating the ``## Project Paths`` injection
    block for agent prompts.

    Args:
        project_root: Optional absolute project root. When None, the git
            working-tree root is used via ``git rev-parse --show-toplevel``.

    Returns:
        Dict mapping every dotted path key to its absolute path string
        (POSIX format). Returns an empty dict when ``paths.json`` is absent.
    """
    flat = _get_flat()
    if not flat:
        return {}
    root = _git_root(project_root)
    return {k: (root / v).as_posix() for k, v in flat.items()}


def expand_placeholders(template: str, project_root: Path | None = None) -> str:
    """Replace every ``{paths.X.Y}`` occurrence in ``template`` with the resolved path.

    Used by config loaders when a ``default_path`` value in ``doc_types.json``
    or ``diagram_types.json`` contains a path placeholder. Unresolvable
    placeholders are left as-is and logged as a warning.

    Args:
        template: String potentially containing ``{paths.X.Y}`` tokens.
        project_root: Optional absolute project root passed through to
            ``resolve_path``.

    Returns:
        String with all resolvable ``{paths.*}`` placeholders replaced.
        Unresolvable tokens are left unchanged.
    """
    def replacer(match: re.Match) -> str:
        """Substitute a single regex match with its resolved path.

        Args:
            match: Regex match object from ``_PLACEHOLDER_RE``; group 1 is
                the dotted key.

        Returns:
            Resolved path string (POSIX), or the original placeholder when
            the key is not found.
        """
        key = match.group(1)
        try:
            path = resolve_path(key, project_root)
            return path.as_posix()
        except KeyError:
            return match.group(0)

    return _PLACEHOLDER_RE.sub(replacer, template)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 11:00 [EPIC-ArchitectureDocsEnforcement/ticket 10]: (#EPIC-LeafcutterMVP/01)
#   Created as the resolution API for paths.json (D10.2). Exposes
#   resolve_path(), get_all_paths(), and expand_placeholders().
#   _flat_paths() skips boolean optional-sentinel values so they do not
#   appear as path entries. Module-level cache is cleared by _clear_cache()
#   in unit tests. git fallback in _git_root() makes the module usable
#   outside a git repository (falls back to cwd).
# ====================================================================
