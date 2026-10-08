"""
MODULE: agent_ability_gate
GOAL: Wire the agent-ability verdict into the build so a disagreement between
    an agent's own declaration and the central registry, or a declared ability
    that resolves to no installed skill, makes the build refuse.
BUSINESS CONTEXT: AR-300c-3 / AR-300c-3-i. The registry's ability fields are a
    derived copy of each template's frontmatter ``skills`` declaration. A
    verdict nobody acts on is the phantom-done shape this repo exists to
    prevent, so the build (ADR-050) treats any finding as a registry error and
    exits non-zero, naming the agent and BOTH ability sets (or, for an
    unresolvable ability, the agent, the ability and where it was looked for).
ARCHITECTURE: ``refuse_on_ability_findings`` (called from
    ``build_main_helpers._run_validation_guards``, so it runs on a normal build
    AND ``--validate-only``) prints each finding as a build error and returns
    the exit code; ``ability_errors(package_root, config)`` computes them. It
    reads ``config/agent_registry.json`` and every non-underscore
    ``templates/agents/*.md`` frontmatter (the I/O boundary — the comparison
    itself lives in ``agent_ability_verdict``), runs ``verify_abilities`` and
    returns one error string per finding. A package without a registry
    file or an agents template directory has nothing to verify and returns [].
    A package that HAS both but yields an empty verdict population returns an
    error, never a clean pass. Build-engine module under ``scripts/``; no
    deploy-manifest entry needed (same as ``registry_validator``).

DECISION HISTORY
- 2026-10-08 [python-coder/AR-300c-3]: Created. Called from
  ``build_main_helpers._run_validation_guards`` (build.py is far over the
  file-size limit and the ratchet forbids adding to it) so the real build.py
  refuses; ``project_root`` is the
  package's parent directory (the consumer layout) and the project-local skills
  directory comes from the declared ``output_root`` (config, then the
  project's skills_config, then ``.leafcutter``). (#AR-300c-3)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agent_ability_verdict import describe_finding, verify_abilities
from build_colors import error as _error
from template_compiler import parse_frontmatter

_log = logging.getLogger(__name__)
_DEFAULT_OUTPUT_ROOT = ".leafcutter"


def _read_json(path: Path) -> Any:
    """Read a JSON file, logging and re-raising on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("cannot read %s: %s", path, exc)
        raise


def _output_root_name(config: dict[str, Any] | None, project_root: Path) -> str:
    """Return the declared output root: config, then the project's skills_config, then default."""
    if config and config.get("output_root"):
        return str(config["output_root"])
    cfg_path = project_root / ".claude" / "skills_config.json"
    if cfg_path.is_file():
        return str(_read_json(cfg_path).get("output_root") or _DEFAULT_OUTPUT_ROOT)
    return _DEFAULT_OUTPUT_ROOT


def _agent_id_for(template: Path, registry_agents: list[dict[str, Any]]) -> str:
    """Resolve a template's agent id via the registry's template_path (stem fallback)."""
    for agent in registry_agents:
        if agent.get("template_path") and Path(agent["template_path"]).stem == template.stem:
            return agent["id"]
    return template.stem


def _read_declarations(agents_dir: Path, registry_agents: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """Return agent id -> frontmatter ``skills`` entries for every template that declares any."""
    declarations: dict[str, list[Any]] = {}
    for template in sorted(agents_dir.glob("*.md")):
        if template.name.startswith("_"):
            continue
        try:
            fm, _body = parse_frontmatter(template.read_text(encoding="utf-8"))
        except OSError as exc:
            _log.warning("cannot read agent template %s: %s", template, exc)
            raise
        if fm.get("skills"):
            declarations[_agent_id_for(template, registry_agents)] = fm["skills"]
    return declarations


def ability_errors(package_root: Path, config: dict[str, Any] | None = None) -> list[str]:
    """Return one build error per ability finding for the package at ``package_root``.

    Args:
        package_root: The leafcutter package root (holds ``config/`` and ``templates/``).
        config: Optional merged build config; its ``output_root`` locates project-local skills.

    Returns:
        Error strings (empty when declarations and registry agree and every
        declared ability resolves, or when the package has no registry/agents to verify).
    """
    registry_path = package_root / "config" / "agent_registry.json"
    agents_dir = package_root / "templates" / "agents"
    if not registry_path.is_file() or not agents_dir.is_dir():
        return []
    registry_agents = _read_json(registry_path).get("agents") or []
    declarations = _read_declarations(agents_dir, registry_agents)
    project_root = package_root.parent
    try:
        verdict = verify_abilities(
            declarations,
            registry_agents,
            packaged_skills_root=package_root / "templates" / "skills",
            project_root=project_root,
            output_root_name=_output_root_name(config, project_root),
        )
    except ValueError as exc:
        return [f"[abilities] cannot verify agent abilities: {exc}"]
    return [f"[abilities] {describe_finding(f)}" for f in verdict["findings"]]


def refuse_on_ability_findings(package_root: Path, config: dict[str, Any], dry_run: bool) -> int:
    """Print every ability finding as a build error and return the exit code.

    Args:
        package_root: The leafcutter package root.
        config: Merged build config.
        dry_run: When True, findings are printed but non-fatal (mirrors the
            registry-error handling in ``build._handle_registry_errors``).

    Returns:
        1 when the build must refuse, 0 to continue.
    """
    errors = ability_errors(package_root, config)
    for err in errors:
        _error(err)
    return 1 if errors and not dry_run else 0
