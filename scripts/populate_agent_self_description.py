"""populate_agent_self_description.py — Phase 2+3 applicator for INF-600 Ticket 5.

Reads proposal files from scripts/proposals/ and applies the self-description
metadata to agent template frontmatter and the agent registry.

Also supports --flip-enforcement to flip self_description_enforcement from
"warning" to "error" in config/agent_registry.json.

Usage:
    python scripts/populate_agent_self_description.py [--dry-run] [--agent <id>]
    python scripts/populate_agent_self_description.py --flip-enforcement

# DECISION HISTORY
# - 2026-06-05 [python-coder/EPIC-SelfDescribingAgents/05]:
#   Applicator script for INF-600 Ticket 5 Phase 2+3. Reads YAML proposals
#   and writes metadata into template frontmatter and registry JSON.
#   (#EPIC-SelfDescribingAgents/05)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent
TEMPLATES_AGENTS = PACKAGE_ROOT / "templates" / "agents"
REGISTRY_PATH = PACKAGE_ROOT / "config" / "agent_registry.json"
PROPOSALS_DIR = SCRIPT_DIR / "proposals"


# ---------------------------------------------------------------------------
# Frontmatter manipulation
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str) -> tuple[str, str, str]:
    """Split file into (prefix_dashes, fm_text, body)."""
    if not text.startswith("---"):
        return "---\n", "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "---\n", "", text
    fm_text = text[3:end + 1]
    body = text[end + 4:]
    return "---", fm_text, body


def _insert_fields(fm_text: str, fields: dict) -> str:
    """Insert YAML fields into frontmatter text after existing fields.

    If a field already exists, skip it (do not overwrite existing data).
    Appends new fields at the end of the frontmatter.
    """
    try:
        fm = yaml.safe_load(fm_text.strip()) or {}
    except yaml.YAMLError:
        fm = {}

    lines = fm_text.rstrip().splitlines()
    appended: list[str] = []
    for key, value in fields.items():
        if key not in fm or fm[key] is None:
            # Serialize the value as YAML
            block = yaml.dump({key: value}, default_flow_style=False, allow_unicode=True)
            appended.append(block.rstrip())

    if not appended:
        return fm_text

    return fm_text.rstrip() + "\n" + "\n".join(appended) + "\n"


def apply_frontmatter_fields(template_path: Path, fields: dict, dry_run: bool = False) -> bool:
    """Add missing self-description fields to a template's frontmatter.

    Returns True if any changes were made.
    """
    text = template_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        print(f"    SKIP {template_path.name}: no frontmatter", file=sys.stderr)
        return False

    end = text.find("\n---", 3)
    if end == -1:
        print(f"    SKIP {template_path.name}: malformed frontmatter", file=sys.stderr)
        return False

    fm_text = text[3:end + 1]
    body = text[end + 4:]

    new_fm_text = _insert_fields(fm_text, fields)
    if new_fm_text == fm_text:
        return False  # Nothing to add

    new_text = "---" + new_fm_text + "\n---" + body
    if not dry_run:
        template_path.write_text(new_text, encoding="utf-8")
    return True


def apply_registry_fields(registry_data: dict, agent_id: str, fields: dict) -> bool:
    """Add missing fields to a registry entry in-place.

    Returns True if any changes were made.
    """
    changed = False
    for entry in registry_data.get("agents", []):
        if entry.get("id") == agent_id:
            for key, value in fields.items():
                if key not in entry:
                    entry[key] = value
                    changed = True
            return changed
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Apply agent self-description metadata.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    parser.add_argument("--agent", metavar="ID", help="Apply only this agent ID")
    parser.add_argument("--flip-enforcement", action="store_true",
                        help="Flip self_description_enforcement to 'error'")
    args = parser.parse_args()

    if args.flip_enforcement:
        return _flip_enforcement(args.dry_run)

    # Load registry once
    try:
        registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
        registry_data = json.loads(registry_text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error loading registry: {exc}", file=sys.stderr)
        return 1

    # Find proposal files
    if args.agent:
        proposal_files = [PROPOSALS_DIR / f"agent_self_description_{args.agent}.yaml"]
    else:
        proposal_files = sorted(PROPOSALS_DIR.glob("agent_self_description_*.yaml"))

    if not proposal_files:
        print("No proposal files found. Run propose_agent_self_description.py first.", file=sys.stderr)
        return 1

    registry_changed = False
    template_changed = 0

    for pf in proposal_files:
        if not pf.exists():
            print(f"  SKIP (not found): {pf.name}")
            continue

        try:
            proposal = yaml.safe_load(pf.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"  ERROR loading {pf.name}: {exc}", file=sys.stderr)
            continue

        agent_id = proposal.get("agent_id", "")
        if not agent_id:
            continue

        # Apply frontmatter fields
        template_path = TEMPLATES_AGENTS / f"{agent_id}.md"
        if template_path.exists():
            fm_fields = proposal.get("proposed_frontmatter", {})
            changed = apply_frontmatter_fields(template_path, fm_fields, args.dry_run)
            if changed:
                action = "would update" if args.dry_run else "updated"
                print(f"  {action} template: {agent_id}.md")
                template_changed += 1

        # Apply registry fields
        reg_fields = proposal.get("proposed_registry", {})
        changed = apply_registry_fields(registry_data, agent_id, reg_fields)
        if changed:
            action = "would update" if args.dry_run else "updated"
            print(f"  {action} registry: {agent_id}")
            registry_changed = True

    # Write registry
    if registry_changed and not args.dry_run:
        REGISTRY_PATH.write_text(
            json.dumps(registry_data, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nRegistry written: {REGISTRY_PATH}")

    print(f"\nTemplates {'would change' if args.dry_run else 'changed'}: {template_changed}")
    return 0


def _flip_enforcement(dry_run: bool) -> int:
    """Flip self_description_enforcement to 'error'."""
    try:
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading registry: {exc}", file=sys.stderr)
        return 1

    current = data.get("self_description_enforcement", "warning")
    if current == "error":
        print("self_description_enforcement is already 'error' — no change needed.")
        return 0

    data["self_description_enforcement"] = "error"
    if not dry_run:
        REGISTRY_PATH.write_text(
            json.dumps(data, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Flipped self_description_enforcement: '{current}' -> 'error'")
    else:
        print(f"[DRY-RUN] Would flip self_description_enforcement: '{current}' -> 'error'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
