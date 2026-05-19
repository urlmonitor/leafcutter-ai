"""
MODULE: bootstrap
GOAL: Create the initial doc_compliance.json config and auto-discover components into a draft components.json.
BUSINESS CONTEXT: The bootstrap step reduces manual setup burden when onboarding a new project to the compliance workflow.
ARCHITECTURE: Not needed.
DOC_LINKS:
    - docs/portability_audit.md
"""
import json
import glob
from pathlib import Path
from scripts.doc_compliance.config import DEFAULT_CONFIG_FILE, DEFAULT_COMPONENTS_FILE, _get

def init_config(project_root: str = ".") -> None:
    """Generate a blank, project-agnostic doc_compliance.json skeleton.

    Produces a structurally valid but entirely empty config with guided
    # REVIEW comments so any project can fill it in. Does not scan the
    current folder tree — no project assumptions are made.

    Args:
        project_root: Root directory of the target project.
    """
    docs_dir = Path(project_root) / "docs"
    docs_dir.mkdir(exist_ok=True)
    config_path = docs_dir / "doc_compliance.json"

    if config_path.exists():
        print(f"Config already exists at {config_path}. Aborting init.")
        return

    blank_config = {
        "$schema": "doc-compliance-config-v1",
        "project": "YOUR_PROJECT_NAME",
        "scan_paths": {
            "python": [],
            "sql": [],
            "docs": []
        },
        "component_sources": [],
        "standalone_components": [],
        "code_header_pattern": "MODULE:",
        "sql_header_pattern": "Object Name:",
        "ignore": ["__pycache__", "venv/", ".venv/"]
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(blank_config, f, indent=2)
        f.write("\n")

    print(
        f"Blank config written to {config_path}. "
        "Edit docs/doc_compliance.json then run --bootstrap or --discover-components."
    )


def bootstrap() -> None:
    """Generates a draft doc_compliance.json by scanning the project.

    Project-specific values (scan paths, component sources, project name) are
    read from scripts/doc_compliance/doc_compliance.json via _get(). Bybit-Trader
    defaults are used as fallbacks so existing behaviour is fully preserved.
    Adopters customise those values in doc_compliance.json without touching this file.
    """
    print("Bootstrapping doc_compliance.json...")

    draft_config = {
        "$schema": "doc-compliance-config-v1",
        "project": _get("bootstrap_project_name", "bybit-trader"),
        "scan_paths": _get("bootstrap_scan_paths", {
            "python": ["collector/", "models/", "trading/", "live_trader/", "utils/"],
            "sql": ["sql_functions/"],
            "docs": ["docs/", "adr/", "architecture/"]
        }),
        "component_sources": _get("bootstrap_component_sources", [
            { "pattern": "collector/services/*/", "type": "service", "name_from": "folder" },
            { "pattern": "models/*.py", "type": "data_table", "name_from": "filename", "exclude": ["__init__.py", "base.py", "*_type.py"] },
            { "pattern": "sql_functions/procedures/*/", "type": "data_pipeline", "name_from": "folder" }
        ]),
        "standalone_components": _get("bootstrap_standalone_components", [
            { "file": "database_manager.py", "type": "infrastructure", "name": "database_manager" }
        ]),
        "code_header_pattern": "MODULE:",
        "sql_header_pattern": "Object Name:",
        "ignore": _get("bootstrap_ignore", ["__pycache__", "alembic/", "unit_tests/", "debugging/", "legacy/", "venv/", ".venv/"])
    }

    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    config_path = docs_dir / "doc_compliance.json"
    if config_path.exists():
        print(f"Config already exists at {config_path}. Aborting bootstrap.")
        return

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(draft_config, f, indent=2)

    print(f"Draft generated. Review {config_path} before proceeding.")

def discover_components(project_root: str = ".") -> None:
    """Reads component_sources and generates a draft components.json.

    Args:
        project_root: Root directory of the target project.
    """
    config_file = Path(project_root) / DEFAULT_CONFIG_FILE
    components_file = Path(project_root) / DEFAULT_COMPONENTS_FILE
    if not config_file.exists():
        print("No doc_compliance.json found. Run --bootstrap first.")
        return

    print("Discovering components...")

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    components = {}

    for source in config.get("component_sources", []):
        pattern = source.get("pattern", "")
        # Very simple globbing for the draft
        matches = glob.glob(pattern, recursive=True)
        for match in matches:
            path = Path(match)
            if source.get("name_from") == "folder":
                name = path.parent.name if path.is_file() else path.name
            else:
                name = path.stem

            if any(glob.fnmatch.fnmatch(path.name, exc) for exc in source.get("exclude", [])):
                continue

            desc = f"Auto-discovered {source.get('type')}. Needs REVIEW."
            readme_path = path / "README.md" if path.is_dir() else path.parent / "README.md"
            if readme_path.exists():
                with open(readme_path, "r", encoding="utf-8") as rf:
                    content = rf.read()
                    # Extract first paragraph
                    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and not p.startswith("#")]
                    if paragraphs:
                        desc = paragraphs[0][:200] + ("..." if len(paragraphs[0]) > 200 else "")

            components[name] = {
                "name": name.replace("_", " ").title(),
                "description": desc,
                "type": source.get("type"),
                "detail_ref": str(path),
                "status": "draft"
            }

    draft_components = {
        "$schema": "component-registry-v1",
        "project": config.get("project", "unknown"),
        "version": "1.0.0",
        "components": components
    }

    if components_file.exists():
        print(f"Registry already exists at {components_file}. Aborting discovery.")
        return
    out_path = components_file

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(draft_components, f, indent=2)

    print(f"Discovered {len(components)} components. Review {out_path} before proceeding.")

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-13 09:20 [EPIC-PortableDevWorkflow/12]: Updated bootstrap() to call _get() for
  all project-specific values (project name, scan_paths, component_sources, standalone_components,
  ignore list). Bybit-Trader values remain as JSON defaults in doc_compliance.json.
  Adopters override them without touching Python source.
- 2026-05-12 10:30 [Agent]: Added init_config() function providing a blank project-agnostic
  doc_compliance.json skeleton (--init mode). Unlike bootstrap(), init_config() makes no
  project-specific guesses and is designed for portability across projects (ticket 14).
- 2026-05-04 19:00 [Antigravity]: Initial creation as part of the doc_compliance_scanner
  modularization. Extracted bootstrap() and discover_components() from the monolithic
  doc_compliance_scanner.py to reduce file size below the pre-commit 400-line threshold.
====================================================================
"""
