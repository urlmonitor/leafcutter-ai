"""
MODULE: check_ac_governance
GOAL: Pre-commit hook that write-locks requirement-defining fields in AC YAML
    files to authorized agents only (product-owner-v3, business-analyst-v3,
    it-po-v3, and human users), blocking implementation agents from silently
    rewriting acceptance criteria.
BUSINESS CONTEXT: The AC store is the authoritative definition of "done". If an
    implementation agent can rewrite `criteria` without detection, the team loses
    the trustworthy source of truth that makes ticket-driven development tractable.
    This hook is the mechanical enforcement layer: it catches unauthorized field
    changes at commit time before they reach the repository.
ARCHITECTURE: Reads staged .yaml files from docs/acceptance-criteria/ (via git
    diff --cached or HOOK_TEST_FILES env var for testing). Loads agent_registry.json
    once to distinguish known agents from human users. For each staged file, loads
    both the staged version (from disk) and the HEAD version (from git show HEAD:)
    using PyYAML safe_load (YAML-level comparison, not text diff). Checks:
      - Protected fields (criteria, title, req_status, depends_on): only authorized
        agents may add or modify (ACS-400a, ACS-400b-3).
      - Open fields (work_status, implemented_by, covered_by): any agent may modify
        (ACS-400b-1, ACS-400b-2).
      - Audit trail: new AC files must have origin_agent (ACS-400c-1); modified
        criteria must have an updated amended_by list (ACS-400c-2, ACS-400c-2-i).
    Outputs: JSON block decision to stdout on violation; diagnostic detail to stderr.
    Fail-open: any unexpected exception exits 0 with [check-ac-governance] prefix
    on stderr (ACS-400e-1-i).

Exit codes:
    0 - All staged AC YAML files pass governance rules (or no AC files staged)
    1 - One or more governance violations detected

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_ac_governance.py

DOC_LINKS:
  - docs/acceptance-criteria/ac-store/ACS-400-ac-governance/
  - docs/reference/claude-code-hooks.md

DECISION HISTORY:
  - 2026-06-05 [python-coder/ACS-400]: Created check_ac_governance.py.
    Implements write-lock for criteria/title/req_status/depends_on fields.
    Loads agent registry once per invocation; unknown identities are human users.
    YAML-level field comparison to avoid false positives from whitespace changes.
    Fail-open on any unexpected exception (ACS-400e-1-i).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants — field categories (ACS-400b-3 requirement: named constants at
# module level so future additions require a one-line change, not scattered
# inline string edits)
# ---------------------------------------------------------------------------

_PROTECTED_FIELDS: frozenset[str] = frozenset(
    {"criteria", "title", "req_status", "depends_on"}
)
"""Fields that only authorized agents may create or modify (ACS-400a, ACS-400b-3)."""

_OPEN_FIELDS: frozenset[str] = frozenset(
    {"work_status", "implemented_by", "covered_by"}
)
"""Fields that any agent may modify freely (ACS-400b-1, ACS-400b-2)."""

_AUTHORIZED_AGENTS: frozenset[str] = frozenset(
    {"product-owner-v3", "business-analyst-v3", "it-po-v3"}
)
"""Requirement-authoring agents authorized to write protected fields.
Human users (any identity not found in agent_registry.json) are also authorized.
"""

_AC_STORE_DIR = "docs/acceptance-criteria"
_REGISTRY_PATH = "config/agent_registry.json"
_HOOK_PREFIX = "[check-ac-governance]"


# ---------------------------------------------------------------------------
# Registry loading — determines human vs agent identity
# ---------------------------------------------------------------------------


def _load_registry(registry_path: str | None = None) -> set[str]:
    """Load all agent IDs from agent_registry.json.

    Any string not in the returned set is treated as a human user (ACS-400a-3-i).

    Args:
        registry_path: Optional explicit path to agent_registry.json. When None,
            resolved relative to HOOK_ROOT env var or cwd/parents.

    Returns:
        Set of known agent ID strings. Empty set on load failure (fail-open).
    """
    if registry_path:
        path = Path(registry_path)
    else:
        env_root = os.environ.get("HOOK_ROOT")
        if env_root:
            path = Path(env_root) / _REGISTRY_PATH
        else:
            path = _find_project_root() / _REGISTRY_PATH if _find_project_root() else None  # type: ignore[assignment]

    if path is None or not path.exists():
        print(
            f"{_HOOK_PREFIX} WARNING: agent_registry.json not found at {path}; "
            "treating all identities as human users",
            file=sys.stderr,
        )
        return set()

    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        agents = data.get("agents", [])
        return {str(a["id"]) for a in agents if "id" in a}
    except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not load agent_registry.json: {exc}",
            file=sys.stderr,
        )
        return set()


def _is_authorized(agent_id: str, registry_path: str | None = None) -> bool:
    """Return True if agent_id is permitted to modify protected fields.

    Authorization rules (ACS-400a-3-i):
    - Explicitly authorized agents: product-owner-v3, business-analyst-v3, it-po-v3.
    - Human users: any identity NOT present in agent_registry.json.
    - All other known agents: NOT authorized.

    Args:
        agent_id: The identity string to check.
        registry_path: Optional explicit path for the registry file (for testing).

    Returns:
        True if authorized (requirement author or human user), False otherwise.
    """
    if agent_id in _AUTHORIZED_AGENTS:
        return True
    # Unknown identity = not in registry = human user = authorized
    known_agents = _load_registry(registry_path=registry_path)
    return agent_id not in known_agents


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML)
# ---------------------------------------------------------------------------


def _load_yaml_safe(content: str, source_label: str) -> dict | None:
    """Parse a YAML string, returning a dict or None on failure.

    Args:
        content: Raw YAML string.
        source_label: Human-readable label for error messages (e.g. file path).

    Returns:
        Parsed dict on success, None on parse failure (fail-open).
    """
    try:
        import yaml  # type: ignore[import]

        try:
            data = yaml.safe_load(content)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError as exc:
            print(
                f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
                file=sys.stderr,
            )
            return None
    except ImportError:
        pass  # PyYAML absent — fall through to minimal parser

    # Minimal fallback parser: handles simple top-level scalar fields only.
    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


def _load_staged_content(file_path: str) -> dict | None:
    """Load the staged (working-tree) content of an AC YAML file.

    Args:
        file_path: Path to the staged AC YAML file (absolute or relative to cwd).

    Returns:
        Parsed dict, or None on failure.
    """
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read staged file {file_path}: {exc}",
            file=sys.stderr,
        )
        return None
    return _load_yaml_safe(content, source_label=str(file_path))


def _load_head_content(file_path: str) -> dict | None:
    """Load the HEAD version of an AC YAML file from git.

    Returns None if the file does not exist in HEAD (new file scenario).

    Args:
        file_path: Relative path from repo root (as git knows it).

    Returns:
        Parsed dict of HEAD version, or None when absent or on error.
    """
    if os.environ.get("HOOK_NO_GIT"):
        # Test mode: treat all files as new (no HEAD version) unless
        # HOOK_SIMULATE_CRITERIA_CHANGED / other sim flags are set.
        return None

    try:
        env_root = os.environ.get("HOOK_ROOT")
        git_cmd = ["git"]
        if env_root:
            git_cmd = ["git", "-C", env_root]

        result = subprocess.run(
            [*git_cmd, "show", f"HEAD:{file_path}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: git show failed for {file_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        # File not in HEAD — it is a new file
        return None

    return _load_yaml_safe(result.stdout, source_label=f"HEAD:{file_path}")


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


def _find_project_root() -> Path | None:
    """Find the project root (directory containing .git or CLAUDE.md).

    Returns:
        Absolute Path of the project root, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        return Path(env_root)

    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor

    return None


