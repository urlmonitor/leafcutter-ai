# Security Scanner Scripts

## Purpose

Scripts for the security-scanner skill. Provides secrets detection (regex + entropy),
dependency CVE scanning, Docker configuration auditing, and a consolidated report generator.

## Key Files

| File | Purpose |
|------|---------|
| `scan_secrets.py` | Regex + Shannon-entropy secrets detection for arbitrary file lists |
| `scan_dependencies.py` | Parse `poetry.lock` / `pyproject.toml`, check CVEs via `pip-audit` |
| `scan_docker.py` | Audit `docker-compose.yml` for privileged containers, host network, exposed ports |
| `generate_security_report.py` | Aggregate all three scanners into a markdown report |

## Critical Context

- **scan_secrets.py** is the hot path for pre-commit — keep it fast (regex + entropy only, no network)
- **scan_dependencies.py** calls `pip-audit` if available; falls back gracefully if not installed
- **scan_docker.py** requires PyYAML; falls back with a warning if unavailable
- **generate_security_report.py** walks the entire project tree — not suitable for pre-commit hot path
- The `.security-allowlist` file (project root) suppresses false positives per rule/file/line

## Maintenance

- To add a new secrets rule: add `(RULE_ID, re.compile(pattern))` to `_RULES` in `scan_secrets.py`
- To change the entropy threshold: edit `_ENTROPY_THRESHOLD` in `scan_secrets.py`
- Unit tests live in `unit_tests/portable_dev_workflow/test_security_scanner.py`
