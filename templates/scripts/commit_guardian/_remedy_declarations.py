"""
MODULE: _remedy_declarations
GOAL: The ONE shared loader of remedy declarations: the per-hook ``rules[]``
    entries of the precommit-autofix routing table that say what happens next
    when a check refuses a commit.
BUSINESS CONTEXT: GE-132a-1 owns this loader so that every reader of the
    declarations (check-hook-parity's registration rule, GE-132a-2's validator,
    check-complexity's refusal text, the BO-3800 run) reads the same merged
    view and keeps no second parser or hard-coded path. Existing installs never
    receive new routing-table fields (build_config_scaffolds writes the scaffold
    only when absent), so a local rule without a disposition falls back to the
    package seed.
ARCHITECTURE: Pure read-only module; project root is the process cwd. Tables are
    read in precedence order: the local table (skills_config
    ``precommit_autofix_config_path``, default ``.claude/precommit-autofix.json``)
    first, then the package seed (``templates/scripts/precommit-autofix.json``,
    else ``scripts/precommit-autofix.json``). A rule counts as a declaration only
    when it carries a ``disposition``. ``load(hook_id)`` returns the first
    declaration found plus the file that supplied it, or None (missing). A
    table that exists but cannot be read or parsed raises
    ``RemedyInputError`` -- unreadable input is never reported as "missing".
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LOCAL_REL = ".claude/precommit-autofix.json"
SKILLS_CONFIG_REL = ".claude/skills_config.json"
SEED_RELS: tuple[str, ...] = (
    "templates/scripts/precommit-autofix.json",
    "scripts/precommit-autofix.json",
)


class RemedyInputError(Exception):
    """A declaration source exists but cannot be read, parsed or understood."""


def _read_json(path: Path) -> object:
    """Read and parse one JSON file, converting every failure to RemedyInputError.

    Args:
        path: File to read.

    Returns:
        The parsed JSON value.

    Raises:
        RemedyInputError: The file cannot be read or is not valid JSON.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"cannot read or parse {path}: {exc}"
        raise RemedyInputError(msg) from exc


def local_table_path(root: Path) -> Path:
    """Return the local routing table path, honouring skills_config.

    Args:
        root: Project root.

    Returns:
        ``precommit_autofix_config_path`` from skills_config when configured,
        otherwise the default ``.claude/precommit-autofix.json``. A missing
        skills_config or a missing key means the default.

    Raises:
        RemedyInputError: skills_config exists but cannot be read or parsed, or is
            not a JSON object (fail closed: never judged against the wrong table).
    """
    config_path = root / SKILLS_CONFIG_REL
    rel = DEFAULT_LOCAL_REL
    if config_path.is_file():
        config = _read_json(config_path)
        if not isinstance(config, dict):
            msg = f"{config_path} is not a JSON object"
            raise RemedyInputError(msg)
        configured = config.get("precommit_autofix_config_path")
        if isinstance(configured, str) and configured:
            rel = configured
    return root / rel


def seed_table_path(root: Path) -> Path | None:
    """Return the first existing package seed path, or None when there is none.

    Args:
        root: Project root.

    Returns:
        The seed file path, or None when no candidate exists.
    """
    for rel in SEED_RELS:
        if (root / rel).is_file():
            return root / rel
    return None


def _rules_of(path: Path) -> list[dict]:
    """Return the rules[] list of one table, validated.

    Args:
        path: Routing table file.

    Returns:
        The rule dicts (an absent ``rules`` key yields an empty list).

    Raises:
        RemedyInputError: Unreadable file, or ``rules`` is not a list of objects.
    """
    table = _read_json(path)
    rules = table.get("rules", []) if isinstance(table, dict) else None
    if not isinstance(rules, list) or not all(isinstance(r, dict) and isinstance(r.get("hook_id"), str) for r in rules):
        msg = f"{path} has no valid rules[] list"
        raise RemedyInputError(msg)
    return rules


def load_tables(root: Path | None = None) -> list[tuple[Path, list[dict]]]:
    """Return every existing declaration table as (path, rules), local first.

    Args:
        root: Project root; defaults to the process cwd.

    Returns:
        ``[(local_path, rules), (seed_path, rules)]`` limited to those that exist.

    Raises:
        RemedyInputError: A table exists but is unreadable or malformed.
    """
    base = root if root is not None else Path.cwd()
    paths = [local_table_path(base), seed_table_path(base)]
    tables: list[tuple[Path, list[dict]]] = []
    for path in paths:
        if path is not None and path.is_file() and path not in [p for p, _ in tables]:
            tables.append((path, _rules_of(path)))
    return tables


def declared_view(tables: list[tuple[Path, list[dict]]]) -> dict[str, dict]:
    """Merge tables into {hook_id: declaration}, earlier tables winning.

    Args:
        tables: Output of ``load_tables``.

    Returns:
        One declaration dict per declared hook, each carrying ``source``.
    """
    view: dict[str, dict] = {}
    for path, rules in tables:
        for rule in rules:
            hook_id = rule["hook_id"]
            if rule.get("disposition") and hook_id not in view:
                skills = rule.get("skills")
                view[hook_id] = {
                    "hook_id": hook_id,
                    "disposition": rule["disposition"],
                    "instruction": rule.get("instruction", ""),
                    "agent": rule.get("agent"),
                    "skills": list(skills) if isinstance(skills, list) else [],
                    "source": str(path),
                }
    return view


def gating_hook_ids(root: Path | None = None) -> list[str] | None:
    """Return the ``blocking_hook_ids`` list: the sole authority on which hooks gate a commit.

    Tables are consulted in precedence order (local, then package seed); the first
    one carrying a ``blocking_hook_ids`` list supplies it, so an install whose local
    table predates the field still resolves against the seed.

    Args:
        root: Project root; defaults to the process cwd.

    Returns:
        The hook ids that gate a commit, or None when no table carries the list.

    Raises:
        RemedyInputError: A table exists but is unreadable, or the list is malformed.
    """
    base = root if root is not None else Path.cwd()
    for path in (local_table_path(base), seed_table_path(base)):
        if path is None or not path.is_file():
            continue
        table = _read_json(path)
        listed = table.get("blocking_hook_ids") if isinstance(table, dict) else None
        if listed is None:
            continue
        if not isinstance(listed, list) or not all(isinstance(h, str) for h in listed):
            msg = f"{path} has a blocking_hook_ids that is not a list of hook ids"
            raise RemedyInputError(msg)
        return listed
    return None


def load(hook_id: str, root: Path | None = None) -> dict | None:
    """Return the remedy declaration for one hook, or None when missing.

    Args:
        hook_id: Registered hook id, e.g. ``check-complexity``.
        root: Project root; defaults to the process cwd.

    Returns:
        ``{hook_id, disposition, instruction, agent, skills, source}`` where
        ``source`` is the path of the file that supplied the declaration, or
        None when neither the local table nor the seed declares the hook.

    Raises:
        RemedyInputError: A declaration table exists but is unreadable.
    """
    return declared_view(load_tables(root)).get(hook_id)
