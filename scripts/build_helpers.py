"""
MODULE: build_helpers
GOAL: Optional build steps — manifest writing, diagram update, doc seeding, and shim install.
BUSINESS CONTEXT: Extracted from build.py to keep that module under the 400-line
    limit. These helpers are invoked by main() in build.py when the
    corresponding CLI flags (--update-diagrams, --seed-docs) are set or after
    the build phases complete (manifest write, shim install). They are standalone
    functions with no shared state; moving them here requires only an import
    change in build.py.
ARCHITECTURE: Each function is self-contained and safe to import independently.
    All exceptions are caught and surfaced as printed warnings — helpers never
    abort the build. write_build_manifest supports both Direction A (template
    hashes) and Direction B (output_mappings) manifest sections.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _compute_output_mappings(
    package_root: Path,
    target_root: Path,
    config: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Compute expected output hashes for all template to output file mappings.

    For each template that build.py renders and writes to the target project,
    computes the SHA-256 of what build.py *actually would write* (i.e. after
    template compilation/injection) and records the template path alongside it.
    This gives check_output_drift.py a ground truth to compare against
    on-disk output files.

    Covers the same template directories that build_phases.py writes:
    - agents:    templates/agents/*.md  to  .claude/agents/
    - skills:    templates/skills/**/* to  .claude/skills/
    - workflows: templates/workflows/*.md to .agents/workflows/
    - rules:     templates/rules/*.md  to  .agents/rules/

    commit-guardian, doc-compliance, and ticket-lifecycle templates are
    intentionally excluded because those output files are maintained by the
    project owner (not agent-authored) and are therefore not subject to the
    edit-templates-not-built-copies guardrail.

    Args:
        package_root: Root of the leafcutter package.
        target_root: Root of the target project (where outputs are written).
        config: Merged config dict used for placeholder injection.

    Returns:
        Dict mapping output-relative-path strings to dicts with keys
        ``template`` (template rel-path) and ``expected_output_hash`` (sha256).
    """
    scripts_dir = package_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from template_compiler import (  # type: ignore[import]
        compile_agent_template,
        compile_skill_template,
        inject_config,
        _load_registry,
    )

    templates_dir = package_root / "templates"
    registry_path = package_root / "config" / "agent_registry.json"
    agents_list = _load_registry(registry_path)
    skills_root = templates_dir / "skills" if (templates_dir / "skills").exists() else None
    repo_root = package_root.parent  # package_root is one level below repo root

    mappings: dict[str, dict[str, str]] = {}

    def _add(template_path: Path, output_path: Path, content: str) -> None:
        """Record an output mapping entry (relative paths, expected hash).

        Args:
            template_path: Absolute path to the source template file.
            output_path: Absolute path to the built output file.
            content: Rendered output content string (post template compilation).
        """
        tpl_key = template_path.relative_to(repo_root).as_posix()
        out_key = output_path.relative_to(repo_root).as_posix()
        mappings[out_key] = {
            "template": tpl_key,
            "expected_output_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }

    # --- agents ---
    agents_tpl_dir = templates_dir / "agents"
    if agents_tpl_dir.is_dir():
        for tpl in sorted(agents_tpl_dir.glob("*.md")):
            if tpl.name.startswith("_"):
                continue
            compiled = compile_agent_template(
                tpl, config,
                registry_path=registry_path,
                agents=agents_list,
                skills_root=skills_root,
            )
            output = target_root / ".claude" / "agents" / tpl.name
            _add(tpl, output, compiled)

    # --- skills (markdown only) ---
    skills_tpl_dir = templates_dir / "skills"
    if skills_tpl_dir.is_dir():
        for tpl in sorted(skills_tpl_dir.rglob("*.md")):
            if not tpl.is_file():
                continue
            rel = tpl.relative_to(skills_tpl_dir)
            compiled = compile_skill_template(tpl, config)
            output = target_root / ".claude" / "skills" / rel
            _add(tpl, output, compiled)

    # --- workflows ---
    workflows_tpl_dir = templates_dir / "workflows"
    if workflows_tpl_dir.is_dir():
        for tpl in sorted(workflows_tpl_dir.glob("*.md")):
            text = inject_config(tpl.read_text(encoding="utf-8"), config)
            output = target_root / ".agents" / "workflows" / tpl.name
            _add(tpl, output, text)

    # --- rules ---
    rules_tpl_dir = templates_dir / "rules"
    if rules_tpl_dir.is_dir():
        for tpl in sorted(rules_tpl_dir.glob("*.md")):
            text = inject_config(tpl.read_text(encoding="utf-8"), config)
            output = target_root / ".agents" / "rules" / tpl.name
            _add(tpl, output, text)

    return mappings


def write_build_manifest(
    package_root: Path,
    dry_run: bool = False,
    target_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Write .build_manifest.json with template hashes and expected output hashes.

    The ``templates`` section records the SHA-256 content hash of every .md file
    under ``package_root/templates/agents/`` (backward-compatible with
    check_build_drift.py — Direction A detection).

    The ``output_mappings`` section records, for each template to output pair managed
    by build.py, the expected SHA-256 of what build.py would write to the output
    path given the current template and config. check_output_drift.py reads this
    section to detect Direction B drift (direct edits to built outputs).

    When ``target_root`` and ``config`` are both provided, output_mappings are
    computed and written. When either is absent, the section is omitted (the
    manifest degrades gracefully to the ticket-37 format).

    Args:
        package_root: Root of the leafcutter package (the directory
            containing ``templates/`` and ``scripts/``).
        dry_run: When True, prints what would be written but writes nothing.
        target_root: Root of the target project. Required for output_mappings.
        config: Merged config dict used for placeholder injection. Required
            for output_mappings.
    """
    templates_dir = package_root / "templates" / "agents"
    manifest_path = package_root / ".build_manifest.json"

    if not templates_dir.is_dir():
        print(f"  [MANIFEST] templates/agents/ not found at {templates_dir}; skipping.")
        return

    # --- Direction A: template hashes (flat dict, backward-compatible) ---
    template_hashes: dict[str, str] = {}
    repo_root = package_root.parent  # leafcutter/ is one level below repo root
    for tpl_path in sorted(templates_dir.rglob("*.md")):
        key = tpl_path.relative_to(repo_root).as_posix()
        template_hashes[key] = hashlib.sha256(tpl_path.read_bytes()).hexdigest()

    # --- Direction B: expected output hashes (new output_mappings section) ---
    output_mappings: dict[str, dict[str, str]] = {}
    if target_root is not None and config is not None:
        try:
            output_mappings = _compute_output_mappings(package_root, target_root, config)
        except Exception as exc:  # noqa: BLE001
            print(
                f"  [MANIFEST] WARNING — could not compute output_mappings: {exc}. "
                "Direction B detection will be unavailable until next build.",
                file=sys.stderr,
            )

    # Merge into final manifest structure
    manifest: dict[str, Any] = dict(template_hashes)
    manifest["output_mappings"] = output_mappings

    if dry_run:
        print(
            f"  [DRY-RUN] would write build manifest ({len(template_hashes)} template "
            f"+ {len(output_mappings)} output_mappings entries) -> {manifest_path}"
        )
        return

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"  Wrote build manifest ({len(template_hashes)} template "
        f"+ {len(output_mappings)} output_mappings entries) -> {manifest_path}"
    )


def seed_docs(target_root: Path, dry_run: bool) -> None:
    """Seed missing architecture-doc scaffolds into the project's docs/architecture/.

    Delegates to ``seed_project_docs.seed_architecture_scaffolds``.  Only missing
    files are copied — existing project content is never overwritten.

    Args:
        target_root: Absolute path to the target project root.
        dry_run: When True, prints intent but writes nothing.
    """
    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from seed_project_docs import seed_architecture_scaffolds  # type: ignore[import]
        dry_label = " (dry-run)" if dry_run else ""
        print(f"\nSeeding architecture scaffolds{dry_label}:")
        result = seed_architecture_scaffolds(target_root, dry_run=dry_run)
        print(
            f"  Done: {len(result['copied'])} copied, {len(result['skipped'])} skipped."
        )
    except Exception as exc:
        print(
            f"\n[WARNING] Scaffold seeding failed: {exc}. "
            "Run manually: python leafcutter/scripts/seed_project_docs.py"
        )


def update_diagrams(package_root: Path) -> None:
    """Regenerate Mermaid diagrams from registry and embed into target docs.

    Args:
        package_root: Root of the leafcutter package (contains
            config/ and docs/ subdirectories).
    """
    try:
        import importlib.util
        diagram_script = package_root / "scripts" / "generate_agent_diagram.py"
        spec = importlib.util.spec_from_file_location("generate_agent_diagram", diagram_script)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            agents = mod.load_registry()
            updated = mod.embed_diagrams(agents)
            print("\nDiagram update:")
            for path, was_updated in updated.items():
                status = "updated" if was_updated else "no change"
                print(f"  {path}: {status}")
    except Exception as exc:
        print(f"\n[WARNING] Diagram update failed: {exc}. "
              "Run manually: python leafcutter/scripts/generate_agent_diagram.py --output-format embed")


def install_shims(target_root: Path) -> None:
    """Dynamically import and run install_shims from the target project.

    Args:
        target_root: Absolute path to the target project root; used to locate
            ``scripts/commit_guardian/install_pre_commit_shims.py``.
    """
    shims_module = (
        target_root / "scripts" / "commit_guardian" / "install_pre_commit_shims.py"
    )
    if not shims_module.exists():
        print(
            f"\n[INFO] install_pre_commit_shims.py not found at {shims_module}; "
            "skipping shim install."
        )
        return
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "install_pre_commit_shims", shims_module
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print("\nInstalling pre-commit shims...")
            mod.install_shims(target_root)
            print("  Shims installed.")
    except Exception as exc:
        print(
            f"\n[WARNING] Shim install failed: {exc}. "
            "Run manually: python scripts/commit_guardian/install_pre_commit_shims.py"
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-15 10:15 [python-coder/EPIC-PortableSQLAgents/ticket-01]: (#EPIC-LeafcutterMVP/01)
#   Created this module by extracting write_build_manifest, _seed_docs,
#   _update_diagrams, and _install_shims from build.py. The extraction
#   was required to keep build.py under the 400-line limit enforced by
#   the check-file-size pre-commit hook. All functions are self-contained
#   utility helpers with no shared state; the move requires only an import
#   change in build.py (from build_helpers import ...). All callers
#   continue to access these functions via build.py's re-exports for
#   backward compatibility.
# - 2026-05-15 10:30 [python-coder/TICKET-20260515]: Merged Direction B (#EPIC-LeafcutterMVP/01)
#   manifest support into write_build_manifest() here (conflict resolution:
#   adopted build_helpers.py as canonical module; ported _compute_output_mappings
#   and the output_mappings manifest section from build_manifest.py). Signature
#   extended with optional target_root and config parameters. When provided,
#   the manifest's output_mappings section records expected SHA-256 of each
#   rendered output so check_output_drift.py can detect Direction B drift.
#   build_manifest.py and build_extras.py (my branch's separate modules) are
#   superseded by this consolidated module.
# ====================================================================
