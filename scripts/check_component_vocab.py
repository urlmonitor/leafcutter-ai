#!/usr/bin/env python3
"""
check_component_vocab.py — CI style guard for the `components` membership field.

Every `components` LIST value on every surface must be a canonical id declared
in docs/components.json (the single component registry — underscore-case). This
guard exists to catch off-registry values (e.g. legacy kebab ids like
``build-orchestration``) that slip onto ``main`` via a MERGE of a pre-migration
branch — a vector the pre-commit transform hook cannot cover, because pre-commit
hooks do not run on merge commits.

Style enforced:
  - Each value present in a `components` list MUST be a key of docs/components.json.
  - This is a STYLE check, not a PRESENCE check: a missing/empty `components`
    field is NOT a violation here (presence is a separate, deferred concern).
  - The scalar `component` field is NOT checked — it is the AC-store namespace
    key (docs/acceptance-criteria/index.yaml, kebab), a deliberately separate axis.

Surfaces scanned:
  - ACs:      docs/acceptance-criteria/**/*.yaml   (top-level `components`)
  - tickets:  tickets/**/*.md                      (frontmatter `components`)
  - docs:     docs/**/*.md                         (frontmatter `components`)
  - registries: config/agent_registry.json, config/skill_registry.json,
                docs/roadmap.json                  (per-entry `components`)

Usage:
    python3 scripts/check_component_vocab.py [--repo-root <path>]

Exit codes:
    0 - all `components` values are canonical (or none present)
    1 - one or more off-registry values found (details printed to stderr)
    2 - the registry itself could not be loaded (hard error)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def load_registry_ids(repo_root: Path) -> set[str]:
    """Return the canonical component ids (keys of docs/components.json)."""
    path = repo_root / "docs" / "components.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read component registry {path}: {exc}", file=sys.stderr)
        return set()
    comps = data.get("components") if isinstance(data, dict) else None
    if not isinstance(comps, dict):
        return set()
    return {str(k).strip() for k in comps if isinstance(k, str) and k.strip()}


def _bad_values(components: object, registry: set[str]) -> list[str]:
    """Return the off-registry string values in a `components` list (or [])."""
    if not isinstance(components, list):
        return []
    return [
        v for v in components
        if isinstance(v, str) and v.strip() and v not in registry
    ]


def _check_yaml_doc(data: object, registry: set[str]) -> list[str]:
    if isinstance(data, dict):
        return _bad_values(data.get("components"), registry)
    return []


def _iter_registry_entries(data: object):
    """Yield candidate entry dicts from a registry JSON structure."""
    if isinstance(data, dict):
        for key in ("agents", "skills", "phases", "components"):
            section = data.get(key)
            if isinstance(section, list):
                yield from (e for e in section if isinstance(e, dict))
            elif isinstance(section, dict):
                yield from (e for e in section.values() if isinstance(e, dict))
    elif isinstance(data, list):
        yield from (e for e in data if isinstance(e, dict))


def scan(repo_root: Path, registry: set[str]) -> list[tuple[str, str]]:
    """Return a list of (repo-relative-path, off-registry-value) violations."""
    violations: list[tuple[str, str]] = []

    def record(path: Path, bad: list[str]) -> None:
        rel = str(path.relative_to(repo_root))
        violations.extend((rel, v) for v in bad)

    # ACs
    ac_dir = repo_root / "docs" / "acceptance-criteria"
    for p in sorted(ac_dir.rglob("*.yaml")):
        if p.name == "index.yaml":
            continue
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        record(p, _check_yaml_doc(data, registry))

    # tickets + docs (markdown frontmatter)
    for base in ("tickets", "docs"):
        for p in sorted((repo_root / base).rglob("*.md")):
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            m = _FRONTMATTER_RE.match(text)
            if not m:
                continue
            try:
                data = yaml.safe_load(m.group(1))
            except yaml.YAMLError:
                continue
            record(p, _check_yaml_doc(data, registry))

    # registries (JSON, per-entry components)
    for rel in ("config/agent_registry.json", "config/skill_registry.json",
                "docs/roadmap.json"):
        p = repo_root / rel
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for entry in _iter_registry_entries(data):
            record(p, _bad_values(entry.get("components"), registry))

    return violations


def main(argv: list[str] | None = None) -> int:
    """Entry point. 0 = clean, 1 = violations, 2 = registry load failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT),
                        help=f"Repo root. Default: {_REPO_ROOT}")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)

    registry = load_registry_ids(repo_root)
    if not registry:
        print("ERROR: empty/unloadable component registry (docs/components.json).",
              file=sys.stderr)
        return 2

    violations = scan(repo_root, registry)
    if not violations:
        print("OK: all `components` values are canonical components.json ids.")
        return 0

    # Group by value for an actionable report.
    from collections import defaultdict
    by_value: dict[str, list[str]] = defaultdict(list)
    for path, value in violations:
        by_value[value].append(path)

    print(
        f"FAIL: {len(violations)} off-registry `components` value(s) found "
        f"({len(by_value)} distinct). Every value must be a key in "
        f"docs/components.json (underscore-case).",
        file=sys.stderr,
    )
    for value in sorted(by_value):
        files = by_value[value]
        print(f"\n  '{value}'  ({len(files)} occurrence(s)):", file=sys.stderr)
        for f in files[:10]:
            print(f"    - {f}", file=sys.stderr)
        if len(files) > 10:
            print(f"    ... and {len(files) - 10} more", file=sys.stderr)
    print(
        "\nFix: run `python scripts/cleanup_component_values.py` to normalise, "
        "or map new values in docs/components.json.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
