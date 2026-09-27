"""
MODULE: build_phases_workflows
GOAL: Deploy the workflow-plane build phases (workflow-variant emission,
    workflow JS scripts, per-platform workflow markdown, and workflow-tool
    Python scripts) that were previously defined inline in build_phases.py.
BUSINESS CONTEXT: build_phases.py is a 2671-commit-guardian-counted-line file
    against a 400-line check-file-size limit. This module carries four
    thematically-adjacent workflow-plane functions out of build_phases.py as
    part of a mechanical file-split refactor, with no behaviour change.
ARCHITECTURE: Four public/private symbols, re-exported from build_phases.py so
    every existing caller (build.py, and every unit test that does
    ``import build_phases`` and calls or monkeypatches these names) keeps
    working unchanged — the same re-export pattern build_phases.py already
    uses for build_precommit_config from build_precommit.py and
    build_knowledge_scripts from build_phases_knowledge.py.

    Each function defers its imports of build_phases's private write/deploy
    helpers (``TEMPLATES_DIR``, ``PACKAGE_ROOT``, ``_should_overwrite``,
    ``_files_content_identical``, ``record_deploy_failure``, ``_write``) and
    shared ``_uptodate_count`` module state to function scope via a late
    ``import build_phases as _bp``, rather than a module-level
    ``from build_phases import ...`` — several unit tests
    (``unit_tests/test_build_workflow_phase.py``,
    ``unit_tests/test_build_workflow_output_paths.py``,
    ``unit_tests/test_workflow_variant_transform.py``, and four
    ``unit_tests/portability/test_ge_120e_*.py`` files) monkeypatch module
    attributes directly on ``build_phases``, and a module-level ``from ...
    import`` would bind a stale local copy that silently defeats the patch.

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
        raise ValueError(  # noqa: TRY003
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
    deterministic E2 top-level-body engine, per ADR-030 and ticket 09). The
    resolved engine is passed to ``_emit_workflow_variant``. Only ``"e2"`` and
    ``"auto"`` are supported; ``"e1"`` raises ``ValueError`` (the E1 wrap was
    removed in EPIC-DualEngineWorkflowSupport ticket 09 — it produced an
    unloadable ESM module).

    **Config injection (BP-900g-6)**: ``inject_config`` is applied to the
    (post-engine-transform) content of every ``.js`` file before it is written,
    exactly as ``build_workflows``/``build_commands``/``build_rules`` already do
    for their ``.md`` templates. This resolves ``{{config.output_root}}`` and
    other ``{{config.*}}`` placeholders so a workflow script can invoke
    ``{{config.output_root}}/scripts/...`` instead of a script path hardcoded to
    the default output root. Injection runs BEFORE the compare-before-write
    guard so a rendered-but-unchanged file still counts as up-to-date rather
    than as a fresh write on every run. Non-UTF-8 source content is written
    through unchanged (injection is skipped with a warning) rather than
    failing the whole phase.

    Applies the compare-before-write guard so that identical files are skipped
    on subsequent runs, satisfying the idempotency requirement.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary; reads ``config["workflows"]["enabled"]``
            and ``config["workflows"]["engine"]``, and supplies the values used
            to resolve ``{{config.*}}`` placeholders (notably ``output_root``).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of ``.js`` files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-05-22 [python-coder/EPIC-AntigravitySupport/01]: Updated build_workflows
    #   to iterate over active platforms defined in config["platforms"] and emit
    #   workflows to their respective target directories (e.g. .gemini/workflows/
    #   for antigravity, .claude/commands/ for claude). Defaults fall back to True
    #   for claude and antigravity.
    # - 2026-06-01 [python-coder/EPIC-FlattenSupervisorChain/01]: Added build_workflow_scripts()
    #   phase. Copies .js files from templates/workflows-js/ to target/.claude/workflows/.
    #   Dual-gate: opt-in flag (skills_config.json workflows.enabled, default false) and
    #   Claude Code version check (>= 2.1.154, via CLAUDE_CODE_VERSION env or subprocess).
    #   Below-minimum: warns and skips. Unknown version: warns and continues (fail-open).
    #   Compare-before-write guard prevents mtime churn on unchanged files. (#EPIC-FlattenSupervisorChain/01)
    # - 2026-06-04 [python-coder/TICKET-20260604-FixFailingBuildPipelineTests]:
    #   Fixed build_workflow_scripts() output path from target_root/"workflows" to
    #   target_root/".claude"/"workflows" to match .claude/ layout convention and
    #   fix unit_tests/test_build_workflow_phase.py assertions.
    #   (#TICKET-20260604-FixFailingBuildPipelineTests)
    # - 2026-07-02 [python-coder/EPIC-DualEngineWorkflowSupport/07]:
    #   build_workflow_scripts(): resolved "auto" → "e2" explicitly before
    #   calling _emit_workflow_variant (ADR-030: E2 is the default deterministic
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
    # - 2026-08-14 [BrainCandy/BP-900g-6]:
    #   Applied inject_config() to workflow .js content before writing. Workflow
    #   scripts invoke deployed Python scripts by path (setup_ticket_worktree.py,
    #   fast_lane.py, pause_store.py, mark_ac_done.py, ...); every such
    #   invocation was hardcoded to the literal "scripts/..." prefix, which is
    #   only correct when a consumer's configured output_root is the default
    #   ".leafcutter". Deploy paths are computed as
    #   "<output_root>/scripts/..." (see build_ac_store, build_agent_support_scripts),
    #   and output_root is documented as "configurable per consumer project" in
    #   config/skills_config.schema.json — so a hardcoded "scripts/..." prefix in
    #   a .js workflow silently breaks for any consumer who customises it.
    #   .md templates already resolve {{config.output_root}} via inject_config;
    #   .js workflows did not because build_workflow_scripts never called it —
    #   an identity byte-copy phase, not an oversight in inject_config itself.
    #   Rejected: hardcoding ".leafcutter/scripts/..." directly in the .js
    #   source. That reintroduces the exact per-consumer breakage this ticket
    #   fixes and duplicates a value the config system already owns; the
    #   {{config.output_root}} placeholder is the single source of truth other
    #   phases already use, and workflow scripts should not special-case that.
    #   Verified non-destructive before applying broadly: the only pre-existing
    #   "{{" occurrences in templates/workflows-js/ are JSDoc type annotations
    #   (e.g. "@returns {{ request: string ... }}", "{{skip:boolean, ...}}"),
    #   each followed by a space or a bare "key:" — neither matches
    #   _PLACEHOLDER_RE's "{{(?:config\\.)?[a-zA-Z0-9_.]+}}", so no prose was
    #   accidentally substituted. (#BP-900g-6)
    """
    import os
    import subprocess

    import build_phases as _bp
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
    # floor gate only and must NOT influence which engine is selected (ADR-030).
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
            _bp._log.warning("claude --version probe failed: %s", exc)
            version_str = None

    version_known = version_str is not None
    version_ok = False
    if version_str is not None:  # not `version_known`: mypy cannot narrow via a bool
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
    workflows_js_src = _bp.TEMPLATES_DIR / "workflows-js"
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
            _bp._log.warning(
                "Skipping %s: workflow transform failed (non-UTF-8 source): %s",
                js_file.name,
                exc,
            )
            continue

        # Apply config-placeholder injection (BP-900g-6) so tokens like
        # {{config.output_root}} resolve in deployed workflow scripts, the same
        # treatment build_workflows/build_commands/build_rules already give
        # .md templates. Runs BEFORE the compare-before-write guard below so an
        # unchanged rendered output still skips the write (idempotency
        # preserved). A non-UTF-8 source cannot be injected into and is copied
        # through unchanged (verbatim byte-for-byte, same as before this phase
        # gained injection).
        try:
            emitted = inject_config(emitted.decode("utf-8"), config).encode("utf-8")
        except UnicodeDecodeError as exc:
            _bp._log.warning(
                "Skipping config injection for %s (non-UTF-8 content): %s",
                js_file.name,
                exc,
            )

        if not _bp._should_overwrite(dest, force):
            continue

        # Compare-before-write guard (binary — SHA-256). This branch does NOT
        # route through _bp._files_content_identical() (it compares the
        # rendered `emitted` bytes to `dest`, not two on-disk files) —
        # ACD-2100d-2-i names it as the load-bearing fourth branch precisely
        # because of that: it is the path the route's own deployed copy
        # (.claude/workflows/*.js) takes, so it must call
        # _bp.announce_if_local_change_replaced() itself rather than relying
        # on instrumentation elsewhere.
        if dest.exists():
            import hashlib as _hashlib
            existing_digest = _hashlib.sha256(dest.read_bytes()).hexdigest()
            new_digest = _hashlib.sha256(emitted).hexdigest()
            if existing_digest == new_digest:
                _bp._uptodate_count += 1
                unchanged += 1
                continue
            _bp.announce_if_local_change_replaced(dest)

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
    import build_phases as _bp

    workflows_dir = _bp.TEMPLATES_DIR / "workflows"
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
            if _bp._write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  {output_subpath}/{template_file.name}")

    return written


