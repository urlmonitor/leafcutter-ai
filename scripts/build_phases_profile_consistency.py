"""
MODULE: build_phases_profile_consistency
GOAL: List every agent whose template frontmatter `tools` can write or edit
    files while its `mutates` declares it changes nothing, so a profile that
    contradicts its own tool list is visible instead of drifting silently.
BUSINESS CONTEXT: ACD-2500e-1 corrected the it-po profile, which had Write and
    Edit tools yet declared `mutates: none`. ACD-2500e-1-i makes that fix
    durable: the next profile that drifts the same way is reported at build
    time. The check is advisory (ADR-026 warn-before-required): a flagged
    agent never changes an exit code. An unreadable registry or template is an
    error, never "zero flagged".
ARCHITECTURE: One pure decision (`_is_flagged`), one I/O function
    (`check_profiles`), a build wiring helper (`profile_warning_count`) and a
    CLI (`main`). validate_agent_self_description in
    build_phases_agent_validation.py calls `profile_warning_count` once at its
    tail and adds the result to the warning count only. "Writes or edits" is
    read from the template frontmatter `tools`; "changes nothing" means every
    `mutates` entry is named `none`; no agent list is hard-coded. Severity is
    the module constant `SEVERITY`, deliberately not
    `self_description_enforcement` (that is `error` today and would make this
    check blocking on day one). Frontmatter is read with
    template_compiler.parse_frontmatter.

    The entry below was carried here verbatim from the docstring of
    validate_agent_self_description (build_phases_agent_validation.py) to
    restore headroom there.

    # DECISION HISTORY
    # - 2026-06-05 12:30 [python-coder/EPIC-SelfDescribingAgents/04]:
    #   Added validate_agent_self_description() per INF-600g. Checks
    #   frontmatter fields (behavioral_patterns, pre_flight_reads, inputs,
    #   outputs, mutates), registry fields (category, skills_invoked,
    #   knowledge_channels), skill_id resolvability (package + project-local),
    #   and knowledge_channels range (1-11). Aggregated output. Two severity
    #   modes: 'warning' returns (0, N); 'error' returns (N, 0).
    #   (#EPIC-SelfDescribingAgents/04)
    # - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/05]:
    #   Confirmed two-path resolution order per INF-600g-3-i:
    #   1. templates/skills/{skill_id}/SKILL.md (package-level)
    #   2. .claude/skills/{skill_id}/SKILL.md (project-local)
    #   A project-local-only skill passes validation without error.
    #   Only when neither path resolves is an error emitted.
    #   (#EPIC-SelfDescribingAgentsCorrections/05)
    # - 2026-07-08 [python-coder/TICKET-20260708-BP-1300a-descriptive-skills]:
    #   Added descriptive_only: true support per INF-600d-1. When a skills_invoked
    #   entry carries "descriptive_only": true, the validator skips skill-dir
    #   resolution (the entry documents an inline capability — no deployed
    #   templates/skills/<id>/ exists by design). The strict ``is True`` identity
    #   test prevents accidental skipping when the key holds a string, int, or None.
    #   Unmarked unresolvable entries continue to fail (guardrail preserved).
    #   (#TICKET-20260708-BP-1300a-descriptive-skills)
    # - 2026-08-18 [python-coder/EPIC-BuildPipelinePhantomRemediation/02_bp1300a1]:
    #   Dropped the ``in_project`` (deployed ``.claude/skills/``) resolution leg
    #   per BP-1300a-1 / -1-i / -1-ii. A stale local deploy previously resolved
    #   ``in_project = True`` for a since-removed skill, masking a genuinely
    #   dangling pointer in a local checkout while it still failed a fresh CI
    #   clone — an environment-dependent verdict. Resolution is now against the
    #   canonical source only (``templates/skills/``); the error message no
    #   longer names the deployed path. (#02_bp1300a1_canonical_skill_resolution)
    # - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation]:
    #   Added the ``config/skill_registry.json`` resolution leg per BP-1300a-1's
    #   literal wording — "canonical source (templates/skills plus the
    #   registry)". Previously only ``templates/skills/<id>/`` was consulted;
    #   a registry entry with ``portable: false`` and no ``template_path``
    #   (a shape ``skill_registry.schema.json`` explicitly permits, for
    #   domain-specific skills deployed only under ``.claude/skills``) was
    #   falsely flagged as unresolvable. That gap was latent only because a
    #   DIFFERENT module (``registry_validator.validate_skill_registry``,
    #   asserted by ``tests/test_skill_registry.py::test_no_orphaned_entries``)
    #   happens to enforce full bidirectional parity between the registry and
    #   ``templates/skills/`` today — an invariant this guard did not name or
    #   depend on explicitly. Adding the registry leg removes the hidden
    #   cross-module dependency and matches the AC text exactly.

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from template_compiler import parse_frontmatter

SEVERITY = "warning"
WRITE_TOOLS = frozenset({"Write", "Edit", "NotebookEdit"})


def _tool_names(tools: Any) -> set[str]:
    """Return the tool names from a frontmatter `tools` value (string or list)."""
    if isinstance(tools, str):
        tools = tools.split(",")
    if not isinstance(tools, list):
        return set()
    return {str(tool).strip() for tool in tools}


def _is_flagged(front: dict[str, Any]) -> bool:
    """True when the tools can write or edit while every mutates entry is `none`."""
    mutates = front.get("mutates")
    if not isinstance(mutates, list) or not mutates:
        return False
    declares_nothing = all(
        isinstance(entry, dict) and entry.get("name") == "none" for entry in mutates
    )
    return declares_nothing and bool(_tool_names(front.get("tools")) & WRITE_TOOLS)


def _load_registry(registry: Path) -> tuple[list[Any], list[str]]:
    """Read the registry's agent list; an unreadable registry yields an error."""
    try:
        agents = json.loads(Path(registry).read_text(encoding="utf-8"))["agents"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], [f"registry {registry} is unreadable: {exc!r}"]
    if not isinstance(agents, list):
        return [], [f"registry {registry} has no agents list"]
    return agents, []


