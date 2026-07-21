#!/usr/bin/env python3
"""
generate_ticket_from_ac.py — Generate a ticket file from an AC YAML record.

Usage:
    python3 scripts/ac_store/generate_ticket_from_ac.py --ac <ac_id> [options]

Options:
    --ac AC_ID              AC id to generate a ticket for (required).
    --ac-root PATH          Root directory of the AC store (default:
                            docs/acceptance-criteria/ relative to worktree).
    --tickets-root PATH     Root directory for written tickets (default:
                            tickets/00_inbox/ relative to worktree).
    --dry-run               Print the ticket body to stdout without writing.

Exit codes:
    0  Ticket written successfully (or --dry-run printed the body).
    1  AC id not found, the ticket already exists (idempotency guard),
       or a file I/O / YAML error occurred. The error message names the
       affected file.

AC-2: Generator produces a valid ticket from an AC YAML.
AC-3: Generator writes implemented_by back-reference into source AC.
AC-4: Generator is idempotent — re-run with existing ticket exits non-zero.
AC-6: Ticket passes ticket_frontmatter_guard without errors.
"""

from __future__ import annotations

import argparse
import glob as _glob
import importlib.util
import json
import logging
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT = "docs/acceptance-criteria"
_DEFAULT_TICKETS_ROOT = "tickets/00_inbox"

#: doc_links relationships that represent a real edit surface (i.e. the linked
#: file is a file the implementing agent must modify or create). Paths with these
#: relationships enter ``files_touched``. Relationships not in this set (e.g.
#: ``describes``, ``related``) are informational only and must NOT enter
#: ``files_touched``.
_EDIT_SURFACE_RELATIONSHIPS: frozenset[str] = frozenset(
    {"constrains", "creates", "implements", "modifies", "specifies"}
)

#: Recognized file extensions for path detection in prose bullet strings.
#: Only tokens whose final component carries one of these suffixes are treated
#: as source file paths (TKT-500f-8-i path-detection rule).
_PROSE_PATH_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".md", ".yaml", ".yml", ".json", ".js", ".ts", ".sql",
    ".txt", ".toml", ".cfg", ".ini", ".html", ".css", ".sh",
})

#: Documentation and configuration file extensions excluded from source-code
#: detection.  Used to derive _SOURCE_CODE_EXTENSIONS from _PROSE_PATH_EXTENSIONS.
_DOC_CONFIG_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".yaml", ".yml", ".json", ".txt", ".toml", ".cfg", ".ini",
})

#: Recognised source-code file extensions that signal a code-ticket for AC-gate
#: wiring.  Derived from _PROSE_PATH_EXTENSIONS (the prose-path-detection allowlist)
#: by removing documentation and configuration suffixes, then extended with common
#: non-Python and frontend source extensions, then explicitly excluding markup,
#: style, and shell files that must NOT gate AC validation (TKT-500f-14,
#: TKT-500f-14-ii).
#:
#: Excluded (not gating source): .html, .css, .sh — markup/style/shell.
#: Included beyond the derived set: .tsx, .jsx, .vue, .svelte (frontend framework);
#:   .go (Go), .rs (Rust), .mjs (ES module) — common non-Python source languages.
#:
#: DECISION HISTORY:
#:   TKT-500f-14 (prior): initial derivation from _PROSE_PATH_EXTENSIONS.
#:   TKT-500f-14-ii (2026-07-21): Added explicit exclusion of .html/.css/.sh
#:   (markup/style/shell are not gating source code) and added .go/.rs/.mjs so
#:   non-Python source files correctly trigger ac-validator/ac-fulfillment-gate.
_SOURCE_CODE_EXTENSIONS: frozenset[str] = (
    (
        (_PROSE_PATH_EXTENSIONS - _DOC_CONFIG_EXTENSIONS)
        | frozenset({".tsx", ".jsx", ".vue", ".svelte", ".go", ".rs", ".mjs"})
    )
    - frozenset({".html", ".css", ".sh"})
)

#: Known coder agents — any of these as the AC's assigned_agent signals a code
#: ticket regardless of files_touched content (TKT-500f-14).
_KNOWN_CODERS: frozenset[str] = frozenset({"python-coder", "frontend-coder", "sql-coder"})

#: Path prefixes that identify extension-less tokens as source paths.
#: A token that begins with one of these prefixes is included even when it
#: carries no recognized file extension (TKT-500f-8-i path-detection rule).
_KNOWN_PATH_PREFIXES: tuple[str, ...] = (
    "scripts/",
    "docs/",
    "templates/",
    "unit_tests/",
    "tests/",
    "leafcutter/",
    "alembic/",
)

#: Matches candidate path tokens in prose text.
#: Requires at least one ``/`` separator; admits the character set of typical
#: POSIX file paths (alphanumeric, ``_``, ``.``, ``-``, ``/``).  The pattern
#: is anchored so that each match begins and ends on a word character,
#: preventing trailing punctuation from being captured as part of the path.
_PROSE_PATH_TOKEN_RE: re.Pattern[str] = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.\-]*/[A-Za-z0-9_./\-]*[A-Za-z0-9_]"
)

#: Canonical support agents always added to every generated ticket.
_CANONICAL_SUPPORT_AGENTS: list[str] = [
    "test-writer",
    "test-runner",
    "pr-reviewer",
    "commit",
    "pull-request",
]

#: Agents always set to not_needed unless the AC's assigned_agent is sql-coder.
_SQL_AGENTS: list[str] = ["sql-coder"]

#: Agents always set to not_needed in generated tickets.
_NOT_NEEDED_AGENTS: list[str] = [
    "documentation-expert",
]

#: Canonical phase order for agent map output.
_CANONICAL_PHASE_ORDER: list[str] = [
    "architect-review",
    "test-writer",
    "python-coder",
    "sql-coder",
    "test-runner",
    "documentation-expert",
    "pr-reviewer",
    "ac-validator",
    "ac-fulfillment-gate",
    "commit",
    "pull-request",
]

#: Phase order for flow-change pairs: documentation-expert is placed before
#: any coder (priority 4 → doc planning before implementation).
_FLOW_CHANGE_PHASE_ORDER: list[str] = [
    "architect-review",
    "documentation-expert",
    "test-writer",
    "python-coder",
    "sql-coder",
    "test-runner",
    "pr-reviewer",
    "ac-validator",
    "ac-fulfillment-gate",
    "commit",
    "pull-request",
]

#: Default path of the agent registry relative to the repo root.
_DEFAULT_AGENT_REGISTRY = "config/agent_registry.json"

#: Default path of the guardrail gates config relative to the repo root.
_DEFAULT_GUARDRAIL_GATES = "config/guardrail_gates.yaml"

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

AcRecord = dict[str, Any]


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search.

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.

    DECISION HISTORY:
        H-2 reorder (2026-07-21): Moved before ``_load_migration_map`` and the
        module-level ``_COMPONENT_MIGRATION_MAP`` assignment so the fallback branch
        inside ``_load_migration_map`` can call this function at import time without
        a ``NameError``. The definition was previously at ~line 271, AFTER the
        module-level call that could trigger the fallback path.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# Component vocabulary: kebab → underscore normalisation
# ---------------------------------------------------------------------------


def _load_migration_map() -> dict[str, str]:
    """Load the canonical kebab-to-underscore MIGRATION_MAP from the side-effect-free data module.

    MODULE: generate_ticket_from_ac
    GOAL: Resolve the sibling data module at
          ``scripts/ac_store/_component_migration_map.py`` and import its
          ``MIGRATION_MAP`` dict so that the generated ticket's ``components``
          LIST carries the underscore graph id rather than the kebab namespace
          scalar.  The data module contains only the dict literal — no
          logging.basicConfig or other side effects (TKT-500f-18).

    Degradation contract (TKT-500f-18-i):
        - Any exec-phase error (SyntaxError, RuntimeError, OSError, etc.) is
          caught; a WARNING is logged naming the failed source; ``{}`` is
          returned so the module-level assignment never raises.
        - When the data module loads but returns an empty MIGRATION_MAP (e.g.
          in tests that patch importlib), the function falls back to an
          auto-derived map built from docs/components.json so that callers
          still receive a non-empty mapping.

    Returns:
        Mapping from kebab component namespace key to underscore graph id.
        Returns ``{}`` only when exec_module raises; otherwise returns a
        non-empty map sourced from the data module or docs/components.json.

    DECISION HISTORY:
        TKT-500f-18 (2026-07-21): Replaced exec-based load of
        migrate_component_vocab.py (which called logging.basicConfig at module
        level) with _component_migration_map.py — a plain data module with no
        side effects.
        TKT-500f-18-i (2026-07-21): Broadened except clause to include
        SyntaxError and RuntimeError; added components.json fallback for the
        empty-map case.
    """
    sibling = Path(__file__).resolve().parent / "_component_migration_map.py"
    try:
        spec = importlib.util.spec_from_file_location("_component_migration_map", sibling)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        migration_map: dict[str, str] = dict(getattr(mod, "MIGRATION_MAP", {}) or {})
    except (OSError, AttributeError, ImportError, SyntaxError, RuntimeError) as exc:
        logger.warning("Cannot load MIGRATION_MAP from %s: %s", sibling, exc)
        return {}

    if migration_map:
        return migration_map

    # Fallback: when the data module loaded but returned an empty map (e.g.
    # test doubles that blank out MIGRATION_MAP), auto-derive a minimal map
    # from docs/components.json so callers still get a non-empty mapping.
    # No WARNING is emitted here — an empty module map is not an error.
    try:
        repo_root = _find_worktree_root(Path(__file__))
        components_path = repo_root / "docs" / "components.json"
        with open(components_path, encoding="utf-8") as fh:
            data = json.load(fh)
        valid_ids: set[str] = set(data.get("components", {}).keys())
        # Derive kebab→underscore pairs by converting each underscore id
        # to its hyphenated form.  This is not the canonical MIGRATION_MAP
        # (which handles non-obvious mappings like ticket-creation →
        # ticket_creation_pipeline) but it covers the simple 1:1 cases and
        # ensures a non-empty return when the data module had no entries.
        return {vid.replace("_", "-"): vid for vid in valid_ids}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Cannot build fallback migration map from docs/components.json: %s", exc
        )
        return {}


