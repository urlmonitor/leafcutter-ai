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
STORE_PATH = "docs/acceptance-criteria/"
STORE_PRODUCES = "requirement_records"


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


def _store_mismatch(front: dict[str, Any], registry_produces: Any) -> tuple[str, str] | None:
    """Return ``(surface, produces)`` when a declared requirement-store surface contradicts produces.

    "Changes the requirement store" is read only from a declared `mutates`
    surface naming `docs/acceptance-criteria/`, never from the Write/Edit tools,
    so an agent the existing rule already lists (`mutates: none`) is never
    listed again here. `produces` comes from the template frontmatter, then the
    registry entry; no agent list is hard-coded.
    """
    mutates = front.get("mutates")
    if not isinstance(mutates, list):
        return None
    produces = str(front.get("produces", registry_produces))
    for entry in mutates:
        surface = entry.get("surface") if isinstance(entry, dict) else None
        if isinstance(surface, str) and STORE_PATH in surface and produces != STORE_PRODUCES:
            return surface, produces
    return None


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


def _profile_findings(
    registry: Path, package_root: Path
) -> tuple[list[tuple[str, str]], int, list[str]]:
    """Examine every registry agent's template profile; one ``(agent_id, line)`` per finding."""
    agents, errors = _load_registry(registry)
    findings: list[tuple[str, str]] = []
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
            findings.append((agent_id, f"{agent_id} has write tools but declares mutates: none"))
        elif front is not None and (hit := _store_mismatch(front, entry.get("produces"))):
            findings.append((agent_id, (
                f"{agent_id} changes the requirement store ({hit[0]}) "
                f"but declares produces: {hit[1]}"
            )))
    return findings, examined, errors


def check_profiles(registry: Path, package_root: Path) -> tuple[list[str], int, list[str]]:
    """Examine every registry agent's template profile against two rules.

    Rule 1 (ACD-2500e-1-i): write-capable tools while every `mutates` entry is
    `none`. Rule 2 (ACD-2500f-1-i): a declared `mutates` surface under
    `docs/acceptance-criteria/` while `produces` is not `requirement_records`.
    The rules are checked in that order and an agent is reported by the first
    that matches, so each mismatch is reported once.

    Args:
        registry: Path of the agent registry json.
        package_root: Root that registry `template_path` entries resolve against.

    Returns:
        ``(flagged, examined, errors)``: flagged agent ids, the number of
        registry agents examined, and one message per unreadable input.

    # DECISION HISTORY
    # - 2026-10-21 [python-coder/EPIC-RightJobRightAgentFollowUps/11]:
    #   Added rule 2 (requirement-store surface vs produces) per ACD-2500f-1-i.
    #   The return shape stays a 3-tuple of agent ids; the CLI prints one line
    #   per finding via _profile_findings, and the build still prints a single
    #   summary line with a count. (#ACD-2500f-1-i)
    """
    findings, examined, errors = _profile_findings(registry, package_root)
    return [agent_id for agent_id, _ in findings], examined, errors


def profile_warning_count(registry: Path, package_root: Path) -> int:
    """Print the findings as warnings and return how many there were (build wiring)."""
    flagged, _, errors = check_profiles(registry, package_root)
    if flagged:
        print(
            f"  [WARNING] Profile consistency: {len(flagged)} agent profile(s) "
            "contradict their tools or produces; run python scripts/build_phases_profile_consistency.py "
            "--registry config/agent_registry.json --templates templates/agents for the list"
        )
    for error in errors:
        print(f"  [WARNING] Profile consistency check: {error}")
    return len(flagged) + len(errors)


def main(argv: list[str] | None = None) -> int:
    """CLI: print the report; exit 1 only on an unreadable input, never for flagged agents."""
    parser = argparse.ArgumentParser(description="Advisory agent-profile consistency check.")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--templates", required=True, type=Path, help="the templates/agents directory")
    args = parser.parse_args(argv)
    findings, examined, errors = _profile_findings(args.registry, args.templates.resolve().parents[1])
    print(f"Profile consistency: examined {examined}, {SEVERITY}: {len(findings)} flagged")
    for _, line in findings:
        print(f"  {SEVERITY}: {line}")
    for error in errors:
        print(f"  error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
