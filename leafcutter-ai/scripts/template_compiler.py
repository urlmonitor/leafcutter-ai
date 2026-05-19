"""
MODULE: template_compiler
GOAL: Compile leafcutter agent and skill template files into
    runtime-ready prompts by stripping metadata and injecting config values.
BUSINESS CONTEXT: Templates carry YAML frontmatter (adopter_notes, config_keys,
    portability declarations) that the AI runtime would never act on.
    This module strips that metadata and resolves {{config.key}} placeholders,
    producing clean output files that contain only actionable AI instructions.
    Ticket 29 extended this module with three registry-injection functions now
    in injection_builders.py: build_per_agent_spawn_table (Type 1),
    build_per_agent_skills_table (Type 2), build_registry_block (Type 3).
    Ticket 08 added build_doc_type_reference_table (Type 4) also in
    injection_builders.py. Ticket 10 added build_project_paths_table (Type 5).
    EPIC-AgentRegistryAsSourceOfTruth ticket 10 added build_agent_priority_table
    (Type 6) and build_doc_types_dispatch_table (Type 7). Registry injection
    happens after config injection.
ARCHITECTURE: Public functions: parse_frontmatter (YAML header extraction),
    strip_metadata_sections (removes ## headings in STRIPPED_HEADINGS),
    inject_config (placeholder substitution), compile_agent_template and
    compile_skill_template (orchestrate all steps). Injection builder
    functions live in injection_builders.py and are re-exported here for
    backward compatibility. Pure transformation — no file I/O except reading
    the registry JSON in registry builders.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from injection_builders import (  # noqa: E402
    build_agent_priority_table,
    build_doc_type_reference_table,
    build_doc_types_dispatch_table,
    build_per_agent_skills_table,
    build_per_agent_spawn_table,
    build_project_paths_table,
    build_registry_block,
    build_signoff_block,
    _load_registry,
)

_log = logging.getLogger(__name__)

STRIPPED_HEADINGS = {
    "## Configuration",
    "## Portability",
    "## Adopter Notes",
}

STRIPPED_HEADING_PREFIXES = (
    "## Sign-off",
    "## Post-edit verification",
)

_PLACEHOLDER_RE = re.compile(r"\{\{config\.([a-zA-Z0-9_]+)\}\}")

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _PACKAGE_ROOT / "templates"

__all__ = [
    "parse_frontmatter",
    "strip_metadata_sections",
    "inject_config",
    "build_agent_priority_table",
    "build_per_agent_spawn_table",
    "build_per_agent_skills_table",
    "build_registry_block",
    "build_doc_type_reference_table",
    "build_doc_types_dispatch_table",
    "build_project_paths_table",
    "build_signoff_block",
    "compile_agent_template",
    "compile_skill_template",
]


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown file.

    Frontmatter is expected in the form ``---\\n<yaml>\\n---`` at the very
    start of the file. If absent or malformed, the full text is returned as
    the body with an empty frontmatter dict.

    Args:
        text: Full text content of a markdown file, potentially starting
            with a YAML frontmatter block delimited by ``---`` lines.

    Returns:
        Tuple of ``(frontmatter_dict, body_without_frontmatter)``. If no
        valid frontmatter is found, returns ``({}, original_text)``.
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")

    if _YAML_AVAILABLE:
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            fm = {}
    else:
        fm = {}

    return fm, body


def strip_metadata_sections(body: str) -> str:
    """Remove sections whose heading matches STRIPPED_HEADINGS or STRIPPED_HEADING_PREFIXES.

    Strips from the ``##``-level heading line through to (not including) the
    next ``##``-level heading or end-of-file.

    Args:
        body: Markdown body text (without frontmatter) to process.

    Returns:
        Body text with all matched sections removed, normalized to end with
        exactly one newline.
    """
    lines = body.split("\n")
    result: list[str] = []
    in_stripped = False

    for line in lines:
        if line.startswith("## "):
            heading = line.rstrip()
            is_stripped = heading in STRIPPED_HEADINGS or any(
                heading.startswith(prefix) for prefix in STRIPPED_HEADING_PREFIXES
            )
            if is_stripped:
                in_stripped = True
                while result and result[-1] == "":
                    result.pop()
                continue
            else:
                in_stripped = False

        if not in_stripped:
            result.append(line)

    return "\n".join(result).rstrip("\n") + "\n"


def inject_config(body: str, config: dict[str, Any]) -> str:
    """Replace ``{{config.key}}`` placeholders with resolved config values.

    Unknown keys are left as-is so templates with optional placeholders
    degrade gracefully when run against a minimal config.

    Args:
        body: Markdown body text containing zero or more ``{{config.key}}``
            placeholder tokens.
        config: Dictionary of config values keyed by the placeholder names
            (without the ``config.`` prefix).

    Returns:
        Body text with all resolvable placeholders substituted.
    """
    def replacer(match: re.Match) -> str:
        """Substitute a single regex match with its config value.

        Args:
            match: Regex match object from ``_PLACEHOLDER_RE``; group 1 is
                the config key name.

        Returns:
            Resolved config value string, or the original placeholder text
            when the key is not present in config.
        """
        key = match.group(1)
        value = config.get(key)
        if value is None:
            return match.group(0)
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)

    return _PLACEHOLDER_RE.sub(replacer, body)


def build_verification_block() -> str:
    """Return the post-edit verification block appended to agents with ``requires_verification: true``.

    Reads the block from ``templates/agents/_post_edit_verification.md`` when it
    exists; falls back to a hardcoded inline version otherwise.

    Returns:
        String containing the verification section markdown, starting with a
        leading newline so it concatenates cleanly after the body.
    """
    verification_template = _TEMPLATES_DIR / "agents" / "_post_edit_verification.md"
    if verification_template.exists():
        return "\n" + verification_template.read_text(encoding="utf-8")
    # Inline fallback
    return """
