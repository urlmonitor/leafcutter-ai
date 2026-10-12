"""
MODULE: agent_grant_delivery_gate
GOAL: Make the build consume ``agent_grant_delivery.verify_grants_delivered``: a
    compiled prompt whose abilities section is short, names an ability that was
    not granted, or is carried by an agent granted nothing REFUSES the build; a
    pure duplicate second account is REPORTED by name and the build continues.
BUSINESS CONTEXT: AR-300a-1 / AR-300a-3 / AR-300a-4. The verifier read the
    compiled prompts but had no production caller, so none of its findings ever
    reached the build's exit status. Same skip rules as the preparation gate: a
    dry run, or a run that compiled no agents, prints a visible skip line; a
    package in which NO agent declares any skills has nothing to compare and is
    skipped with a stated line (AR-300a-1-i would otherwise make that empty
    declarations population a failure).
ARCHITECTURE: ``note_agents_source`` is told by the agents phase which template
    directory it compiled from (declarations are read from those SOURCE
    templates, never from the registry). ``refuse_if_grants_undelivered`` is the
    seam ``agent_preparation_delivery.refuse_if_agents_compiled`` calls beside
    the preparation gate. Build-engine module under ``scripts/``; no
    deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-12 [python-coder/AR-300-review]: Created. A ``second-account``-only
  prompt is reported, not refused (AR-300a-4-i: a duplicate must not block a
  mid-migration tree; a contradiction already surfaces as short/extra). (#AR-300a-4)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent_declaration_shape import MalformedDeclarationError
from agent_grant_delivery import describe_delivery_finding, verify_grants_delivered
from agent_inplace_abilities import installed_skill_ids
from template_compiler import parse_frontmatter

_log = logging.getLogger(__name__)
_SOURCE: dict[str, Path | None] = {"agents_dir": None}
_REPORT_ONLY = frozenset({"second-account"})
_TAG = "agent grant delivery"


def note_agents_source(agents_dir: Path) -> None:
    """Record the template directory the agents phase compiled from (call after the registry reset)."""
    _SOURCE["agents_dir"] = Path(agents_dir)


def _read_declarations(agents_dir: Path) -> dict[str, list[Any]]:
    """Return ``{template_stem: skills}`` for every non-helper template that declares any."""
    declarations: dict[str, list[Any]] = {}
    for template in sorted(agents_dir.glob("*.md")):
        if template.name.startswith("_"):
            continue
        try:
            fm, _body = parse_frontmatter(template.read_text(encoding="utf-8"))
        except OSError as exc:
            _log.warning("cannot read agent template %s: %s", template, exc)
            raise
        if isinstance(fm, dict) and fm.get("skills"):
            declarations[template.stem] = fm["skills"]
    return declarations


def _verdict(agents_dir: Path, roots: list[Path], expected: int) -> dict[str, Any] | None:
    """Return the delivery verdict, or None when no agent declares any skills."""
    declarations = _read_declarations(agents_dir)
    if not declarations:
        return None
    return verify_grants_delivered(
        declarations, roots, expected_prompt_count=expected,
        known_skill_ids=installed_skill_ids(agents_dir.parent / "skills"))


def _present(verdict: dict[str, Any]) -> int:
    """Print the verdict (reported then refusing lines) and return the exit code."""
    reported = [f for f in verdict["findings"] if f["kind"] in _REPORT_ONLY]
    refusing = [f for f in verdict["findings"] if f["kind"] not in _REPORT_ONLY]
    status = "FAILED" if refusing else "ok"
    print(f"{_TAG}: {status} -- {verdict['granted_count']} agents hold a grant "
          f"({verdict['conditional_grant_count']} conditional), {verdict['complete_count']} complete, "
          f"{verdict['no_section_count']} section-free, across {verdict['inspected_count']} compiled prompts")
    for finding in reported:
        print(f"  WARNING (reported, not refused): {describe_delivery_finding(finding)}")
    for finding in refusing:
        print(f"  {describe_delivery_finding(finding)}")
    return 1 if refusing else 0


def refuse_if_grants_undelivered(
    project_root: Path, config: dict[str, Any], dry_run: bool, *, compiled_roots: list[Path], expected: int
) -> int:
    """Build seam: print the grant-delivery verdict and return 1 to refuse, else 0.

    Args:
        project_root: Project root the build wrote into (unused beyond the skip rules; kept for symmetry).
        config: Build config.
        dry_run: When True nothing was written, so there is nothing to judge.
        compiled_roots: The platform roots the agents phase wrote.
        expected: Prompts the build compiled (templates x roots).

    Returns:
        1 when a finding other than a duplicate second account exists, otherwise 0.
    """
    del project_root, config
    agents_dir = _SOURCE["agents_dir"]
    if dry_run:
        print(f"{_TAG}: skipped (dry-run writes no compiled prompts)")
        return 0
    if agents_dir is None:
        print(f"{_TAG}: skipped -- no agent template directory was recorded in this run")
        return 0
    try:
        verdict = _verdict(agents_dir, compiled_roots, expected)
    except MalformedDeclarationError as exc:
        print(f"{_TAG}: FAILED -- malformed declaration: {exc}")
        return 1
    if verdict is None:
        print(f"{_TAG}: skipped -- no agent declares any skills (nothing to compare)")
        return 0
    return _present(verdict)
