"""
MODULE: agent_ability_gate
GOAL: Wire the agent-ability verdict into the build: REPORT a registry copy
    that disagrees with an agent's own declaration and carry on, but REFUSE when
    a declared ability resolves to no installed skill.
BUSINESS CONTEXT: AR-300c-3 / AR-300c-3-i. The registry's ability fields are a
    derived copy of each template's frontmatter ``skills`` declaration, which
    the build compiles prompts from. A verdict nobody acts on is the
    phantom-done shape this repo exists to prevent, so a disagreement is
    printed naming the agent and BOTH ability sets. It does not refuse (user
    decision, BrainCandy 2026-10-09: the pre-commit transform hook regenerates
    the copy, and the build never writes the package source tree). An
    unresolvable ability still refuses, naming the agent, the ability and where
    it was looked for.
ARCHITECTURE: ``refuse_on_ability_findings`` (called from
    ``build_main_helpers._run_validation_guards``, so it runs on a normal build
    AND ``--validate-only``) prints comparison findings as warnings, refusing
    findings as build errors, and returns the exit code.
    ``split_ability_findings(package_root, config)`` returns the
    ``(reported, refusing)`` message lists (the split is keyed on
    ``agent_ability_verdict.REPORT_ONLY_KINDS``); ``ability_errors`` returns
    both lists joined. It reads ``config/agent_registry.json`` and every
    non-underscore ``templates/agents/*.md`` frontmatter (the I/O boundary — the
    comparison itself lives in ``agent_ability_verdict``) and runs
    ``verify_abilities``. A package without a registry file or an agents
    template directory has nothing to verify. A package that HAS both but
    yields an empty verdict population is a refusing finding, never a clean
    pass. Build-engine module under ``scripts/``; no deploy-manifest entry
    needed (same as ``registry_validator``).

DECISION HISTORY
- 2026-10-08 [python-coder/AR-300c-3]: Created. Called from
  ``build_main_helpers._run_validation_guards`` (build.py is far over the
  file-size limit and the ratchet forbids adding to it) so the real build.py
  refuses; ``project_root`` is the
  package's parent directory (the consumer layout) and the project-local skills
  directory comes from the declared ``output_root`` (config, then the
  project's skills_config, then ``.leafcutter``). (#AR-300c-3)
- 2026-10-09 [python-coder/AR-300c-3]: Split findings into report-only
  (comparison kinds) and refusing (unresolved, empty population). The build now
  reports and continues on a disagreeing registry copy, per the user decision
  above; ``_run_validation_guards`` keeps its name and signature.
  (#AR-300c-3)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agent_ability_verdict import REPORT_ONLY_KINDS, describe_finding, verify_abilities
from build_colors import error as _error
from build_colors import warn as _warn
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


def _verdict_findings(package_root: Path, config: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Return ``(findings, cannot_verify)`` for the package at ``package_root``.

    ``cannot_verify`` holds the single refusing message produced when the
    verdict population is empty (a verdict over nothing must not read as clean).
    A package without a registry file or an agents template directory has
    nothing to verify and yields ``([], [])``.
    """
    registry_path = package_root / "config" / "agent_registry.json"
    agents_dir = package_root / "templates" / "agents"
    if not registry_path.is_file() or not agents_dir.is_dir():
        return [], []
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
        return [], [f"[abilities] cannot verify agent abilities: {exc}"]
    return verdict["findings"], []


def split_ability_findings(package_root: Path, config: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    """Split the package's ability findings into ``(reported, refusing)`` message lists.

    ``reported`` holds the comparison findings (the registry copy disagrees with a
    declaration): the build prints them and continues. ``refusing`` holds every
    other finding -- an unresolvable declared ability, or an empty verdict
    population -- which makes the build exit non-zero.
    """
    findings, cannot_verify = _verdict_findings(package_root, config)
    reported = [f"[abilities] {describe_finding(f)}" for f in findings if f["kind"] in REPORT_ONLY_KINDS]
    refusing = [f"[abilities] {describe_finding(f)}" for f in findings if f["kind"] not in REPORT_ONLY_KINDS]
    return reported, refusing + cannot_verify


def ability_errors(package_root: Path, config: dict[str, Any] | None = None) -> list[str]:
    """Return one message per ability finding (reported AND refusing) for ``package_root``.

    Args:
        package_root: The leafcutter package root (holds ``config/`` and ``templates/``).
        config: Optional merged build config; its ``output_root`` locates project-local skills.

    Returns:
        Message strings (empty when declarations and registry agree and every
        declared ability resolves, or when the package has no registry/agents to verify).
    """
    reported, refusing = split_ability_findings(package_root, config)
    return reported + refusing


def refuse_on_ability_findings(package_root: Path, config: dict[str, Any], dry_run: bool) -> int:
    """Report registry-copy disagreements, print refusing findings as errors, return the exit code.

    A registry copy that disagrees with the declarations is REPORTED (a warning
    naming the agent and both ability sets) and never refuses; the build
    compiles from the declarations either way and never writes the package
    source tree. Any other finding refuses.

    Args:
        package_root: The leafcutter package root.
        config: Merged build config.
        dry_run: When True, refusing findings are printed but non-fatal (mirrors
            the registry-error handling in ``build._handle_registry_errors``).

    Returns:
        1 when the build must refuse, 0 to continue.
    """
    reported, refusing = split_ability_findings(package_root, config)
    for line in reported:
        _warn(line)
    for err in refusing:
        _error(err)
    return 1 if refusing and not dry_run else 0
