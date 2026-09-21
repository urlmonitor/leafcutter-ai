"""
MODULE: build_phases_lifecycle
GOAL: Deploy the project-lifecycle build phases (hooks, commands, rules,
    ticket-lifecycle scaffolding, and commit-guardian) that were previously
    defined inline in build_phases.py.
BUSINESS CONTEXT: build_phases.py is a 2671-commit-guardian-counted-line file
    against a 400-line check-file-size limit. This module carries six
    thematically-adjacent lifecycle-plane functions out of build_phases.py as
    part of a mechanical file-split refactor, with no behaviour change.
ARCHITECTURE: Six public/private symbols, re-exported from build_phases.py so
    every existing caller (build.py, and every unit test that does
    ``import build_phases`` and calls or monkeypatches these names) keeps
    working unchanged — the same re-export pattern build_phases.py already
    uses for build_precommit_config from build_precommit.py and
    build_knowledge_scripts from build_phases_knowledge.py.

    Each function defers its imports of build_phases's private write/deploy
    helpers (``TEMPLATES_DIR``, ``PACKAGE_ROOT``, ``_should_overwrite``,
    ``_files_content_identical``, ``_write``) and shared ``_uptodate_count``
    module state to function scope via a late ``import build_phases as _bp``,
    rather than a module-level ``from build_phases import ...`` — several
    unit tests (``unit_tests/test_build_hooks.py`` and four
    ``unit_tests/portability/test_ge_120e_*.py`` files, plus
    ``unit_tests/test_build_deployment.py``) monkeypatch module attributes
    directly on ``build_phases``, and a module-level ``from ... import``
    would bind a stale local copy that silently defeats the patch.

    ``build_commit_guardian`` retains its documented portability contract
    unchanged: it resolves its template source as
    ``TEMPLATES_DIR/"scripts"/"commit_guardian"`` (with a legacy fallback to
    ``TEMPLATES_DIR/"commit-guardian"`` predating that move) — only the
    module the constant is read through has changed, via ``_bp.TEMPLATES_DIR``.

    This module lives alongside build_phases.py, build_precommit.py, and
    build_phases_knowledge.py directly under ``scripts/`` in the leafcutter-ai
    package source. None of those "build engine" files are themselves copied
    anywhere by any build phase — a consumer install runs
    ``python leafcutter-ai/scripts/build.py --target-dir .`` directly against
    the cloned package source, and ``scripts/`` is already on ``sys.path`` at
    that point. So this module ships and resolves at import time exactly the
    way build_precommit.py and build_phases_knowledge.py already do, with no
    deploy-manifest entry required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from template_compiler import inject_config


def build_hooks(target_root: Path, config: dict[str, Any],
                dry_run: bool, force: bool) -> int:
    """Copy hook scripts verbatim to platform-specific hook directories.

    Hooks are plain Python scripts (no template compilation). Each ``.py`` file
    in ``templates/hooks/`` is copied to the active platform directories.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (used for platform selection).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    hooks_template_dir = _bp.TEMPLATES_DIR / "hooks"
    if not hooks_template_dir.exists():
        return 0

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "hooks",
        "antigravity": "gemini/hooks",
        "cursor": None,
        "copilot": None,
        "cline": None
    }

    written = 0
    for hook_file in sorted(hooks_template_dir.glob("*.py")):
        if hook_file.name.startswith("_"):
            continue
        if hook_file.name == "__pycache__":
            continue

        content = hook_file.read_text(encoding="utf-8")

        for platform, is_active in platforms.items():
            if not is_active:
                continue

            output_subpath = platform_dirs.get(platform)
            if not output_subpath:
                continue

            output_dir = target_root / output_subpath
            output_path = output_dir / hook_file.name

            if _bp._write(output_path, content, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  {output_subpath}/{hook_file.name}")

    return written


def build_commands(target_root: Path, config: dict[str, Any],
                   dry_run: bool, force: bool) -> int:
    """Copy command templates to ``<target_root>/.claude/commands/``.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    commands_dir = _bp.TEMPLATES_DIR / "commands"
    if not commands_dir.exists():
        return 0

    output_dir = target_root / "commands"
    written = 0

    for template_file in sorted(commands_dir.glob("*.md")):
        output_path = output_dir / template_file.name
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _bp._write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  commands/{template_file.name}")

    return written


def build_rules(target_root: Path, config: dict[str, Any],
                dry_run: bool, force: bool) -> int:
    """Copy rule templates to ``<output_root>/.agents/rules/``.

    .. warning::
       The ``target_root`` parameter name is a misnomer for this function and
       every other member of build.py's ``internal_phases`` list: that loop
       passes ``output_root`` (``<target_root>/.leafcutter`` by default), never
       ``target_root``. Rules land at ``<output_root>/.agents/rules/`` and are
       NOT shimmed back up to ``<target_root>/.agents/`` — ``shim_map`` has no
       ``.agents`` entry, by design.

       Trusting this parameter's name is what made ``_compute_output_mappings``
       record 16 manifest keys under ``<target_root>/.agents/rules/`` — a
       directory the build never creates — while the 16 files it does write
       went unrecorded and ungated (BP-100k-2).

    Args:
        target_root: Absolute path the outputs are written beneath. Despite the
            name, callers in ``internal_phases`` pass ``output_root``.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    rules_dir = _bp.TEMPLATES_DIR / "rules"
    if not rules_dir.exists():
        return 0

    output_dir = target_root / ".agents" / "rules"
    written = 0

    for template_file in sorted(rules_dir.glob("*.md")):
        output_path = output_dir / template_file.name
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _bp._write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  rules/{template_file.name}")

    return written


def build_ticket_lifecycle(target_root: Path, config: dict[str, Any],
                           dry_run: bool, force: bool) -> int:
    """Scaffold ``tickets/`` folder structure from the ticket-lifecycle template.

    Reads ``leafcutter/config/ticket_lifecycle.json`` as the source
    of truth for folder names. Creates each folder with a generated README and
    a ``.gitkeep`` file. Also copies ``ticket_lifecycle.json`` to
    ``<tickets_root>/ticket_lifecycle.json`` so supervisors can read it.

    The tickets root is derived from the ``tickets_inbox_path`` config key
    (e.g. ``"leafcutter-ai/tickets/00_inbox"`` → root is
    ``"leafcutter-ai/tickets/"``). Falls back to ``"tickets/"`` when the key
    is absent, preserving consumer-project defaults. A skip-if-manifest-exists
    guard prevents re-running on already-populated projects (override with
    ``force=True``).

    Folder paths declared in the manifest may be remapped via config overlay
    using the same key mapping used by ``build_project_paths_table()``.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, bypasses the skip-if-manifest-exists guard and
            overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-03 12:00 [python-coder/TICKET-20260603-ConfigDrivenBuildPaths]:
    #   Replaced hardcoded ``target_root / "tickets"`` with config-derived path
    #   from ``tickets_inbox_path`` key. Added skip-if-manifest-exists guard and
    #   folder remap dict to support self-hosting builds where ticket dirs live
    #   under ``leafcutter-ai/`` instead of the workspace root.
    #   (#TICKET-20260603-ConfigDrivenBuildPaths)
    """
    import json as _json

    import build_phases as _bp

    lifecycle_dir = _bp.TEMPLATES_DIR / "ticket-lifecycle"
    if not lifecycle_dir.exists():
        return 0

    manifest_path = _bp.PACKAGE_ROOT / "config" / "ticket_lifecycle.json"

    # Derive tickets_root from config — supports self-hosting builds where the
    # inbox lives under a subdirectory (e.g. "leafcutter-ai/tickets/00_inbox").
    inbox_path_str = config.get("tickets_inbox_path", "tickets/00_inbox")
    tickets_root = (target_root / inbox_path_str).parent

    written = 0

    # Skip guard: if the manifest already exists and force is False, skip all
    # writes — matches the write-if-absent pattern used by build_vision().
    target_manifest = tickets_root / "ticket_lifecycle.json"
    if target_manifest.exists() and not force:
        print(
            f"  ticket_lifecycle: {tickets_root.relative_to(target_root)}"
            f"/ticket_lifecycle.json exists (skipped)"
        )
        return 0

    # Folder remap: canonical manifest paths → config-overridden actual paths.
    # Ensures that self-hosting builds write to the correct location rather than
    # the hardcoded "tickets/NN_*" canonical names in ticket_lifecycle.json.
    _folder_remap = {
        "tickets/00_inbox":    config.get("tickets_inbox_path",    "tickets/00_inbox"),
        "tickets/01_todo":     config.get("tickets_todo_path",     "tickets/01_todo"),
        "tickets/99_done":     config.get("tickets_done_path",     "tickets/99_done"),
        "tickets/99_rejected": config.get("tickets_rejected_path", "tickets/99_rejected"),
    }

    # Copy ticket_lifecycle.json to the target project
    if manifest_path.exists():
        if _bp._write(target_manifest,
                       manifest_path.read_text(encoding="utf-8"),
                       dry_run, force):
            written += 1
            if not dry_run:
                rel_manifest = tickets_root.relative_to(target_root)
                print(f"  {rel_manifest}/ticket_lifecycle.json")

    # Copy all template files (READMEs, .gitkeeps)
    for template_file in sorted(lifecycle_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(lifecycle_dir)
        output_path = tickets_root / rel
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _bp._write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  {tickets_root.relative_to(target_root)}/{rel}")

    # Scaffold all folders declared in ticket_lifecycle.json (the manifest is
    # the single source of truth — create any that templates didn't cover).
    if manifest_path.exists():
        try:
            manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            manifest = {}
        for folder in manifest.get("folders", []):
            canonical = folder["path"]
            actual_rel = _folder_remap.get(canonical, canonical)
            folder_path = target_root / actual_rel
            gitkeep = folder_path / ".gitkeep"
            if _bp._write(gitkeep, "", dry_run, force=False):
                written += 1
                if not dry_run:
                    print(f"  {actual_rel}/.gitkeep")
            if folder.get("has_epics_subfolder"):
                epics_gitkeep = folder_path / "epics" / ".gitkeep"
                if _bp._write(epics_gitkeep, "", dry_run, force=False):
                    written += 1
                    if not dry_run:
                        print(f"  {actual_rel}/epics/.gitkeep")

    return written


def build_commit_guardian(target_root: Path, config: dict[str, Any],
                          dry_run: bool, force: bool) -> int:
    """Copy commit guardian files to the consumer directory structure.

    Deploys all files from ``templates/scripts/commit_guardian/`` to
    ``<target_root>/scripts/commit_guardian/``, then additionally copies the
    manifest ``commit_guardian.json`` to ``<target_root>/config/commit_guardian/``
    (BO-1700f-1-ii — manifest at canonical config path).

    Text files (``.json``, ``.py``, ``.yaml``, ``.yml``, ``.md``) have config
    placeholders injected; all other file types are copied verbatim.

    The manifest is deployed to both locations so that:
    - ``scripts/commit_guardian/commit_guardian.json`` serves the hook runner.
    - ``config/commit_guardian/commit_guardian.json`` serves as the authoritative
      "guardian installed" indicator for ``check_guardian_scripts_complete()``
      (BO-1700e-5 — no-config detection).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import shutil

    import build_phases as _bp

    cg_dir = _bp.TEMPLATES_DIR / "scripts" / "commit_guardian"
    if not cg_dir.exists():
        return 0

    output_dir = target_root / "scripts" / "commit_guardian"
    written = 0

    for template_file in sorted(cg_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(cg_dir)
        output_path = output_dir / rel

        if template_file.suffix in (".json", ".py", ".yaml", ".yml", ".md"):
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _bp._write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  commit_guardian/{rel}")
        else:
            # SHA-256 compare-before-copy skips identical binary files.
            if not _bp._should_overwrite(output_path, force):
                continue
            if _bp._files_content_identical(template_file, output_path):
                _bp._uptodate_count += 1
                continue
            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/commit_guardian/{rel}")
                written += 1
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_file, output_path)
                print(f"  scripts/commit_guardian/{rel}")
                written += 1

    # Deploy manifest to config/commit_guardian/ (BO-1700f-1-ii).
    # The manifest is the authoritative hook registry; deploying it to config/
    # separates configuration from scripts and enables the authoritative
    # "no config" detection check_guardian_scripts_complete() in
    # verify_precommit_active.py (BO-1700e-5).
    manifest_src = cg_dir / "commit_guardian.json"
    if manifest_src.exists():
        config_guardian_dir = target_root / "config" / "commit_guardian"
        config_dest = config_guardian_dir / "commit_guardian.json"
        try:
            raw = manifest_src.read_text(encoding="utf-8")
        except OSError as exc:
            _bp._log.warning(
                "build_commit_guardian: cannot read manifest source %s: %s",
                manifest_src,
                exc,
            )
        else:
            text = inject_config(raw, config)
            if _bp._write(config_dest, text, dry_run, force):
                written += 1
                if not dry_run:
                    print("  config/commit_guardian/commit_guardian.json")

    # AC BP-900h-4: declaring files read via a __file__-anchored ancestor walk, confirmed
    # absent from a genuine consumer install (2026-08-18, reproduced 2026-08-25) because
    # self-hosted builds accidentally resolve them with source beside output. Deploying here
    # is necessary; check_declaring_files.py proves sufficiency. roadmap.schema.json joined
    # 2026-09-14, same accident, once KI-CG-010 fixed its SCHEMA_RELATIVE path (see below).
    written += _deploy_commit_guardian_config_files(target_root, dry_run, force)

    return written


def _deploy_commit_guardian_config_files(
    target_root: Path, dry_run: bool, force: bool
) -> int:
    """Deploy the commit-guardian declaring files BP-900h-4 confirmed absent.

    Mirrors ``config/ac_store_schema.json``'s deployment block in
    ``build_ac_store`` for each of ``doc_types.json``, ``diagram_types.json``,
    ``agent_registry.json``, and ``roadmap.schema.json`` — write-if-absent-or-changed
    to ``<target_root>/config/<name>``.

    Args:
        target_root: Absolute path to the target project root directory.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    written = 0
    for filename in (
        "doc_types.json",
        "diagram_types.json",
        "agent_registry.json",
        "roadmap.schema.json",
    ):
        src = _bp.PACKAGE_ROOT / "config" / filename
        if not src.is_file():
            continue
        output_path = target_root / "config" / filename
        if _bp._write(output_path, src.read_text(encoding="utf-8"), dry_run, force):
            written += 1
            if not dry_run:
                print(f"  config/{filename}")
    return written


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-13 17:00 [Agent/ticket-19]: Updated build_ticket_lifecycle() to
#   read ticket_lifecycle.json manifest and copy it to target project at
#   tickets/ticket_lifecycle.json. Folder structure is still driven by
#   templates/ticket-lifecycle/ but the manifest is now the authoritative
#   source of truth for folder semantics and routing. (#EPIC-LeafcutterMVP/01)
# - 2026-06-03 12:00 [python-coder/TICKET-20260603-ConfigDrivenBuildPaths]:
#   Fixed build_ticket_lifecycle() to derive tickets_root from config key
#   tickets_inbox_path instead of hardcoding "tickets". Added skip-if-manifest-
#   exists guard (matches build_vision() pattern). Added _folder_remap dict so
#   manifest canonical paths are rewritten to config-overridden actual paths.
#   (#TICKET-20260603-ConfigDrivenBuildPaths)
# - 2026-05-18 11:15 [EPIC-PortableInstallHardening/T03]: Changed
#   build_commit_guardian cg_dir from TEMPLATES_DIR/"commit-guardian" to
#   TEMPLATES_DIR/"scripts"/"commit_guardian" with legacy fallback for
#   backward compatibility. (#EPIC-PortableInstallHardening/T03)
# - 2026-09-14 [python-coder/bp-size-split]: Moved build_hooks, build_commands,
#   build_rules, build_ticket_lifecycle, build_commit_guardian, and
#   _deploy_commit_guardian_config_files verbatim from build_phases.py into
#   this new sibling module to bring build_phases.py under the
#   400-counted-line check-file-size limit. Re-exported from build_phases.py
#   so build.py and every test import keeps working.
#   (#refactor/build-phases-size-limit)
# ===========================================================================
