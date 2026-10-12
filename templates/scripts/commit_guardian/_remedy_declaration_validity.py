"""
MODULE: _remedy_declaration_validity
GOAL: The GE-132a-2 rule hosted by check-hook-parity: a remedy declaration must
    carry one valid disposition, tell the author something, and name only agents
    and skills that exist.
BUSINESS CONTEXT: A declaration that points at a specialist or skill that cannot
    be engaged does damage at the worst moment, when a run tries to bring that
    party in. Catching it in the commit that wrote the declaration is the cheap
    moment. The disposition is the only signal a reader uses to choose the route,
    so it is validated here and never inferred from the agent's name.
ARCHITECTURE: Pure judgment over the merged declaration view of the shared loader
    (``_remedy_declarations``). "The agent exists" means its id is in
    ``agent_registry.json`` agents[] with a ``template_path`` that resolves, or it
    is a member of the closed platform list ``hook_parity.platform_agents`` in the
    canonical manifest (data, never code). "The skill exists" means its id is in
    ``skill_registry.json`` skills[] with a resolving ``template_path``. The
    registries are read from ``config/`` under the project root, else from
    ``.leafcutter/config/``; when neither location holds one the existence arms are
    not applicable (stderr note). A registry that exists but cannot be read raises
    ``RemedyInputError`` (could-not-check, never a pass and never "does not exist").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _remedy_declarations import RemedyInputError

DISPOSITIONS = ("author-clears", "mechanical-autofix", "engage-specialist")
REGISTRY_DIRS = ("config", ".leafcutter/config")
_SKILL_PREFIX = "leafcutter/"


def _registry_path(root: Path, name: str) -> Path | None:
    """Return the first existing registry file, or None when there is none.

    Args:
        root: Project root.
        name: Registry file name, e.g. ``agent_registry.json``.

    Returns:
        The registry path, or None when no candidate location holds it.
    """
    for directory in REGISTRY_DIRS:
        if (root / directory / name).is_file():
            return root / directory / name
    return None


def _load_entries(root: Path, name: str, key: str) -> list[dict] | None:
    """Read one registry strictly and return its entry list.

    Args:
        root: Project root.
        name: Registry file name.
        key: Top-level list key (``agents`` or ``skills``).

    Returns:
        The entry dicts, or None when the registry file does not exist.

    Raises:
        RemedyInputError: The registry exists but cannot be read or parsed, or
            ``key`` is not a list of objects carrying a string ``id``.
    """
    path = _registry_path(root, name)
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"cannot read or parse registry {path}: {exc}"
        raise RemedyInputError(msg) from exc
    entries = data.get(key) if isinstance(data, dict) else None
    if not isinstance(entries, list) or not all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in entries):
        msg = f"registry {path} has no valid {key}[] list"
        raise RemedyInputError(msg)
    return entries


def _resolving_ids(entries: list[dict], root: Path) -> set[str]:
    """Return the ids whose ``template_path`` resolves to something under ``root``.

    Args:
        entries: Registry entries.
        root: Project root.

    Returns:
        Ids with a template that exists (the ``leafcutter/`` prefix some entries
        carry is also tried without it).
    """
    found: set[str] = set()
    for entry in entries:
        path = entry.get("template_path")
        if not isinstance(path, str) or not path:
            continue
        candidates = [path, path.removeprefix(_SKILL_PREFIX)]
        if any((root / candidate).exists() for candidate in candidates):
            found.add(entry["id"])
    return found


def platform_agents(manifest: dict, where: str) -> set[str]:
    """Return the closed list of platform-provided agents declared as data.

    Args:
        manifest: Parsed canonical manifest.
        where: Manifest path (for messages).

    Returns:
        The platform agent ids (empty when the key is absent).

    Raises:
        RemedyInputError: The key holds something other than a list of strings.
    """
    section = manifest.get("hook_parity")
    raw = section.get("platform_agents") if isinstance(section, dict) else None
    if raw is None:
        return set()
    if not isinstance(raw, list) or not all(isinstance(i, str) for i in raw):
        msg = f"platform_agents in {where} is not a list of agent ids"
        raise RemedyInputError(msg)
    return set(raw)


def _shape_findings(hook_id: str, decl: dict) -> list[str]:
    """Judge disposition, agent, skills and instruction shape of one declaration.

    Args:
        hook_id: The declared check.
        decl: Its declaration (loader view, carrying ``source``).

    Returns:
        Refusal strings naming the hook and the file that supplied it.
    """
    who = f"Check '{hook_id}' (declaration from {decl['source']})"
    disposition, agent, skills = decl["disposition"], decl.get("agent"), decl.get("skills") or []
    findings: list[str] = []
    if disposition not in DISPOSITIONS:
        findings.append(
            f"  {who} has disposition {disposition!r}, which is not one of {', '.join(DISPOSITIONS)}.\n"
            f"  Fix: set the disposition to exactly one of those three values."
        )
    elif disposition == "author-clears" and (agent or skills):
        findings.append(
            f"  {who} is author-clears but names an agent or skills; the author clears it, so it names none.\n"
            f"  Fix: remove the agent and skills, or change the disposition."
        )
    elif disposition != "author-clears" and not agent:
        findings.append(
            f"  {who} is {disposition} but names no agent.\n"
            f"  Fix: name the agent that handles it, or declare author-clears."
        )
    instruction = decl.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        findings.append(
            f"  {who} tells the author nothing: its instruction is absent, empty or only whitespace.\n"
            f"  Fix: give the author an instruction."
        )
    return findings


def _existence_findings(
    hook_id: str, decl: dict, agents: set[str], skills: set[str]
) -> list[str]:
    """Judge that the agent and skills one declaration names exist.

    Args:
        hook_id: The declared check.
        decl: Its declaration (loader view, carrying ``source``).
        agents: Ids of agents that exist (registry plus platform list).
        skills: Ids of skills that exist.

    Returns:
        Refusal strings naming the hook, the unresolved name, agent or skill,
        and the file that supplied the declaration.
    """
    who = f"Check '{hook_id}' (declaration from {decl['source']})"
    findings: list[str] = []
    agent = decl.get("agent")
    if agent and decl["disposition"] in DISPOSITIONS and agent not in agents:
        findings.append(
            f"  {who} names the agent '{agent}', which does not exist: it has no entry with a "
            f"template in agent_registry.json and is not a platform-provided agent.\n"
            f"  Fix: name an agent that exists, or register it."
        )
    for skill in decl.get("skills") or []:
        if skill not in skills:
            findings.append(
                f"  {who} names the skill '{skill}', which does not exist: it has no entry with a "
                f"template in skill_registry.json.\n"
                f"  Fix: name a skill that exists, or register it."
            )
    return findings


def validate(declared: dict[str, dict], manifest: dict, manifest_path: Path, root: Path) -> list[str]:
    """Judge every declaration in the merged view.

    Args:
        declared: Loader view ``{hook_id: declaration}``.
        manifest: Parsed canonical manifest (carries the platform agent list).
        manifest_path: Its path (for messages).
        root: Project root.

    Returns:
        Refusal strings; empty when every declaration is valid.

    Raises:
        RemedyInputError: A registry or the platform list is unreadable.
    """
    agent_entries = _load_entries(root, "agent_registry.json", "agents")
    skill_entries = _load_entries(root, "skill_registry.json", "skills")
    platform = platform_agents(manifest, str(manifest_path))
    agents = None if agent_entries is None else _resolving_ids(agent_entries, root) | platform
    skills = None if skill_entries is None else _resolving_ids(skill_entries, root)
    if agents is None or skills is None:
        print(
            "check-hook-parity: agent or skill registry not found under config/; "
            "agent and skill existence not checked.",
            file=sys.stderr,
        )
    findings: list[str] = []
    for hook_id in sorted(declared):
        decl = declared[hook_id]
        findings.extend(_shape_findings(hook_id, decl))
        if agents is not None and skills is not None:
            findings.extend(_existence_findings(hook_id, decl, agents, skills))
    return findings
