"""
MODULE: agent_grant_delivery
GOAL: Prove, from the COMPILED prompts alone, that every agent holding a declared
    grant of abilities has the WHOLE grant named in its prompt in every platform
    root, with exactly one account of it -- and that agents granted nothing carry
    no abilities section.
BUSINESS CONTEXT: AR-300a-1 / AR-300a-1-i / AR-300a-3 / AR-300a-4 / AR-300d-4.
    The registry and the source template both agreed for 31 agents that received
    nothing, so neither is evidence; only the prompt the agent actually reads is.
    A comparison that examined nothing must not read as one that found nothing
    wrong (KI-ACS-001), so an empty population on EITHER side, an unreadable
    root, and a population shorter than the build's own compiled-prompt count
    all FAIL, naming which side came back empty.
ARCHITECTURE: ``verify_grants_delivered(declarations, compiled_roots, *,
    expected_prompt_count, known_skill_ids)`` returns an ADR-037 verdict
    (``ok``, ``inspected_count``, ``granted_count``, ``conditional_grant_count``,
    ``complete_count``, ``no_section_count``, ``expected_prompt_count``,
    ``roots_examined``, ``population_source``, ``findings``). Per-prompt finding
    kinds: ``undelivered``, ``short-section``, ``extra-ability``,
    ``second-account``, ``unexpected-section``; population kinds:
    ``empty-population`` (+ ``side``), ``short-population``, ``unreadable-root``.
    Every compiled prompt is complete, section-free, or carries a finding.
    The verifier is NOT yet called by the build (build-time enforcement is
    AR-300b-1, slice 3). Build-engine module under ``scripts/``; no
    deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300a-1]: Created. The account definition is shared
  with the in-place detector via ``agent_ability_accounts``. (#AR-300a-1)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent_ability_accounts import find_accounts
from agent_ability_verdict import normalize_entries
from template_compiler import parse_frontmatter

_log = logging.getLogger(__name__)
_POPULATION_SOURCE = (
    "compiled prompts read from every supplied platform root; granted population "
    "from the agents' own frontmatter declarations"
)


def _read_prompts(root: Path) -> list[tuple[str, str]]:
    """Return ``(stem, text)`` for each agent prompt (a ``.md`` with a frontmatter name) in ``root``."""
    prompts = []
    for path in sorted(root.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning("cannot read compiled prompt %s: %s", path, exc)
            raise
        fm, _body = parse_frontmatter(text)
        if isinstance(fm, dict) and fm.get("name"):
            prompts.append((path.stem, text))
    return prompts


def _classify(stem: str, root: str, text: str, want: set[str], known: set[str]) -> list[dict[str, Any]]:
    """Return the per-prompt findings for one compiled prompt (empty list = complete / section-free)."""
    base = {"agent": stem, "platform_root": root}
    accounts = find_accounts(text, known)
    if not want:
        named_ids = sorted({i for account in accounts for i in account["ids"]})
        return [{**base, "kind": "unexpected-section", "accounts": len(accounts), "named": named_ids}] if accounts else []
    if not accounts:
        return [{**base, "kind": "undelivered", "missing": sorted(want)}]
    named = {i for account in accounts for i in account["ids"]}
    findings: list[dict[str, Any]] = []
    if want - named:
        findings.append({**base, "kind": "short-section", "missing": sorted(want - named)})
    if named - want:
        findings.append({**base, "kind": "extra-ability", "extra": sorted(named - want)})
    if len(accounts) > 1:
        findings.append({**base, "kind": "second-account", "accounts": len(accounts)})
    return findings


def verify_grants_delivered(
    declarations: dict[str, list[Any]],
    compiled_roots: list[Path],
    *,
    expected_prompt_count: int,
    known_skill_ids: set[str],
) -> dict[str, Any]:
    """Compare each agent's declared grant with its compiled prompt in every root.

    Args:
        declarations: ``{template_stem: skills entries}`` for agents declaring a grant.
        compiled_roots: Every platform root the build wrote (a missing path or a
            broken symlink is an unreadable root, never skipped).
        expected_prompt_count: How many prompts the build compiled on this run.
        known_skill_ids: Installed skill ids (which rows of a section name an ability).

    Returns:
        The ADR-037 verdict described in the module docstring; never raises on an
        empty or short population -- it returns ``ok: False``.
    """
    entries = {stem: normalize_entries(raw) for stem, raw in declarations.items()}
    granted = {stem: e for stem, e in entries.items() if e}
    known = set(known_skill_ids) | {i["skill_id"] for e in granted.values() for i in e}
    roots = [Path(r) for r in compiled_roots]
    findings: list[dict[str, Any]] = []
    inspected = complete = no_section = 0
    for root in roots:
        if not root.is_dir():
            findings.append({"kind": "unreadable-root", "platform_root": str(root)})
            continue
        for stem, text in _read_prompts(root):
            inspected += 1
            want = {i["skill_id"] for i in granted.get(stem, [])}
            found = _classify(stem, str(root), text, want, known)
            findings.extend(found)
            if not found:
                complete, no_section = complete + bool(want), no_section + (not want)
    sides = [side for side, empty in (("compiled_prompts", inspected == 0), ("declarations", not granted)) if empty]
    findings.extend({"kind": "empty-population", "side": side} for side in sides)
    if inspected < expected_prompt_count:
        findings.append({"kind": "short-population", "inspected": inspected, "expected": expected_prompt_count})
    return {
        "ok": not findings,
        "inspected_count": inspected,
        "granted_count": len(granted),
        "conditional_grant_count": sum(i["mode"] == "conditional" for e in granted.values() for i in e),
        "complete_count": complete,
        "no_section_count": no_section,
        "expected_prompt_count": expected_prompt_count,
        "roots_examined": [str(r) for r in roots],
        "population_source": _POPULATION_SOURCE,
        "findings": findings,
    }


def describe_delivery_finding(finding: dict[str, Any]) -> str:
    """Render one delivery finding as a single human-readable line for the build output."""
    detail = {k: v for k, v in finding.items() if k not in {"kind", "agent", "platform_root"}}
    where = f" in {finding['platform_root']}" if "platform_root" in finding else ""
    who = f"agent '{finding['agent']}' " if "agent" in finding else ""
    return f"{who}{finding['kind']}{where}: {detail}" if detail else f"{who}{finding['kind']}{where}"



