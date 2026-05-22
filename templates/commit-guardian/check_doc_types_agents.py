"""
MODULE: check_doc_types_agents
GOAL: Pre-commit hook that validates every writer_agent referenced in doc_types.json
    resolves to a real, non-deprecated entry in agent_registry.json.
BUSINESS CONTEXT: doc_types.json maps each Diataxis doc type to a writer_agent
    responsible for producing that doc class. If a referenced agent is absent from
    the registry, the documentation routing system will fail silently at runtime
    (documentation-expert dispatches to an agent that does not exist). This hook
    catches the mismatch at commit time, before it can propagate to production. The
    check is intentionally fail-open on absent config files (a project may not yet
    have either file; missing files should not block legitimate commits).
ARCHITECTURE: Thin pre-commit hook following the check_agent_registry.py pattern.
    Resolves the leafcutter package root via git rev-parse --show-toplevel.
    Reads both JSON files directly (no shared validator module needed — the logic is
    simple enough to inline). Only fires when doc_types.json or agent_registry.json
    is staged; no-ops on unrelated commits. Deprecated agents (deprecated: true) are
    excluded from the valid-agent set — a writer_agent referencing a deprecated agent
    is treated as a mismatch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _get_staged_files() -> list[str]:
    """Return list of staged file paths from git.

    Returns:
        List of staged file path strings relative to the repo root.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACRM"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip().splitlines()


def _is_doc_types_related(staged: list[str]) -> bool:
    """Return True if any staged file touches doc_types or agent_registry config.

    Args:
        staged: List of staged file paths.

    Returns:
        True if at least one staged file is doc_types.json or agent_registry.json
        inside the leafcutter config directory.
    """
    triggers = (
        "leafcutter/config/doc_types.json",
        "leafcutter/config/agent_registry.json",
    )
    return any(
        any(f.replace("\\", "/").endswith(t) for t in triggers)
        for f in staged
    )


def _load_json_file(path: Path, label: str) -> dict | None:
    """Load a JSON file, returning None and printing a warning if absent or invalid.

    Args:
        path: Absolute path to the JSON file.
        label: Human-readable label for error messages.

    Returns:
        Parsed JSON dict on success, None on missing file or parse error.
    """
    if not path.exists():
        print(
            f"[check_doc_types_agents] {label} not found at {path} — skipping check.",
            file=sys.stderr,
        )
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(
            f"[check_doc_types_agents] {label} is not valid JSON: {exc} — skipping check.",
            file=sys.stderr,
        )
        return None


def _build_valid_agent_ids(registry: dict) -> set[str]:
    """Extract non-deprecated agent IDs from the registry.

    An agent is valid iff it has an "id" field and does NOT have "deprecated": true.

    Args:
        registry: Parsed agent_registry.json dict.

    Returns:
        Set of valid (non-deprecated) agent ID strings.
    """
    valid: set[str] = set()
    for agent in registry.get("agents", []):
        agent_id = agent.get("id")
        if agent_id and not agent.get("deprecated", False):
            valid.add(agent_id)
    return valid


def main() -> int:
    """Run doc_types -> agent_registry consistency check as a pre-commit hook.

    Returns:
        Exit code: 0 when consistent, files absent, or not triggered; 1 on errors.
    """
    staged = _get_staged_files()
    if not _is_doc_types_related(staged):
        return 0  # No relevant files staged — nothing to check

    # Locate the package root via git rev-parse --show-toplevel.
    repo_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if repo_root_result.returncode != 0:
        print(
            "[check_doc_types_agents] Could not determine repo root; skipping.",
            file=sys.stderr,
        )
        return 0

    repo_root = Path(repo_root_result.stdout.strip())
    package_root = repo_root / "leafcutter"

    if not package_root.exists():
        # Package not present in this repo — nothing to validate.
        return 0

    config_dir = package_root / "config"

    # Load both config files; fail-open (return 0) when either is absent/invalid.
    doc_types_data = _load_json_file(config_dir / "doc_types.json", "doc_types.json")
    if doc_types_data is None:
        return 0  # Fail open — missing doc_types.json is not a blocking error

    registry_data = _load_json_file(config_dir / "agent_registry.json", "agent_registry.json")
    if registry_data is None:
        return 0  # Fail open — missing agent_registry.json is not a blocking error

    valid_agent_ids = _build_valid_agent_ids(registry_data)

    # Collect writer_agent values that are non-null and non-empty.
    errors: list[str] = []
    doc_types = doc_types_data.get("doc_types", {})
    for doc_type_key, doc_type_entry in doc_types.items():
        if not isinstance(doc_type_entry, dict):
            continue
        writer_agent = doc_type_entry.get("writer_agent")
        if not writer_agent:
            # Null or empty — intentionally unrouted; skip.
            continue
        if writer_agent not in valid_agent_ids:
            errors.append(
                f"  doc_type '{doc_type_key}' references writer_agent '{writer_agent}'"
                f" which is absent or deprecated in agent_registry.json"
            )

    if errors:
        print(
            "[check_doc_types_agents] doc_types.json -> agent_registry.json mismatch:",
            file=sys.stderr,
        )
        for err in errors:
            print(err, file=sys.stderr)
        print(
            "\nFix the mismatches above before committing. Either add the missing agent "
            "to agent_registry.json, update the writer_agent in doc_types.json, or "
            "set writer_agent to null for intentionally unrouted doc types.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 11:00 [ticket-09/python-coder]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Fail-open on absent files (doc_types.json or agent_registry.json
#   missing is not a blocking error — the repo may not yet have either).
#   Hard-error on resolvable mismatches (agent referenced in doc_types.json
#   is absent or deprecated in the registry). Follows check_agent_registry.py
#   pattern: staged-file gate, repo-root resolution, stderr error output.
#   Deprecated agents (deprecated: true in registry) are excluded from the
#   valid-agent set — routing to a deprecated agent is treated as a mismatch.
# ====================================================================
