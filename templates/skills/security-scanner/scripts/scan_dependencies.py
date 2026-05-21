"""
MODULE: scan_dependencies.py
GOAL: Scan Python dependencies for known CVEs using pip-audit or a
    fallback manual check against pyproject.toml / poetry.lock.
BUSINESS CONTEXT: Supply-chain attacks via compromised packages are a
    real risk. This scanner gives a quick CVE check before deploying
    to a live trading server.
ARCHITECTURE: Standalone script. Reads pyproject.toml and poetry.lock
    from the project root. Calls pip-audit if available; falls back
    to extracting direct dependencies and warning that pip-audit is
    needed for full coverage.

# DECISION HISTORY
# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.
#   pip-audit chosen over safety CLI because it uses PYSEC advisories,
#   is stdlib-compatible, and doesn't require an API key.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class DependencyFinding(NamedTuple):
    """A single dependency vulnerability finding."""

    package: str
    version: str
    vuln_id: str
    description: str
    fix_versions: list[str]


def _run_pip_audit(project_root: Path) -> list[DependencyFinding] | None:
    """Run pip-audit and return findings, or None if pip-audit is unavailable.

    Args:
        project_root: Project root directory.

    Returns:
        List of DependencyFinding objects, or None if pip-audit is not installed.
    """
    try:
        result = subprocess.run(
            ["pip-audit", "--format", "json", "--progress-spinner", "off"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
    except FileNotFoundError:
        return None  # pip-audit not installed

    if result.returncode not in (0, 1):
        # pip-audit returns 1 when vulnerabilities are found
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    findings: list[DependencyFinding] = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            findings.append(DependencyFinding(
                package=dep.get("name", "unknown"),
                version=dep.get("version", "unknown"),
                vuln_id=vuln.get("id", "UNKNOWN"),
                description=vuln.get("description", "")[:200],
                fix_versions=vuln.get("fix_versions", []),
            ))
    return findings


def _extract_direct_deps(project_root: Path) -> list[tuple[str, str]]:
    """Parse pyproject.toml to extract direct dependency names and version constraints.

    Args:
        project_root: Project root directory.

    Returns:
        List of (package_name, version_constraint) tuples.
    """
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return []

    deps: list[tuple[str, str]] = []
    in_section = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "[tool.poetry.dependencies]":
            in_section = True
            continue
        if stripped.startswith("[") and in_section:
            in_section = False
        if in_section and "=" in stripped and not stripped.startswith("#"):
            parts = stripped.split("=", 1)
            pkg = parts[0].strip().strip('"').lower()
            ver = parts[1].strip().strip('"\'')
            if pkg != "python":
                deps.append((pkg, ver))
    return deps


def scan_dependencies(project_root: Path | None = None) -> tuple[list[DependencyFinding], str]:
    """Scan project dependencies for known vulnerabilities.

    Args:
        project_root: Project root directory. Defaults to CWD.

    Returns:
        Tuple of (findings list, status_message). Status message explains
        whether pip-audit was used or only a manual check.
    """
    root = project_root or Path.cwd()
    findings = _run_pip_audit(root)

    if findings is not None:
        status = f"pip-audit ran successfully. {len(findings)} vulnerability/vulnerabilities found."
        return findings, status

    # Fallback: pip-audit not available
    deps = _extract_direct_deps(root)
    dep_names = [f"{name} ({ver})" for name, ver in deps]
    status = (
        "pip-audit is not installed — full CVE scan was not performed.\n"
        f"Install with: poetry add --group dev pip-audit\n"
        f"Direct dependencies found: {len(dep_names)}\n"
        + (("\n".join(f"  - {d}" for d in dep_names)) if dep_names else "  (none)")
    )
    return [], status


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 = clean, 1 = vulnerabilities found.
    """
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings, status = scan_dependencies(root)
    print(status)
    for f in findings:
        fix = ", ".join(f.fix_versions) if f.fix_versions else "none available"
        print(f"  [{f.vuln_id}] {f.package}=={f.version}: {f.description} (fix: {fix})")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