def _read_front(agent_id: str, template: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Parse one template's frontmatter; return (frontmatter, error)."""
    try:
        front, _ = parse_frontmatter(template.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{agent_id}: template {template} is unreadable: {exc!r}"
    if not front:
        return None, f"{agent_id}: template {template} has no readable frontmatter"
    return front, None


def check_profiles(registry: Path, package_root: Path) -> tuple[list[str], int, list[str]]:
    """Examine every registry agent's template profile.

    Args:
        registry: Path of the agent registry json.
        package_root: Root that registry `template_path` entries resolve against.

    Returns:
        ``(flagged, examined, errors)``: flagged agent ids, the number of
        registry agents examined, and one message per unreadable input.
    """
    agents, errors = _load_registry(registry)
    flagged: list[str] = []
    examined = 0
    for entry in agents:
        if not isinstance(entry, dict) or "id" not in entry:
            errors.append(f"registry entry without an id: {entry!r}")
            continue
        examined += 1
        agent_id = str(entry["id"])
        rel = str(entry.get("template_path", f"templates/agents/{agent_id}.md"))
        front, error = _read_front(agent_id, Path(package_root) / rel)
        if error:
            errors.append(error)
        elif front is not None and _is_flagged(front):
            flagged.append(agent_id)
    return flagged, examined, errors


def profile_warning_count(registry: Path, package_root: Path) -> int:
    """Print the findings as warnings and return how many there were (build wiring)."""
    flagged, _, errors = check_profiles(registry, package_root)
    for agent_id in flagged:
        print(f"  [WARNING] Agent '{agent_id}' has write tools but declares mutates: none.")
    for error in errors:
        print(f"  [WARNING] Profile consistency check: {error}")
    return len(flagged) + len(errors)


def main(argv: list[str] | None = None) -> int:
    """CLI: print the report; exit 1 only on an unreadable input, never for flagged agents."""
    parser = argparse.ArgumentParser(description="Advisory agent-profile consistency check.")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--templates", required=True, type=Path, help="the templates/agents directory")
    args = parser.parse_args(argv)
    flagged, examined, errors = check_profiles(args.registry, args.templates.resolve().parents[1])
    print(f"Profile consistency: examined {examined}, {SEVERITY}: {len(flagged)} flagged")
    for agent_id in flagged:
        print(f"  {SEVERITY}: {agent_id} has write tools but declares mutates: none")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