_COMPONENT_MIGRATION_MAP: dict[str, str] = _load_migration_map()


# ---------------------------------------------------------------------------
# AC lookup
# ---------------------------------------------------------------------------


def _find_ac_by_id(ac_root: Path, ac_id: str) -> tuple[Path, AcRecord] | None:
    """Search *ac_root* recursively for a YAML file with id: *ac_id*.

    Args:
        ac_root: Root directory of the AC store.
        ac_id: The AC id to search for.

    Returns:
        ``(path, record)`` when found; ``None`` when not found or parse error.
    """
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(f"WARNING: {yaml_path}: could not read: {exc}", file=sys.stderr)
            continue
        else:
            if isinstance(data, dict) and data.get("id") == ac_id:
                return yaml_path, data
    return None


# ---------------------------------------------------------------------------
# Idempotency guard
# ---------------------------------------------------------------------------


def _find_existing_ticket(tickets_root: Path, ac_id: str) -> Path | None:
    """Search *tickets_root* for a ticket with source_ac: *ac_id* in frontmatter.

    Args:
        tickets_root: Root directory to search for existing tickets.
        ac_id: The AC id to search for.

    Returns:
        Path to the existing ticket, or None when not found.
    """
    for md_path in tickets_root.rglob("*.md"):
        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        else:
            if isinstance(fm, dict) and fm.get("source_ac") == ac_id:
                return md_path
    return None


# ---------------------------------------------------------------------------
# Ticket body construction
# ---------------------------------------------------------------------------


def _extract_local_paths(
    doc_links: list[Any],
    *,
    relationships: frozenset[str] | None = None,
) -> list[str]:
    """Extract local file paths from a doc_links list.

    Filters out entries whose path starts with 'http' (URLs).  When
    *relationships* is provided, only entries whose ``relationship`` field is
    a member of that set are included; entries with an absent or non-matching
    relationship are skipped.

    Args:
        doc_links: List of doc_link dicts (each has at least a 'path' key)
                   or None/empty.
        relationships: Optional frozenset of relationship strings to include.
                       When ``None`` (default) no relationship filtering is
                       applied.

    Returns:
        List of local path strings (may be empty).
    """
    if not doc_links:
        return []
    local: list[str] = []
    for link in doc_links:
        if not isinstance(link, dict):
            continue
        if relationships is not None:
            rel = link.get("relationship", "")
            if rel not in relationships:
                continue
        path_val = link.get("path", "")
        if isinstance(path_val, str) and path_val and not path_val.startswith("http"):
            local.append(path_val)
    return local


def _extract_paths_from_prose(text: str) -> list[str]:
    """Extract file path tokens from a prose bullet string.

    A token is included only when it contains at least one ``/`` separator
    AND satisfies one of two conditions:

    * Its final path component ends in a recognized extension from
      ``_PROSE_PATH_EXTENSIONS`` (e.g. ``scripts/foo.py``, ``docs/bar.md``).
    * The token begins with a known path prefix from ``_KNOWN_PATH_PREFIXES``
      (e.g. ``scripts/``, ``docs/``) even when it carries no extension.

    Bare words such as ``"pipeline"`` or prose phrases such as
    ``"system architecture"`` never satisfy either condition because they
    contain no ``/`` character, so they are never extracted.

    Args:
        text: A prose bullet string (one item from a list-form it_requirements).

    Returns:
        List of file path strings found in *text* (may be empty).
    """
    found: list[str] = []
    for match in _PROSE_PATH_TOKEN_RE.finditer(text):
        token = match.group(0)
        # Check for a recognized extension on the final path component.
        dot_pos = token.rfind(".")
        slash_pos = token.rfind("/")
        if dot_pos > slash_pos:
            # The dot is after the last slash — it belongs to the filename component.
            ext = token[dot_pos:].lower()
            if ext in _PROSE_PATH_EXTENSIONS:
                found.append(token)
                continue
        # No recognized extension: fall back to known-prefix check.
        if any(token.startswith(prefix) for prefix in _KNOWN_PATH_PREFIXES):
            found.append(token)
    return found


def _build_files_touched(ac: dict[str, Any]) -> list[str]:
    """Build the sorted, de-duplicated ``files_touched`` list for a generated ticket.

    The list is the union of:

    1. The ``reference_file_path`` named in ``it_requirements`` (structured form),
       or file path tokens extracted from prose bullets when ``it_requirements``
       is a list of strings (list form — TKT-500f-8-i).
    2. Paths from ``doc_links`` whose ``relationship`` is one of the edit-surface
       relationships defined in ``_EDIT_SURFACE_RELATIONSHIPS`` (``constrains``,
       ``creates``, ``implements``, ``modifies``, ``specifies``).

    Doc_links with ``relationship`` set to ``describes`` or ``related`` are
    informational only and are excluded from ``files_touched``.  Paths that
    appear in both sources are deduplicated so each path is listed exactly once.
    The returned list is sorted deterministically so that regenerating the same
    AC always yields byte-identical output.

    Args:
        ac: Parsed AC record dict.

    Returns:
        Sorted list of unique local path strings (may be empty).
    """
    paths: set[str] = set()

    # Source 1 — it_requirements edit surface.
    # Structured form: a dict with an explicit reference_file_path key.
    # List form (TKT-500f-8-i): a list of prose bullet strings; each bullet is
    # scanned for file path tokens via _extract_paths_from_prose.
    it_req = ac.get("it_requirements")
    if isinstance(it_req, dict):
        ref_path = it_req.get("reference_file_path", "")
        if isinstance(ref_path, str) and ref_path:
            paths.add(ref_path)
    elif isinstance(it_req, list):
        for bullet in it_req:
            if isinstance(bullet, str):
                for path_token in _extract_paths_from_prose(bullet):
                    paths.add(path_token)

    # Source 2 — doc_links edit-surface entries
    doc_links = ac.get("doc_links") or []
    for path_val in _extract_local_paths(
        doc_links, relationships=_EDIT_SURFACE_RELATIONSHIPS
    ):
        paths.add(path_val)

    return sorted(paths)


def _resolve_reference_patterns(it_req: dict, ac_id: str) -> dict:
    """Resolve ``reference_pattern`` globs in an it_requirements dict to concrete paths.

    When the ``reference_pattern`` key is present, the glob is expanded against
    the filesystem.  Exactly one match is required — zero matches raises
    ``ValueError`` (authoring error: the pattern resolves to nothing, or the
    target file is missing).

    The function returns a shallow copy of *it_req* with ``reference_pattern``
    replaced by the single resolved concrete path string.  When the key is
    absent the original dict is returned unchanged.

    Args:
        it_req: The ``it_requirements`` dict from the AC record.
        ac_id: AC identifier, included in error messages so the author can
               trace the broken pattern back to its source AC.

    Returns:
        Shallow copy of *it_req* with ``reference_pattern`` replaced by the
        resolved concrete path, or *it_req* unchanged when the key is absent.

    Raises:
        ValueError: When ``reference_pattern`` resolves to zero files.
    """
    if "reference_pattern" not in it_req:
        return it_req

    pattern = str(it_req["reference_pattern"])
    try:
        matches = _glob.glob(pattern)
    except OSError as exc:
        raise ValueError(  # noqa: TRY003
            f"AC '{ac_id}': error expanding reference_pattern {pattern!r}: {exc}"
        ) from exc

    if not matches:
        raise ValueError(  # noqa: TRY003
            f"AC '{ac_id}': reference_pattern {pattern!r} resolves to no files. "
            "Ensure the referenced file exists or correct the pattern in the AC."
        )

    resolved_req = dict(it_req)
    resolved_req["reference_pattern"] = matches[0]
    return resolved_req


def _load_guardrail_gates(guardrail_config_path: Path) -> dict[str, Any]:
    """Load and return the guardrail gates configuration from YAML.

    Args:
        guardrail_config_path: Absolute path to guardrail_gates.yaml.

    Returns:
        Parsed YAML content as a dict.

    Raises:
        FileNotFoundError: When the file does not exist.
        yaml.YAMLError: When the file cannot be parsed.
        OSError: When the file cannot be read.
    """
    try:
        with open(guardrail_config_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        print(
            f"ERROR: could not load guardrail config {guardrail_config_path}: {exc}",
            file=sys.stderr,
        )
        raise
    return data or {}


def _load_production_code_agents(agent_registry_path: Path) -> set[str]:
    """Return the set of agent IDs whose produces field equals 'production_code'.

    Args:
        agent_registry_path: Absolute path to agent_registry.json.

    Returns:
        Set of agent IDs that produce production_code.

    Raises:
        FileNotFoundError: When the file does not exist.
        json.JSONDecodeError: When the file cannot be parsed.
        OSError: When the file cannot be read.
    """
    try:
        with open(agent_registry_path, encoding="utf-8") as fh:
            registry = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"ERROR: could not load agent registry {agent_registry_path}: {exc}",
            file=sys.stderr,
        )
        raise
    producers: set[str] = set()
    for agent in registry.get("agents", []):
        agent_id = agent.get("id", "")
        if agent.get("produces") == "production_code" and agent_id:
            producers.add(agent_id)
    return producers


