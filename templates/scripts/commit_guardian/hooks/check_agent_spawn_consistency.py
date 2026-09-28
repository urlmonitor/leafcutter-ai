"""
MODULE: check_agent_spawn_consistency
GOAL: Pre-commit hook that validates bidirectional spawn consistency in
    config/agent_registry.json when it is staged for commit, and that
    generated agent cards mirror the registry's spawn relationships.
BUSINESS CONTEXT: The agent registry is the single source of truth for spawn
    relationships. Bidirectional mismatches (agent A lists B in spawn_allowlist
    but B does not list A in spawned_by, or vice versa) cause runtime failures
    that are hard to diagnose. Additionally, generated agent cards must agree
    with the registry — a card that shows a spawn edge the registry does not
    have (or vice versa) silently misleads readers. This hook catches both
    asymmetric spawn relationships and card<->registry mirror mismatches at
    commit time so engineers receive immediate named-pair error messages before
    bad registry or card state reaches main.
ARCHITECTURE: Standalone script (no leafcutter-internal package imports).
    Reads the staged registry JSON via _read_registry_json() (patchable for
    unit tests). Checks both directions of the spawn relationship in two
    passes: (1) spawn_allowlist → spawned_by, (2) spawned_by → spawn_allowlist.
    Also checks card<->registry mirror: parses the mermaid spawn diagram in
    each docs/agents/cards/<id>.card.md and compares against the registry
    spawn_allowlist and spawned_by for that agent (both directions).
    Skips __ticket_phase_agents__ special token and every recognized external
    caller (AC INF-600k-1): the literal "user" trigger, or the filename of a
    workflow that really exists under the package's templates/workflows-js/
    (falling back to .claude/workflows/ only when that source directory is
    entirely absent). That classification is defined ONCE in
    agent_spawn_external_callers.py, a sibling file in this same
    commit_guardian/ directory that build_commit_guardian() always deploys
    alongside this hook -- imported via an adjacent sys.path entry rather
    than a leafcutter-internal package import, so the import still resolves
    when this file runs as the deployed
    .leafcutter/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py
    in a consumer project with no scripts/ package on its Python path.
    Emits structured errors to stderr naming both agents involved in any
    asymmetry or mismatch per AC INF-600g-1 and INF-600l-1. Triggers when
    config/agent_registry.json OR any docs/agents/cards/*.card.md is staged.

    PACKAGE-ROOT RESOLUTION (GE-113c-1-vi, AC INF-600k-1): the package root
    used for is_recognized_external_caller() is found the same way
    check_agent_registry.py finds it -- via the shared
    _resolve_root.resolve_package_root(), never a hand-rolled git rev-parse.
    Unlike that hook, a missing manifest here WARNS and falls back to
    _resolve_root.find_project_root() rather than blocking the commit: this
    hook validates spawn consistency, and AC INF-600k-1 does not require
    blocking on a missing manifest, so it mirrors check_build_drift.py's /
    check_output_drift.py's warn-and-continue policy instead (see
    _resolve_package_root()). That resolved package_root is a DIFFERENT root
    from the one used to find docs/agents/cards/ (still
    _resolve_root.find_project_root() directly) -- see main()'s own comment
    for why those two must not be conflated.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_spawn_external_callers import is_recognized_external_caller  # noqa: E402
from card_mermaid_parser import parse_card_spawn_edges  # noqa: E402
from _resolve_root import find_project_root, resolve_package_root  # noqa: E402

_HOOK_FILE = Path(__file__).resolve()
_parse_card_spawn_edges = parse_card_spawn_edges  # back-compat alias (moved to card_mermaid_parser.py)

_REGISTRY_PATH = "config/agent_registry.json"
_CARDS_DIR_PATH = "docs/agents/cards"
_SPECIAL_TOKEN = "__ticket_phase_agents__"


def _get_staged_files() -> list[str]:
    """Return the list of staged file paths from git.

    Returns:
        List of staged file path strings relative to the repo root.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACRM"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        print(f"[check-agent-spawn-consistency] ERROR: git diff failed: {exc}", file=sys.stderr)
        return []
    return result.stdout.strip().splitlines()


