"""
MODULE: generate_agent_cards
GOAL: Generate .card.md documentation files for agent templates from structured
    metadata sources (template frontmatter, agent registry entries).
BUSINESS CONTEXT: Part of the leafcutter build system (INF-600b). Agent cards
    are a build artifact — never hand-written. Each `python build.py` run
    regenerates the cards so that documentation stays in sync with
    the agent definition. The golden output is
    `docs/agents/cards/python-coder.card.md`.
ARCHITECTURE: Single public entry point `generate_card()` returns a complete
    card markdown string for one agent. Section-rendering helpers (one per
    card section) encapsulate the rendering logic for each block. A top-level
    `build_agent_cards()` function drives the full-tree pass for `build.py`.
    YAML frontmatter is parsed with `yaml.safe_load()`. All file I/O is
    wrapped in `try/except OSError`. Hyperlink helpers convert doc_links and
    knowledge_channel sources that resolve to real files into relative Markdown
    links from the card output path. doc_links entries that reference files not
    present on disk are rendered as plain text with a ``(missing)`` marker and
    a WARNING is emitted — card generation continues without error.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _PACKAGE_ROOT / "templates"
_REGISTRY_PATH = _PACKAGE_ROOT / "config" / "agent_registry.json"

# File extensions and path patterns considered "file-like" sources in
# knowledge_channels.  A source string matching any of these is a candidate
# for hyperlink conversion when the file exists on disk.
_FILE_EXTENSIONS = frozenset(
    {".md", ".py", ".yaml", ".yml", ".json", ".sh", ".toml", ".txt"}
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_registry(registry_path: Path) -> list[dict[str, Any]]:
    """Load and return the agent registry as a list of entry dicts.

    Args:
        registry_path: Absolute path to agent_registry.json.

    Returns:
        List of agent registry entry dicts. Empty list on error.
    """
    try:
        with registry_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        _log.warning("Cannot read agent registry at %s: %s", registry_path, exc)
        return []
    if isinstance(data, list):
        return data
    return data.get("agents", [])


def _parse_frontmatter(template_text: str) -> dict[str, Any]:
    """Extract and parse YAML frontmatter between the first two '---' delimiters.

    Args:
        template_text: Full text of an agent template markdown file.

    Returns:
        Parsed frontmatter dict, or empty dict if no frontmatter found.
    """
    lines = template_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}
    fm_text = "\n".join(lines[1:end_idx])
    try:
        parsed = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        _log.warning("YAML parse error in frontmatter: %s", exc)
        return {}
    return parsed or {}


def _read_existing_provenance(card_path: Path | None) -> dict[str, Any]:
    """Read the existing card's frontmatter so provenance can be carried through.

    Used to recover the ``created`` / ``last_updated`` fields a previously
    generated card already carries, so a fresh render does not invent a new
    ``created`` date or drop the ``last_updated`` date the
    transform-doc-frontmatter commit hook maintains (BP-018).

    Args:
        card_path: Absolute path of the card file that would be written, or
            ``None`` when link/provenance generation is disabled.

    Returns:
        Parsed frontmatter dict from the existing card, or an empty dict when
        *card_path* is ``None``, the file does not exist, or it cannot be
        read/parsed. A malformed or unreadable existing card degrades to "no
        provenance" rather than raising.
    """
    if card_path is None or not card_path.exists():
        return {}
    try:
        existing_text = card_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning(
            "Cannot read existing card %s for provenance: %s", card_path, exc
        )
        return {}
    return _parse_frontmatter(existing_text)


def _valid_provenance_value(value: Any) -> Any | None:
    """Return *value* unchanged if it is a usable provenance date, else None.

    Deliberately preserves the *original type* rather than normalizing to a
    string. YAML parses an unquoted ``2026-08-13`` scalar into a
    ``datetime.date`` object but a quoted ``'2026-08-13'`` into a plain
    ``str`` — that is exactly how the transform-doc-frontmatter commit hook
    leaves ``created`` unquoted (round-tripped as a ``date``) and
    ``last_updated`` quoted (inserted as a ``str``) on disk (see
    ``templates/scripts/commit_guardian/transform_doc_frontmatter.py``).
    Feeding the value straight back into ``yaml.dump()`` with its original
    type reproduces that exact quoting style, which is what lets the
    generator's byte-for-byte compare-before-write guard match what the hook
    writes on commit (BP-018).

    Args:
        value: Value read from parsed frontmatter, or ``None``.

    Returns:
        *value* unchanged when it is a non-empty ``datetime.date`` or
        ``str``; ``None`` when *value* carries no usable date (absent,
        empty, or an unexpected type).
    """
    # NOTE: isinstance() below deliberately uses `datetime.date` (the module
    # import) rather than the bare `date` symbol imported at module level.
    # Tests patch `generate_agent_cards.date` wholesale with a MagicMock to
    # control `date.today()`, which would make `isinstance(value, date)`
    # raise TypeError once patched.
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and value:
        return value
    return None


def make_relative_link(
    from_path: Path,
    to_path: Path,
    label: str,
) -> str:
    """Return a Markdown hyperlink from *from_path* to *to_path* with *label*.

    Computes a POSIX-style relative path from the directory containing
    *from_path* to *to_path*.  Both paths should be absolute.

    Args:
        from_path: Absolute path of the card file that will contain the link.
        to_path: Absolute path of the target document.
        label: Human-readable link label.

    Returns:
        Markdown link string ``[label](relative_path)``.
    """
    rel = os.path.relpath(to_path, from_path.parent)
    # Normalise path separators to POSIX forward-slashes for Markdown.
    rel_posix = Path(rel).as_posix()
    return f"[{label}]({rel_posix})"


def _resolve_source_to_path(
    source: str,
    package_root: Path,
) -> Path | None:
    """Attempt to resolve a knowledge-channel source string to a real file.

    Tries the following strategies in order and returns the first match:

    1. Treat *source* as a path relative to *package_root*.
    2. When the source token has a directory-hinting prefix word (e.g.
       ``"signoff SKILL.md"``), look for a file at
       ``<any-dir-containing-prefix-word>/<filename>`` within the package tree.
    3. Walk the package tree looking for any file whose name matches the
       filename component of *source* (shallow search — only 4 levels deep).

    Args:
        source: Raw source string from a knowledge_channels entry, e.g.
            ``"Root CLAUDE.md"`` or ``"signoff SKILL.md"``.
        package_root: Absolute path to the package root (repo root).

    Returns:
        Resolved :class:`~pathlib.Path` if found on disk, else ``None``.
    """
    # Strategy 1: direct relative path.
    candidate = package_root / source
    if candidate.exists():
        return candidate

    # Extract filename token (last word that carries a known extension).
    tokens = source.split()
    filename: str | None = None
    filename_idx: int = -1
    for i, token in reversed(list(enumerate(tokens))):
        if Path(token).suffix in _FILE_EXTENSIONS:
            filename = token
            filename_idx = i
            break

    if filename is None:
        return None

    # Strategy 2: directory-hint match.  When there is a word before the
    # filename token, treat that word as a hint for the parent directory name.
    if filename_idx > 0:
        hint = tokens[filename_idx - 1].lower()
        for root_dir, _dirs, files in os.walk(package_root):
            root_path = Path(root_dir)
            try:
                rel_depth = len(root_path.relative_to(package_root).parts)
            except ValueError:
                continue
            if rel_depth > 5:
                _dirs.clear()
                continue
            # Parent directory name must contain the hint word.
            if hint in root_path.name.lower() and filename in files:
                return root_path / filename

    # Strategy 3: filename-only match (up to 4 levels deep).
    # Collect ALL matches; resolve only when exactly one unique path is found.
    # An ambiguous match (multiple locations share the same basename) returns None
    # so that the caller's missing-doc / plain-text fallback applies rather than
    # producing a non-deterministic hyperlink.
    matches: list[Path] = []
    for root_dir, _dirs, files in os.walk(package_root):
        root_path = Path(root_dir)
        try:
            rel_depth = len(root_path.relative_to(package_root).parts)
        except ValueError:
            continue
        if rel_depth > 4:
            _dirs.clear()  # prune deeper subtrees
            continue
        if filename in files:
            matches.append(root_path / filename)

    unique_matches = sorted(set(matches))
    if len(unique_matches) == 1:
        return unique_matches[0]
    return None


# ---------------------------------------------------------------------------
# Section-rendering helpers
# ---------------------------------------------------------------------------

def render_when_to_use(registry_entry: dict[str, Any]) -> str:
    """Render the '## When to Use' card section.

    Derives auto-dispatch conditions from the registry ``auto_dispatch``
    list, ``spawned_by``, and optional negative-use notes.

    Args:
        registry_entry: Registry entry dict for the agent.

    Returns:
        Markdown string for the When to Use section.
    """
    lines: list[str] = ["## When to Use", ""]
    auto_dispatch = registry_entry.get("auto_dispatch", [])
    if auto_dispatch:
        lines += ["### Auto-Dispatch Conditions", ""]
        lines += ["| Type | Expression |", "|------|-----------|"]
        for cond in auto_dispatch:
            ctype = cond.get("type", "")
            expr = cond.get("expression", "")
            lines.append(f"| {ctype} | {expr} |")
        lines.append("")
    spawned_by = registry_entry.get("spawned_by", [])
    if spawned_by:
        lines += ["### Spawned By", ""]
        for parent in spawned_by:
            lines.append(f"- `{parent}`")
        lines.append("")
    return "\n".join(lines)


def render_knowledge_flow(
    registry_entry: dict[str, Any],
    card_path: Path | None = None,
    package_root: Path | None = None,
) -> str:
    """Render the '## Knowledge Flow' card section.

    Builds a table from the ``knowledge_channels`` array in the registry entry.
    When *card_path* and *package_root* are supplied, source strings that
    resolve to concrete file paths on disk are rendered as relative Markdown
    hyperlinks instead of bare strings.

    A source may name several files separated by ``; `` — each token is
    converted independently and the results are joined with ``; ``.

    Args:
        registry_entry: Registry entry dict for the agent.
        card_path: Absolute path of the card file being written.  Used to
            compute relative links.  May be ``None`` (disables hyperlinks).
        package_root: Absolute path to the package root.  May be ``None``
            (disables hyperlinks).

    Returns:
        Markdown string for the Knowledge Flow section.
    """
    channels = registry_entry.get("knowledge_channels", [])
    if not channels:
        return "## Knowledge Flow\n\n*No knowledge channels declared.*\n\n"

    hyperlinks_enabled = card_path is not None and package_root is not None

    lines: list[str] = [
        "## Knowledge Flow",
        "",
        "| Channel | Source | Injection Mode | Description |",
        "|---------|--------|----------------|-------------|",
    ]
    for ch in channels:
        num = ch.get("channel", "—")
        raw_source = ch.get("source", "—")
        mode = ch.get("injection_mode", "—")
        desc = ch.get("description", "—")

        if hyperlinks_enabled and raw_source != "—":
            source = _linkify_source(raw_source, card_path, package_root)
        else:
            source = raw_source

        lines.append(f"| {num} | {source} | {mode} | {desc} |")
    lines.append("")
    return "\n".join(lines)


def _linkify_source(
    raw_source: str,
    card_path: Path,
    package_root: Path,
) -> str:
    """Convert file-path tokens within *raw_source* to Markdown hyperlinks.

    Splits *raw_source* on ``; `` to handle multi-file source strings.  For
    each token, attempts to resolve it to a real file on disk; if successful,
    wraps it as ``[token](relative_path)``.  Tokens that do not resolve are
    left as-is.

    Args:
        raw_source: Source string from a knowledge_channels entry.
        card_path: Absolute path of the card file (link origin).
        package_root: Absolute path to the package root (search base).

    Returns:
        Source string with file-path tokens replaced by Markdown links.
    """
    parts = [t.strip() for t in raw_source.split(";")]
    result_parts: list[str] = []
    for part in parts:
        resolved = _resolve_source_to_path(part, package_root)
        if resolved is not None:
            label = part
            result_parts.append(make_relative_link(card_path, resolved, label))
        else:
            result_parts.append(part)
    return "; ".join(result_parts)


def render_spawn_diagram(registry_entry: dict[str, Any]) -> str:
    """Render the '## Spawn and Dependency' section with a Mermaid flowchart.

    Reads ``spawned_by`` and ``spawn_allowlist`` from the registry entry and
    derives a ``flowchart TD`` diagram using string substitution.

    Args:
        registry_entry: Registry entry dict for the agent.

    Returns:
        Markdown string for the Spawn and Dependency section.
    """
    agent_id = registry_entry.get("id", "unknown")
    spawned_by = registry_entry.get("spawned_by", [])
    spawn_allowlist = registry_entry.get("spawn_allowlist", [])
    tier = registry_entry.get("tier", "phase")
    priority = registry_entry.get("priority", "?")

    lines: list[str] = ["## Spawn and Dependency", ""]
    lines += ["```mermaid", "flowchart TD"]
    lines += [
        "    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px",
        "    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px",
        "    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px",
        "    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px",
        "",
    ]

    # Parent nodes
    parent_ids: list[str] = []
    for parent in spawned_by:
        node_id = parent.replace("-", "_")
        parent_tier = "supervisor" if "supervisor" in parent else "phase"
        lines.append(
            f'    {node_id}["{parent}\\n({parent_tier} tier)"]:::{parent_tier}'
        )
        parent_ids.append(node_id)

    # The agent itself
    self_id = agent_id.replace("-", "_")
    lines.append(
        f'    {self_id}["{agent_id}\\n({tier} tier, priority {priority})"]:::target'
    )

    # Child nodes
    child_ids: list[str] = []
    for child in spawn_allowlist:
        cid = child.replace("-", "_")
        child_tier = "utility" if "research" in child else "phase"
        lines.append(
            f'    {cid}["{child}\\n({child_tier} tier)"]:::{child_tier}'
        )
        child_ids.append(cid)

    lines.append("")
    # Spawn relationships
    for pid in parent_ids:
        lines.append(f"    {pid} -->|dispatches| {self_id}")
    for cid in child_ids:
        lines.append(f"    {self_id} -->|spawns| {cid}")

    lines += ["```", ""]
    return "\n".join(lines)


def render_io_contract(template_frontmatter: dict[str, Any]) -> str:
    """Render the '## Input / Output Contract' card section.

    Builds tables from ``inputs``, ``outputs``, and ``mutates`` arrays in the
    template frontmatter.

    Args:
        template_frontmatter: Parsed frontmatter dict from the agent template.

    Returns:
        Markdown string for the Input / Output Contract section.
    """
    lines: list[str] = ["## Input / Output Contract", ""]
    inputs = template_frontmatter.get("inputs", [])
    outputs = template_frontmatter.get("outputs", [])
    mutates = template_frontmatter.get("mutates", [])

    if inputs:
        lines += ["### Inputs", "", "| Name | Type | Description |", "|------|------|-------------|"]
        for item in inputs:
            name = item.get("name", "—")
            itype = item.get("type", "—")
            desc = item.get("description", "—")
            lines.append(f"| `{name}` | {itype} | {desc} |")
        lines.append("")

    if outputs:
        lines += ["### Outputs", "", "| Name | Type | Description |", "|------|------|-------------|"]
        for item in outputs:
            name = item.get("name", "—")
            itype = item.get("type", "—")
            desc = item.get("description", "—")
            lines.append(f"| `{name}` | {itype} | {desc} |")
        lines.append("")

    if mutates:
        lines += ["### Mutates (Side Effects)", "", "| Name | Type | Description |", "|------|------|-------------|"]
        for item in mutates:
            name = item.get("name", "—")
            itype = item.get("type", "—")
            desc = item.get("description", "—")
            lines.append(f"| `{name}` | {itype} | {desc} |")
        lines.append("")

    if not inputs and not outputs and not mutates:
        lines.append("*No structured I/O contract declared.*\n")

    return "\n".join(lines)


def render_skills(
    template_frontmatter: dict[str, Any],
    registry_entry: dict[str, Any],
) -> str:
    """Render the '## Skills Used' card section.

    Precedence rule: ``skills_invoked`` (structured, from template or registry)
    takes precedence over the legacy ``skills_used`` string list. This prevents
    double-listing when both fields are present.

    Args:
        template_frontmatter: Parsed frontmatter dict from the agent template.
        registry_entry: Registry entry dict for the agent.

    Returns:
        Markdown string for the Skills Used section.
    """
    # Precedence: skills_invoked from template FM, then from registry, then legacy skills_used
    skills_invoked: list[dict] | None = (
        template_frontmatter.get("skills_invoked")
        or registry_entry.get("skills_invoked")
    )

    lines: list[str] = ["## Skills Used", ""]

    if skills_invoked:
        lines += ["| Skill | Mode | Condition |", "|-------|------|-----------|"]
        for item in skills_invoked:
            if isinstance(item, dict):
                skill_id = item.get("skill_id", "—")
                mode = item.get("mode", "—")
                condition = item.get("condition", "—")
            else:
                skill_id = str(item)
                mode = "—"
                condition = "—"
            lines.append(f"| `{skill_id}` | {mode} | {condition} |")
        lines.append("")
        return "\n".join(lines)

    # Fallback: legacy skills_used string list
    skills_used = (
        template_frontmatter.get("skills_used")
        or registry_entry.get("skills_used")
        or []
    )
    if skills_used:
        lines += ["| Skill | Mode | Condition |", "|-------|------|-----------|"]
        for skill in skills_used:
            lines.append(f"| `{skill}` | — | — |")
        lines.append("")
    else:
        lines.append("*No skills declared.*\n")

    return "\n".join(lines)


def render_configuration(template_frontmatter: dict[str, Any]) -> str:
    """Render the '## Configuration' card section.

    Derives configuration entries from the ``config_keys`` frontmatter block.

    Args:
        template_frontmatter: Parsed frontmatter dict from the agent template.

    Returns:
        Markdown string for the Configuration section.
    """
    config_keys = template_frontmatter.get("config_keys", {})
    lines: list[str] = ["## Configuration", ""]

    if not config_keys:
        lines.append("*No configuration keys declared.*\n")
        return "\n".join(lines)

    lines += ["| Key | Required | Description |", "|-----|----------|-------------|"]
    for key, meta in config_keys.items():
        if isinstance(meta, dict):
            required = "Yes" if meta.get("required", False) else "No"
            desc = meta.get("description", "—")
        else:
            required = "—"
            desc = str(meta) if meta else "—"
        lines.append(f"| `{key}` | {required} | {desc} |")
    lines.append("")
    return "\n".join(lines)


def render_behavioral_patterns(template_frontmatter: dict[str, Any]) -> str:
    """Render the '## Contributor Notes' card section.

    Renders ``behavioral_patterns`` as a table when the array is non-empty,
    or a fallback message when the array is empty or absent.

    Args:
        template_frontmatter: Parsed frontmatter dict from the agent template.

    Returns:
        Markdown string for the Contributor Notes section.
    """
    patterns = template_frontmatter.get("behavioral_patterns", [])
    lines: list[str] = ["## Contributor Notes", ""]

    if not patterns:
        lines.append(
            "No conditional behaviors — this agent follows a single fixed execution path\n"
        )
        return "\n".join(lines)

    lines += [
        "### Key Behavioral Patterns",
        "",
        "| Pattern | Trigger | Behavior | Related Agent |",
        "|---------|---------|----------|---------------|",
    ]
    for pat in patterns:
        name = pat.get("name", "—")
        trigger = pat.get("trigger", "—")
        behavior = pat.get("behavior", "—")
        related = pat.get("related_agent", "—")
        lines.append(f"| {name} | {trigger} | {behavior} | `{related}` |")
    lines.append("")
    return "\n".join(lines)


def render_ac_assignments(agent_id: str, ac_list: list[dict[str, Any]]) -> str:
    """Render the '## AC Assignments' card section for a specific agent.

    Groups the provided AC dicts (each with at minimum ``id`` and ``title``)
    under a ``### {agent_id}`` heading.  Returns an empty string when
    *ac_list* is empty so callers can omit the section entirely.

    Args:
        agent_id: Canonical agent identifier (e.g. ``"python-coder"``).
        ac_list: List of AC dicts, each containing at minimum ``id`` and
            ``title`` keys.  Only ACs that belong to *agent_id* (i.e. whose
            ``assigned_agent`` field equals *agent_id*) should be supplied by
            the caller — this function does not filter.

    Returns:
        Markdown string for the AC Assignments section, or empty string when
        *ac_list* is empty.
    """
    if not ac_list:
        return ""

    lines: list[str] = ["## AC Assignments", "", f"### {agent_id}", ""]
    for ac in ac_list:
        ac_id = ac.get("id", "—")
        title = ac.get("title", "—")
        lines.append(f"- {ac_id}: {title}")
    lines.append("")
    return "\n".join(lines)


def _scan_ac_assignments(
    agent_id: str,
    docs_root: Path,
) -> list[dict[str, Any]]:
    """Scan the AC store for YAML files assigned to *agent_id*.

    Walks ``docs_root/docs/acceptance-criteria/`` recursively and loads
    every ``.yaml`` / ``.yml`` file.  Returns dicts with ``id`` and
    ``title`` for files whose ``assigned_agent`` field matches *agent_id*
    and whose ``status`` field is ``"active"``.

    Args:
        agent_id: Canonical agent identifier to match against
            ``assigned_agent`` in each AC YAML file.
        docs_root: Absolute path to the package root (repo root).  The AC
            store is expected at ``docs_root/docs/acceptance-criteria/``.

    Returns:
        List of ``{"id": ..., "title": ..., "assigned_agent": ...}`` dicts
        for each matching active AC, sorted by AC ``id``.  Empty list when
        the AC store directory does not exist or no matching ACs are found.
    """
    ac_dir = docs_root / "docs" / "acceptance-criteria"
    if not ac_dir.exists():
        return []

    results: list[dict[str, Any]] = []
    for dirpath, _dirs, filenames in os.walk(ac_dir):
        for filename in filenames:
            if not (filename.endswith(".yaml") or filename.endswith(".yml")):
                continue
            filepath = Path(dirpath) / filename
            try:
                text = filepath.read_text(encoding="utf-8")
            except OSError as exc:
                _log.warning("Cannot read AC file %s: %s", filepath, exc)
                continue
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                _log.warning("YAML parse error in %s: %s", filepath, exc)
                continue
            if not isinstance(data, dict):
                continue
            if data.get("assigned_agent") != agent_id:
                continue
            if data.get("status") != "active":
                continue
            results.append({
                "id": data.get("id", Path(filename).stem),
                "title": data.get("title", ""),
                "assigned_agent": agent_id,
            })

    results.sort(key=lambda d: d.get("id", ""))
    return results


def _scan_all_ac_assignments(
    docs_root: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Scan the AC store ONCE and group active ACs by ``assigned_agent``.

    Walks ``docs_root/docs/acceptance-criteria/`` a single time, parses each
    ``.yaml`` / ``.yml`` file once, and returns a mapping of ``assigned_agent``
    -> list of ``{"id", "title", "assigned_agent"}`` dicts (each group sorted
    by AC ``id``).  This is the batch equivalent of calling
    :func:`_scan_ac_assignments` for every agent, but it avoids re-walking and
    re-parsing the entire store once per agent — an O(agents × ac_files) cost
    that pegged the CPU for >12 minutes on a large store.

    Args:
        docs_root: Absolute path to the package root (repo root).  The AC
            store is expected at ``docs_root/docs/acceptance-criteria/``.

    Returns:
        Mapping of agent id to its list of matching active AC dicts.  Empty
        mapping when the AC store directory does not exist.
    """
    ac_dir = docs_root / "docs" / "acceptance-criteria"
    grouped: dict[str, list[dict[str, Any]]] = {}
    if not ac_dir.exists():
        return grouped

    for dirpath, _dirs, filenames in os.walk(ac_dir):
        for filename in filenames:
            if not (filename.endswith(".yaml") or filename.endswith(".yml")):
                continue
            filepath = Path(dirpath) / filename
            try:
                text = filepath.read_text(encoding="utf-8")
            except OSError as exc:
                _log.warning("Cannot read AC file %s: %s", filepath, exc)
                continue
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                _log.warning("YAML parse error in %s: %s", filepath, exc)
                continue
            if not isinstance(data, dict):
                continue
            assigned_agent = data.get("assigned_agent")
            if not assigned_agent:
                continue
            if data.get("status") != "active":
                continue
            grouped.setdefault(assigned_agent, []).append({
                "id": data.get("id", Path(filename).stem),
                "title": data.get("title", ""),
                "assigned_agent": assigned_agent,
            })

    for entries in grouped.values():
        entries.sort(key=lambda d: d.get("id", ""))
    return grouped


