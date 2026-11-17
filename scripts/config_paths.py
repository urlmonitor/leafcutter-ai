"""
MODULE: config_paths
GOAL: Give every build step ONE shared reading of a file-location setting in
    skills_config.json: off (empty), the shipped default (key absent), usable
    (names a real file) or broken (names a missing file or a folder).
BUSINESS CONTEXT: BP-1500h-1 / -1-i / -1-ii (user decisions 2, 8, 11). An empty
    ``changelog_categories_path`` used to be joined to the project root and read
    as a file ("could not read <project> ... Is a directory") by one step while
    another skipped it silently. Now an empty value means "this feature is not
    configured" for every step, a missing key means the shipped default
    location, and a path that is not a file is a loudly reported broken
    setting that is skipped without ever falling back to the default.
ARCHITECTURE: ``resolve_file_setting`` is pure (no printing). ``report_setting``
    is the single reporting point: an empty value is announced once per key per
    build at info level, a broken one is warned once per key per build; both are
    de-duplicated by process-local state that ``begin_build`` resets.
    ``setting_file`` is what readers call: the path to read or install at, or
    None when the feature is off or broken. Shipped defaults are read from
    config/skills_config.default.json, never passed in as literals. The set of
    file-location keys (FILE_KEYS) is declared once here; folder keys are not
    judged by is_file().
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from build_colors import info as _info
from build_colors import warn as _warn

DEFAULTS_PATH = Path(__file__).resolve().parent.parent / "config" / "skills_config.default.json"

# Keys whose value names a FILE (dotted = nested under a parent object).
FILE_KEYS: tuple[str, ...] = (
    "changelog_categories_path",
    "precommit_autofix_config_path",
    "reachability_exemptions_path",
    "testing_context.readme_path",
)

_announced: set[str] = set()
_build_target_root: Path | None = None


def begin_build(target_root: Path) -> None:
    """Start a build: forget what was announced and remember the project root.

    Args:
        target_root: Absolute path to the project the build installs into.
    """
    global _build_target_root  # noqa: PLW0603
    _announced.clear()
    _build_target_root = target_root


def build_target_root() -> Path | None:
    """Return the project root registered by ``begin_build`` (None outside a build)."""
    return _build_target_root


def is_file_key(key: str) -> bool:
    """True when *key* is a declared file-location setting."""
    return key in FILE_KEYS


def was_reported(key: str) -> bool:
    """True when *key* has already been announced or warned about this build."""
    return key in _announced


@lru_cache(maxsize=1)
def _defaults() -> dict[str, Any]:
    """Read the shipped defaults once (config/skills_config.default.json)."""
    return json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))


def setting_value(data: dict[str, Any], key: str) -> Any:
    """Look *key* (dotted for nested settings) up in *data*; None when absent."""
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def effective_setting(config: dict[str, Any], key: str) -> tuple[str | None, str | None]:
    """Return ``(value, source)``: the value in force and where it came from.

    A merged config that holds exactly the shipped default for *key* counts as
    ``default`` (the loader merges defaults under the project's settings, so an
    absent key arrives already holding it). A non-string value counts as absent.
    """
    default = setting_value(_defaults(), key)
    default = default if isinstance(default, str) else None
    value = setting_value(config, key)
    if not isinstance(value, str):
        return default, ("default" if default is not None else None)
    return value, ("default" if value == default else "configured")


def resolve_file_setting(
    config: dict[str, Any], key: str, target_root: Path | None
) -> dict[str, Any]:
    """Interpret a file-location setting.

    Args:
        config: The (merged or raw) skills config.
        key: Setting name; dotted for nested keys (``testing_context.readme_path``).
        target_root: Project root the value is relative to. None skips the
            on-disk check (a non-empty value is then reported usable).

    Returns:
        ``{'state': 'off' | 'usable' | 'broken', 'source': 'configured' |
        'default' | None, 'path': Path | None, 'reason': None | 'missing' |
        'is_directory'}``. ``off`` means the value is empty/blank (or the key
        has neither a value nor a shipped default); ``path`` is None then.
    """
    value, source = effective_setting(config, key)
    if value is None or not value.strip():
        return {"state": "off", "source": source, "path": None, "reason": None}
    if target_root is None:
        return {"state": "usable", "source": source, "path": Path(value), "reason": None}
    path = Path(target_root) / value
    if path.is_dir():
        return {"state": "broken", "source": source, "path": path, "reason": "is_directory"}
    if path.is_file():
        return {"state": "usable", "source": source, "path": path, "reason": None}
    return {"state": "broken", "source": source, "path": path, "reason": "missing"}


def installable(result: dict[str, Any]) -> bool:
    """True when the shipped default location simply has no file yet (to be scaffolded)."""
    return (
        result["state"] == "broken"
        and result["reason"] == "missing"
        and result["source"] == "default"
    )


def report_setting(config: dict[str, Any], key: str, result: dict[str, Any]) -> None:
    """The single reporting point: say once per key per build what is wrong.

    An empty value is announced at info level ("not configured"). A broken
    setting is warned about, naming the key, the value and the reason. A
    missing file at the shipped default location is NOT broken: the scaffold
    step installs it, so nothing is said.
    """
    if key in _announced:
        return
    value, _ = effective_setting(config, key)
    if result["state"] == "off" and result["source"] == "configured":
        _announced.add(key)
        _info(f"{key} is not configured (empty value): this feature is off for this build")
    elif result["state"] == "broken" and not installable(result):
        _announced.add(key)
        why = (
            f"{value!r} is a folder, not a file"
            if result["reason"] == "is_directory"
            else f"file not found at {value!r}"
        )
        _warn(f"setting {key} is broken: {why}; skipped (no fallback to the default)")


def resolve_and_report(config: dict[str, Any], key: str, target_root: Path | None) -> dict[str, Any]:
    """Resolve *key* and run it through ``report_setting``; return the result."""
    result = resolve_file_setting(config, key, target_root)
    report_setting(config, key, result)
    return result


def setting_file(config: dict[str, Any], key: str, target_root: Path) -> Path | None:
    """Path a reader should read or install at for *key*, or None to skip it.

    Usable files and a not-yet-installed shipped default give a path; an empty
    or broken setting gives None (and is reported once).
    """
    result = resolve_and_report(config, key, target_root)
    if result["state"] == "usable" or installable(result):
        return result["path"]
    return None


def scaffold_target(source: Path, config: dict[str, Any], key: str, target_root: Path) -> Path | None:
    """setting_file for a scaffold built from *source*; None when *source* is not a file."""
    path = setting_file(config, key, target_root)
    return path if source.is_file() else None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-14 12:00 [python-coder]: Created the shared file-location setting
#   helper (user decisions 2, 8, 11). A missing file at the SHIPPED DEFAULT is
#   not reported as broken: the scaffold step installs it, and agents compile
#   before scaffolds run on a fresh build. (#BP-1500h/1)
# ====================================================================
