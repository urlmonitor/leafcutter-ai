"""
MODULE: scripts/commit_guardian/_ac_schema_loader.py
GOAL: Load config/ac_store_schema.json for check_ac_schema.py (moved verbatim, ACD-200b-2).
BUSINESS CONTEXT: The AC validator needs the one JSON schema, including its
    documentation_triggers enum, to validate records at commit time.
ARCHITECTURE: Sibling of check_ac_schema.py, which imports ``SCHEMA_PATH`` and
    ``_load_schema`` back. Stdlib only; deploys with the directory.

DECISION HISTORY:
  - 2026-10-21 [python-coder/ACD-200b-2]: Created by moving _load_schema and
    SCHEMA_PATH verbatim out of check_ac_schema.py to repay its size ratchet.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_PATH = "config/ac_store_schema.json"


def _load_schema(root: Path) -> dict[str, Any] | None:
    """Load config/ac_store_schema.json; None if absent.

    Args:
        root: Repository root directory.

    Returns:
        Parsed schema dict, or None.
    """
    schema_path = root / SCHEMA_PATH
    if not schema_path.is_file():
        return None
    try:
        with open(schema_path, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[return-value]
    except OSError as exc:
        print(f"Warning: cannot read schema {schema_path}: {exc}", file=sys.stderr)
        return None


def _find_project_root() -> Path | None:
    """Find the project root by .git or CLAUDE.md presence.

    Returns:
        Absolute Path of the project root, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        return Path(env_root)

    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor

    return None
