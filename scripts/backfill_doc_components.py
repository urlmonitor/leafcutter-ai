#!/usr/bin/env python3
"""
backfill_doc_components.py — Backfill the `components` list into doc frontmatter.

MODULE: backfill_doc_components
GOAL: Backfill the `components` LIST field into docs surface markdown files that
    have YAML frontmatter but lack a `components` entry, so the knowledge graph
    can build component_membership edges for them.
BUSINESS CONTEXT: The knowledge graph reads `components` from each docs surface
    item (paths.json: docs.edge_fields contains 'components'). Many docs lack
    this field, so they are invisible to component-level graph queries. This
    script closes that gap idempotently without breaking the check_doc_frontmatter
    pre-commit hook.
ARCHITECTURE: Not needed.

=== VOCABULARY CONFLICT — READ BEFORE MODIFYING ===

Two component registries exist with DIFFERENT vocabularies:

  1. docs/components.json (hook registry) — UNDERSCORE IDs:
       build_pipeline, ac_store, commit_guardian, testing_quality, ...
     Used by: check_doc_frontmatter.py (pre-commit hook)
     This hook validates the `components` field in staged docs against
     docs/components.json and REJECTS any ID not in that file.

  2. docs/acceptance-criteria/index.yaml (AC registry) — HYPHEN IDs:
       build-pipeline, ac-store, guardrail-engine, testing-quality, ...
     Used by: AC store scripts, knowledge graph queries on the acs surface.

These are SEPARATE namespaces. A hyphen ID from index.yaml is NOT valid in the
doc hook's components field. Existing docs that carry hyphen IDs (e.g.
`ac-store`, `build-orchestration`) would fail check_doc_frontmatter when staged.
This script uses docs/components.json IDs ONLY, so backfilled docs pass the
pre-commit hook without modification.

Existing docs that already have hyphen IDs are NOT touched — they need a
separate normalization pass to replace hyphen IDs with their underscore
equivalents from docs/components.json.

=== Inference strategy ===

Two reliable signals are used (in priority order):

  1. Agent card files — docs that carry an ``agent_id`` YAML frontmatter field.
     Agent cards document a single agent. A curated lookup table maps each
     known agent_id to its owning component in docs/components.json. This is a
     definitive signal because the card IS the agent documentation.

  2. All other docs with frontmatter but no `components` field are reported
     as uninferable and left unchanged. The script never guesses from content.

Idempotent: a doc that already has a non-empty `components` list is skipped,
even if its existing IDs use the wrong vocabulary (hyphen IDs, unknown IDs).
Fixing wrong existing IDs is a normalization task, not a backfill task.

Usage:
    python3 scripts/backfill_doc_components.py [--dry-run] \\
        [--docs-dir <path>] [--registry <path>]

Exit codes:
    0 - success (including when files were reported for review)
    1 - a real error occurred (unreadable registry, write failures)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_DOCS_DIR = _REPO_ROOT / "docs"
_DEFAULT_REGISTRY = _REPO_ROOT / "docs" / "components.json"

# ---------------------------------------------------------------------------
# Agent-id → component mapping (all values validated against docs/components.json)
# Maps each known agent_id to the single most appropriate component.
# ---------------------------------------------------------------------------
_AGENT_COMPONENT_MAP: dict[str, str] = {
    # AC store and pipeline
    "ac-fulfillment-gate": "ac_store",
    "ac-triage": "ac_store",
    "ac-validator": "testing_quality",
    "build-ac": "ac_store",
    # Architecture documentation
    "adr-author": "documentation_system",
    "architect-review": "review_system",
    "architecture-diagram-author": "documentation_system",
    # Supervisor / orchestration
    "brainstorm-lead": "supervisor_system",
    "brainstorm-worker": "supervisor_system",
    "create-epic": "supervisor_system",
    "create-ticket": "supervisor_system",
    "epic-supervisor": "supervisor_system",
    "finalize-feature": "supervisor_system",
    "ticket-supervisor": "supervisor_system",
    # Business analysis and product ownership
    "business-analyst": "ticket_creation_pipeline",
    "it-po": "ticket_creation_pipeline",
    "product-owner": "ticket_creation_pipeline",
    "product-owner-agent": "ticket_creation_pipeline",
    "refinement": "ticket_creation_pipeline",
    # Review
    "change-scope-reviewer": "review_system",
    "code-review-architect": "review_system",
    "pr-reviewer": "review_system",
    # Changelog
    "changelog-agent": "changelog",
    # VCS operations
    "commit": "git_vcs_operations",
    "conflict-resolver": "git_vcs_operations",
    "pull-request": "git_vcs_operations",
    # Documentation authoring
    "documentation-expert": "documentation_system",
    "explanation-author": "documentation_system",
    "how-to-author": "documentation_system",
    "reference-author": "documentation_system",
    # Feedback and retrospective
    "feedback-analyst": "feedback_collector",
    "retrospective-agent": "feedback_collector",
    # Coding agents
    "frontend-coder": "frontend_coding",
    "python-coder": "python_coding",
    "sql-coder": "sql_coding",
    "sql-function-creator": "sql_coding",
    "sql-index-creator": "sql_coding",
    "sql-procedure-creator": "sql_coding",
    "sql-query": "sql_coding",
    "sql-table-creator": "sql_coding",
    "sql-test-writer": "sql_coding",
    "sql-view-creator": "sql_coding",
    # Glossary
    "glossary-triage": "glossary",
    # Knowledge
    "knowledge-harvester": "knowledge_system",
    # LLM authoring
    "llm-expert": "llm_authoring",
    # Onboarding
    "onboard": "onboarding",
    "onboard-config-section": "onboarding",
    # Research
    "research-agent": "research_analysis",
    # SQL specialists (additional)
    # Testing
    "test-failure-triage": "testing_quality",
    "test-runner": "testing_quality",
    "test-writer": "testing_quality",
    "user-surface-smoker": "testing_quality",
    # Ticket lifecycle
    "status-checker": "ticket_lifecycle",
    # Build pipeline
    "workflow-architect": "build_pipeline",
    # Worktree management
    "worktree-agent": "worktree_manager",
}


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def _load_valid_ids(registry_path: Path) -> set[str]:
    """Load valid component IDs from docs/components.json.

    Supports both dict-keyed (current) and list-of-dicts (legacy) formats.

    Args:
        registry_path: Absolute path to docs/components.json.

    Returns:
        set[str]: Set of valid component ID strings from the registry.

    Raises:
        SystemExit: Printed to stderr and exits 1 when registry is unreadable.
    """
    if not registry_path.exists():
        print(
            f"ERROR: component registry not found: {registry_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(registry_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"ERROR: cannot read component registry {registry_path}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    components = data.get("components", {})
    if isinstance(components, dict):
        return set(components.keys())
    if isinstance(components, list):
        return {c["id"] for c in components if isinstance(c, dict) and "id" in c}
    return set()


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def _extract_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from markdown content.

    Args:
        content: Full file content as a string.

    Returns:
        dict | None: Parsed frontmatter dict, or None if absent or malformed.
    """
    if not content.startswith("---"):
        return None
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None
    raw_yaml = content[3:end_idx].strip()
    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _has_nonempty_components(fm: dict) -> bool:
    """Return True when frontmatter already has a non-empty `components` list.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        bool: True when the field is present and non-empty.
    """
    raw = fm.get("components")
    return isinstance(raw, list) and any(
        isinstance(v, str) and v.strip() for v in raw
    )


