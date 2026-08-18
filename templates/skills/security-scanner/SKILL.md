---
name: security-scanner
description: |
  Secrets and vulnerability scanning skill for the leafcutter package.
  Provides pre-commit secrets detection (staged files only) and a full-repo
  /security-audit workflow covering secrets, dependency CVEs, and Docker config.
  Use when: running the pre-commit hook check_secrets.py; when the user invokes
  /security-audit; when an architect-review agent needs a security posture check.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# Security Scanner Skill

## Overview

The security scanner has two operational modes:

1. **Pre-commit mode** (`check_secrets.py`): fast scan of staged files only; blocks commit on findings.
2. **Full-audit mode** (`/security-audit`): scans entire repo — secrets, dependency CVEs, Docker config.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/scan_secrets.py` | Regex + Shannon-entropy secrets detection |
| `scripts/scan_dependencies.py` | Parse `poetry.lock`, check for known CVEs via `pip-audit` |
| `scripts/scan_docker.py` | Audit `docker-compose.yml` for security misconfigurations |
| `scripts/generate_security_report.py` | Aggregate all scan outputs into a markdown report |

## CLI Usage

```bash
# Scan a list of files for secrets (pre-commit mode)
python .claude/skills/security-scanner/scripts/scan_secrets.py file1.py file2.env

# Full audit (all modes)
python .claude/skills/security-scanner/scripts/generate_security_report.py --output report.md

# Scan dependencies only
python .claude/skills/security-scanner/scripts/scan_dependencies.py

# Scan Docker config only
python .claude/skills/security-scanner/scripts/scan_docker.py docker-compose.yml
```

## Allowlist

To suppress a known false positive, add an entry to `.security-allowlist` in the project root:

```
# .security-allowlist
# Format: <rule_id>:<file_path>:<line_number>  OR  <rule_id>:*  (suppress globally)
ENTROPY_HIGH:tests/fixtures/test_data.py:42
API_KEY_GENERIC:docs/external-api.md:*
```

### How path matching decides suppression

`_is_suppressed` in `scripts/scan_secrets.py` compares an allowlist entry's `file_path`
against a finding's path by POSIX path *segments*, not by string prefix/suffix or
basename alone. A finding is suppressed only when one of three modes holds:

- **wildcard** — the allowlist path is the literal `*` (suppresses any finding for
  that rule, regardless of path).
- **exact-path** — the allowlist path segments equal the finding path segments
  exactly.
- **path-suffix** — the allowlist path segments are a true segment-by-segment
  suffix of the finding path segments. A bare filename (no path separator, e.g.
  `secrets.py`) is a 1-segment allowlist path, so it suppresses findings with that
  basename at *any* depth — this is intentional. A multi-segment, path-qualified
  entry (e.g. `config/secrets.py`) only suppresses a finding whose trailing path
  segments match all of those segments in order (e.g. it suppresses
  `src/config/secrets.py` but not `other/secrets.py`).

**Basename equality alone is never sufficient to suppress a finding when the
allowlist entry contains a path separator.** Two exploit shapes this guards
against:

- A path-qualified entry for `src/foo.py` must **not** suppress a same-basename
  finding in a different, equal-length directory such as `deploy/foo.py`
  (basename-collision shadowing).
- A longer allowlist path (e.g. `src/config/foo.py`) must **not** suppress a
  shorter finding path (e.g. root-level `foo.py`) — there are not enough finding
  path segments for a suffix match to be possible.

See `unit_tests/commit_guardian/test_scan_secrets_suppression.py` for the test
coverage of all six suppression/non-suppression cases, and
[ADR-001](../../../docs/architecture/adrs/ADR-001-self-hosting-boundary.md) for why
`scripts/scan_secrets.py` under `templates/` is the canonical copy to edit (fixes here
propagate to the deployed copies via `build.py`; the [commit-guardian component
doc](../../../docs/architecture/components/commit-guardian.md) covers how this scanner
fits into the broader pre-commit hook pipeline).

## Secrets Detection Rules

The scanner applies these rules in order:

| Rule ID | Pattern / Method | Description |
|---------|-----------------|-------------|
| `ENV_FILE` | filename match `*.env`, `.env.*` | Staged .env files |
| `EXCHANGE_API_KEY` | `[A-Za-z0-9]{36,}` near `api_key`, `apikey`, `api_secret` | Third-party API key pattern |
| `GENERIC_SECRET` | keyword proximity: `secret`, `password`, `token`, `passwd` | Generic credential keyword |
| `AWS_KEY` | `AKIA[0-9A-Z]{16}` | AWS access key pattern |
| `PRIVATE_KEY` | `-----BEGIN (RSA\|EC\|OPENSSH) PRIVATE KEY-----` | Private key header |
| `ENTROPY_HIGH` | Shannon entropy > 4.5 on string tokens > 20 chars | High-entropy string heuristic |

## Integration with Pre-Commit

`check_secrets.py` (in `scripts/commit_guardian/`) is the thin pre-commit wrapper.
It calls `scan_secrets.py` on staged files only and returns exit code 1 on findings.

The hook is registered in `commit_guardian.json` under `"secrets"`.

## False Positive Guidance

Common false positives:
- Base64-encoded test fixtures (entropy trigger) → add to `.security-allowlist`
- Documented example API key patterns in docs → add file-level allowlist entry
- Hash values or UUIDs → entropy threshold is 4.5; genuine keys typically > 4.8

## Event Schema (Telemetry)

Each scan emits a `security_scan` event via `emit_event.py`:

```json
{
  "agent_name": "security-scanner",
  "event_type": "agent_signoff",
  "metadata": {
    "scan_mode": "pre-commit|full-audit",
    "findings_count": 0,
    "suppressed_count": 0
  }
}
```
