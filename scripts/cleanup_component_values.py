#!/usr/bin/env python3
"""
cleanup_component_values.py — Normalise stray `components` LIST values to the
canonical docs/components.json registry across every surface.

After the taxonomy unification (see project component-taxonomy work / KM-KGS-100e),
the graph reads the `components` LIST field and validates it against
docs/components.json (underscore ids). Two kinds of stray value can still appear
— reintroduced by concurrent merges of pre-migration branches, or authored by
hand:

  1. Legacy kebab ids (e.g. ``build-orchestration``) — handled by the canonical
     ``MIGRATION_MAP`` imported from ``migrate_component_vocab``.
  2. Free-form / near-miss values (e.g. ``commit-guardian``, ``pre_commit_hooks``,
     ``onboard``, ``feedback``) — handled by ``NEAR_MISS_MAP`` below.

Genuinely ambiguous values (``AMBIGUOUS``) are REPORTED for human decision and
left unchanged — the script never guesses. Any other out-of-registry value is
also reported, never rewritten.

Scope: the ``components`` LIST field only, on ACs (docs/acceptance-criteria/**/*.yaml),
tickets (tickets/**/*.md frontmatter) and docs (docs/**/*.md frontmatter). The
scalar ``component`` field is left untouched — it is the AC-store namespace/prefix
key (index.yaml, kebab), a separate axis.

Idempotent. Preserves file formatting (targeted line rewrite, no YAML round-trip).

Usage:
    python3 scripts/cleanup_component_values.py [--dry-run] [--repo-root <path>]

Exit codes:
    0 - success (including when values were reported for review)
    1 - a real error occurred (unreadable registry, write failure)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

# Reuse the canonical kebab -> underscore map so this tool also finishes any
# legacy-id migration left behind by a concurrent merge.
sys.path.insert(0, str(_SCRIPT_DIR))
from migrate_component_vocab import MIGRATION_MAP  # noqa: E402

# High-confidence free-form / near-miss values -> canonical components.json id.
# Only separator/spelling variants and unambiguous synonyms belong here.
NEAR_MISS_MAP: dict[str, str] = {
    # Naive hyphen->underscore conversions whose underscore form is NOT a real
    # components.json id. NOTE: knowledge_management is a VALID id (PR #274 split
    # it from knowledge_system), so it is deliberately NOT remapped here.
    "guardrail_engine": "commit_guardian",
    "ticket_creation": "ticket_creation_pipeline",
    # Separator / spelling variants and unambiguous synonyms.
    "commit-guardian": "commit_guardian",
    "pre_commit_hooks": "precommit_hooks",
    "pre-commit-hooks": "precommit_hooks",
    "precommit-hooks": "precommit_hooks",
    "ac_traceability_store": "ac_store",
    "ac-traceability-store": "ac_store",
    "release": "release_manager",
    "feedback": "feedback_collector",
    "onboard": "onboarding",
    "docs": "documentation_system",
    "architecture_docs": "documentation_system",
    "architecture-docs": "documentation_system",
}

# Genuinely ambiguous values: reported for a human to map, never auto-rewritten.
AMBIGUOUS: frozenset[str] = frozenset({
    "agents",            # agent_registry? supervisor_system?
    "hooks",             # commit_guardian? precommit_hooks?
    "skills",            # skills_system? skill_registry?
    "registries",        # agent_registry? skill_registry?
    "build_system",      # build_pipeline? build_orchestration?
    "workflow_deployment",  # build_pipeline? build_orchestration?
    "agent-infrastructure",  # agent_registry? injection_builder?
    "phase-agents",      # supervisor_system? agent_registry?
})

# Combined auto-apply map (legacy kebab + free-form near-miss).
REMAP: dict[str, str] = {**MIGRATION_MAP, **NEAR_MISS_MAP}

_FRONTMATTER_RE = re.compile(r"^(---\n)(.*?)(\n---)", re.DOTALL)


def load_registry_ids(repo_root: Path) -> set[str]:
    """Load the canonical component ids (keys of docs/components.json)."""
    path = repo_root / "docs" / "components.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read component registry {path}: {exc}", file=sys.stderr)
        return set()
    components = data.get("components") if isinstance(data, dict) else None
    if not isinstance(components, dict):
        return set()
    return {str(k).strip() for k in components if isinstance(k, str) and k.strip()}


def _rewrite_components_block(
    text: str,
    registry: set[str],
    reviews: Counter,
    rel: str,
) -> tuple[str, int]:
    """Rewrite in-registry-invalid `components:` list entries in a YAML/frontmatter block.

    Operates line-wise on a `components:` block of the form::

        components:
          - value
          - value

    Returns (new_text, num_values_changed). Values in AMBIGUOUS or otherwise
    unmapped are recorded in ``reviews`` and left unchanged. Duplicates created
    by a remap collapse to a single entry.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    changed = 0
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # Detect a top-level (or frontmatter-level) `components:` key with a
        # block list beneath it. Match the key at its own indent.
        m = re.match(r"^(\s*)components:\s*$", line.rstrip("\n"))
        if not m:
            out.append(line)
            i += 1
            continue

        key_indent = m.group(1)
        out.append(line)
        i += 1
        seen_targets: set[str] = set()
        # Consume the list items (deeper indent, starting with '-').
        while i < n:
            item = lines[i]
            im = re.match(r"^(\s*)-\s+(.+?)\s*$", item.rstrip("\n"))
            # Block-sequence items may sit at the SAME indent as the key
            # (PyYAML's column-0 style, common in tickets) or deeper (2-space
            # style, common in ACs). Only a LESS-indented line, or a non-item
            # line (e.g. the next `key:`), ends this block.
            if not im or len(im.group(1)) < len(key_indent):
                break
            item_indent = im.group(1)
            raw_val = im.group(2).strip().strip('"').strip("'")
            i += 1

            if raw_val in registry:
                target = raw_val
            elif raw_val in AMBIGUOUS:
                reviews[f"{raw_val}\tAMBIGUOUS (map by hand)"] += 1
                target = raw_val  # unchanged
            elif raw_val in REMAP:
                target = REMAP[raw_val]
                if target != raw_val:
                    changed += 1
            else:
                reviews[f"{raw_val}\tUNKNOWN (no mapping)"] += 1
                target = raw_val  # unchanged

            if target in seen_targets:
                continue  # dedup collapse after remap
            seen_targets.add(target)
            out.append(f"{item_indent}- {target}\n")
        # continue outer loop without consuming the current (non-item) line
    return "".join(out), changed