def _build_agents_map(
    assigned_agent: str,
    change_targets: list[str] | None = None,
    risk_surface: str | None = None,
    not_needed_overrides: dict[str, str] | None = None,
    guardrail_config_path: Path | str | None = None,
    agent_registry_path: Path | str | None = None,
    files_touched: list[str] | None = None,
) -> dict[str, str]:
    """Build the agents map for the ticket frontmatter.

    When change_targets and risk_surface are provided the map is computed from
    the guardrail_gates.yaml lookup (unioning all applicable targets) plus the
    work agent.  When they are omitted the function falls back to the legacy
    behaviour (assigned_agent + canonical support agents).

    The returned dict is ordered according to _CANONICAL_PHASE_ORDER.
    test-writer is auto-injected before, and test-runner after, any agent
    whose produces field equals 'production_code' in agent_registry.json.
    Explicit not_needed_overrides are preserved for non-TDD agents and never
    recomputed to 'needed'. TDD-mandated agents (test-writer and test-runner)
    cannot be excluded via not_needed_overrides when the computed chain requires
    them — the computed chain wins (BO-550-1-i).

    When files_touched contains at least one recognised source-code file (not
    limited to .py — any extension in _SOURCE_CODE_EXTENSIONS qualifies) OR
    the assigned_agent is a known coder (python-coder/frontend-coder/sql-coder),
    ac-validator and ac-fulfillment-gate are wired as needed phases
    (TKT-500f-12, broadened by TKT-500f-14).  This check applies only in the
    computed path (when change_targets and risk_surface are provided) and keys
    off the actual edit surface and/or the assigned agent, not the change_target
    label.

    Args:
        assigned_agent: The agent name from the AC's assigned_agent field.
        change_targets: List of change target categories (e.g. ['python_code', 'config']).
        risk_surface: Risk surface label (e.g. 'low', 'high', 'production').
        not_needed_overrides: Map of agent → 'not_needed' that must be preserved.
        guardrail_config_path: Path to config/guardrail_gates.yaml.
        agent_registry_path: Path to config/agent_registry.json.
        files_touched: List of file paths the ticket will touch.  Used to detect
            implementation .py files so that ac-validator and ac-fulfillment-gate
            are wired when needed.

    Returns:
        Ordered dict suitable for YAML frontmatter serialisation.
    """
    overrides: dict[str, str] = not_needed_overrides or {}

    if change_targets is not None and risk_surface is not None:
        # --- Computed path ---
        # Resolve config paths
        if guardrail_config_path is None:
            # Try to locate the repo root relative to this script
            try:
                repo_root = _find_worktree_root(Path(__file__))
                guardrail_config_path = repo_root / _DEFAULT_GUARDRAIL_GATES
            except FileNotFoundError:
                guardrail_config_path = Path(_DEFAULT_GUARDRAIL_GATES)
        guardrail_config_path = Path(guardrail_config_path)

        if agent_registry_path is None:
            try:
                repo_root = _find_worktree_root(Path(__file__))
                agent_registry_path = repo_root / _DEFAULT_AGENT_REGISTRY
            except FileNotFoundError:
                agent_registry_path = Path(_DEFAULT_AGENT_REGISTRY)
        agent_registry_path = Path(agent_registry_path)

        # Load guardrail gates
        try:
            gates = _load_guardrail_gates(guardrail_config_path)
        except (OSError, yaml.YAMLError):
            gates = {}

        # Load production_code producers
        try:
            prod_code_agents = _load_production_code_agents(agent_registry_path)
        except (OSError, json.JSONDecodeError):
            prod_code_agents = {"python-coder", "sql-coder", "frontend-coder"}

        # Union guardrail agents from all change_targets × risk_surface
        guardrail_set: set[str] = set()
        for target in change_targets:
            surface_map = gates.get(target, {})
            gate_list = surface_map.get(risk_surface, [])
            if gate_list:
                guardrail_set.update(gate_list)
            else:
                logger.warning(
                    "No guardrail entry for (change_target=%r, risk_surface=%r) — "
                    "no guardrail agents added for this pair.",
                    target,
                    risk_surface,
                )

        # Consume flow_change_gates: for each (change_target, risk_surface) pair
        # that is listed as a flow-change pair, union mandatory_agents into guardrail_set
        # and switch to the flow-change phase order so documentation-expert is placed
        # BEFORE any coder (as required by the phase_constraint in each entry).
        flow_change_entries = gates.get("flow_change_gates", []) or []
        is_flow_change_pair = False
        for entry in flow_change_entries:
            if not isinstance(entry, dict):
                continue
            if (
                entry.get("change_target") in change_targets
                and entry.get("risk_surface") == risk_surface
            ):
                mandatory = entry.get("mandatory_agents") or []
                guardrail_set.update(mandatory)
                is_flow_change_pair = True

        # For flow-change pairs, documentation-expert must appear before any coder.
        # _FLOW_CHANGE_PHASE_ORDER encodes this constraint; all other pairs use the
        # standard _CANONICAL_PHASE_ORDER.
        phase_order = _FLOW_CHANGE_PHASE_ORDER if is_flow_change_pair else _CANONICAL_PHASE_ORDER

        # Collect all agent names that should appear in the map
        # Start with guardrails + assigned agent + standard tail agents
        all_needed: set[str] = set(guardrail_set)
        all_needed.add(assigned_agent)
        # Always include commit and pull-request
        all_needed.add("commit")
        all_needed.add("pull-request")

        # Auto-inject test-writer before and test-runner after any production_code agent
        for agent in list(all_needed):
            if agent in prod_code_agents:
                all_needed.add("test-writer")
                all_needed.add("test-runner")
                break

        # Wire ac-validator and ac-fulfillment-gate for code tickets
        # (TKT-500f-12, broadened by TKT-500f-14). A ticket is classified as a
        # code ticket when EITHER of the following is true:
        #   (a) files_touched contains at least one recognised source-code file
        #       extension (not limited to .py — covers .js, .ts, .tsx, .jsx,
        #       .sql, .vue, .svelte, .html, .css, .sh, etc. as defined by
        #       _SOURCE_CODE_EXTENSIONS, derived from _PROSE_PATH_EXTENSIONS);
        #   (b) the assigned agent is a known coder (python-coder,
        #       frontend-coder, or sql-coder) — coder assignment alone is
        #       sufficient regardless of files_touched content.
        # Docs/config/diagram-only tickets (no source file in files_touched AND
        # a non-coder assigned agent) satisfy neither condition and are not gated.
        _has_source_file = bool(files_touched) and any(
            Path(p).suffix.lower() in _SOURCE_CODE_EXTENSIONS for p in files_touched
        )
        _is_coder_assigned = assigned_agent in _KNOWN_CODERS
        if _has_source_file or _is_coder_assigned:
            all_needed.add("ac-validator")
            all_needed.add("ac-fulfillment-gate")

        # Determine TDD-mandated agents that cannot be overridden (BO-550-1-i).
        # When the computed chain requires test-writer or test-runner (via guardrail
        # lookup or auto-inject), those agents cannot be excluded by not_needed_overrides.
        # Non-TDD agents (e.g. architect-review) remain freely overridable.
        _TDD_MANDATORY: frozenset[str] = frozenset({"test-writer", "test-runner"})
        tdd_protected: set[str] = all_needed & _TDD_MANDATORY

        # Remove any agent that has an explicit not_needed override,
        # but protect TDD-mandated agents (BO-550-1-i: computed chain wins).
        for agent in overrides:
            if agent not in tdd_protected:
                all_needed.discard(agent)

        # Build ordered result according to the chosen phase order.
        # Non-canonical agents (not in phase_order) are inserted in stable
        # sorted order BEFORE commit and pull-request so they are never placed
        # after the terminal phase agents.
        agents: dict[str, str] = {}

        # Separate non-canonical needed agents; insert them sorted before commit.
        non_canonical_needed = sorted(
            a for a in all_needed
            if a not in phase_order and a not in overrides
        )
        non_canonical_not_needed = sorted(
            a for a in overrides
            if a not in phase_order
        )

        # Walk phase order; insert non-canonical agents just before commit.
        for phase_agent in phase_order:
            if phase_agent == "commit":
                # Insert non-canonical agents at a stable position before commit.
                for nc_agent in non_canonical_needed:
                    agents[nc_agent] = "needed"
                for nc_agent in non_canonical_not_needed:
                    agents[nc_agent] = "not_needed"
            if phase_agent in tdd_protected:
                # TDD-mandated agents are never overridable (BO-550-1-i).
                agents[phase_agent] = "needed"
            elif phase_agent in overrides:
                agents[phase_agent] = "not_needed"
            elif phase_agent in all_needed:
                agents[phase_agent] = "needed"

        # Add any overrides for agents not already in the map
        for agent, status in overrides.items():
            if agent not in agents:
                agents[agent] = status

        return agents

    # --- Legacy path (no change_targets/risk_surface) ---
    agents_legacy: dict[str, str] = {}
    agents_legacy[assigned_agent] = "needed"
    for canonical in _CANONICAL_SUPPORT_AGENTS:
        if canonical != assigned_agent:
            agents_legacy[canonical] = "needed"
    for sql_agent in _SQL_AGENTS:
        if sql_agent != assigned_agent and sql_agent not in agents_legacy:
            agents_legacy[sql_agent] = "not_needed"
    for not_needed in _NOT_NEEDED_AGENTS:
        if not_needed != assigned_agent and not_needed not in agents_legacy:
            agents_legacy[not_needed] = "not_needed"
    return agents_legacy


