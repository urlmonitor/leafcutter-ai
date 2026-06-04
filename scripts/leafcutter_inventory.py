"""
MODULE: leafcutter_inventory.py
GOAL: Extract and display agent, skill, and command inventories from registry
    JSON files and deployed command directories for the /leafcutter command.
BUSINESS CONTEXT: Provides a dynamic, always-current view of the leafcutter
    package surface area without hardcoding lists that rot as the package grows.
ARCHITECTURE: Pure stdlib (json, pathlib, argparse, sys). Reads
    config/agent_registry.json and config/skill_registry.json from the repo,
    scans the deployed commands directory, and prints a formatted Markdown
    inventory to stdout. No file writes, no side-effects.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"WARNING: could not load {path}: {exc}", file=sys.stderr)
        return {}


def _agent_table(registry: dict) -> str:
    agents = registry.get("agents", [])
    if not agents:
        return "*No agents found in registry.*"

    tiers: dict[str, list[dict]] = {}
    for a in agents:
        tier = a.get("tier", "unknown")
        tiers.setdefault(tier, []).append(a)

    lines = []
    for tier in sorted(tiers.keys()):
        lines.append(f"### {tier.title()} agents")
        lines.append("")
        lines.append("| Agent | Role | Model | Phase? | Deprecated? |")
        lines.append("|-------|------|-------|--------|-------------|")
        for a in sorted(tiers[tier], key=lambda x: x.get("id", "")):
            deprecated = "yes" if a.get("deprecated") else ""
            phase = "yes" if a.get("is_ticket_phase") else ""
            model = a.get("model", "—")
            role = a.get("role", "—")
            lines.append(f"| `{a['id']}` | {role} | {model} | {phase} | {deprecated} |")
        lines.append("")

    return "\n".join(lines)


def _skill_table(registry: dict) -> str:
    skills = registry.get("skills", [])
    if not skills:
        return "*No skills found in registry.*"

    lines = [
        "| Skill | Portable? | Domain | Internal? |",
        "|-------|-----------|--------|-----------|",
    ]
    for s in sorted(skills, key=lambda x: x.get("id", "")):
        portable = "yes" if s.get("portable") else "no"
        domain = s.get("domain") or "—"
        internal = "yes" if s.get("internal") else ""
        lines.append(f"| `{s['id']}` | {portable} | {domain} | {internal} |")

    return "\n".join(lines)


def _command_list(commands_dir: Path) -> str:
    if not commands_dir.is_dir():
        return "*No commands directory found.*"

    cmds = sorted(commands_dir.glob("*.md"))
    if not cmds:
        return "*No commands found.*"

    lines = []
    for cmd in cmds:
        name = cmd.stem
        desc = ""
        in_frontmatter = False
        for line in cmd.read_text(encoding="utf-8").splitlines():
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter and line.strip().startswith("description:"):
                desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                break
        lines.append(f"- `/{name}` — {desc}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Leafcutter package inventory")
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Path to the leafcutter-ai repo root",
    )
    parser.add_argument(
        "--commands-dir",
        type=Path,
        default=None,
        help="Path to the deployed .claude/commands/ directory",
    )
    parser.add_argument(
        "--section",
        choices=["agents", "skills", "commands", "all"],
        default="all",
        help="Which section to output",
    )
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    agent_reg = _load_json(repo / "config" / "agent_registry.json")
    skill_reg = _load_json(repo / "config" / "skill_registry.json")
    commands_dir = (args.commands_dir or repo.parent / ".claude" / "commands").resolve()

    if args.section in ("agents", "all"):
        print("## Agents\n")
        print(_agent_table(agent_reg))

    if args.section in ("skills", "all"):
        print("## Skills\n")
        print(_skill_table(skill_reg))

    if args.section in ("commands", "all"):
        print("## Slash Commands\n")
        print(_command_list(commands_dir))


if __name__ == "__main__":
    main()