def _process_yaml_file(path: Path, registry: set[str], reviews: Counter, rel: str,
                       dry_run: bool) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: cannot read {rel}: {exc}", file=sys.stderr)
        return 0
    new_text, changed = _rewrite_components_block(text, registry, reviews, rel)
    if changed and not dry_run:
        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: cannot write {rel}: {exc}", file=sys.stderr)
            raise
    if changed:
        print(f"{'[dry-run] would fix' if dry_run else 'fixed'} {changed} value(s) in {rel}")
    return changed


def _process_md_file(path: Path, registry: set[str], reviews: Counter, rel: str,
                     dry_run: bool) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: cannot read {rel}: {exc}", file=sys.stderr)
        return 0
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return 0
    block = fm.group(2)
    new_block, changed = _rewrite_components_block(block, registry, reviews, rel)
    if changed:
        new_text = text[: fm.start(2)] + new_block + text[fm.end(2):]
        if not dry_run:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as exc:
                print(f"ERROR: cannot write {rel}: {exc}", file=sys.stderr)
                raise
        print(f"{'[dry-run] would fix' if dry_run else 'fixed'} {changed} value(s) in {rel}")
    return changed


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success (even with reviews), 1 on hard error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing files.")
    parser.add_argument("--repo-root", default=str(_REPO_ROOT),
                        help=f"Repo root. Default: {_REPO_ROOT}")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    registry = load_registry_ids(repo_root)
    if not registry:
        print("ERROR: empty component registry; refusing to run.", file=sys.stderr)
        return 1

    reviews: Counter = Counter()
    total = 0

    ac_dir = repo_root / "docs" / "acceptance-criteria"
    for p in sorted(ac_dir.rglob("*.yaml")):
        if p.name == "index.yaml":
            continue
        total += _process_yaml_file(p, registry, reviews, str(p.relative_to(repo_root)),
                                    args.dry_run)

    for base in ("tickets", "docs"):
        for p in sorted((repo_root / base).rglob("*.md")):
            total += _process_md_file(p, registry, reviews, str(p.relative_to(repo_root)),
                                      args.dry_run)

    mode = "dry-run" if args.dry_run else "actual"
    print(f"\nComponent-value cleanup complete ({mode}):")
    print(f"  Values {'would be ' if args.dry_run else ''}normalised: {total}")
    if reviews:
        print("\n  Values left for HUMAN REVIEW (not changed):")
        for key, count in sorted(reviews.items(), key=lambda kv: (-kv[1], kv[0])):
            value, reason = key.split("\t", 1)
            print(f"    {count:4}  {value:24} {reason}")
    else:
        print("  No values needed human review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