## Post-edit verification (mandatory)

After every Edit/Write batch, run `git diff --stat <touched_paths>` and paste verbatim. For large diffs, also paste the first 5 hunks of `git diff <path>`. In non-git contexts, `Read` the changed line range and paste the extract.

Do not declare success without one of these proofs in the response.

Even if the diff is huge, always paste at least the `--stat` summary and list each touched path explicitly.
"""


def _resolve_agent_id(template_path: Path, agents: list[dict[str, Any]]) -> str:
    """Resolve the agent ID for a template file by matching against registry entries.

    Falls back to the template filename stem when no registry entry matches.

    Args:
        template_path: Absolute path to the agent template file being compiled.
        agents: List of agent dicts from agent_registry.json.

    Returns:
        The resolved agent ID string (never empty).
    """
    template_stem = template_path.stem
    for a in agents:
        reg_tpl = a.get("template_path") or ""
        if reg_tpl and Path(reg_tpl).stem == template_stem:
            return a["id"]
    return template_stem


def _apply_registry_injection(
    body: str,
    template_name: str,
    agent_id: str,
    agents: list[dict[str, Any]],
    registry_path: Path | None,
    skills_root: Path | None,
    inject_registry: bool,
) -> str:
    """Apply all four registry placeholder types to a template body.

    Resolves ``{{my_spawn_allowlist}}``, ``{{my_skills_used}}``,
    ``{{registry_phase_agents_table}}`` (when inject_registry is True),
    ``{{doc_type_reference_table}}``, ``{{project_paths_table}}``,
    ``{{agent_priority_table}}``, and ``{{doc_types_dispatch_table}}``.

    Args:
        body: Template body text after config injection.
        template_name: Filename of the template (used in error messages).
        agent_id: Registry ID for the agent being compiled.
        agents: Full list of agent dicts from agent_registry.json.
        registry_path: Path to agent_registry.json (for Type 3 only).
        skills_root: Path to ``templates/skills/`` (for Type 2 descriptions).
        inject_registry: When True, resolve Type 3 placeholder.

    Returns:
        Body text with all applicable placeholders replaced.
    """
    if "{{my_spawn_allowlist}}" in body:
        try:
            table = build_per_agent_spawn_table(agent_id, agents)
        except ValueError as exc:
            raise ValueError(
                f"Registry injection failed for '{template_name}': {exc}"
            ) from exc
        body = body.replace("{{my_spawn_allowlist}}", table)

    if "{{my_skills_used}}" in body:
        try:
            skills_table = build_per_agent_skills_table(agent_id, agents, skills_root)
        except ValueError as exc:
            raise ValueError(
                f"Registry injection failed for '{template_name}': {exc}"
            ) from exc
        body = body.replace("{{my_skills_used}}", skills_table)

    if inject_registry and "{{registry_phase_agents_table}}" in body:
        phase_table = build_registry_block(registry_path) if registry_path else ""
        body = body.replace("{{registry_phase_agents_table}}", phase_table)

    if "{{doc_type_reference_table}}" in body:
        doc_table = build_doc_type_reference_table()
        body = body.replace("{{doc_type_reference_table}}", doc_table)

    # Type 5: {{project_paths_table}} — injected from paths.json
    if "{{project_paths_table}}" in body:
        paths_table = build_project_paths_table()
        body = body.replace("{{project_paths_table}}", paths_table)

    # Type 6: {{agent_priority_table}} — canonical phase ordering from registry
    if "{{agent_priority_table}}" in body:
        priority_table = build_agent_priority_table()
        body = body.replace("{{agent_priority_table}}", priority_table)

    # Type 7: {{doc_types_dispatch_table}} — unified dispatch table from doc_types.json
    if "{{doc_types_dispatch_table}}" in body:
        dispatch_table = build_doc_types_dispatch_table()
        body = body.replace("{{doc_types_dispatch_table}}", dispatch_table)

    return body


def _build_output_header(fm: dict[str, Any]) -> str:
    """Render the output frontmatter header, keeping only runtime-relevant keys.

    Strips adopter-only keys (``adopter_notes``, ``config_keys``,
    ``inject_registry``, ``requires_verification``) and keeps only ``name``, ``description``,
    ``model``, ``tools``, and ``memory``.

    Args:
        fm: Parsed frontmatter dict from the template.

    Returns:
        YAML frontmatter header string (including ``---`` delimiters and
        trailing newlines), or empty string when no relevant keys are present.
    """
    output_fm_keys = {"name", "description", "model", "tools", "memory"}
    output_fm = {k: v for k, v in fm.items() if k in output_fm_keys}
    if not output_fm:
        return ""
    if _YAML_AVAILABLE:
        fm_str = yaml.dump(output_fm, default_flow_style=False, allow_unicode=True).rstrip()
        return f"---\n{fm_str}\n---\n\n"
    lines_fm = []
    for k, v in output_fm.items():
        if isinstance(v, str) and "\n" in v:
            indented = "\n".join("  " + line for line in v.split("\n"))
            lines_fm.append(f"{k}: |\n{indented}")
        else:
            lines_fm.append(f"{k}: {v}")
    return "---\n" + "\n".join(lines_fm) + "\n---\n\n"


def compile_agent_template(
    template_path: Path,
    config: dict[str, Any],
    registry_path: Path | None = None,
    agents: list[dict[str, Any]] | None = None,
    skills_root: Path | None = None,
) -> str:
    """Compile an agent template file into a runtime-ready agent prompt.

    Compilation steps:
    (1) parse YAML frontmatter;
    (2) build output header — runtime-relevant keys only, build directives stripped;
    (3) strip metadata sections from body;
    (4) inject config placeholders;
    (5) inject registry placeholders (Types 1–4) via ``_apply_registry_injection``;
    (6) conditionally append sign-off block when ``signoff: true`` is set.

    Args:
        template_path: Absolute path to a ``.md`` agent template file with
            optional YAML frontmatter.
        config: Merged config dictionary used for placeholder injection.
        registry_path: Optional absolute path to ``agent_registry.json``. When
            provided together with ``agents``, used for Type 3 injection.
        agents: Optional pre-loaded list of agent dicts from agent_registry.json.
            Required for Types 1 and 2. When None, registry placeholders are
            left as-is (graceful degradation — no error).
        skills_root: Optional absolute path to the ``templates/skills/`` directory.
            Used for skill description lookup in Type 2 injection.

    Returns:
        Compiled agent prompt string ready to be written to the target
        ``.claude/agents/`` directory.
    """
    text = template_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    header = _build_output_header(fm)
    body = strip_metadata_sections(body)
    body = inject_config(body, config)

    if agents is not None:
        agent_id = _resolve_agent_id(template_path, agents)
        body = _apply_registry_injection(
            body=body,
            template_name=template_path.name,
            agent_id=agent_id,
            agents=agents,
            registry_path=registry_path,
            skills_root=skills_root,
            inject_registry=bool(fm.get("inject_registry", False)),
        )

    if fm.get("requires_verification") is True:
        body = body.rstrip("\n")
        v_block = build_verification_block()
        if body.endswith("```"):
            fence_start = body.rfind("\n```", 0, len(body) - 3)
            if fence_start != -1:
                body = body[:fence_start].rstrip("\n") + v_block + "\n\n" + body[fence_start:].lstrip("\n")
            else:
                body = body + v_block
        else:
            body = body + v_block
        body += "\n"

    if fm.get("signoff") is True:
        body = body.rstrip("\n") + build_signoff_block()

    return header + body


def compile_skill_template(template_path: Path, config: dict[str, Any]) -> str:
    """Compile a skill template (SKILL.md or any ``.md`` in a skill directory).

    Skills preserve their full frontmatter (``name``, ``description``,
    ``allowed-tools``) but have metadata sections stripped and config
    placeholders injected.

    Args:
        template_path: Absolute path to a skill ``.md`` template file.
        config: Merged config dictionary used for placeholder injection.

    Returns:
        Compiled skill content string ready to be written to the target
        ``.claude/skills/`` directory.
    """
    text = template_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    if fm and _YAML_AVAILABLE:
        fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True).rstrip()
        header = f"---\n{fm_str}\n---\n\n"
    else:
        header = ""

    body = strip_metadata_sections(body)
    body = inject_config(body, config)

    return header + body


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 12:05 [epic-supervisor/ticket-13]: Extracted from build.py (#EPIC-LeafcutterMVP/01)
#   during file-size refactor (build.py exceeded 400-line limit). All
#   template-compilation logic (parse, strip, inject, compile) moved here
#   so build.py stays focused on build phases and CLI orchestration.
# - 2026-05-13 12:45 [epic-supervisor/ticket-14]: Added STRIPPED_HEADING_PREFIXES (#EPIC-LeafcutterMVP/01)
#   tuple and updated strip_metadata_sections() to strip any ## Sign-off*
#   heading by prefix. This handles both "## Sign-off (when ticket_path is
#   provided)" and "## Sign-offs" variants present in the agent corpus, so
#   that agent templates can be copied as-is from .claude/agents/ with their
#   inline sign-off blocks replaced by signoff: true in frontmatter.
# - 2026-05-13 18:00 [epic-supervisor/ticket-29]: Added registry injection. (#EPIC-LeafcutterMVP/01)
#   build_per_agent_spawn_table / build_per_agent_skills_table / build_registry_block
#   resolve {{my_spawn_allowlist}}, {{my_skills_used}}, {{registry_phase_agents_table}}.
#   compile_agent_template() takes optional registry_path/agents/skills_root.
# - 2026-05-13 14:00 [epic-supervisor/ticket-04]: Fixed type error in (#EPIC-LeafcutterMVP/01)
#   build_registry_block(): trigger_conditions items are dicts {type, expression}
#   but code did "; ".join(triggers) expecting strings. Fixed by extracting
#   t.get("expression", str(t)) for dict items. All 308 tests pass post-fix.
# - 2026-05-14 15:30 [Claude]: Added `memory` to agent output_fm_keys (#EPIC-LeafcutterMVP/01)
#   allowlist; was silently stripping `memory: true` from commit.md,
#   pr-reviewer.md, worktree-agent.md on every build.
# - 2026-05-14 21:00 [EPIC-ArchitectureDocsEnforcement/ticket 09 — Hendrik/Claude]: (#EPIC-LeafcutterMVP/01)
#   Fixed _resolve_agent_id(): guard `template_path` with `or ""` to handle null JSON value.
# - 2026-05-14 00:00 [EPIC-ArchitectureDocsEnforcement/ticket 08]: (#EPIC-LeafcutterMVP/01)
#   Added build_doc_type_reference_table() for {{doc_type_reference_table}} (Type 4
#   injection). Injected into architect-review.md and business-analyst.md.
# - 2026-05-14 10:00 [EPIC-ArchitectureDocsEnforcement/ticket 08 — refactor]: (#EPIC-LeafcutterMVP/01)
#   Extracted all injection builder functions (Types 1-4 + signoff block) to
#   injection_builders.py to keep template_compiler.py under 400 stripped lines.
#   Re-exported via __all__ for backward compatibility with build_phases.py.
# - 2026-05-14 20:30 [ticket-add-postedit-verification]: Added build_verification_block (#EPIC-LeafcutterMVP/01)
#   and injection logic before terminal JSON blocks. Added requires_verification
#   to docstrings.
# ====================================================================
