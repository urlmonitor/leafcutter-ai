"""
MODULE: agent_signoff_grant_check
GOAL: Refuse a build in which an agent's own template declares ``signoff: false``
    yet its own ``skills:`` declaration grants the ``signoff`` ability.
BUSINESS CONTEXT: AR-400c-5. An agent that says it does not sign off but is handed
    the signoff skill carries an instruction set that contradicts its header (the
    product-owner case, AR-400c-2). Only an explicit ``signoff: false`` counts; an
    absent key is not a declaration. Agents whose authored registry ``tier`` is
    ``supervisor`` load the skill to VALIDATE ticket state and are exempt -- the
    exemption is data (the registry entry), never an agent id.
ARCHITECTURE: ``signoff_grant_errors(agents, package_root)`` reads both sides from
    each agent's OWN template frontmatter (``signoff:`` flag and ``skills:`` parsed by
    ``agent_ability_verdict.normalize_entries``); the derived registry skills lists
    are never consulted. Returns one error string per offender, appended by
    ``registry_validator.validate_agent_registry`` to its returned error list so the
    build aborts and the CLI exits 1. Build-engine module under ``scripts/`` (same
    deploy status as ``agent_declaration_shape``); no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-14 [python-coder/AR-400c-5]: Created. Lives outside registry_validator.py,
  which may not grow. (#AR-400c-5)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_ability_verdict import normalize_entries
from agent_declaration_shape import MalformedDeclarationError

logger = logging.getLogger(__name__)

_ABILITY = "signoff"
_EXEMPT_TIER = "supervisor"


def _grants_signoff(frontmatter: dict[str, Any], name: str) -> bool:
    """Return True when the template's own ``skills:`` declaration grants ``signoff``."""
    try:
        entries = normalize_entries(frontmatter.get("skills"))
    except MalformedDeclarationError as exc:
        # The ability gate refuses malformed declarations by name; do not double-report.
        logger.warning("signoff grant check skipped for %s: %s", name, exc)
        return False
    return any(entry["skill_id"] == _ABILITY for entry in entries)


def _read_frontmatter(path: Path, parse: Callable[[str], tuple[dict[str, Any], str]]) -> dict[str, Any] | None:
    """Return the template's frontmatter, or None when the file cannot be read."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("signoff grant check cannot read %s: %s", path, exc)
        return None
    return parse(text)[0]


def signoff_grant_errors(agents: list[dict[str, Any]], package_root: Path) -> list[str]:
    """Return one error per non-supervisor agent declaring ``signoff: false`` yet granted ``signoff``.

    Args:
        agents: Registry agent records (``id``, ``tier``, ``template_path``).
        package_root: Package root the records' ``template_path`` values resolve against.

    Returns:
        Human-readable error strings; empty when no agent contradicts itself.
    """
    try:
        # Lazy: template_compiler hard-imports yaml, and registry_validator must stay importable without it.
        from template_compiler import parse_frontmatter
    except ModuleNotFoundError as exc:
        return [f"Cannot check `signoff: false` grants: template_compiler failed to import "
                f"(missing module '{exc.name}'); install the missing dependency (see requirements-dev.txt)"]
    errors: list[str] = []
    for record in agents:
        rel = record.get("template_path")
        if not rel or record.get("tier") == _EXEMPT_TIER:
            continue
        frontmatter = _read_frontmatter(package_root / rel, parse_frontmatter)
        if not frontmatter or frontmatter.get("signoff") is not False:
            continue
        name = record.get("id") or frontmatter.get("name")
        if _grants_signoff(frontmatter, str(name)):
            errors.append(
                f"agent '{name}' declares `signoff: false` but its skills declaration grants "
                f"'{_ABILITY}'; remove the '{_ABILITY}' grant or declare `signoff: true`"
            )
    return errors
