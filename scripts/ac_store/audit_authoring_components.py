#!/usr/bin/env python3
"""
MODULE: audit_authoring_components
GOAL: Store-wide audit that identifies acceptance criteria authored by the
    product-owner, business-analyst, or it-po agents (and their -v2/-v3
    historical variants) that lack a non-empty, registry-valid `components`
    membership field.
BUSINESS CONTEXT: KM-KGS-100e-4. For the knowledge graph's component_membership
    edges to be complete at emission time, every AC produced by the three authoring
    agents must carry a `components` list. This audit discovers the backlog of
    violations so the team can prioritise the remediation sweep before the
    commit-time gate (KM-KGS-100e-1) is activated. It is an ADVISORY audit —
    it reports violations and exits non-zero when any are found, but does not
    block commits.
ARCHITECTURE: Scans all .yaml files under the AC store root
    (docs/acceptance-criteria/ by default). Loads the component registry from
    docs/acceptance-criteria/index.yaml using load_registry_ids() from
    _ac_components.py (the shared predicate module). Filters records by
    origin_agent membership in _AUTHORING_AGENTS, validates each with
    components_field_errors(), and prints a structured text or JSON report.

    origin_agent matching: Case-insensitive match against the canonical names
    and historical -v2/-v3 variants. Does NOT validate origin_agent against the
    live agent registry (see docs/reference/ac-schema.md: origin_agent is a
    free-form provenance string that intentionally accepts historical names).

Exit codes:
    0 — no violations found
    1 — one or more violations found (advisory, non-blocking)
    2 — internal error (fail-open: printed to stderr, does not block commits)

DECISION HISTORY:
  - 2026-07-08 [python-coder/KM-KGS-100e-4]: Initial implementation.
    Scope: advisory audit surface (not a commit-time gate). Reuses the
    components_field_errors predicate from _ac_components.py to ensure
    consistency with the AC schema validator and KM-KGS-100e-1 gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

# _ac_components lives alongside this script in scripts/ac_store/.
# When invoked directly (python scripts/ac_store/audit_authoring_components.py),
# the script directory is sys.path[0] so the import resolves automatically.
# Tests must insert scripts/ac_store/ into sys.path before importing this module.
from _ac_components import components_field_errors, load_registry_ids  # noqa: E402


# ---------------------------------------------------------------------------
# Authoring agent set (KM-KGS-100e-4)
# ---------------------------------------------------------------------------

#: Canonical authoring agent names plus historical -v2/-v3 variants.
#: Per ac-schema.md, origin_agent is NOT validated against the live registry —
#: historical names remain valid. Matching is case-insensitive.
_AUTHORING_AGENTS: frozenset[str] = frozenset({
    "product-owner",
    "product-owner-v2",
    "product-owner-v3",
    "business-analyst",
    "business-analyst-v2",
    "business-analyst-v3",
    "it-po",
    "it-po-v2",
    "it-po-v3",
})

_AC_STORE_REL: Path = Path("docs") / "acceptance-criteria"


def _repo_root() -> Path:
    """Resolve the repository root from this script's location.

    Returns:
        Absolute path to the repo root directory.
    """
    return Path(__file__).resolve().parent.parent.parent


def _default_ac_root() -> Path:
    """Return the default AC store path.

    Returns:
        Absolute path to docs/acceptance-criteria/ relative to repo root.
    """
    return _repo_root() / _AC_STORE_REL


# ---------------------------------------------------------------------------
# Origin-agent matching
# ---------------------------------------------------------------------------


def _is_authoring_agent(origin_agent: str | None) -> bool:
    """Return True if the AC was produced by one of the three authoring agents.

    Matching is case-insensitive and strips leading/trailing whitespace.
    Does NOT validate against the live agent registry (see ac-schema.md).

    Args:
        origin_agent: The value of the `origin_agent` field, or None.

    Returns:
        True if origin_agent identifies one of the authoring agents.
    """
    if not origin_agent or not isinstance(origin_agent, str):
        return False
    return origin_agent.strip().lower() in _AUTHORING_AGENTS


# ---------------------------------------------------------------------------
# YAML file loading
# ---------------------------------------------------------------------------


def _load_yaml_file(path: Path) -> dict | None:
    """Read and parse a YAML file, returning None on failure.

    Args:
        path: Absolute path to a YAML file.

    Returns:
        Parsed dict on success, None on I/O or parse error.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(
            f"WARNING: cannot read {path}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        print(f"WARNING: YAML parse error in {path}: {exc}", file=sys.stderr)
        return None

    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# AC store scanning
# ---------------------------------------------------------------------------


def scan_store(
    ac_root: Path,
    registry_ids: set[str],
) -> tuple[int, list[dict[str, Any]]]:
    """Scan the AC store and return violation records for authoring-agent ACs.

    Args:
        ac_root: Root path of the AC store (docs/acceptance-criteria/).
        registry_ids: Set of valid component IDs from the registry.

    Returns:
        Tuple of (total_scanned, violations) where total_scanned is the number
        of authoring-agent ACs examined and violations is a list of violation
        dicts with keys: path, ac_id, origin_agent, errors.
    """
    violations: list[dict[str, Any]] = []
    total_scanned = 0

    if not ac_root.is_dir():
        print(
            f"WARNING: AC store root not found: {ac_root}",
            file=sys.stderr,
        )
        return 0, violations

    for yaml_file in sorted(ac_root.rglob("*.yaml")):
        data = _load_yaml_file(yaml_file)
        if data is None:
            continue

        origin_agent = data.get("origin_agent")
        if not _is_authoring_agent(origin_agent):
            continue

        total_scanned += 1
        errors = components_field_errors(data, registry_ids)
        if errors:
            ac_id = str(data.get("id", "")).strip() or str(yaml_file)
            violations.append({
                "path": str(yaml_file),
                "ac_id": ac_id,
                "origin_agent": str(origin_agent),
                "errors": errors,
            })

    return total_scanned, violations


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _print_text_report(violations: list[dict[str, Any]], total_scanned: int) -> None:
    """Print a human-readable text report to stdout.

    Args:
        violations: List of violation dicts from scan_store.
        total_scanned: Total number of authoring-agent ACs scanned.
    """
    if not violations:
        print(
            f"[audit-authoring-components] OK — "
            f"all {total_scanned} authoring-agent ACs carry a valid components list."
        )
        return

    print(
        f"[audit-authoring-components] VIOLATIONS — "
        f"{len(violations)} of {total_scanned} authoring-agent ACs "
        f"lack a valid components list:\n"
    )
    for v in violations:
        print(f"  AC: {v['ac_id']}")
        print(f"    file:   {v['path']}")
        print(f"    author: {v['origin_agent']}")
        for err in v["errors"]:
            print(f"    error:  {err}")
        print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the authoring-components audit.

    Args:
        argv: Command-line argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 = clean, 1 = violations found, 2 = internal error.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Audit AC store for authoring-agent ACs missing a components field."
        )
    )
    parser.add_argument(
        "--ac-root",
        type=Path,
        default=None,
        help="Root directory of the AC store (default: docs/acceptance-criteria/).",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output violations as JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    ac_root = args.ac_root if args.ac_root is not None else _default_ac_root()
    registry_ids = load_registry_ids()
    total_scanned, violations = scan_store(ac_root, registry_ids)

    if args.json_output:
        print(
            json.dumps(
                {
                    "total_scanned": total_scanned,
                    "violation_count": len(violations),
                    "violations": violations,
                },
                indent=2,
            )
        )
    else:
        _print_text_report(violations, total_scanned)

    return 1 if violations else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"[audit-authoring-components] unexpected error: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)