def _agent_produces_production_code(
    agent_id: str,
    agent_registry_path: Path | str | None = None,
) -> bool:
    """Return True if the given agent produces production_code.

    Loads agent_registry.json to check the produces field. Falls back to a
    known hard-coded set when the registry cannot be loaded.

    Args:
        agent_id: The agent identifier to check.
        agent_registry_path: Path to agent_registry.json; resolved from repo
                             root when omitted.

    Returns:
        True if the agent produces production_code, False otherwise.
    """
    # Known production_code producers (fallback when registry is unavailable)
    _FALLBACK_PRODUCERS: frozenset[str] = frozenset(
        {
            "python-coder",
            "sql-coder",
            "frontend-coder",
            "sql-table-creator",
            "sql-query",
            "sql-procedure-creator",
            "sql-function-creator",
            "sql-index-creator",
            "sql-view-creator",
        }
    )

    if agent_registry_path is None:
        try:
            repo_root = _find_worktree_root(Path(__file__))
            agent_registry_path = repo_root / _DEFAULT_AGENT_REGISTRY
        except FileNotFoundError:
            return agent_id in _FALLBACK_PRODUCERS

    try:
        producers = _load_production_code_agents(Path(agent_registry_path))
    except (OSError, json.JSONDecodeError):
        return agent_id in _FALLBACK_PRODUCERS
    else:
        return agent_id in producers


def _build_implementation_notes_section(ac: AcRecord, ac_id: str = "") -> str:
    """Build the ## Implementation Notes section from it_requirements in the AC record.

    Emits a verbatim reproduction of every field in ``it_requirements`` as a
    YAML code block so that a phase agent can locate and parse the spec without
    guesswork.  Returns an empty string when ``it_requirements`` is absent from
    the AC record, so that no empty stub is ever written (AC-2 / BO-2000c-1-i).

    Before serialising, any ``reference_pattern`` glob in ``it_requirements``
    is resolved to the single concrete path it matches (BO-2000c-3).  When the
    pattern resolves to zero files a ``ValueError`` is raised so the authoring
    error surfaces immediately rather than silently emitting a broken wildcard
    into the ticket body (BO-2000c-3-i).

    The section is placed consistently in the ticket body just before the
    ``## Sign-offs`` block so that phase agents can locate it with a simple
    heading search (AC-3 / BO-2000c-2).

    Args:
        ac: Parsed AC record.
        ac_id: The AC id; used in ``reference_pattern`` error messages so the
               author can trace the broken pattern back to its source AC.

    Returns:
        Formatted ``## Implementation Notes`` markdown block, or ``""`` when
        ``it_requirements`` is absent.

    Raises:
        ValueError: When a ``reference_pattern`` glob in ``it_requirements``
                    resolves to zero files (authoring error).
    """
    it_req = ac.get("it_requirements")
    if not it_req:
        return ""
    # Resolve reference_pattern globs before serialising (BO-2000c-3 / BO-2000c-3-i).
    # _resolve_reference_patterns raises ValueError on unresolvable patterns;
    # that exception propagates to the caller (not caught here — Rule 4).
    it_req = _resolve_reference_patterns(it_req, ac_id)
    try:
        spec_yaml = yaml.dump(
            it_req,
            default_flow_style=False,
            allow_unicode=True,
        ).rstrip()
    except yaml.YAMLError as exc:
        logger.warning("Could not serialise it_requirements to YAML: %s", exc)
        spec_yaml = str(it_req)
    return "\n".join([
        "## Implementation Notes",
        "",
        "```yaml",
        spec_yaml,
        "```",
        "",
    ])


def _slugify_for_test(text: str, max_words: int = 8) -> str:
    """Convert free text into a snake_case identifier fragment for a test name.

    Args:
        text: Source text (e.g. a Gherkin Then clause or an AC id).
        max_words: Cap on the number of words retained.

    Returns:
        A lowercase snake_case fragment safe for a Python test function name.
    """
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    if not words:
        return "criterion"
    return "_".join(words[:max_words])


def _derive_tests_from_criteria(ac: AcRecord, ac_id: str) -> list[dict[str, Any]]:
    """Derive best-effort test descriptors from an AC's Gherkin criteria.

    Fallback used only when the AC carries no explicit ``test_spec``. Each
    ``Then`` clause in the criteria becomes one test descriptor, so the derived
    ticket still tells test-writer what to assert straight from the criteria —
    the AC remains the source of truth. When no ``Then`` clause is present a
    single generic descriptor is emitted so the ticket is never left with an
    empty test contract.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.

    Returns:
        List of test descriptor dicts (name / file / covers / asserts).
    """
    criteria = str(ac.get("criteria") or "")
    slug = _slugify_for_test(ac_id)
    then_clauses = [
        m.group(1).strip()
        for m in re.finditer(r"^\s*Then\b(.*)$", criteria, re.MULTILINE | re.IGNORECASE)
        if m.group(1).strip()
    ]
    file_path = f"unit_tests/test_{slug}.py"
    if not then_clauses:
        return [{
            "name": f"test_{slug}_satisfies_criteria",
            "file": file_path,
            "covers": [ac_id],
            "asserts": "Derived from AC criteria — replace with a concrete assertion.",
        }]
    tests: list[dict[str, Any]] = []
    seen: set[str] = set()
    for clause in then_clauses:
        name = f"test_{slug}_{_slugify_for_test(clause)}"
        if name in seen:
            # Disambiguate until unique — a fixed suffix can still collide with an
            # earlier clause's slug, which would silently drop a test.
            suffix = len(tests)
            candidate = f"{name}_{suffix}"
            while candidate in seen:
                suffix += 1
                candidate = f"{name}_{suffix}"
            name = candidate
        seen.add(name)
        tests.append({
            "name": name,
            "file": file_path,
            "covers": [ac_id],
            "asserts": clause,
        })
    return tests


def _test_descriptors_from_spec(ac: AcRecord, ac_id: str) -> list[dict[str, Any]]:
    """Build test descriptors from the AC's explicit ``test_spec`` field.

    ``test_spec`` is the source-of-truth test contract authored on the AC by
    it-po. Each entry is normalised into the ticket ``## Test Requirements``
    shape (name / file / covers / asserts, plus optional framework / type /
    requires_db). The ``file`` path is derived from ``target_dir`` and the AC id
    when the entry does not already point at a ``.py`` file.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.

    Returns:
        List of test descriptor dicts. Empty when ``test_spec`` is absent or
        contains no usable entries.
    """
    test_spec = ac.get("test_spec")
    if not isinstance(test_spec, list) or not test_spec:
        return []
    slug = _slugify_for_test(ac_id)
    descriptors: list[dict[str, Any]] = []
    for item in test_spec:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        target_dir = str(item.get("target_dir") or "").rstrip("/")
        if target_dir.endswith(".py"):
            file_path = target_dir
        elif target_dir:
            file_path = f"{target_dir}/test_{slug}.py"
        else:
            file_path = f"unit_tests/test_{slug}.py"
        entry: dict[str, Any] = {
            "name": name,
            "file": file_path,
            "covers": item.get("covers") or [ac_id],
        }
        if item.get("description"):
            entry["asserts"] = item["description"]
        if item.get("framework"):
            entry["framework"] = item["framework"]
        if item.get("type"):
            entry["type"] = item["type"]
        if item.get("requires_db"):
            entry["requires_db"] = True
        descriptors.append(entry)
    return descriptors


