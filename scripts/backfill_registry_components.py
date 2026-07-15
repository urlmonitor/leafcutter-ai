#!/usr/bin/env python3
"""
MODULE: backfill_registry_components
GOAL: Backfill the `components` field on every agent, skill, and roadmap-phase
    registry entry that is currently missing it. Uses a docs/components.json
    reverse-map (primary_code path → component_id) to assign components with
    high confidence; entries with no inferable mapping are reported and skipped.
BUSINESS CONTEXT: The knowledge graph builds component_membership edges from
    the `components` field on registry entries (see config/paths.json
    edge_fields). Without it, every agent, skill, and roadmap phase is a
    disconnected node. This backfill is a prerequisite for enabling the
    check-surface-components-e3 hook.
ARCHITECTURE:
    - Vocabulary: docs/components.json underscore-case IDs.
      Rationale: the e3 hook's error message points to both docs/components.json
      (underscore-case) and docs/acceptance-criteria/index.yaml (kebab-case),
      but only the former carries architectural component semantics. The hook
      currently enforces presence+non-empty only (membership validation
      deferred), so either vocabulary passes. Using the architectural component
      vocabulary is more semantically correct for registry-level membership.
    - Reverse-map strategy: for each component in docs/components.json, each
      primary_code entry is a key. Agent/skill template paths are compared
      against these keys (exact match for files; directory-prefix match for
      directory keys ending with '/').
    - Skills strip the 'leafcutter/' consumer prefix before comparison
      (skill_registry.json template_paths use the consumer-relative form
      'leafcutter/templates/skills/X/', while components.json uses the
      repo-relative 'templates/skills/').
    - Roadmap phases are assigned ["roadmap"] because docs/roadmap.json is in
      the 'roadmap' component's primary_code. The e3 hook extracts phases via
      the 'phases' fallback key in _extract_entries.
    - Idempotent: entries already carrying a non-empty `components` list are
      not touched.
    - Fail-open on individual entries: an uninferable entry is reported but
      does not abort the run. Unrecoverable file errors exit 1.

Exit codes: 0 = success (all inferable entries processed, uninferable reported);
            1 = unrecoverable error (file not found / JSON parse failure).

Usage:
    python scripts/backfill_registry_components.py [--dry-run]

Options:
    --dry-run    Print what would be changed without modifying any file.

DECISION HISTORY:
  - 2026-07-08 [python-coder/xsurface-backfill]: Initial implementation.
    Vocabulary: docs/components.json underscore-case. See ARCHITECTURE above.
    Roadmap confirmed as a membership-bearing surface (has 'components' in
    edge_fields and is a non-directory path per paths.json). Hook uses 'phases'
    fallback key in _extract_entries, so phases array is the target.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Return the project root by walking up from this script's location.

    Returns:
        Absolute path to the project root.

    Raises:
        SystemExit: if no project root marker (CLAUDE.md or .git) is found.
    """
    for ancestor in [Path(__file__).parent, *Path(__file__).parent.parents]:
        if (ancestor / "CLAUDE.md").exists() or (ancestor / ".git").exists():
            return ancestor
    print("ERROR: cannot locate project root (no CLAUDE.md or .git found)", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _detect_indent(text: str) -> int:
    """Detect the indentation size of a JSON file by scanning the first indented line.

    Args:
        text: Raw JSON file content.

    Returns:
        Number of spaces used for one indentation level (2 or 4; defaults to 4).
    """
    for line in text.splitlines():
        if not line:
            continue
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0 and stripped and stripped[0] not in ("{", "[", "]", "}"):
            return leading
    return 4


def _load_json_file(path: Path) -> tuple[Any, int]:
    """Read and parse a JSON file, returning the parsed data and detected indent.

    Args:
        path: Absolute path to the JSON file.

    Returns:
        (parsed_data, indent_size) tuple.

    Raises:
        SystemExit: on read error or JSON parse failure.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    indent = _detect_indent(text)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: JSON parse error in {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    return data, indent


def _write_json_file(path: Path, data: Any, indent: int) -> None:
    """Write a Python object as JSON to a file, with a trailing newline.

    Args:
        path: Absolute path to the output file.
        data: JSON-serialisable object.
        indent: Number of spaces to use for indentation.

    Raises:
        SystemExit: on write error.
    """
    try:
        text = json.dumps(data, indent=indent, ensure_ascii=False)
        path.write_text(text + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: cannot write {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Reverse-map: docs/components.json → path_fragment → [component_id]
# ---------------------------------------------------------------------------


def _build_reverse_map(project_root: Path) -> dict[str, list[str]]:
    """Build a path-fragment → component_ids mapping from docs/components.json.

    Each primary_code entry in a component becomes a key. The component id is
    added to the value list. If multiple components share a primary_code path,
    all of them are recorded.

    Args:
        project_root: Absolute path to the repository root.

    Returns:
        Dict mapping path_fragment → list of component_ids.

    Raises:
        SystemExit: on read or parse error.
    """
    components_path = project_root / "docs" / "components.json"
    data, _ = _load_json_file(components_path)

    reverse_map: dict[str, list[str]] = {}
    components = data.get("components", {})
    if not isinstance(components, dict):
        return reverse_map

    for comp_id, comp_data in components.items():
        if not isinstance(comp_data, dict):
            continue
        primary_code = comp_data.get("primary_code", [])
        if not isinstance(primary_code, list):
            continue
        for code_path in primary_code:
            if not isinstance(code_path, str) or not code_path.strip():
                continue
            reverse_map.setdefault(code_path, [])
            if comp_id not in reverse_map[code_path]:
                reverse_map[code_path].append(comp_id)

    return reverse_map


# ---------------------------------------------------------------------------
# Component inference
# ---------------------------------------------------------------------------


def _match_path(candidate: str, reverse_map: dict[str, list[str]]) -> list[str]:
    """Return all component IDs whose primary_code matches candidate.

    Matching rules (applied in order; all matching keys contribute):
    1. Exact string match: candidate == key.
    2. Directory-prefix match: key ends with '/' and candidate starts with key.
    3. Suffix match: candidate ends with key (handles path aliasing).

    Args:
        candidate: Normalised path to test (e.g. "templates/agents/commit.md").
        reverse_map: Dict from path_fragment → [component_id].

    Returns:
        Deduplicated list of matching component IDs (may be empty).
    """
    found: list[str] = []
    seen_ids: set[str] = set()

    for key, comp_ids in reverse_map.items():
        matched = False
        if candidate == key:
            matched = True
        elif key.endswith("/") and candidate.startswith(key):
            matched = True
        elif not key.endswith("/") and candidate.endswith(key):
            matched = True

        if matched:
            for cid in comp_ids:
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    found.append(cid)

    return found


def _infer_agent_components(
    agent_id: str,
    template_path: str | None,
    reverse_map: dict[str, list[str]],
) -> list[str] | None:
    """Infer component IDs for a single agent entry.

    Agent template paths (e.g. "templates/agents/commit.md") are matched
    against the reverse_map exactly or by suffix.

    Args:
        agent_id: The agent's id field (used only for reporting).
        template_path: The agent's template_path value, or None.
        reverse_map: Path-fragment → component_ids mapping.

    Returns:
        Non-empty list of component IDs if inferable; None otherwise.
    """
    if not template_path:
        return None
    matched = _match_path(template_path, reverse_map)
    return matched if matched else None


def _infer_skill_components(
    skill_id: str,
    template_path: str | None,
    reverse_map: dict[str, list[str]],
) -> list[str] | None:
    """Infer component IDs for a single skill entry.

    Skill template_path values use the consumer-relative form
    'leafcutter/templates/skills/X/' (with the 'leafcutter/' prefix).
    The prefix is stripped before lookup because components.json uses the
    repo-relative form 'templates/skills/' (without 'leafcutter/').

    All skills match skills_system via the 'templates/skills/' directory key.
    More-specific matches (e.g. building-epics → supervisor_system via the
    .claude/skills/ deployed path) are included when they also appear.

    Args:
        skill_id: The skill's id field (used only for reporting).
        template_path: The skill's template_path value, or None.
        reverse_map: Path-fragment → component_ids mapping.

    Returns:
        Non-empty list of component IDs if inferable; None otherwise.
    """
    if not template_path:
        return None

    # Strip consumer-relative prefix so 'leafcutter/templates/skills/X/'
    # becomes 'templates/skills/X/' which matches the 'templates/skills/'
    # directory key in skills_system.primary_code.
    normalised = template_path
    if normalised.startswith("leafcutter/"):
        normalised = normalised[len("leafcutter/"):]

    matched = _match_path(normalised, reverse_map)
    return matched if matched else None


def _infer_roadmap_phase_components(
    phase_id: str,
    reverse_map: dict[str, list[str]],
) -> list[str]:
    """Infer component IDs for a roadmap phase.

    The file docs/roadmap.json is listed in the 'roadmap' component's
    primary_code, so all phases within it belong to the roadmap component.

    Args:
        phase_id: The phase's id field (used only for reporting).
        reverse_map: Path-fragment → component_ids mapping.

    Returns:
        Always returns ["roadmap"].
    """
    # docs/roadmap.json is the canonical key for roadmap phases.
    # Fall back to the hardcoded value if the map is somehow empty.
    candidates = reverse_map.get("docs/roadmap.json", ["roadmap"])
    return list(candidates) if candidates else ["roadmap"]


# ---------------------------------------------------------------------------
# Entry extraction (mirrors check_surface_components_e3 logic)
# ---------------------------------------------------------------------------

_ENTRY_FALLBACK_KEYS = ("agents", "skills", "phases", "items")


def _extract_entries(data: Any, surface_name: str) -> list[Any]:
    """Extract the top-level entry list from a registry JSON payload.

    Mirrors the _extract_entries strategy used by check_surface_components_e3.

    Args:
        data: Parsed JSON data.
        surface_name: The surface name from paths.json (e.g. "agents").

    Returns:
        List of entries (may contain non-dict items; callers skip those).
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in (surface_name, *_ENTRY_FALLBACK_KEYS):
        candidate = data.get(key)
        if isinstance(candidate, list):
            return candidate
    return []


# ---------------------------------------------------------------------------
# Registry processing
# ---------------------------------------------------------------------------


class _RegistryResult:
    """Accumulates per-registry processing results."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.already_set: list[str] = []
        self.assigned: list[tuple[str, list[str]]] = []  # (entry_id, components)
        self.uninferable: list[str] = []


def _process_agent_registry(
    project_root: Path,
    reverse_map: dict[str, list[str]],
    dry_run: bool,
) -> _RegistryResult:
    """Process config/agent_registry.json.

    Args:
        project_root: Repository root path.
        reverse_map: Path-fragment → component_ids mapping.
        dry_run: If True, do not write any changes.

    Returns:
        _RegistryResult with counts and lists of outcomes.
    """
    result = _RegistryResult("agent_registry")
    path = project_root / "config" / "agent_registry.json"
    data, indent = _load_json_file(path)

    entries = _extract_entries(data, "agents")
    modified = False

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", "<unknown>"))
        existing = entry.get("components")
        if isinstance(existing, list) and any(
            isinstance(v, str) and v.strip() for v in existing
        ):
            result.already_set.append(entry_id)
            continue

        inferred = _infer_agent_components(entry_id, entry.get("template_path"), reverse_map)
        if inferred is None:
            result.uninferable.append(entry_id)
            continue

        result.assigned.append((entry_id, inferred))
        if not dry_run:
            entry["components"] = inferred
            modified = True

    if modified and not dry_run:
        _write_json_file(path, data, indent)

    return result


def _process_skill_registry(
    project_root: Path,
    reverse_map: dict[str, list[str]],
    dry_run: bool,
) -> _RegistryResult:
    """Process config/skill_registry.json.

    Args:
        project_root: Repository root path.
        reverse_map: Path-fragment → component_ids mapping.
        dry_run: If True, do not write any changes.

    Returns:
        _RegistryResult with counts and lists of outcomes.
    """
    result = _RegistryResult("skill_registry")
    path = project_root / "config" / "skill_registry.json"
    data, indent = _load_json_file(path)

    entries = _extract_entries(data, "skills")
    modified = False

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", "<unknown>"))
        existing = entry.get("components")
        if isinstance(existing, list) and any(
            isinstance(v, str) and v.strip() for v in existing
        ):
            result.already_set.append(entry_id)
            continue

        inferred = _infer_skill_components(entry_id, entry.get("template_path"), reverse_map)
        if inferred is None:
            result.uninferable.append(entry_id)
            continue

        result.assigned.append((entry_id, inferred))
        if not dry_run:
            entry["components"] = inferred
            modified = True

    if modified and not dry_run:
        _write_json_file(path, data, indent)

    return result


def _process_roadmap(
    project_root: Path,
    reverse_map: dict[str, list[str]],
    dry_run: bool,
) -> _RegistryResult:
    """Process docs/roadmap.json (phases array).

    Args:
        project_root: Repository root path.
        reverse_map: Path-fragment → component_ids mapping.
        dry_run: If True, do not write any changes.

    Returns:
        _RegistryResult with counts and lists of outcomes.
    """
    result = _RegistryResult("roadmap")
    path = project_root / "docs" / "roadmap.json"
    data, indent = _load_json_file(path)

    entries = _extract_entries(data, "roadmap")
    modified = False

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", "<unknown>"))
        existing = entry.get("components")
        if isinstance(existing, list) and any(
            isinstance(v, str) and v.strip() for v in existing
        ):
            result.already_set.append(entry_id)
            continue

        inferred = _infer_roadmap_phase_components(entry_id, reverse_map)
        result.assigned.append((entry_id, inferred))
        if not dry_run:
            entry["components"] = inferred
            modified = True

    if modified and not dry_run:
        _write_json_file(path, data, indent)

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_result(result: _RegistryResult, dry_run: bool) -> None:
    """Print a per-registry processing summary to stdout.

    Args:
        result: Processing result for one registry.
        dry_run: Whether this was a dry run.
    """
    action = "WOULD ASSIGN" if dry_run else "ASSIGNED"
    print(f"\n=== {result.name} ===")
    print(f"  Already set   : {len(result.already_set)}")
    print(f"  {action:13s} : {len(result.assigned)}")
    print(f"  Uninferable   : {len(result.uninferable)} (reported for review)")

    if result.assigned:
        print(f"\n  {action}:")
        for entry_id, components in result.assigned:
            print(f"    {entry_id}: {components}")

    if result.uninferable:
        print("\n  UNINFERABLE (need manual component assignment):")
        for entry_id in result.uninferable:
            print(f"    {entry_id}")


# ---------------------------------------------------------------------------
# Idempotency verification
# ---------------------------------------------------------------------------


def _verify_idempotent(project_root: Path, reverse_map: dict[str, list[str]]) -> bool:
    """Verify that a second run would produce zero new assignments.

    Args:
        project_root: Repository root path.
        reverse_map: Path-fragment → component_ids mapping.

    Returns:
        True if all previously-assigned entries already have components set;
        False if any entry is still missing (indicates a write failure).
    """
    checks: list[tuple[Path, str]] = [
        (project_root / "config" / "agent_registry.json", "agents"),
        (project_root / "config" / "skill_registry.json", "skills"),
        (project_root / "docs" / "roadmap.json", "roadmap"),
    ]
    all_good = True
    for file_path, surface in checks:
        data, _ = _load_json_file(file_path)
        entries = _extract_entries(data, surface)
        missing = [
            str(e.get("id", "<unknown>"))
            for e in entries
            if isinstance(e, dict)
            and not (
                isinstance(e.get("components"), list)
                and any(isinstance(v, str) and v.strip() for v in e["components"])
            )
        ]
        # Entries that are uninferable are expected to still be missing.
        # We cannot check without re-running the inference, so we just report
        # the total missing count.
        if missing:
            print(
                f"  Idempotency: {file_path.name} still has "
                f"{len(missing)} entries without components: {missing[:5]}...",
                file=sys.stderr,
            )
            all_good = False

    return all_good


# ---------------------------------------------------------------------------
# JSON parse verification
# ---------------------------------------------------------------------------


def _verify_json_parseable(project_root: Path) -> bool:
    """Confirm all three registry files still parse as valid JSON after writes.

    Args:
        project_root: Repository root path.

    Returns:
        True if all files parse cleanly; False if any fail.
    """
    files = [
        project_root / "config" / "agent_registry.json",
        project_root / "config" / "skill_registry.json",
        project_root / "docs" / "roadmap.json",
    ]
    all_ok = True
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
            json.loads(text)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"  JSON-parse FAIL: {path}: {exc}", file=sys.stderr)
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the registry components backfill. Returns 0 on success, 1 on error."""
    parser = argparse.ArgumentParser(
        description="Backfill `components` field on registry entries using docs/components.json reverse-map."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be changed without modifying any file.",
    )
    args = parser.parse_args()
    dry_run: bool = args.dry_run

    project_root = _find_project_root()
    print(f"Project root   : {project_root}")
    print(f"Mode           : {'DRY RUN' if dry_run else 'APPLY'}")
    print("Vocabulary     : docs/components.json underscore-case IDs")

    reverse_map = _build_reverse_map(project_root)
    print(f"Reverse-map    : {len(reverse_map)} primary_code keys loaded")

    agent_result = _process_agent_registry(project_root, reverse_map, dry_run)
    skill_result = _process_skill_registry(project_root, reverse_map, dry_run)
    roadmap_result = _process_roadmap(project_root, reverse_map, dry_run)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    _print_result(agent_result, dry_run)
    _print_result(skill_result, dry_run)
    _print_result(roadmap_result, dry_run)

    total_assigned = (
        len(agent_result.assigned)
        + len(skill_result.assigned)
        + len(roadmap_result.assigned)
    )
    total_uninferable = (
        len(agent_result.uninferable)
        + len(skill_result.uninferable)
        + len(roadmap_result.uninferable)
    )
    total_already = (
        len(agent_result.already_set)
        + len(skill_result.already_set)
        + len(roadmap_result.already_set)
    )

    print(f"\nTotal already set   : {total_already}")
    print(f"Total assigned      : {total_assigned}" + (" (dry run — not written)" if dry_run else ""))
    print(f"Total uninferable   : {total_uninferable} (require manual assignment)")

    if not dry_run and total_assigned > 0:
        print("\nVerifying JSON parseable after writes...")
        if _verify_json_parseable(project_root):
            print("  All files parse cleanly.")
        else:
            print("  One or more files failed to parse — check output above.", file=sys.stderr)
            return 1

        print("\nVerifying idempotency (second-run dry run)...")
        agent_result2 = _process_agent_registry(project_root, reverse_map, dry_run=True)
        skill_result2 = _process_skill_registry(project_root, reverse_map, dry_run=True)
        roadmap_result2 = _process_roadmap(project_root, reverse_map, dry_run=True)
        new_on_rerun = (
            len(agent_result2.assigned)
            + len(skill_result2.assigned)
            + len(roadmap_result2.assigned)
        )
        if new_on_rerun == 0:
            print("  Idempotency confirmed: 0 new assignments on second run.")
        else:
            print(
                f"  WARNING: {new_on_rerun} entries would still be assigned on a second run. "
                "Check write path.",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"UNEXPECTED ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
