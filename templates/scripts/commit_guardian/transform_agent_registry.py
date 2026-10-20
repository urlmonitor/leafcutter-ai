"""
MODULE: leafcutter/scripts/commit_guardian/transform_agent_registry.py
GOAL: Pre-stage transformer that regenerates the derived fields
      (``skills_invoked`` from the frontmatter ``skills``
      declaration -- the retired ``skills_used`` is never written and is dropped
      from any record that carries it -- and ``spawn_allowlist`` from the frontmatter ``spawn_allowlist``
      declaration) of config/agent_registry.json from each agent template, and
      re-stages the registry when it changed.
BUSINESS CONTEXT: AR-300c made the template frontmatter the one source of truth
      for an agent's abilities; the registry's ability fields are a DERIVED
      copy. The build compiles prompts from the declarations and only REPORTS a
      copy that disagrees (it never writes the package source tree), so
      something has to keep the copy current. This hook does it at commit time,
      so a declaration edit and its derived copy land in the same commit
      (user decision, BrainCandy 2026-10-09).
ARCHITECTURE: Modelled on transform_doc_index.py. ``main(argv)`` resolves the
      package root (``--package-root DIR`` when given, otherwise the git
      toplevel), reads the registry and every agent's template, regenerates the
      ability field through the sibling ``_agent_ability_sync`` module and each
      templated agent's ``spawn_allowlist`` from its declaration (macro kept as
      written; an absent declaration gives ``[]``), and writes the registry only
      when its parsed content changed. It changes no other field (``spawned_by``
      and ``is_ticket_phase`` stay hand-authored) and no template-less record. With ``--package-root`` it does
      no git staging (used by tests and tooling); without it, it ``git add``s
      the registry after a write. Exits 0 always (fail-open contract -- never
      blocks a commit). ``_agent_ability_sync.py`` sits in this directory,
      which the build copies wholesale, so the deployed hook finds it with no
      deploy-manifest entry.

====================================================================
DECISION HISTORY
====================================================================
- 2026-10-09 [python-coder/AR-300c-3]: Created, registered beside
  transform-doc-index in commit_guardian.json (same tier, language, stages,
  pass_filenames and change_set_source). The registry copy is regenerated here
  instead of by the build, which only reports a disagreement. (#AR-300c-3)
- 2026-10-09 [python-coder/AR-300c-5]: Also regenerates ``spawn_allowlist`` from
  each template's declaration (user decision: the registry copy of the sub-agent
  permission is derived exactly like the abilities). (#AR-300c-5-ii)
- 2026-10-12 [python-coder/AR-400e-2]: Regenerates ONLY ``skills_invoked`` (with
  ``provided_by``) and drops the retired ``skills_used`` from every templated
  record; byte-stable and idempotent. (#AR-400e-2)
====================================================================
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _agent_ability_sync import (  # noqa: E402
    MalformedDeclarationError,
    declared_spawn,
    dump_registry,
    frontmatter_of,
    normalize_declared,
    regenerate_record,
    regenerate_spawn,
)

_TAG = "[transform-agent-registry]"
_REGISTRY_REL = Path("config") / "agent_registry.json"


def _warn(message: str) -> None:
    """Print a WARNING line to stderr (hook diagnostics never go to stdout)."""
    print(f"{_TAG} WARNING: {message}", file=sys.stderr)


def _resolve_repo_root() -> Path:
    """Return the git toplevel, falling back to the CWD with a WARNING."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
    except OSError as exc:
        _warn(f"git rev-parse failed: {exc}")
    else:
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    _warn(f"could not determine repo root via git, falling back to cwd: {Path.cwd()}")
    return Path.cwd()


def _restage(registry_path: Path) -> None:
    """Re-stage the regenerated registry via ``git add`` (failures are warned, never raised)."""
    try:
        result = subprocess.run(["git", "add", str(registry_path)], capture_output=True, check=False)
    except OSError as exc:
        _warn(f"git add failed for {registry_path}: {exc}")
        return
    if result.returncode != 0:
        _warn(f"git add exited with code {result.returncode}")


def _declaration_for(root: Path, agent: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]] | None:
    """Return the agent's declared ``(grants, sub-agents)`` from its template, or None to leave the record alone."""
    template_path = agent.get("template_path")
    path = root / template_path if template_path else None
    if path is None or not path.is_file():
        return None
    import yaml  # noqa: PLC0415 - lazy: the caller (``main``) has already proven PyYAML imports

    try:
        fm = frontmatter_of(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        _warn(f"cannot read declaration from {path}: {exc}")
        return None
    if fm is None:
        return None
    try:
        return normalize_declared(fm.get("skills")), declared_spawn(fm)
    except MalformedDeclarationError as exc:
        _warn(f"agent '{agent.get('id')}' ({path}) has a malformed declaration; its registry record is left as is: {exc}")
        return None


def regenerate(root: Path, data: dict[str, Any]) -> None:
    """Regenerate every templated agent's derived fields (abilities, sub-agents) in ``data`` in place."""
    for agent in data.get("agents") or []:
        declaration = _declaration_for(root, agent)
        if declaration is not None:
            regenerate_record(agent, declaration[0])
            regenerate_spawn(agent, declaration[1])


def _write_registry(registry_path: Path, data: dict[str, Any]) -> bool:
    """Write ``data`` to the registry; return False (after a WARNING) when the write fails."""
    try:
        registry_path.write_bytes(dump_registry(data).encode("utf-8"))
    except OSError as exc:
        _warn(f"failed to write {registry_path}: {exc}")
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Entry point for the agent-registry regeneration hook; always returns 0 (fail-open)."""
    parser = argparse.ArgumentParser(description="Regenerate the agent registry's ability fields.")
    parser.add_argument("--package-root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.package_root.resolve() if args.package_root else _resolve_repo_root()
    registry_path = root / _REGISTRY_REL
    if not registry_path.is_file():
        return 0
    try:
        original = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _warn(f"cannot read {registry_path}: {exc}")
        return 0
    try:
        import yaml  # noqa: F401, PLC0415 - fail-open probe: templates cannot be read without PyYAML
    except ImportError as exc:
        _warn(f"PyYAML is unavailable, registry left unchanged: {exc}")
        return 0
    data = json.loads(json.dumps(original))
    regenerate(root, data)
    if data == original or not _write_registry(registry_path, data):
        return 0
    if args.package_root is None:
        _restage(registry_path)
    print(f"{_TAG} Regenerated agent ability fields in {registry_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        # Fail-open outermost boundary: an unexpected error must never block a commit.
        _warn(f"unexpected error, skipping: {exc}")
        sys.exit(0)