def _build_test_requirements_section(ac: AcRecord, ac_id: str) -> str:
    """Build the ## Test Requirements section, derived from the AC.

    Source-of-truth order:
      1. explicit ``test_spec`` on the AC (authored by it-po) — preferred;
      2. otherwise derive stubs from the Gherkin ``criteria`` Then-clauses.

    Either way the tests are derived from the AC — never a hardcoded ``tests: []``
    stub — so the ticket-level Test Requirements guard passes by construction and
    test-writer receives a real, AC-derived contract. Returns an empty string
    only when the AC explicitly sets ``test_required: false`` (genuinely
    test-free), in which case the caller omits the section.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.

    Returns:
        Formatted ``## Test Requirements`` markdown block, or ``""`` when the AC
        is explicitly marked test-free.
    """
    if ac.get("test_required") is False:
        return ""

    descriptors = _test_descriptors_from_spec(ac, ac_id)
    if not descriptors:
        descriptors = _derive_tests_from_criteria(ac, ac_id)

    try:
        # sort_keys=False is REQUIRED: 'name' must stay the first key in each test
        # item so check_ticket_test_requirements._TESTS_ENTRY_RE ("- name: \\S+")
        # and the --verify guard-equivalence regex both match. Do not enable sorting.
        block = yaml.dump(
            {"tests": descriptors},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
    except yaml.YAMLError as exc:
        logger.warning("Could not serialise derived test descriptors to YAML: %s", exc)
        return ""

    return "\n".join([
        "## Test Requirements",
        "",
        "```yaml",
        block,
        "```",
        "",
    ])


def _build_agent_contracts_section(ac: AcRecord) -> str:
    """Build the ## Agent Contracts section from delivers_to and expects_from.

    When both fields are None, returns an empty string so no section is emitted.
    The section is only rendered when at least one contract field is non-null,
    ensuring the null-contract path produces no contract heading or content.

    Args:
        ac: Parsed AC record.

    Returns:
        Formatted ## Agent Contracts markdown block, or empty string when both
        delivers_to and expects_from are None.
    """
    delivers_to = ac.get("delivers_to") or None
    expects_from = ac.get("expects_from") or None

    if delivers_to is None and expects_from is None:
        return ""

    lines: list[str] = ["## Agent Contracts", ""]
    if delivers_to is not None:
        lines.append("### Delivers To")
        lines.append("")
        agent_name = delivers_to.get("agent", "")
        contract_text = delivers_to.get("contract", "")
        if agent_name:
            lines.append(f"- **Agent:** {agent_name}")
        if contract_text:
            lines.append(f"- **Contract:** {contract_text}")
        lines.append("")
    if expects_from is not None:
        lines.append("### Expects From")
        lines.append("")
        upstream_ac_id = expects_from.get("ac_id", "")
        contract_text = expects_from.get("contract", "")
        if upstream_ac_id:
            lines.append(f"- **AC:** {upstream_ac_id}")
        if contract_text:
            lines.append(f"- **Contract:** {contract_text}")
        lines.append("")
    return "\n".join(lines)


def _build_signoffs_section(agents: dict[str, str]) -> str:
    """Build the ## Sign-offs section from the agents map.

    Only agents with status 'needed' appear in Sign-offs.

    Args:
        agents: Agents map dict.

    Returns:
        Formatted ## Sign-offs markdown block.
    """
    lines = ["## Sign-offs", ""]
    for agent_name, status in agents.items():
        if status == "needed":
            lines.append(f"- [ ] {agent_name}")
    return "\n".join(lines)


def _load_valid_component_ids() -> frozenset[str]:
    """Load the set of valid component graph IDs from docs/components.json.

    MODULE: generate_ticket_from_ac
    GOAL: Provide the authoritative set of valid underscore graph IDs so that
          ``_build_components_list`` can validate resolved component values and
          emit targeted WARNINGs for values absent from the registry.
    BUSINESS CONTEXT: docs/components.json is the SSOT for component graph IDs.
          Any resolved component value absent from this set is suspect and
          should be surfaced to the author via a WARNING rather than silently
          inserted into the generated ticket.
    ARCHITECTURE: I/O boundary function — catches read/parse errors and
          returns an empty frozenset (no validation) rather than propagating.
          Calls ``_find_worktree_root`` so that unit tests can patch it to
          supply a controlled test-double components.json.

    Returns:
        frozenset of underscore component id strings from docs/components.json,
        or an empty frozenset when the file cannot be found or read (in which
        case no validity check is performed by callers).

    DECISION HISTORY:
        TKT-500f-17 (2026-07-21): Introduced to support data-driven validity
        checking in ``_build_components_list`` — validity is determined by
        membership in docs/components.json, not by the partial MIGRATION_MAP.
    """
    try:
        repo_root = _find_worktree_root(Path(__file__))
        components_path = repo_root / "docs" / "components.json"
        with open(components_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return frozenset(data.get("components", {}).keys())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Cannot load valid component IDs from docs/components.json: %s", exc
        )
        return frozenset()


def _build_components_list(ac: AcRecord, ac_id: str = "") -> list[str]:
    """Build the ``components`` LIST for a generated ticket frontmatter.

    Prefers the AC's own ``components`` field when non-empty.  When the field
    holds a SCALAR string (not a YAML list), it is treated as a single
    component id and wrapped in a one-element list — applying the
    ``_COMPONENT_MIGRATION_MAP`` kebab→underscore lookup so that kebab
    namespace keys (e.g. ``ticket-creation``) are resolved to their
    components.json graph ids (e.g. ``ticket_creation_pipeline``).

    When the field holds a YAML LIST, each element is normalised through
    ``_COMPONENT_MIGRATION_MAP`` and then validated against the set of valid
    ids loaded from docs/components.json (TKT-500f-16 / TKT-500f-17).
    Elements whose resolved value is absent from docs/components.json receive
    a WARNING that names both the source AC id and the offending value.
    Warnings are emitted at most once per distinct unresolved value (AC-3
    deduplication).  The unresolved value is passed through VERBATIM so the
    Component-vocab CI check can surface it; it is never silently dropped.
    Duplicate resolved values are deduped in the output (order-preserving).

    When the field is absent or falsy, the scalar ``component`` key is
    normalised via ``_COMPONENT_MIGRATION_MAP``, falling back to the raw
    value when the key is absent from the map.

    The scalar ``component`` field in the ticket frontmatter is left unchanged
    — only the LIST is normalised to the components.json graph vocabulary.

    Args:
        ac: Parsed AC record dict.
        ac_id: The AC identifier; used in WARNING messages so the author can
               trace an unresolvable component value back to its source AC.

    Returns:
        List of underscore graph ids for the generated ticket ``components`` LIST.

    DECISION HISTORY:
        TKT-500f-15 (2026-07-21): Added ``isinstance(existing, str)`` branch to
        prevent ``list(str)`` per-character shatter when the YAML ``components``
        field is a scalar string.  A scalar string is now treated as a single
        value and resolved through ``_COMPONENT_MIGRATION_MAP`` before wrapping.
        TKT-500f-16 (2026-07-21): LIST elements are now each normalised through
        ``_COMPONENT_MIGRATION_MAP`` instead of passed through with ``list()``.
        Previously kebab elements such as ``build-pipeline`` passed straight
        through without normalisation.
        TKT-500f-17 / TKT-500f-17-i (2026-07-21): Added docs/components.json
        validity check for LIST elements; WARNING emitted once per distinct
        unresolvable value naming both the AC id and the value; unresolved
        values passed through verbatim (not dropped).
    """
    existing = ac.get("components")
    if existing:
        if isinstance(existing, str):
            return [_COMPONENT_MIGRATION_MAP.get(existing, existing)]
        # LIST case: normalise each element, validate against components.json.
        valid_ids = _load_valid_component_ids()
        result: list[str] = []
        seen_resolved: set[str] = set()   # order-preserving dedup of resolved values
        warned_values: set[str] = set()   # dedup WARNING emissions per distinct value
        for el in existing:
            resolved: str = _COMPONENT_MIGRATION_MAP.get(el, el)
            if resolved not in seen_resolved:
                seen_resolved.add(resolved)
                result.append(resolved)
            # Validity check: warn once per distinct unresolved value when the
            # resolved id is absent from docs/components.json.  Skip the check
            # when valid_ids is empty (components.json unavailable) to avoid
            # false positives.
            if valid_ids and resolved not in valid_ids and resolved not in warned_values:
                logger.warning(
                    "AC '%s': component value %r cannot be resolved to a valid "
                    "docs/components.json graph id",
                    ac_id,
                    resolved,
                )
                warned_values.add(resolved)
        return result
    kebab = ac.get("component", "unknown")
    return [_COMPONENT_MIGRATION_MAP.get(kebab, kebab)]


def _build_frontmatter(
    ac: AcRecord,
    ac_id: str,
    files_touched: list[str],
    agents: dict[str, str],
    ac_store_path: "str | None" = None,
) -> str:
    """Build the YAML frontmatter block for the ticket.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        files_touched: Local paths extracted from doc_links.
        agents: Agents map dict.
        ac_store_path: Repo-root-relative path to the source AC YAML file.
            When provided, an ``ac_traceability`` entry is added to the
            frontmatter carrying both the AC id and the store path, enabling
            ac-validator and ac-fulfillment-gate to locate the source AC
            directly without scanning the whole store.

    Returns:
        Formatted frontmatter string (including opening and closing ``---``).
    """
    today = date.today().isoformat()
    complexity = _infer_complexity(ac)
    fm: dict[str, Any] = {
        "title": ac.get("title", f"Implement {ac_id}"),
        "status": "todo",
        "source_ac": ac_id,
        "components": _build_components_list(ac, ac_id),
        "created": today,
        "depends_on": ac.get("depends_on") or [],
        "priority": _map_priority(ac),
        "roadmap_phase": "phase_1",
        "advances_current_outcome": True,
        "requires_diagram": False,
        "requires_adr": False,
        "files_touched": files_touched,
        "agents": agents,
        "complexity": complexity,
    }
    if ac_store_path is not None:
        fm["ac_traceability"] = {"id": ac_id, "path": ac_store_path}
    test_constraints_raw = ac.get("test_constraints")
    test_constraints = _parse_test_constraints(test_constraints_raw)
    if test_constraints:
        fm["test_constraints"] = test_constraints
    # Emit classification axes when the source AC carries them (AC-4).
    change_target = ac.get("change_target")
    if change_target is not None:
        fm["change_target"] = change_target
    risk_surface = ac.get("risk_surface")
    if risk_surface is not None:
        fm["risk_surface"] = risk_surface
    return "---\n" + yaml.dump(fm, default_flow_style=False, allow_unicode=True) + "---"


def _map_priority(ac: AcRecord) -> str:
    """Map AC priority field to ticket priority string.

    Args:
        ac: Parsed AC record.

    Returns:
        One of 'critical', 'high', 'medium', or 'low'.
    """
    ac_priority = ac.get("priority", "")
    if ac_priority in ("critical", "high", "medium", "low"):
        return ac_priority
    complexity = ac.get("estimated_complexity", "")
    mapping = {"S": "low", "M": "medium", "L": "high", "XL": "critical"}
    return mapping.get(complexity, "medium")


def _computed_map_has_production_code_producer(
    agents_map: dict[str, str],
    agent_registry_path: "Path | str | None" = None,
) -> bool:
    """Return True if any agent in the computed map is a production_code producer.

    Args:
        agents_map: The computed agents map (agent name → status).
        agent_registry_path: Path to agent_registry.json; resolved from repo
                             root when omitted.

    Returns:
        True if any 'needed' agent in the map produces production_code.
    """
    needed_agents = [name for name, status in agents_map.items() if status == "needed"]
    return any(
        _agent_produces_production_code(name, agent_registry_path)
        for name in needed_agents
    )


def _normalize_change_target(ac: AcRecord) -> list[str] | None:
    """Normalize the change_target field from an AC record to a list or None.

    Converts a string value to a single-item list, passes a list through
    unchanged (but returns None for an empty list), and returns None when the
    field is absent or explicitly set to None.

    Args:
        ac: Parsed AC record dict.

    Returns:
        A non-empty list of change-target strings when the field is present
        and non-empty, or None when the field is absent, None, or an empty list.
    """
    raw = ac.get("change_target")
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw if raw else None
    return [raw]


def _criteria_checkboxes(criteria: str) -> list[str]:
    """Derive machine-parseable ``- [ ] AC-N: <text>`` checkbox lines from criteria.

    Extracts the text of each ``Then`` / ``And`` keyword clause in a Gherkin
    criteria string (one checkbox per clause).  When no ``Then`` / ``And``
    clauses are found, falls back to the first non-empty stripped line of the
    criteria so that every non-empty criteria string produces at least one
    checkbox.

    The resulting lines match the ac-validator parser pattern
    ``^- \\[ \\] AC-\\d+:\\s*\\S`` (with MULTILINE), satisfying TKT-500f-11.

    Args:
        criteria: The raw Gherkin criteria text from an AC record.

    Returns:
        A list of ``- [ ] AC-N: <text>`` strings — one per extracted clause.
        Returns an empty list only when *criteria* is blank.
    """
    raw_lines = criteria.split("\n")
    clauses: list[str] = []
    for line in raw_lines:
        stripped = line.strip()
        m = re.match(r"^(Then|And)\s+(.*)", stripped, re.IGNORECASE)
        if m:
            text = m.group(2).rstrip(",").strip()
            if text:
                clauses.append(text)
    if not clauses:
        # Fallback: use the first non-empty line verbatim
        for line in raw_lines:
            stripped = line.strip()
            if stripped:
                clauses.append(stripped)
                break
    return [f"- [ ] AC-{i + 1}: {clause}" for i, clause in enumerate(clauses)]


def _build_ticket_body(ac: AcRecord, ac_id: str, agents_map: "dict[str, str] | None" = None) -> str:
    """Build the ticket body (everything after the frontmatter).

    Includes: Actor/Goal, Context, Acceptance Criteria (verbatim from AC),
    an optional Test Requirements block (emitted when the computed agent map
    contains any production_code producer), and Sign-offs.

    The Test Requirements block is gated on the COMPUTED map (not only the
    assigned agent) so that a non-coder assigned agent whose guardrail
    classification pulls in a coder still receives the block.

    When ``agents_map`` is provided it is used as-is (M-1: avoids double-compute
    and drift). When absent the map is computed internally via _build_agents_map.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        agents_map: Optional pre-computed agents map. When provided, it is used
            instead of recomputing _build_agents_map internally.

    Returns:
        The ticket body string (not including the frontmatter block).
    """
    title = ac.get("title", f"Implement {ac_id}")
    criteria = ac.get("criteria", "(No criteria provided)")
    assigned_agent = ac.get("assigned_agent", "python-coder")

    if agents_map is not None:
        # M-1: use the pre-computed map; do not recompute.
        agents = agents_map
    else:
        # Extract classification fields from the AC record; default to None so
        # _build_agents_map falls back to legacy behaviour when absent.
        change_targets = _normalize_change_target(ac)
        risk_surface = ac.get("risk_surface") or None
        files_touched_for_map = _build_files_touched(ac)

        agents = _build_agents_map(
            assigned_agent,
            change_targets=change_targets,
            risk_surface=risk_surface,
            files_touched=files_touched_for_map,
        )
    signoffs = _build_signoffs_section(agents)
    complexity = _infer_complexity(ac)

    # Gate Test Requirements block on computed map: emit whenever any needed
    # agent in the computed map produces production_code.
    has_code_producer = _computed_map_has_production_code_producer(agents)

    checkbox_lines = _criteria_checkboxes(criteria)
    lines: list[str] = [
        f"# {title}",
        "",
        "## Actor / Goal",
        "",
        f"As the leafcutter-ai system, I want to implement AC `{ac_id}` — "
        f"{title} — so that the acceptance criterion is satisfied.",
        "",
        "## Context",
        "",
        f"This ticket was generated from AC store entry `{ac_id}`. "
        f"Component: `{ac.get('component', 'unknown')}`. "
        f"Assigned agent: `{assigned_agent}`. "
        f"Estimated complexity: `{ac.get('estimated_complexity', '?')}`. "
        f"Complexity: `{complexity}`.",
        "",
        "## Acceptance Criteria",
        "",
        "```gherkin",
        criteria.rstrip(),
        "```",
        "",
        *checkbox_lines,
        "",
    ]

    if has_code_producer:
        # Derive the Test Requirements from the AC (test_spec first, else the
        # Gherkin criteria) — never a hardcoded empty stub. The AC is the source
        # of truth for what test-writer must test.
        test_requirements = _build_test_requirements_section(ac, ac_id)
        if test_requirements:
            lines.append(test_requirements)

    impl_notes = _build_implementation_notes_section(ac, ac_id)
    if impl_notes:
        lines.append(impl_notes)

    agent_contracts = _build_agent_contracts_section(ac)
    if agent_contracts:
        lines.append(agent_contracts)

    lines.extend([
        signoffs,
        "",
        "## Comments",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Back-reference write
# ---------------------------------------------------------------------------


def _normalise_repo_relative(path: str) -> str:
    """Strip leading ``./`` or ``/`` and normalise separators for dedup comparison.

    Produces a canonical repo-relative form used only inside
    :func:`_write_implemented_by` to compare a candidate path against existing
    ``implemented_by`` entries.  The stored AC YAML value is never modified —
    only the comparison is normalised so that ``./tickets/foo.md`` and
    ``tickets/foo.md`` are treated as the same entry.

    Args:
        path: A raw path string, potentially prefixed with ``./`` or ``/``.

    Returns:
        The normalised repo-relative path with any leading ``./`` or ``/``
        stripped and path separators unified to ``/``.
    """
    normalised = path.replace("\\", "/")
    normalised = normalised.lstrip("/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


def _canonicalise_to_repo_relative(path: str, repo_root: "Path | None" = None) -> str:
    """Canonicalise a ticket path to its repo-relative form.

    Uses a three-tier strategy so that absolute paths, cross-worktree paths,
    and cosmetically-prefixed relative paths all resolve to the same canonical
    ``tickets/…`` string:

    1. **repo_root relativisation** — when *repo_root* is provided and *path* is
       absolute, ``Path.relative_to(repo_root)`` is attempted.  Falls through to
       tier 2 on ``ValueError`` (path is outside the given root).
    2. **tickets-segment extraction** — after stripping any leading ``/``, the
       leftmost ``tickets/`` segment is located.  Everything from that segment
       onward is returned.  Handles absolute legacy paths and cross-worktree
       absolute paths where the exact repo root is unknown.
    3. **Simple strip** — strip any remaining leading ``./`` or ``/`` characters
       for already-relative paths with cosmetic prefixes.

    Args:
        path: A raw path string — absolute, relative, or prefixed with ``./``.
        repo_root: Optional repo root ``Path``.  When provided and *path* is
            absolute, ``relative_to`` is attempted before any segment extraction.

    Returns:
        A repo-relative path string with no leading ``/`` and no absolute
        filesystem prefix (e.g. ``tickets/00_inbox/TICKET-test.md``).

    DECISION HISTORY:
    - 2026-07-21 [ACD-1200a-13]: Introduced to extend ``_normalise_repo_relative``
      with tickets-segment extraction, enabling dedup of legacy absolute entries
      against canonical repo-relative incoming paths without a git subprocess call.
    - 2026-07-21 [ACD-1200a-14]: Added *repo_root* parameter so callers can inject
      a known repo root for relativisation, producing identical canonical strings
      regardless of checkout location.
    """
    normalised = path.replace("\\", "/")

    # Tier 1: repo_root-based relativisation
    if repo_root is not None and Path(normalised).is_absolute():
        try:
            return str(Path(normalised).relative_to(repo_root)).replace("\\", "/")
        except ValueError:
            pass  # Fall through to tier 2

    # Tier 2 & 3: strip leading characters, then extract tickets/ segment
    normalised = normalised.lstrip("/")
    while normalised.startswith("./"):
        normalised = normalised[2:]

    # Tier 2: extract everything from the first 'tickets/' segment when the
    # cleaned string still has a non-trivial prefix before 'tickets/'
    tickets_idx = normalised.find("tickets/")
    if tickets_idx > 0:
        return normalised[tickets_idx:]

    return normalised


def _derive_repo_root_from_git() -> "Path | None":
    """Derive the git repository root via ``git rev-parse --show-toplevel``.

    Returns ``None`` and logs a ``WARNING`` when the command fails (e.g. the
    working directory is not inside a git repository, or git is not installed).
    Never raises — callers must handle the ``None`` case via the fallback
    canonicaliser.

    Returns:
        The repo root as a ``Path``, or ``None`` when git cannot resolve it.

    DECISION HISTORY:
    - 2026-07-21 [ACD-1200a-14]: Introduced to derive repo root for absolute-path
      canonicalisation when neither a worktree nor an explicit *repo_root* is
      provided to ``_write_implemented_by``.
    - 2026-07-21 [ACD-1200a-14-i]: Wrapped subprocess call with specific exception
      types (``CalledProcessError``, ``FileNotFoundError``) per Error Handling Policy
      Rule 1; always logs ``WARNING`` on failure and never re-raises so that the
      caller's fallback path can succeed.
    - 2026-07-21 [M-1/M-2 review findings]: Broadened except to
      ``(subprocess.CalledProcessError, OSError)`` — ``FileNotFoundError`` and
      ``PermissionError`` are both ``OSError`` subclasses, so the narrower form
      missed ``PermissionError`` on restricted filesystems (M-1). Added
      ``timeout=5`` to the ``subprocess.run`` call to prevent indefinite hangs on
      network/degenerate filesystems, and added ``subprocess.TimeoutExpired`` to the
      except clause (M-2).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(
            "git rev-parse --show-toplevel failed — falling back to tickets-segment "
            "canonicalisation for implemented_by path normalisation: %s",
            exc,
        )
        return None


def _write_implemented_by(
    ac_path: Path,
    ticket_path: str,
    ac_id: str,
    worktree: Path | None = None,
    repo_root: "Path | None" = None,
) -> None:
    """Append *ticket_path* to the implemented_by list in the source AC YAML.

    Uses a targeted field update (not a full yaml.dump round-trip) to minimise
    diff noise in the AC store.  Both the incoming path and every existing
    ``implemented_by`` entry are canonicalised through a shared
    ``_canonicalise_to_repo_relative`` call before comparison, so legacy
    absolute entries are recognised as duplicates of canonical repo-relative
    incoming paths and no duplicate is appended.

    The update strategy:
    1. Determine the effective repo root (from *repo_root*, worktree fallback, or
       ``git rev-parse --show-toplevel``; logs WARNING on git failure).
    2. Canonicalise *ticket_path* to a clean ``tickets/…`` repo-relative form.
    3. Read the full file content and parse ``implemented_by`` from the YAML.
    4. Canonicalise every existing entry through the same canonicaliser.
    5. If the canonical incoming is already present, skip appending (idempotent).
    6. Rewrite the ``implemented_by`` block only when the normalised list differs
       from the original (write-back normalises legacy absolute entries in place).

    Args:
        ac_path: Absolute path to the source AC YAML file.
        ticket_path: Path of the generated ticket to record.  May be absolute
                     or relative; will be normalised to repo-relative form
                     before writing.
        ac_id: The AC id (for diagnostic messages).
        worktree: Optional worktree root.  When provided and *ticket_path* is
                  absolute and *repo_root* is absent, the worktree prefix is
                  stripped via ``Path.relative_to`` to produce a clean
                  repo-relative path.
        repo_root: Optional repository root ``Path``.  When provided, all path
                   canonicalisation uses ``Path.relative_to(repo_root)``.  Takes
                   precedence over *worktree*-based relativisation.  When absent
                   and *ticket_path* is absolute, ``git rev-parse --show-toplevel``
                   is attempted; on failure a WARNING is logged and the
                   tickets-segment fallback is used.

    Raises:
        OSError: When the file cannot be read or written.
        yaml.YAMLError: When the YAML cannot be parsed.

    DECISION HISTORY:
    - 2026-07-21 [ACD-1200a-13]: Switched dedup to use ``_canonicalise_to_repo_relative``
      on BOTH incoming and existing entries so that legacy absolute entries are
      recognised as duplicates of canonical repo-relative incoming paths.  Existing
      entries are retroactively normalised on every write-back so no absolute path
      survives in the stored list.
    - 2026-07-21 [ACD-1200a-14]: Added *repo_root* parameter; when provided, all
      canonicalisation uses ``Path.relative_to(repo_root)`` producing identical
      stored strings regardless of checkout or worktree location.
    - 2026-07-21 [ACD-1200a-14-i]: When *repo_root* is absent and the path is
      absolute, git rev-parse is attempted via ``_derive_repo_root_from_git``; on
      failure a WARNING is logged and the tickets-segment fallback handles the path.
    """
    # ------------------------------------------------------------------
    # Step 1: Determine the effective repo root for canonicalisation.
    # ------------------------------------------------------------------
    _p = Path(ticket_path)
    effective_repo_root: "Path | None" = repo_root

    if _p.is_absolute() and effective_repo_root is None:
        if worktree is not None:
            try:
                ticket_path = str(_p.relative_to(worktree))
                _p = Path(ticket_path)
                # Successfully relativised against worktree; no git call needed.
            except ValueError:
                # Ticket lies outside the worktree — derive root from git.
                effective_repo_root = _derive_repo_root_from_git()
        else:
            effective_repo_root = _derive_repo_root_from_git()

    # ------------------------------------------------------------------
    # Step 2: Canonicalise the incoming ticket path.
    # ------------------------------------------------------------------
    canonical_incoming = _canonicalise_to_repo_relative(str(_p), effective_repo_root)

    # ------------------------------------------------------------------
    # Step 3: Read the file and parse existing implemented_by entries.
    # ------------------------------------------------------------------
    try:
        content = ac_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read AC YAML %s: %s", ac_path, exc)
        raise
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        logger.warning("Cannot parse AC YAML %s: %s", ac_path, exc)
        raise
    implemented_by: list[str] = data.get("implemented_by") or []

    # ------------------------------------------------------------------
    # Step 4: Normalise all existing entries through the shared canonicaliser
    # and check whether the incoming is already represented.
    # ------------------------------------------------------------------
    normalised_list: list[str] = [
        _canonicalise_to_repo_relative(entry, effective_repo_root)
        for entry in implemented_by
    ]
    already_recorded = canonical_incoming in normalised_list
    if not already_recorded:
        normalised_list.append(canonical_incoming)

    # If the normalised list is byte-for-byte identical to what is on disk,
    # no write is necessary (true no-op; covers the idempotent re-run case).
    if normalised_list == implemented_by:
        return

    # ------------------------------------------------------------------
    # Step 5: Targeted rewrite — replace only the implemented_by block.
    # ------------------------------------------------------------------
    new_value_yaml = yaml.dump(
        {"implemented_by": normalised_list},
        default_flow_style=False,
        allow_unicode=True,
    ).strip()
    # new_value_yaml is e.g. "implemented_by:\n- tickets/foo/bar.md"

    lines = content.splitlines(keepends=True)
    result_lines: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if not replaced and line.startswith("implemented_by:"):
            # Emit the new (normalised) block, then skip the old list items.
            result_lines.append(new_value_yaml + "\n")
            i += 1
            while i < len(lines) and (
                lines[i].startswith(" ")
                or lines[i].startswith("\t")
                or lines[i].strip() == "-"
                or (
                    lines[i].startswith("- ")
                    and not lines[i - 1].startswith(" ")
                )
            ):
                if lines[i].startswith("- ") or lines[i].startswith("  - "):
                    i += 1
                else:
                    break
            replaced = True
        else:
            result_lines.append(line)
            i += 1

    if not replaced:
        # implemented_by key not present in file — append the new block.
        new_content = content.rstrip("\n") + "\n" + new_value_yaml + "\n"
    else:
        new_content = "".join(result_lines)

    try:
        ac_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot write AC YAML %s: %s", ac_path, exc)
        raise


# ---------------------------------------------------------------------------
# Test constraints parsing
# ---------------------------------------------------------------------------


def _parse_test_constraints(value: "str | list[str] | None") -> list[str]:
    """Normalise the test_constraints frontmatter field to a list of strings.

    Args:
        value: Raw value from an AC record's test_constraints field.
               May be ``None`` (absent), a bare string, or a list of strings.

    Returns:
        A list of constraint strings.  An absent field returns ``[]`` so
        callers can safely iterate without a ``None`` check.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


# ---------------------------------------------------------------------------
# Complexity inference
# ---------------------------------------------------------------------------


def _infer_complexity(ac: AcRecord) -> str:
    """Infer a complexity label from an AC record.

    Priority:
    1. ``estimated_complexity`` field (S → low, M → medium, L/XL → high).
    2. Criteria line count (1-2 → low, 3-6 → medium, 7+ → high).
    3. Default to ``"medium"`` when no criteria are present.

    Args:
        ac: Parsed AC record dict.

    Returns:
        One of ``"low"``, ``"medium"``, or ``"high"``.
    """
    explicit = ac.get("estimated_complexity", "")
    _complexity_map: dict[str, str] = {
        "S": "low",
        "M": "medium",
        "L": "high",
        "XL": "high",
    }
    if explicit in _complexity_map:
        return _complexity_map[explicit]

    criteria: str = ac.get("criteria") or ""
    non_empty_lines = [ln for ln in criteria.split("\n") if ln.strip()]
    line_count = len(non_empty_lines)
    if line_count == 0:
        return "medium"
    if line_count <= 2:
        return "low"
    if line_count <= 6:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Complexity → model tier
# ---------------------------------------------------------------------------


def _complexity_to_model_tier(complexity: str) -> str:
    """Map a complexity label to a model tier string.

    Args:
        complexity: One of ``"low"``, ``"medium"``, or ``"high"``.

    Returns:
        ``"sonnet"`` for low/medium, ``"opus"`` for high.

    Raises:
        ValueError: When *complexity* is not a recognised value.
    """
    _tier_map: dict[str, str] = {
        "low": "sonnet",
        "medium": "sonnet",
        "high": "opus",
    }
    if complexity not in _tier_map:
        raise ValueError(f"Unknown complexity: {complexity!r}")  # noqa: TRY003
    return _tier_map[complexity]


# ---------------------------------------------------------------------------
# Challenge gate / Opus escalation
# ---------------------------------------------------------------------------


def _should_escalate_to_opus(
    complexity: str,
    complexity_override: "str | None" = None,
) -> bool:
    """Determine whether a ticket should escalate to the Opus model tier.

    The challenge gate fires when either:
    - *complexity_override* is ``"force_opus"`` (user hard-override), or
    - *complexity* is ``"high"`` (inferred or declared high effort).

    Args:
        complexity: Inferred complexity label (``"low"``, ``"medium"``, or ``"high"``).
        complexity_override: Optional override string from the AC/ticket.
                             Pass ``"force_opus"`` to bypass the challenge gate.

    Returns:
        ``True`` when the ticket should run on Opus, ``False`` otherwise.
    """
    if complexity_override == "force_opus":
        return True
    return complexity == "high"


# ---------------------------------------------------------------------------
# Ticket filename
# ---------------------------------------------------------------------------


def _ticket_filename(ac_id: str) -> str:
    """Return the ticket filename for the given AC id.

    Args:
        ac_id: The AC id.

    Returns:
        Filename string of the form ``TICKET-YYYYMMDD-<ac_id>.md``.
    """
    today = date.today().strftime("%Y%m%d")
    return f"TICKET-{today}-{ac_id}.md"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_verification_report(
    ac: AcRecord,
    ac_id: str,
    agents: dict[str, str],
    ticket_body: str,
    files_touched: list[str],
) -> tuple[str, bool]:
    """Build a readiness report answering "can agents work from this AC alone?".

    Verifies that the AC (the source of truth) carries enough for a coder to
    build and a test-writer to test purely by following the generated ticket's
    pointers. Each line is tagged PASS / WARN / FAIL. Returns the formatted
    report and a boolean indicating whether any FAIL was recorded.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        agents: The computed agents map.
        ticket_body: The generated ticket body (for guard-equivalence checks).
        files_touched: Local paths extracted from doc_links.

    Returns:
        ``(report_text, has_fail)``.
    """
    lines: list[str] = []
    has_fail = False

    def record(status: str, message: str) -> None:
        nonlocal has_fail
        if status == "FAIL":
            has_fail = True
        lines.append(f"  [{status}] {message}")

    is_code_ac = _computed_map_has_production_code_producer(agents)
    criteria = str(ac.get("criteria") or "").strip()
    test_spec = ac.get("test_spec")
    has_spec = isinstance(test_spec, list) and len(test_spec) > 0
    test_required = ac.get("test_required")

    # 1. Criteria present — a coder and test-writer both need it.
    if criteria:
        record("PASS", "criteria present (behavioural source of truth)")
    else:
        record("FAIL", "criteria is empty — nothing for a coder or test-writer to work from")

    # 2. Assigned agent.
    if ac.get("assigned_agent"):
        record("PASS", f"assigned_agent: {ac.get('assigned_agent')}")
    else:
        record("WARN", "assigned_agent absent — generator defaults to python-coder")

    # 3. Test contract (only meaningful for code ACs).
    if is_code_ac:
        if has_spec:
            record("PASS", f"test_spec authored ({len(test_spec)} test(s)) — precise test contract")
        elif test_required is False:
            record("WARN", "test_required: false on a code AC — no tests will be authored (confirm this is intentional)")
        elif criteria:
            record(
                "WARN",
                "no test_spec — Test Requirements will be DERIVED from criteria "
                "Then-clauses (author test_spec on the AC for a precise contract)",
            )
        else:
            record("FAIL", "code AC with neither test_spec nor derivable criteria — test-writer has nothing to write")
    else:
        record("PASS", "non-code AC — no test contract required")

    # 4. Generated Test Requirements would pass the ticket-level guard.
    if is_code_ac and test_required is not False:
        if re.search(r"^\s*-\s+name:\s+\S+", ticket_body, re.MULTILINE):
            record("PASS", "generated ## Test Requirements has >=1 test entry (ticket guard passes)")
        else:
            record("FAIL", "generated ## Test Requirements has no test entry — ticket guard would block dispatch")

    # 5. Implementation constraints for the coder.
    if is_code_ac:
        if ac.get("it_requirements"):
            record("PASS", "it_requirements present — coder gets an Implementation Notes section")
        else:
            record("WARN", "no it_requirements — coder has only the criteria to work from")

    # 6. File scope.
    if files_touched:
        record("PASS", f"files_touched has {len(files_touched)} path(s) from doc_links")
    else:
        record("WARN", "files_touched is empty — coder has no file-scope signal (add doc_links to the AC)")

    # 7. Scanner eligibility.
    if ac.get("readiness") == "approved":
        record("PASS", "readiness: approved (scanner-eligible)")
    else:
        record("WARN", f"readiness: {ac.get('readiness')!r} — the AC scanner only surfaces approved ACs")

    verdict = "BLOCKED" if has_fail else ("READY" if all("[WARN]" not in ln for ln in lines) else "READY (with warnings)")
    header = f"=== Ticket readiness report for {ac_id}: {verdict} ==="
    return "\n".join([header, *lines]), has_fail


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Generate a ticket file from an AC YAML record.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ac",
        required=True,
        dest="ac_id",
        help="AC id to generate a ticket for.",
    )
    parser.add_argument(
        "--ac-root",
        dest="ac_root",
        default=None,
        help=f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--tickets-root",
        dest="tickets_root",
        default=None,
        help=f"Root directory for written tickets (default: {_DEFAULT_TICKETS_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print the ticket body to stdout without writing.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        dest="verify",
        help=(
            "Print the ticket that WOULD be generated plus a readiness report "
            "checking whether the AC provides enough for a coder to build and a "
            "test-writer to test. Implies --dry-run. Exits non-zero on any FAIL."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for generate_ticket_from_ac.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    ac_id: str = args.ac_id

    # Resolve roots
    try:
        worktree = _find_worktree_root(Path(__file__))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ac_root = Path(args.ac_root) if args.ac_root else worktree / _DEFAULT_AC_ROOT
    tickets_root = Path(args.tickets_root) if args.tickets_root else worktree / _DEFAULT_TICKETS_ROOT

    if not ac_root.exists():
        print(f"ERROR: AC root not found: {ac_root}", file=sys.stderr)
        return 1

    # Find the AC
    result = _find_ac_by_id(ac_root, ac_id)
    if result is None:
        print(f"ERROR: AC id '{ac_id}' not found under {ac_root}", file=sys.stderr)
        return 1
    ac_path, ac = result

    # Compute repo-root-relative path to the AC file for ac_traceability.
    # ac_path is guaranteed to be under ac_root (found by _find_ac_by_id),
    # so relative_to(ac_root.parent.parent) always succeeds.
    ac_store_path = str(ac_path.relative_to(ac_root.parent.parent))

    # Dry-run / verify: build the ticket in memory, print it, and (for --verify)
    # append a readiness report. Neither path writes a file.
    if args.dry_run or args.verify:
        files_touched = _build_files_touched(ac)
        assigned_agent = ac.get("assigned_agent", "python-coder")
        change_targets = _normalize_change_target(ac)
        risk_surface = ac.get("risk_surface") or None
        agents = _build_agents_map(
            assigned_agent,
            change_targets=change_targets,
            risk_surface=risk_surface,
            files_touched=files_touched,
        )
        frontmatter = _build_frontmatter(ac, ac_id, files_touched, agents, ac_store_path)
        body = _build_ticket_body(ac, ac_id, agents_map=agents)
        print(frontmatter)
        print()
        print(body)
        if args.verify:
            report, has_fail = _build_verification_report(
                ac, ac_id, agents, body, files_touched
            )
            print()
            print(report)
            return 2 if has_fail else 0
        return 0

    # Idempotency guard: check for existing ticket
    tickets_root.mkdir(parents=True, exist_ok=True)
    existing = _find_existing_ticket(tickets_root, ac_id)
    if existing is not None:
        print(
            f"ERROR: ticket for AC '{ac_id}' already exists: {existing}",
            file=sys.stderr,
        )
        return 1

    # Build ticket content
    files_touched = _build_files_touched(ac)
    assigned_agent = ac.get("assigned_agent", "python-coder")
    change_targets = _normalize_change_target(ac)
    risk_surface = ac.get("risk_surface") or None
    agents = _build_agents_map(
        assigned_agent,
        change_targets=change_targets,
        risk_surface=risk_surface,
        files_touched=files_touched,
    )
    frontmatter = _build_frontmatter(ac, ac_id, files_touched, agents, ac_store_path)
    body = _build_ticket_body(ac, ac_id, agents_map=agents)
    ticket_content = frontmatter + "\n\n" + body

    # Write ticket file
    filename = _ticket_filename(ac_id)
    ticket_path = tickets_root / filename
    try:
        ticket_path.write_text(ticket_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: could not write ticket {ticket_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Written: {ticket_path}")

    # Write implemented_by back-reference into source AC
    relative_ticket_path = str(ticket_path.relative_to(worktree)) if ticket_path.is_relative_to(worktree) else str(ticket_path)
    try:
        _write_implemented_by(ac_path, relative_ticket_path, ac_id, worktree=worktree)
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"WARNING: ticket written but could not update implemented_by in {ac_path}: {exc}",
            file=sys.stderr,
        )
        # Non-fatal: ticket is written; only the back-reference failed.

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [ticket-01]: Initial implementation.
  Searches ac_root recursively for the AC with the given id. Extracts
  local paths from doc_links (filtering http URLs). Builds agents map with
  assigned_agent + canonical support agents. Writes ticket to tickets_root.
  Performs implemented_by back-write using targeted line replacement (not
  full yaml.dump round-trip) to minimise diff noise. Idempotency guard:
  exits 1 when a ticket with source_ac: <ac_id> already exists.
- 2026-07-08 [ticket-03 EPIC-PromptAssemblyHardening]: Add ## Implementation Notes emission.
  Added _build_implementation_notes_section() helper that serialises the
  it_requirements dict from an AC record to a YAML code block inside a
  ## Implementation Notes section. Omits the section entirely when
  it_requirements is absent (no empty stub). Section is placed after
  ## Test Requirements and before ## Sign-offs for consistent locatability.
  (AC BO-2000c-1, BO-2000c-1-i, BO-2000c-2)
- 2026-07-08 [feature/ac-source-of-truth-test-spec]: Derive ## Test Requirements
  from the AC (source of truth) instead of emitting a hardcoded tests: [] stub.
  Added _build_test_requirements_section() + _test_descriptors_from_spec()
  (from the AC's test_spec) with a _derive_tests_from_criteria() fallback
  (Gherkin Then-clauses). The derived block always carries >=1 populated test
  entry so the check-ticket-test-requirements guard passes by construction;
  omitted only when the AC sets test_required: false. Added a --verify flag +
  _build_verification_report() that prints the would-be ticket plus a PASS/WARN/
  FAIL readiness report (exits non-zero on FAIL) so an author can confirm the AC
  gives a coder enough to build and test-writer enough to test. (AC BO-2000e)
====================================================================
"""
