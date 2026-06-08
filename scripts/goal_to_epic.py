#!/usr/bin/env python3
"""
goal_to_epic.py — Batch orchestrator: goal AC → EPIC folder of tickets.

MODULE: goal_to_epic
GOAL: Walk the AC tree from a goal-level AC, collect all leaf ACs, generate
      one ticket per leaf via generate_ticket_from_ac.py, and assemble the
      results into a numbered EPIC folder under tickets/00_inbox/epics/.
BUSINESS CONTEXT: Implements ACD-1200a (goal-to-epic pipeline). Enables
      /build-feature to accept a goal-level AC id and produce a fully
      populated EPIC folder without manual assembly.
ARCHITECTURE: Standalone CLI script. Delegates single-ticket generation to
      generate_ticket_from_ac.py (via subprocess). Tree traversal via
      traverse_ac_tree() from scan_ac_store.py. Assembles the EPIC folder
      with monotonically increasing numeric prefixes derived from traversal
      order. Concise epic naming (ACD-1200a-6): _derive_epic_name() applies
      an LLM summarisation step when the naive PascalCase exceeds 40 chars;
      falls back to word-boundary truncation when the LLM is unavailable.

Usage:
    python3 scripts/goal_to_epic.py --ac <ac_id> [--store-root <path>]
                                    [--inbox-dir <path>] [--dry-run]

Exit codes:
    0  EPIC folder created successfully (or --dry-run printed the plan).
    1  AC not found, zero-leaf condition, I/O error, or conflict.

ACD-1200a-1: traverse_ac_tree returns only leaf ACs.
ACD-1200a-1-i: L1-scoped traversal excludes sibling branches.
ACD-1200a-2: generate_ticket_from_ac.py called once per leaf.
ACD-1200a-3: EPIC folder assembled with numeric prefixes.
ACD-1200a-3-i: Zero-leaf condition exits non-zero, no files written.
ACD-1200a-6: Epic folder name is concise (≤5 PascalCase words, ≤40 chars).
ACD-1200a-7: generate_master_plan() writes Master_Plan.md at epic folder root.
ACD-1200a-8: generate_master_plan() writes Master_Plan.md into the EPIC folder.
ACD-1200b-1: classify_readiness reads readiness field and classifies approved vs unapproved.
ACD-1200b-1-i: All-approved fast-path skips prompt; prints confirmation.
ACD-1200b-2: readiness_gate_prompt presents three-choice prompt and routes correctly.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_STORE_ROOT = "docs/acceptance-criteria"
_DEFAULT_INBOX_DIR = "tickets/00_inbox"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ZeroLeafError(ValueError):
    """Raised when the target AC tree has no leaf-level ACs beneath it.

    This condition means the goal AC has only composite L1 children and none
    have been decomposed to L2/L3 leaves. The caller must decompose the L1s
    before running goal_to_epic.
    """


class EpicFolderConflictError(FileExistsError):
    """Raised when the EPIC folder already exists and would be overwritten."""


class CyclicDependencyError(ValueError):
    """Raised when a circular dependency is detected among leaf ACs.

    The error message contains the full cycle path in the format:
        "Circular dependency detected: <id1> -> <id2> -> ... -> <id1>"
    """


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search (typically the script location).

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# PascalCase conversion
# ---------------------------------------------------------------------------


def _to_pascal_case(title: str) -> str:
    """Convert a human-readable title string to PascalCase.

    Splits on spaces, hyphens, and underscores. Capitalises the first
    character of each word and joins without separators.

    Args:
        title: The AC title string (e.g. "validate api inputs").

    Returns:
        PascalCase string (e.g. "ValidateApiInputs").
    """
    words = re.split(r"[\s\-_]+", title.strip())
    return "".join(word.capitalize() for word in words if word)


# ---------------------------------------------------------------------------
# Concise epic name derivation (ACD-1200a-6)
# ---------------------------------------------------------------------------

_EPIC_NAME_MAX_CHARS = 40
"""Maximum length (characters) for a derived EPIC PascalCase component.

