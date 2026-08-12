#!/usr/bin/env python3
"""
MODULE: render_effective_prompt
GOAL: Assemble and render the *effective prompt* a phase agent receives at spawn
    time — the union of the reproducible knowledge-injection channels plus the
    AC-graph task context — into one reviewable Markdown document (+ JSON sidecar).
BUSINESS CONTEXT: An agent's real context window is not a single file; it is the
    union of many channels (see docs/architecture/agent_knowledge_plane.md). When
    we move AC content out of ticket bodies and require agents to pull it from the
    AC store, a reviewer must be able to SEE that union to confirm the agent still
    knows what to do and where to find its spec. This tool renders it statically so
    it can be eyeballed — or fed to another agent — before templates are rewritten.
ARCHITECTURE: Read-only CLI in scripts/. Reproduces the deterministic subset of
    the 11 injection channels (CLAUDE.md, auto-memory, glossary, agent template,
    registry skills, ticket, AC graph) and emits explicit [NOT REPRODUCIBLE]
    markers for the channels only a live harness can supply (MCP schemas, cwd
    READMEs, on-demand skills, settings feature flags). AC-graph traversal uses the
    canonical derive_parent_id() from scripts/ac_store/ac_parent_id.py.

Usage:
    python3 scripts/render_effective_prompt.py --agent python-coder --ac ACD-300c-3
    python3 scripts/render_effective_prompt.py --agent test-writer --ticket tickets/TICKET-x.md
    python3 scripts/render_effective_prompt.py --agent python-coder --ac FIN-001 --out-dir /tmp

Options:
    --agent NAME        Agent id (matches templates/agents/<name>.md). Required.
    --ticket PATH       Ticket file; its `source_ac` frontmatter seeds the AC graph.
    --ac AC_ID          AC id to seed the graph (overrides ticket source_ac).
    --repo-root PATH    Repo root (default: auto-detected from this file).
    --out-dir PATH      Output directory (default: /tmp).
    --dep-depth N       Max transitive depth for depends_on traversal (default: 3).
    --doc-excerpt N     Lines of each linked doc to include (default: 40).
    --quiet             Suppress the stdout echo of the Markdown.

Exit codes:
    0  Rendered successfully.
    1  Bad input (agent template not found, AC id not found, I/O error).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import deque
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

#: Prefer the libyaml C loader when available — the AC store can hold thousands of
#: files and pure-Python parsing of the whole store on every run is prohibitively
#: slow (~2500 files → minutes on SafeLoader, ~1s on CSafeLoader).
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

# Make the canonical parent-derivation helper importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from ac_store.ac_parent_id import derive_parent_id
except ImportError as exc:  # pragma: no cover - import-environment guard
    logger.error("Cannot import derive_parent_id from ac_store.ac_parent_id: %s", exc)
    raise

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT = "docs/acceptance-criteria"
_DEFAULT_AGENTS_DEPLOYED = ".claude/agents"
_DEFAULT_AGENTS_TEMPLATES = "templates/agents"
_DEFAULT_SKILLS_TEMPLATES = "templates/skills"
_DEFAULT_MEMORY_DIR = "memory"
_DEFAULT_GLOSSARY = "docs/glossary.md"
_DEFAULT_CLAUDE_MD = "CLAUDE.md"
_DEFAULT_REGISTRY = "config/agent_registry.json"

_MARKER = "> ⚠️ **[NOT REPRODUCIBLE OUTSIDE A LIVE SESSION]**"

#: Channels a static script cannot recreate — surfaced as explicit markers so the
#: review is honest about what the live harness layers on top.
_NON_REPRODUCIBLE_CHANNELS: list[tuple[str, str]] = [
    ("② Per-folder README.md", "Injected by the harness when the agent's cwd overlaps a folder."),
    ("⑤ On-demand skills (Skill tool)", "Loaded only when the agent calls the Skill tool at runtime."),
    ("⑦ settings.json feature flags", "Harness-level flags translated into injection decisions at startup."),
    ("⑩ MCP server prompts + tool schemas", "Contributed by registered MCP servers at harness startup."),
]

#: Primary-AC fields an *implementer* needs. Pipeline/authoring-management fields
#: (readiness, work_status, req_status, status, origin_agent, created, amended_by,
#: superseded_by, priority) are "meant for" the authoring pipeline — not the coder —
#: so they are dropped from the implementer-facing render.
_IMPLEMENTER_AC_FIELDS: tuple[str, ...] = (
    "id", "title", "component", "components", "level",
    "assigned_agent", "estimated_complexity", "complexity",
    "change_target", "risk_surface", "depends_on", "doc_links",
    "covered_by", "implemented_by",
)

#: Implementation-contract fields surfaced as their own labelled block (with an
#: explicit ABSENT flag when missing) rather than buried in the field dump — these
#: are what actually tell a coder WHAT to touch and HOW it is tested.
_IMPL_INPUT_FIELDS: tuple[str, ...] = (
    "it_requirements", "test_spec", "test_required", "delivers_to", "expects_from",
)

AcRecord = dict[str, Any]
AcIndex = dict[str, tuple[Path, AcRecord]]


# ---------------------------------------------------------------------------
# Repo root + file helpers
# ---------------------------------------------------------------------------


def _find_repo_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git marker is found.

    Args:
        start: Starting path for the upward search.

    Returns:
        The repo root path, or *start* resolved when no marker is found.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return current


def _read_text(path: Path) -> str | None:
    """Read a UTF-8 text file, returning None (with a WARNING) on failure.

    Args:
        path: File to read.

    Returns:
        File contents, or None when the file is absent or unreadable.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a Markdown file into (frontmatter dict, body).

    Args:
        text: Full file contents.

    Returns:
        A (frontmatter, body) tuple. Frontmatter is {} when absent or invalid.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        logger.warning("Could not parse frontmatter: %s", exc)
        return {}, text
    return (fm if isinstance(fm, dict) else {}), parts[2].lstrip("\n")