def render_references(
    registry_entry: dict[str, Any],
    card_path: Path | None = None,
    package_root: Path | None = None,
) -> str:
    """Render the '## References' card section from ``doc_links`` entries.

    Each entry in the ``doc_links`` list becomes a relative Markdown hyperlink
    pointing from the card's location to the referenced document.  If the
    referenced file does not exist on disk, the path is rendered as plain text
    annotated with ``(missing)`` so the card remains valid Markdown even for
    files that have not yet been created.  A WARNING is emitted to the build
    log for every missing file so consumers can detect stale ``doc_links``
    without failing the build.

    Args:
        registry_entry: Registry entry dict for the agent.
        card_path: Absolute path of the card file being written.  Used to
            compute relative links.  May be ``None`` (disables hyperlinks).
        package_root: Absolute path to the package root.  May be ``None``
            (disables hyperlinks).

    Returns:
        Markdown string for the References section, or empty string when
        ``doc_links`` is absent or empty.
    """
    doc_links = registry_entry.get("doc_links", [])
    if not doc_links:
        return ""

    agent_id = registry_entry.get("id", "unknown")
    hyperlinks_enabled = card_path is not None and package_root is not None

    lines: list[str] = ["## References", ""]
    for entry in doc_links:
        if isinstance(entry, dict):
            path_str: str = entry.get("path", "")
            label: str = entry.get("label", path_str)
        else:
            path_str = str(entry)
            label = path_str

        if not path_str:
            continue

        if hyperlinks_enabled:
            target = package_root / path_str
            if target.exists():
                link = make_relative_link(card_path, target, label)
                lines.append(f"- {link}")
                continue
            # File does not exist: emit warning and render as plain text with marker.
            _log.warning(
                "%s: doc_links references %s but the file does not exist on disk",
                agent_id,
                path_str,
            )
            lines.append(f"- `{path_str}` (missing)")
            continue

        # Hyperlinks disabled (card_path or package_root not supplied): render as code span.
        lines.append(f"- `{path_str}`")

    lines.append("")
    return "\n".join(lines)


