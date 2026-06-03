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
        # Auto-detect in target root across known platform directories
        platform_dirs = [".claude", ".gemini", ".cursor", ".github", ".cline"]
        for p_dir in platform_dirs:
            candidate = target_root / p_dir / "skills_config.json"
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as f:
                    project_config = json.load(f)
                project_config.pop("_comment", None)
                break

    merged = {**defaults, **project_config}
    return _flatten_nested_keys(merged)


def _flatten_nested_keys(
    config: dict[str, Any],
    prefix: str = "",
    separator: str = ".",
) -> dict[str, Any]:
    """Flatten nested dict keys into dot-notation strings.

    Converts ``{"frontend": {"project_context_path": "..."}}`` into
    ``{"frontend": {"project_context_path": "..."}, "frontend.project_context_path": "..."}``
    so that ``{{frontend.project_context_path}}`` placeholders in agent/skill
    templates resolve correctly via ``inject_config``.

    The original nested dict keys are preserved alongside the flattened keys,
    so existing code that reads ``config["frontend"]`` (the nested dict) still
    works. Only dict values are flattened; list and scalar values are left as-is.

    Args:
        config: Flat-or-nested dictionary to flatten.
        prefix: Dot-separated key prefix accumulated during recursion (empty
            at the top level).
        separator: Character to use between key segments (default: ``"."``)

    Returns:
        New dictionary with both the original keys and additional dot-notation
        keys for every nested dict level.
    """
    result: dict[str, Any] = {}
    for key, value in config.items():
        full_key = f"{prefix}{separator}{key}" if prefix else key
        result[full_key] = value
        if isinstance(value, dict):
            nested = _flatten_nested_keys(value, prefix=full_key, separator=separator)
            result.update(nested)
    return result


class ConfigValidationError(ValueError):
    """Raised when a config value fails validation outside JSON-Schema."""


_VALID_SHIM_STRATEGIES = ("symlink", "copy", "auto")


def _validate_live_surface_testing(config: dict[str, Any]) -> None:
    """Validate the live_surface_testing config block when present.

    Enforces four rules:
    1. ``enabled`` must be a bool when present.
    2. When ``enabled`` is True, ``startup_command`` must be a non-empty string.
    3. When both ``port_range_start`` and ``port_range_end`` are present,
       ``port_range_start`` must be less than ``port_range_end``.
    4. Absence of the key is valid — it is treated as ``enabled: false``.

    Args:
        config: The top-level config dict (flat or nested); reads the nested
            ``live_surface_testing`` key directly.

    Raises:
        ConfigValidationError: When any of the above rules are violated.
    """
    block = config.get("live_surface_testing")
    if block is None:
        return  # Optional block; absence is valid.

    enabled = block.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise ConfigValidationError(
            "live_surface_testing.enabled must be a boolean (true or false)."
        )

    if enabled is True:
        startup_command = block.get("startup_command", "")
        if not startup_command or not str(startup_command).strip():
            raise ConfigValidationError(
                "live_surface_testing.startup_command must be a non-empty string "
                "when live_surface_testing.enabled is true."
            )

    port_start = block.get("port_range_start")
    port_end = block.get("port_range_end")
    if port_start is not None and port_end is not None:
        if port_start >= port_end:
            raise ConfigValidationError(
                f"live_surface_testing port_range_start ({port_start}) must be "
                f"less than port_range_end ({port_end})."
            )


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate config against the package JSON schema and custom rules.

    Args:
        config: Dictionary of config values to validate against the package
            JSON schema at ``config/skills_config.schema.json``.

    Returns:
        List of error message strings. Empty list means the config is valid.
        Returns a single warning string if ``jsonschema`` is not installed or
        the schema file is not found.

    Raises:
        ConfigValidationError: When shim_strategy or live_surface_testing
            has an invalid value.
    """
    shim_strategy = config.get("shim_strategy", "auto")
    if shim_strategy not in _VALID_SHIM_STRATEGIES:
        raise ConfigValidationError(
            f"Invalid shim_strategy: {shim_strategy!r}. "
            f"Valid values: {', '.join(_VALID_SHIM_STRATEGIES)}"
        )

    _validate_live_surface_testing(config)

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
# - 2026-06-03 10:05 [python-coder]: Added _validate_live_surface_testing() and wired it
#   into validate_config(). Validates enabled (bool), startup_command (non-empty when
#   enabled=true), and port_range_start < port_range_end. Absence of the key is valid
#   (treated as enabled: false). (#EPIC-LiveSurfaceTesting/03)
# ====================================================================