def _read_registry_json() -> str:
    """Read the staged registry JSON from the git index.

    Returns the raw JSON string of the staged config/agent_registry.json.

    Returns:
        Raw JSON content of the registry file.

    Raises:
        OSError: If the file cannot be read from the git index.
    """
    try:
        result = subprocess.run(
            ["git", "show", f":0:{_REGISTRY_PATH}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        raise OSError(f"Cannot read staged {_REGISTRY_PATH}: {exc}") from exc  # noqa: TRY003
    if result.returncode != 0:
        # Fallback: read directly from disk (for edge cases where git show fails)
        try:
            repo_root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            return Path(repo_root, _REGISTRY_PATH).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise  # Propagate as-is so main() advisory branch fires (not an error)
        except OSError as exc:
            raise OSError(f"Cannot read {_REGISTRY_PATH}: {exc}") from exc  # noqa: TRY003
    return result.stdout


def _check_asymmetric_spawns(agents: list[dict], package_root: Path) -> list[str]:
    """Check for asymmetric spawn relationships in the agent list.

    Performs two passes:
    1. For each agent A with spawn_allowlist entry B: verify B.spawned_by includes A.
    2. For each agent A with spawned_by entry B: verify B.spawn_allowlist includes A.

    Skips __ticket_phase_agents__ token and every recognized external caller
    (AC INF-600k-1's is_recognized_external_caller: the literal "user"
    trigger, or a real workflow filename).

    Args:
        agents: List of agent dicts from the registry.
        package_root: Absolute path to the package root (for resolving real
            workflow filenames as recognized external callers). main()
            resolves this via _resolve_package_root(), the GE-113c-1-vi
            manifest-based lookup (it_requirement #3).

    Returns:
        List of "asymmetric spawn:" error strings, one per asymmetric pair found.
        Empty list means all relationships are bidirectionally consistent.
    """
    registry_ids = {a["id"] for a in agents if "id" in a}
    spawn_map = {a["id"]: a.get("spawn_allowlist", []) for a in agents if "id" in a}
    spawned_by_map = {a["id"]: a.get("spawned_by", []) for a in agents if "id" in a}

    errors: list[str] = []

    # Pass 1: spawn_allowlist → spawned_by
    for agent_id, allowlist in spawn_map.items():
        for child_id in allowlist:
            if child_id == _SPECIAL_TOKEN:
                continue
            if child_id not in registry_ids:
                continue  # Unknown agents are caught by other validators
            child_spawned_by = spawned_by_map.get(child_id, [])
            if agent_id not in child_spawned_by and not is_recognized_external_caller(agent_id, package_root):
                errors.append(
                    f"asymmetric spawn: {agent_id}.spawn_allowlist includes {child_id}, "
                    f"but {child_id}.spawned_by does not include {agent_id}"
                )

    # Pass 2: spawned_by → spawn_allowlist
    for agent_id, spawners in spawned_by_map.items():
        for parent_id in spawners:
            if is_recognized_external_caller(parent_id, package_root):
                continue
            if parent_id not in registry_ids:
                continue  # Unknown agents are caught by other validators
            parent_allowlist = spawn_map.get(parent_id, [])
            if agent_id not in parent_allowlist and _SPECIAL_TOKEN not in parent_allowlist:
                errors.append(
                    f"asymmetric spawn: {agent_id}.spawned_by includes {parent_id}, "
                    f"but {parent_id}.spawn_allowlist does not include {agent_id}"
                )

    return errors


def _get_repo_root() -> Path:
    """Get the repository root path via git rev-parse.

    Used for docs/agents/cards/ resolution (_resolve_cards_dir) only -- a
    DIFFERENT need from _resolve_package_root() below: cards-dir and
    skills_config.json are workspace-level and not necessarily inside the
    manifest-derived package_root in a consumer layout that vendors the
    package as a subdirectory.

    Returns:
        Absolute path to the git repository root.

    Raises:
        OSError: If git rev-parse fails or returns no output.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        raise OSError(f"Cannot determine repo root via git: {exc}") from exc  # noqa: TRY003
    if result.returncode != 0 or not result.stdout.strip():
        raise OSError("git rev-parse --show-toplevel returned no output")  # noqa: TRY003
    return Path(result.stdout.strip())


def _resolve_package_root() -> Path:
    """Resolve the package root the GE-113c-1-vi way (AC INF-600k-1).

    Delegates to ``_resolve_root.resolve_package_root()`` — the SAME lookup
    check_agent_registry.py uses — rather than a hand-rolled ``git
    rev-parse`` (the prior placeholder). Unlike check_agent_registry.py, this
    hook's own policy on a miss is WARN, not block: it validates spawn
    consistency, and AC INF-600k-1 does not require blocking the commit when
    no manifest can be found. This mirrors check_build_drift.py's /
    check_output_drift.py's warn-and-continue policy on the identical
    missing-manifest condition (a fresh clone with no manifest yet must not
    self-block) rather than check_agent_registry.py's block policy (a
    different gate's different criterion — see ``_resolve_root.py``'s own
    "POLICY IS NOT SHARED" docstring note).

    Returns:
        The resolved package root, or ``_resolve_root.find_project_root()``
        (the repo root) with a WARNING to stderr when no manifest could be
        located. Never raises, never returns ``None``.
    """
    package_root, tried = resolve_package_root(_HOOK_FILE)
    if package_root is not None:
        return package_root
    tried_str = "\n  ".join(tried)
    print(
        "[check-agent-spawn-consistency] WARNING: no .build_manifest.json "
        f"resolved a package root; falling back to the repo root. Tried:\n  {tried_str}",
        file=sys.stderr,
    )
    return find_project_root()


def _resolve_cards_dir(repo_root: Path) -> Path:
    """Resolve the agent cards directory from the card-path convention.

    Checks for 'agent_cards_path' in skills_config.json at the repo root or
    under .leafcutter/. Falls back to the hardcoded default 'docs/agents/cards'
    when absent or unreadable.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        Absolute path to the agent cards directory (may not exist on disk).
    """
    _DEFAULT_CARDS_SUBDIR = "docs/agents/cards"
    config_locations = [
        repo_root / "skills_config.json",
        repo_root / ".leafcutter" / "skills_config.json",
    ]
    for config_path in config_locations:
        if not config_path.exists():
            continue
        try:
            config_text = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"[check-agent-spawn-consistency] WARNING: Cannot read {config_path}: {exc}",
                file=sys.stderr,
            )
            continue
        try:
            config_data = json.loads(config_text)
        except json.JSONDecodeError as exc:
            print(
                f"[check-agent-spawn-consistency] WARNING: {config_path} is not valid JSON: {exc}",
                file=sys.stderr,
            )
            continue
        agent_cards_path = config_data.get("agent_cards_path")
        if agent_cards_path:
            return repo_root / agent_cards_path
    return repo_root / _DEFAULT_CARDS_SUBDIR


def _check_card_registry_mirror(
    agents: list[dict],
    cards_dir: Path,
    package_root: Path | None = None,
) -> list[str]:
    """Check for mismatches between agent cards and the registry spawn relationships.

    For each registry agent that has a generated card file under *cards_dir*,
    compares the spawn edges shown in the card's mermaid diagram against the
    registry's spawn_allowlist and spawned_by fields. Reports mismatches in
    both directions:

    Direction 1 (card → registry): card shows a spawn edge the registry lacks.
    Direction 2 (registry → card): registry records an edge the card does not show.

    The same two-direction check is applied to both spawn_allowlist (``-->|spawns|``)
    and spawned_by (``-->|dispatches|``) edges.

    Emits an advisory note to stderr for agents whose card file does not exist
    (naming the agent and path) then skips them — the absence of a card file
    is not treated as a mismatch. Skips __ticket_phase_agents__ and every
    recognized external caller in the same way as _check_asymmetric_spawns()
    (this is the load-bearing check for rejecting an unrecognized spawned_by
    entry as an unknown agent, Direction 2b below).

    Args:
        agents: List of agent dicts from the registry.
        cards_dir: Absolute path to the directory containing .card.md files.
        package_root: Absolute path to the package root (for resolving real
            workflow filenames as recognized external callers). Defaults to
            the current working directory when omitted -- callers that only
            exercise agent-id / literal-"user" / special-token classification
            (unaffected by the workflow directory's contents) may omit it.
            main() always passes it explicitly, via _resolve_package_root().

    Returns:
        List of human-readable mismatch error strings. Empty list when all
        cards agree with the registry.
    """
    resolved_root = package_root if package_root is not None else Path.cwd()
    errors: list[str] = []

    # Expand __ticket_phase_agents__ macro to the concrete set of ticket-phase agent IDs.
    # A card-spawn edge to any agent in this set is suppressed when the registry uses the
    # macro — it is covered implicitly. Genuine extra edges (agents NOT in the set) are
    # still flagged, avoiding the previous blanket-suppression that silently missed them.
    ticket_phase_ids: frozenset[str] = frozenset(
        a["id"] for a in agents if a.get("is_ticket_phase", False) and "id" in a
    )

    for entry in agents:
        agent_id = entry.get("id")
        if not agent_id:
            continue

        card_path = cards_dir / f"{agent_id}.card.md"
        if not card_path.exists():
            print(
                f"[check-agent-spawn-consistency] ADVISORY: card for '{agent_id}' not found at "
                f"{card_path} — mirror comparison skipped for this agent",
                file=sys.stderr,
            )
            continue

        try:
            card_text = card_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"[check-agent-spawn-consistency] WARNING: Cannot read card "
                f"{card_path}: {exc}",
                file=sys.stderr,
            )
            continue

        card_spawn, card_spawned_by = parse_card_spawn_edges(card_text, agent_id)
        reg_spawn: set[str] = set(entry.get("spawn_allowlist", []))
        reg_spawned_by: set[str] = set(entry.get("spawned_by", []))

        # Direction 1a: card shows spawn edge not in registry spawn_allowlist.
        # When the registry uses the __ticket_phase_agents__ macro, card edges to any
        # ticket-phase agent are covered by the macro and are suppressed.  Edges to
        # agents NOT in the ticket-phase set are still flagged (no blanket suppression).
        for child in sorted(card_spawn):
            if child == _SPECIAL_TOKEN:
                continue
            if _SPECIAL_TOKEN in reg_spawn and child in ticket_phase_ids:
                continue  # Covered by __ticket_phase_agents__ macro
            if child not in reg_spawn:
                errors.append(
                    f"{agent_id} card shows spawn edge to {child}, "
                    f"but the registry has no such edge"
                )

        # Direction 1b: registry spawn_allowlist has edge the card does not show
        for child in sorted(reg_spawn):
            if child == _SPECIAL_TOKEN:
                continue
            if child not in card_spawn:
                errors.append(
                    f"{agent_id}'s registry entry shows spawn edge to {child}, "
                    f"but the card does not show it"
                )

        # Direction 2a: card shows dispatches edge not in registry spawned_by
        for parent in sorted(card_spawned_by):
            if is_recognized_external_caller(parent, resolved_root):
                continue
            if parent not in reg_spawned_by:
                errors.append(
                    f"{agent_id} card shows {parent} dispatches it, "
                    f"but the registry has no such edge"
                )

        # Direction 2b: registry spawned_by has edge the card does not show
        for parent in sorted(reg_spawned_by):
            if is_recognized_external_caller(parent, resolved_root):
                continue
            if parent not in card_spawned_by:
                errors.append(
                    f"{agent_id}'s registry entry shows {parent} spawns it, "
                    f"but the card does not show it"
                )

    return errors


def main() -> int:
    """Run the spawn consistency pre-commit hook.

    Triggers when config/agent_registry.json OR any docs/agents/cards/*.card.md
    is staged.

    Returns:
        0 if no relevant files are staged, relationships are consistent, or no
        agents are present. 1 if asymmetric spawn relationships or card<->registry
        mirror mismatches are detected, or the registry cannot be read.
    """
    staged = _get_staged_files()

    registry_staged = _REGISTRY_PATH in staged
    cards_staged = any(
        f.startswith(_CARDS_DIR_PATH + "/") and f.endswith(".card.md")
        for f in staged
    )

    if not registry_staged and not cards_staged:
        return 0

    try:
        registry_json = _read_registry_json()
    except FileNotFoundError:
        print(
            f"[check-agent-spawn-consistency] ADVISORY: No agent registry found at "
            f"{_REGISTRY_PATH}. Check skipped for projects without the agent subsystem.",
            file=sys.stderr,
        )
        return 0
    except OSError as exc:
        print(
            f"[check-agent-spawn-consistency] ERROR: Cannot read {_REGISTRY_PATH}: {exc}",
            file=sys.stderr,
        )
        return 1

    try:
        data = json.loads(registry_json)
    except json.JSONDecodeError as exc:
        print(
            f"[check-agent-spawn-consistency] ERROR: {_REGISTRY_PATH} is not valid JSON: {exc}",
            file=sys.stderr,
        )
        return 1

    agents = data.get("agents", [])
    if not agents:
        return 0

    # Resolved ONCE, threaded into both checks below (a DIFFERENT root from
    # repo_root below -- see _resolve_package_root()'s docstring).
    package_root = _resolve_package_root()

    errors: list[str] = []

    # Asymmetric registry-only check (only when registry itself is staged)
    if registry_staged:
        errors.extend(_check_asymmetric_spawns(agents, package_root))

    # Card<->registry mirror check (runs whenever registry OR cards are staged)
    try:
        repo_root = _get_repo_root()
    except OSError as exc:
        print(
            f"[check-agent-spawn-consistency] WARNING: Cannot determine repo root "
            f"for card mirror check: {exc}",
            file=sys.stderr,
        )
        repo_root = None

    if repo_root is not None:
        cards_dir = _resolve_cards_dir(repo_root)
        if not cards_dir.exists():
            print(
                f"[check-agent-spawn-consistency] ADVISORY: Agent cards directory not found at "
                f"{cards_dir}. Mirror check skipped — project may not use the leafcutter agent subsystem.",
                file=sys.stderr,
            )
        else:
            errors.extend(_check_card_registry_mirror(agents, cards_dir, package_root))

    if not errors:
        return 0

    print(
        f"[check-agent-spawn-consistency] Asymmetric spawn relationship(s) or "
        f"card<->registry mirror mismatch(es) found in {_REGISTRY_PATH}:",
        file=sys.stderr,
    )
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print(
        f"\nFix the above mismatches in {_REGISTRY_PATH} or regenerate agent "
        f"cards before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/01]: Initial
#   implementation. AC INF-600g-1: validates bidirectional spawn consistency
#   when config/agent_registry.json is staged. Two-pass check:
#   (1) spawn_allowlist → spawned_by (2) spawned_by → spawn_allowlist.
#   Skips __ticket_phase_agents__ special token and external callers.
#   Error format: "asymmetric spawn: A.spawn_allowlist includes B, but
#   B.spawned_by does not include A" (and vice versa).
#   Standalone — no leafcutter-internal imports for portability.
#   (#EPIC-SelfDescribingAgentsCorrections/01)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/01]: Card<->registry
#   mirror check (AC INF-600l-1). Extended with four new helpers:
#   _get_repo_root(), _node_id_to_agent_id(), _parse_card_spawn_edges(),
#   _check_card_registry_mirror(). Hook now also triggers when any
#   docs/agents/cards/*.card.md is staged. Mirror check parses the mermaid
#   spawn diagram in each card and compares spawn_allowlist and spawned_by
#   against the registry in both directions. Error format:
#   "{agent} card shows spawn edge to {child}, but the registry has no such edge"
#   (and the four symmetric variants). _SPECIAL_TOKEN handled via
#   _node_id_to_agent_id() identity case. Asymmetric registry check still
#   only runs when the registry itself is staged (cards_staged-only runs skip it).
#   (#EPIC-RegistryCardMirror/01)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/02]: Absent-card advisory
#   (AC INF-600l-1-i). When _check_card_registry_mirror() encounters an agent
#   whose card file does not exist on disk, it now emits an ADVISORY message to
#   stderr naming the agent and path before continuing, instead of silently
#   skipping. This makes the skip visible without treating the absence as a
#   mismatch. Registry-internal spawn-consistency check is unaffected.
#   Message format:
#   "[check-agent-spawn-consistency] ADVISORY: card for '{id}' not found at
#   {path} — mirror comparison skipped for this agent"
#   (#EPIC-RegistryCardMirror/02)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/03]: Registry-absent no-op
#   (AC INF-600l-1-ii). When the agent registry is entirely absent (FileNotFoundError
#   from _read_registry_json()), main() now exits 0 with an ADVISORY message
#   instead of exiting 1 with an ERROR. This prevents the hook from blocking
#   projects that do not use the leafcutter agent subsystem at all.
#   FileNotFoundError is caught before the generic OSError clause so that
#   genuinely unreadable registries (PermissionError etc.) still exit 1.
#   Advisory message format:
#   "[check-agent-spawn-consistency] ADVISORY: No agent registry found at
#   config/agent_registry.json. Check skipped for projects without the agent
#   subsystem."
#   (#EPIC-RegistryCardMirror/03)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/04]: Convention-based card-path
#   resolution and opt-in subsystem scoping (AC INF-600l-2). Added _resolve_cards_dir()
#   helper that reads agent_cards_path from skills_config.json (at repo root or .leafcutter/)
#   and falls back to 'docs/agents/cards' when absent. main() now uses _resolve_cards_dir()
#   instead of hardcoded _CARDS_DIR_PATH for the mirror check. Added opt-in gate: when
#   the resolved cards directory does not exist on disk, main() emits an ADVISORY and
#   skips the mirror check (project does not use the leafcutter agent subsystem).
#   (#EPIC-RegistryCardMirror/04)
#
# - 2026-07-07 [python-coder/EPIC-RegistryCardMirror/remediation]: Four defect fixes.
#   DEFECT 1: _read_registry_json() disk-fallback now catches FileNotFoundError
#   before the generic OSError clause and re-raises it unchanged, so main()'s
#   FileNotFoundError advisory branch fires correctly on the real path (previously
#   the subtype was collapsed into a base OSError → exit 1 instead of exit 0).
#   DEFECT 3: _check_card_registry_mirror() Direction 1a no longer blanket-suppresses
#   ALL card→registry extra-edge reporting when __ticket_phase_agents__ appears in the
#   registry. Instead, the macro is expanded to the concrete set of ticket-phase agent
#   IDs; only edges to agents in that set are suppressed — genuine extra edges (to
#   non-phase agents) are still flagged. The suppression is now symmetric: both
#   directions use the same expansion logic. ticket_phase_ids is pre-computed once
#   before the agent loop.
#   (#EPIC-RegistryCardMirror/remediation)
# - 2026-09-28 14:00 [python-coder]: AC INF-600k-1: is_recognized_external_caller()
#   replaces _EXTERNAL_CALLERS. (#TICKETLESS reason=inf-600k-1-workflow-callers)
# - 2026-09-28 15:30 [python-coder]: pr-reviewer fixes on AC INF-600k-1:
#   package_root is now threaded explicitly through _check_asymmetric_spawns()
#   and _check_card_registry_mirror() (main() resolves it once via
#   _get_repo_root(), a placeholder for the GE-113c-1-vi resolver landing
#   with PR #943) instead of each call site reaching for Path.cwd(). Restored
#   the 2026-07-06 EPIC-RegistryCardMirror/04 entry above to its original
#   text. Moved _node_id_to_agent_id() and _parse_card_spawn_edges() to the
#   new sibling card_mermaid_parser.py to make room without growing this
#   file past its HEAD line count. (#TICKETLESS reason=inf-600k-1-workflow-callers)
# - 2026-09-28 16:00 [python-coder/AC INF-600k-1, pr-reviewer HIGH-3]: PR #943
#   landed the shared resolver. Added _resolve_package_root(), calling the
#   SAME _resolve_root.resolve_package_root() check_agent_registry.py uses,
#   warning and falling back to find_project_root() on a miss instead of
#   blocking. package_root (is_recognized_external_caller) is now resolved
#   separately from repo_root (_get_repo_root(), for docs/agents/cards/).
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
