"""
MODULE: scan_docker.py
GOAL: Audit docker-compose.yml files for security misconfigurations.
BUSINESS CONTEXT: Docker containers may have direct access to sensitive
    infrastructure, databases, and external APIs. Privileged containers or host
    network mode can be exploited to escalate from container compromise
    to full host compromise.
ARCHITECTURE: Standalone script. Accepts docker-compose file paths as
    CLI args. Parses YAML, checks each service for known risk patterns.
    Returns exit code 0 (clean) or 1 (findings). Does NOT require
    Docker daemon to be running.

# DECISION HISTORY
# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.
#   Pure YAML parse approach chosen to avoid Docker daemon dependency.
#   Focused on the three highest-risk patterns: privileged, host network,
#   and exposed 0.0.0.0 ports.
# - 2026-05-18 12:00 [EPIC-PortableInstallHardening/T01]: Genericised BUSINESS CONTEXT docstring for leafcutter promotion. (#EPIC-PortableInstallHardening/T01)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, NamedTuple

try:
    import yaml as _yaml  # type: ignore[import]
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


class DockerFinding(NamedTuple):
    """A single Docker security finding."""

    rule_id: str
    service: str
    detail: str


def _parse_compose(path: Path) -> dict[str, Any]:
    """Parse a docker-compose YAML file.

    Args:
        path: Path to the docker-compose file.

    Returns:
        Parsed YAML as a dict, or empty dict on error.
    """
    if not _HAS_YAML:
        return {}
    try:
        data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _audit_service(name: str, config: dict[str, Any]) -> list[DockerFinding]:
    """Check a single docker-compose service for security issues.

    Args:
        name: Service name.
        config: Service configuration dict.

    Returns:
        List of DockerFinding objects for this service.
    """
    findings: list[DockerFinding] = []

    # Rule: PRIVILEGED — privileged: true
    if config.get("privileged") is True:
        findings.append(DockerFinding(
            "PRIVILEGED", name,
            "Service runs with privileged: true — container can access host devices"
        ))

    # Rule: HOST_NETWORK — network_mode: host
    if config.get("network_mode") == "host":
        findings.append(DockerFinding(
            "HOST_NETWORK", name,
            "Service uses host network mode — bypasses Docker network isolation"
        ))

    # Rule: EXPOSED_PORT — port bound to 0.0.0.0 (all interfaces)
    for port_spec in config.get("ports", []):
        spec = str(port_spec)
        if spec.startswith("0.0.0.0:") or (
            ":" in spec and not spec.startswith("127.") and not spec.startswith("::1")
        ):
            findings.append(DockerFinding(
                "EXPOSED_PORT", name,
                f"Port exposed on all interfaces: {spec}"
            ))

    # Rule: CAP_ADD — added Linux capabilities
    cap_add = config.get("cap_add", [])
    dangerous_caps = {"SYS_ADMIN", "NET_ADMIN", "SYS_PTRACE", "ALL"}
    for cap in cap_add:
        if str(cap).upper() in dangerous_caps:
            findings.append(DockerFinding(
                "DANGEROUS_CAP", name,
                f"Dangerous capability added: {cap}"
            ))

    return findings


def scan_docker_compose(compose_path: Path) -> list[DockerFinding]:
    """Audit a docker-compose file for security misconfigurations.

    Args:
        compose_path: Path to the docker-compose.yml file.

    Returns:
        List of DockerFinding objects.
    """
    if not _HAS_YAML:
        return [DockerFinding(
            "YAML_MISSING", "(scanner)",
            "PyYAML is not installed — Docker scan skipped. Install: pip install pyyaml"
        )]

    data = _parse_compose(compose_path)
    services = data.get("services", {}) or {}
    findings: list[DockerFinding] = []
    for service_name, service_config in services.items():
        if isinstance(service_config, dict):
            findings.extend(_audit_service(service_name, service_config))
    return findings


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 = clean, 1 = findings found.
    """
    if len(sys.argv) < 2:
        print("Usage: scan_docker.py <docker-compose.yml> [...]")
        return 1

    findings: list[DockerFinding] = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"File not found: {path}")
            continue
        findings.extend(scan_docker_compose(path))

    if not findings:
        print("Docker scan: clean")
        return 0

    for f in findings:
        print(f"[{f.rule_id}] {f.service}: {f.detail}")
    print(f"\n{len(findings)} Docker security issue(s) found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
