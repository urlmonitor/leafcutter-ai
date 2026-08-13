"""
MODULE: package_audit
GOAL: Formalise the gap analysis between the leafcutter package
    templates and a consumer project's live files, producing a structured
    Markdown + JSON report of what is missing from the package, what is
    project-specific, and what is already in the package.
BUSINESS CONTEXT: EPIC-PortableDevWorkflow shipped with gaps: 19 files
    present in the live project are absent from the package templates,
    including critical hooks (check_build_drift.py) and the
    .pre-commit-config.yaml that registers them. This script makes the gap
    analysis repeatable and machine-readable so it can be wrapped by the
    package-audit skill (T8) and run in CI via a pre-commit hook (T1).
ARCHITECTURE: Single public function run_audit(project_root, package_root,
    boundary_config_path) returns an AuditReport dataclass. Three private
    helpers audit_section() walk one directory pair, classify_item() maps a
    filename to its boundary bucket using the config, and format_markdown()
    renders the report as Markdown. CLI entry point at bottom calls run_audit
    with sensible defaults, prints Markdown by default or JSON with --json.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AuditItem:
    """One file found in the live project directory.

    Attributes:
        filename: Bare filename (no path prefix).
        classification: 'portable', 'project-specific', or 'unknown'.
        in_template: True if the file is already in the template directory.
        action: 'move', 'mark-boundary', or 'none'.
    """

    filename: str
    classification: str
    in_template: bool
    action: str


@dataclass
class SectionReport:
    """Audit result for one directory pair.

    Attributes:
        name: Human-readable section name (e.g. 'commit-guardian').
        live_dir: Path to the live project directory that was scanned.
        template_dir: Path to the package template directory that was compared.
        items: Ordered list of AuditItem for every file found in live_dir.
        missing_count: Number of portable files absent from template_dir.
    """

    name: str
    live_dir: str
    template_dir: str
    items: list[AuditItem] = field(default_factory=list)
    missing_count: int = 0


@dataclass
class AuditReport:
    """Top-level audit result across all sections.

    Attributes:
        project_root: Absolute path to the consumer project root.
        package_root: Absolute path to the leafcutter package root.
        sections: One SectionReport per audited directory pair.
        total_missing: Total number of portable files absent from all templates.
    """

    project_root: str
    package_root: str
    sections: list[SectionReport] = field(default_factory=list)
    total_missing: int = 0


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

_SKIP_NAMES = frozenset({
    "__pycache__", ".DS_Store", "Thumbs.db",
    "__init__.py",  # shared boilerplate — always in both; skip from gap list
})
_SKIP_EXTENSIONS = frozenset({".pyc", ".pyo"})


def _classify_item(filename: str, items_map: dict[str, str]) -> str:
    """Return the boundary classification for a filename.

    Args:
        filename: Bare filename to classify.
        items_map: Mapping from filename to 'portable' or 'project-specific'
            as loaded from package_boundary.json.

    Returns:
        'portable', 'project-specific', or 'unknown' when the filename is not
        in the items_map and cannot be inferred.
    """
    return items_map.get(filename, "unknown")


def _suggest_action(classification: str, in_template: bool) -> str:
    """Derive the recommended action from classification and template presence.

    Args:
        classification: One of 'portable', 'project-specific', 'unknown'.
        in_template: True if the file is already present in the template dir.

    Returns:
        'move' if portable and absent from template; 'mark-boundary' if
        project-specific and absent; 'none' if already in template or unknown
        and in template.
    """
    if in_template:
        return "none"
    if classification == "portable":
        return "move"
    if classification == "project-specific":
        return "mark-boundary"
    return "none"


# ---------------------------------------------------------------------------
# Core audit logic
# ---------------------------------------------------------------------------

def _audit_section(
    section_name: str,
    live_dir: Path,
    template_dir: Path,
    items_map: dict[str, str],
) -> SectionReport:
    """Audit one directory pair and return a SectionReport.

    Walks live_dir, skips boilerplate names and non-code extensions, then
    classifies each entry against the items_map from package_boundary.json.
    Files already present in template_dir are marked in_template=True.

    Args:
        section_name: Human-readable label (e.g. 'commit-guardian').
        live_dir: Absolute path to the live project directory.
        template_dir: Absolute path to the package template directory.
        items_map: {filename: classification} from package_boundary.json.

    Returns:
        Populated SectionReport with items sorted by filename.
    """
    report = SectionReport(
        name=section_name,
        live_dir=str(live_dir),
        template_dir=str(template_dir),
    )

    if not live_dir.exists():
        return report

    template_files: set[str] = set()
    if template_dir.exists():
        for entry in template_dir.iterdir():
            if entry.name.startswith("_"):
                continue
            template_files.add(entry.name)

    for entry in sorted(live_dir.iterdir(), key=lambda p: p.name):
        name = entry.name
        if name in _SKIP_NAMES:
            continue
        if entry.suffix in _SKIP_EXTENSIONS:
            continue
        # Skip hidden files/dirs
        if name.startswith("."):
            continue

        classification = _classify_item(name, items_map)
        in_template = name in template_files
        action = _suggest_action(classification, in_template)

        item = AuditItem(
            filename=name,
            classification=classification,
            in_template=in_template,
            action=action,
        )
        report.items.append(item)
        if action == "move":
            report.missing_count += 1

    return report


def run_audit(
    project_root: Path,
    package_root: Path,
    boundary_config_path: Path | None = None,
) -> AuditReport:
    """Run the full package gap audit and return a structured AuditReport.

    Reads package_boundary.json from boundary_config_path (defaults to
    package_root/config/package_boundary.json) and audits each section
    defined there against the actual filesystem.

    Args:
        project_root: Absolute path to the consumer project root (e.g. the
            adopting repository's checkout).
        package_root: Absolute path to the leafcutter package root
            (the directory containing config/, scripts/, templates/).
        boundary_config_path: Optional override for the boundary config file.
            Defaults to package_root/config/package_boundary.json.

    Returns:
        AuditReport with one SectionReport per audited directory pair.

    Raises:
        FileNotFoundError: If boundary_config_path does not exist.
        json.JSONDecodeError: If the config file is not valid JSON.
    """
    if boundary_config_path is None:
        boundary_config_path = package_root / "config" / "package_boundary.json"

    with open(boundary_config_path, encoding="utf-8") as fh:
        boundary_config: dict[str, Any] = json.load(fh)

    report = AuditReport(
        project_root=str(project_root),
        package_root=str(package_root),
    )

    sections_cfg: dict[str, Any] = boundary_config.get("sections", {})
    for section_name, section_cfg in sections_cfg.items():
        if section_name.startswith("_"):
            continue
        live_dir = project_root / section_cfg["live_dir"]
        template_dir = project_root / section_cfg["template_dir"]
        items_map: dict[str, str] = section_cfg.get("items", {})

        section_report = _audit_section(section_name, live_dir, template_dir, items_map)
        report.sections.append(section_report)
        report.total_missing += section_report.missing_count

    return report


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_markdown(audit: AuditReport) -> str:
    """Render an AuditReport as a human-readable Markdown string.

    Args:
        audit: Populated AuditReport from run_audit().

    Returns:
        Multi-line Markdown string with one table per section.
    """
    lines: list[str] = [
        "# Package Audit Report",
        "",
        f"**Project root**: `{audit.project_root}`",
        f"**Package root**: `{audit.package_root}`",
        f"**Total portable files missing from package**: {audit.total_missing}",
        "",
    ]

    if audit.total_missing == 0:
        lines.append(
            "> No package gap detected — all portable artifacts are in the package."
        )
        lines.append("")

    for section in audit.sections:
        lines.append(f"## {section.name}")
        lines.append("")
        lines.append(f"- Live: `{section.live_dir}`")
        lines.append(f"- Template: `{section.template_dir}`")
        lines.append(f"- Missing from package: **{section.missing_count}**")
        lines.append("")

        if not section.items:
            lines.append("_No files found in live directory._")
            lines.append("")
            continue

        lines.append("| File | Classification | In Template | Action |")
        lines.append("|------|----------------|-------------|--------|")
        for item in section.items:
            in_tmpl = "yes" if item.in_template else "no"
            lines.append(
                f"| `{item.filename}` | {item.classification} "
                f"| {in_tmpl} | {item.action} |"
            )
        lines.append("")

    return "\n".join(lines)


def format_json(audit: AuditReport) -> str:
    """Render an AuditReport as compact JSON suitable for machine consumption.

    Args:
        audit: Populated AuditReport from run_audit().

    Returns:
        Pretty-printed JSON string (2-space indent).
    """
    return json.dumps(asdict(audit), indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the package_audit CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="package_audit",
        description=(
            "Audit the gap between leafcutter package templates "
            "and the live project files. Prints a Markdown report by default."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=(
            "Absolute path to the consumer project root. Defaults to the "
            "parent-parent of this script (assumes the script lives in "
            "leafcutter/scripts/)."
        ),
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        default=None,
        help=(
            "Absolute path to the leafcutter package root. "
            "Defaults to the parent of this script's directory."
        ),
    )
    parser.add_argument(
        "--boundary-config",
        type=Path,
        default=None,
        help=(
            "Path to package_boundary.json. Defaults to "
            "<package_root>/config/package_boundary.json."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output raw JSON instead of Markdown (for machine consumption).",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Also write a JSON sidecar to this path alongside the Markdown output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for package_audit.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Exit code: 0 when audit passes (no missing portable files) or when
        running in report-only mode; 1 on unexpected errors.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    package_root = args.package_root or script_dir.parent
    project_root = args.project_root or package_root.parent

    try:
        audit = run_audit(
            project_root=project_root,
            package_root=package_root,
            boundary_config_path=args.boundary_config,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Could not parse boundary config: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(format_json(audit))
    else:
        print(format_markdown(audit))

    if args.json_out:
        args.json_out.write_text(format_json(audit), encoding="utf-8")
        print(f"\n[JSON sidecar written to {args.json_out}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 12:00 [epic-supervisor/T01]: Created to formalise the (#EPIC-LeafcutterMVP/01)
#   gap analysis between leafcutter templates and live project
#   files. Boundary classification externalised to package_boundary.json
#   so reclassification requires no script edits. Supports --json for
#   machine consumption by the package-audit skill (T08) and --json-out
#   for CI sidecar generation.
# ====================================================================
