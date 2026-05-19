"""
MODULE: config
GOAL: Load and provide the doc_compliance.json config and components.json registry to all sub-modules.
BUSINESS CONTEXT: Centralises path constants and config loading so that every module uses the same defaults.
ARCHITECTURE: Not needed.
DOC_LINKS:
    - docs/portability_audit.md
"""
import sys
import typing
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Portability loader
# ---------------------------------------------------------------------------
# The portable configuration for this package lives at:
#   scripts/doc_compliance/doc_compliance.json
# That file holds project-specific path overrides. If the file is absent or
# a key is missing, the Bybit-Trader defaults below are used as fallbacks.
# An adopter customises this package by editing doc_compliance.json only —
# no Python source changes are required.
# ---------------------------------------------------------------------------

_PKG_CONFIG_PATH = Path(__file__).parent / "doc_compliance.json"
_pkg_config: dict | None = None

def _load_pkg_config() -> dict:
    """Load scripts/doc_compliance/doc_compliance.json once; cache the result.

    Returns:
        dict: Parsed JSON contents, or an empty dict if the file is absent.
    """
    global _pkg_config
    if _pkg_config is None:
        if _PKG_CONFIG_PATH.exists():
            with open(_PKG_CONFIG_PATH, "r", encoding="utf-8") as fh:
                _pkg_config = json.load(fh)
        else:
            _pkg_config = {}
    return _pkg_config


def _get(key: str, default: object) -> object:
    """Return config value for *key*, falling back to *default* if absent.

    Args:
        key: Top-level key in scripts/doc_compliance/doc_compliance.json.
        default: Value to return when the key is absent.

    Returns:
        object: The configured value or the default.
    """
    return _load_pkg_config().get(key, default)


# Docs root — derived from doc_compliance.json or commit_guardian config.
_DOCS_ROOT: str = _get("docs_root", None) or "docs"

# Default relative paths — resolved against project_root at runtime.
# These are read from doc_compliance.json when present; defaults are
# derived from _DOCS_ROOT so projects with custom docs dirs work out of the box.
DEFAULT_CONFIG_FILE: str = _get("config_file", f"{_DOCS_ROOT}/doc_compliance.json")
DEFAULT_COMPONENTS_FILE: str = _get("components_file", f"{_DOCS_ROOT}/components.json")


def _load_config_and_registry(project_root: str) -> tuple[dict | None, dict | None]:
    """Load configuration and component registry.

    Args:
        project_root: Root directory of the project.

    Returns:
        tuple: (config_dict, registry_dict) or (None, None) if not found.
    """
    config_file = Path(project_root) / DEFAULT_CONFIG_FILE
    components_file = Path(project_root) / DEFAULT_COMPONENTS_FILE
    if not config_file.exists() or not components_file.exists():
        return None, None

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    with open(components_file, "r", encoding="utf-8") as f:
        registry = json.load(f)
    return config, registry

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-04 19:00 [Antigravity]: Initial creation as part of the doc_compliance_scanner (#EPIC-LeafcutterMVP/01)
  modularization. Extracted from the monolithic doc_compliance_scanner.py to reduce file
  size below the pre-commit 400-line threshold.
- 2026-05-13 09:20 [EPIC-PortableDevWorkflow/12]: Added _get(key, default) loader and (#EPIC-LeafcutterMVP/01)
  _load_pkg_config() cache. DEFAULT_CONFIG_FILE and DEFAULT_COMPONENTS_FILE now read from
  scripts/doc_compliance/doc_compliance.json with fallback to Bybit-Trader defaults.
  This makes the package adoptable by any project without editing Python source.
====================================================================
"""
