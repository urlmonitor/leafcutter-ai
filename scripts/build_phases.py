"""
MODULE: build_phases
GOAL: Execute each build phase of the leafcutter build system,
    materialising template files into a target project directory.
BUSINESS CONTEXT: Templates for agents, skills, workflows, rules, hooks, and
    ticket lifecycle folders are stored under leafcutter/templates/.
    Each phase function reads a template sub-directory, compiles or copies the
    files, and writes them to the correct output path in the target project.
    Ticket 29 added registry injection: build_agents() now loads
    agent_registry.json and passes it + the skills_root to
    compile_agent_template(), enabling {{my_spawn_allowlist}},
    {{my_skills_used}}, and {{registry_phase_agents_table}} placeholder
    resolution at build time.
ARCHITECTURE: Eight public phase functions, one per output category:
    ``build_agents``, ``build_skills``, ``build_workflows``, ``build_rules``,
    ``build_ticket_lifecycle``, ``build_commit_guardian``, ``build_precommit_config``
    (imported from build_precommit.py), ``build_doc_compliance``.
    All functions share the same signature (target_root, config, dry_run, force)
    and return a file-written count. File-write helpers come from build.py's
    ``write_file`` and ``should_overwrite``. The ``force`` parameter defaults
    to True at the CLI level (overwrite existing files); callers pass
    force=False only when --no-overwrite is requested.
    A compare-before-write guard in ``_write`` skips byte-identical text files;
    ``_files_content_identical`` does the same for binary files via SHA-256.
    Skipped files are counted in module-level ``_uptodate_count`` and surfaced
    by main() via ``reset_uptodate_count`` / ``get_uptodate_count``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from template_compiler import (
    _load_registry,
    compile_agent_template,
    compile_skill_template,
    inject_config,
    parse_frontmatter,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
REGISTRY_PATH = PACKAGE_ROOT / "config" / "agent_registry.json"
SKILLS_TEMPLATE_DIR = TEMPLATES_DIR / "skills"

_log = logging.getLogger(__name__)

# Re-export build_precommit_config so callers (build.py, tests) can import it
# from either module.
from build_precommit import (  # noqa: E402
    build_precommit_config,
    _render_hook_yaml,
    _strip_package_managed_blocks,
    _find_decision_history_index,
    _build_output_lines,
)


# ---------------------------------------------------------------------------
# Module-level up-to-date counter (reset by build.py before each CLI run)
# ---------------------------------------------------------------------------

# Counts files whose on-disk content was byte-identical to the new content
# and were therefore skipped by _write or _files_content_identical.  main()
# in build.py resets this via reset_uptodate_count() and reads it via
# get_uptodate_count() to emit "Up-to-date: N files (unchanged)".
_uptodate_count: int = 0


def reset_uptodate_count() -> None:
    """Reset the module-level up-to-date counter to zero.

    Must be called by main() in build.py before the build phases run, so
    that consecutive CLI invocations report accurate per-run counts.
    """
    global _uptodate_count  # noqa: PLW0603
    _uptodate_count = 0


def get_uptodate_count() -> int:
    """Return the number of files skipped due to identical content this run.

    Returns:
        Current value of the module-level up-to-date counter.
    """
    return _uptodate_count


# ---------------------------------------------------------------------------
# Internal write helpers (thin wrappers; callers can also use build.write_file)
# ---------------------------------------------------------------------------

def _should_overwrite(target: Path, force: bool) -> bool:
    """Return True when target does not exist or force is set.

    Args:
        target: Path to check.
        force: When True, existing files are overwritten.

    Returns:
        True if the file is absent or force is True; False otherwise.
    """
    return not target.exists() or force


def _write(target: Path, content: str, dry_run: bool, force: bool) -> bool:
    """Write content to target, respecting dry-run and force flags.

    Adds a compare-before-write guard: when the target already exists and the
    encoded content is byte-identical to what is already on disk, the write is
    skipped and False is returned.  This eliminates mtime churn and spurious
    ``git status`` entries for unchanged files.  Binary or unreadable files
    fall through to an unconditional write (UnicodeDecodeError / OSError are
    caught and silently ignored).

    Args:
        target: Absolute path to the destination file.
        content: Text content to write (UTF-8).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        True if a write occurred or dry-run mode is active; False if skipped
        because the file already existed and the content was byte-identical.
    """
    if not _should_overwrite(target, force):
        return False
    if dry_run:
        print(f"  [DRY-RUN] would write {target}")
        return True
    # Compare-before-write: skip if the on-disk content is byte-identical.
    # Runs only for real writes; dry-run always returns True (intent) above.
    if target.exists():
        try:
            existing = target.read_text(encoding="utf-8")
            if existing == content:
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                return False
        except (UnicodeDecodeError, OSError):
            pass  # Binary or unreadable file — fall through to write.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return True


def _files_content_identical(src: Path, dst: Path) -> bool:
    """Return True when src and dst exist and have byte-identical content.

    Uses SHA-256 hashes to compare binary files without loading both into
    memory simultaneously when files are large.

    Args:
        src: Source file path.
        dst: Destination file path.

    Returns:
        True iff both files exist and their SHA-256 digests match.
    """
    if not dst.exists():
        return False
    try:
        def _sha256(path: Path) -> str:
            h = hashlib.sha256()
            h.update(path.read_bytes())
            return h.hexdigest()
        return _sha256(src) == _sha256(dst)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Build phase functions
# ---------------------------------------------------------------------------

def build_agents(target_root: Path, config: dict[str, Any],
                 dry_run: bool, force: bool) -> int:
    """Compile all agent templates to ``<target_root>/.claude/agents/``.

    Skips helper files whose names start with ``_`` (e.g. ``_signoff_block.md``).

    Registry injection (ticket 29): loads ``agent_registry.json`` once and passes
    the agents list, registry path, and skills root to ``compile_agent_template``
    so that ``{{my_spawn_allowlist}}``, ``{{my_skills_used}}``, and
    ``{{registry_phase_agents_table}}`` placeholders are resolved at compile time.
    When the registry is absent, compilation proceeds without injection (graceful
    degradation — unresolved placeholders remain as-is in the compiled output).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    agents_template_dir = TEMPLATES_DIR / "agents"
    if not agents_template_dir.exists():
        return 0

    agents_output_dir = target_root / ".claude" / "agents"

    # Load registry once for the whole phase (ticket 29)
    agents_list = _load_registry(REGISTRY_PATH)
    skills_root = SKILLS_TEMPLATE_DIR if SKILLS_TEMPLATE_DIR.exists() else None

    written = 0
    for template_file in sorted(agents_template_dir.glob("*.md")):
        if template_file.name.startswith("_"):
            continue  # Skip helper files like _signoff_block.md
        output_path = agents_output_dir / template_file.name
        compiled = compile_agent_template(
            template_file,
            config,
            registry_path=REGISTRY_PATH,
            agents=agents_list,
            skills_root=skills_root,
        )
        if _write(output_path, compiled, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  agents/{template_file.name}")

    return written


def build_skills(target_root: Path, config: dict[str, Any],
                 dry_run: bool, force: bool) -> int:
    """Copy all skill templates to ``<target_root>/.claude/skills/``.

    Markdown files (``.md``) are compiled via ``compile_skill_template``.
    Non-markdown files (scripts, data) are copied verbatim.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    skills_template_dir = TEMPLATES_DIR / "skills"
    if not skills_template_dir.exists():
        return 0

    skills_output_dir = target_root / ".claude" / "skills"
    written = 0
    internal_skills: list[str] = []

    for skill_dir in sorted(skills_template_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        # Detect internal skills by reading the SKILL.md frontmatter.
        # Internal skills (internal: true) are still copied to .claude/skills/
        # so runtime agents can invoke them, but they are excluded from
        # user-facing skill listings and summary tables.
        skill_md = skill_dir / "SKILL.md"
        is_internal = False
        if skill_md.is_file():
            fm, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            is_internal = bool(fm.get("internal", False))
            if is_internal:
                internal_skills.append(skill_dir.name)

        for template_file in sorted(skill_dir.rglob("*")):
            if not template_file.is_file():
                continue
            rel = template_file.relative_to(skills_template_dir)
            output_path = skills_output_dir / rel

            if template_file.suffix == ".md":
                compiled = compile_skill_template(template_file, config)
                if _write(output_path, compiled, dry_run, force):
                    written += 1
                    if not dry_run:
                        suffix = " [internal]" if is_internal else ""
                        print(f"  skills/{rel}{suffix}")
            else:
                # Non-markdown files (scripts, etc.) are copied verbatim.
                # SHA-256 compare-before-copy skips identical binary files.
                if not _should_overwrite(output_path, force):
                    continue
                if _files_content_identical(template_file, output_path):
                    global _uptodate_count  # noqa: PLW0603
                    _uptodate_count += 1
                    continue
                if dry_run:
                    print(f"  [DRY-RUN] would copy {output_path}")
                    written += 1
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(template_file, output_path)
                    print(f"  skills/{rel}")
                    written += 1

    if internal_skills and not dry_run:
        _log.info(
            "Internal skills (excluded from user-facing listings): %s",
            ", ".join(internal_skills),
        )

    return written


def build_workflows(target_root: Path, config: dict[str, Any],
                    dry_run: bool, force: bool) -> int:
    """Copy workflow templates to ``<target_root>/.claude/commands/``.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    workflows_dir = TEMPLATES_DIR / "workflows"
    if not workflows_dir.exists():
        return 0

    output_dir = target_root / ".claude" / "commands"
    written = 0

    for template_file in sorted(workflows_dir.glob("*.md")):
        output_path = output_dir / template_file.name
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  workflows/{template_file.name}")

    return written


def build_rules(target_root: Path, config: dict[str, Any],
                dry_run: bool, force: bool) -> int:
    """Copy rule templates to ``<target_root>/.agents/rules/``.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    rules_dir = TEMPLATES_DIR / "rules"
    if not rules_dir.exists():
        return 0

    output_dir = target_root / ".agents" / "rules"
    written = 0

    for template_file in sorted(rules_dir.glob("*.md")):
        output_path = output_dir / template_file.name
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
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
    ``<target_root>/tickets/ticket_lifecycle.json`` so supervisors can read it.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import json as _json

    lifecycle_dir = TEMPLATES_DIR / "ticket-lifecycle"
    if not lifecycle_dir.exists():
        return 0

    manifest_path = PACKAGE_ROOT / "config" / "ticket_lifecycle.json"
    tickets_root = target_root / "tickets"
    written = 0

    # Copy ticket_lifecycle.json to the target project
    if manifest_path.exists():
        target_manifest = tickets_root / "ticket_lifecycle.json"
        if _write(target_manifest,
                  manifest_path.read_text(encoding="utf-8"),
                  dry_run, force):
            written += 1
            if not dry_run:
                print("  tickets/ticket_lifecycle.json")

    # Copy all template files (READMEs, .gitkeeps)
    for template_file in sorted(lifecycle_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(lifecycle_dir)
        output_path = tickets_root / rel
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  tickets/{rel}")

    return written


def build_commit_guardian(target_root: Path, config: dict[str, Any],
                          dry_run: bool, force: bool) -> int:
    """Copy commit guardian files to ``<target_root>/scripts/commit_guardian/``.

    Text files (``.json``, ``.py``, ``.yaml``, ``.yml``, ``.md``) have config
    placeholders injected; all other file types are copied verbatim.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    _canonical = TEMPLATES_DIR / "scripts" / "commit_guardian"
    cg_dir = _canonical if _canonical.exists() else TEMPLATES_DIR / "commit-guardian"
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
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  scripts/commit_guardian/{rel}")
        else:
            # SHA-256 compare-before-copy skips identical binary files.
            if not _should_overwrite(output_path, force):
                continue
            if _files_content_identical(template_file, output_path):
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                continue
            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/commit_guardian/{rel}")
                written += 1
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_file, output_path)
                print(f"  scripts/commit_guardian/{rel}")
                written += 1

    return written


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
    dc_dir = TEMPLATES_DIR / "doc-compliance"
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
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  scripts/doc_compliance/{rel}")

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
    template_path = TEMPLATES_DIR / "vision" / "VISION.template.md"
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
    if _write(target_path, content, dry_run, force=False):
        print("  vision: created from template (PLEASE FILL — see <!-- QUESTION --> markers)")
        return 1
    return 0


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 00:50 [epic-supervisor/T04]: Added _find_decision_history_index (#EPIC-LeafcutterMVP/01)
#   and _build_output_lines to re-exports from build_precommit so unit tests
#   can access them via build_phases. No logic changes in this module.
# - 2026-05-13 16:30 [epic-supervisor/T03]: Extracted precommit-config logic (#EPIC-LeafcutterMVP/01)
#   into build_precommit.py to keep this module within 400 counted lines.
#   build_precommit_config, _render_hook_yaml, _strip_package_managed_blocks
#   are imported and re-exported from build_precommit. build.py imports
#   build_precommit_config directly from build_phases (unchanged call site).
# - 2026-05-13 12:15 [epic-supervisor/ticket-13]: Extracted from build.py (#EPIC-LeafcutterMVP/01)
#   during file-size refactor (build.py exceeded 400-line limit). All
#   seven build phase functions moved here. build.py now imports them and
#   calls them in sequence from main(). Private _write / _should_overwrite
#   helpers duplicated here to keep the module self-contained and avoid a
#   circular import with build.py.
# - 2026-05-13 17:00 [Agent/ticket-19]: Updated build_ticket_lifecycle() to (#EPIC-LeafcutterMVP/01)
#   read ticket_lifecycle.json manifest and copy it to target project at
#   tickets/ticket_lifecycle.json. Folder structure is still driven by
#   templates/ticket-lifecycle/ but the manifest is now the authoritative
#   source of truth for folder semantics and routing.
# - 2026-05-13 18:00 [epic-supervisor/ticket-29]: build_agents() now loads (#EPIC-LeafcutterMVP/01)
#   agent_registry.json once per phase call and passes agents, registry_path,
#   and skills_root to compile_agent_template(). Adds REGISTRY_PATH and
#   SKILLS_TEMPLATE_DIR module-level constants. Graceful degradation: when
#   registry absent, compilation proceeds without injection.
# - 2026-05-13 22:00 [python-coder/TICKET-20260513]: Updated ARCHITECTURE (#EPIC-LeafcutterMVP/01)
#   docstring to document that the force parameter now defaults to True at the
#   CLI level (overwrite by default). Phase function signatures are unchanged;
#   the effective_force=True default is resolved in build.py main() before
#   dispatch.
# - 2026-05-14 12:00 [python-coder/TICKET-20260513-CompareBeforeWrite]: Added (#EPIC-LeafcutterMVP/01)
#   compare-before-write guard to _write(): reads existing file content and
#   skips the write if byte-identical. Added _files_content_identical() for
#   SHA-256 hash comparison in binary shutil.copy2 branches. Added module-
#   level _uptodate_count counter with reset_uptodate_count() /
#   get_uptodate_count() API so main() can report "Up-to-date: N files" vs
#   "Total files written: N". Eliminates mtime churn on unchanged files.
# - 2026-05-17 12:00 [python-coder/TICKET-20260517-VisionTemplate]: Added (#EPIC-LeafcutterMVP/01)
#   build_vision() phase. Materialises docs/vision.md from
#   templates/vision/VISION.template.md with unconditional write-if-absent
#   semantics (force=False always passed to _write, ignoring caller flag).
#   This makes vision.md a human-curated living document that is never
#   clobbered by subsequent build runs.
# - 2026-05-18 11:15 [EPIC-PortableInstallHardening/T03]: Changed build_commit_guardian cg_dir from TEMPLATES_DIR/"commit-guardian" to TEMPLATES_DIR/"scripts"/"commit_guardian" with legacy fallback for backward compatibility. (#EPIC-PortableInstallHardening/T03)
# ====================================================================
