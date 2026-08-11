"""
Central configuration loader for Commit Guardian hooks.

Loads all settings from ``commit_guardian.json`` located next to this file.
Every checker imports its constants from here — edit the JSON to customise.

Usage::

    from config import MAX_COMPLEXITY_SCORE, EXCLUDED_DIRS
"""

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# JSON loader (cached at module-import time)
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).resolve().parent / "commit_guardian.json"
_config: dict[str, Any] = {}


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and cache the JSON configuration file.

    Args:
        path: Optional override path to the JSON config. Defaults to
              ``commit_guardian.json`` in the same directory as this module.

    Returns:
        dict[str, Any]: The parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        json.JSONDecodeError: If the config file contains invalid JSON.
    """
    global _config
    if _config:
        return _config

    config_file = path or _CONFIG_PATH
    if not config_file.exists():
        raise FileNotFoundError(
            f"Commit Guardian config not found: {config_file}\n"
            "  FIX: Ensure commit_guardian.json exists next to config.py."
        )

    try:
        with open(config_file, encoding="utf-8") as f:
            _config = json.load(f)
    except OSError as exc:
        raise FileNotFoundError(
            f"Commit Guardian config could not be read: {config_file}\n"
            f"  OS error: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"Commit Guardian config contains invalid JSON: {config_file}\n"
            f"  {exc.msg}",
            exc.doc,
            exc.pos,
        ) from exc

    return _config


def _get(section: str, key: str, default: Any = None) -> Any:
    """Retrieve a nested config value by section and key.

    Args:
        section: Top-level JSON key (e.g. 'complexity', 'docstrings').
        key: Second-level key within the section.
        default: Fallback if the key is missing.

    Returns:
        Any: The config value, or *default* if not found.
    """
    cfg = load_config()
    return cfg.get(section, {}).get(key, default)


# ---------------------------------------------------------------------------
# Eagerly load on import so missing-file errors surface immediately
# ---------------------------------------------------------------------------
load_config()

# ---------------------------------------------------------------------------
# Global
# ---------------------------------------------------------------------------
EXCLUDED_DIRS: set[str] = set(load_config().get("excluded_dirs", []))

# ---------------------------------------------------------------------------
# check_file_size
# ---------------------------------------------------------------------------
FILE_LINE_LIMITS: dict[str, int] = _get("file_size", "line_limits", {".py": 400, ".sql": 600})
DEFAULT_LINE_LIMIT: int = _get("file_size", "default_limit", 400)
CHECKED_EXTENSIONS: list[str] = _get("file_size", "checked_extensions", [".py", ".sql"])

# ---------------------------------------------------------------------------
# check_complexity
# ---------------------------------------------------------------------------
MAX_COMPLEXITY_SCORE: int = _get("complexity", "max_score", 15)
COMPLEXITY_EXCLUDED_DIRS: tuple[str, ...] = tuple(_get("complexity", "excluded_dirs", ["alembic", "legacy"]))

# ---------------------------------------------------------------------------
# check_sql_complexity
# ---------------------------------------------------------------------------
MAX_SQL_COMPLEXITY_SCORE: int = _get("sql_complexity", "max_score", 65)
SQL_COMPLEXITY_EXCLUDED_DIRS: tuple[str, ...] = tuple(_get("sql_complexity", "excluded_dirs", ["alembic", "legacy"]))

# ---------------------------------------------------------------------------
# check_docstrings
# ---------------------------------------------------------------------------
DOCSTRING_STYLE: str = _get("docstrings", "style", "google")
DOCSTRING_TRIVIAL_MAX_LINES: int = _get("docstrings", "trivial_max_lines", 5)
ENFORCE_TYPE_ANNOTATIONS: bool = _get("docstrings", "enforce_type_annotations", True)
EXEMPT_DUNDERS: set[str] = set(_get("docstrings", "exempt_dunders", []))

# ---------------------------------------------------------------------------
# check_documentation
# ---------------------------------------------------------------------------
SQL_REQUIRED_FIELDS: list[str] = _get("documentation", "sql_required_fields",
                                       ["Object Name:", "Goal:", "Business Context:", "Architecture:"])
PYTHON_REQUIRED_FIELDS: list[str] = _get("documentation", "python_required_fields",
                                          ["MODULE:", "GOAL:", "BUSINESS CONTEXT:", "ARCHITECTURE:"])

# ---------------------------------------------------------------------------
# check_root_files
# ---------------------------------------------------------------------------
ALLOWED_ROOT_FILES: set[str] = set(_get("root_files", "allowed_files", []))
ALLOWED_ROOT_EXTENSIONS: set[str] = set(_get("root_files", "allowed_extensions", []))

# ---------------------------------------------------------------------------
# check_folder_density
# ---------------------------------------------------------------------------
MAX_FILES_PER_FOLDER: int = _get("folder_density", "max_files_per_folder", 15)
DENSITY_EXCLUDED_DIRS: set[str] = set(_get("folder_density", "excluded_dirs", []))
DENSITY_EXEMPT_EXTENSIONS: set[str] = set(_get("folder_density", "exempt_extensions", []))
DENSITY_EXEMPT_FILENAMES: set[str] = set(_get("folder_density", "exempt_filenames", []))

# ---------------------------------------------------------------------------
# check_debug_scripts
# ---------------------------------------------------------------------------
DEBUG_VALID_CATEGORIES: list[str] = _get("debug_scripts", "valid_categories", [])
DEBUG_REQUIRED_TAGS: list[str] = _get("debug_scripts", "required_tags", [])
DEBUG_CONTEXT_TAGS: list[str] = _get("debug_scripts", "context_tags", [])
DEBUG_EXEMPT_NAMES: set[str] = set(_get("debug_scripts", "exempt_names", []))
DEBUG_EXEMPT_DIRS: set[str] = set(_get("debug_scripts", "exempt_dirs", []))

# ---------------------------------------------------------------------------
# check_infra_docs
# ---------------------------------------------------------------------------
INFRA_FILE_PATTERNS: list[str] = _get("infra_docs", "infra_file_patterns", [])
INFRA_HIGH_IMPACT_KEYWORDS: list[str] = _get("infra_docs", "high_impact_keywords", [])

# ---------------------------------------------------------------------------
# check_doc_frontmatter
# Docs root — configurable via commit_guardian.json → doc_frontmatter.docs_dir
# or the top-level docs_root key. All doc-related globs and paths derive from this.
DOC_FM_DOCS_DIR: str = _get("doc_frontmatter", "docs_dir", None) or load_config().get("docs_root", "docs").rstrip("/")

# ---------------------------------------------------------------------------
# required_fields is a per-glob dict:
#   { "<docs>/architecture/**": [..., "flight_level"], "<docs>/**": [...] }
# Callers resolve the correct field list via fnmatch against the file path.
DOC_FM_REQUIRED_FIELDS_BY_GLOB: dict[str, list[str]] = _get(
    "doc_frontmatter",
    "required_fields",
    {
        f"{DOC_FM_DOCS_DIR}/architecture/adrs/**": ["title", "type", "status", "created", "last_updated", "components"],
        f"{DOC_FM_DOCS_DIR}/architecture/**": ["title", "type", "status", "created", "last_updated", "components", "flight_level"],
        f"{DOC_FM_DOCS_DIR}/**": ["title", "type", "status", "created", "last_updated", "components"],
    },
)
# Fallback flat list for callers that have not yet been updated to pass a file path.
# Points to the broadest glob (<docs>/**) so existing tests keep working.
DOC_FM_REQUIRED_FIELDS: list[str] = DOC_FM_REQUIRED_FIELDS_BY_GLOB.get(
    f"{DOC_FM_DOCS_DIR}/**", ["title", "type", "status", "created", "last_updated", "components"]
)
DOC_FM_ALLOWED_TYPES: list[str] = _get("doc_frontmatter", "allowed_types",
                                        ["tutorial", "how-to", "reference", "explanation", "adr", "cross-cutting"])
DOC_FM_ALLOWED_STATUSES: list[str] = _get("doc_frontmatter", "allowed_statuses",
                                           ["active", "draft", "deprecated", "migrating"])
DOC_FM_FLIGHT_LEVEL_VALUES: list[str] = _get("doc_frontmatter", "flight_level_values",
                                              ["L1-Context", "L2-Container", "L3-Component", "L4-Code"])
# DEPRECATED: superseded by diagram_types.json via diagram_type_validators._load_diagram_types().
# frontmatter_validators.py now delegates validate_diagram_type() to diagram_type_validators,
# which reads the canonical enum from leafcutter/config/diagram_types.json.
# Do NOT remove this constant yet — other importers may reference it.
DOC_FM_DIAGRAM_TYPE_VALUES: list[str] = _get("doc_frontmatter", "diagram_type_values",
                                              ["context", "container", "component", "sequence",
                                               "erd", "state", "dataflow", "none"])
DOC_FM_COMPONENTS_REGISTRY: str = _get("doc_frontmatter", "components_registry", f"{DOC_FM_DOCS_DIR}/components.json")

# ---------------------------------------------------------------------------
# check_doc_length
# ---------------------------------------------------------------------------
DOC_LENGTH_MAX_LINES: int = _get("doc_length", "max_lines", 300)
DOC_LENGTH_MAX_LINES_ADR: int = _get("doc_length", "max_lines_adr", 400)
DOC_LENGTH_MAX_SECTIONS: int = _get("doc_length", "max_sections", 25)
DOC_LENGTH_SEVERITY: str = _get("doc_length", "severity", "warn")
DOC_LENGTH_EXCLUDED_FILES: list[str] = _get("doc_length", "excluded_files", ["README.md", "CHANGELOG.md"])

# ---------------------------------------------------------------------------
# check_doc_links
# ---------------------------------------------------------------------------
DOC_LINKS_SEVERITY: str = _get("doc_links", "severity", "warn")
DOC_LINKS_CHECK_BIDIRECTIONAL: bool = _get("doc_links", "check_bidirectional", True)
DOC_LINKS_CHECK_MERMAID: bool = _get("doc_links", "check_mermaid_architecture_link", True)

# ---------------------------------------------------------------------------
# check_doc_frontmatter — ticket-side
# ---------------------------------------------------------------------------
TICKET_FM_REQUIRED_FIELDS: list[str] = _get("ticket_frontmatter", "required_fields",
                                             ["title", "status", "components", "created", "depends_on"])
TICKET_FM_ALLOWED_STATUSES: list[str] = _get("ticket_frontmatter", "allowed_statuses",
                                              ["todo", "in_progress", "blocked", "done", "deferred"])
TICKET_FM_ALLOWED_TYPES: list[str] = _get("ticket_frontmatter", "allowed_types", ["epic"])
TICKET_FM_TICKETS_DIR: str = _get("ticket_frontmatter", "tickets_dir", "tickets")

# ---------------------------------------------------------------------------
# check_ticket_signoff_parity — agent registry
# ---------------------------------------------------------------------------
AGENT_REGISTRY_PATH: str = _get(
    "ticket_signoff_parity", "agent_registry_path", "leafcutter/config/agent_registry.json"
)

# ---------------------------------------------------------------------------
# check_doc_coverage
# ---------------------------------------------------------------------------
DOC_COVERAGE_LARGE_DIFF_THRESHOLD: int = _get("doc_coverage", "large_diff_threshold", 50)
DOC_COVERAGE_KNOWLEDGE_GRAPH_PATH: str = _get("doc_coverage", "knowledge_graph_path", "knowledge_graph.json")

# ---------------------------------------------------------------------------
# check_structural_change
# ---------------------------------------------------------------------------
STRUCTURAL_SIGNALS: list[dict] = _get(
    "structural_change",
    "signals",
    [
        {"name": "new top-level package", "pattern": r"^[^/]+/__init__\.py$"},
    ],
)
STRUCTURAL_REQUIRED_DOC: str = _get("structural_change", "required_doc", f"{DOC_FM_DOCS_DIR}/components.json")
STRUCTURAL_BYPASS_TOKEN: str = _get("structural_change", "bypass_token", "[NO-ARCH-UPDATE]")

# ---------------------------------------------------------------------------
# check_secrets
# ---------------------------------------------------------------------------
SECURITY_SCANNER_SCRIPTS_DIR: str = _get(
    "security_scanner",
    "scripts_dir",
    ".claude/skills/security-scanner/scripts",
)

# ---------------------------------------------------------------------------
# check_mermaid_complexity
# ---------------------------------------------------------------------------
MERMAID_COMPLEXITY_STRICT: bool = _get("mermaid_complexity", "strict", False)
MERMAID_COMPLEXITY_MAX_NODES: int = _get("mermaid_complexity", "max_nodes", 15)
MERMAID_COMPLEXITY_MAX_EDGES: int = _get("mermaid_complexity", "max_edges", 20)
MERMAID_COMPLEXITY_MAX_PARTICIPANTS: int = _get("mermaid_complexity", "max_participants", 8)
MERMAID_COMPLEXITY_MAX_INTERACTIONS: int = _get("mermaid_complexity", "max_interactions", 25)
MERMAID_COMPLEXITY_MAX_TABLES: int = _get("mermaid_complexity", "max_tables", 12)
MERMAID_COMPLEXITY_MAX_STATES: int = _get("mermaid_complexity", "max_states", 10)
MERMAID_COMPLEXITY_MAX_CLASSES: int = _get("mermaid_complexity", "max_classes", 10)
MERMAID_COMPLEXITY_MAX_BOUNDARIES: int = _get("mermaid_complexity", "max_boundaries", 4)

# ---------------------------------------------------------------------------
# check_duplicate_code
# ---------------------------------------------------------------------------
DUPLICATE_CODE_ENABLED: bool = _get("duplicate_code", "enabled", False)
DUPLICATE_CODE_STRICT: bool = _get("duplicate_code", "strict", False)
DUPLICATE_CODE_MIN_LINES: int = _get("duplicate_code", "min_lines", 5)
DUPLICATE_CODE_MIN_TOKENS: int = _get("duplicate_code", "min_tokens", 50)
DUPLICATE_CODE_THRESHOLD_PERCENT: int = _get("duplicate_code", "threshold_percent", 5)
DUPLICATE_CODE_CHECKED_EXTENSIONS: list[str] = _get(
    "duplicate_code",
    "checked_extensions",
    [".py", ".ts", ".js", ".tsx", ".jsx", ".sql"],
)


# ---------------------------------------------------------------------------
# check_diff_coverage
# ---------------------------------------------------------------------------
DIFF_COVERAGE_ENABLED: bool = _get("diff_coverage", "enabled", False)
DIFF_COVERAGE_STRICT: bool = _get("diff_coverage", "strict", False)
DIFF_COVERAGE_MIN_COVERAGE_PERCENT: int = _get("diff_coverage", "min_coverage_percent", 80)
DIFF_COVERAGE_XML_PATH: str = _get("diff_coverage", "coverage_xml_path", "coverage.xml")
DIFF_COVERAGE_COMPARE_BRANCH: str = _get("diff_coverage", "compare_branch", "origin/main")
DIFF_COVERAGE_MAX_AGE_SECONDS: int = _get("diff_coverage", "max_age_seconds", 3600)


# ---------------------------------------------------------------------------
# check_ticket_ac_status_parity
# ---------------------------------------------------------------------------
TICKET_AC_PARITY_ENABLED: bool = _get("ticket_ac_status_parity", "enabled", True)
TICKET_AC_PARITY_AC_STORE_ROOT: str = _get(
    "ticket_ac_status_parity", "ac_store_root", "docs/acceptance-criteria"
)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-11 [workflow-architect/KI-1]: Added TICKET_AC_PARITY_ENABLED and
  TICKET_AC_PARITY_AC_STORE_ROOT constants for check_ticket_ac_status_parity.py
  (BO-2200 retrospective KI-1). enabled defaults to True; ac_store_root defaults
  to 'docs/acceptance-criteria'. Tunable via ticket_ac_status_parity section in
  commit_guardian.json.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100d]: Added DIFF_COVERAGE_* constants for
  check_diff_coverage.py (AC GE-101a / originally GE-100d). enabled and strict both
  default to False; min_coverage_percent=80; coverage_xml_path='coverage.xml';
  compare_branch='origin/main'; max_age_seconds=3600. All tunable via diff_coverage
  section in commit_guardian.json.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100b]: Added DUPLICATE_CODE_THRESHOLD_PERCENT
  and DUPLICATE_CODE_CHECKED_EXTENSIONS constants (AC GE-100b). threshold_percent defaults
  to 5; checked_extensions defaults to [.py, .ts, .js, .tsx, .jsx, .sql] matching the AC.
  Removed the legacy DUPLICATE_CODE_THRESHOLD int (superseded by threshold_percent).
- 2026-06-18 [python-coder/TICKET-20260616-GE-100a]: Added DUPLICATE_CODE_* constants for
  check_duplicate_code.py (AC GE-100a). enabled and strict both default to False;
  min_lines/min_tokens/threshold are tunable via duplicate_code section in commit_guardian.json.
- 2026-05-15 12:00 [python-coder/T06]: Added AGENT_REGISTRY_PATH constant for check_ticket_signoff_parity
  check #6 (unchecked-tasks parity guard). Defaults to
  "leafcutter/config/agent_registry.json" relative to project root;
  overridable via ticket_signoff_parity.agent_registry_path in commit_guardian.json.
- 2026-05-14 02:40 [epic-supervisor/merge]: Resolved merge conflict with main — adopted main's
  DOC_LENGTH defaults (max_lines 300, max_lines_adr 400, max_sections 25,
  excluded_files [README.md, CHANGELOG.md]) over epic's (500/600/20/[]).
- 2026-05-14 02:15 [epic-supervisor/T09]: Added DOC_LENGTH_MAX_LINES/ADR/MAX_SECTIONS/SEVERITY/EXCLUDED_FILES
  constants for check_doc_length.py; added STRUCTURAL_SIGNALS/REQUIRED_DOC/BYPASS_TOKEN constants for
  check_structural_change.py. Both sets were missing from the template, causing ImportError on startup.
- 2026-05-13 12:00 [epic-supervisor/T02]: Added SECURITY_SCANNER_SCRIPTS_DIR constant so
  check_secrets.py resolves the scanner skill path via config rather than a hardcoded
  project-specific path. Consumer projects override via commit_guardian.json
  security_scanner.scripts_dir.
- 2026-05-12 11:30 [Agent]: Added DOC_COVERAGE_* constants for check_doc_coverage advisory hook (ticket 12 EPIC-DocTraceability).
- 2026-05-11 00:00 [Agent]: Added DOC_FM_REQUIRED_FIELDS_BY_GLOB (per-glob dict),
  DOC_FM_FLIGHT_LEVEL_VALUES and DOC_FM_DIAGRAM_TYPE_VALUES constants. Kept
  DOC_FM_REQUIRED_FIELDS as a flat-list fallback pointing to the broadest glob so
  existing call-sites remain compatible (ticket 02).
- 2026-05-10 13:42 [AI/Antigravity]: Added TICKET_FM_* constants for check_ticket_signoff_parity
  configurations to fix import errors during test collection.
- 2026-05-05 12:00 [AI]: Added TICKET_FM_* constants for the ticket-side YAML
  frontmatter validation in check_doc_frontmatter (EPIC-DocTraceability #15).
- 2026-05-03 18:00 [AI/Antigravity]: Added DOC_FM_* constants for check_doc_frontmatter
  and DOC_LINKS_* constants for check_doc_links configurations.
- 2026-04-30 19:12 [AI/Antigravity]: Added ENFORCE_TYPE_ANNOTATIONS constant
  for the new type annotation enforcement in check_docstrings.py.
- 2026-04-30 16:00 [AI/Antigravity]: Extracted all hardcoded settings from
  checker scripts into commit_guardian.json with this config loader module.
====================================================================
"""
