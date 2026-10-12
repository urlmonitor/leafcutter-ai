"""
MODULE: agent_inplace_abilities
GOAL: Report, by template name, a SOURCE agent definition that states its own
    grant of abilities in its body, labelling the report ``duplicate`` when the
    in-place list equals the declaration and ``contradiction`` when it differs.
BUSINESS CONTEXT: AR-300a-4-i. Delivery appends the one account of an agent's
    abilities from its frontmatter declaration. A hand-written section in the
    body is a second source of truth: today's python-coder carried one that named
    fewer abilities than its declaration granted. The report keeps a second
    account from entering the tree quietly -- and does NOT fire on the many
    templates that merely discuss skills in prose (a noisy rule gets switched
    off, AR-200b-1), because the positive signal is a structured section naming
    installed skill ids, outside code fences.
ARCHITECTURE: ``classify_inplace`` (pure) compares one body with its declaration;
    ``detect_inplace_abilities`` walks ``templates_dir/*.md`` (underscore partials
    and files without a frontmatter ``name`` are not agents) and states how many
    it examined and how many stated their own grant; ``ok`` is False only for an
    empty population. ``report_inplace_abilities`` is the compile-time hook: it
    logs a WARNING naming the template file, called from
    ``template_compiler.compile_agent_template``. ``report_inplace_accounts``
    is the same hook widened over the account kind (AR-300a-5-i): it also
    reports a hand-written sub-agent table or list (``classify_inplace_spawn``,
    the ``sub-agents`` kind of the one ``find_accounts`` recogniser) against the
    declared ``spawn_allowlist``, macro resolved. Severity disposition: BOTH
    kinds are REPORTED and neither refuses, so a mid-migration tree still builds.
    With no path the package's own ``templates/agents`` is resolved from this
    module's location, never the current directory. This detector reads SOURCE
    templates; the compiled-prompt checks live in ``agent_grant_delivery``.
    Build-engine module under ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300a-4-i]: Created. (#AR-300a-4-i)
- 2026-10-09 [python-coder/AR-300a-5-i]: Generalised over the account kind
  (``report_inplace_accounts``) instead of a parallel spawn detector, so a
  hand-written sub-agent table or list is reported by file name as
  ``duplicate`` / ``contradiction`` exactly like a hand-written abilities
  section. (#AR-300a-5-i)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent_ability_accounts import find_accounts
from agent_ability_verdict import normalize_entries
from agent_spawn_declaration import declared_spawn, resolve_spawn_ids

_log = logging.getLogger(__name__)
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def installed_skill_ids(skills_root: Path | None) -> set[str]:
    """Return the ids of the skills installed under ``skills_root`` (the package's own when None)."""
    root = skills_root if skills_root is not None else _PACKAGE_ROOT / "templates" / "skills"
    return {p.parent.name for p in root.glob("*/SKILL.md")}


def classify_inplace(body: str, fm: dict[str, Any], known_ids: set[str]) -> dict[str, Any] | None:
    """Return the in-place finding for one template body, or None when it states no grant.

    Args:
        body: The template body (frontmatter removed).
        fm: The template's parsed frontmatter (only ``skills`` is read).
        known_ids: Installed skill ids.

    Returns:
        ``{kind, inplace_abilities, declared_abilities}`` or None.
    """
    inplace = {i for account in find_accounts(body, known_ids) for i in account["ids"]}
    if not inplace:
        return None
    declared = {e["skill_id"] for e in normalize_entries(fm.get("skills"))}
    return {
        "kind": "duplicate" if inplace == declared else "contradiction",
        "inplace_abilities": sorted(inplace),
        "declared_abilities": sorted(declared),
    }


def report_inplace_abilities(template_name: str, fm: dict[str, Any], body: str, skills_root: Path | None) -> None:
    """Log a WARNING naming ``template_name`` when its body states its own grant."""
    finding = classify_inplace(body, fm, installed_skill_ids(skills_root))
    if finding:
        _log.warning(
            "%s states its own abilities in its body (%s): in place %s vs declared %s -- "
            "remove the hand-written section; delivery appends the declared one",
            template_name, finding["kind"], finding["inplace_abilities"], finding["declared_abilities"],
        )


def classify_inplace_spawn(body: str, declared: set[str], known_ids: set[str]) -> dict[str, Any] | None:
    """Return the in-place finding for a body that states its own sub-agents, or None.

    The same account recogniser as for abilities (``find_accounts``), applied to
    the ``sub-agents`` kind, so a hand-written table OR list is caught.

    Args:
        body: The template body (frontmatter removed).
        declared: The declaration after macro resolution.
        known_ids: Agent ids (registry ids and sibling template stems).

    Returns:
        ``{kind, inplace_sub_agents, declared_sub_agents}`` or None.
    """
    inplace = {i for account in find_accounts(body, known_ids, "sub-agents") for i in account["ids"]}
    if not inplace:
        return None
    return {
        "kind": "duplicate" if inplace == declared else "contradiction",
        "inplace_sub_agents": sorted(inplace),
        "declared_sub_agents": sorted(declared),
    }


def report_inplace_spawn(
    template_path: Path, fm: dict[str, Any], body: str, agents: list[dict[str, Any]] | None
) -> None:
    """Log a WARNING naming the template file when its body states its own sub-agents."""
    rows = agents or []
    phase = [a["id"] for a in rows if a.get("is_ticket_phase")]
    known = {a["id"] for a in rows} | {p.stem for p in template_path.parent.glob("*.md")}
    declared = set(resolve_spawn_ids(declared_spawn(fm), phase))
    finding = classify_inplace_spawn(body, declared, known)
    if finding:
        _log.warning(
            "%s states its own sub-agents in its body (%s): in place %s vs declared %s -- "
            "remove the hand-written section; delivery appends the declared one",
            template_path.name, finding["kind"], finding["inplace_sub_agents"], finding["declared_sub_agents"],
        )


def report_inplace_accounts(
    template_path: Path, fm: dict[str, Any], body: str, skills_root: Path | None,
    agents: list[dict[str, Any]] | None = None,
) -> None:
    """Report a hand-written abilities account AND a hand-written sub-agent account in one body."""
    report_inplace_abilities(template_path.name, fm, body, skills_root)
    report_inplace_spawn(template_path, fm, body, agents)


def detect_inplace_abilities(
    templates_dir: Path | None = None, *, known_skill_ids: set[str] | None = None
) -> dict[str, Any]:
    """Scan source agent templates for bodies that state their own grant.

    Args:
        templates_dir: Directory of ``*.md`` agent templates; None resolves the
            package's own ``templates/agents`` from this module's location.
        known_skill_ids: Installed skill ids; None derives them from the sibling
            ``templates/skills`` directory.

    Returns:
        ``{ok, examined_count, stating_count, findings}``; each finding carries
        ``template`` (file name), ``kind`` and both ability lists. ``ok`` is False
        only when no template was examined.
    """
    # deferred: template_compiler imports this module, so a top-level import would be circular
    from template_compiler import parse_frontmatter

    agents_dir = Path(templates_dir) if templates_dir is not None else _PACKAGE_ROOT / "templates" / "agents"
    known = known_skill_ids if known_skill_ids is not None else installed_skill_ids(agents_dir.parent / "skills")
    findings: list[dict[str, Any]] = []
    examined = 0
    for template in sorted(agents_dir.glob("*.md")):
        if template.name.startswith("_"):
            continue
        try:
            fm, body = parse_frontmatter(template.read_text(encoding="utf-8"))
        except OSError as exc:
            _log.warning("cannot read agent template %s: %s", template, exc)
            raise
        if not fm.get("name"):
            continue
        examined += 1
        finding = classify_inplace(body, fm, known)
        if finding:
            findings.append({"template": template.name, **finding})
    return {"ok": examined > 0, "examined_count": examined, "stating_count": len(findings), "findings": findings}
