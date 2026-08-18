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

    BP-100k-1/-2 (2026-08-18): Direction A now records a fingerprint for
    every template family the drift gates actually scan — not just
    templates/agents/*.md — by mirroring check_build_drift.py's own scanned
    set (templates/agents/*.md + templates/scripts/commit_guardian/*.py).
    Direction B now records output_mappings keys at the CANONICAL,
    shim-resolved path (e.g. ``.claude/agents/README.md``,
    ``.agents/rules/foo.md``) that check_output_drift.py actually looks up,
    rather than the pre-shim ``output_root``-relative path — the earlier
    keys (e.g. ``agents/README.md``) never matched any real on-disk file, so
    every deployed output was permanently "not in output_mappings". The
    agents/commands/workflows/hooks families are derived from
    build_phases._compute_phase_mappings() (the same enumeration build.py's
    own collision guard uses) rather than a second hand-written inventory,
    and translated to their canonical path via ``shim_map`` — the same
    table install_shims() uses to create the shims — so a new deploy
    phase or a new shim entry extends coverage on both sides without a
    separate edit here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_colors import dry_run as _dry_run
from build_colors import error as _error
from build_colors import info as _info
from build_colors import success as _success
from build_colors import warn as _warn

# ---------------------------------------------------------------------------
# Canonical (shimmed) output directory table — the SINGLE source of truth for
# translating an output_root-relative deploy path (e.g. "agents/README.md")
# into the canonical tool path check_output_drift.py actually scans (e.g.
# ".claude/agents/README.md"). install_shims() uses this exact table (in
# place, not copied) to create the shims; _compute_output_mappings() reuses
# it to key output_mappings entries the same way — never a second,
# independently-maintained copy. Named ``shim_map`` (lowercase, matching
# install_shims()'s historical local-variable name) rather than an
# ALL_CAPS module constant so it stays the literal `tests/
# test_build_artifact_parity.py::TestShimMapCoversAllUserFacingCategories`
# AST-parses for — a structural parity test unrelated to this ticket.
# ---------------------------------------------------------------------------
shim_map: list[tuple[str, str]] = [
    (".claude/agents", "agents"),
    (".claude/skills", "skills"),
    (".claude/commands", "commands"),
    (".claude/hooks", "hooks"),
    (".claude/workflows", "workflows"),
    (".gemini", "gemini"),
    # Bridge pre-consolidation scripts/ paths to .leafcutter/scripts/ so that
    # tests and hooks that reference scripts/commit_guardian/,
    # scripts/doc_compliance/, and scripts/feedback/ still resolve after the
    # ADR-004 consolidation moved those directories under .leafcutter/scripts/.
    # Required for CI (fresh-clone) and for any test suite that adds these
    # directories to sys.path at the old location (ADR-016).
    ("scripts/commit_guardian", "scripts/commit_guardian"),
    ("scripts/doc_compliance", "scripts/doc_compliance"),
    ("scripts/feedback", "scripts/feedback"),
]

# Reverse lookup restricted to single-path-component output_rel entries —
# those are the only ones usable as a per-file canonicalization prefix (the
# multi-segment "scripts/commit_guardian" family is copied verbatim, not
# rendered per-template-file by _compute_output_mappings).
_OUTPUT_REL_TO_CANONICAL: dict[str, str] = {
    output_rel: canonical_rel
    for canonical_rel, output_rel in shim_map
    if "/" not in output_rel
}


def _load_build_phases_module(package_root: Path):
    """Load ``build_phases.py`` fresh from ``package_root/scripts``.

    ``build_phases.py`` resolves its own module-level constants
    (``TEMPLATES_DIR``, ``PACKAGE_ROOT``, ``REGISTRY_PATH``,
    ``SKILLS_TEMPLATE_DIR``) from ``Path(__file__)`` at import time rather
    than accepting ``package_root`` as a parameter. A bare
    ``import build_phases`` would silently reuse whatever copy of the module
    a PRIOR call already cached in ``sys.modules`` under that bare name —
    reading the wrong package's templates whenever this function runs more
    than once against a different ``package_root`` within the same process
    (exactly the scenario this module's own test suite exercises with
    multiple temp-directory synthetic packages). Loading via
    ``importlib.util.spec_from_file_location`` under a name derived from
    ``package_root`` guarantees a fresh, correctly-rooted module every call.

    Args:
        package_root: Root of the leafcutter package to load
            ``build_phases.py`` from.

    Returns:
        The freshly executed ``build_phases`` module object.
    """
    module_path = package_root / "scripts" / "build_phases.py"
    unique_name = f"_build_helpers_dyn_build_phases_{abs(hash(str(module_path)))}"
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _template_family(source: Path, templates_dir: Path) -> str | None:
    """Return the top-level template family name for a source template path.

    E.g. ``<templates_dir>/agents/foo.md`` -> ``"agents"``. Used to pick the
    correct render step (compile_agent_template, inject_config, or a raw
    copy) for a ``(source, target)`` pair produced by
    ``build_phases._compute_phase_mappings``.

    Args:
        source: Absolute path to a template source file.
        templates_dir: Absolute path to the package's ``templates/`` root.

    Returns:
        The first path component of ``source`` relative to ``templates_dir``,
        or None if ``source`` is not under ``templates_dir``.
    """
    try:
        rel = source.relative_to(templates_dir)
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def _canonicalize_output_path(
    output_root_path: Path, output_root: Path, target_root: Path
) -> Path | None:
    """Translate an ``output_root``-relative deploy target into its canonical,
    shim-resolved path under ``target_root``.

    Deploy phases (build_agents, build_commands, build_workflows, build_hooks)
    write into ``output_root`` (``.leafcutter/`` by default); ``install_shims``
    then bridges each managed subdirectory to its canonical tool path (e.g.
    ``.claude/agents``). ``check_output_drift.py`` looks up deployed files at
    that canonical path, so ``output_mappings`` keys must use it too — this
    reuses ``shim_map``, the exact table ``install_shims`` uses to create the
    shims, rather than a second hardcoded translation.

    Args:
        output_root_path: Absolute path under ``output_root`` that a deploy
            phase would write to.
        output_root: Absolute path to the consolidated output directory.
        target_root: Absolute path to the target project root.

    Returns:
        The canonical absolute path under ``target_root``, or None when
        ``output_root_path`` is not under ``output_root`` or its top-level
        directory has no canonical shim entry.
    """
    try:
        rel = output_root_path.relative_to(output_root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    canonical_dir = _OUTPUT_REL_TO_CANONICAL.get(rel.parts[0])
    if canonical_dir is None:
        return None
    return target_root / canonical_dir / Path(*rel.parts[1:])


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

    Covers the same template directories that build_phases.py writes, keyed
    by the CANONICAL (post-shim) path check_output_drift.py scans:
    - agents:    templates/agents/*.md      to  .claude/agents/
    - commands:  templates/commands/*.md    to  .claude/commands/
    - workflows: templates/workflows/*.md   to  .claude/commands/
    - hooks:     templates/hooks/*.py       to  .claude/hooks/
    - skills:    templates/skills/**/*      to  .claude/skills/
    - rules:     templates/rules/*.md       to  .agents/rules/
    - workflow scripts: templates/workflows-js/*.js to .claude/workflows/

    The agents/commands/workflows/hooks families are derived from
    ``build_phases._compute_phase_mappings()`` — the same per-platform
    enumeration build.py's own deploy-collision guard uses — rather than a
    second hand-written inventory, then translated to their canonical path
    via ``shim_map`` (BP-100k-2).

    commit-guardian, doc-compliance, and ticket-lifecycle templates are
    intentionally excluded because those output files are maintained by the
    project owner (not agent-authored) and are therefore not subject to the
    edit-templates-not-built-copies guardrail.

    Args:
        package_root: Root of the leafcutter package.
        target_root: Root of the target project (where outputs are written).
        config: Merged config dict used for placeholder injection.

    Returns:
        Dict mapping canonical output-relative-path strings to dicts with
        keys ``template`` (template rel-path) and ``expected_output_hash``
        (sha256).
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

    output_root_name = config.get("output_root", ".leafcutter")
    output_root = target_root / output_root_name

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

    # --- agents / commands / workflows(->commands) / hooks ---
    # Derived from the SAME (source, target) enumeration build.py's collision
    # guard uses, so a new deploy phase added there extends coverage here
    # automatically instead of requiring a parallel edit. Best-effort: a
    # package_root without a full scripts/ tree (e.g. a minimal fixture that
    # only exercises one of the other families below) degrades to skipping
    # just this section instead of aborting the whole computation.
    build_phases_mod = None
    phase_mappings: list[tuple[Path, Path]] = []
    try:
        build_phases_mod = _load_build_phases_module(package_root)
        phase_mappings = build_phases_mod._compute_phase_mappings(output_root, config)
    except (OSError, ImportError, AttributeError, ValueError) as exc:
        _warn(f"could not enumerate deploy-phase output mappings: {exc}")

    def _render_phase_source(source: Path, family: str | None) -> str | None:
        """Render a phase-mapping source exactly as its deploy phase would.

        Args:
            source: Absolute path to the template source file.
            family: Top-level template family name (from ``_template_family``).

        Returns:
            The rendered content string, or None if ``family`` is not one of
            the families handled by this section (caller should skip it).
        """
        if family == "agents":
            content = compile_agent_template(
                source, config,
                registry_path=registry_path,
                agents=agents_list,
                skills_root=skills_root,
            )
            return build_phases_mod._inject_components_table(content, package_root)
        if family in ("commands", "workflows"):
            return inject_config(source.read_text(encoding="utf-8"), config)
        if family == "hooks":
            return source.read_text(encoding="utf-8")
        return None

    for source, target in phase_mappings:
        canonical_output = _canonicalize_output_path(target, output_root, target_root)
        if canonical_output is None:
            continue  # no canonical shim for this family (e.g. cursor/copilot)

        content = _render_phase_source(source, _template_family(source, templates_dir))
        if content is None:
            continue

        _add(source, canonical_output, content)

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

    # --- rules ---
    rules_tpl_dir = templates_dir / "rules"
    if rules_tpl_dir.is_dir():
        for tpl in sorted(rules_tpl_dir.glob("*.md")):
            text = inject_config(tpl.read_text(encoding="utf-8"), config)
            output = target_root / ".agents" / "rules" / tpl.name
            _add(tpl, output, text)

    # --- workflow scripts (JS, no compilation — raw copy) ---
    workflows_js_dir = templates_dir / "workflows-js"
    if workflows_js_dir.is_dir():
        for tpl in sorted(workflows_js_dir.glob("*.js")):
            content = tpl.read_text(encoding="utf-8")
            output = target_root / ".claude" / "workflows" / tpl.name
            _add(tpl, output, content)

    return mappings


def write_build_manifest(
    package_root: Path,
    dry_run: bool = False,
    target_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Write .build_manifest.json with template hashes and expected output hashes.

    The ``templates`` section records the SHA-256 content hash of every .md file
    under ``package_root/templates/agents/`` AND every .py file under
    ``package_root/templates/scripts/commit_guardian/`` (backward-compatible
    with, and mirroring the exact scope of, check_build_drift.py's own two
    scanned template trees — Direction A detection). Without the second tree,
    every commit-guardian hook template is permanently "not in manifest" and
    can never be drift-checked (BP-100k-1).

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
        _warn(f"templates/agents/ not found at {templates_dir}; skipping.")
        return

    # --- Direction A: template hashes (flat dict, backward-compatible) ---
    template_hashes: dict[str, str] = {}
    repo_root = package_root.parent  # leafcutter/ is one level below repo root
    for tpl_path in sorted(templates_dir.rglob("*.md")):
        key = tpl_path.relative_to(repo_root).as_posix()
        template_hashes[key] = hashlib.sha256(tpl_path.read_bytes()).hexdigest()

    # Commit-guardian hook templates: check_build_drift.py scans this second
    # template tree independently (its own _collect_py_template_files()), so
    # its fingerprints must live in the same manifest or every hook script
    # edit is permanently reported "not in manifest" (BP-100k-1). Mirrors
    # that collector exactly: all .py files, __pycache__ excluded.
    cg_templates_dir = package_root / "templates" / "scripts" / "commit_guardian"
    if cg_templates_dir.is_dir():
        for tpl_path in sorted(cg_templates_dir.rglob("*.py")):
            if "__pycache__" in tpl_path.parts:
                continue
            key = tpl_path.relative_to(repo_root).as_posix()
            template_hashes[key] = hashlib.sha256(tpl_path.read_bytes()).hexdigest()

    # --- Direction B: expected output hashes (new output_mappings section) ---
    output_mappings: dict[str, dict[str, str]] = {}
    if target_root is not None and config is not None:
        try:
            output_mappings = _compute_output_mappings(package_root, target_root, config)
        except Exception as exc:  # noqa: BLE001
            import warnings
            warnings.warn(
                f"could not compute output_mappings: {exc}. "
                "Direction B detection will be unavailable until next build.",
                stacklevel=2,
            )
            _warn(
                f"could not compute output_mappings: {exc}. "
                "Direction B detection will be unavailable until next build."
            )

    # Merge into final manifest structure
    manifest: dict[str, Any] = dict(template_hashes)
    manifest["output_mappings"] = output_mappings

    if dry_run:
        _dry_run(
            f"would write build manifest ({len(template_hashes)} template "
            f"+ {len(output_mappings)} output_mappings entries) -> {manifest_path}"
        )
        return

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _success(
        f"build manifest ({len(template_hashes)} template "
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
    except Exception as exc:  # noqa: BLE001
        print()
        _warn(
            f"Scaffold seeding failed: {exc}. "
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
    except Exception as exc:  # noqa: BLE001
        print()
        _warn(f"Diagram update failed: {exc}. "
              "Run manually: python leafcutter/scripts/generate_agent_diagram.py --output-format embed")


def install_shims(
    target_root: Path,
    output_root: Path | None = None,
    config: dict[str, Any] | None = None,
    dry_run: bool = False,
    force: bool = True,
) -> list[dict[str, str]]:
    """Create shims at canonical tool paths pointing into the consolidated output root.

    Tools like Claude Code expect files at `.claude/agents/`, pre-commit reads
    `.pre-commit-config.yaml` from the repo root, and Gemini reads `.gemini/`.
    After build phases write everything into `<output_root>/`, this function
    bridges those canonical paths via symlinks (preferred) or file copies
    (Windows fallback).

    The strategy is controlled by ``config["shim_strategy"]``:
    - ``"symlink"``: always use symlinks; fail loudly on PermissionError.
    - ``"copy"``: always use file copies (safe on all platforms).
    - ``"auto"`` (default): try symlinks first, fall back to copies on error.

    Args:
        target_root: Absolute path to the target project root.
        output_root: Absolute path to the consolidated output directory
            (e.g. ``target_root / ".leafcutter"``). When None, reads from
            ``config["output_root"]`` or defaults to ``target_root / ".leafcutter"``.
        config: Build config dict. Used to read ``shim_strategy``.
        dry_run: When True, prints the shim plan but writes nothing.
        force: When True, overwrites existing shims.

    Returns:
        List of dicts describing each shim: {canonical, target, method}.
    """
    if config is None:
        config = {}

    strategy = config.get("shim_strategy", "auto")
    if output_root is None:
        output_root = target_root / config.get("output_root", ".leafcutter")

    # Uses the module-level shim_map directly (single source of truth,
    # shared with _compute_output_mappings' canonical-path translation) —
    # never a second, independently-maintained copy of this table.
    results: list[dict[str, str]] = []

    for canonical_rel, output_rel in shim_map:
        canonical_path = target_root / canonical_rel
        source_path = output_root / output_rel

        if not source_path.exists():
            _warn(f"shim source missing: {output_rel}/ — "
                  f"no build phase populated it. Skipping {canonical_rel} shim.")
            continue

        if canonical_path.exists() or canonical_path.is_symlink():
            if not force:
                results.append({
                    "canonical": canonical_rel,
                    "target": output_rel,
                    "method": "skipped (exists)",
                })
                continue
            if not dry_run:
                if canonical_path.is_symlink() or canonical_path.is_file():
                    canonical_path.unlink()
                elif canonical_path.is_dir():
                    import shutil
                    shutil.rmtree(canonical_path)

        if dry_run:
            method = "symlink" if strategy != "copy" else "copy"
            _dry_run(f"would shim {canonical_rel} -> {output_rel} ({method})")
            results.append({
                "canonical": canonical_rel,
                "target": output_rel,
                "method": f"dry-run ({method})",
            })
            continue

        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        method = _create_shim(canonical_path, source_path, strategy)
        results.append({
            "canonical": canonical_rel,
            "target": output_rel,
            "method": method,
        })
        _info(f"shim: {canonical_rel} -> {output_rel} ({method})")

    # Single-file shims (these are files, not directories)
    file_shims: list[tuple[str, str]] = [
        (".pre-commit-config.yaml", "pre-commit-config.yaml"),
        (".claude/settings.json", "settings.json"),
    ]

    for canonical_rel, output_rel in file_shims:
        canonical_path = target_root / canonical_rel
        source_path = output_root / output_rel

        if not source_path.exists():
            continue

        if canonical_path.exists() or canonical_path.is_symlink():
            if not force:
                results.append({
                    "canonical": canonical_rel,
                    "target": output_rel,
                    "method": "skipped (exists)",
                })
                continue
            if not dry_run:
                canonical_path.unlink()

        if dry_run:
            method = "symlink" if strategy != "copy" else "copy"
            _dry_run(f"would shim {canonical_rel} -> {output_rel} ({method})")
            results.append({
                "canonical": canonical_rel,
                "target": output_rel,
                "method": f"dry-run ({method})",
            })
            continue

        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        method = _create_file_shim(canonical_path, source_path, strategy)
        results.append({
            "canonical": canonical_rel,
            "target": output_rel,
            "method": method,
        })
        _info(f"shim: {canonical_rel} -> {output_rel} ({method})")

    return results


def _create_shim(canonical: Path, source: Path, strategy: str) -> str:
    """Create a directory shim (symlink or copy) at canonical pointing to source.

    Returns the method used ("symlink" or "copy").
    """
    import shutil

    if strategy == "copy":
        shutil.copytree(source, canonical, dirs_exist_ok=True)
        return "copy"

    try:
        canonical.symlink_to(source, target_is_directory=True)
    except (OSError, PermissionError):
        if strategy == "symlink":
            raise
        shutil.copytree(source, canonical, dirs_exist_ok=True)
        return "copy (symlink failed)"
    else:
        return "symlink"


def _create_file_shim(canonical: Path, source: Path, strategy: str) -> str:
    """Create a file shim (symlink or copy) at canonical pointing to source.

    Returns the method used ("symlink" or "copy").
    """
    import shutil

    if strategy == "copy":
        shutil.copy2(source, canonical)
        return "copy"

    try:
        canonical.symlink_to(source)
    except (OSError, PermissionError):
        if strategy == "symlink":
            raise
        shutil.copy2(source, canonical)
        return "copy (symlink failed)"
    else:
        return "symlink"


def _resolve_precommit_cmd():
    """Return the command list to invoke pre-commit, or None if unavailable.

    Three-tier detection:
    1. ``shutil.which("pre-commit")`` — binary on PATH.
    2. ``importlib.util.find_spec("pre_commit")`` — installed as a Python
       package in the same environment running build.py (handles the common
       case where pip installed it but the Scripts/ dir isn't on PATH).
    3. Probe known pip/pipx install locations — handles non-interactive shells
       where ~/.local/bin or Scripts/ aren't in PATH.
    """
    if shutil.which("pre-commit"):
        return ["pre-commit"]
    if importlib.util.find_spec("pre_commit"):
        return [sys.executable, "-m", "pre_commit"]
    for candidate in _precommit_known_paths():
        if not candidate.is_file():
            continue
        try:
            probe = subprocess.run(
                [str(candidate), "--version"],
                capture_output=True,
                timeout=5,
            )
            if probe.returncode == 0:
                return [str(candidate)]
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def _precommit_known_paths():
    """Yield common install locations for the pre-commit binary."""
    home = Path.home()
    yield home / ".local" / "bin" / "pre-commit"
    exe_dir = Path(sys.executable).parent
    yield exe_dir / "pre-commit"
    if sys.platform == "win32":
        yield exe_dir / "Scripts" / "pre-commit.exe"
    else:
        yield exe_dir / "Scripts" / "pre-commit"


def install_hooks(target_root, dry_run=False):
    """Run ``pre-commit install`` after build.py writes .pre-commit-config.yaml.

    Closes the "last mile" gap: the generated config exists on disk but
    ``pre-commit install`` must be run to wire ``.git/hooks/pre-commit`` to it.
    This function is idempotent — calling it multiple times on the same project
    is safe.

    Args:
        target_root: Absolute path to the target project root.
        dry_run: When True, prints the action but does not run any subprocess.

    Returns:
        One of "installed", "dry-run", "failed",
        "skipped (pre-commit not found)", "skipped (custom hooksPath)",
        or "skipped (not a git repo)".
    """
    # 1. Resolve pre-commit binary (PATH lookup, then Python module fallback).
    precommit_cmd = _resolve_precommit_cmd()
    if precommit_cmd is None:
        _warn("pre-commit not found; skipping hook install")
        _info("         Pre-commit runs code-quality checks automatically before")
        _info("         each commit. Install it with:")
        _info("")
        _info("           pip install pre-commit")
        _info("")
        _info("         Then re-run this build to complete hook setup.")
        return "skipped (pre-commit not found)"

    # 2. Dry-run guard (before any subprocess calls that mutate state).
    if dry_run:
        _dry_run("would run pre-commit install")
        return "dry-run"

    # 3. Check core.hooksPath git config.
    try:
        hooks_path_result = subprocess.run(
            ["git", "-C", str(target_root), "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        # git binary not found — degrade safely rather than hard-failing.
        _warn(f"hooks: could not read core.hooksPath (git not found): {exc}")
        hooks_path_result = None
    if hooks_path_result is not None and hooks_path_result.returncode == 0:
        hooks_path_value = hooks_path_result.stdout.strip()
        default_hooks = Path(target_root) / ".git" / "hooks"
        is_default = (
            hooks_path_value.lower() in (".git/hooks", ".git\\hooks")
            or Path(hooks_path_value).resolve() == default_hooks.resolve()
        )
        if is_default:
            try:
                subprocess.run(
                    ["git", "-C", str(target_root), "config", "--unset", "core.hooksPath"],
                    capture_output=True,
                )
            except OSError as exc:
                _warn(f"hooks: could not unset core.hooksPath (git not found): {exc}")
            else:
                _info("hooks: cleared redundant core.hooksPath (.git/hooks)")
        elif hooks_path_value:
            _warn(
                f"core.hooksPath is set to '{hooks_path_value}' "
                "(non-default); skipping pre-commit install"
            )
            return "skipped (custom hooksPath)"

    # 3.5. Guard: verify target_root is inside a git working tree.
    # Using `git rev-parse --git-dir` is more robust than checking for a .git
    # directory directly: it also handles worktrees and nested repos correctly.
    try:
        git_check = subprocess.run(
            ["git", "-C", str(target_root), "rev-parse", "--git-dir"],
            capture_output=True,
        )
    except OSError as exc:
        # git binary not found — degrade safely rather than hard-failing.
        _warn(f"hooks: could not verify git repo (git not found): {exc}")
        git_check = None

    if git_check is not None and git_check.returncode != 0:
        _info("hooks: skipping pre-commit install (target is not a git repo)")
        return "skipped (not a git repo)"

    # 4. Run pre-commit install.
    try:
        subprocess.run(
            [*precommit_cmd, "install"],
            cwd=str(target_root),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        _error(f"pre-commit install failed: {stderr.strip()}")
        return "failed"

    _success("hooks: pre-commit install OK")
    return "installed"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 [python-coder/EPIC-BuildPipelinePhantomRemediation/07]: (#BP-100k-1/-2)
#   Fixed two blind spots that made the drift gates report every non-agent
#   template and every real deployed output as absent/unregistered while
#   exiting clean. (1) Direction A (template_hashes) only hashed
#   templates/agents/*.md; check_build_drift.py separately scans
#   templates/scripts/commit_guardian/*.py and looked those keys up in the
#   same manifest, so every commit-guardian hook template was permanently
#   "not in manifest". write_build_manifest() now also hashes that tree,
#   mirroring check_build_drift.py's own two-directory scan exactly.
#   (2) Direction B (output_mappings) keyed entries by the pre-shim,
#   output_root-relative path (e.g. "agents/README.md"), but
#   check_output_drift.py looks up the CANONICAL, post-shim path (e.g.
#   ".claude/agents/README.md") — no real deployed file ever matched.
#   _compute_output_mappings() now derives the agents/commands/workflows/
#   hooks families from build_phases._compute_phase_mappings() (the same
#   enumeration build.py's own collision guard uses) and translates each
#   target through the module-level shim_map — the exact table
#   install_shims() uses to create the shims (both now read the SAME
#   module-level list; install_shims() previously defined its own local
#   copy) — rather than a second hardcoded inventory. skills/rules/
#   workflow-js entries were also re-keyed onto their
#   canonical path (.claude/skills, .agents/rules, .claude/workflows).
#   Added _load_build_phases_module() to load build_phases.py by file path
#   under a name derived from package_root: build_phases.py resolves
#   TEMPLATES_DIR/PACKAGE_ROOT from its own __file__ at import time, so a
#   bare `import build_phases` would silently reuse a stale module cached
#   under a different package_root within the same process.
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
# - 2026-05-30 10:15 [python-coder/TICKET-20260530-AutoInstallPrecommitHooks]: Added (#TICKET-20260530)
#   install_hooks(target_root, dry_run) to close the "last mile" gap between
#   generating .pre-commit-config.yaml and activating it. Handles: pre-commit
#   not on PATH (non-fatal warning), dry-run mode (returns early before any
#   subprocess), core.hooksPath redundant default (auto-unset), core.hooksPath
#   custom path (warn+skip), and CalledProcessError (non-fatal, returns "failed").
#   Called from build.py main() under the same --no-shims guard as install_shims().
#   Idempotent. Added shutil and subprocess to module-level imports.
# - 2026-06-04 00:00 [python-coder/TICKET-20260604-PrecommitBinaryResolution]: (#TICKET-20260604)
#   Added --version probe to _resolve_precommit_cmd() tier-3 (known-paths) loop.
#   Tier 3 previously accepted any .is_file() candidate, allowing stale or
#   non-executable binaries on WSL2 / broken pip installs to slip through and
#   cause [ERROR] pre-commit install failed: instead of the correct graceful
#   "skipped (pre-commit not found)" warning. Probe uses subprocess.run with
#   capture_output=True and timeout=5; OSError and TimeoutExpired both continue
#   to the next candidate. Zero performance cost on the common happy path (tier 1
#   succeeds before tier 3 runs). Added BLE001 noqa on unavoidable broad-except
#   blocks in seed_docs() and update_diagrams(). Refactored try/except in
#   _create_shim() and _create_file_shim() to use else clause (Ruff compliance).
# - 2026-06-17 [python-coder/quick-fix]: Added step 3.5 git-repo guard to (#BP-007)
#   install_hooks(). Before this change, calling install_hooks() against a
#   target_root that has no reachable .git caused `pre-commit install` to run
#   unconditionally, exit non-zero (no git repo), and surface a misleading
#   [ERROR] with empty stderr while returning "failed". The fix inserts a
#   `git -C <target_root> rev-parse --git-dir` probe between step 3 (custom
#   hooksPath guard) and step 4 (`pre-commit install`). Non-zero return code
#   triggers a graceful _info() message and returns "skipped (not a git repo)"
#   instead of reaching pre-commit. The subprocess call is wrapped in
#   try/except OSError so that a missing git binary degrades safely. When
#   target_root IS a real git repo the probe succeeds and execution falls
#   through to step 4 unchanged, preserving the loud-failure path for genuine
#   install errors. Docstring Returns: section updated to list the new status.
# ====================================================================
