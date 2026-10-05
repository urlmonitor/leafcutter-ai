"""Shared neutral records and safe data readers for native artifact metadata.

BUSINESS CONTEXT: KM-400a-3-i exposes authored fields without schema defaulting.
ARCHITECTURE: Type readers return records; graph identity and publication stay outside.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

import yaml


@dataclass(frozen=True)
class NativeRecord:
    """One authored record with a source-relative path and exact metadata values."""

    kind: str
    native_id: str
    source_path: str
    metadata: dict[str, Any]
    locator: str = ""
    title: str = ""
    description: str = ""
    derived: dict[str, Any] = field(default_factory=dict)


def read_text(path: Path) -> str:
    """Read source text with explicit failures and support UTF-8 BOM files."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read native source {path}") from error


def read_json(path: Path) -> Any:
    """Parse JSON source data without executing its contents."""
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid native JSON {path}") from error


def read_yaml(path: Path) -> Any:
    """Parse safe YAML while retaining authored date and scalar types."""
    try:
        return yaml.safe_load(read_text(path))
    except yaml.YAMLError as error:
        raise ValueError(f"invalid native YAML {path}") from error


def frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Return Markdown frontmatter plus body; missing frontmatter is an empty map."""
    text = read_text(path)
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError(f"unclosed native frontmatter {path}")
    try:
        value = yaml.safe_load("".join(lines[1:end]))
    except yaml.YAMLError as error:
        raise ValueError(f"invalid native frontmatter {path}") from error
    if value is not None and not isinstance(value, dict):
        raise ValueError(f"native frontmatter must be an object: {path}")
    return value or {}, "".join(lines[end + 1 :])


def relative(root: Path, path: Path) -> str:
    """Return the source path, refusing resolved paths outside the supplied snapshot."""
    return path.resolve().relative_to(root.resolve()).as_posix()
