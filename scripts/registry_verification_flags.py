"""
MODULE: registry_verification_flags
GOAL: Validate an agent template's requires_verification frontmatter flag
    bidirectionally against its declared tools: list.
BUSINESS CONTEXT: An agent whose tools: list includes Edit or Write can
    modify files and must append the post-edit verification block
    (docs/reference/agent-template-frontmatter.md); template_compiler.
    compile_agent_template() reads requires_verification to decide whether
    to do so. This module is the enforcement side: it catches an agent that
    can write but has not declared requires_verification: true (or the
    reverse — declares it without the tools to justify it, or without Bash,
    which the verification block's `git diff` step requires) at build time,
    before a silently-unverified coder agent ships.
ARCHITECTURE: validate_verification_flags(template_dir) was originally
    defined inline in registry_validator.py and is called from
    validate_agent_registry(package_root) exactly as before — this is a
    pure extraction into a sibling module, not a behaviour change. It moved
    out because registry_validator.py was already over the project's
    file-size ratchet limit (400 lines, measured via count_content_lines in
    .leafcutter/scripts/commit_guardian/_file_size_ratchet.py) and the
    ratchet forbids it growing further; extracting this self-contained,
    single-function check made room for BO-2400a-1-iii's step_kinds check
    (see step_kinds_validator.py, registry_validator.py's sibling module for
    that check) without registry_validator.py growing (see
    registry_validator.py's DECISION HISTORY, BO-2400a-1-iii entry).
"""

from __future__ import annotations

from pathlib import Path


def validate_verification_flags(template_dir: Path) -> list[str]:
    """Validate requires_verification flag in agent templates.

    - Bidirectional rule A: if tools: has Edit or Write and requires_verification is not True -> error.
    - Bidirectional rule B: if requires_verification: true but tools: has neither Edit nor Write -> error.
    - Rule C: if requires_verification: true but Bash is not in tools: -> error.

    Args:
        template_dir: Path to the templates/agents/ directory.

    Returns:
        List of error strings.
    """
    from template_compiler import parse_frontmatter

    errors: list[str] = []
    if not template_dir.exists():
        return errors

    for tmpl_file in sorted(template_dir.glob("*.md")):
        if tmpl_file.name.startswith("_"):
            continue

        text = tmpl_file.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)

        tools = fm.get("tools", [])
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",")]

        has_edit_or_write = "Edit" in tools or "Write" in tools
        requires_verification = fm.get("requires_verification") is True

        if has_edit_or_write and not requires_verification:
            errors.append(
                f"Template '{tmpl_file.name}' has Edit/Write in tools but lacks requires_verification: true."
            )
        elif requires_verification and not has_edit_or_write:
            errors.append(
                f"Template '{tmpl_file.name}' has requires_verification: true but lacks Edit/Write in tools."
            )

        if requires_verification and "Bash" not in tools:
            errors.append(
                f"Template '{tmpl_file.name}' has requires_verification: true but lacks Bash in tools (required for git diff)."
            )

    return errors


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-28 [python-coder]: Extracted verbatim out of (#TICKETLESS reason=bo-2400a-1-iii-step-kinds)
#   registry_validator.py as a pure move (no behaviour change) to make room
#   for BO-2400a-1-iii's step_kinds check. registry_validator.py was already
#   over the project's file-size ratchet limit and the ratchet forbids it
#   growing further; this function was the most self-contained candidate
#   (no dependency on any other private helper in registry_validator.py,
#   only a local import of template_compiler.parse_frontmatter) so moving it
#   out cost the least context. registry_validator.py now imports
#   validate_verification_flags from this module and calls it exactly as
#   before from validate_agent_registry().
# ====================================================================