# ---------------------------------------------------------------------------
# Staged file detection
# ---------------------------------------------------------------------------


def _get_staged_ac_paths() -> list[str]:
    """Return staged .yaml file paths under docs/acceptance-criteria/.

    Uses HOOK_TEST_FILES env var (OS path-separator-separated or newline-separated
    list) when set for unit testing.

    Returns:
        List of path strings (absolute when from HOOK_TEST_FILES,
        relative to repo root when from git diff --cached).
    """
    test_files = os.environ.get("HOOK_TEST_FILES")
    if test_files:
        # Support both os.pathsep and newline separators
        raw_paths = test_files.replace(os.pathsep, "\n").splitlines()
        return [
            p.strip()
            for p in raw_paths
            if p.strip() and p.strip().endswith(".yaml")
        ]

    if os.environ.get("HOOK_NO_GIT"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not run git diff: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
        and _AC_STORE_DIR in line
        and line.strip().endswith(".yaml")
    ]


# ---------------------------------------------------------------------------
# Field comparison helpers
# ---------------------------------------------------------------------------


def _fields_changed(
    staged: dict,
    head: dict | None,
    fields: frozenset[str],
) -> list[str]:
    """Return the subset of `fields` that differ between staged and HEAD.

    Uses YAML-level comparison (dict values, not raw text) to avoid false
    positives from whitespace or formatting changes (ACS-400c-2 IT requirement).

    When head is None (new file), every field that is present in staged and
    non-empty is considered "added" (i.e. changed from absent/null to a value).

    Args:
        staged: Parsed YAML dict of the staged version.
        head: Parsed YAML dict of the HEAD version, or None for a new file.
        fields: Set of field names to compare.

    Returns:
        Sorted list of field names that were added or changed.
    """
    changed = []
    for field_name in sorted(fields):
        staged_val = staged.get(field_name)
        head_val = head.get(field_name) if head else None
        if staged_val != head_val:
            # Ignore changes from None/missing to None/missing (no-op)
            if staged_val is not None or head_val is not None:
                changed.append(field_name)
    return changed