# ---------------------------------------------------------------------------
# AC store index + traversal
# ---------------------------------------------------------------------------


def _build_ac_index(ac_root: Path) -> AcIndex:
    """Scan *ac_root* recursively and index every AC YAML by its id.

    Args:
        ac_root: Root directory of the AC store.

    Returns:
        Mapping of ac_id -> (path, record). Empty when the root is absent.
    """
    index: AcIndex = {}
    if not ac_root.exists():
        logger.warning("AC store not found at %s", ac_root)
        return index
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.load(fh, Loader=_YAML_LOADER)  # noqa: S506 - trusted repo store, C loader for speed
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Skipping unreadable AC %s: %s", yaml_path, exc)
            continue
        if isinstance(data, dict) and data.get("id"):
            index[str(data["id"])] = (yaml_path, data)
    return index


def _lean(record: AcRecord, *, extra: tuple[str, ...] = ()) -> dict[str, Any]:
    """Project an AC record down to the lean fields used for related-AC context.

    Related ACs (parents, dependencies, dependents, siblings) contribute only
    their id, title, and Gherkin criteria — not their full frontmatter — per the
    reviewer's guidance. *extra* names additional fields to carry (e.g.
    implemented_by for dependencies, where "what already shipped" matters).

    Args:
        record: The full AC record.
        extra: Additional top-level field names to include when present.

    Returns:
        A lean dict with id / title / criteria (+ any requested extras).
    """
    lean: dict[str, Any] = {
        "id": record.get("id"),
        "title": record.get("title"),
        "criteria": record.get("criteria"),
        "assigned_agent": record.get("assigned_agent"),
    }
    for key in extra:
        if record.get(key):
            lean[key] = record[key]
    return lean


