"""
MODULE: config_loader
GOAL: Load and validate the skills_config.json that drives leafcutter
    template compilation, merging package defaults with project overrides.
BUSINESS CONTEXT: Each adopter project supplies a single skills_config.json that
    controls every placeholder injected into generated agent/skill files. This
    module isolates config I/O and schema validation so build.py stays focused
    on orchestration.
ARCHITECTURE: Two public functions: ``load_config`` (merge defaults +
    project config), ``validate_config`` (JSON-Schema Draft-7 check via the
    optional jsonschema library). No side effects outside return values.
    Runnable module: not directly runnable (library only).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PACKAGE_ROOT / "config"
SCHEMA_PATH = CONFIG_DIR / "skills_config.schema.json"
DEFAULTS_PATH = CONFIG_DIR / "skills_config.default.json"


def load_config(config_path: Path | None, target_root: Path) -> dict[str, Any]:
    """Load and merge config: defaults first, then project config on top.

    Args:
        config_path: Explicit path to a skills_config.json file, or None to
            auto-detect from ``<target_root>/.claude/skills_config.json``.
        target_root: Absolute path to the target project root, used for
            auto-detection of the project config.

    Returns:
        Merged dictionary of config values with project config overriding
        package defaults.
    """
    # Load defaults
    defaults: dict[str, Any] = {}
    if DEFAULTS_PATH.exists():
        with DEFAULTS_PATH.open("r", encoding="utf-8") as f:
            defaults = json.load(f)
    defaults.pop("_comment", None)

    # Load project config (optional)
    project_config: dict[str, Any] = {}
    if config_path is not None and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            project_config = json.load(f)
        project_config.pop("_comment", None)
    elif config_path is None:
        # Auto-detect in target root
        candidate = target_root / ".claude" / "skills_config.json"
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as f:
                project_config = json.load(f)
            project_config.pop("_comment", None)

    merged = {**defaults, **project_config}
    return merged


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate config against the package JSON schema.

    Args:
        config: Dictionary of config values to validate against the package
            JSON schema at ``config/skills_config.schema.json``.

    Returns:
        List of error message strings. Empty list means the config is valid.
        Returns a single warning string if ``jsonschema`` is not installed or
        the schema file is not found.
    """
    if not _JSONSCHEMA_AVAILABLE:
        return ["jsonschema not installed — skipping schema validation (pip install jsonschema)"]
    if not SCHEMA_PATH.exists():
        return [f"Schema not found at {SCHEMA_PATH}"]
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft7Validator(schema)
    errors = [e.message for e in validator.iter_errors(config)]
    return errors


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 12:05 [epic-supervisor/ticket-13]: Extracted from build.py (#EPIC-LeafcutterMVP/01)
#   during file-size refactor (build.py exceeded 400-line limit). Config
#   loading and schema validation isolated here so build.py stays focused
#   on orchestration.
# ====================================================================
