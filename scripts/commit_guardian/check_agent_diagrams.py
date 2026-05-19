"""
MODULE: check_agent_diagrams
GOAL: Pre-commit hook that warns when agent_registry.json has been modified but
    the embedded Mermaid diagrams in target docs are stale.
BUSINESS CONTEXT: Agent topology diagrams are auto-generated from agent_registry.json
    (ticket 28). When the registry changes but the diagrams are not regenerated,
    the docs silently drift from reality. This hook detects the mismatch and warns
    the committer to run --update-diagrams.
ARCHITECTURE: Reads the staged version of agent_registry.json, computes an 8-char
    SHA256 hash, then checks whether the same hash appears in the <!-- registry-hash:
    XXXXXXXX --> comment inside each marker block. Emits a warning (non-blocking)
    when any doc is stale. Only fires when agent_registry.json is staged.

# DECISION HISTORY
# - 2026-05-13 19:00 [epic-supervisor/ticket-28]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Warning (non-blocking) chosen over error — diagram staleness is a documentation
#   hygiene issue, not a correctness issue. Stale diagrams never break functionality.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path


_MARKER_RE = re.compile(r"<!--\s*registry-hash:([0-9a-f]{8})\s*-->")
_REGISTRY_SUBPATH = "leafcutter/config/agent_registry.json"
_DOC_PATHS = [
    "leafcutter/docs/agentic-runtime-flow.md",
    "leafcutter/docs/agents/README.md",
]


def _staged_files() -> list[str]:
    """Return list of staged file paths.

    Returns:
        List of staged file path strings relative to repo root.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip().splitlines()


def _registry_content_hash(repo_root: Path) -> str | None:
    """Compute the hash of the staged (or on-disk) agent_registry.json.

    Args:
        repo_root: Root of the git repository.

    Returns:
        8-char hex hash string, or None if the registry file is not found.
    """
    registry = repo_root / _REGISTRY_SUBPATH
    if not registry.exists():
        return None
    content = registry.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def _embedded_hash(doc_path: Path) -> str | None:
    """Extract the embedded registry hash from a doc's first marker block.

    Args:
        doc_path: Path to the target documentation file.

    Returns:
        8-char hash string if found, or None if not present.
    """
    if not doc_path.exists():
        return None
    content = doc_path.read_text(encoding="utf-8")
    m = _MARKER_RE.search(content)
    return m.group(1) if m else None


def main() -> int:
    """Run the stale-diagram check.

    Returns:
        Exit code: 0 always (warning only, non-blocking).
    """
    staged = _staged_files()

    # Only fire when agent_registry.json is staged
    registry_staged = any(_REGISTRY_SUBPATH in f for f in staged)
    if not registry_staged:
        return 0

    # Find repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    repo_root = Path(result.stdout.strip())

    current_hash = _registry_content_hash(repo_root)
    if current_hash is None:
        return 0  # Registry not found — skip check

    stale_docs: list[str] = []
    for doc_subpath in _DOC_PATHS:
        doc_path = repo_root / doc_subpath
        embedded = _embedded_hash(doc_path)
        if embedded is None:
            continue  # No marker block present — doc not yet set up
        if embedded != current_hash:
            stale_docs.append(doc_subpath)

    if stale_docs:
        print(
            "\n[WARN] agent_registry.json was modified but the following docs have "
            "stale embedded diagrams:\n",
            file=sys.stderr,
        )
        for doc in stale_docs:
            print(f"  {doc}", file=sys.stderr)
        print(
            "\nRun to regenerate:\n"
            "  python leafcutter/scripts/generate_agent_diagram.py "
            "--output-format embed\n"
            "or:\n"
            "  python leafcutter/scripts/build.py --update-diagrams\n",
            file=sys.stderr,
        )

    return 0  # Warning only — never block the commit


if __name__ == "__main__":
    sys.exit(main())