def _insert_components_in_frontmatter(content: str, component_id: str) -> str:
    """Insert a `components` YAML block into the doc's frontmatter.

    Finds the closing ``---`` delimiter and inserts the block immediately before
    it, preserving all other formatting.

    Args:
        content: Full file content as a string.
        component_id: The single component ID to assign.

    Returns:
        str: Modified file content with the `components` block inserted.
    """
    lines = content.splitlines(keepends=True)
    # Find the opening `---` (line 0 must start with `---`)
    if not lines or not lines[0].startswith("---"):
        return content

    # Find the closing `---` (first occurrence after line 0)
    close_idx = None
    for i in range(1, len(lines)):
        stripped = lines[i].rstrip("\n\r")
        if stripped == "---":
            close_idx = i
            break

    if close_idx is None:
        return content  # Malformed frontmatter — leave unchanged

    block = f"components:\n  - {component_id}\n"
    lines.insert(close_idx, block)
    return "".join(lines)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


def _infer_component(
    path: Path,
    fm: dict,
    valid_ids: set[str],
) -> tuple[str | None, str]:
    """Infer the component ID for a doc file.

    Args:
        path: Absolute path to the doc file.
        fm: Parsed frontmatter dictionary.
        valid_ids: Set of valid component IDs from docs/components.json.

    Returns:
        tuple[str | None, str]: (component_id, reason). component_id is None
            when inference fails; reason describes the outcome for logging.
    """
    # Signal 1: agent card with agent_id field
    agent_id = fm.get("agent_id")
    if agent_id and isinstance(agent_id, str):
        mapped = _AGENT_COMPONENT_MAP.get(agent_id.strip())
        if mapped and mapped in valid_ids:
            return mapped, f"agent_id='{agent_id}' → '{mapped}'"
        if mapped and mapped not in valid_ids:
            return None, (
                f"agent_id='{agent_id}' maps to '{mapped}' but "
                f"that ID is not in docs/components.json"
            )
        return None, f"agent_id='{agent_id}' has no entry in _AGENT_COMPONENT_MAP"

    return None, "no reliable inference signal (not an agent card)"


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------


