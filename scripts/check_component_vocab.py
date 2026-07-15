#!/usr/bin/env python3
"""
check_component_vocab.py — CI style guard for the `components` membership field.

Every `components` LIST value on every surface must be a canonical id declared
in docs/components.json (the single component registry — underscore-case). This
guard exists to catch off-registry values (e.g. legacy kebab ids like
``build-orchestration``) that slip in via a MERGE of a pre-migration branch — a
vector the pre-commit transform hook cannot cover, because pre-commit hooks do
not run on merge commits.

Two scopes:
  - Full-tree (default): scan every surface file. Use on push-to-main and as a
    scheduled backstop — guarantees main never carries an off-registry value.
  - Changed-only (--changed BASE_REF): scan only files changed vs BASE_REF
    (git diff BASE_REF...HEAD). Use as the PR gate, so a clean PR is not failed
    for pre-existing drift in the base it didn't introduce — while any PR that
    *adds* drift still has that file in its diff and is caught.

Style enforced:
  - Each value present in a `components` list MUST be a key of docs/components.json.
  - STYLE check, not PRESENCE: a missing/empty `components` field is not a
    violation (presence is a separate, deferred concern).
  - The scalar `component` field is NOT checked — it is the AC-store namespace
    key (docs/acceptance-criteria/index.yaml, kebab), a deliberately separate axis.

Surfaces:
  - ACs:      docs/acceptance-criteria/**/*.yaml   (top-level `components`)
  - tickets:  tickets/**/*.md                      (frontmatter `components`)
  - docs:     docs/**/*.md                         (frontmatter `components`)
  - registries: config/agent_registry.json, config/skill_registry.json,
                docs/roadmap.json                  (per-entry `components`)

Usage:
    python3 scripts/check_component_vocab.py [--repo-root <path>]
    python3 scripts/check_component_vocab.py --changed origin/main   # PR gate

Exit codes:
    0 - all checked `components` values are canonical (or nothing to check)
    1 - one or more off-registry values found (details printed to stderr)
    2 - the registry itself could not be loaded (hard error)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

_AC_PREFIX = "docs/acceptance-criteria/"
_REGISTRY_FILES = (
    "config/agent_registry.json",
    "config/skill_registry.json",
    "docs/roadmap.json",
)


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


def _check_file(repo_root: Path, rel: str, registry: set[str]) -> list[str]:
    """Return off-registry `components` values for one repo-relative file, by type."""
    p = repo_root / rel
    if not p.is_file():
        return []

    if rel.startswith(_AC_PREFIX) and rel.endswith(".yaml") and not rel.endswith("index.yaml"):
        try:
            return _check_yaml_doc(yaml.safe_load(p.read_text(encoding="utf-8")), registry)
        except (OSError, yaml.YAMLError):
            return []

    if rel.endswith(".md") and (rel.startswith("tickets/") or rel.startswith("docs/")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            return []
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return []
        try:
            return _check_yaml_doc(yaml.safe_load(m.group(1)), registry)
        except yaml.YAMLError:
            return []

    if rel in _REGISTRY_FILES:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        bad: list[str] = []
        for entry in _iter_registry_entries(data):
            bad.extend(_bad_values(entry.get("components"), registry))
        return bad

    return []


def _all_surface_files(repo_root: Path) -> list[str]:
    """Every membership-bearing file in the tree, as repo-relative paths."""
    rels: list[str] = []
    ac_dir = repo_root / "docs" / "acceptance-criteria"
    if ac_dir.is_dir():
        rels += [str(p.relative_to(repo_root)) for p in ac_dir.rglob("*.yaml")
                 if p.name != "index.yaml"]
    for base in ("tickets", "docs"):
        base_dir = repo_root / base
        if base_dir.is_dir():
            rels += [str(p.relative_to(repo_root)) for p in base_dir.rglob("*.md")]
    rels += [f for f in _REGISTRY_FILES if (repo_root / f).is_file()]
    return sorted(rels)


def _changed_files(repo_root: Path, base_ref: str) -> list[str] | None:
    """Repo-relative files changed vs base_ref (git diff base_ref...HEAD).

    Returns None if the diff cannot be computed (caller falls back to full scan).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only",
             "--diff-filter=ACMR", f"{base_ref}...HEAD"],
            capture_output=True, text=True,
        )
    except OSError as exc:
        print(f"WARNING: could not run git diff vs {base_ref}: {exc}", file=sys.stderr)
        return None
    if result.returncode != 0:
        print(f"WARNING: git diff vs {base_ref} failed: {result.stderr.strip()}",
              file=sys.stderr)
        return None
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


def scan(repo_root: Path, registry: set[str],
         files: list[str] | None = None) -> list[tuple[str, str]]:
    """Return (repo-relative-path, off-registry-value) violations.

    files=None scans the whole tree; otherwise only the given repo-relative files.
    """
    rels = files if files is not None else _all_surface_files(repo_root)
    violations: list[tuple[str, str]] = []
    for rel in rels:
        violations.extend((rel, v) for v in _check_file(repo_root, rel, registry))
    return violations


def main(argv: list[str] | None = None) -> int:
    """Entry point. 0 = clean, 1 = violations, 2 = registry load failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT),
                        help=f"Repo root. Default: {_REPO_ROOT}")
    parser.add_argument("--changed", metavar="BASE_REF", default=None,
                        help="Only check files changed vs BASE_REF (git diff "
                             "BASE_REF...HEAD). Use as the PR gate.")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)

    registry = load_registry_ids(repo_root)
    if not registry:
        print("ERROR: empty/unloadable component registry (docs/components.json).",
              file=sys.stderr)
        return 2

    scope = "full tree"
    if args.changed:
        changed = _changed_files(repo_root, args.changed)
        if changed is None:
            print("WARNING: falling back to full-tree scan (could not diff).",
                  file=sys.stderr)
            violations = scan(repo_root, registry)
        else:
            surface = set(_all_surface_files(repo_root))
            files = [f for f in changed if f in surface]
            scope = f"{len(files)} changed surface file(s) vs {args.changed}"
            if not files:
                print(f"OK: no changed component-bearing files vs {args.changed}.")
                return 0
            violations = scan(repo_root, registry, files=files)
    else:
        violations = scan(repo_root, registry)

    if not violations:
        print(f"OK: all `components` values are canonical components.json ids ({scope}).")
        return 0

    from collections import defaultdict
    by_value: dict[str, list[str]] = defaultdict(list)
    for path, value in violations:
        by_value[value].append(path)

    print(
        f"FAIL: {len(violations)} off-registry `components` value(s) found "
        f"({len(by_value)} distinct; scope: {scope}). Every value must be a key in "
        f"docs/components.json (underscore-case).",
        file=sys.stderr,
    )
    for value in sorted(by_value):
        files_ = by_value[value]
        print(f"\n  '{value}'  ({len(files_)} occurrence(s)):", file=sys.stderr)
        for f in files_[:10]:
            print(f"    - {f}", file=sys.stderr)
        if len(files_) > 10:
            print(f"    ... and {len(files_) - 10} more", file=sys.stderr)
    print(
        "\nFix: run `python scripts/cleanup_component_values.py` to normalise, "
        "or map new values in docs/components.json.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
