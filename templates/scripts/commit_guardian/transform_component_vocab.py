"""
MODULE: leafcutter/scripts/commit_guardian/transform_component_vocab.py
GOAL: Pre-stage transformer that normalises legacy / near-miss `components` LIST
      values to the canonical docs/components.json vocabulary in staged ACs,
      tickets, and docs — BEFORE the component validators run — so kebab ids
      reintroduced by a merge of a pre-migration branch are auto-healed instead
      of silently re-fragmenting the knowledge graph.
BUSINESS CONTEXT: The knowledge graph reads the `components` LIST field and the
      canonical vocabulary is docs/components.json (underscore ids). Merges of
      older branches keep reintroducing kebab values (build-orchestration,
      ac-store, ...). Rather than hard-block those commits (which would break
      in-flight work), this transformer rewrites the mappable stray values on
      the way in. Unmappable values are left untouched for a validator to catch.
ARCHITECTURE: Reads staged (added/modified) files via `git diff --cached`
      (HOOK_TEST_STAGED_FILES seam for tests). For each ticket/doc .md
      (frontmatter block only) and AC .yaml, rewrites in-registry-invalid
      `components` list entries that appear in REMAP, dedupes, re-stages via
      `git add`. Only the `components` LIST is touched; the scalar `component`
      (AC-store namespace key, index.yaml kebab) is left alone. Values already
      valid in components.json (e.g. knowledge_management) are never rewritten.
      Exits 0 always (fail-open transform contract).

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-14 [component-taxonomy-guard]: Initial implementation. Durable guard
  that stops kebab component ids trickling back in via pre-migration merges.
  Mirrors the kebab->underscore map of scripts/migrate_component_vocab.py plus
  the near-miss map of scripts/cleanup_component_values.py. knowledge_management
  is a VALID id (PR #274) and is deliberately absent from REMAP.
====================================================================
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_HOOK_PREFIX = "[transform-component-vocab]"

# Canonical stray-value -> components.json id map. Kept in sync with
# migrate_component_vocab.MIGRATION_MAP + cleanup_component_values.NEAR_MISS_MAP.
# knowledge_management is intentionally NOT here — it is a valid distinct id.
REMAP: dict[str, str] = {
    # legacy kebab -> underscore
    "build-pipeline": "build_pipeline",
    "ac-store": "ac_store",
    "testing-quality": "testing_quality",
    "knowledge-management": "knowledge_management",
    "guardrail-engine": "commit_guardian",
    "ticket-creation": "ticket_creation_pipeline",
    "build-orchestration": "build_orchestration",
    "ux-prototyping": "ux_prototyping",
    "persona-management": "persona_management",
    "stakeholder-delivery": "stakeholder_delivery",
    "ac-driven-dev": "ac_driven_dev",
    # naive underscore that is not the real id
    "guardrail_engine": "commit_guardian",
    "ticket_creation": "ticket_creation_pipeline",
    # separator / synonym near-misses
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


def _load_registry(root: Path) -> set[str]:
    """Load valid component ids from docs/components.json (empty set on error)."""
    try:
        data = json.loads((root / "docs" / "components.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    comps = data.get("components") if isinstance(data, dict) else None
    if not isinstance(comps, dict):
        return set()
    return {str(k).strip() for k in comps if isinstance(k, str) and k.strip()}


def rewrite_components_block(text: str, registry: set[str]) -> tuple[str, int]:
    """Rewrite mappable stray `components` list values in a YAML/frontmatter block.

    Handles both column-0 (`components:` then `- x` at same indent) and indented
    (`  - x`) block-sequence styles. Values already in ``registry`` are left as
    is; values in REMAP are rewritten; anything else is left untouched. Returns
    (new_text, num_values_changed).
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    changed = 0
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = re.match(r"^(\s*)components:\s*$", line.rstrip("\n"))
        if not m:
            out.append(line)
            i += 1
            continue
        key_indent = m.group(1)
        out.append(line)
        i += 1
        seen: set[str] = set()
        while i < n:
            im = re.match(r"^(\s*)-\s+(.+?)\s*$", lines[i].rstrip("\n"))
            if not im or len(im.group(1)) < len(key_indent):
                break
            item_indent = im.group(1)
            raw = im.group(2).strip().strip('"').strip("'")
            i += 1
            if raw in registry:
                target = raw
            elif raw in REMAP:
                target = REMAP[raw]
                if target != raw:
                    changed += 1
            else:
                target = raw
            if target in seen:
                continue
            seen.add(target)
            out.append(f"{item_indent}- {target}\n")
    return "".join(out), changed


_FRONTMATTER_RE = re.compile(r"^(---\n)(.*?)(\n---)", re.DOTALL)


def transform_file(path: Path, registry: set[str]) -> int:
    """Normalise the components block in one file in place. Returns values changed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{_HOOK_PREFIX} WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return 0

    if path.suffix == ".md":
        fm = _FRONTMATTER_RE.match(text)
        if not fm:
            return 0
        new_block, changed = rewrite_components_block(fm.group(2), registry)
        new_text = text[: fm.start(2)] + new_block + text[fm.end(2):] if changed else text
    else:  # .yaml
        new_text, changed = rewrite_components_block(text, registry)

    if changed:
        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            print(f"{_HOOK_PREFIX} WARNING: cannot write {path}: {exc}", file=sys.stderr)
            return 0
    return changed


def _staged_files(root: Path) -> list[Path]:
    """Return staged (added/modified) AC/ticket/doc files, HOOK_TEST_STAGED_FILES seam."""
    test_env = os.environ.get("HOOK_TEST_STAGED_FILES")
    if test_env is not None:
        raw = [p.strip() for p in test_env.replace(os.pathsep, "\n").splitlines() if p.strip()]
    else:
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
        except OSError as exc:
            print(f"{_HOOK_PREFIX} WARNING: git diff failed: {exc}", file=sys.stderr)
            return []
        if result.returncode != 0:
            return []
        raw = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]

    selected: list[Path] = []
    for rel in raw:
        is_ac = rel.startswith("docs/acceptance-criteria/") and rel.endswith(".yaml")
        is_ticket = rel.startswith("tickets/") and rel.endswith(".md")
        is_doc = rel.startswith("docs/") and rel.endswith(".md")
        if not (is_ac or is_ticket or is_doc):
            continue
        if rel.endswith("index.yaml"):
            continue
        p = Path(rel)
        if not p.is_absolute():
            p = root / rel
        if p.is_file():
            selected.append(p)
    return selected


def _restage(path: Path) -> None:
    try:
        subprocess.run(["git", "add", str(path)], capture_output=True)
    except OSError as exc:
        print(f"{_HOOK_PREFIX} WARNING: git add failed for {path}: {exc}", file=sys.stderr)


def main() -> int:
    """Pre-stage transform entry point. Always returns 0 (fail-open)."""
    root = Path(os.environ.get("HOOK_ROOT", str(Path.cwd())))
    registry = _load_registry(root)
    if not registry:
        # No registry to validate against — do nothing rather than guess.
        return 0
    for path in _staged_files(root):
        changed = transform_file(path, registry)
        if changed:
            _restage(path)
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"{_HOOK_PREFIX} normalised {changed} component value(s) in {rel}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — fail-open transform must never block a commit
        print(f"{_HOOK_PREFIX} unexpected error (fail-open): {type(exc).__name__}: {exc}",
              file=sys.stderr)
        sys.exit(0)