def build_workflow_tools(target_root: Path, config: dict[str, Any],
                         dry_run: bool, force: bool) -> int:
    """Deploy workflow tool scripts to ``<target_root>/scripts/``.

    Copies workflow-tool Python scripts from the package source
    (``scripts/<name>.py``) to the consumer project's ``scripts/`` directory.
    These scripts are referenced by ticket-lifecycle agents, skills, and
    pre-commit hooks, but were not previously deployed by any build phase
    (Class B gap, EPIC-BuildGuardFalsePositive).

    Scripts deployed:

    - ``scripts/add_component.py`` — used by the add-component skill.
    - ``scripts/knowledge_query.py`` — used by the knowledge-query skill.
    - ``scripts/knowledge_frontmatter_reader.py`` — knowledge_query.py's
      sibling frontmatter/YAML reader module (KM-KGS-100a-3-xi); must ship
      alongside it or knowledge_query.py fails to import in consumers.
    - ``scripts/knowledge_file_nodes.py`` — knowledge_query.py's second
      sibling module (KM-KGS-100d-4), resolving file-path relationship
      values to path-keyed graph nodes; must also ship alongside it for the
      same reason.
    - ``scripts/knowledge_surface_check.py`` — knowledge_query.py's third
      sibling module (KM-KGS-100c-1/-i/-ii), the surface-set completeness
      check; loaded on demand by knowledge_query.check_surface_set() and
      must also ship alongside it.
    - ``scripts/set_ticket_status.py`` — used by ticket-lifecycle agents and skills.
    - ``scripts/ticket_prioritizer.py`` — used by the ticket-prioritizer skill.
    - ``scripts/port_registry.py`` — used by the live-surface-tester agent.
    - ``scripts/live_surface_startup.py`` — used by the live-surface-tester agent.
    - ``scripts/generate_doc_index.py`` — used by the transform-doc-index pre-commit hook.

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
    # - 2026-07-10 [claude/revive]: Added port_registry.py and
    #   live_surface_startup.py to the deploy list so the live-surface-tester
    #   agent's referenced scripts are deployed to consumers (registry-completeness
    #   build-guard). (#EPIC-LiveSurfaceTesting)
    # - 2026-07-15 [TICKET-20260715-DocIndexAutoRegen / defect-remediation]:
    #   Added generate_doc_index.py so the transform-doc-index pre-commit hook
    #   can import it in consumer projects. Previously absent from the deployed
    #   .leafcutter/scripts/ tree, making the hook a silent no-op outside the
    #   source tree. Parity with _manifest_workflow_tool_scripts() in build.py.
    # - 2026-09-17 12:00 [python-coder/KM-KGS-100a-3-xi]: Added
    #   knowledge_frontmatter_reader.py right after knowledge_query.py so the
    #   extracted reader module deploys side by side with it in every
    #   consumer install. (#TICKETLESS reason=km-kgs-100a-3-xi-fastlane)
    # - 2026-09-25 [python-coder/KM-KGS-100d-4 epic]: Added
    #   knowledge_file_nodes.py right after knowledge_frontmatter_reader.py --
    #   knowledge_query.py's second sibling module, loaded the same eager way
    #   at import time, so a consumer install missing it fails to import
    #   knowledge_query.py at all. (#TICKETLESS reason=km-fast-lane-file-nodes)
    # - 2026-09-25 15:16 [python-coder/KM-KGS-100c-1 surface-check]: Added
    #   knowledge_surface_check.py right after knowledge_file_nodes.py --
    #   knowledge_query.py's third sibling module, loaded on demand via
    #   _load_sibling_module() by check_surface_set(), so a consumer install
    #   missing it fails that call. (#TICKETLESS reason=km-kgs-100c-1-surface-check)
    """
    import shutil

    import build_phases as _bp

    scripts_src = _bp.PACKAGE_ROOT / "scripts"
    deploy_scripts = [
        "add_component.py",
        "knowledge_query.py",
        "knowledge_frontmatter_reader.py",
        "knowledge_file_nodes.py",
        "knowledge_surface_check.py",
        "set_ticket_status.py",
        "ticket_prioritizer.py",
        "port_registry.py",
        "live_surface_startup.py",
        "generate_doc_index.py",
    ]
    output_dir = target_root / "scripts"
    written = 0

    for script_name in deploy_scripts:
        src_file = scripts_src / script_name
        if not src_file.is_file():
            # BP-900g-9 (n_location_rule: all) — same warn-and-continue shape as
            # build_ac_store. Fixing only the loop the AC names leaves the
            # identical hole in its siblings.
            _bp.record_deploy_failure("build_workflow_tools", script_name, src_file)
            continue

        output_path = output_dir / script_name

        if not _bp._should_overwrite(output_path, force):
            continue

        if _bp._files_content_identical(src_file, output_path):
            _bp._uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/{script_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _bp._log.warning(
                    "build_workflow_tools: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/{script_name}")
            written += 1

    return written


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-22 [python-coder/EPIC-AntigravitySupport/01]: Updated build_workflows
#   to iterate over active platforms defined in config["platforms"] and emit
#   workflows to their respective target directories (e.g. .gemini/workflows/
#   for antigravity, .claude/commands/ for claude). Defaults fall back to True
#   for claude and antigravity.
# - 2026-06-01 [python-coder/EPIC-FlattenSupervisorChain/01]: Added build_workflow_scripts()
#   phase. Copies .js files from templates/workflows-js/ to target/.claude/workflows/.
#   Dual-gate: opt-in flag (skills_config.json workflows.enabled, default false) and
#   Claude Code version check (>= 2.1.154, via CLAUDE_CODE_VERSION env or subprocess).
#   Below-minimum: warns and skips. Unknown version: warns and continues (fail-open).
#   Compare-before-write guard prevents mtime churn on unchanged files. (#EPIC-FlattenSupervisorChain/01)
# - 2026-06-04 [python-coder/TICKET-20260604-FixFailingBuildPipelineTests]:
#   Fixed build_workflow_scripts() output path from target_root/"workflows" to
#   target_root/".claude"/"workflows" to match .claude/ layout convention and
#   fix unit_tests/test_build_workflow_phase.py assertions.
#   (#TICKET-20260604-FixFailingBuildPipelineTests)
# - 2026-07-02 [python-coder/EPIC-DualEngineWorkflowSupport/07]:
#   build_workflow_scripts(): resolved "auto" → "e2" explicitly before
#   calling _emit_workflow_variant (ADR-030: E2 is the default deterministic
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
# - 2026-09-14 [python-coder/bp-size-split]: Moved _emit_workflow_variant,
#   build_workflow_scripts, build_workflows, and build_workflow_tools
#   verbatim from build_phases.py into this new sibling module to bring
#   build_phases.py under the 400-counted-line check-file-size limit.
#   Re-exported from build_phases.py so build.py and every test import
#   keeps working. (#refactor/build-phases-size-limit)
# - 2026-09-14 [python-coder/KI-BP-20260831-0620]: Reapplied the mypy narrowing
#   fix to build_workflow_scripts() after the bp-size-split moved it here:
#   `if version_str is not None:` in place of `if version_known:` -- mypy
#   cannot narrow an Optional through an intermediate bool, so the widened
#   CI pathspec (this file now being checked for the first time) flagged
#   Version(version_str) as str | None where str is required. version_known
#   still holds the same value and is still consulted below; behaviour is
#   unchanged. (#KI-BP-20260831-0620)
# ===========================================================================
