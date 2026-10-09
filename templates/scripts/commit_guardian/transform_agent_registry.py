"""
MODULE: leafcutter/scripts/commit_guardian/transform_agent_registry.py
GOAL: Pre-stage transformer that regenerates the ability fields
      (``skills_used`` / ``skills_invoked``) of config/agent_registry.json from
      each agent template's frontmatter ``skills`` declaration, and re-stages
      the registry when it changed.
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
      ability fields through the sibling ``_agent_ability_sync`` module (shared
      with the one-shot migration, so both write the identical record), and
      writes the registry only when its parsed content changed. It changes no
      other field and no other agent's record. With ``--package-root`` it does
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
====================================================================
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _agent_ability_sync import declared_entries, dump_registry, regenerate_record  # noqa: E402

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


def _declaration_for(root: Path, agent: dict[str, Any]) -> list[dict[str, str]] | None:
    """Return the agent's declared grants from its template, or None to leave the record alone."""
    template_path = agent.get("template_path")
    path = root / template_path if template_path else None
    if path is None or not path.is_file():
        return None
    try:
        return declared_entries(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        _warn(f"cannot read declaration from {path}: {exc}")
        return None


def regenerate(root: Path, data: dict[str, Any]) -> None:
    """Regenerate every templated agent's ability fields in ``data`` in place."""
    for agent in data.get("agents") or []:
        entries = _declaration_for(root, agent)
        if entries is not None:
            regenerate_record(agent, entries)


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