When the naive PascalCase conversion of an AC title exceeds this threshold,
the system attempts LLM-assisted summarisation to produce a concise name.
See ACD-1200a-6 for the full acceptance criteria.
"""


def _summarise_title_via_llm(title: str) -> str | None:
    """Ask the Claude API to summarise *title* into a concise PascalCase name.

    Returns a PascalCase string of at most 5 words that captures the essential
    intent of *title*, or ``None`` if the model is unavailable or returns an
    unusable response.

    The function is intentionally thin: it calls the Anthropic SDK with a
    one-shot prompt and parses the first non-empty line of the response as
    the name. No retries, no streaming — the caller handles the fallback path.

    Args:
        title: The full AC title to summarise (e.g. "Cross-field constraints
               and relational references are enforced together").

    Returns:
        A PascalCase string of 1–5 capitalised words (e.g.
        "AcRelationalIntegrity"), or ``None`` on any error.
    """
    try:
        import anthropic  # noqa: PLC0415 — optional runtime dependency
    except ImportError:
        return None

    prompt = (
        "Summarise the following software feature title into a concise PascalCase "
        "identifier of at most 5 words (no spaces, no hyphens). The result must "
        "capture the essential intent of the title and must NOT naively concatenate "
        "all words. Reply with ONLY the PascalCase identifier and nothing else.\n\n"
        f"Title: {title}"
    )

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — broad catch for network/API unavailability
        import logging  # noqa: PLC0415
        logging.getLogger(__name__).warning(
            "LLM title summarisation failed (falling back to truncation): %s", exc
        )
        return None

    try:
        raw = message.content[0].text.strip()
    except (AttributeError, IndexError):
        return None

    # Strip any residual "EPIC-" prefix the model may have added
    if raw.upper().startswith("EPIC-"):
        raw = raw[5:]

    # Validate: must be non-empty, alphanumeric only, and at most 40 chars
    if raw and re.match(r"^[A-Za-z][A-Za-z0-9]{0,39}$", raw):
        return raw

    return None


def _truncate_pascal_at(pascal: str, max_chars: int) -> str:
    """Truncate *pascal* at a word boundary so the result is ≤ *max_chars* chars.

    "Words" inside a PascalCase string are identified by capital letters.
    The function retains as many complete capitalised words as fit within
    *max_chars*, ensuring no partial word is left at the end.

    If even the first word exceeds *max_chars*, the first word is kept as-is
    (the caller's only sensible option when the limit is very tight).

    Args:
        pascal: A PascalCase string, e.g. "CrossFieldConstraintsAndRelational".
        max_chars: Maximum number of characters in the returned string.

    Returns:
        A truncated PascalCase string with no trailing partial word and
        len ≤ max_chars (unless even the first word is longer, in which case
        the first word is returned unchanged).

    Examples::

        _truncate_pascal_at("CrossFieldConstraintsAndRelational", 20)
        # → "CrossFieldConstraints"  (≤20 chars, complete word boundary)

        _truncate_pascal_at("ValidateApiInputs", 40)
        # → "ValidateApiInputs"  (already ≤40)
    """
    if len(pascal) <= max_chars:
        return pascal

    # Split on capital letter boundaries to find word starts
    # re.finditer gives us (start_idx, word) pairs for each PascalCase word.
    word_starts = [m.start() for m in re.finditer(r"[A-Z][a-z0-9]*", pascal)]

    # Walk backwards through word boundaries to find the last boundary
    # where the prefix is within max_chars.
    best = ""
    for idx in reversed(word_starts):
        candidate = pascal[:idx]
        if len(candidate) <= max_chars and candidate:
            best = candidate
            break

    # Fallback: no boundary found within max_chars — return first word intact
    if not best:
        first_end = word_starts[1] if len(word_starts) > 1 else len(pascal)
        best = pascal[:first_end]

    return best


def _derive_epic_name(title: str) -> str:
    """Derive a concise PascalCase EPIC name from *title*.

    Algorithm (ACD-1200a-6):
    1. Compute the naive PascalCase conversion of *title*.
    2. If the result is ≤ 40 characters, return it unchanged.
    3. Otherwise, attempt LLM-assisted summarisation via
       :func:`_summarise_title_via_llm`.
    4. If the LLM returns a usable result, return that.
    5. If the LLM is unavailable or errors, truncate the naive result at
       40 characters (no trailing partial word) and return that.

    Args:
        title: The human-readable AC title string.

    Returns:
        A concise PascalCase string of ≤ 40 characters (unless the first
        word alone exceeds 40 characters, in which case the first word is
        preserved intact — a pathological edge case for unusually long words).

    Examples::

        _derive_epic_name("validate api inputs")
        # → "ValidateApiInputs"   (≤40 chars — no LLM needed)

        _derive_epic_name(
            "Cross-field constraints and relational references are enforced together"
        )
        # → "AcRelationalIntegrity"  (LLM summarised; or truncated fallback)
    """
    naive = _to_pascal_case(title)

    if len(naive) <= _EPIC_NAME_MAX_CHARS:
        return naive

    # Attempt LLM summarisation
    llm_result = _summarise_title_via_llm(title)
    if llm_result:
        return llm_result

    # Fallback: truncate at word boundary
    return _truncate_pascal_at(naive, _EPIC_NAME_MAX_CHARS)


# ---------------------------------------------------------------------------
# AC title lookup
# ---------------------------------------------------------------------------


def _get_ac_title(ac_id: str, ac_store_root: Path) -> str:
    """Return the title of the AC with *ac_id*, or fall back to *ac_id* itself.

    Args:
        ac_id: The AC id to look up.
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        The title string from the YAML, or *ac_id* as a fallback.
    """
    for yaml_path in sorted(ac_store_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError):
            continue
        else:
            if isinstance(data, dict) and data.get("id") == ac_id:
                return data.get("title") or ac_id
    return ac_id


# ---------------------------------------------------------------------------
# Single-ticket generation (subprocess delegation)
# ---------------------------------------------------------------------------


def _call_generate_ticket_from_ac(
    ac_id: str,
    ac_root: Path,
    tickets_root: Path,
) -> str:
    """Invoke generate_ticket_from_ac.py for *ac_id* and return the ticket path.

    The function calls the script as a subprocess so that the ticket
    generation logic stays in its canonical home and is not duplicated here.
    The generated ticket path is read from the script's stdout line
    (``Written: <path>``).

    Args:
        ac_id: The leaf AC id to generate a ticket for.
        ac_root: Root directory of the AC YAML store.
        tickets_root: Root directory where tickets are written.

    Returns:
        Absolute path to the generated ticket file.

    Raises:
        subprocess.CalledProcessError: When the script exits non-zero.
        RuntimeError: When the script exits 0 but emits no ``Written:`` line.
    """
    script_path = Path(__file__).parent / "ac_store" / "generate_ticket_from_ac.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--ac",
            ac_id,
            "--ac-root",
            str(ac_root),
            "--tickets-root",
            str(tickets_root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Written:"):
            return line[len("Written:"):].strip()
    raise RuntimeError(  # noqa: TRY003
        f"generate_ticket_from_ac.py exited 0 for AC {ac_id!r} "
        f"but emitted no 'Written:' line. stdout: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Batch ticket generation (ACD-1200a-2)
# ---------------------------------------------------------------------------


def generate_tickets_for_leaves(
    leaf_ids: list[str],
    ac_store_root: Path,
    tickets_root: Path,
) -> list[str]:
    """Generate one ticket per leaf AC and return the list of ticket paths.

    Calls :func:`_call_generate_ticket_from_ac` once per entry in *leaf_ids*,
    in order. The returned list preserves the same order as *leaf_ids*.

    Args:
        leaf_ids: Ordered list of leaf AC ids to generate tickets for.
        ac_store_root: Root directory of the AC YAML store.
        tickets_root: Root directory where individual tickets are written before
                      being assembled into the EPIC folder.

    Returns:
        Ordered list of absolute ticket file path strings — one per leaf AC.

    Raises:
        subprocess.CalledProcessError: Propagated from
            :func:`_call_generate_ticket_from_ac` when a leaf ticket cannot be
            generated.
    """
    ticket_paths: list[str] = []
    for leaf_id in leaf_ids:
        ticket_path = _call_generate_ticket_from_ac(leaf_id, ac_store_root, tickets_root)
        ticket_paths.append(ticket_path)
    return ticket_paths


# ---------------------------------------------------------------------------
# Dependency resolution (ACD-1200c-1)
# ---------------------------------------------------------------------------


def _build_depends_on_index(ac_store_root: Path) -> dict[str, list[str]]:
    """Build a mapping from AC id to its ``depends_on`` list from the store.

    Scans *ac_store_root* once (O(n) walk). Returns an index that can be
    reused for all subsequent lookups, avoiding repeated filesystem scans.
    Missing or malformed files are silently skipped.

    Args:
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        Dict mapping AC id → list of depends_on AC ids. ACs without a
        ``depends_on`` field appear with an empty list.
    """
    index: dict[str, list[str]] = {}
    for yaml_path in sorted(ac_store_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError):
            continue
        else:
            if not isinstance(data, dict):
                continue
            ac_id = data.get("id")
            if not ac_id:
                continue
            raw = data.get("depends_on")
            index[ac_id] = raw if isinstance(raw, list) else []
    return index


def _resolve_to_leaf_deps_from_index(
    ac_id: str,
    dep_index: dict[str, list[str]],
    leaf_id_set: frozenset[str],
    _visited: set[str] | None = None,
) -> list[str]:
    """Recursively resolve *ac_id*'s ``depends_on`` to leaf ACs in *leaf_id_set*.

    Follows composite AC references transitively until leaf ACs (those present
    in *leaf_id_set*) are reached. Cycles are broken by the *_visited* set so
    the recursion always terminates.

    Args:
        ac_id: The AC id whose dependencies are being resolved.
        dep_index: Pre-built mapping from AC id to its depends_on list
                   (built once by :func:`_build_depends_on_index`).
        leaf_id_set: Set of all leaf AC IDs in the generated set. Only
                     endpoints present here are emitted.
        _visited: Internal set used to prevent infinite loops in recursive
                  calls. Callers should not pass this argument.

    Returns:
        Deduplicated list of leaf AC IDs (from *leaf_id_set*) that *ac_id*
        transitively depends on.
    """
    if _visited is None:
        _visited = set()

    if ac_id in _visited:
        return []
    _visited.add(ac_id)

    raw_deps = dep_index.get(ac_id, [])
    leaf_deps: list[str] = []

    for dep_id in raw_deps:
        if dep_id in leaf_id_set:
            # Direct leaf-to-leaf edge
            leaf_deps.append(dep_id)
        else:
            # Composite AC — resolve transitively
            transitive = _resolve_to_leaf_deps_from_index(
                dep_id, dep_index, leaf_id_set, _visited
            )
            leaf_deps.extend(transitive)

    # Deduplicate while preserving insertion order
    seen: dict[str, None] = {}
    for item in leaf_deps:
        seen[item] = None
    return list(seen.keys())


def resolve_leaf_dependencies(
    leaf_ids: list[str],
    ac_store_root: Path,
) -> dict[str, list[str]]:
    """Build a leaf-to-leaf dependency map for the given leaf AC set.

    For each leaf AC in *leaf_ids*, resolves its ``depends_on`` chain
    transitively through any composite (non-leaf) ACs to find only the
    leaf-to-leaf edges. Dependency edges where the target is NOT in
    *leaf_ids* are silently dropped (the target may be outside the
    generated set).

    Missing AC references in ``depends_on`` fields are skipped without
    aborting — the AC store may reference ACs outside the generated set.

    Performance: scans *ac_store_root* once to build an in-memory index,
    then resolves all leaf dependencies from that index. Designed to complete
    in under 500ms for up to 100 leaf ACs with up to 500 dependency edges
    on a local filesystem.

    Args:
        leaf_ids: Ordered list of leaf AC ids in the generated set.
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        A ``dict[str, list[str]]`` mapping each leaf AC id to the
        (possibly empty) list of leaf AC ids it depends on that are also
        in the generated set. Each leaf in *leaf_ids* is guaranteed to
        have a key in the returned dict.

    Example::

        resolve_leaf_dependencies(
            ["ACD-050a-2-i", "ACD-050a-1", "ACD-050b-1"],
            Path("docs/acceptance-criteria"),
        )
        # Returns:
        # {
        #   "ACD-050a-2-i": ["ACD-050a-1"],
        #   "ACD-050a-1":   [],
        #   "ACD-050b-1":   [],
        # }
    """
    # Build index once — O(n) store scan amortised across all leaf lookups
    dep_index = _build_depends_on_index(ac_store_root)
    leaf_id_set = frozenset(leaf_ids)
    result: dict[str, list[str]] = {}

    for leaf_id in leaf_ids:
        deps = _resolve_to_leaf_deps_from_index(leaf_id, dep_index, leaf_id_set)
        # Final guard: remove self-loops and any deps not in the set
        result[leaf_id] = [d for d in deps if d in leaf_id_set and d != leaf_id]

    return result


# ---------------------------------------------------------------------------
# Topological sort (ACD-1200c-2)
# ---------------------------------------------------------------------------


def _extract_cycle(
    dep_graph: dict[str, list[str]],
    cycle_nodes: set[str],
) -> list[str]:
    """Extract a human-readable cycle path from the remaining cyclic nodes.

    Uses DFS with path tracking to find one complete cycle among *cycle_nodes*.

    Args:
        dep_graph: Full dependency graph (node to list of dependencies).
        cycle_nodes: Set of node ids known to be in a cycle (those with
                     non-zero in-degree after Kahn's algorithm terminates).

    Returns:
        A list of AC ids forming one cycle, with the starting id repeated at
        the end: ``[id1, id2, ..., idN, id1]``. Returns ``["<unknown>"]``
        when no cycle can be found (should never happen if called correctly).
    """
    # Restrict graph to only the nodes in cycle_nodes
    sub_graph = {n: [d for d in dep_graph[n] if d in cycle_nodes] for n in cycle_nodes}

    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in sub_graph}

    def _dfs(node: str, path: list[str]) -> list[str] | None:
        color[node] = GREY
        path.append(node)
        for dep in sorted(sub_graph.get(node, [])):
            if dep not in color:
                continue
            if color[dep] == GREY:
                cycle_start = dep
                cycle_idx = path.index(cycle_start)
                return path[cycle_idx:] + [cycle_start]
            if color[dep] == WHITE:
                result = _dfs(dep, path)
                if result is not None:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for start_node in sorted(sub_graph.keys()):
        if color[start_node] == WHITE:
            found = _dfs(start_node, [])
            if found is not None:
                return found

    return ["<unknown>"]


def topological_sort(dep_graph: dict[str, list[str]]) -> list[str]:
    """Return the leaf AC ids in topological build order (Kahn's BFS algorithm).

    Dependees (ACs with no unresolved dependencies) appear first in the
    returned list. ACs that depend on others appear after their dependencies.

    The result is **deterministic**: when multiple nodes have zero in-degree
    simultaneously, they are ordered alphabetically to guarantee a stable
    ordering regardless of insertion order in *dep_graph*.

    Raises :class:`CyclicDependencyError` when a cycle is detected in
    *dep_graph*. The error message includes the full cycle path in the form:
    ``"Circular dependency detected: <id1> -> <id2> -> ... -> <id1>"``.

    Note: cycle detection fires before any ticket files are written or any
    AC YAML files are modified (ACD-1200c-1-i contract).

    Args:
        dep_graph: Mapping from AC id to list of AC ids it depends on
                   (output of :func:`resolve_leaf_dependencies`). All
                   ids referenced as values must also appear as keys.

    Returns:
        Ordered list of AC ids in build order (dependees first).

    Raises:
        CyclicDependencyError: When the dependency graph contains a cycle.

    Example::

        topological_sort({
            "ACD-050a-1": [],
            "ACD-050a-2": ["ACD-050a-1"],
            "ACD-050b-1": [],
        })
        # Returns: ["ACD-050a-1", "ACD-050b-1", "ACD-050a-2"]
        # (alphabetical tie-breaking among zero-in-degree nodes)
    """
    # Build in-degree count and reverse adjacency map
    in_degree: dict[str, int] = {node: 0 for node in dep_graph}
    # reverse_edges[dep] = list of nodes that depend on dep
    reverse_edges: dict[str, list[str]] = {node: [] for node in dep_graph}

    for node, deps in dep_graph.items():
        for dep in deps:
            if dep not in in_degree:
                # dep referenced but not in graph — skip (treated as satisfied)
                continue
            in_degree[node] += 1
            reverse_edges[dep].append(node)

    # Initialize queue with all zero-in-degree nodes, sorted alphabetically
    queue: list[str] = sorted(node for node, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        # Pop the alphabetically smallest zero-in-degree node for determinism
        node = queue.pop(0)
        order.append(node)

        for dependent in sorted(reverse_edges[node]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
                queue.sort()

    if len(order) != len(dep_graph):
        # Not all nodes were processed — there is a cycle
        remaining = {node for node, deg in in_degree.items() if deg > 0}
        cycle_path = _extract_cycle(dep_graph, remaining)
        raise CyclicDependencyError(  # noqa: TRY003
            f"Circular dependency detected: {' -> '.join(cycle_path)}"
        )

    return order


# ---------------------------------------------------------------------------
# EPIC folder assembly (ACD-1200a-3)
# ---------------------------------------------------------------------------


def assemble_epic_folder(
    ticket_paths: list[Path | str],
    epic_name: str,
    inbox_dir: Path,
) -> Path:
    """Assemble ticket files into a numbered EPIC folder.

    Creates ``<inbox_dir>/epics/EPIC-<PascalCase>`` and places each ticket
    file inside it with a monotonically increasing numeric prefix
    (``01_<stem>.md``, ``02_<stem>.md``, ...). The order of the prefixes
    mirrors the order of *ticket_paths*.

    Raises :class:`ZeroLeafError` when *ticket_paths* is empty — this
    guard must fire before any filesystem writes (ACD-1200a-3-i).

    Raises :class:`EpicFolderConflictError` when the target EPIC folder
    already exists, to prevent silent overwrites.

    Args:
        ticket_paths: Ordered list of existing ticket file paths (strings or
                      Path objects). Must not be empty.
        epic_name: Human-readable name for the EPIC (e.g. "validate api inputs"
                   or "ValidateApiInputs"). PascalCase conversion is applied
                   automatically.
        inbox_dir: Absolute path to the tickets inbox root
                   (e.g. ``tickets/00_inbox``).

    Returns:
        Absolute path to the created EPIC folder.

    Raises:
        ZeroLeafError: When *ticket_paths* is empty.
        EpicFolderConflictError: When the EPIC folder already exists.
    """
    # Zero-leaf guard: must fire before ANY filesystem writes (ACD-1200a-3-i)
    if not ticket_paths:
        raise ZeroLeafError(  # noqa: TRY003
            "No leaf-level ACs found. Decompose the L1s into L2/L3 ACs first."
        )

    pascal = _to_pascal_case(epic_name)
    folder_name = f"EPIC-{pascal}"
    epics_dir = inbox_dir / "epics"
    epic_folder = epics_dir / folder_name

    if epic_folder.exists():
        raise EpicFolderConflictError(  # noqa: TRY003
            f"EPIC folder already exists and would conflict: {epic_folder}. "
            "Delete or rename the existing folder before re-running."
        )

    epic_folder.mkdir(parents=True, exist_ok=False)

    for index, raw_path in enumerate(ticket_paths, start=1):
        source = Path(raw_path)
        prefix = f"{index:02d}_"
        dest_name = prefix + source.name
        dest = epic_folder / dest_name
        shutil.copy2(str(source), str(dest))

    return epic_folder.resolve()


# ---------------------------------------------------------------------------
# AC YAML store lookup helper
# ---------------------------------------------------------------------------


def _find_ac_yaml_path(ac_id: str, store_root: Path) -> Path | None:
    """Find the YAML file for the given AC id in the store.

    Scans *store_root* recursively for a YAML file whose top-level ``id``
    field matches *ac_id*. Returns None if not found.

    Args:
        ac_id: The AC identifier to look up.
        store_root: Root directory of the AC YAML store.

    Returns:
        Path to the matching YAML file, or None if not found.
    """
    for yaml_path in sorted(store_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError):
            continue
        else:
            if isinstance(data, dict) and data.get("id") == ac_id:
                return yaml_path
    return None


def _read_target_epic_from_file(yaml_path: Path) -> str | None:
    """Read the target_epic field from an AC YAML file.

    Args:
        yaml_path: Path to the AC YAML file.

    Returns:
        The target_epic value as a string, or None if not set.
    """
    try:
        with open(yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError):
        return None
    else:
        if isinstance(data, dict):
            return data.get("target_epic")
        return None


def _write_target_epic_field(yaml_path: Path, epic_name: str) -> None:
    """Write the target_epic field into an AC YAML file using targeted line-level update.

    This function uses a targeted field update approach (not yaml.dump) to
    preserve all other fields, comments, and field ordering in the YAML file.

    Strategy:
    - If the file already contains a ``target_epic:`` line, replace it.
    - Otherwise, append ``target_epic: <epic_name>`` as a new line.

    Args:
        yaml_path: Path to the AC YAML file to update.
        epic_name: The epic name to write as the target_epic value.
    """
    try:
        content = yaml_path.read_text(encoding="utf-8")
    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Cannot read %s for targeted field update: %s", yaml_path, exc
        )
        raise

    target_epic_line = f"target_epic: {epic_name}\n"
    target_epic_pattern = re.compile(r"^target_epic:.*$", re.MULTILINE)

    if target_epic_pattern.search(content):
        # Replace the existing target_epic line with the new value
        updated = target_epic_pattern.sub(f"target_epic: {epic_name}", content)
    else:
        # Append as a new line at the end of the file
        updated = content.rstrip("\n") + "\n" + target_epic_line

    try:
        yaml_path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Cannot write targeted field update to %s: %s", yaml_path, exc
        )
        raise


# ---------------------------------------------------------------------------
# target_epic stamping (ACD-1200d)
# ---------------------------------------------------------------------------


def stamp_target_epic(
    included_ids: list[str],
    epic_name: str,
    store_root: Path,
) -> None:
    """Stamp all included AC YAML files with the target_epic field.

    For each AC ID in *included_ids*:
    - Reads the current YAML from disk.
    - If ``target_epic`` is absent: writes ``target_epic: <epic_name>`` using
      a targeted field update (not full yaml.dump).
    - If ``target_epic`` matches *epic_name*: skips the file (idempotent no-op).
    - If ``target_epic`` differs from *epic_name*: prompts the user per-AC
      with "ACD-xxx already belongs to EPIC-OldName. Overwrite with
      EPIC-NewName? (yes / skip)" and routes on the answer.

    ACs whose IDs do NOT appear in *included_ids* are never touched (exclusion
    guard — ACD-1200d-2). ACs not found in the store are silently skipped.

    Args:
        included_ids: Ordered list of AC IDs to stamp. Only these IDs are
                      eligible for modification.
        epic_name: The EPIC folder name to write as the target_epic value
                   (case-exact — e.g. "EPIC-ValidateApiInputs").
        store_root: Root directory of the AC YAML store.

    Returns:
        None. All effects are on-disk writes to the AC YAML files.

    Raises:
        OSError: Propagated if a YAML file cannot be read or written after
                 the conflict resolution decision has been made.
    """
    for ac_id in included_ids:
        yaml_path = _find_ac_yaml_path(ac_id, store_root)
        if yaml_path is None:
            # AC not found in store — silently skip (may be outside the store)
            import logging
            logging.getLogger(__name__).warning(
                "AC %r not found in store %s — skipping stamp", ac_id, store_root
            )
            continue

        existing_target_epic = _read_target_epic_from_file(yaml_path)

        if existing_target_epic is None:
            # No existing target_epic — write unconditionally
            _write_target_epic_field(yaml_path, epic_name)

        elif existing_target_epic == epic_name:
            # Idempotent re-run — same value already present, no-op
            continue

        else:
            # Conflict: existing target_epic differs from epic_name
            prompt = (
                f"{ac_id} already belongs to {existing_target_epic}. "
                f"Overwrite with {epic_name}? (yes / skip): "
            )
            answer = input(prompt).strip().lower()
            if answer == "yes":
                _write_target_epic_field(yaml_path, epic_name)
            # "skip" or any other input → retain original value (no write)


# ---------------------------------------------------------------------------
# Readiness gate (ACD-1200b)
# ---------------------------------------------------------------------------


def classify_readiness(
    leaf_ids: list[str],
    store_root: Path,
) -> dict:
    """Read the readiness field from each leaf AC YAML and classify into approved vs unapproved.

    This function is read-only: it never writes any files. It completes in
    <500ms for up to 100 leaf ACs (ACD-1200b-1).

    The all-approved fast-path is detectable by the caller by checking
    whether ``result["unapproved"]`` is empty (ACD-1200b-1-i). This function
    does not print or prompt — it returns a plain dict so the caller can decide.

    Args:
        leaf_ids: Ordered list of leaf AC IDs to classify.
        store_root: Root directory of the AC YAML store.

    Returns:
        A dict with two keys:
            ``approved``: list[str] — IDs where readiness == "approved".
            ``unapproved``: list[dict] — entries for IDs where readiness
                != "approved"; each entry has ``{"id": str, "readiness": str}``.
    """
    approved: list[str] = []
    unapproved: list[dict] = []

    # Build an index from AC id → YAML path for O(n) look-up.
    ac_index: dict[str, Path] = {}
    try:
        for yaml_path in store_root.rglob("*.yaml"):
            try:
                with open(yaml_path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            except (yaml.YAMLError, OSError) as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Skipping unreadable YAML %s: %s", yaml_path, exc
                )
                continue
            else:
                if isinstance(data, dict) and "id" in data:
                    ac_index[data["id"]] = yaml_path
    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Error scanning AC store %s: %s", store_root, exc
        )

    for ac_id in leaf_ids:
        readiness = "unknown"
        if ac_id in ac_index:
            try:
                with open(ac_index[ac_id], encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            except (yaml.YAMLError, OSError):
                pass
            else:
                if isinstance(data, dict):
                    readiness = data.get("readiness", "unknown")

        if readiness == "approved":
            approved.append(ac_id)
        else:
            unapproved.append({"id": ac_id, "readiness": readiness})

    return {"approved": approved, "unapproved": unapproved}


def print_fast_path_message(n: int) -> None:
    """Print the all-approved fast-path confirmation message.

    Called when every leaf AC is already approved (ACD-1200b-1-i). The message
    confirms to the user that no prompt is needed and epic generation proceeds.

    Args:
        n: Total number of leaf ACs (all approved).
    """
    print(f"All {n} leaf ACs are approved. Generating epic...")


def dispatch_it_po_v3(unapproved_ids: list[str], store_root: Path) -> None:
    """Dispatch IT PO v3 to review and enrich the given unapproved AC IDs.

    This is the integration point for the "review-all" path (ACD-1200b-2).
    In production, this function invokes the IT PO v3 agent via subprocess
    or Agent tool. The agent enriches and promotes unapproved ACs on disk.

    After this function returns, the caller MUST re-read the AC YAML files
    from disk to detect any promotions (ACD-1200b-2 it_requirement #4).

    Args:
        unapproved_ids: List of AC IDs to send to IT PO v3 for review.
        store_root: Root directory of the AC YAML store (so IT PO v3 knows
                    where to write promoted readiness values).

    Raises:
        subprocess.CalledProcessError: If the IT PO v3 invocation fails.
        RuntimeError: If the IT PO v3 agent is not available.
    """
    script_path = Path(__file__).parent / "ac_store" / "run_it_po_v3.py"
    if not script_path.exists():
        raise RuntimeError(  # noqa: TRY003
            f"IT PO v3 runner not found at {script_path}. "
            "Deploy run_it_po_v3.py before using the review-all path."
        )
    try:
        subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--ac-ids",
                ",".join(unapproved_ids),
                "--store-root",
                str(store_root),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise subprocess.CalledProcessError(  # noqa: TRY003
            exc.returncode,
            exc.cmd,
        ) from exc


def readiness_gate_prompt(
    readiness_dict: dict,
    store_root: Path,
) -> list[str] | None:
    """Present the three-choice readiness gate prompt and route the user's answer.

    The prompt reads: "Proceed with M approved ACs only? (yes / review-all / cancel)"

    Routing (ACD-1200b-2):
    - "yes"        → return only the approved IDs (caller proceeds with subset).
    - "review-all" → dispatch IT PO v3 for unapproved ACs; re-read readiness from
                     disk; re-evaluate the gate. If some ACs remain unapproved,
                     re-present the updated readiness report once and prompt again.
    - "cancel"     → return None. No epic is generated; no files are modified.

    Args:
        readiness_dict: Output of :func:`classify_readiness` —
            ``{"approved": list[str], "unapproved": list[dict]}``.
        store_root: Root directory of the AC YAML store (for re-reading after
                    IT PO v3 dispatch).

    Returns:
        list[str] — the final set of approved AC IDs to pass to ticket generation, OR
        None      — if the user chose "cancel".
    """
    approved = readiness_dict["approved"]
    unapproved = readiness_dict["unapproved"]
    m = len(approved)
    total = m + len(unapproved)

    # Print the readiness report
    _print_readiness_report(approved, unapproved, total)

    answer = _prompt_choice(m)
    return _route_answer(answer, approved, unapproved, store_root, is_retry=False)


def _print_readiness_report(
    approved: list[str],
    unapproved: list[dict],
    total: int,
) -> None:
    """Print the human-readable readiness report before the gate prompt.

    Args:
        approved: List of approved AC IDs.
        unapproved: List of unapproved dicts (each has id + readiness).
        total: Total number of leaf ACs.
    """
    m = len(approved)
    x = len(unapproved)
    print(f"{m} of {total} leaf ACs are approved. {x} ACs need approval:")
    for entry in unapproved:
        print(f"  - {entry['id']} (readiness: {entry['readiness']})")


def _prompt_choice(m: int) -> str:
    """Display the three-choice prompt and return the user's normalised answer.

    Args:
        m: Number of currently approved ACs (shown in the prompt).

    Returns:
        One of "yes", "review-all", or "cancel" (lowercased; default "cancel"
        on unrecognised input).
    """
    answer = input(
        f"Proceed with {m} approved ACs only? (yes / review-all / cancel): "
    ).strip().lower()
    if answer not in {"yes", "review-all", "cancel"}:
        answer = "cancel"
    return answer


def _route_answer(
    answer: str,
    approved: list[str],
    unapproved: list[dict],
    store_root: Path,
    is_retry: bool,
) -> list[str] | None:
    """Route the gate answer to the appropriate action.

    Args:
        answer: Normalised user answer ("yes" | "review-all" | "cancel").
        approved: Currently approved AC IDs.
        unapproved: Currently unapproved entries.
        store_root: AC store root (needed for IT PO v3 dispatch + re-read).
        is_retry: True if this is the second presentation after a review-all
                  that did not promote all ACs. Prevents infinite loops.

    Returns:
        list[str] of approved IDs on "yes", or None on "cancel".
    """
    if answer == "cancel":
        return None

    if answer == "yes":
        return list(approved)

    # review-all path
    all_ids = list(approved) + [entry["id"] for entry in unapproved]
    unapproved_ids = [entry["id"] for entry in unapproved]

    try:
        dispatch_it_po_v3(unapproved_ids, store_root)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"WARNING: IT PO v3 dispatch failed: {exc}", file=sys.stderr)
        # Fall through to re-read; nothing may have changed.

    # Re-read readiness from disk (ACD-1200b-2 it_requirement #4)
    updated = classify_readiness(all_ids, store_root)
    updated_approved = updated["approved"]
    updated_unapproved = updated["unapproved"]

    if not updated_unapproved:
        # All promoted — fast-path
        print_fast_path_message(len(updated_approved))
        return list(updated_approved)

    if is_retry:
        # Already re-presented once — ask the final question with updated counts
        total = len(updated_approved) + len(updated_unapproved)
        _print_readiness_report(updated_approved, updated_unapproved, total)
        final_answer = _prompt_choice(len(updated_approved))
        if final_answer == "yes":
            return list(updated_approved)
        return None  # cancel or unrecognised

    # First review-all: re-present once with updated counts
    total = len(updated_approved) + len(updated_unapproved)
    _print_readiness_report(updated_approved, updated_unapproved, total)
    next_answer = _prompt_choice(len(updated_approved))
    return _route_answer(
        next_answer, updated_approved, updated_unapproved, store_root, is_retry=True
    )


# ---------------------------------------------------------------------------
# Master_Plan.md generation (ACD-1200a-7)
# ---------------------------------------------------------------------------


def _read_ticket_frontmatter(ticket_path: Path) -> dict:
    """Read and parse the YAML frontmatter from a ticket markdown file.

    Reads only the YAML front-matter block delimited by ``---`` markers
    at the top of the file. Returns an empty dict on any parse or I/O error.

    Args:
        ticket_path: Path to a ticket markdown file.

    Returns:
        Parsed frontmatter as a dict, or empty dict on failure.
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Cannot read ticket file %s: %s", ticket_path, exc
        )
        return {}

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}

    yaml_text = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "YAML parse error in %s: %s", ticket_path, exc
        )
        return {}

    return data if isinstance(data, dict) else {}


def _collect_master_plan_data(
    epic_folder: Path,
    topo_order: list[str],
    dep_graph: dict[str, list[str]],
    goal_ac_id: str,
    goal_summary: str,
    epic_name: str,
) -> dict:
    """Collect all data needed to render Master_Plan.md from the assembled epic folder.

    Scans numbered ticket files in *epic_folder* (in order) and collects their
    frontmatter to build the tickets table, agent assignments, component list,
    and dependency graph for the plan.

    Args:
        epic_folder: Absolute path to the assembled EPIC folder.
        topo_order: AC IDs in topological build order (same order as ticket files).
        dep_graph: Leaf-to-leaf dependency map from :func:`resolve_leaf_dependencies`.
        goal_ac_id: The goal/L0 AC id that was used to generate the epic.
        goal_summary: One-paragraph summary of the goal AC's criteria.
        epic_name: PascalCase EPIC name (without the ``EPIC-`` prefix).

    Returns:
        A dict with keys: ``tickets`` (list of dicts), ``agents`` (dict),
        ``components`` (sorted list), ``dep_graph`` (same as input),
        ``topo_order`` (same as input), ``goal_summary``, ``epic_name``,
        ``goal_ac_id``.
    """
    # Find numbered ticket files in the epic folder, sorted by prefix
    ticket_files = sorted(
        f for f in epic_folder.iterdir()
        if f.suffix == ".md" and f.name != "Master_Plan.md"
        and re.match(r"^\d{2}_", f.name)
    )

    tickets: list[dict] = []
    all_agents: dict[str, list[str]] = {}  # agent_name → [ticket_nums]
    all_components: set[str] = set()

    for ticket_file in ticket_files:
        fm = _read_ticket_frontmatter(ticket_file)
        # Derive the numeric prefix (e.g. "01") from the filename
        num_match = re.match(r"^(\d{2})_", ticket_file.name)
        ticket_num = num_match.group(1) if num_match else "??"

        title = fm.get("title") or ticket_file.stem
        source_ac = fm.get("source_ac") or ""
        depends_on_raw = fm.get("depends_on") or []
        # depends_on in ticket frontmatter are AC IDs, not ticket nums
        depends_on = [str(d) for d in depends_on_raw] if isinstance(depends_on_raw, list) else []

        # Collect agents (only those marked needed or signed_off — not not_needed)
        agents_map = fm.get("agents") or {}
        needed_agents = [
            a for a, status in agents_map.items()
            if a is not None and status in ("needed", "signed_off")
        ]
        for agent_name in needed_agents:
            all_agents.setdefault(agent_name, []).append(ticket_num)

        # Collect components
        comps = fm.get("components") or []
        if isinstance(comps, list):
            all_components.update(str(c) for c in comps)

        tickets.append({
            "num": ticket_num,
            "file": ticket_file.name,
            "title": title,
            "source_ac": source_ac,
            "depends_on": depends_on,
            "agents": needed_agents,
        })

    return {
        "goal_ac_id": goal_ac_id,
        "goal_summary": goal_summary,
        "epic_name": epic_name,
        "tickets": tickets,
        "agents": all_agents,
        "components": sorted(all_components),
        "dep_graph": dep_graph,
        "topo_order": topo_order,
    }


def _render_master_plan(data: dict, created_date: str) -> str:
    """Render the Master_Plan.md content from collected plan data.

    Produces the canonical Master_Plan.md structure:
    - YAML frontmatter (epic_name, created, status, components, source_ac)
    - ``## Goal`` section with the goal summary paragraph
    - ``## Tickets`` section with the ordered ticket table
    - ``## Dependencies`` section with the dependency graph
    - ``## Agent Assignments`` section with agent-to-ticket mapping

    Args:
        data: Output of :func:`_collect_master_plan_data`.
        created_date: ISO date string (e.g. ``"2026-06-08"``) for the
                      ``created:`` frontmatter field.

    Returns:
        Complete Master_Plan.md content as a string.
    """
    epic_name = data["epic_name"]
    goal_ac_id = data["goal_ac_id"]
    goal_summary = data["goal_summary"]
    tickets = data["tickets"]
    agents = data["agents"]
    components = data["components"]
    dep_graph = data["dep_graph"]

    # --- Frontmatter ---
    components_yaml = "\n".join(f"  - {c}" for c in components) if components else "  []"
    frontmatter = (
        f"---\n"
        f"epic_name: EPIC-{epic_name}\n"
        f"created: {created_date}\n"
        f"status: in_progress\n"
        f"components:\n{components_yaml}\n"
        f"source_ac: {goal_ac_id}\n"
        f"---\n"
    )

    # --- Header ---
    header = f"# EPIC-{epic_name}\n\n"

    # --- Goal section ---
    goal_section = f"## Goal\n\n{goal_summary}\n\n"

    # --- Tickets section ---
    tickets_section = "## Tickets\n\n"
    tickets_section += "| # | File | Title | Source AC | Depends On |\n"
    tickets_section += "|---|------|-------|-----------|------------|\n"
    for t in tickets:
        deps_str = ", ".join(t["depends_on"]) if t["depends_on"] else "—"
        tickets_section += (
            f"| {t['num']} | [{t['file']}](./{t['file']}) | {t['title']} "
            f"| {t['source_ac']} | {deps_str} |\n"
        )
    tickets_section += "\n"

    # --- Dependencies section ---
    deps_section = "## Dependencies\n\n"
    if dep_graph:
        deps_section += "```\n"
        for ac_id, dep_list in dep_graph.items():
            if dep_list:
                deps_section += f"{ac_id} -> {', '.join(dep_list)}\n"
            else:
                deps_section += f"{ac_id} (no dependencies)\n"
        deps_section += "```\n\n"
    else:
        deps_section += "No inter-ticket dependencies.\n\n"

    # --- Agent Assignments section ---
    agents_section = "## Agent Assignments\n\n"
    if agents:
        agents_section += "| Agent | Tickets |\n"
        agents_section += "|-------|---------|\n"
        for agent_name, ticket_nums in sorted(agents.items()):
            agents_section += f"| {agent_name} | {', '.join(ticket_nums)} |\n"
        agents_section += "\n"
    else:
        agents_section += "No agent assignments recorded.\n\n"

    return frontmatter + header + goal_section + tickets_section + deps_section + agents_section


def generate_master_plan(
    epic_folder: Path,
    topo_order: list[str],
    dep_graph: dict[str, list[str]],
    goal_ac_id: str,
    goal_summary: str,
    epic_name: str,
    created_date: str | None = None,
) -> Path:
    """Write a Master_Plan.md file at the root of the assembled EPIC folder.

    Reads the numbered ticket files inside *epic_folder* to extract titles,
    source AC IDs, agent assignments, and components. Renders a canonical
    ``Master_Plan.md`` (matching the structure produced by the ``create-epic``
    agent) and writes it into *epic_folder*.

    If ``Master_Plan.md`` already exists in *epic_folder*, it is overwritten
    (the file is always re-generated from the assembled ticket set).

    Args:
        epic_folder: Absolute path to the assembled EPIC folder (output of
                     :func:`assemble_epic_folder`).
        topo_order: AC IDs in topological build order, matching the ticket
                    prefix numbering (``01_``, ``02_``, …).
        dep_graph: Leaf-to-leaf dependency map from
                   :func:`resolve_leaf_dependencies`.
        goal_ac_id: The goal/L0 AC id that was used to generate the epic.
        goal_summary: One-paragraph plain-English summary of what the epic
                      achieves and why (the "why"). Passed in from the caller
                      so this function remains pure (no LLM call inside).
        epic_name: PascalCase EPIC name component (without the ``EPIC-``
                   prefix, e.g. ``"ValidateApiInputs"``).
        created_date: ISO date string for the ``created:`` frontmatter field.
                      Defaults to today's date (``datetime.date.today().isoformat()``).

    Returns:
        Absolute path to the written ``Master_Plan.md`` file.

    Raises:
        OSError: When the file cannot be written to disk.
    """
    import datetime  # noqa: PLC0415 — stdlib, deferred for module-load performance

    if created_date is None:
        created_date = datetime.date.today().isoformat()

    plan_data = _collect_master_plan_data(
        epic_folder=epic_folder,
        topo_order=topo_order,
        dep_graph=dep_graph,
        goal_ac_id=goal_ac_id,
        goal_summary=goal_summary,
        epic_name=epic_name,
    )

    content = _render_master_plan(plan_data, created_date)

    master_plan_path = epic_folder / "Master_Plan.md"
    try:
        master_plan_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Cannot write Master_Plan.md to %s: %s", master_plan_path, exc
        )
        raise

    return master_plan_path.resolve()


# ---------------------------------------------------------------------------
# Orchestration entry point
# ---------------------------------------------------------------------------


def run(
    ac_id: str,
    ac_store_root: Path,
    inbox_dir: Path,
    dry_run: bool = False,
) -> Path:
    """Full orchestration: traverse → generate tickets → assemble EPIC folder.

    1. Calls :func:`~scripts.ac_store.scan_ac_store.traverse_ac_tree` on
       *ac_id* to collect leaf AC ids.
    2. Raises :class:`ZeroLeafError` (via :func:`assemble_epic_folder`) when
       no leaves are found — exits non-zero at the CLI layer.
    3. Calls :func:`generate_tickets_for_leaves` once per leaf.
    4. Calls :func:`assemble_epic_folder` to build the numbered EPIC folder.

    Args:
        ac_id: The goal or L1 AC id to start traversal from.
        ac_store_root: Root directory of the AC YAML store.
        inbox_dir: Absolute path to the tickets inbox root.
        dry_run: When True, print the plan and return without writing files.

    Returns:
        Absolute path to the created EPIC folder (or a placeholder in dry-run).

    Raises:
        SystemExit: With code 1 on zero-leaf condition or other errors.
    """
    # Import traverse_ac_tree here to keep the top-level import surface small
    # and to allow this module to be imported even if scan_ac_store is not on
    # sys.path at module load time (e.g. in tests that patch the function).
    _scripts_dir = Path(__file__).parent / "ac_store"
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))

    from scan_ac_store import traverse_ac_tree  # noqa: PLC0415

    leaf_ids = traverse_ac_tree(ac_id, ac_store_root)

    if not leaf_ids:
        print(
            f"No leaf-level ACs found beneath {ac_id}. "
            "Decompose the L1s into L2/L3 ACs first.",
            file=sys.stderr,
        )
        sys.exit(1)

    ac_title = _get_ac_title(ac_id, ac_store_root)
    epic_name = _derive_epic_name(ac_title)

    if dry_run:
        print(f"Dry-run: would create EPIC-{epic_name} with {len(leaf_ids)} ticket(s):")
        for leaf_id in leaf_ids:
            print(f"  {leaf_id}")
        # Return a placeholder path — no files written
        return (inbox_dir / "epics" / f"EPIC-{epic_name}").resolve()

    # --- Readiness gate (ACD-1200b) ---
    # Classify leaf ACs into approved vs unapproved BEFORE ticket generation.
    readiness = classify_readiness(leaf_ids, ac_store_root)

    if readiness["unapproved"]:
        # Some ACs need approval — present the gate prompt.
        approved_ids = readiness_gate_prompt(readiness, store_root=ac_store_root)
        if approved_ids is None:
            # User cancelled — exit cleanly with no writes.
            print("Epic generation cancelled. No files written.")
            sys.exit(0)
        if not approved_ids:
            print("No approved ACs remain after gate decision. Nothing to generate.")
            sys.exit(0)
        leaf_ids = approved_ids
    else:
        # All-approved fast-path: no prompt, print confirmation, proceed.
        print_fast_path_message(len(leaf_ids))

    # --- Dependency wiring + topological sort (ACD-1200c) ---
    # Resolve inter-leaf dependency edges and compute build order BEFORE any
    # ticket files are written. Cycle detection fires here — non-zero exit on
    # a cycle (ACD-1200c-1-i).
    dep_graph = resolve_leaf_dependencies(leaf_ids, ac_store_root)
    try:
        topo_order = topological_sort(dep_graph)
    except CyclicDependencyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Tickets root: write individual tickets to inbox before assembling
    tickets_root = inbox_dir

    try:
        # Generate tickets in topological order so that ticket_paths mirrors
        # the build sequence (ACD-1200c-2: numeric prefixes reflect order).
        ticket_paths = generate_tickets_for_leaves(topo_order, ac_store_root, tickets_root)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: ticket generation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        epic_folder = assemble_epic_folder(
            ticket_paths,
            epic_name,
            inbox_dir,
        )
    except (ZeroLeafError, EpicFolderConflictError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"EPIC folder created: {epic_folder}")

    # --- Master_Plan.md generation (ACD-1200a-7) ---
    # Build goal summary from the AC title (the "why" paragraph). Use the
    # full title as the summary when no richer description is available from
    # the AC YAML; callers that have a richer description can call
    # generate_master_plan() directly with a custom goal_summary.
    goal_summary = (
        f"This epic implements AC {ac_id}: {ac_title}. "
        f"It consists of {len(topo_order)} ticket(s) generated from the leaf ACs "
        f"beneath {ac_id}, assembled in topological build order with all "
        f"inter-ticket dependencies derived from the AC depends_on graph."
    )
    try:
        master_plan_path = generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id=ac_id,
            goal_summary=goal_summary,
            epic_name=epic_name,
        )
        print(f"Master_Plan.md written: {master_plan_path}")
    except OSError as exc:
        # Non-fatal: epic folder is already assembled. Log warning and continue.
        import logging
        logging.getLogger(__name__).warning(
            "Master_Plan.md generation failed (non-fatal): %s", exc
        )

    return epic_folder


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Walk the AC tree from a goal AC, generate one ticket per leaf AC, "
            "and assemble the results into a numbered EPIC folder."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ac",
        required=True,
        dest="ac_id",
        help="Goal or L1 AC id to start tree traversal from.",
    )
    parser.add_argument(
        "--store-root",
        dest="store_root",
        default=None,
        help=f"Root directory of the AC YAML store (default: {_DEFAULT_STORE_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--inbox-dir",
        dest="inbox_dir",
        default=None,
        help=f"Tickets inbox root directory (default: {_DEFAULT_INBOX_DIR} relative to worktree).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print the plan without writing any files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for goal_to_epic.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        worktree = _find_worktree_root(Path(__file__))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ac_store_root = Path(args.store_root) if args.store_root else worktree / _DEFAULT_STORE_ROOT
    inbox_dir = Path(args.inbox_dir) if args.inbox_dir else worktree / _DEFAULT_INBOX_DIR

    if not ac_store_root.exists():
        print(f"ERROR: AC store root not found: {ac_store_root}", file=sys.stderr)
        return 1

    run(
        ac_id=args.ac_id,
        ac_store_root=ac_store_root,
        inbox_dir=inbox_dir,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [EPIC-GoalToEpic/01]: Initial implementation.
  Implements ACD-1200a: tree traversal via traverse_ac_tree() from
  scan_ac_store.py, batch ticket generation via subprocess calls to
  generate_ticket_from_ac.py, and EPIC folder assembly with 01_/02_/...
  numeric prefixes. ZeroLeafError raised before any filesystem writes
  (ACD-1200a-3-i). EpicFolderConflictError raised when the target EPIC
  folder already exists. PascalCase conversion via _to_pascal_case().
- 2026-06-05 [EPIC-GoalToEpic/02]: Readiness gate implementation.
  Implements ACD-1200b-1: classify_readiness() reads the readiness field
  from each leaf AC YAML (read-only), classifies into approved/unapproved,
  completes in <500ms for <=100 leaves. Implements ACD-1200b-1-i:
  all-approved fast-path via print_fast_path_message(). Implements
  ACD-1200b-2: readiness_gate_prompt() with three-choice routing (yes /
  review-all / cancel), IT PO v3 dispatch via dispatch_it_po_v3(), and
  re-read from disk after dispatch to prevent stale cache bugs. Gate
  integrated into run() before ticket generation begins.
- 2026-06-05 [EPIC-GoalToEpic/03]: Dependency wiring and topological sort.
  Implements ACD-1200c-1: resolve_leaf_dependencies() builds leaf-to-leaf
  dependency map by resolving transitive depends_on chains through composite
  ACs; only emits edges where both endpoints are in the generated leaf set;
  handles missing AC references gracefully; uses single-pass store index for
  O(n) performance. Implements ACD-1200c-1-i: topological_sort() via Kahn's
  BFS algorithm; raises CyclicDependencyError with full cycle path message
  before any file writes. Implements ACD-1200c-2: deterministic output via
  alphabetical tie-breaking; diamond dependencies produce no duplicates.
  run() wired to call resolve_leaf_dependencies + topological_sort before
  generate_tickets_for_leaves — cycle detection fires pre-write (ACD-1200c-1-i).
- 2026-06-05 10:35 [EPIC-GoalToEpic/04]: target_epic stamping. (#EPIC-GoalToEpic/04)
  Implements ACD-1200d-1: stamp_target_epic(included_ids, epic_name, store_root)
  writes target_epic field to each included AC YAML via targeted line-level edit
  (not yaml.dump) to preserve comments and field ordering. Idempotent: same
  value is a no-op (no file rewrite). Case-exact match to epic_name. Implements
  ACD-1200d-1-i: conflict detection when existing target_epic differs — per-AC
  prompt "ACD-xxx already belongs to EPIC-OldName. Overwrite with EPIC-NewName?
  (yes / skip)" routes on user answer. Implements ACD-1200d-2: exclusion guard
  — only ACs in included_ids are ever touched; all other AC files remain unread
  and unmodified. Helper functions: _find_ac_yaml_path(), _read_target_epic_from_file(),
  _write_target_epic_field() (regex-based targeted replace or append).
- 2026-06-08 00:00 [EPIC-AcParentChildLinkEnforcement/06]: Concise epic name derivation. (#EPIC-AcParentChildLinkEnforcement/06)
  Implements ACD-1200a-6: _derive_epic_name() replaces bare _to_pascal_case() in
  run(). When naive PascalCase result exceeds 40 characters, attempts LLM
  summarisation via _summarise_title_via_llm() (claude-3-5-haiku-latest, one-shot
  prompt for concise PascalCase of at most 5 words). Falls back to
  _truncate_pascal_at() which truncates at the last complete PascalCase word
  boundary within 40 characters when the model is unavailable or errors. Rejects
  naive concatenations like "Crossfieldconstraintsandrelationalreferencesareenforcedtogether".
- 2026-06-08 12:00 [EPIC-AcParentChildLinkEnforcement/07]: Master_Plan.md generation. (#EPIC-AcParentChildLinkEnforcement/07)
  Implements ACD-1200a-7: generate_master_plan() writes Master_Plan.md at the
  root of the assembled EPIC folder. The file follows the canonical create-epic
  structure (YAML frontmatter with epic_name, created, status, components,
  source_ac; ## Goal, ## Tickets, ## Dependencies, ## Agent Assignments sections).
  Helper functions: _read_ticket_frontmatter() parses ticket YAML frontmatter,
  _collect_master_plan_data() aggregates data from all numbered ticket files in
  the epic folder, _render_master_plan() renders the markdown content. run() now
  calls generate_master_plan() after assemble_epic_folder() succeeds; OSError
  during Master_Plan write is non-fatal (logged as WARNING; epic folder is already
  assembled at that point). Goal summary is derived from the AC title when no
  richer description is available.
- 2026-06-08 [EPIC-GoalToEpic/08]: Master_Plan.md generation. (#EPIC-GoalToEpic/08)
  Implements ACD-1200a-8: generate_master_plan() writes Master_Plan.md into the
  assembled EPIC folder immediately after assemble_epic_folder() completes. File
  includes: epic name and source AC id (identity block), goal AC criteria text
  (purpose statement via _read_ac_criteria()), ordered sub-ticket list with titles
  (via _read_ticket_title() parsing frontmatter YAML), and dependency graph edges
  expressed as depends_on per ticket filename. Idempotent: existing Master_Plan.md
  with identical content is not rewritten. OSError on write is caught and surfaces
  as a non-zero CLI exit. Helper functions: _read_ticket_title(), _read_ac_criteria(),
  generate_master_plan(). Integration point: run() calls generate_master_plan()
  after epic_folder is created, using the already-computed dep_graph and topo_order.
====================================================================
"""
