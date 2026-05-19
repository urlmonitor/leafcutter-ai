"""
MODULE: generate_security_report.py
GOAL: Aggregate all security scan outputs into a structured markdown report.
BUSINESS CONTEXT: Security audits must produce a single artifact that can
    be reviewed before a production deployment or shared in an incident
    post-mortem. This script drives all three scanners and assembles the
    consolidated view.
ARCHITECTURE: Standalone script. Walks the project root, runs scan_secrets
    on all non-.git files, scan_dependencies for CVEs, and scan_docker on
    all docker-compose*.yml files. Outputs markdown to stdout or --output file.

# DECISION HISTORY
# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.
#   Report is markdown (not JSON) because the /security-audit workflow
#   renders it directly to the user. Machine-parseable summary at the top.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent

# Add parent dirs to path so we can import sibling scripts
sys.path.insert(0, str(_SCRIPT_DIR))

from scan_secrets import scan_files  # noqa: E402
from scan_dependencies import scan_dependencies  # noqa: E402
from scan_docker import scan_docker_compose  # noqa: E402


_EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}


def _collect_files(root: Path) -> list[Path]:
    """Collect all source files for secrets scanning.

    Args:
        root: Project root directory.

    Returns:
        List of file paths to scan (excludes .git, .venv, etc.).
    """
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file():
            parts = set(path.parts)
            if not parts & _EXCLUDED_DIRS:
                files.append(path)
    return files


def _collect_compose_files(root: Path) -> list[Path]:
    """Find docker-compose files in the project root.

    Args:
        root: Project root directory.

    Returns:
        List of docker-compose YAML file paths.
    """
    return [
        p for p in root.glob("docker-compose*.yml")
        if p.is_file()
    ]


def generate_report(project_root: Path) -> str:
    """Generate a full security audit report.

    Args:
        project_root: Project root directory to scan.

    Returns:
        Markdown-formatted security report string.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Run scanners
    source_files = _collect_files(project_root)
    secret_findings = scan_files(source_files, project_root)
    dep_findings, dep_status = scan_dependencies(project_root)
    compose_files = _collect_compose_files(project_root)
    docker_findings = []
    for cf in compose_files:
        docker_findings.extend(scan_docker_compose(cf))

    # Determine overall status
    total = len(secret_findings) + len(dep_findings) + len(docker_findings)
    overall = "PASS" if total == 0 else "FAIL"

    lines: list[str] = [
        f"# Security Audit Report",
        f"",
        f"**Generated:** {timestamp}  ",
        f"**Project root:** `{project_root}`  ",
        f"**Overall status:** {overall}",
        f"**Total findings:** {total}",
        f"",
    ]

    # Secrets section
    lines += [
        "## 1. Secrets Scan",
        f"",
        f"Files scanned: {len(source_files)}  ",
        f"Findings: {len(secret_findings)}",
        f"",
    ]
    if secret_findings:
        lines.append("| Rule | File | Line | Excerpt |")
        lines.append("|------|------|------|---------|")
        for f in secret_findings:
            ln = str(f.line_no) if f.line_no else "-"
            excerpt = f.excerpt.replace("|", "\\|")[:80]
            lines.append(f"| `{f.rule_id}` | `{f.file_path}` | {ln} | `{excerpt}` |")
    else:
        lines.append("No secrets detected.")
    lines.append("")

    # Dependencies section
    lines += [
        "## 2. Dependency Vulnerability Scan",
        f"",
        dep_status,
        f"",
    ]
    if dep_findings:
        lines.append("| CVE ID | Package | Version | Fix |")
        lines.append("|--------|---------|---------|-----|")
        for f in dep_findings:
            fix = ", ".join(f.fix_versions) if f.fix_versions else "none"
            lines.append(f"| `{f.vuln_id}` | {f.package} | {f.version} | {fix} |")
    lines.append("")

    # Docker section
    lines += [
        "## 3. Docker Configuration Audit",
        f"",
        f"Compose files scanned: {len(compose_files)}  ",
        f"Findings: {len(docker_findings)}",
        f"",
    ]
    if docker_findings:
        lines.append("| Rule | Service | Detail |")
        lines.append("|------|---------|--------|")
        for f in docker_findings:
            lines.append(f"| `{f.rule_id}` | {f.service} | {f.detail} |")
    else:
        lines.append("No Docker security issues detected.")
    lines.append("")

    # Remediation summary
    if total > 0:
        lines += [
            "## 4. Remediation",
            "",
            "1. For secrets findings: remove the credential from source, rotate the key, "
            "add to `.gitignore` or `.security-allowlist` if it is a false positive.",
            "2. For dependency CVEs: run `poetry update <package>` to get the patched version.",
            "3. For Docker findings: apply principle of least privilege — remove `privileged: true`, "
            "bind ports to `127.0.0.1` instead of `0.0.0.0`.",
            "",
        ]

    return "\n".join(lines)


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 = no findings, 1 = findings found.
    """
    parser = argparse.ArgumentParser(description="Generate a full security audit report.")
    parser.add_argument("--root", default=".", help="Project root directory (default: CWD)")
    parser.add_argument("--output", default=None, help="Write report to file instead of stdout")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = generate_report(root)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)

    # Return exit code based on findings
    has_findings = "Overall status:** FAIL" in report
    return 1 if has_findings else 0


if __name__ == "__main__":
    sys.exit(main())