def _parent_chain(ac_id: str, index: AcIndex) -> list[dict[str, Any]]:
    """Walk the parent chain from *ac_id* up to the L0 root (nearest first).

    Args:
        ac_id: The AC id to start from.
        index: The AC store index.

    Returns:
        Lean records for each ancestor found in the store, nearest parent first.
    """
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = derive_parent_id(ac_id)
    while current and current not in seen:
        seen.add(current)
        entry = index.get(current)
        if entry:
            chain.append(_lean(entry[1]))
        else:
            chain.append({"id": current, "title": None, "criteria": None,
                          "_note": "referenced ancestor not found in store"})
        current = derive_parent_id(current)
    return chain


def _dependency_closure(ac_id: str, index: AcIndex, max_depth: int) -> list[dict[str, Any]]:
    """BFS the transitive depends_on closure of *ac_id* (deduped, depth-capped).

    Args:
        ac_id: The seed AC id.
        index: The AC store index.
        max_depth: Maximum transitive depth to traverse.

    Returns:
        Lean records (+ implemented_by) for each prerequisite AC, in BFS order.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = {ac_id}
    queue: deque[tuple[str, int]] = deque([(ac_id, 0)])
    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        entry = index.get(node_id)
        if not entry:
            continue
        for dep in entry[1].get("depends_on") or []:
            dep_id = str(dep)
            if dep_id in seen:
                continue
            seen.add(dep_id)
            dep_entry = index.get(dep_id)
            if dep_entry:
                lean = _lean(dep_entry[1], extra=("implemented_by",))
                lean["_depth"] = depth + 1
                out.append(lean)
                queue.append((dep_id, depth + 1))
            else:
                out.append({"id": dep_id, "title": None, "criteria": None,
                            "_depth": depth + 1,
                            "_note": "dependency not found in store"})
    return out


def _dependents(ac_id: str, index: AcIndex) -> list[dict[str, Any]]:
    """Find ACs that declare *ac_id* in their depends_on (reverse edge, "next").

    Args:
        ac_id: The AC id to search for.
        index: The AC store index.

    Returns:
        Lean records (title + criteria) for each direct dependent.
    """
    out: list[dict[str, Any]] = []
    for _id, (_path, record) in index.items():
        deps = [str(d) for d in (record.get("depends_on") or [])]
        if ac_id in deps:
            out.append(_lean(record))
    return out


def _siblings(ac_id: str, index: AcIndex) -> list[dict[str, Any]]:
    """Find sibling ACs (same derived parent) other than *ac_id*.

    Args:
        ac_id: The AC id whose siblings to find.
        index: The AC store index.

    Returns:
        Lean records (title + criteria) for each sibling.
    """
    parent = derive_parent_id(ac_id)
    if not parent:
        return []
    out: list[dict[str, Any]] = []
    for other_id, (_path, record) in index.items():
        if other_id == ac_id:
            continue
        if derive_parent_id(other_id) == parent:
            out.append(_lean(record))
    return out


def _doc_link_paths(record: AcRecord) -> list[str]:
    """Extract local doc paths from an AC's doc_links (dicts or bare strings).

    Args:
        record: The AC record.

    Returns:
        A list of local (non-http) doc path strings.
    """
    paths: list[str] = []
    for link in record.get("doc_links") or []:
        if isinstance(link, dict):
            val = link.get("path", "")
        elif isinstance(link, str):
            val = link
        else:
            val = ""
        if val and not val.startswith("http"):
            paths.append(val)
    return paths


# ---------------------------------------------------------------------------
# Channel resolvers
# ---------------------------------------------------------------------------


def _resolve_agent_template(repo_root: Path, agent: str) -> tuple[str | None, str]:
    """Load the agent's compiled template, preferring the deployed copy.

    Args:
        repo_root: Repo root.
        agent: Agent id.

    Returns:
        A (contents, source_label) tuple. Contents is None when neither the
        deployed nor the template file exists.
    """
    deployed = repo_root / _DEFAULT_AGENTS_DEPLOYED / f"{agent}.md"
    template = repo_root / _DEFAULT_AGENTS_TEMPLATES / f"{agent}.md"
    if deployed.exists():
        return _read_text(deployed), f"deployed: {_DEFAULT_AGENTS_DEPLOYED}/{agent}.md"
    if template.exists():
        return (_read_text(template),
                f"template (uncompiled — placeholders unresolved): "
                f"{_DEFAULT_AGENTS_TEMPLATES}/{agent}.md")
    return None, "NOT FOUND"


def _resolve_agent_skills(repo_root: Path, agent: str) -> list[dict[str, Any]]:
    """Read the agent's skills_invoked from the registry and load each SKILL.md.

    Args:
        repo_root: Repo root.
        agent: Agent id.

    Returns:
        A list of {skill, path, present, body} dicts (empty when unknown).
    """
    registry_path = repo_root / _DEFAULT_REGISTRY
    text = _read_text(registry_path)
    if text is None:
        return []
    try:
        registry = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse agent registry: %s", exc)
        return []
    raw: list[Any] = []
    for entry in registry.get("agents", []):
        if entry.get("id") == agent:
            raw = entry.get("skills_invoked") or []
            break
    out: list[dict[str, Any]] = []
    for item in raw:
        # skills_invoked entries are dicts ({skill_id, mode, descriptive_only})
        # or, defensively, bare strings.
        if isinstance(item, dict):
            skill = item.get("skill_id") or item.get("skill") or item.get("id")
            mode = item.get("mode")
            descriptive_only = bool(item.get("descriptive_only"))
        else:
            skill, mode, descriptive_only = str(item), None, False
        if not skill:
            continue
        skill_md = repo_root / _DEFAULT_SKILLS_TEMPLATES / skill / "SKILL.md"
        out.append({
            "skill": skill,
            "mode": mode,
            "descriptive_only": descriptive_only,
            "path": str(skill_md.relative_to(repo_root)) if skill_md.exists() else None,
            "present": skill_md.exists(),
            "body": _read_text(skill_md) if skill_md.exists() else None,
        })
    return out


def _resolve_memory(repo_root: Path) -> list[dict[str, str]]:
    """Load auto-memory files from the repo-local memory/ directory.

    Args:
        repo_root: Repo root.

    Returns:
        A list of {name, body} dicts (empty when no memory dir).
    """
    mem_dir = repo_root / _DEFAULT_MEMORY_DIR
    if not mem_dir.exists():
        return []
    out: list[dict[str, str]] = []
    for md in sorted(mem_dir.glob("*.md")):
        body = _read_text(md)
        if body is not None:
            out.append({"name": md.name, "body": body})
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def assemble(  # noqa: PLR0913 - explicit resolved-channel inputs, no hidden state
    *,
    agent: str,
    ac_id: str | None,
    ticket_path: str | None,
    repo_root: Path,
    dep_depth: int,
) -> dict[str, Any]:
    """Resolve every reproducible channel + the AC graph into one payload dict.

    Args:
        agent: Agent id.
        ac_id: Seed AC id (may be None if resolvable from the ticket).
        ticket_path: Ticket file path (optional).
        repo_root: Repo root.
        dep_depth: Max transitive depends_on depth.

    Returns:
        The structured payload (also serialised to the JSON sidecar).
    """
    ac_root = repo_root / _DEFAULT_AC_ROOT
    index = _build_ac_index(ac_root)

    # Ticket + source_ac resolution.
    ticket_block: dict[str, Any] | None = None
    if ticket_path:
        tpath = Path(ticket_path)
        if not tpath.is_absolute():
            tpath = repo_root / ticket_path
        raw = _read_text(tpath)
        if raw is not None:
            fm, body = _split_frontmatter(raw)
            ticket_block = {"path": str(tpath), "frontmatter": fm, "body": body}
            if not ac_id:
                ac_id = fm.get("source_ac")

    agent_body, agent_source = _resolve_agent_template(repo_root, agent)

    # AC graph.
    ac_graph: dict[str, Any] = {"seed": ac_id}
    if ac_id and ac_id in index:
        primary = index[ac_id][1]
        ac_graph.update({
            "primary": primary,  # full record — the spec being built
            "parents": _parent_chain(ac_id, index),
            "dependencies": _dependency_closure(ac_id, index, dep_depth),
            "dependents": _dependents(ac_id, index),
            "siblings": _siblings(ac_id, index),
            "doc_links": _doc_link_paths(primary),
        })
    elif ac_id:
        ac_graph["error"] = f"AC id {ac_id!r} not found in store ({ac_root})"

    return {
        "meta": {
            "agent": agent,
            "ac_id": ac_id,
            "ticket": ticket_path,
            "repo_root": str(repo_root),
            "dep_depth": dep_depth,
            "ac_store_size": len(index),
        },
        "harness": {
            "claude_md": _read_text(repo_root / _DEFAULT_CLAUDE_MD),
            "memory": _resolve_memory(repo_root),
            "glossary": _read_text(repo_root / _DEFAULT_GLOSSARY),
        },
        "agent": {
            "source": agent_source,
            "body": agent_body,
            "skills_invoked": _resolve_agent_skills(repo_root, agent),
        },
        "ticket": ticket_block,
        "ac_graph": ac_graph,
        "non_reproducible": _NON_REPRODUCIBLE_CHANNELS,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _fence(text: str | None, lang: str = "") -> str:
    """Wrap *text* in a fenced code block, or emit a MISSING marker when None.

    The fence length is chosen to exceed the longest backtick run inside *text*
    so that embedded documents which themselves contain ``` code blocks (CLAUDE.md,
    memory files, agent templates) do not prematurely close the outer fence.
    """
    if text is None:
        return "_[MISSING]_"
    longest = 0
    run = 0
    for ch in text:
        if ch == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{text.rstrip()}\n{ticks}"


def _skill_status(sk: dict[str, Any]) -> str:
    """Format the status label for one invoked skill (present / descriptive / missing)."""
    mode = f" · {sk['mode']}" if sk.get("mode") else ""
    if sk["present"]:
        return f"{sk['path']}{mode}"
    if sk.get("descriptive_only"):
        return f"descriptive-only, no SKILL.md{mode}"
    return f"**NOT FOUND**{mode}"


def _fmt_implemented_by(value: Any) -> str:
    """Format an implemented_by value as a comma-separated backticked list."""
    if isinstance(value, list):
        return ", ".join(f"`{v}`" for v in value)
    return f"`{value}`"


def _render_related(
    title: str,
    items: list[dict[str, Any]],
    *,
    note: str,
    seen: set[str],
    target_agent: str,
) -> list[str]:
    """Render a related-AC list section (parents / deps / dependents / siblings).

    Two trimming rules keep the render free of content meant for another agent:

    * An AC already rendered in full in an earlier section (tracked via *seen*) is
      shown as a compact back-reference — never repeated.
    * An AC owned by a DIFFERENT agent (``assigned_agent`` != *target_agent*) is
      shown as a compact pointer (title + owner + implemented_by), WITHOUT its full
      Gherkin — the detailed spec of another agent's work item is not this agent's
      to read. Same-agent (or unassigned) items keep their Gherkin.
    """
    lines = [f"### {title} ({len(items)})", "", f"_{note}_", ""]
    if not items:
        lines.append("_(none)_")
        lines.append("")
        return lines
    for item in items:
        aid = str(item.get("id"))
        depth = f" · depth {item['_depth']}" if "_depth" in item else ""
        owner = item.get("assigned_agent")
        impl = ""
        if item.get("implemented_by"):
            impl = f" · implemented by {_fmt_implemented_by(item['implemented_by'])}"
        if aid in seen:
            lines.append(f"- `{aid}` — {item.get('title') or '?'}{depth} — "
                         f"_(shown above)_{impl}")
            lines.append("")
            continue
        seen.add(aid)
        cross_agent = bool(owner) and owner != target_agent
        if cross_agent:
            # Compact pointer only — the Gherkin is owned by another agent.
            lines.append(f"- `{aid}` — {item.get('title') or '?'}{depth} — "
                         f"_owned by `{owner}` (spec elided){impl}_")
            lines.append("")
            continue
        lines.append(f"#### `{aid}` — {item.get('title') or '?'}{depth}")
        if item.get("_note"):
            lines.append(f"> {item['_note']}")
        if item.get("criteria"):
            lines.append(_fence(item["criteria"], "gherkin"))
        if item.get("implemented_by"):
            lines.append(f"**Already implemented by:** {_fmt_implemented_by(item['implemented_by'])}")
        lines.append("")
    return lines


def _first_line(text: str, limit: int = 140) -> str:
    """Return the first non-empty line of *text*, truncated to *limit* chars."""
    for line in text.splitlines():
        if line.strip():
            stripped = line.strip()
            return stripped if len(stripped) <= limit else stripped[:limit] + "…"
    return ""


def render_markdown(
    payload: dict[str, Any], repo_root: Path, doc_excerpt: int, *, brief: bool = False
) -> str:
    """Render the assembled payload into a sectioned Markdown review document.

    Args:
        payload: The dict from assemble().
        repo_root: Repo root (for reading linked docs).
        doc_excerpt: Lines of each linked doc to include.
        brief: When True, collapse Layer 1/2 bulk (memory files and invoked-skill
            bodies) to one-line summaries so the document is scannable while the
            full AC-graph task layer is preserved.

    Returns:
        The Markdown document string.
    """
    meta = payload["meta"]
    lines: list[str] = [
        f"# Effective prompt — `{meta['agent']}`",
        "",
        f"- **AC:** `{meta['ac_id'] or '(none)'}`  ·  **Ticket:** "
        f"`{meta['ticket'] or '(none)'}`",
        f"- **Repo:** `{meta['repo_root']}`  ·  **AC store size:** "
        f"{meta['ac_store_size']}  ·  **dep-depth:** {meta['dep_depth']}",
        "",
        "> This document approximates what the agent sees at spawn time. It "
        "assembles the **reproducible** channels only; the harness layers more on "
        "top at runtime (see the end of this doc).",
        "",
        "---",
        "",
        "## Layer 1 · Harness (always-on, reproducible)",
        "",
        "### ① Root CLAUDE.md",
        "",
        _fence(payload["harness"]["claude_md"], "markdown"),
        "",
        "### ⑨ Auto-memory",
        "",
    ]
    memory = payload["harness"]["memory"]
    if not memory:
        lines.append("_(no repo-local memory/ directory)_")
        lines.append("")
    elif brief:
        for mem in memory:
            lines.append(f"- `memory/{mem['name']}` — {_first_line(mem['body'])}")
        lines.append("")
    else:
        for mem in memory:
            lines.append(f"#### `memory/{mem['name']}`")
            lines.append(_fence(mem["body"], "markdown"))
            lines.append("")

    lines.extend([
        "### ⑪ Glossary (`docs/glossary.md`)",
        "",
        _fence(payload["harness"]["glossary"], "markdown"),
        "",
        "---",
        "",
        "## Layer 2 · Agent (channel ⑥)",
        "",
        f"**Source:** `{payload['agent']['source']}`",
        "",
        _fence(payload["agent"]["body"], "markdown"),
        "",
        "### Skills this agent invokes (registry `skills_invoked`)",
        "",
    ])
    skills = payload["agent"]["skills_invoked"]
    if not skills:
        lines.append("_(none declared / registry unavailable)_")
        lines.append("")
    elif brief:
        for sk in skills:
            summary = ""
            if sk["body"]:
                fm, body = _split_frontmatter(sk["body"])
                desc = fm.get("description") or _first_line(body)
                summary = f" — {_first_line(desc)}" if desc else ""
            lines.append(f"- `{sk['skill']}` ({_skill_status(sk)}){summary}")
        lines.append("")
    else:
        for sk in skills:
            lines.append(f"#### `{sk['skill']}` — {_skill_status(sk)}")
            if sk["body"]:
                lines.append(_fence(sk["body"], "markdown"))
            lines.append("")

    lines.extend(["---", "", "## Layer 3 · Task (ticket + AC graph)", ""])

    ticket = payload["ticket"]
    lines.append("### ⑧ Ticket")
    lines.append("")
    if ticket is None:
        lines.append("_(no ticket supplied)_")
        lines.append("")
    else:
        lines.append(f"**Path:** `{ticket['path']}`")
        lines.append(_fence(yaml.safe_dump(ticket["frontmatter"], sort_keys=False).rstrip(), "yaml"))
        lines.append(_fence(ticket["body"], "markdown"))
        lines.append("")

    graph = payload["ac_graph"]
    if "error" in graph:
        lines.append(f"> ⚠️ {graph['error']}")
        lines.append("")
    elif graph.get("primary"):
        primary = graph["primary"]
        target_agent = meta["agent"]
        lines.append("### PRIMARY AC — the spec this agent must build")
        lines.append("")
        lines.append("**Criteria (the behaviour to build):**")
        lines.append(_fence(primary.get("criteria"), "gherkin"))

        # Implementer-relevant fields only; pipeline/authoring metadata is dropped
        # because it is meant for the authoring pipeline, not the coder.
        impl_fields = {k: primary[k] for k in _IMPLEMENTER_AC_FIELDS if k in primary}
        lines.append("**Fields (implementer-relevant; pipeline/authoring metadata omitted):**")
        lines.append(_fence(yaml.safe_dump(impl_fields, sort_keys=False,
                                           allow_unicode=True).rstrip(), "yaml"))

        # Implementation inputs — surfaced explicitly and flagged when absent, so a
        # reviewer immediately sees whether the AC is actually build-ready.
        lines.append("**Implementation inputs (what to touch + how it is tested):**")
        lines.append("")
        any_input = False
        for field in _IMPL_INPUT_FIELDS:
            val = primary.get(field)
            if val in (None, [], {}, ""):
                continue
            any_input = True
            lines.append(f"- `{field}`:")
            lines.append(_fence(yaml.safe_dump(val, sort_keys=False,
                                               allow_unicode=True).rstrip(), "yaml"))
        if not any_input:
            lines.append("> ⚠️ This AC carries NO it_requirements / test_spec / "
                         "contract fields. A coder has no file targets and no test "
                         "contract from the store — the AC is not implementation-ready "
                         "(IT-PO enrichment incomplete).")
        lines.append("")

        # Track ids already rendered so later sections back-reference rather than
        # repeat (e.g. an AC that is both a parent and a dependency).
        seen: set[str] = {str(primary.get("id"))}
        lines.extend(_render_related(
            "Parent chain (why — up to L0)", graph["parents"],
            note="Nearest parent first; Gherkin shown only for same-agent items.",
            seen=seen, target_agent=target_agent))
        lines.extend(_render_related(
            "Dependencies (already built — prerequisites)", graph["dependencies"],
            note="Transitive depends_on closure; shows what code already shipped.",
            seen=seen, target_agent=target_agent))
        lines.extend(_render_related(
            "Dependents (what this enables — next)", graph["dependents"],
            note="Direct reverse depends_on edges.",
            seen=seen, target_agent=target_agent))
        lines.extend(_render_related(
            "Siblings (related — same parent)", graph["siblings"],
            note="Same derived parent.",
            seen=seen, target_agent=target_agent))

        lines.append("### Linked docs (`doc_links`)")
        lines.append("")
        doc_paths = graph.get("doc_links") or []
        if not doc_paths:
            lines.append("_(none)_")
            lines.append("")
        for dp in doc_paths:
            full = repo_root / dp
            body = _read_text(full)
            lines.append(f"#### `{dp}`")
            if body is None:
                lines.append("_[MISSING]_")
            else:
                excerpt = "\n".join(body.splitlines()[:doc_excerpt])
                lines.append(_fence(excerpt, "markdown"))
                if len(body.splitlines()) > doc_excerpt:
                    lines.append(f"_… truncated to {doc_excerpt} lines_")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## Layer 4 · How to traverse (runtime guidance)",
        "",
        "When you need more than what is inlined above:",
        "",
        "- **AC store:** `docs/acceptance-criteria/{component}/{id}.yaml` is the "
        "source of truth. Derive a parent id by stripping the last id segment "
        "(`ACD-300c-3` → `ACD-300c` → `ACD-300`).",
        "- **Prerequisites:** follow `depends_on`; check each dep's "
        "`implemented_by` to see what already shipped before re-building it.",
        "- **Contracts:** honour `delivers_to` / `expects_from` on the primary AC.",
        "- **Docs:** follow `doc_links`; those docs cross-link ADRs under "
        "`docs/architecture/adrs/`.",
        "",
        "---",
        "",
        "## Channels NOT reproduced here (added live by the harness)",
        "",
        _MARKER,
        "",
    ])
    for name, why in payload["non_reproducible"]:
        lines.append(f"- **{name}** — {why}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Render an agent's effective prompt.")
    parser.add_argument("--agent", required=True, help="Agent id (templates/agents/<name>.md).")
    parser.add_argument("--ticket", help="Ticket file; its source_ac seeds the AC graph.")
    parser.add_argument("--ac", help="AC id to seed the graph (overrides ticket source_ac).")
    parser.add_argument("--repo-root", help="Repo root (default: auto-detected).")
    parser.add_argument("--out-dir", default="/tmp", help="Output directory (default: /tmp).")
    parser.add_argument("--dep-depth", type=int, default=3, help="Max depends_on depth (default: 3).")
    parser.add_argument("--doc-excerpt", type=int, default=40, help="Lines per linked doc (default: 40).")
    parser.add_argument("--brief", action="store_true",
                        help="Collapse memory/skills to one-liners; keep full AC-graph.")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout echo.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector (defaults to sys.argv[1:]).

    Returns:
        Process exit code.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _find_repo_root(Path(__file__))

    if not args.ac and not args.ticket:
        logger.error("Provide --ac or --ticket (to resolve source_ac).")
        return 1

    payload = assemble(
        agent=args.agent,
        ac_id=args.ac,
        ticket_path=args.ticket,
        repo_root=repo_root,
        dep_depth=args.dep_depth,
    )

    if payload["agent"]["body"] is None:
        logger.error("Agent template for %r not found under %s or %s.",
                     args.agent, _DEFAULT_AGENTS_DEPLOYED, _DEFAULT_AGENTS_TEMPLATES)
        return 1

    markdown = render_markdown(payload, repo_root, args.doc_excerpt, brief=args.brief)

    out_dir = Path(args.out_dir)
    stem = f"effective_prompt_{args.agent}"
    if payload["meta"]["ac_id"]:
        stem += f"_{payload['meta']['ac_id']}"
    md_path = out_dir / f"{stem}.md"
    json_path = out_dir / f"{stem}.json"
    try:
        md_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except OSError as exc:
        logger.error("Could not write output: %s", exc)
        return 1

    if not args.quiet:
        print(markdown)
    print(f"\n---\nWrote: {md_path}\nWrote: {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
