"""propose_agent_self_description.py — Phase 1 helper for INF-600 Ticket 5.

Scans one or all agent templates, extracts proposed self-description field
values using text heuristics, and writes YAML proposal files to
scripts/proposals/agent_self_description_<agent-id>.yaml.

Usage:
    python scripts/propose_agent_self_description.py [--agent <id>]

If --agent is omitted, all templates in templates/agents/ are processed.

# DECISION HISTORY
# - 2026-06-05 [python-coder/EPIC-SelfDescribingAgents/05]:
#   Written per INF-600 Ticket 5 Phase 1. Extracts heuristic field proposals
#   from agent template prose. Does NOT modify templates or registry directly.
#   (#EPIC-SelfDescribingAgents/05)
"""

from __future__ import annotations

import argparse
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
PROPOSALS_DIR = SCRIPT_DIR / "proposals"

# ---------------------------------------------------------------------------
# Frontmatter parser (minimal — avoid dep on build_phases)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}
    body = text[end + 4:].lstrip("\n")
    return fm, body


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def _extract_pre_flight_reads(text: str) -> list[dict]:
    """Extract pre_flight_reads proposals from template prose."""
    reads: list[dict] = []

    # Always include ticket_path if it's a phase agent that signs off
    reads.append({"source": "ticket_path", "required": True})

    # Look for "Pre-Flight Reads" section
    pf_match = re.search(
        r"##\s+(?:Pre-Flight Reads?|Pre-Flight Steps?|Mandatory Pre-Flight)[^\n]*\n(.*?)(?=\n##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if pf_match:
        section_body = pf_match.group(1)
        # Extract bullets
        for line in section_body.splitlines():
            stripped = line.strip().lstrip("0123456789.-*").strip()
            if stripped and len(stripped) > 10:
                # Extract file paths / source references
                file_refs = re.findall(r"`([^`]+\.(?:md|json|yaml|py))`", stripped)
                for ref in file_refs[:2]:  # Limit to first 2
                    reads.append({"source": ref, "required": False, "condition": "when present"})
                if not file_refs and "read" in stripped.lower():
                    # Generic reads
                    reads.append({"source": "project conventions", "required": False})

    # Look for PROJECT_CONTEXT.md patterns
    if "PROJECT_CONTEXT" in text:
        reads.append({"source": ".agents/agents/<name>/PROJECT_CONTEXT.md", "required": False, "condition": "when present"})

    # De-duplicate by source
    seen: set[str] = set()
    unique: list[dict] = []
    for r in reads:
        if r["source"] not in seen:
            seen.add(r["source"])
            unique.append(r)
    return unique


def _extract_skills_invoked(text: str) -> list[dict]:
    """Extract skills_invoked proposals from skill references in prose."""
    skills: list[dict] = []
    # Look for SKILL.md references
    skill_refs = re.findall(r"[`'\"]?\.claude/skills/([a-z][a-z0-9-]+)/SKILL\.md[`'\"]?", text)
    skill_refs += re.findall(r"`([a-z][a-z0-9-]+)` skill", text)
    skill_refs += re.findall(r"the `([a-z][a-z0-9-]+)` skill", text)

    # Detect conditional vs always
    seen: set[str] = set()
    for skill_id in skill_refs:
        if skill_id in seen:
            continue
        seen.add(skill_id)
        # Heuristically determine mode
        pattern = re.compile(
            rf"(?:if|when|only|conditional)\b.*\b{re.escape(skill_id)}\b|"
            rf"\b{re.escape(skill_id)}\b.*(?:if|when|only)",
            re.IGNORECASE,
        )
        mode = "conditional" if pattern.search(text) else "always"
        skills.append({"skill_id": skill_id, "mode": mode})

    # signoff is always invoked by any phase agent
    if "signoff" not in seen:
        fm, _ = parse_frontmatter(text)
        if fm.get("signoff"):
            skills.append({"skill_id": "signoff", "mode": "always"})

    return skills


def _extract_behavioral_patterns(text: str) -> list[dict]:
    """Extract behavioral_patterns proposals from conditional prose."""
    patterns: list[dict] = []

    # Look for Stop-and-Ask style triggers
    stop_ask = re.findall(
        r"(?:Stop\s+and\s+ask|halt\s+immediately|Halt\s+and\s+surface|refuse\s+politely|do\s+NOT\s+proceed)[^.!]*[.!]",
        text,
        re.IGNORECASE,
    )
    for match in stop_ask[:2]:
        patterns.append({
            "name": "Stop-and-Ask",
            "trigger": "condition requiring user decision or out-of-scope action",
            "behavior": match.strip()[:100],
            "related_agent": None,
        })

    # Look for delegation patterns (e.g. "delegate to X")
    delegate = re.findall(
        r"(?:delegate|dispatch|spawn|invoke)\s+(?:to\s+)?`([a-z][a-z0-9-]+)`[^.]*\.",
        text,
        re.IGNORECASE,
    )
    related_seen: set[str] = set()
    for agent_name in delegate[:3]:
        if agent_name not in related_seen:
            related_seen.add(agent_name)
            patterns.append({
                "name": f"Delegation to {agent_name}",
                "trigger": f"task requiring {agent_name} capabilities",
                "behavior": f"Delegates to {agent_name} via Agent tool",
                "related_agent": agent_name,
            })

    # Look for "only when X" or "if Y, then Z" conditional behaviors
    conditionals = re.findall(
        r"(?:If|When|Only\s+if|Only\s+when)\s+([^,.\n]{15,80}),\s*([^.\n]{15,100})[.\n]",
        text,
        re.IGNORECASE,
    )
    for trigger, behavior in conditionals[:2]:
        patterns.append({
            "name": "Conditional Behavior",
            "trigger": trigger.strip()[:80],
            "behavior": behavior.strip()[:100],
            "related_agent": None,
        })

    # Default fallback
    if not patterns:
        patterns.append({
            "name": "Standard-Phase",
            "trigger": "normal phase agent invocation",
            "behavior": "Reads ticket, performs work, signs off with status: ok or blocker",
            "related_agent": None,
        })

    return patterns


def _extract_inputs(text: str, fm: dict) -> list[dict]:
    """Extract inputs from template."""
    inputs: list[dict] = []

    # ticket_path is always an input for phase agents
    if fm.get("signoff"):
        inputs.append({
            "name": "ticket_path",
            "type": "file_path",
            "required": True,
            "description": "Absolute path to the ticket markdown file",
        })

    # Look for ## Input or ## Invocation contract sections
    input_match = re.search(
        r"##\s+(?:Input|Invocation\s+contract|Inputs)[^\n]*\n(.*?)(?=\n##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if input_match:
        section = input_match.group(1)
        # Extract named params from backtick references
        params = re.findall(r"`([a-z][a-z0-9_]+)`:\s*([^\n]{5,80})", section)
        for name, desc in params[:4]:
            if name != "ticket_path":
                inputs.append({
                    "name": name,
                    "type": "string",
                    "required": False,
                    "description": desc.strip(),
                })

    # Question / design input pattern for internal agents
    if "question:" in text.lower() and "perspective:" in text.lower():
        inputs = [
            {"name": "question", "type": "string", "required": True, "description": "Design question to reason about"},
            {"name": "perspective", "type": "string", "required": True, "description": "Single reasoning lens (simplicity, robustness, etc.)"},
        ]

    return inputs


def _extract_outputs(text: str, fm: dict) -> list[dict]:
    """Extract outputs from template."""
    outputs: list[dict] = []

    if fm.get("signoff"):
        outputs.append({
            "name": "sign_off_comment",
            "type": "sign_off_comment",
            "description": "Sign-off comment with status: ok | blocker | handoff",
        })

    # Look for ## Output section
    out_match = re.search(
        r"##\s+Output[^\n]*\n(.*?)(?=\n##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if out_match:
        section = out_match.group(1)
        # Extract JSON keys
        json_keys = re.findall(r'"([a-z][a-z0-9_]+)"\s*:', section)
        for key in json_keys[:3]:
            if key not in {"status", "feedback_id"}:
                outputs.append({
                    "name": key,
                    "type": "structured_response",
                    "description": f"Output field: {key}",
                })

    if not outputs:
        outputs.append({
            "name": "completion_report",
            "type": "structured_response",
            "description": "Structured completion payload or sign-off comment",
        })

    return outputs


def _extract_mutates(text: str, fm: dict) -> list[dict]:
    """Extract mutates from template."""
    mutates: list[dict] = []

    if fm.get("signoff"):
        mutates.append({
            "name": "ticket_frontmatter_agents_status",
            "surface": "ticket frontmatter",
            "description": f"Sets agents.{fm.get('name', '<name>')} to signed_off or failed",
        })
        mutates.append({
            "name": "sign_offs_checklist",
            "surface": "ticket body sign-offs section",
            "description": f"Checks the {fm.get('name', '<name>')} checkbox with timestamp",
        })

    # Look for what the agent writes
    if "Write" in fm.get("tools", "") and fm.get("signoff"):
        mutates.append({
            "name": "implementation_artifacts",
            "surface": "repository files",
            "description": "Files created or modified during phase execution",
        })

    if not mutates:
        mutates.append({
            "name": "none",
            "surface": "none",
            "description": "Read-only agent — no filesystem mutations",
        })

    return mutates


def _extract_knowledge_channels(text: str, fm: dict) -> list[dict]:
    """Extract knowledge_channels from template.

    Channels are per docs/architecture/agent_knowledge_plane.md (channels 1-11):
    1=system-prompt, 2=slash-command-invocation, 3=agent-tool-input,
    4=pre-flight-reads, 5=config-injection, 6=file-read-in-task,
    7=bash-output, 8=project-context, 9=memory-store, 10=signoff-comment,
    11=agent-registry
    """
    channels: list[dict] = []

    # Channel 1: always — system prompt / template description
    channels.append({"channel": 1, "source": "template description field"})

    # Channel 3: Agent tool input (for phase agents receiving ticket_path)
    if fm.get("signoff"):
        channels.append({"channel": 3, "source": "ticket_path from ticket-supervisor"})

    # Channel 4: pre-flight reads
    if "Pre-Flight Reads" in text or "pre-flight" in text.lower():
        channels.append({"channel": 4, "source": "pre-flight file reads"})

    # Channel 5: config injection (skills_config.json)
    if fm.get("config_keys"):
        channels.append({"channel": 5, "source": "skills_config.json config_keys"})

    # Channel 6: file reads during task
    if "Read" in fm.get("tools", ""):
        channels.append({"channel": 6, "source": "project files read during execution"})

    # Channel 7: bash output
    if "Bash" in fm.get("tools", ""):
        channels.append({"channel": 7, "source": "bash command output (git, build, tests)"})

    # Channel 8: PROJECT_CONTEXT
    if "PROJECT_CONTEXT" in text:
        channels.append({"channel": 8, "source": "PROJECT_CONTEXT.md"})

    # Channel 9: memory
    if fm.get("memory"):
        channels.append({"channel": 9, "source": "agent memory store"})

    return channels


def _extract_category(fm: dict) -> str:
    """Assign a category based on agent characteristics."""
    name = fm.get("name", "")
    signoff = fm.get("signoff", False)
    tools = fm.get("tools", "")

    # Supervisor agents
    if any(s in name for s in ["supervisor", "create-ticket", "create-epic", "brainstorm-lead", "finalize-feature", "worktree-agent", "onboard"]):
        return "supervisor"

    # Planning agents
    if any(s in name for s in ["business-analyst", "architect-review", "it-po", "refinement", "product-owner", "test-planner"]):
        return "planning"

    # Testing agents
    if any(s in name for s in ["test-runner", "test-writer", "sql-test-writer", "ac-validator", "ac-fulfillment-gate", "user-surface-smoker", "test-failure-triage"]):
        return "testing"

    # Research agents
    if any(s in name for s in ["research-agent", "brainstorm-worker", "knowledge-harvester"]):
        return "research"

    # Implementation agents (coders and doc writers that write artifacts)
    if signoff and ("Edit" in tools or "Write" in tools):
        if any(s in name for s in ["sql-", "python-coder", "frontend-coder"]):
            return "implementation"
        if any(s in name for s in ["documentation-expert", "explanation-author", "how-to-author", "reference-author", "adr-author", "architecture-diagram-author", "llm-expert"]):
            return "implementation"

    # Phase agents with signoff that review/commit/PR
    if signoff and any(s in name for s in ["commit", "pr-reviewer", "pull-request", "change-scope-reviewer", "code-review-architect"]):
        return "implementation"

    # Default
    if signoff:
        return "implementation"
    return "supervisor"


def propose_agent(template_file: Path) -> dict:
    """Generate a proposal dict for a single agent template."""
    text = template_file.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    full_text = body  # Use body for prose analysis

    return {
        "agent_id": fm.get("name") or template_file.stem,
        "template_file": str(template_file.relative_to(PACKAGE_ROOT)),
        "proposed_frontmatter": {
            "pre_flight_reads": _extract_pre_flight_reads(full_text),
            "inputs": _extract_inputs(full_text, fm),
            "outputs": _extract_outputs(full_text, fm),
            "mutates": _extract_mutates(full_text, fm),
            "behavioral_patterns": _extract_behavioral_patterns(full_text),
        },
        "proposed_registry": {
            "category": _extract_category(fm),
            "skills_invoked": _extract_skills_invoked(full_text),
            "knowledge_channels": _extract_knowledge_channels(full_text, fm),
        },
    }


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Propose agent self-description metadata.")
    parser.add_argument("--agent", metavar="ID", help="Agent ID to process (default: all)")
    args = parser.parse_args()

    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

    if args.agent:
        template_file = TEMPLATES_AGENTS / f"{args.agent}.md"
        if not template_file.exists():
            print(f"Error: template not found: {template_file}", file=sys.stderr)
            return 1
        files = [template_file]
    else:
        files = sorted(TEMPLATES_AGENTS.glob("*.md"))

    processed = 0
    for tf in files:
        if tf.name.startswith("_"):
            continue
        try:
            proposal = propose_agent(tf)
            agent_id = proposal["agent_id"]
            output_path = PROPOSALS_DIR / f"agent_self_description_{agent_id}.yaml"
            output_path.write_text(yaml.dump(proposal, default_flow_style=False, allow_unicode=True, sort_keys=False), encoding="utf-8")
            print(f"  Proposed: {agent_id} -> {output_path.name}")
            processed += 1
        except (OSError, yaml.YAMLError, KeyError) as exc:
            print(f"  Error processing {tf.name}: {exc}", file=sys.stderr)

    print(f"\nGenerated {processed} proposal files in {PROPOSALS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
