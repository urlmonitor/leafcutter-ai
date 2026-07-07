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
ARCHITECTURE: Eleven public phase functions, one per output category:
    ``build_agents``, ``build_workflow_scripts``, ``build_ac_store``,
    ``build_skills``, ``build_workflows``, ``build_hooks``,
    ``build_rules``, ``build_ticket_lifecycle``, ``build_commit_guardian``,
    ``build_precommit_config`` (imported from build_precommit.py),
    ``build_doc_compliance``, ``build_antigravity_instructions``.
    ``build_ac_store`` deploys the seven AC pipeline scripts
    (scan_ac_store, generate_ticket_from_ac, ac_prioritizer, mark_ac_done,
    scan_ac_orphans, build_ac_mode_detection, goal_to_epic) from their source
    locations directly to ``<target_root>/scripts/ac_store/``, making
    ``portable: true`` AC-pipeline skills functional on consumer installs
    (ADR-013).
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
from build_precommit import (  # noqa: E402, F401  # re-exported for callers
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

    # Load registry once for the whole phase (ticket 29)
    agents_list = _load_registry(REGISTRY_PATH)
    skills_root = SKILLS_TEMPLATE_DIR if SKILLS_TEMPLATE_DIR.exists() else None

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "agents",
        "antigravity": "gemini/agents",
        "cursor": None,
        "copilot": None,
        "cline": None
    }

    written = 0
    for template_file in sorted(agents_template_dir.glob("*.md")):
        if template_file.name.startswith("_"):
            continue  # Skip helper files like _signoff_block.md

        compiled = compile_agent_template(
            template_file,
            config,
            registry_path=REGISTRY_PATH,
            agents=agents_list,
            skills_root=skills_root,
        )

        for platform, is_active in platforms.items():
            if not is_active:
                continue

            output_subpath = platform_dirs.get(platform)
            if not output_subpath:
                continue

            output_dir = target_root / output_subpath
            output_path = output_dir / template_file.name

            if _write(output_path, compiled, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  {output_subpath}/{template_file.name}")

    return written


def _emit_workflow_variant(raw: bytes, engine: str) -> bytes:
    """Return engine-specific bytes for a canonical E2 workflow source.

    The build pipeline is E2-only. Only ``"e2"`` and ``"auto"`` are supported
    (``"auto"`` is resolved to ``"e2"`` upstream by ``build_workflow_scripts``
    before this function is invoked, but ``"auto"`` is also accepted here for
    callers that invoke this function directly).

    Requesting ``"e1"`` raises ``ValueError``. The E1 wrap was fundamentally
    broken — it prepended ``export async function run`` over a top-level body
    that contains a bare ``return`` statement, producing an ESM module that
    throws ``SyntaxError: Illegal return statement`` on import. It has been
    removed per the decision recorded in
    EPIC-DualEngineWorkflowSupport ticket 09 (2026-07-06).

    Args:
        raw: Raw bytes of the canonical E2 workflow script.
        engine: Target engine identifier. ``"e2"`` and ``"auto"`` produce the
            identity transform (raw bytes returned unchanged). ``"e1"`` raises
            ``ValueError`` (unsupported — see above). Any other unknown value
            also returns raw bytes unchanged (safe identity default).

    Returns:
        Transformed bytes ready to write to the output directory.

    Raises:
        ValueError: When ``engine`` is ``"e1"`` — E1 is not supported.
    """
    if engine == "e1":
        raise ValueError(
            "E1 workflow engine is not supported. "
            "Use engine='e2' or engine='auto' (resolves to e2). "
            "The E1 wrap was removed in EPIC-DualEngineWorkflowSupport/09 "
            "because it produced an unloadable ESM module."
        )
    # "e2", "auto", and any unknown value all return raw bytes unchanged.
    # (The identity transform is the correct E2 contract.)
    return raw


def build_workflow_scripts(target_root: Path, config: dict[str, Any],
                           dry_run: bool, force: bool) -> int:
    """Copy Claude Code Workflow JS scripts to ``<output_root>/workflows/``.

    Gated on two conditions (both must pass for files to be copied):

    1. **Opt-in flag**: ``config["workflows"]["enabled"]`` must be ``True``.
       Default is ``False`` — workflows are experimental. If absent or ``False``,
       the phase skips silently with a "skipped (not enabled" message.

    2. **Version check (floor only)**: detects Claude Code version via the
       ``CLAUDE_CODE_VERSION`` environment variable, then ``claude --version``
       subprocess (2-second timeout), then treats version as unknown.
       - Below minimum (``2.1.154``): warn and skip file copying.
       - Unknown: warn and install (fail-open, since CI may lack Claude Code).
       The version check is a **floor gate only** — it does NOT influence which
       engine is selected. Engine selection is determined solely by
       ``config["workflows"]["engine"]``.

    **Engine resolution**: ``config["workflows"]["engine"]`` is resolved before
    any file is written. The value ``"auto"`` resolves to ``"e2"`` (the
    deterministic E2 top-level-body engine, per ADR-017 and ticket 09). The
    resolved engine is passed to ``_emit_workflow_variant``. Only ``"e2"`` and
    ``"auto"`` are supported; ``"e1"`` raises ``ValueError`` (the E1 wrap was
    removed in EPIC-DualEngineWorkflowSupport ticket 09 — it produced an
    unloadable ESM module).

    Applies the compare-before-write guard so that identical files are skipped
    on subsequent runs, satisfying the idempotency requirement.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary; reads ``config["workflows"]["enabled"]``
            and ``config["workflows"]["engine"]``.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of ``.js`` files written (or that would be written in dry-run mode).
    """
    import os
    import subprocess
    from packaging.version import Version, InvalidVersion  # type: ignore[import]

    _MINIMUM_VERSION = "2.1.154"

    # ------------------------------------------------------------------
    # Gate 1 — opt-in flag
    # ------------------------------------------------------------------
    workflows_config = config.get("workflows", {})
    enabled = workflows_config.get("enabled", False) if isinstance(workflows_config, dict) else False
    _raw_engine = workflows_config.get("engine", "auto") if isinstance(workflows_config, dict) else "auto"
    # Resolve "auto" → "e2" (the deterministic E2 top-level-body engine).
    # Engine selection is purely config-driven; the version check below is a
    # floor gate only and must NOT influence which engine is selected (ADR-017).
    engine = "e2" if _raw_engine == "auto" else _raw_engine
    if not enabled:
        print("Workflow scripts: skipped (not enabled in skills_config.json)")
        return 0

    # ------------------------------------------------------------------
    # Gate 2 — version detection
    # ------------------------------------------------------------------
    version_str: str | None = os.environ.get("CLAUDE_CODE_VERSION")
    if not version_str:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            # `claude --version` typically outputs e.g. "2.1.154" or "2.1.154\n"
            if result.returncode == 0:
                version_str = result.stdout.strip().split()[-1]
        except Exception as exc:  # noqa: BLE001
            _log.warning("claude --version probe failed: %s", exc)
            version_str = None

    version_known = version_str is not None
    version_ok = False
    if version_known:
        try:
            version_ok = Version(version_str) >= Version(_MINIMUM_VERSION)
        except InvalidVersion:
            version_known = False  # Treat unparseable version as unknown.

    if version_known and not version_ok:
        print(
            f"[WARNING] Claude Code >= {_MINIMUM_VERSION} required for workflow "
            f"scripts. Detected: {version_str}. Skipping."
        )
        return 0

    if not version_known:
        print(
            "[WARNING] Claude Code version unknown. "
            "Installing workflow scripts (fail-open)."
        )
        # Fall through — continue with file copying.

    # ------------------------------------------------------------------
    # Copy .js files from templates/workflows-js/ to output_root/workflows/
    # ------------------------------------------------------------------
    workflows_js_src = TEMPLATES_DIR / "workflows-js"
    if not workflows_js_src.exists():
        print("Workflow scripts: 0 installed (templates/workflows-js/ absent)")
        return 0

    output_dir = target_root / "workflows"
    written = 0
    unchanged = 0

    for js_file in sorted(workflows_js_src.glob("*.js")):
        dest = output_dir / js_file.name
        content = js_file.read_bytes()

        try:
            emitted = _emit_workflow_variant(content, engine)
        except UnicodeDecodeError as exc:
            _log.warning(
                "Skipping %s: workflow transform failed (non-UTF-8 source): %s",
                js_file.name,
                exc,
            )
            continue

        if not _should_overwrite(dest, force):
            continue

        # Compare-before-write guard (binary — SHA-256).
        if dest.exists():
            import hashlib as _hashlib
            existing_digest = _hashlib.sha256(dest.read_bytes()).hexdigest()
            new_digest = _hashlib.sha256(emitted).hexdigest()
            if existing_digest == new_digest:
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                unchanged += 1
                continue

        if dry_run:
            print(f"  [DRY-RUN] would write .claude/workflows/{js_file.name}")
            written += 1
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(emitted)
            written += 1

    if not dry_run:
        print(f"Workflow scripts: {written} installed ({unchanged} unchanged)")

    return written


def build_ac_store(target_root: Path, config: dict[str, Any],
                   dry_run: bool, force: bool) -> int:
    """Deploy AC pipeline scripts to ``<output_root>/scripts/ac_store/``.

    Copies the seven AC-pipeline Python scripts from their source locations in
    the package tree and deploys them to ``<output_root>/scripts/ac_store/``
    (i.e. ``.leafcutter/scripts/ac_store/`` on a default consumer build).
    This makes the ``portable: true`` skills ``ac-scanner`` and ``build-ac``
    functional on consumer installs by ensuring their runtime dependencies are
    present alongside the skill SKILL.md files deployed by ``build_skills``.

    Note: ``target_root`` IS the output root (``.leafcutter/`` by default).
    Scripts land at ``target_root / "scripts" / "ac_store" /`` which resolves
    to ``.leafcutter/scripts/ac_store/``.  The ``{{config.output_root}}``
    placeholder in agent/skill templates resolves to this same root, so
    script paths like ``{{config.output_root}}/scripts/ac_store/<name>.py``
    correctly reference the deployed scripts on consumer installs.

    The seven source → destination mappings are:

    - ``scripts/ac_store/scan_ac_store.py``
      → ``<output_root>/scripts/ac_store/scan_ac_store.py``
    - ``scripts/ac_store/generate_ticket_from_ac.py``
      → ``<output_root>/scripts/ac_store/generate_ticket_from_ac.py``
    - ``scripts/ac_store/ac_prioritizer.py``
      → ``<output_root>/scripts/ac_store/ac_prioritizer.py``
    - ``scripts/ac_store/mark_ac_done.py``
      → ``<output_root>/scripts/ac_store/mark_ac_done.py``
    - ``scripts/ac_store/scan_ac_orphans.py``
      → ``<output_root>/scripts/ac_store/scan_ac_orphans.py``
    - ``scripts/build_ac_mode_detection.py``
      → ``<output_root>/scripts/ac_store/build_ac_mode_detection.py``
    - ``scripts/goal_to_epic.py``
      → ``<output_root>/scripts/ac_store/goal_to_epic.py``

    Files are copied verbatim (no template compilation).  The
    compare-before-write guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (used for interface parity;
            not consumed by this phase — scripts are copied verbatim).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-AcPipelineDeployGaps/03]:
    #   Added build_ac_store() phase per ADR-013 (Option a). Closes the
    #   portable-skill/missing-script gap for ac-scanner and build-ac.
    #   (#EPIC-AcPipelineDeployGaps/03)
    """
    ac_store_src = PACKAGE_ROOT / "scripts" / "ac_store"
    scripts_src = PACKAGE_ROOT / "scripts"

    # The seven files to deploy: (source_path, destination_filename)
    deploy_map = [
        (ac_store_src / "scan_ac_store.py",            "scan_ac_store.py"),
        (ac_store_src / "generate_ticket_from_ac.py",  "generate_ticket_from_ac.py"),
        (ac_store_src / "ac_prioritizer.py",            "ac_prioritizer.py"),
        (ac_store_src / "mark_ac_done.py",              "mark_ac_done.py"),
        (ac_store_src / "scan_ac_orphans.py",           "scan_ac_orphans.py"),
        (scripts_src / "build_ac_mode_detection.py",    "build_ac_mode_detection.py"),
        (scripts_src / "goal_to_epic.py",               "goal_to_epic.py"),
    ]

    output_dir = target_root / "scripts" / "ac_store"
    written = 0

    for src_file, dest_name in deploy_map:
        if not src_file.is_file():
            _log.warning(
                "build_ac_store: source script not found, skipping: %s", src_file
            )
            continue

        output_path = output_dir / dest_name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/ac_store/{dest_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_ac_store: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/ac_store/{dest_name}")
            written += 1

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

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "skills",
        "antigravity": "gemini/skills",
        "cursor": None,
        "copilot": None,
        "cline": None
    }

    written = 0
    internal_skills: list[str] = []
    deprecated_skills: list[str] = []

    for skill_dir in sorted(skills_template_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        # Detect internal and deprecated skills by reading the SKILL.md frontmatter.
        skill_md = skill_dir / "SKILL.md"
        is_internal = False
        is_deprecated = False
        if skill_md.is_file():
            fm, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            is_internal = bool(fm.get("internal", False))
            is_deprecated = bool(fm.get("deprecated", False))
            if is_internal:
                internal_skills.append(skill_dir.name)
            if is_deprecated:
                deprecated_skills.append(skill_dir.name)

        # Skip deprecated skills entirely — their principles have been migrated
        # elsewhere (e.g. embedded in agent templates). Deploying them would
        # violate fresh-install guarantees (AC BP-700d-1-i).
        if is_deprecated:
            continue

        for template_file in sorted(skill_dir.rglob("*")):
            if not template_file.is_file():
                continue
            rel = template_file.relative_to(skills_template_dir)
            
            for platform, is_active in platforms.items():
                if not is_active:
                    continue
                    
                output_subpath = platform_dirs.get(platform)
                if not output_subpath:
                    continue
                    
                output_dir = target_root / output_subpath
                output_path = output_dir / rel

                if template_file.suffix == ".md":
                    compiled = compile_skill_template(template_file, config)
                    if _write(output_path, compiled, dry_run, force):
                        written += 1
                        if not dry_run:
                            suffix = " [internal]" if is_internal else ""
                            print(f"  {output_subpath}/{rel}{suffix}")
                else:
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
                        print(f"  {output_subpath}/{rel}")
                        written += 1

    if internal_skills and not dry_run:
        _log.info(
            "Internal skills (excluded from user-facing listings): %s",
            ", ".join(internal_skills),
        )
    if deprecated_skills and not dry_run:
        _log.info(
            "Deprecated skills (not deployed — principles migrated to agent templates): %s",
            ", ".join(deprecated_skills),
        )

    return written


def build_workflows(target_root: Path, config: dict[str, Any],
                    dry_run: bool, force: bool) -> int:
    """Copy workflow templates to platform-specific directories.

    Iterates over the active platforms defined in config["platforms"] and
    writes workflows to their respective output directories (e.g.
    ``.claude/commands/``, ``.gemini/workflows/``).

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

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "commands",
        "antigravity": "gemini/workflows",
        "cursor": "cursor/rules",
        "copilot": "copilot-instructions",
        "cline": "cline/rules"
    }

    written = 0

    for platform, is_active in platforms.items():
        if not is_active:
            continue
            
        output_subpath = platform_dirs.get(platform)
        if not output_subpath:
            continue
            
        output_dir = target_root / output_subpath
        
        for template_file in sorted(workflows_dir.glob("*.md")):
            output_path = output_dir / template_file.name
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  {output_subpath}/{template_file.name}")

    return written


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
    hooks_template_dir = TEMPLATES_DIR / "hooks"
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

            if _write(output_path, content, dry_run, force):
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
    commands_dir = TEMPLATES_DIR / "commands"
    if not commands_dir.exists():
        return 0

    output_dir = target_root / "commands"
    written = 0

    for template_file in sorted(commands_dir.glob("*.md")):
        output_path = output_dir / template_file.name
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  commands/{template_file.name}")

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

    lifecycle_dir = TEMPLATES_DIR / "ticket-lifecycle"
    if not lifecycle_dir.exists():
        return 0

    manifest_path = PACKAGE_ROOT / "config" / "ticket_lifecycle.json"

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
        if _write(target_manifest,
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
        if _write(output_path, text, dry_run, force):
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
            if _write(gitkeep, "", dry_run, force=False):
                written += 1
                if not dry_run:
                    print(f"  {actual_rel}/.gitkeep")
            if folder.get("has_epics_subfolder"):
                epics_gitkeep = folder_path / "epics" / ".gitkeep"
                if _write(epics_gitkeep, "", dry_run, force=False):
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
    cg_dir = TEMPLATES_DIR / "scripts" / "commit_guardian"
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
                    print(f"  commit_guardian/{rel}")
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
            _log.warning(
                "build_commit_guardian: cannot read manifest source %s: %s",
                manifest_src,
                exc,
            )
        else:
            text = inject_config(raw, config)
            if _write(config_dest, text, dry_run, force):
                written += 1
                if not dry_run:
                    print("  config/commit_guardian/commit_guardian.json")

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
    template_path = TEMPLATES_DIR / "docs" / "components.json.template"
    if not template_path.exists():
        return 0
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    target_path = target_root / docs_dir / "components.json"
    if target_path.exists():
        print(f"  components: {docs_dir}/components.json exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    if _write(target_path, content, dry_run, force=False):
        print(
            "  components: created from template "
            "(PLEASE POPULATE — add one entry per module; "
            "see templates/docs/components.json.template for the schema)"
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
    feedback_src = TEMPLATES_DIR / "scripts" / "feedback"
    config_src = PACKAGE_ROOT / "config" / "feedback_categories.yaml"
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
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  feedback/{rel}")
        else:
            if not _should_overwrite(output_path, force):
                continue
            if _files_content_identical(template_file, output_path):
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
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
        if _write(config_output, text, dry_run, force):
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
    template_path = TEMPLATES_DIR / "ANTIGRAVITY.md.template"
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
    if _write(output_path, content, dry_run, force):
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
    sp_dir = TEMPLATES_DIR / "scripts" / "sync_platforms"
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
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  sync_platforms/{rel}")
        else:
            if not _should_overwrite(output_path, force):
                continue
            if _files_content_identical(template_file, output_path):
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
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


def build_ac_store_docs(target_root: Path, config: dict[str, Any],
                        dry_run: bool, force: bool) -> int:
    """Install AC Traceability Store documentation into the target project.

    Copies ``templates/docs/how-to/ac-traceability-store.md`` to
    ``{target_root}/docs/how-to/ac-traceability-store.md`` and
    ``templates/docs/reference/ac-schema.md`` to
    ``{target_root}/docs/reference/ac-schema.md``.

    Uses write-if-absent semantics — existing files are never overwritten,
    regardless of the ``force`` parameter.  This preserves user-edited
    documentation across subsequent build runs.

    Args:
        target_root: Absolute path to the target project root.
        config: Build configuration dict (not used, accepted for interface
            consistency).
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-04 13:10 [documentation-expert/EPIC-ACTraceabilityStore/09]:
    #   Created to install how-to and reference docs for the AC store.
    #   Both files are write-if-absent so user-edited versions are preserved.
    #   (#EPIC-ACTraceabilityStore/09)
    """
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    docs_template_dir = TEMPLATES_DIR / "docs"
    doc_files = [
        (
            docs_template_dir / "how-to" / "ac-traceability-store.md",
            target_root / docs_dir / "how-to" / "ac-traceability-store.md",
            "how-to/ac-traceability-store.md",
        ),
        (
            docs_template_dir / "reference" / "ac-schema.md",
            target_root / docs_dir / "reference" / "ac-schema.md",
            "reference/ac-schema.md",
        ),
    ]

    written = 0
    for template_path, dest_path, display_name in doc_files:
        if not template_path.exists():
            print(f"  [WARNING] AC store docs: template not found: {template_path}")
            continue
        if dest_path.exists():
            print(f"  ac-store-docs: docs/{display_name} exists (skipped)")
            continue
        if dry_run:
            print(f"  [DRY-RUN] would write docs/{display_name}")
            written += 1
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            content = inject_config(
                template_path.read_text(encoding="utf-8"), config
            )
            dest_path.write_text(content, encoding="utf-8")
            print(f"  docs/{display_name}")
            written += 1

    return written


def validate_agent_self_description(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    enforcement_level: str = "warning",
) -> tuple[int, int]:
    """Validate all agent templates have required self-description fields.

    Checks each agent template under ``target_root / "templates" / "agents"``
    for the presence of required frontmatter fields, and each registry entry
    in ``target_root / "config" / "agent_registry.json"`` for required registry
    fields.

    Required frontmatter fields: ``behavioral_patterns``, ``pre_flight_reads``,
    ``inputs``, ``outputs``, ``mutates``.

    Required registry fields: ``category``, ``skills_invoked``,
    ``knowledge_channels``.

    ``skills_invoked`` entries are validated by resolving ``skill_id`` against
    both ``target_root / "templates" / "skills"`` (package) and
    ``.claude/skills/`` (project-local). An unresolvable skill_id produces a
    problem entry naming which lookup location was checked.

    ``knowledge_channels`` entries are validated: ``channel`` must be an
    integer in the range 1-11 inclusive.

    All problems across all agents are collected before returning (aggregated
    output — never halts on the first error).

    Args:
        target_root: Absolute path to the target project root (or package root).
        config: Build configuration dict (accepted for interface parity;
            currently unused).
        dry_run: When True, logs intent but performs no file I/O side-effects.
            Validation reads are always performed regardless.
        enforcement_level: One of ``"warning"`` or ``"error"``.
            ``"warning"`` prints warnings and returns ``(0, warning_count)``.
            ``"error"`` prints errors and returns ``(error_count, 0)``.

    Returns:
        Tuple ``(error_count, warning_count)`` as integers.

    # DECISION HISTORY
    # - 2026-06-05 12:30 [python-coder/EPIC-SelfDescribingAgents/04]:
    #   Added validate_agent_self_description() per INF-600g. Checks
    #   frontmatter fields (behavioral_patterns, pre_flight_reads, inputs,
    #   outputs, mutates), registry fields (category, skills_invoked,
    #   knowledge_channels), skill_id resolvability (package + project-local),
    #   and knowledge_channels range (1-11). Aggregated output. Two severity
    #   modes: 'warning' returns (0, N); 'error' returns (N, 0).
    #   (#EPIC-SelfDescribingAgents/04)
    # - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/05]:
    #   Confirmed two-path resolution order per INF-600g-3-i:
    #   1. templates/skills/{skill_id}/SKILL.md (package-level)
    #   2. .claude/skills/{skill_id}/SKILL.md (project-local)
    #   A project-local-only skill passes validation without error.
    #   Only when neither path resolves is an error emitted.
    #   (#EPIC-SelfDescribingAgentsCorrections/05)
    """
    agents_template_dir = target_root / "templates" / "agents"
    registry_path = target_root / "config" / "agent_registry.json"
    package_skills_dir = target_root / "templates" / "skills"
    project_skills_dir = target_root / ".claude" / "skills"

    _REQUIRED_FRONTMATTER = [
        "behavioral_patterns",
        "pre_flight_reads",
        "inputs",
        "outputs",
        "mutates",
    ]
    _REQUIRED_REGISTRY = [
        "category",
        "skills_invoked",
        "knowledge_channels",
    ]
    _VALID_CHANNEL_RANGE = range(1, 12)  # 1-11 inclusive

    # Collect all problems as (agent_id, field, location, hint) tuples.
    problems: list[str] = []

    # ----------------------------------------------------------------
    # Load registry — build dict keyed by agent ID for fast lookup.
    # ----------------------------------------------------------------
    registry_entries: dict[str, dict] = {}
    if registry_path.exists():
        try:
            raw = registry_path.read_text(encoding="utf-8")
            registry_data = json.loads(raw)
        except OSError as exc:
            _log.warning("validate_agent_self_description: cannot read registry: %s", exc)
            registry_data = {}
        for entry in registry_data.get("agents", []):
            agent_id = entry.get("id")
            if agent_id:
                registry_entries[agent_id] = entry

    # ----------------------------------------------------------------
    # Validate each agent template file.
    # ----------------------------------------------------------------
    if agents_template_dir.exists():
        for template_file in sorted(agents_template_dir.glob("*.md")):
            if template_file.name.startswith("_"):
                continue  # Skip helper files.
            if template_file.name.upper() == "README.MD":
                continue  # Skip the directory README — not an agent template.

            try:
                text = template_file.read_text(encoding="utf-8")
            except OSError as exc:
                _log.warning(
                    "validate_agent_self_description: cannot read %s: %s",
                    template_file,
                    exc,
                )
                continue

            fm, _ = parse_frontmatter(text)
            agent_name = fm.get("name") or template_file.stem

            # --- Frontmatter field checks ---
            for field in _REQUIRED_FRONTMATTER:
                if field not in fm or fm[field] is None:
                    hint = _self_desc_field_hint(field)
                    problems.append(
                        f"Agent '{agent_name}' template missing required frontmatter field "
                        f"'{field}' ({template_file.name}).\n"
                        f"  Fix hint: {hint}"
                    )

            # --- Registry field checks ---
            entry = registry_entries.get(agent_name, {})

            for field in _REQUIRED_REGISTRY:
                if field not in entry:
                    problems.append(
                        f"Registry entry '{agent_name}' missing required field '{field}'.\n"
                        f"  Fix hint: Add '{field}' to the agent's entry in config/agent_registry.json."
                    )
                    continue

                # skills_invoked: resolve each skill_id
                if field == "skills_invoked":
                    skills_invoked = entry.get("skills_invoked") or []
                    if isinstance(skills_invoked, list):
                        for inv in skills_invoked:
                            skill_id = inv.get("skill_id") if isinstance(inv, dict) else None
                            if not skill_id:
                                continue
                            in_package = (package_skills_dir / skill_id).exists()
                            in_project = (project_skills_dir / skill_id).exists()
                            if not in_package and not in_project:
                                problems.append(
                                    f"Registry entry '{agent_name}' has unresolvable "
                                    f"skills_invoked skill_id '{skill_id}'.\n"
                                    f"  Not found in package (templates/skills/{skill_id}/) "
                                    f"nor project-local (.claude/skills/{skill_id}/).\n"
                                    f"  Fix hint: Create the skill template or correct the skill_id."
                                )

                # knowledge_channels: check channel range 1-11
                if field == "knowledge_channels":
                    channels = entry.get("knowledge_channels") or []
                    if isinstance(channels, list):
                        for ch_entry in channels:
                            channel = (
                                ch_entry.get("channel")
                                if isinstance(ch_entry, dict)
                                else None
                            )
                            if channel is not None and channel not in _VALID_CHANNEL_RANGE:
                                problems.append(
                                    f"Registry entry '{agent_name}' has invalid "
                                    f"knowledge_channels channel value {channel}.\n"
                                    f"  Valid range is 1-11 (per ADR-029 Agent Knowledge Plane).\n"
                                    f"  Fix hint: Correct the channel value."
                                )

    # ----------------------------------------------------------------
    # Emit problems according to enforcement_level.
    # ----------------------------------------------------------------
    if not problems:
        if not dry_run:
            print("  Self-description validation: all agents pass.")
        return (0, 0)

    is_error = enforcement_level == "error"
    prefix = "ERROR" if is_error else "WARNING"
    for problem in problems:
        print(f"  [{prefix}] {problem}")

    if is_error:
        print(
            f"\n  Self-description validation: {len(problems)} error(s) found. "
            "Fix these fields and re-run the build."
        )
        return (len(problems), 0)
    else:
        print(
            f"\n  Self-description validation: {len(problems)} warning(s). "
            "Enforcement is 'warning' — build continues. "
            "Set self_description_enforcement='error' in config/agent_registry.json "
            "once all agents are populated."
        )
        return (0, len(problems))


def _self_desc_field_hint(field: str) -> str:
    """Return a one-line fix hint for a missing self-description frontmatter field.

    Args:
        field: The missing frontmatter field name.

    Returns:
        A short string describing what the field should contain.
    """
    _HINTS = {
        "behavioral_patterns": (
            "Add a behavioral_patterns array listing conditional behaviors, "
            "gates, and delegation rules. Example: "
            "behavioral_patterns: [{name: 'Stop-and-Ask', trigger: '...', "
            "behavior: '...', related_agent: null}]"
        ),
        "pre_flight_reads": (
            "Add a pre_flight_reads list of documents the agent reads before "
            "starting work. Example: pre_flight_reads: ['ticket body', "
            "'cited ADRs']"
        ),
        "inputs": (
            "Add an inputs list describing what the agent receives. Example: "
            "inputs: [{name: ticket_path, type: path, description: 'Path to ticket'}]"
        ),
        "outputs": (
            "Add an outputs list describing what the agent produces. Example: "
            "outputs: [{name: 'Sign-off comment', type: comment, "
            "description: 'status: ok | blocker'}]"
        ),
        "mutates": (
            "Add a mutates list describing what the agent modifies. Example: "
            "mutates: [{name: 'Ticket frontmatter', type: file, "
            "description: 'agents.<name>: signed_off'}]"
        ),
    }
    return _HINTS.get(field, f"Populate the '{field}' field in the agent template frontmatter.")


def build_agent_cards(target_root: Path, config: dict[str, Any],
                      dry_run: bool, force: bool) -> int:
    """Generate .card.md files for all agent templates.

    Delegates entirely to ``generate_agent_cards.build_agent_cards()``.
    Reads all ``.md`` files in ``<target_root>/templates/agents/`` (excluding
    ``_*.md`` helper files), reads YAML frontmatter and the corresponding
    registry entry from ``config/agent_registry.json``, calls
    ``generate_card()``, and writes to
    ``<target_root>/docs/agents/cards/<agent-id>.card.md``.

    Args:
        target_root: Absolute path to the target project root.
        config: Build configuration dict (passed through for interface parity).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing card files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-05 10:30 [python-coder/EPIC-SelfDescribingAgents/02]:
    #   Added build_agent_cards phase. Delegates to generate_agent_cards.py
    #   to keep build_phases.py a thin dispatcher. Registered in build.py
    #   scaffold_phases after ("AC store docs", build_ac_store_docs).
    #   (#EPIC-SelfDescribingAgents/02)
    """
    from generate_agent_cards import (  # noqa: PLC0415 — lazy import avoids circular
        build_agent_cards as _generate_cards,
    )
    return _generate_cards(target_root=target_root, config=config,
                           dry_run=dry_run, force=force)


def build_workflow_tools(target_root: Path, config: dict[str, Any],
                         dry_run: bool, force: bool) -> int:
    """Deploy workflow tool scripts to ``<target_root>/scripts/``.

    Copies the four workflow-tool Python scripts from the package source
    (``scripts/<name>.py``) to the consumer project's ``scripts/`` directory.
    These scripts are referenced by ticket-lifecycle agents and skills but were
    not previously deployed by any build phase (Class B gap, EPIC-BuildGuardFalsePositive).

    Scripts deployed:

    - ``scripts/add_component.py`` — used by the add-component skill.
    - ``scripts/knowledge_query.py`` — used by the knowledge-query skill.
    - ``scripts/set_ticket_status.py`` — used by ticket-lifecycle agents and skills.
    - ``scripts/ticket_prioritizer.py`` — used by the ticket-prioritizer skill.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
    #   Added build_workflow_tools() phase. Deploys add_component.py,
    #   knowledge_query.py, set_ticket_status.py, ticket_prioritizer.py from
    #   package source to scripts/. Closes the Class B deploy gap for these
    #   four workflow-tool scripts. (#EPIC-BuildGuardFalsePositive/03)
    """
    scripts_src = PACKAGE_ROOT / "scripts"
    deploy_scripts = [
        "add_component.py",
        "knowledge_query.py",
        "set_ticket_status.py",
        "ticket_prioritizer.py",
    ]
    output_dir = target_root / "scripts"
    written = 0

    for script_name in deploy_scripts:
        src_file = scripts_src / script_name
        if not src_file.is_file():
            _log.warning(
                "build_workflow_tools: source script not found, skipping: %s", src_file
            )
            continue

        output_path = output_dir / script_name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/{script_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_workflow_tools: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/{script_name}")
            written += 1

    return written


def build_knowledge_scripts(target_root: Path, config: dict[str, Any],
                             dry_run: bool, force: bool) -> int:
    """Deploy knowledge scripts to ``<target_root>/scripts/knowledge/``.

    Copies ``scripts/knowledge/harvest_learnings.py`` from the package source
    to the consumer project. This script is referenced by the knowledge-harvester
    agent but was not previously deployed by any build phase (Class B gap,
    EPIC-BuildGuardFalsePositive/03).

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
    #   Added build_knowledge_scripts() phase. Deploys harvest_learnings.py from
    #   package source scripts/knowledge/ to consumer scripts/knowledge/. Closes
    #   the Class B deploy gap for knowledge-harvester agent.
    #   (#EPIC-BuildGuardFalsePositive/03)
    """
    knowledge_src = PACKAGE_ROOT / "scripts" / "knowledge"
    deploy_scripts = ["harvest_learnings.py"]
    output_dir = target_root / "scripts" / "knowledge"
    written = 0

    for script_name in deploy_scripts:
        src_file = knowledge_src / script_name
        if not src_file.is_file():
            _log.warning(
                "build_knowledge_scripts: source script not found, skipping: %s",
                src_file,
            )
            continue

        output_path = output_dir / script_name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/knowledge/{script_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_knowledge_scripts: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/knowledge/{script_name}")
            written += 1

    return written


def build_template_standalone_scripts(target_root: Path, config: dict[str, Any],
                                      dry_run: bool, force: bool) -> int:
    """Deploy standalone Python scripts from ``templates/scripts/`` to ``<target_root>/scripts/``.

    Copies Python files (``*.py``) from ``templates/scripts/`` (excluding
    subdirectories) to the consumer project's ``scripts/`` directory.

    Currently deploys:

    - ``templates/scripts/setup_ticket_worktree.py`` → ``scripts/setup_ticket_worktree.py``
      Referenced by worktree-agent.md and build-single-ticket/SKILL.md.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
    #   Added build_template_standalone_scripts() phase. Deploys .py files from
    #   templates/scripts/ (shallow, non-recursive) to consumer scripts/.
    #   Primary driver: setup_ticket_worktree.py template was present but no
    #   phase copied it to consumer projects (Class B gap). (#EPIC-BuildGuardFalsePositive/03)
    """
    templates_scripts_src = TEMPLATES_DIR / "scripts"
    if not templates_scripts_src.exists():
        return 0

    output_dir = target_root / "scripts"
    written = 0

    # Shallow scan — only top-level .py files; subdirectories have their own phases
    for src_file in sorted(templates_scripts_src.glob("*.py")):
        if not src_file.is_file():
            continue

        output_path = output_dir / src_file.name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/{src_file.name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_template_standalone_scripts: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/{src_file.name}")
            written += 1

    return written


# ---------------------------------------------------------------------------
# Clean-mode: remove stale artifacts
# ---------------------------------------------------------------------------

#: Artifact subdirectories managed by build.py that are eligible for clean-mode
#: removal. Only files/directories within these subdirectories are ever removed
#: by clean_stale_artifacts(). Paths outside this list are never touched.
_MANAGED_ARTIFACT_DIRS = {
    "agents": "agents",
    "skills": "skills",
    "hooks": "hooks",
    "workflows": ".claude/workflows",
}


def clean_stale_artifacts(
    target_dir: Path,
    source_manifests: dict[str, set[str]],
) -> int:
    """Remove compiled artifacts in the target directory that have no matching source template.

    Scans the three managed artifact subdirectories (``agents/``, ``skills/``,
    ``hooks/``) inside ``<target_dir>/.claude/``. For each artifact found on
    disk, checks whether its name appears in the corresponding set in
    ``source_manifests``. Anything NOT in the manifest is considered stale and
    is removed.

    Only removes files/directories under the known managed subdirectories
    (``.claude/agents/``, ``.claude/skills/``, ``.claude/hooks/``). Files
    elsewhere in ``.claude/`` or the broader target directory are never touched.

    Args:
        target_dir: Root directory of the target project. The managed artifact
            subdirectories are resolved relative to ``<target_dir>/.claude/``.
        source_manifests: Mapping from artifact type to the set of expected
            artifact names. Accepted keys: ``"agents"``, ``"skills"``, ``"hooks"``.
            Each value is a set of file/directory **base names** (e.g.
            ``{"my-agent.md", "other-agent.md"}``). An absent key is treated
            the same as an empty set — all items of that type are considered
            stale.

    Returns:
        Count of artifacts removed (0 when nothing is stale).
    """
    import shutil as _shutil

    claude_dir = target_dir / ".claude"
    removed = 0

    for artifact_type, subdir_name in _MANAGED_ARTIFACT_DIRS.items():
        managed_dir = claude_dir / subdir_name
        if not managed_dir.exists():
            continue

        expected_names: set[str] = source_manifests.get(artifact_type, set())

        for item in sorted(managed_dir.iterdir()):
            if item.name not in expected_names:
                print(f"Removing stale artifact: {item}")
                if item.is_dir() and not item.is_symlink():
                    _shutil.rmtree(item)
                else:
                    item.unlink()
                removed += 1

    if removed == 0:
        print("No stale artifacts found")

    return removed


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
# - 2026-05-21 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]: Added
#   build_feedback() phase. Deploys submit_feedback.py, emit_hook_finding.py,
#   list_tags.py to target_root/scripts/feedback/ and feedback_categories.yaml
#   to target_root/config/. Creates debugging/logs/ directory on first build.
#   Follows build_commit_guardian pattern (rglob + inject_config on .py files).
# - 2026-05-22 [python-coder/EPIC-AntigravitySupport/01]: Updated build_workflows
#   to iterate over active platforms defined in config["platforms"] and emit 
#   workflows to their respective target directories (e.g. .gemini/workflows/ 
#   for antigravity, .claude/commands/ for claude). Defaults fall back to True
#   for claude and antigravity.
# - 2026-05-22 [python-coder/EPIC-AntigravitySupport/09]: Added build_antigravity_instructions
#   phase to compile ANTIGRAVITY.md.template to .gemini/instructions.md.
# - 2026-05-22 [python-coder/Ticket-10]: Added build_sync_platforms phase to
#   deploy scripts/sync_platforms directory.
# - 2026-06-01 [python-coder/EPIC-FlattenSupervisorChain/01]: Added build_workflow_scripts()
#   phase. Copies .js files from templates/workflows-js/ to target/.claude/workflows/.
#   Dual-gate: opt-in flag (skills_config.json workflows.enabled, default false) and
#   Claude Code version check (>= 2.1.154, via CLAUDE_CODE_VERSION env or subprocess).
#   Below-minimum: warns and skips. Unknown version: warns and continues (fail-open).
#   Compare-before-write guard prevents mtime churn on unchanged files. (#EPIC-FlattenSupervisorChain/01)
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
# - 2026-06-03 12:00 [python-coder/TICKET-20260603-ConfigDrivenBuildPaths]:
#   Fixed build_ticket_lifecycle() to derive tickets_root from config key
#   tickets_inbox_path instead of hardcoding "tickets". Added skip-if-manifest-
#   exists guard (matches build_vision() pattern). Added _folder_remap dict so
#   manifest canonical paths are rewritten to config-overridden actual paths.
#   (#TICKET-20260603-ConfigDrivenBuildPaths)
# - 2026-06-04 [python-coder/TICKET-20260604-FixFailingBuildPipelineTests]:
#   Fixed build_workflow_scripts() output path from target_root/"workflows" to
#   target_root/".claude"/"workflows" to match .claude/ layout convention and
#   fix unit_tests/test_build_workflow_phase.py assertions.
#   (#TICKET-20260604-FixFailingBuildPipelineTests)
# - 2026-06-18 [python-coder/EPIC-Oneagenthandlesboththelookandthecodefor/14]:
#   Added deprecated skill exclusion in build_skills(). Skills with
#   deprecated: true in their SKILL.md frontmatter are skipped entirely —
#   not deployed to .claude/skills/ on fresh installs or upgrades.
#   The frontend-design skill is the first user: its design principles are now
#   embedded in templates/agents/frontend-coder.md. Adding deprecated: true
#   to frontend-design/SKILL.md prevents it from being deployed, satisfying
#   AC BP-700d-1-i (fresh install must not create .claude/skills/frontend-design/).
#   (#EPIC-Oneagenthandlesboththelookandthecodefor/14)
# - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
#   Extended build_feedback() to deploy aggregate.py and resolve_feedback.py
#   alongside the three previously-deployed feedback scripts. Added three new
#   phases: build_workflow_tools() (deploys add_component.py, knowledge_query.py,
#   set_ticket_status.py, ticket_prioritizer.py from scripts/ to consumer scripts/),
#   build_knowledge_scripts() (deploys harvest_learnings.py to scripts/knowledge/),
#   and build_template_standalone_scripts() (deploys .py files from templates/scripts/
#   to scripts/, primarily setup_ticket_worktree.py). All new phases use the
#   shutil.copy2 + compare-before-write pattern established by build_ac_store.
#   (#EPIC-BuildGuardFalsePositive/03)
# - 2026-06-17 [python-coder/EPIC-AcPipelineDeployGaps/03]: Added
#   build_ac_store() phase. Copies six AC pipeline scripts
#   (scan_ac_store.py, generate_ticket_from_ac.py, ac_prioritizer.py,
#   mark_ac_done.py, build_ac_mode_detection.py, goal_to_epic.py) to
#   <target_root>/scripts/ac_store/, closing the portable-skill/missing-script
#   gap for ac-scanner and build-ac per ADR-013. (#EPIC-AcPipelineDeployGaps/03)
# - 2026-07-02 [python-coder/EPIC-DualEngineWorkflowSupport/07]:
#   build_workflow_scripts(): resolved "auto" → "e2" explicitly before
#   calling _emit_workflow_variant (ADR-017: E2 is the default deterministic
#   engine). Version check remains a floor gate only — it warns/skips when
#   the Claude Code version is below the minimum but does NOT influence engine
#   selection. Updated _emit_workflow_variant docstring to reflect that "auto"
#   is resolved upstream and no longer reaches the transform function.
#   (#EPIC-DualEngineWorkflowSupport/07)
# - 2026-07-06 [python-coder/EPIC-DualEngineWorkflowSupport/09]:
#   Removed _E1_SHIM constant and the E1-wrap branch from
#   _emit_workflow_variant. "e1" now raises ValueError("E1 workflow engine is
#   not supported") — no file is ever written for e1. The E1 wrap was
#   fundamentally broken: it prepended `export async function run` over a
#   top-level body containing a bare `return` statement, producing an ESM
#   module that throws SyntaxError: Illegal return statement on import.
#   "e2" and "auto" both return raw bytes unchanged (identity transform).
#   Updated build_workflow_scripts docstring to reflect E1 is unsupported.
#   Ruff F401 clean: hashlib and json remain used elsewhere in this module.
#   (#EPIC-DualEngineWorkflowSupport/09)
# ====================================================================