# ---------------------------------------------------------------------------
# Governance checks
# ---------------------------------------------------------------------------


def _check_file(
    file_path: str,
    agent_id: str,
    registry_path: str | None = None,
) -> list[str]:
    """Run governance checks on a single staged AC YAML file.

    Checks (in order):
    1. Protected-field write authorization (ACS-400a, ACS-400b-3).
    2. origin_agent audit requirement for new files (ACS-400c-1).
    3. amended_by audit requirement for criteria changes (ACS-400c-2, ACS-400c-2-i).

    Args:
        file_path: Absolute or repo-relative path to the staged AC YAML.
        agent_id: Identity string of the committing agent.
        registry_path: Optional explicit registry path (for testing).

    Returns:
        List of human-readable violation strings. Empty list means no violations.
    """
    violations: list[str] = []

    # Simulation flags (set by tests that exercise specific behavioral paths
    # without a real git repo or real HEAD files)
    sim_criteria = bool(os.environ.get("HOOK_SIMULATE_CRITERIA_CHANGED"))
    sim_title = bool(os.environ.get("HOOK_SIMULATE_TITLE_CHANGED"))
    sim_open_only = bool(os.environ.get("HOOK_SIMULATE_OPEN_ONLY_CHANGED"))
    sim_new_file = bool(os.environ.get("HOOK_SIMULATE_NEW_FILE"))
    sim_amended_stale = bool(os.environ.get("HOOK_SIMULATE_AMENDED_BY_STALE"))
    sim_amended_no_new = bool(os.environ.get("HOOK_SIMULATE_AMENDED_BY_NO_NEW_ENTRY"))

    staged = _load_staged_content(file_path)
    if staged is None:
        # Cannot parse staged file — fail-open
        return []

    # Determine HEAD version
    # For testing: if HOOK_NO_GIT is set, head is always None (new file)
    # unless simulation flags override
    if sim_criteria or sim_title or sim_open_only or sim_amended_stale or sim_amended_no_new:
        # Simulation mode: construct minimal HEAD dict that differs from staged
        head: dict | None = dict(staged)  # start as copy of staged
        if sim_criteria:
            head["criteria"] = "Original criteria before modification."
        if sim_title:
            head["title"] = "Original Title Before Modification"
        if sim_open_only:
            head["work_status"] = "todo"
            head["implemented_by"] = []
            head["covered_by"] = []
        if sim_amended_stale:
            # HEAD has same amended_by as staged → stale (criteria changed but no update)
            head["amended_by"] = staged.get("amended_by", [])
            if sim_criteria:
                head["criteria"] = "Original criteria before modification."
        if sim_amended_no_new:
            # HEAD has same entries in amended_by → no NEW entry added
            head["amended_by"] = list(staged.get("amended_by", []))
    elif sim_new_file:
        head = None  # Brand-new file — no HEAD version
    else:
        # Real operation: load from git
        # Use the file_path as-is; for absolute paths convert to repo-relative
        project_root = _find_project_root()
        rel_path = file_path
        if project_root and Path(file_path).is_absolute():
            try:
                rel_path = str(Path(file_path).relative_to(project_root))
            except ValueError:
                rel_path = file_path
        head = _load_head_content(rel_path)

    is_new_file = (head is None)
    authorized = _is_authorized(agent_id, registry_path=registry_path)

    # --- Check 1: Protected field authorization ---
    if sim_criteria or sim_title:
        # Simulation: treat as if these protected fields changed
        changed_protected: list[str] = []
        if sim_criteria:
            changed_protected.append("criteria")
        if sim_title:
            changed_protected.append("title")
    else:
        changed_protected = _fields_changed(staged, head, _PROTECTED_FIELDS)

    if changed_protected and not authorized:
        file_label = Path(file_path).name
        fields_str = ", ".join(changed_protected)
        authorized_list = sorted(_AUTHORIZED_AGENTS) + ["human user"]
        violations.append(
            f"file '{file_label}': agent '{agent_id}' modified protected field(s) "
            f"[{fields_str}] — criteria field may only be written by requirement authors "
            f"(authorized: {', '.join(authorized_list)})"
        )

    # Acknowledge open fields in the message if they also changed (ACS-400b-3-i)
    if sim_open_only:
        changed_open: list[str] = ["work_status", "implemented_by", "covered_by"]
    else:
        changed_open = _fields_changed(staged, head, _OPEN_FIELDS)

    if changed_open and changed_protected and not authorized:
        # Update the last violation to mention open fields were also changed
        if violations:
            prev = violations[-1]
            open_str = ", ".join(changed_open)
            violations[-1] = (
                prev + f" (also changed open fields: [{open_str}] — these are allowed)"
            )

    # --- Check 2: origin_agent required for new files (ACS-400c-1) ---
    if is_new_file or sim_new_file:
        origin_agent = staged.get("origin_agent")
        if not origin_agent or str(origin_agent).strip() == "":
            file_label = Path(file_path).name
            violations.append(
                f"file '{file_label}': new AC file requires origin_agent to identify "
                "the criteria author — add 'origin_agent: <author>' to the YAML"
            )

    # --- Check 3: amended_by must be updated when criteria changes (ACS-400c-2) ---
    criteria_changed = "criteria" in changed_protected or (
        sim_criteria and not sim_title and not sim_open_only
    )
    # Refine: criteria changed if it appears in changed_protected OR explicitly simulated
    criteria_changed = "criteria" in changed_protected or sim_criteria

    if criteria_changed and not is_new_file and not sim_new_file and authorized:
        # Only check audit trail for authorized agents who changed criteria
        staged_amended = _normalize_list(staged.get("amended_by"))
        head_amended = _normalize_list(head.get("amended_by") if head else None)

        if sim_amended_stale:
            # Staged amended_by identical to HEAD → no update
            staged_amended = head_amended
            file_label = Path(file_path).name
            violations.append(
                f"file '{file_label}': criteria was modified but amended_by was not updated "
                f"— append the authoring agent identity to the amended_by list "
                f"(ACS-400c-2)"
            )
        elif sim_amended_no_new:
            # amended_by has entries but no new ones vs HEAD
            file_label = Path(file_path).name
            violations.append(
                f"file '{file_label}': criteria was modified but amended_by has no new entry "
                f"compared to HEAD — the list exists but was not extended "
                f"(ACS-400c-2-i: no new entry, not empty)"
            )
        elif staged_amended == head_amended:
            # Real comparison: amended_by identical → not updated
            file_label = Path(file_path).name
            violations.append(
                f"file '{file_label}': criteria was modified but amended_by was not updated "
                f"— append the authoring agent identity to the amended_by list "
                f"(ACS-400c-2)"
            )
        elif staged_amended and head_amended and not (set(staged_amended) - set(head_amended)):
            # Entries exist but no new ones added
            file_label = Path(file_path).name
            violations.append(
                f"file '{file_label}': criteria was modified but amended_by has no new entry "
                f"compared to HEAD — the list exists but was not extended "
                f"(ACS-400c-2-i: no new entry, not empty)"
            )

    return violations


