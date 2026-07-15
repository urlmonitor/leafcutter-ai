"""
MODULE: test_frontend_coder_unified
GOAL: Backfill green, source-contract coverage for 19 BP-700 (unified-frontend)
    acceptance criteria — the `frontend-coder` unified-agent surface. Each test
    reads a shipped artifact file (agent template, agent registry, build.py /
    build_phases.py migration code, or how-to / reference / architecture docs)
    and asserts its structure/content (or, for the build phases, its actual
    behaviour against a temp target dir) against the corresponding AC's criteria.

    Mirrors two established patterns:
      - unit_tests/agents/test_llm_expert_artifacts.py  (parse-file-as-text /
        parse-JSON source-contract assertions with a robust repo-root walk)
      - unit_tests/build/test_bp_stragglers_backfill.py (functional invocation of
        build_phases build_* functions against a tmp target dir)

    Nature: CODE_NO_TEST backfill. The artifacts already exist and are correct;
    these tests never modify them. Every test carries a `# covers: <AC-id>`
    comment naming the AC it backs.

    ACs covered (19): BP-700a-1, BP-700a-1-i, BP-700a-2, BP-700a-3, BP-700a-4,
    BP-700a-5, BP-700b-3, BP-700c-1, BP-700c-2, BP-700c-2-i, BP-700c-3,
    BP-700c-4, BP-700c-5, BP-700d-1, BP-700d-1-i, BP-700d-1-ii, BP-700d-2,
    BP-700d-3, BP-700d-4.

    NOT covered here (already fully covered by
    unit_tests/test_frontend_coder_llm_trigger.py): BP-700b-1, BP-700b-2,
    BP-700b-2-i.

    Surfaces under test (all read-only):
      - templates/agents/frontend-coder.md           (unified agent template)
      - templates/agents/onboard.md                  (onboard wizard)
      - templates/skills/frontend-design/SKILL.md    (deprecated legacy skill)
      - config/agent_registry.json                   (frontend-coder entry)
      - scripts/build.py / scripts/build_phases.py   (build-time migration)
      - docs/how-to/using-frontend-coder-with-design-integration.md
      - docs/how-to/upgrade-frontend-coder-unified-agent.md
      - docs/reference/frontend-coder-capabilities.md
      - docs/architecture/agent_delivery_workflows.md

TICKET: tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/03_bp700_frontend_coder_test_coverage.md
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Robust repo-root resolution: walk up until we find the directory that holds
# both templates/ and config/ (works from the worktree or the main checkout).
# ---------------------------------------------------------------------------

class _RepoRootNotFound(RuntimeError):
    """Raised when no ancestor directory holds both templates/ and config/."""

    def __init__(self) -> None:
        super().__init__("repo root (dir containing templates/ and config/) not found")


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "templates").is_dir() and (candidate / "config").is_dir():
            return candidate
    raise _RepoRootNotFound


_ROOT = _repo_root()
_TEMPLATE = _ROOT / "templates" / "agents" / "frontend-coder.md"
_ONBOARD = _ROOT / "templates" / "agents" / "onboard.md"
_LEGACY_SKILL = _ROOT / "templates" / "skills" / "frontend-design" / "SKILL.md"
_REGISTRY = _ROOT / "config" / "agent_registry.json"
_HOWTO_DESIGN = _ROOT / "docs" / "how-to" / "using-frontend-coder-with-design-integration.md"
_HOWTO_UPGRADE = _ROOT / "docs" / "how-to" / "upgrade-frontend-coder-unified-agent.md"
_REFERENCE = _ROOT / "docs" / "reference" / "frontend-coder-capabilities.md"
_ARCH = _ROOT / "docs" / "architecture" / "agent_delivery_workflows.md"

# Make scripts/ importable for the build-phase functional tests.
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    """Parse the leading YAML frontmatter block of a markdown file."""
    parts = text.split("---", 2)
    assert len(parts) >= 3, "file does not open with a --- frontmatter block"
    return yaml.safe_load(parts[1])


def _md_section(text: str, heading: str) -> str:
    """Return the text of the markdown section that starts with `heading`
    (matched on the stripped line prefix), up to the next heading of the same
    or higher level. Fenced code blocks (```-delimited) are skipped when
    detecting headings so that `#`-prefixed shell comments inside code blocks
    are not mistaken for markdown headings. Returns '' when heading is absent."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    start = None
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.strip().startswith(heading):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    in_fence = False
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith("#"):
            cur_level = len(line) - len(line.lstrip("#"))
            if cur_level <= level:
                end = j
                break
    return "\n".join(lines[start:end])


def _tool_list(value: str) -> list[str]:
    return [tok.strip() for tok in value.split(",") if tok.strip()]


def _registry_agent(agent_id: str) -> dict:
    data = json.loads(_read(_REGISTRY))
    matches = [a for a in data["agents"] if a.get("id") == agent_id]
    assert len(matches) == 1, f"expected exactly one '{agent_id}' registry entry"
    return matches[0]


_BUILD_MODULE = None


def _build_mod():
    """Load scripts/build.py explicitly by path.

    A plain ``import build`` resolves to the ``unit_tests/build`` test package
    (which shadows the script), so we load the real module from its file path
    under a unique name and cache it.
    """
    global _BUILD_MODULE  # noqa: PLW0603
    if _BUILD_MODULE is None:
        spec = importlib.util.spec_from_file_location(
            "_leafcutter_build_script", _SCRIPTS / "build.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _BUILD_MODULE = module
    return _BUILD_MODULE


# Minimal platform config for functional build-phase tests: only claude active,
# to avoid spurious writes to gemini/, cursor/, copilot/, cline/ paths.
_CLAUDE_ONLY_CONFIG: dict = {
    "platforms": {
        "claude": True,
        "antigravity": False,
        "cursor": False,
        "copilot": False,
        "cline": False,
    },
}


# ===========================================================================
# BP-700a — unified template embeds design principles
# ===========================================================================

def test_bp700a_1_template_embeds_five_principles_and_checklist():
    # covers: BP-700a-1
    text = _read(_TEMPLATE)
    embedded = _md_section(text, "## Embedded Design Principles")
    assert embedded, "## Embedded Design Principles section not found"

    # All five design principles are embedded (headings present).
    for n in range(1, 6):
        assert f"### Principle {n} " in text, f"embedded Principle {n} heading missing"

    # The five principle topics appear (font pairing, primary colour, negative
    # space, interactive states, component-level personality).
    lowered = text.lower()
    for topic in ("font pairing", "primary colour", "negative space",
                  "interactive states", "component-level personality"):
        assert topic in lowered, f"design principle topic missing: {topic!r}"

    # The 6-question pre-write checklist is embedded with six numbered items.
    checklist = _md_section(text, "### Pre-Write Checklist")
    assert checklist, "### Pre-Write Checklist section not found"
    for n in range(1, 7):
        assert f"{n}. **" in checklist, f"pre-write checklist item {n} missing"

    # No instruction to LOAD an external frontend-design SKILL.md — the embedded
    # section explicitly forbids reading it.
    assert "Do NOT read" in embedded and "frontend-design/SKILL.md" in embedded, (
        "Embedded Design Principles must explicitly instruct NOT to read the "
        "external frontend-design SKILL.md file."
    )


def test_bp700a_1_i_legacy_skill_ignored_no_double_apply():
    # covers: BP-700a-1-i
    text = _read(_TEMPLATE)
    integration = _md_section(text, "## Optional-Skill Integration")
    assert integration, "## Optional-Skill Integration section not found"
    # The leftover legacy file must be ignored entirely.
    assert "ignore it entirely" in integration
    assert ".claude/skills/frontend-design/SKILL.md" in integration
    # No double-apply: applying the legacy file on top of embedded principles
    # would duplicate constraints (documented as applying rules "twice").
    assert "twice" in integration.lower()
    # The Constraints section reinforces the do-not-read contract.
    constraints = _md_section(text, "## Constraints")
    assert "Do NOT read `.claude/skills/frontend-design/SKILL.md`" in constraints


def test_bp700a_2_completion_report_flags_principles_applied_no_warning():
    # covers: BP-700a-2
    text = _read(_TEMPLATE)
    payload = _md_section(text, "## Response Payload")
    assert payload, "## Response Payload section not found"
    # Completion report carries design_principles_applied: true in the optional
    # skills section.
    assert "design_principles_applied: true" in payload, (
        "Completion Report must include 'design_principles_applied: true'."
    )
    # No 'frontend-design: not installed' warning anywhere in the template —
    # design is embedded, so no missing-optional-skill warning is emitted.
    assert "frontend-design: not installed" not in text, (
        "Template must not emit a 'frontend-design: not installed' warning."
    )


def test_bp700a_3_project_design_system_overrides_embedded_defaults():
    # covers: BP-700a-3
    section = _md_section(_read(_TEMPLATE), "### Project Design System Override")
    assert section, "### Project Design System Override section not found"
    # design_system values override the embedded defaults for colour + fonts.
    assert "design_system" in section
    for key in ("primary_colour", "font_heading", "font_body"):
        assert key in section, f"override key missing: {key}"
    assert "override" in section.lower(), "override precedence not stated"
    # Embedded principles still fill aspects NOT specified by the design system
    # (e.g. negative space, interactive states).
    lowered = section.lower()
    assert "not covered" in lowered or "not specified" in lowered or "only for aspects" in lowered
    assert "negative space" in lowered
    assert "interactive states" in lowered


def test_bp700a_4_howto_covers_four_design_integration_topics():
    # covers: BP-700a-4
    assert _HOWTO_DESIGN.is_file(), f"how-to guide not found at {_HOWTO_DESIGN}"
    text = _read(_HOWTO_DESIGN)
    assert _frontmatter(text).get("type") == "how-to", "doc is not a how-to"
    # Topic 1: applies design principles automatically.
    assert _md_section(text, "## How the unified agent applies design principles automatically")
    # Topic 2: override via PROJECT_CONTEXT.md.
    assert _md_section(text, "## How to override defaults via PROJECT_CONTEXT.md")
    # Topic 3: differs from the previous coder + skill split.
    assert _md_section(text, "## How the agent differs from the previous frontend-coder + skill split")
    # Topic 4: before/after example.
    assert _md_section(text, "## Before/after example")


def test_bp700a_5_architecture_diagram_shows_unified_agent_priority_8():
    # covers: BP-700a-5
    assert _ARCH.is_file(), f"architecture doc not found at {_ARCH}"
    text = _read(_ARCH)
    section = _md_section(text, "## 5. Detail View")
    assert section, "frontend-coder dispatch-topology detail section not found"
    # Component diagram (mermaid) at priority 8.
    assert "```mermaid" in section, "no mermaid diagram in the dispatch-topology section"
    assert "priority 8" in section.lower(), "diagram section does not state priority 8"
    # Relationships to PROJECT_CONTEXT.md and the optional webapp-testing skill.
    assert "PROJECT_CONTEXT" in section
    assert "webapp-testing" in section
    # No separate frontend-design box in the topology.
    assert "no longer a separate box" in section or "no longer a separate node" in section, (
        "diagram section must state frontend-design is no longer a separate box/node"
    )


# ===========================================================================
# BP-700b — dispatch behaviour (no side effects when not dispatched)
# ===========================================================================

def test_bp700b_3_agent_not_dispatched_for_non_frontend_repo():
    # covers: BP-700b-3
    # Source contract: the agent is only spawned when a trigger fires. With a
    # default_status of not_needed and file-extension DSL triggers restricted to
    # frontend extensions, a repo containing only .py/.sql files never triggers
    # the agent — so it produces no output or side effects.
    entry = _registry_agent("frontend-coder")
    criteria = entry["selection_criteria"]
    assert criteria["default_status"] == "not_needed", (
        "frontend-coder must default to not_needed so it is never dispatched "
        "unless a trigger fires."
    )
    dsl = [c for c in criteria["trigger_conditions"] if c.get("type") == "dsl"]
    assert dsl, "expected at least one dsl trigger condition"
    dsl_expr = " ".join(c["expression"] for c in dsl)
    # The DSL trigger keys off frontend extensions only — not .py or .sql.
    for ext in (".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss"):
        assert ext in dsl_expr, f"dsl trigger missing frontend extension {ext}"
    assert "*.py" not in dsl_expr, "dsl trigger must not fire on .py files"
    assert "*.sql" not in dsl_expr, "dsl trigger must not fire on .sql files"


# ===========================================================================
# BP-700c — capability & registry preservation
# ===========================================================================

def test_bp700c_1_all_skill_sections_2_to_5_preserved_in_template():
    # covers: BP-700c-1
    text = _read(_TEMPLATE)
    # Section 2 — project-context hook (design_system) preserved with precedence.
    override = _md_section(text, "### Project Design System Override")
    assert override and "design_system" in override
    assert "override" in override.lower(), "project-context precedence not preserved"
    # Section 3 — five design principles.
    for n in range(1, 6):
        assert f"### Principle {n} " in text, f"Principle {n} missing"
    # Section 4 — 6-question pre-write checklist.
    checklist = _md_section(text, "### Pre-Write Checklist")
    for n in range(1, 7):
        assert f"{n}. **" in checklist, f"checklist item {n} missing"
    # Section 5 — constraints (advisory, platform-agnostic, project-defers).
    constraints = _md_section(text, "### Design Principles Constraints")
    assert constraints, "### Design Principles Constraints section missing"
    lowered = constraints.lower()
    assert "advisory" in lowered
    assert "platform-agnostic" in lowered
    assert "defer to the project design system" in lowered


def test_bp700c_2_all_frontend_coder_capabilities_present():
    # covers: BP-700c-2
    text = _read(_TEMPLATE)
    # Stop-and-Ask rules for .py and .sql.
    assert _md_section(text, "## Stop-and-Ask Rule for Python")
    assert _md_section(text, "## Stop-and-Ask Rule for SQL")
    # Contract-Aware Mode (Agent Contracts parsing).
    contract = _md_section(text, "## Contract-Aware Mode")
    assert contract and "## Agent Contracts" in contract
    # Pre-flight reads.
    assert _md_section(text, "## Pre-Flight Reads")
    # File-size limit (300 components / 500 stylesheets).
    filesize = _md_section(text, "## File-Size Limit")
    assert filesize and "300" in filesize and "500" in filesize
    # Research delegation via research-agent.
    research = _md_section(text, "## Research Delegation")
    assert research and "research-agent" in research
    # Completion report / response payload.
    assert _md_section(text, "## Response Payload")
    # Sign-off artifact checklist (frontmatter default_artifact_checklist).
    fm = _frontmatter(text)
    checklist = fm.get("default_artifact_checklist", [])
    for item in ("code_implemented", "ui_verified", "design_principles_applied"):
        assert item in checklist, f"default_artifact_checklist missing {item}"


def test_bp700c_2_i_framework_agnostic_constraint_explicit():
    # covers: BP-700c-2-i
    text = _read(_TEMPLATE)
    constraints = _md_section(text, "### Design Principles Constraints")
    lowered = constraints.lower()
    # Platform-agnostic across React, Vue, Svelte, and plain HTML/CSS.
    assert "platform-agnostic" in lowered
    for framework in ("react", "vue", "svelte"):
        assert framework in lowered, f"framework not named in constraints: {framework}"
    assert "html/css" in lowered or "plain html" in lowered
    # Must not import a framework the project does not already use.
    assert "do not import" in lowered
    assert "project does not already use" in lowered
    # Detect the project's framework from existing files before writing code.
    assert "existing stylesheets" in lowered or "package.json" in lowered


def test_bp700c_3_webapp_testing_separate_optional_with_antigravity_override():
    # covers: BP-700c-3
    section = _md_section(_read(_TEMPLATE), "## Optional-Skill Integration")
    assert section, "## Optional-Skill Integration section not found"
    # File-existence detection (unchanged), not a registry lookup.
    assert ".claude/skills/webapp-testing/SKILL.md" in section
    assert "file existence" in section.lower()
    # Behaviour when installed vs not installed.
    assert "If installed" in section
    assert "If not installed" in section
    # Antigravity environment override preserved.
    assert "ANTIGRAVITY" in section
    # webapp-testing stays a separate skill (detected, not embedded/merged).
    assert "skip the webapp-testing skill" in section.lower()


def test_bp700c_4_registry_preserves_metadata_and_drops_frontend_design():
    # covers: BP-700c-4
    entry = _registry_agent("frontend-coder")
    # Preserved metadata.
    assert entry["id"] == "frontend-coder"
    assert entry["tier"] == "phase"
    assert entry["priority"] == 8
    assert entry["owns_file_extensions"] == [
        ".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss",
    ]
    assert entry["spawn_allowlist"] == ["research-agent"]
    assert entry["requires_verification"] is True
    assert entry["category"] == "implementation"
    # skills_used drops frontend-design, keeps webapp-testing.
    assert "frontend-design" not in entry["skills_used"], (
        "skills_used must not list frontend-design (design is embedded)."
    )
    assert "webapp-testing" in entry["skills_used"]
    # skills_invoked drops frontend-design, keeps webapp-testing + signoff (conditional).
    invoked_ids = {s["skill_id"] for s in entry["skills_invoked"]}
    assert "frontend-design" not in invoked_ids
    assert "webapp-testing" in invoked_ids
    assert "signoff" in invoked_ids
    for s in entry["skills_invoked"]:
        if s["skill_id"] in ("webapp-testing", "signoff"):
            assert s["mode"] == "conditional", (
                f"{s['skill_id']} must be invoked conditionally"
            )


def test_bp700c_5_reference_doc_catalogues_preserved_capabilities():
    # covers: BP-700c-5
    assert _REFERENCE.is_file(), f"reference doc not found at {_REFERENCE}"
    text = _read(_REFERENCE)
    assert _frontmatter(text).get("type") == "reference", "doc is not a reference"
    # Design principles carried forward (all five).
    principles = _md_section(text, "## 1. Design Principles")
    assert principles
    for n in range(1, 6):
        assert f"### Principle {n} " in principles, f"reference missing Principle {n}"
    # Behavioural rules carried forward from the old agent.
    assert _md_section(text, "## 3. Behavioral Rules")
    # webapp-testing integration status (still optional, same detection).
    webapp = _md_section(text, "## 4. webapp-testing Integration Status")
    assert webapp and "file-existence detection" in webapp.lower()
    # Comparison table: old artifact/source → new location.
    comparison = _md_section(text, "## 6. Comparison Table")
    assert comparison and "New location" in comparison
    # Table has real data rows mapping old → new.
    data_rows = [ln for ln in comparison.splitlines()
                 if ln.strip().startswith("|") and "frontend-coder.md" in ln]
    assert len(data_rows) >= 5, (
        f"comparison table should map many rules old→new; got {len(data_rows)} rows"
    )


# ===========================================================================
# BP-700d — build-time migration & wiring
# ===========================================================================

def test_bp700d_1_build_migration_overwrites_template_and_reports(tmp_path, capsys):
    # covers: BP-700d-1
    # build.py overwrites .claude/agents/frontend-coder.md with the unified
    # template (embedded principles), does not regenerate the deprecated
    # frontend-design skill, needs no manual edits, and reports the migration.
    _migrate_skills_config = _build_mod()._migrate_skills_config
    from build_phases import build_agents, build_skills

    # Simulate an existing (upgrade) install: an old agent template on disk.
    old_agent = tmp_path / "agents" / "frontend-coder.md"
    old_agent.parent.mkdir(parents=True)
    old_agent.write_text("OLD TEMPLATE — no embedded design principles\n", encoding="utf-8")

    # A skills_config.json still listing the deprecated frontend-design skill.
    cfg_dir = tmp_path / ".claude"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "skills_config.json"
    cfg_path.write_text(
        json.dumps({"frontend": {"optional_skills": ["webapp-testing", "frontend-design"]}}),
        encoding="utf-8",
    )

    # Run the migration + deploy phases (no manual edits required).
    _migrate_skills_config(cfg_path, tmp_path, dry_run=False)
    build_agents(tmp_path, _CLAUDE_ONLY_CONFIG, dry_run=False, force=True)
    build_skills(tmp_path, _CLAUDE_ONLY_CONFIG, dry_run=False, force=True)

    # The agent template is overwritten with the unified (embedded) template.
    new_agent = (tmp_path / "agents" / "frontend-coder.md").read_text(encoding="utf-8")
    assert "Embedded Design Principles" in new_agent, (
        "build_agents must overwrite frontend-coder.md with the unified template."
    )
    assert "OLD TEMPLATE" not in new_agent, "old template content was not overwritten"

    # The deprecated frontend-design skill is not (re)deployed.
    assert not (tmp_path / "skills" / "frontend-design").exists(), (
        "build_skills must not deploy the deprecated frontend-design skill."
    )

    # The migration is reported in the build output.
    out = capsys.readouterr().out
    assert "Removed deprecated optional_skills" in out and "frontend-design" in out, (
        "build.py must report the skills_config.json migration."
    )


def test_bp700d_1_i_fresh_install_no_error_no_skill_dir(tmp_path):
    # covers: BP-700d-1-i
    # Fresh install (no prior frontend-design dir, no prior agent template):
    # unified template is deployed, no error about a missing dir to remove,
    # and the frontend-design skill directory is NOT created.
    from build_phases import build_agents, build_skills

    written_agents = build_agents(tmp_path, _CLAUDE_ONLY_CONFIG, dry_run=False, force=True)
    written_skills = build_skills(tmp_path, _CLAUDE_ONLY_CONFIG, dry_run=False, force=True)
    assert written_agents > 0 and written_skills > 0, "build phases wrote nothing"

    assert (tmp_path / "agents" / "frontend-coder.md").is_file(), (
        "unified frontend-coder template not deployed on fresh install"
    )
    assert not (tmp_path / "skills" / "frontend-design").exists(), (
        "fresh install must NOT create the deprecated frontend-design skill dir"
    )


def test_bp700d_1_ii_upgrade_preserves_project_context(tmp_path):
    # covers: BP-700d-1-ii
    # An upgrade must never modify/delete a customised PROJECT_CONTEXT.md — the
    # unified agent reads the custom design_system values from it.
    _migrate_skills_config = _build_mod()._migrate_skills_config
    from build_phases import build_agents, build_skills

    pc_dir = tmp_path / ".agents" / "agents" / "frontend-coder"
    pc_dir.mkdir(parents=True)
    pc_path = pc_dir / "PROJECT_CONTEXT.md"
    original = (
        "## design_system\n\n"
        'primary_colour: "#E11D48"\n'
        'font_heading: "Montserrat"\n'
    )
    pc_path.write_text(original, encoding="utf-8")

    cfg_dir = tmp_path / ".claude"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "skills_config.json"
    cfg_path.write_text(
        json.dumps({"frontend": {"optional_skills": ["webapp-testing", "frontend-design"]}}),
        encoding="utf-8",
    )

    _migrate_skills_config(cfg_path, tmp_path, dry_run=False)
    build_agents(tmp_path, _CLAUDE_ONLY_CONFIG, dry_run=False, force=True)
    build_skills(tmp_path, _CLAUDE_ONLY_CONFIG, dry_run=False, force=True)

    assert pc_path.is_file(), "PROJECT_CONTEXT.md was deleted during upgrade"
    assert pc_path.read_text(encoding="utf-8") == original, (
        "PROJECT_CONTEXT.md custom design_system values were modified during upgrade"
    )


def test_bp700d_2_onboard_wizard_drops_frontend_design_keeps_webapp_testing():
    # covers: BP-700d-2
    assert _ONBOARD.is_file(), f"onboard wizard template not found at {_ONBOARD}"
    text = _read(_ONBOARD)
    # The wizard still lists webapp-testing as a frontend optional skill.
    assert "webapp-testing" in text, "onboard wizard no longer offers webapp-testing"
    # The wizard no longer offers frontend-design as a separate installable skill.
    assert "frontend-design" not in text, (
        "onboard wizard must NOT offer frontend-design as a separate installable skill."
    )


def test_bp700d_3_migrate_skills_config_removes_frontend_design(tmp_path):
    # covers: BP-700d-3
    _migrate_skills_config = _build_mod()._migrate_skills_config

    cfg = tmp_path / ".claude" / "skills_config.json"
    cfg.parent.mkdir(parents=True)
    payload = {
        "frontend": {
            "optional_skills": ["webapp-testing", "frontend-design"],
            "project_context_path": ".agents/agents/frontend-coder/PROJECT_CONTEXT.md",
            "test_command": "npm test",
        },
        "other_section": {"keep": "me"},
    }
    cfg.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _migrate_skills_config(cfg, tmp_path, dry_run=False)

    updated = json.loads(cfg.read_text(encoding="utf-8"))
    # frontend-design removed; webapp-testing retained.
    assert updated["frontend"]["optional_skills"] == ["webapp-testing"]
    # Other frontend keys preserved unchanged.
    assert updated["frontend"]["project_context_path"] == (
        ".agents/agents/frontend-coder/PROJECT_CONTEXT.md"
    )
    assert updated["frontend"]["test_command"] == "npm test"
    # Unrelated sections untouched.
    assert updated["other_section"] == {"keep": "me"}


def test_bp700d_3_migrate_skills_config_noop_when_absent(tmp_path):
    # covers: BP-700d-3
    # When frontend-design is not listed, the frontend section is not changed.
    _migrate_skills_config = _build_mod()._migrate_skills_config

    cfg = tmp_path / ".claude" / "skills_config.json"
    cfg.parent.mkdir(parents=True)
    original = json.dumps(
        {"frontend": {"optional_skills": ["webapp-testing"]}}, indent=2
    )
    cfg.write_text(original, encoding="utf-8")

    _migrate_skills_config(cfg, tmp_path, dry_run=False)

    assert cfg.read_text(encoding="utf-8") == original, (
        "config with no frontend-design must be left byte-identical (no-op)."
    )


def test_bp700d_3_legacy_skill_marked_deprecated_so_not_deployed():
    # covers: BP-700d-3
    # The deploy-time exclusion that keeps frontend-design out of installs is the
    # deprecated:true flag on its SKILL.md frontmatter (read by build_skills).
    assert _LEGACY_SKILL.is_file(), f"legacy skill not found at {_LEGACY_SKILL}"
    fm = _frontmatter(_read(_LEGACY_SKILL))
    assert fm.get("name") == "frontend-design"
    assert fm.get("deprecated") is True, (
        "frontend-design/SKILL.md must carry deprecated: true so build_skills "
        "skips deploying it."
    )


def test_bp700d_4_upgrade_howto_documents_migration_path():
    # covers: BP-700d-4
    assert _HOWTO_UPGRADE.is_file(), f"upgrade how-to not found at {_HOWTO_UPGRADE}"
    text = _read(_HOWTO_UPGRADE)
    assert _frontmatter(text).get("type") == "how-to", "doc is not a how-to"
    lowered = text.lower()
    # What changes when you run build.py.
    assert _md_section(text, "## What changed")
    assert "build.py" in text
    # Files removed / updated.
    assert ".claude/skills/frontend-design/" in text, "removed-file path not documented"
    assert ".claude/agents/frontend-coder.md" in text, "updated agent file not documented"
    assert "skills_config.json" in text, "updated config file not documented"
    # No manual steps.
    assert "no manual steps are required" in lowered or "no manual steps" in lowered
    # Verification.
    assert _md_section(text, "## Verifying the migration succeeded")
    # Rollback.
    assert _md_section(text, "## Rollback instructions")
