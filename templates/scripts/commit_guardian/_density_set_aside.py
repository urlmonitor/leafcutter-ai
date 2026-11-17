"""
Declared set-aside locations for the folder-density check (GE-133a).

A location listed in ``folder_density.set_aside_locations`` of
commit_guardian.json is not judged against the crowding limit, and is reported
as set aside together with its stated ground.

MODULE: _density_set_aside.py
GOAL: Resolve which folders the configuration sets aside from the density limit.
BUSINESS CONTEXT: A store of records only tools read (the AC store) is flat by
    design; judging it with a limit written for folders people browse blocks
    commits for a crowding nobody experiences.
ARCHITECTURE: Not needed.
"""

from __future__ import annotations

from typing import Any

from config import load_config

KEY = "set_aside_locations"
CONFIG_NAME = "commit_guardian.json"


def load_set_aside() -> tuple[list[tuple[str, str]], list[str]]:
    """Read the declared set-aside locations.

    Returns:
        (entries, problems): entries are (repo-relative path, ground) pairs;
        problems are human-readable lines saying what could not be read or
        interpreted. A declaration that cannot be used sets nothing aside.
    """
    section = load_config().get("folder_density", {})
    if KEY not in section:
        return [], [f"{KEY} could not be read from {CONFIG_NAME} (key not found); nothing is set aside"]
    raw: Any = section[KEY]
    if not isinstance(raw, list):
        return [], [f"{KEY} in {CONFIG_NAME} could not be interpreted (not a list): {raw!r}; nothing is set aside"]
    entries: list[tuple[str, str]] = []
    problems: list[str] = []
    for item in raw:
        path = item.get("path") if isinstance(item, dict) else None
        ground = item.get("ground") if isinstance(item, dict) else None
        if isinstance(path, str) and path.strip("/") and isinstance(ground, str) and ground.strip():
            entries.append((path.strip().strip("/"), ground.strip()))
        else:
            problems.append(f"{KEY} entry in {CONFIG_NAME} could not be interpreted (needs path and ground): {item!r}")
    return entries, problems


def ground_for(folder: str, entries: list[tuple[str, str]]) -> str | None:
    """Return the ground of the declared location containing *folder*, else None.

    Matching is exact on whole path components (backslash separators are read as "/"): ``docs/a`` contains
    ``docs/a/b`` but not ``docs/a-archive``.
    """
    folder = folder.replace("\\", "/")
    for path, ground in entries:
        if folder == path or folder.startswith(path + "/"):
            return ground
    return None


def report(set_aside: dict[str, str], judged_count: int, problems: list[str]) -> None:
    """Print unreadable-declaration problems, the set-aside folders and the two counts."""
    for problem in problems:
        print(f"⚠️  {problem}")
    for folder in sorted(set_aside):
        print(f"   - {folder}/ set aside: {set_aside[folder]}")
    print(f"   {judged_count} folders judged, {len(set_aside)} folders set aside\n")