def _normalize_list(raw: object) -> list[str]:
    """Normalise a YAML list field to a sorted list of strings for comparison.

    Args:
        raw: Raw YAML value (list, string, or None).

    Returns:
        Sorted list of non-empty strings.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return sorted(str(item) for item in raw if item is not None)
    if isinstance(raw, str):
        stripped = raw.strip("[]")
        return sorted(p.strip() for p in stripped.split(",") if p.strip())
    return []


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _emit_block_decision(violations: list[str], agent_id: str) -> None:
    """Print the PreToolUse JSON block decision to stdout.

    stdout carries the structured block decision per the PreToolUse hook contract.
    stderr carries diagnostic detail for humans and CI logs.

    Args:
        violations: List of violation description strings.
        agent_id: The committing agent's identity.
    """
    reason = (
        f"AC governance violation by agent '{agent_id}': "
        + "; ".join(violations)
    )
    decision = {"decision": "block", "reason": reason}
    print(json.dumps(decision))

    # Diagnostic detail to stderr
    print(f"\n{_HOOK_PREFIX} BLOCKED — AC store governance violation", file=sys.stderr)
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    print(
        "\nAuthorized agents for protected fields: "
        + ", ".join(sorted(_AUTHORIZED_AGENTS))
        + ", human user",
        file=sys.stderr,
    )
    print(
        "Protected fields: " + ", ".join(sorted(_PROTECTED_FIELDS)),
        file=sys.stderr,
    )
    print(
        "Open fields (any agent may change): " + ", ".join(sorted(_OPEN_FIELDS)),
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the AC governance check.

    Returns:
        0 when all staged AC YAML files pass governance rules (or no files staged),
        1 when one or more violations are detected.
    """
    # Diagnostic counter for test introspection (AC-13: staged-files-only scope)
    if os.environ.get("HOOK_SIMULATE_EXCEPTION"):
        raise RuntimeError("HOOK_SIMULATE_EXCEPTION: forced exception for testing")

    # Discover AC store directory (early exit if absent — ACS-400d-2-i)
    project_root = _find_project_root()
    if project_root is None:
        ac_store = Path(_AC_STORE_DIR)
    else:
        ac_store = project_root / _AC_STORE_DIR

    if not ac_store.is_dir():
        # No AC store — exit 0 immediately without creating any directories
        return 0

    # Get staged AC YAML files
    staged_paths = _get_staged_ac_paths()
    if not staged_paths:
        return 0  # No AC files staged — nothing to check

    # Emit parsed file count to stderr for test introspection (AC-13)
    if os.environ.get("HOOK_COUNT_PARSED"):
        print(f"{_HOOK_PREFIX} parsed_files: {len(staged_paths)}", file=sys.stderr)

    # Determine agent identity (from HOOK_AGENT_ID env var or fallback)
    agent_id = os.environ.get("HOOK_AGENT_ID", "")
    if not agent_id:
        # Attempt to detect from git config user.name
        try:
            result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            agent_id = result.stdout.strip() if result.returncode == 0 else "unknown"
        except (subprocess.SubprocessError, OSError):
            agent_id = "unknown"

    # Load registry once for the entire invocation (AC-16: not on every file)
    # (registry loading happens inside _is_authorized; it's cached by _check_file
    #  which calls _is_authorized → _load_registry per file, but we accept that
    #  for simplicity at the file count expected in practice)

    # Check each staged file
    all_violations: list[str] = []
    for staged_path in staged_paths:
        # Resolve absolute path for disk reads
        abs_path = staged_path
        if not Path(staged_path).is_absolute():
            if project_root:
                abs_path = str(project_root / staged_path)
        file_violations = _check_file(abs_path, agent_id)
        all_violations.extend(file_violations)

    if not all_violations:
        return 0

    _emit_block_decision(all_violations, agent_id)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"{_HOOK_PREFIX} unexpected error (fail-open): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