def _process_file(
    path: Path,
    valid_ids: set[str],
    dry_run: bool,
) -> str:
    """Process a single doc file.

    Args:
        path: Absolute path to the doc file.
        valid_ids: Set of valid component IDs from docs/components.json.
        dry_run: When True, prints what would change without writing.

    Returns:
        str: One of 'skipped', 'backfilled', 'review', 'error'.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return "error"

    fm = _extract_frontmatter(content)
    if fm is None:
        return "skipped"  # No frontmatter — out of scope

    if _has_nonempty_components(fm):
        return "skipped"  # Already tagged — idempotent

    component_id, reason = _infer_component(path, fm, valid_ids)

    if component_id is None:
        print(f"REVIEW: {path} — {reason}; left unchanged.")
        return "review"

    if dry_run:
        print(f"[dry-run] Would backfill {path} → components: [{component_id}]")
        return "backfilled"

    new_content = _insert_components_in_frontmatter(content, component_id)
    if new_content == content:
        print(
            f"WARNING: could not insert components into {path} "
            "(frontmatter structure unexpected); left unchanged.",
            file=sys.stderr,
        )
        return "error"

    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write {path}: {exc}", file=sys.stderr)
        return "error"

    print(f"Backfilled {path} → components: [{component_id}]")
    return "backfilled"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Backfill the `components` list into doc frontmatter so the "
            "knowledge graph can build component_membership edges for docs."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing any files.",
    )
    parser.add_argument(
        "--docs-dir",
        default=str(_DEFAULT_DOCS_DIR),
        help=f"Path to the docs directory. Default: {_DEFAULT_DOCS_DIR}",
    )
    parser.add_argument(
        "--registry",
        default=str(_DEFAULT_REGISTRY),
        help=f"Path to docs/components.json. Default: {_DEFAULT_REGISTRY}",
    )
    return parser.parse_args()


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code (0 = success, 1 = errors).

    Args:
        argv: Optional argument list override (for testing).

    Returns:
        int: 0 on success, 1 if any file errors occurred.
    """
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    args = _parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        print(f"ERROR: docs directory not found: {docs_dir}", file=sys.stderr)
        return 1

    registry_path = Path(args.registry)
    valid_ids = _load_valid_ids(registry_path)
    if not valid_ids:
        print(
            f"ERROR: could not load any component IDs from {registry_path}; "
            "refusing to backfill without a registry.",
            file=sys.stderr,
        )
        return 1

    # Validate that every _AGENT_COMPONENT_MAP value is in the registry
    unknown_in_map = {
        v for v in _AGENT_COMPONENT_MAP.values() if v not in valid_ids
    }
    if unknown_in_map:
        print(
            "WARNING: _AGENT_COMPONENT_MAP references IDs not in docs/components.json: "
            f"{sorted(unknown_in_map)}",
            file=sys.stderr,
        )

    counts: dict[str, int] = {"backfilled": 0, "skipped": 0, "review": 0, "error": 0}
    review_files: list[Path] = []

    # Scan all .md files recursively, excluding acceptance-criteria/
    for path in sorted(docs_dir.rglob("*.md")):
        if "acceptance-criteria" in path.parts:
            continue
        result = _process_file(path, valid_ids, dry_run=args.dry_run)
        counts[result] += 1
        if result == "review":
            review_files.append(path)

    mode = "dry-run" if args.dry_run else "actual"
    action = "Would backfill" if args.dry_run else "Backfilled"
    print(
        f"\nDoc components backfill complete ({mode}):\n"
        f"  {action}: {counts['backfilled']} files\n"
        f"  Skipped (already have components / no frontmatter): {counts['skipped']} files\n"
        f"  Needs review (component not inferable): {counts['review']} files\n"
        f"  Errors: {counts['error']} files"
    )

    if review_files:
        print("\nFiles needing human review (component could not be inferred safely):")
        for p in review_files:
            print(f"  - {p}")

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-08 [python-coder/xsurface-backfill]: Initial implementation.
  Backfills `components` list into docs surface markdown files that have
  frontmatter but lack the field. Uses two reliable inference signals:
  (1) agent cards with `agent_id` field mapped to components.json IDs;
  (2) all other docs reported as uninferable — never guesses from content.
  Uses docs/components.json (underscore IDs) vocabulary, NOT index.yaml
  (hyphen IDs), because check_doc_frontmatter validates against the former.
  This vocabulary mismatch is documented prominently in the module docstring.
  Idempotent: skips docs that already have any non-empty `components` value.
  Uses targeted line insertion (not YAML round-trip) to preserve formatting.
====================================================================
"""