def render_tools(template_frontmatter: dict[str, Any]) -> str:
    """Render the '## Tools Available' card section.

    Reads the ``tools`` field from template frontmatter.

    Args:
        template_frontmatter: Parsed frontmatter dict from the agent template.

    Returns:
        Markdown string for the Tools Available section.
    """
    tools_raw = template_frontmatter.get("tools", "")
    lines: list[str] = ["## Tools Available", ""]

    if not tools_raw:
        lines.append("*No tools declared.*\n")
        return "\n".join(lines)

    tools = [t.strip() for t in str(tools_raw).split(",") if t.strip()]
    lines += ["| Tool |", "|------|"]
    for tool in tools:
        lines.append(f"| `{tool}` |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_card(
    agent_id: str,
    template_frontmatter: dict[str, Any],
    registry_entry: dict[str, Any],
    card_path: Path | None = None,
    package_root: Path | None = None,
    ac_assignments: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a complete .card.md string for one agent.

    Reads structured metadata from template frontmatter and registry entry,
    then renders each card section in canonical order. Every render function
    handles absent fields gracefully (missing key → omit section or render
    placeholder). No KeyError is raised for pre-Ticket-5 agents.

    When *card_path* and *package_root* are supplied, ``doc_links`` entries are
    rendered as relative Markdown hyperlinks in a "## References" section, and
    knowledge_channel source strings that resolve to real files on disk are
    also rendered as hyperlinks in the Knowledge Flow table.

    When *ac_assignments* is a non-empty list, a "## AC Assignments" section
    is appended after all other sections, grouping the listed ACs under the
    agent's own heading (INF-600b-2).

    Args:
        agent_id: Canonical agent identifier (e.g. ``"python-coder"``).
        template_frontmatter: Parsed frontmatter dict from the agent's
            template markdown file.
        registry_entry: Registry entry dict for the agent (from
            ``config/agent_registry.json``).
        card_path: Absolute path of the card output file.  Used to compute
            relative hyperlinks.  ``None`` disables link generation.
        package_root: Absolute path to the package root (repo root).  Used to
            resolve file paths when generating hyperlinks.  ``None`` disables
            link generation.
        ac_assignments: Optional list of AC dicts (each with at minimum ``id``
            and ``title``) for ACs assigned to this agent in the AC store.
            When non-empty, a "## AC Assignments" section is appended to the
            card.  ``None`` or ``[]`` omits the section.

    Returns:
        Complete card markdown string, starting with YAML frontmatter.
    """
    today = date.today()
    name = template_frontmatter.get("name", agent_id)
    description = template_frontmatter.get("description", "")
    if isinstance(description, str):
        description = description.strip()
    # The frontmatter's `description` scalar must be a single flowing line
    # (matching what yaml.dump()'s own width-wrapping produces for a plain
    # long string — see the real cards). The BODY's bold description line
    # further down intentionally keeps any embedded newlines the source
    # template's description carries (some templates use blank-line-
    # separated YAML folding to force real paragraph breaks there) — do not
    # collapse the shared `description` variable itself, only this
    # frontmatter-only copy.
    description_for_fm = (
        description.replace("\n", " ") if isinstance(description, str) else description
    )

    # Carry provenance through from the existing on-disk card instead of
    # inventing it (BP-018): `created` must survive unchanged, and
    # `last_updated` (maintained by the transform-doc-frontmatter commit
    # hook, not by this generator) must not be dropped on rewrite. Falling
    # back to `today` only applies when there is no existing card to read.
    existing_provenance = _read_existing_provenance(card_path)
    created = _valid_provenance_value(existing_provenance.get("created")) or today
    last_updated = _valid_provenance_value(existing_provenance.get("last_updated"))

    # Build YAML frontmatter with the SAME yaml.dump() call
    # transform_doc_frontmatter.py's _rebuild_content() uses to reserialize
    # the whole frontmatter block whenever it fills a missing field (see
    # `_rebuild_content()` in
    # templates/scripts/commit_guardian/transform_doc_frontmatter.py).
    # Hand-building the header text field-by-field (as this function used
    # to) can never byte-match what that hook writes back on the very next
    # commit — quoting style, line width, and folding are all yaml.dump()
    # decisions — which silently defeats the compare-before-write guard in
    # build_agent_cards() forever after the first commit touches a card
    # (BP-018, discovered via a real-artifact spot-check against
    # docs/agents/cards/ after the provenance-only fix still left every
    # card churning). Key order matches the hook and existing cards exactly
    # (`sort_keys=False` preserves insertion order); quoting for `created`
    # vs `last_updated` falls out naturally from whether the value is a
    # `datetime.date` object or a `str` — see _valid_provenance_value().
    fm_dict: dict[str, Any] = {
        "agent_id": agent_id,
        "title": f"Agent Card: {agent_id}",
        "description": description_for_fm,
        "type": "card",
        "status": "active",
        "created": created,
        "card_version": "generated",
    }
    if last_updated is not None:
        fm_dict["last_updated"] = last_updated

    fm_yaml = yaml.dump(
        fm_dict, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    fm_yaml = fm_yaml.rstrip("\n")
    card_fm = f"---\n{fm_yaml}\n---\n"

    # Title block
    title_block = f"# {name}\n\n"
    if description:
        title_block += f"**{description}**\n\n"

    # Summary table
    model = template_frontmatter.get("model", "—")
    portable = "Yes" if template_frontmatter.get("portable", False) else "No"
    tier = registry_entry.get("tier", "—")
    priority = registry_entry.get("priority", "—")
    signoff = "Yes" if template_frontmatter.get("signoff", False) else "No"

    summary_table = (
        "| Field | Value |\n"
        "|-------|-------|\n"
        f"| Model | {model} |\n"
        f"| Tier | {tier} |\n"
        f"| Priority | {priority} |\n"
        f"| Portable | {portable} |\n"
        f"| Sign-off capable | {signoff} |\n"
        "\n---\n\n"
    )

    # Render optional References section (non-empty only).
    references_section = render_references(registry_entry, card_path, package_root)

    # Render all sections
    sections: list[str] = [
        render_when_to_use(registry_entry),
        "---\n\n",
        render_knowledge_flow(registry_entry, card_path, package_root),
        "---\n\n",
        render_spawn_diagram(registry_entry),
        "---\n\n",
        render_io_contract(template_frontmatter),
        "---\n\n",
        render_tools(template_frontmatter),
        "---\n\n",
        render_skills(template_frontmatter, registry_entry),
        "---\n\n",
        render_configuration(template_frontmatter),
        "---\n\n",
        render_behavioral_patterns(template_frontmatter),
    ]

    if references_section:
        sections += ["---\n\n", references_section]

    # Append the AC Assignments section when assignments are available (INF-600b-2).
    ac_section = render_ac_assignments(agent_id, ac_assignments or [])
    if ac_section:
        sections += ["---\n\n", ac_section]

    return card_fm + title_block + summary_table + "".join(sections)


# ---------------------------------------------------------------------------
# Build-phase entry point (called by build_phases.build_agent_cards)
# ---------------------------------------------------------------------------

def build_agent_cards(
    target_root: Path,
    config: dict[str, Any],  # noqa: ARG001 — accepted for interface parity
    dry_run: bool,
    force: bool,
) -> int:
    """Generate .card.md files for all agent templates.

    Reads all ``.md`` files in ``<target_root>/templates/agents/`` (excluding
    ``_*.md`` helper files), reads YAML frontmatter and the corresponding
    registry entry from ``config/agent_registry.json``, calls
    ``generate_card()``, and writes to
    ``<target_root>/docs/agents/cards/<agent-id>.card.md``.

    Respects ``dry_run`` (no writes) and ``force`` (overwrite existing).
    Returns the count of written (or would-write in dry-run) files.

    Args:
        target_root: Absolute path to the target project root.
        config: Build configuration dict (accepted for interface parity;
            not currently used by this phase).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing card files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    agents_template_dir = target_root / "templates" / "agents"
    if not agents_template_dir.exists():
        _log.warning(
            "generate_agent_cards: templates/agents/ not found at %s", target_root
        )
        return 0

    registry_path = target_root / "config" / "agent_registry.json"
    registry_entries = _load_registry(registry_path)
    registry_map: dict[str, dict[str, Any]] = {
        entry["id"]: entry for entry in registry_entries if "id" in entry
    }

    cards_dir = target_root / "docs" / "agents" / "cards"
    written = 0

    # Scan the AC store ONCE and group by assigned_agent, rather than
    # re-walking + re-parsing every AC YAML file per agent.  A per-agent scan
    # is O(agents × ac_files); on a large store (thousands of AC files ×
    # dozens of agents) that pegged the CPU for >12 minutes.  Skipped entirely
    # in dry-run mode, where card content is never materialised.
    ac_assignments_by_agent = (
        {} if dry_run else _scan_all_ac_assignments(target_root)
    )

    for template_file in sorted(agents_template_dir.glob("*.md")):
        if template_file.name.startswith("_"):
            continue  # Skip helper templates

        try:
            template_text = template_file.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning("Cannot read template %s: %s", template_file, exc)
            continue

        fm = _parse_frontmatter(template_text)
        agent_id = fm.get("name") or template_file.stem

        # Fast-path for dry-run: skip the expensive generate_card() call (which
        # performs multiple os.walk passes over the package tree per agent) and
        # just print the DRY-RUN intent.  Card content is only materialised when
        # a real write will follow.
        if dry_run:
            print(f"  [DRY-RUN] would write docs/agents/cards/{agent_id}.card.md")
            written += 1
            continue

        registry_entry = registry_map.get(agent_id, {"id": agent_id})

        card_path = cards_dir / f"{agent_id}.card.md"

        ac_assignments = ac_assignments_by_agent.get(agent_id, [])

        try:
            card_content = generate_card(
                agent_id,
                fm,
                registry_entry,
                card_path=card_path,
                package_root=target_root,
                ac_assignments=ac_assignments,
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("Card generation failed for %s: %s", agent_id, exc)
            continue

        if not force and card_path.exists():
            # Compare-before-write: skip byte-identical files
            try:
                existing = card_path.read_text(encoding="utf-8")
                if existing == card_content:
                    continue
            except OSError:
                pass

        try:
            cards_dir.mkdir(parents=True, exist_ok=True)
            card_path.write_text(card_content, encoding="utf-8")
            print(f"  docs/agents/cards/{agent_id}.card.md")
            written += 1
        except OSError as exc:
            _log.warning("Cannot write card %s: %s", card_path, exc)

    return written


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-05 10:30 [python-coder/EPIC-SelfDescribingAgents/02]:
#   Initial implementation. skills_invoked takes precedence over
#   skills_used to prevent double-listing. Mermaid diagram generated
#   via string template (no graph library dependency). knowledge_channels
#   array from registry is the sole source for Knowledge Flow table —
#   docs/architecture/agent_knowledge_plane.md is NOT read at build time.
#   build_agent_cards() uses overwrite semantics (respects force param)
#   with compare-before-write guard to skip byte-identical files.
#   Output path: docs/agents/cards/<agent-id>.card.md.
#   (#EPIC-SelfDescribingAgents/02)
#
# - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/08]:
#   Added hyperlink generation (INF-600b-1). Three new helpers:
#   make_relative_link(), _resolve_source_to_path(), _linkify_source().
#   render_knowledge_flow() now accepts card_path + package_root and
#   converts resolvable source strings to relative Markdown links.
#   render_references() renders doc_links as a ## References section.
#   generate_card() and build_agent_cards() updated to pass card_path
#   and package_root through the render pipeline.
#   (#EPIC-SelfDescribingAgentsCorrections/08)
#
# - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/09]:
#   Missing doc_links handling (INF-600b-1-i). render_references() now
#   annotates non-existent doc_links with "(missing)" plain-text marker
#   instead of a code span, and emits a WARNING via the module logger so
#   consumers detect stale references without failing the build.
#   (#EPIC-SelfDescribingAgentsCorrections/09)
#
# - 2026-06-30 [python-coder/EPIC-SelfDescribingAgentsCorrections/10]:
#   Per-agent AC assignment section (INF-600b-2). Added two new helpers:
#   render_ac_assignments() emits a ## AC Assignments / ### {agent_id}
#   grouped Markdown section; _scan_ac_assignments() walks
#   docs/acceptance-criteria/ for YAML files with assigned_agent ==
#   agent_id and status == active. generate_card() gains an optional
#   ac_assignments parameter; when non-empty, the section is appended
#   after ## References. build_agent_cards() calls _scan_ac_assignments()
#   per agent and passes results to generate_card(). Both new functions
#   follow project error-handling rules (OSError + yaml.YAMLError
#   wrapped, never bare except, never silently swallowed).
#   (#EPIC-SelfDescribingAgentsCorrections/10)
#
# - 2026-08-12 [debug]:
#   Perf fix — build_agent_cards() called _scan_ac_assignments() once per
#   agent, and each call re-walked + re-parsed the ENTIRE AC store. With a
#   large store (2714 AC YAML files × 59 agents = ~160k yaml.safe_load calls)
#   this pegged the CPU for ~13 min with no output, hanging build.py's
#   "Agent cards" phase during worktree bootstrap. Added
#   _scan_all_ac_assignments() which walks the store ONCE and groups active
#   ACs by assigned_agent; build_agent_cards() now builds that index once
#   (skipped in dry-run) and looks up per agent — O(agents × ac_files) →
#   O(ac_files). Single walk ~16s vs ~775s. _scan_ac_assignments() is left
#   intact for the direct-call unit tests; per-agent results are byte-identical.
#
# - 2026-08-14 [python-coder/BP-018]:
#   Provenance-preserving frontmatter (BP-018). generate_card() hardcoded
#   `created: {date.today()}` and never emitted `last_updated`, so the
#   generated string differed from disk on any day after the last build and
#   the compare-before-write guard in build_agent_cards() (unchanged by this
#   fix) never matched — every card was rewritten, resetting `created` and
#   dropping the `last_updated` the transform-doc-frontmatter commit hook
#   maintains. Added _read_existing_provenance() (reads the on-disk card's
#   frontmatter via _parse_frontmatter(), degrading to {} on any OSError or
#   YAML error) and _valid_provenance_value() (validates a YAML-parsed
#   `created`/`last_updated` value — a `datetime.date` for an unquoted
#   scalar, or a non-empty `str` for a quoted one — returning it UNCHANGED
#   so its original type survives). generate_card() now carries `created`
#   through from disk (falling back to `date.today()` only when there is no
#   existing card to read) and re-emits `last_updated` unchanged when
#   present on disk.
#
#   CORRECTION (same day, caught by a real-artifact spot-check against the
#   actual 60 files under docs/agents/cards/, not the unit tests): the first
#   pass above still hand-built the frontmatter header as literal text
#   (`f'title: "Agent Card: {agent_id}"'`, etc.), which fixed the
#   `created`/`last_updated` VALUES but not the surrounding format. The
#   transform-doc-frontmatter commit hook's `_rebuild_content()` re-dumps
#   the ENTIRE frontmatter dict via `yaml.dump(fm_dict,
#   default_flow_style=False, allow_unicode=True, sort_keys=False)` whenever
#   it fills any missing field — not just the field it filled — so on the
#   very first commit after a card is created (which always fills the
#   missing `last_updated`), the hook silently reformats `title`,
#   `description`, and `card_version` too (double- to single-quotes,
#   long-line to width-80-folded). generate_card()'s hand-built text could
#   never reproduce that. Fixed by building `fm_dict` — same key order:
#   agent_id, title, description, type, status, created, card_version, then
#   last_updated when present — and serializing it with the IDENTICAL
#   `yaml.dump()` call the hook uses, so the generator's own output is a
#   fixed point of the hook's transform from the start. `created`/
#   `last_updated` are passed through with their original parsed type
#   (`datetime.date` vs `str`) rather than stringified, so quoting falls out
#   of yaml.dump()'s own type-preservation logic instead of being
#   hand-guessed. Removed the now-unused `textwrap` import (frontmatter is
#   no longer built via `textwrap.dedent()` line-joining).
#   unit_tests/test_generate_agent_cards_bp018.py's `_REALISTIC_EXISTING_CARD`
#   fixture was rebuilt the same way (via yaml.dump(), not hand-written
#   text) so it cannot silently drift from the real on-disk format again,
#   and a new fixed-point test
#   (test_generated_frontmatter_survives_hook_transform_unchanged) asserts
#   generate_card()'s output round-trips unchanged through the hook's own
#   transform_content().
# ====================================================================
