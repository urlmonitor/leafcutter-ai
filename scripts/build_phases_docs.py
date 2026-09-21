"""
MODULE: build_phases_docs
GOAL: Deploy the docs-and-instructions-plane build phases (doc compliance
    scripts, the human-curated vision/components/UI-context scaffolds, the
    feedback tooling, the antigravity platform instructions, and the
    sync_platforms scripts) that were previously defined inline in
    build_phases.py.
BUSINESS CONTEXT: build_phases.py is grandfathered many times over the
    400-content-line check-file-size limit, and the GE-127b-1 ratchet refuses
    any change that leaves an already-oversized file longer than it was.
    Carrying this thematically-adjacent group of seven phase functions out
    here restores headroom with no behaviour change, exactly as
    build_phases_knowledge.py and build_phases_product_truth.py did for their
    own phase groups.
ARCHITECTURE: Seven public phase functions — ``build_doc_compliance``,
    ``build_vision``, ``build_components_registry``, ``build_ui_context``,
    ``build_feedback``, ``build_antigravity_instructions``,
    ``build_sync_platforms`` — re-exported from build_phases.py so every
    existing caller (notably build.py) keeps working unchanged. All seven
    share the standard phase signature (target_root, config, dry_run, force)
    and defer their imports of build_phases's private write/deploy helpers
    (``PACKAGE_ROOT``, ``TEMPLATES_DIR``, ``_write``, ``_should_overwrite``,
    ``_files_content_identical``) and shared ``_uptodate_count`` module state
    to function scope, to avoid a circular import at module load time
    (build_phases.py imports this module at its own top level). Note
    ``build_vision``, ``build_components_registry``, and ``build_ui_context``
    all deliberately ignore the caller's ``force`` flag and always pass
    ``force=False`` to ``_write`` — these three scaffold human-curated living
    documents that must never be clobbered by a build run once they exist.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from template_compiler import inject_config


def build_doc_compliance(target_root: Path, config: dict[str, Any],
                         dry_run: bool, force: bool) -> int:
    """Copy doc compliance files to ``<target_root>/scripts/doc_compliance/``.

    All files have config placeholders injected regardless of extension.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    dc_dir = _bp.TEMPLATES_DIR / "doc-compliance"
    if not dc_dir.exists():
        return 0

    output_dir = target_root / "scripts" / "doc_compliance"
    written = 0

    for template_file in sorted(dc_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(dc_dir)
        output_path = output_dir / rel

        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _bp._write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  doc_compliance/{rel}")

    return written

def build_vision(target_root: Path, config: dict[str, Any],
                 dry_run: bool, force: bool) -> int:
    """Materialise docs/vision.md from the vision template — write-if-absent only.

    This phase intentionally overrides the ``force`` flag passed by the caller.
    A project's vision.md is a human-curated living document; once it exists it
    must never be clobbered by a build run. The write-if-absent contract is
    declared in the template's ``build_behavior: write_if_absent`` frontmatter
    field and enforced here by always passing force=False to _write().

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    import build_phases as _bp

    template_path = _bp.TEMPLATES_DIR / "vision" / "VISION.template.md"
    if not template_path.exists():
        return 0
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    target_path = target_root / docs_dir / "vision.md"
    if target_path.exists():
        print(f"  vision: {docs_dir}/vision.md exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    # Always force=False regardless of the caller's effective_force —
    # write-if-absent is the non-negotiable contract for this phase.
    if _bp._write(target_path, content, dry_run, force=False):
        print("  vision: created from template (PLEASE FILL — see <!-- QUESTION --> markers)")
        return 1
    return 0


def build_components_registry(target_root: Path, config: dict[str, Any],
                              dry_run: bool, force: bool) -> int:
    """Materialise docs/components.json from the components template — write-if-absent only.

    This phase intentionally overrides the ``force`` flag passed by the caller.
    A project's components.json is a human-curated living registry; once it exists
    it must never be clobbered by a build run.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    import build_phases as _bp

    template_path = _bp.TEMPLATES_DIR / "docs" / "components.json.template"
    if not template_path.exists():
        return 0
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    target_path = target_root / docs_dir / "components.json"
    if target_path.exists():
        print(f"  components: {docs_dir}/components.json exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    if _bp._write(target_path, content, dry_run, force=False):
        print(
            "  components: created from template "
            "(PLEASE POPULATE — add one entry per module; "
            "see templates/docs/components.json.template for the schema)"
        )
        return 1
    return 0


def build_ui_context(target_root: Path, config: dict[str, Any],
                     dry_run: bool, force: bool) -> int:
    """Materialise the UI-context pointer file from the template — write-if-absent only.

    This phase intentionally ignores the ``force`` flag.  The UI-context file is a
    human-curated living document (filled via ``/onboard``); once it exists it must
    never be clobbered by a build run.  The destination path is read from the
    ``ui_context_path`` config key (default ``docs/ui-context.md``).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    import build_phases as _bp

    template_path = _bp.TEMPLATES_DIR / "docs" / "ui-context.template.md"
    if not template_path.exists():
        return 0
    ui_context_rel = config.get("ui_context_path", "docs/ui-context.md")
    target_path = target_root / ui_context_rel
    if target_path.exists():
        print(f"  ui-context: {ui_context_rel} exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    # Always force=False — write-if-absent is the non-negotiable contract for this phase.
    if _bp._write(target_path, content, dry_run, force=False):
        print(
            f"  ui-context: created {ui_context_rel} from template "
            "(set filled: true after curating the pointer fields — see /onboard Step 5c)"
        )
        return 1
    return 0


def build_feedback(target_root: Path, config: dict[str, Any],
                   dry_run: bool, force: bool) -> int:
    """Deploy feedback scripts and config to ``<target_root>/scripts/feedback/`` and ``<target_root>/config/``.

    Reads feedback scripts from ``templates/scripts/feedback/`` (the canonical
    tracked source, per ADR-016) so that a fresh clone with no gitignored build
    outputs still produces a correct deployment. This mirrors the pattern used
    by ``build_commit_guardian``, which reads from
    ``templates/scripts/commit_guardian/``.

    All ``.py`` and text files have config placeholders injected via
    ``inject_config``; the directory is scanned with ``rglob`` so that any
    sub-directories are also handled. ``feedback_categories.yaml`` is deployed
    from ``config/feedback_categories.yaml`` in the package root.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    feedback_src = _bp.TEMPLATES_DIR / "scripts" / "feedback"
    config_src = _bp.PACKAGE_ROOT / "config" / "feedback_categories.yaml"
    if not feedback_src.exists():
        return 0

    output_dir = target_root / "scripts" / "feedback"
    written = 0

    for template_file in sorted(feedback_src.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(feedback_src)
        output_path = output_dir / rel

        if template_file.suffix in (".py", ".yaml", ".yml", ".json", ".md"):
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _bp._write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  feedback/{rel}")
        else:
            if not _bp._should_overwrite(output_path, force):
                continue
            if _bp._files_content_identical(template_file, output_path):
                _bp._uptodate_count += 1  # noqa: SLF001 -- shared build-run counter
                continue
            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/feedback/{rel}")
                written += 1
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil as _shutil
                _shutil.copy2(template_file, output_path)
                print(f"  scripts/feedback/{rel}")
                written += 1

    if config_src.is_file():
        config_output = target_root / "config" / "feedback_categories.yaml"
        text = config_src.read_text(encoding="utf-8")
        if _bp._write(config_output, text, dry_run, force):
            written += 1
            if not dry_run:
                print("  config/feedback_categories.yaml")

    logs_dir = target_root / "debugging" / "logs"
    if not logs_dir.exists() and not dry_run:
        logs_dir.mkdir(parents=True, exist_ok=True)
        print("  debugging/logs/ (created)")

    return written


def build_antigravity_instructions(target_root: Path, config: dict[str, Any],
                                   dry_run: bool, force: bool) -> int:
    """Compile ANTIGRAVITY.md.template to .gemini/instructions.md.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    import build_phases as _bp

    template_path = _bp.TEMPLATES_DIR / "ANTIGRAVITY.md.template"
    if not template_path.exists():
        return 0

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    if not platforms.get("antigravity", True):
        return 0

    output_path = target_root / "gemini" / "instructions.md"

    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    if _bp._write(output_path, content, dry_run, force):
        if not dry_run:
            print("  .gemini/instructions.md")
        return 1
    return 0


def build_sync_platforms(target_root: Path, config: dict[str, Any],
                         dry_run: bool, force: bool) -> int:
    """Copy sync_platforms files to ``<target_root>/scripts/sync_platforms/``.

    All text files have config placeholders injected.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    sp_dir = _bp.TEMPLATES_DIR / "scripts" / "sync_platforms"
    if not sp_dir.exists():
        return 0

    output_dir = target_root / "scripts" / "sync_platforms"
    written = 0

    for template_file in sorted(sp_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(sp_dir)
        output_path = output_dir / rel

        if template_file.suffix in (".py", ".json", ".yaml", ".yml", ".md"):
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _bp._write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  sync_platforms/{rel}")
        else:
            if not _bp._should_overwrite(output_path, force):
                continue
            if _bp._files_content_identical(template_file, output_path):
                _bp._uptodate_count += 1  # noqa: SLF001 -- shared build-run counter
                continue
            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/sync_platforms/{rel}")
                written += 1
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_file, output_path)
                print(f"  scripts/sync_platforms/{rel}")
                written += 1

    return written


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved build_doc_compliance,
#   build_vision, build_components_registry, build_ui_context, build_feedback,
#   build_antigravity_instructions, build_sync_platforms verbatim from
#   build_phases.py into this new sibling module to bring build_phases.py
#   under the 400-counted-line check-file-size limit. Re-exported from
#   build_phases.py so build.py and every test import keeps working.
#   (#refactor/build-phases-size-limit)
# - 2026-05-17 12:00 [python-coder/TICKET-20260517-VisionTemplate]: Added
#   build_vision() phase. Materialises docs/vision.md from
#   templates/vision/VISION.template.md with unconditional write-if-absent
#   semantics (force=False always passed to _write, ignoring caller flag).
#   This makes vision.md a human-curated living document that is never
#   clobbered by subsequent build runs. (#EPIC-LeafcutterMVP/01)
# - 2026-05-21 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]: Added
#   build_feedback() phase. Deploys submit_feedback.py, emit_hook_finding.py,
#   list_tags.py to target_root/scripts/feedback/ and feedback_categories.yaml
#   to target_root/config/. Creates debugging/logs/ directory on first build.
#   Follows build_commit_guardian pattern (rglob + inject_config on .py files).
# - 2026-05-22 [python-coder/EPIC-AntigravitySupport/09]: Added build_antigravity_instructions
#   phase to compile ANTIGRAVITY.md.template to .gemini/instructions.md.
# - 2026-05-22 [python-coder/Ticket-10]: Added build_sync_platforms phase to
#   deploy scripts/sync_platforms directory.
# - 2026-06-02 [python-coder/TICKET-20260602-ComponentsRegistryScaffold]: Added
#   build_components_registry() phase. Materialises docs/components.json from
#   templates/docs/components.json.template with unconditional write-if-absent
#   semantics (force=False always passed to _write, ignoring caller flag).
#   Follows the build_vision() pattern exactly. (#TICKET-20260602-ComponentsRegistryScaffold)
# - 2026-06-03 10:00 [python-coder/EPIC-TemplateDocViolations/04]: Verified
#   build_sync_platforms() already copies .md files (suffix check on line ~1001
#   includes ".md" in the inject_config path). No code change required.
#   README.md added to templates/scripts/sync_platforms/ and
#   scripts/sync_platforms/ to satisfy check_documentation hook. (#EPIC-TemplateDocViolations/04)
# ===========================================================================
