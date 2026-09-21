"""
MODULE: build_phases_script_deploy
GOAL: Deploy the agent-support, build-orchestration, and template-standalone
    script phases (plus their AGENT_SUPPORT_SCRIPT_DIRS /
    AGENT_SUPPORT_SCRIPT_FILES deploy declarations) that were previously
    defined inline in build_phases.py.
BUSINESS CONTEXT: These phases close Class B deploy gaps -- scripts referenced
    by deployed agent and skill templates that had no deploy phase and were
    therefore silently dead in every consumer install (BP-900g). This module
    carries three thematically-adjacent script-deploy phases out of
    build_phases.py to bring that file under the 400-counted-line
    check-file-size limit, with no behaviour change.
ARCHITECTURE: Three public phase functions -- build_agent_support_scripts,
    build_build_orchestration_scripts, build_template_standalone_scripts --
    plus their private helpers _copy_agent_support_file and
    _deploy_fast_lane_release_dependency, and the two module-level deploy
    declarations AGENT_SUPPORT_SCRIPT_DIRS / AGENT_SUPPORT_SCRIPT_FILES.
    Re-exported from build_phases.py so every existing caller (notably
    build.py, which imports AGENT_SUPPORT_SCRIPT_DIRS and
    AGENT_SUPPORT_SCRIPT_FILES to derive its deploy manifest, per the
    anti-drift Set B -> Set C guard) keeps working unchanged -- the same
    re-export pattern build_phases.py already uses for build_precommit_config
    from build_precommit.py and for build_knowledge_scripts /
    build_knowledge_sink_declaration from build_phases_knowledge.py. All
    three phase functions share the standard phase signature (target_root,
    config, dry_run, force) and defer their imports of build_phases's private
    write/deploy helpers (``PACKAGE_ROOT``, ``TEMPLATES_DIR``,
    ``_should_overwrite``, ``_files_content_identical``,
    ``record_deploy_failure``) and shared ``_uptodate_count`` module state to
    function scope, to avoid a circular import at module load time
    (build_phases.py imports this module at its own top level).
    build_agent_support_scripts() and _copy_agent_support_file() call each
    other directly as plain local references within this module, not through
    the deferred ``_bp`` import -- neither is shared with a phase that stays
    behind in build_phases.py.

    This module lives alongside build_phases.py, build_precommit.py,
    build_phases_knowledge.py, and template_compiler.py directly under
    ``scripts/`` in the leafcutter-ai package source. None of those "build
    engine" files are themselves copied anywhere by any build phase -- a
    consumer install runs ``python leafcutter-ai/scripts/build.py
    --target-dir .`` directly against the cloned package source, and
    ``scripts/`` is already on ``sys.path`` at that point (the same mechanism
    that already makes the ``build_precommit`` and ``build_phases_knowledge``
    re-exports work). So this module ships and resolves at import time
    exactly the way those two already do, with no deploy-manifest entry
    required.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Agent-support script deploy spec (AC BP-900g-5)
# ---------------------------------------------------------------------------
# Scripts referenced by deployed agent and skill templates that had no deploy
# phase and were therefore silently dead in every consumer install. They were
# invisible to the reference guard until BP-900g-4 taught the extractor to see
# output-root-form references.
#
# This is the SINGLE source of truth for the phase below and for
# _manifest_agent_support_scripts() in build.py, which imports it. The two must
# not be allowed to drift — a manifest that disagrees with what is actually
# deployed is precisely the BP-900g-4 defect.
#
# Directories deploy recursively (every .py), which also carries sibling modules
# an entry point imports. Single files list any same-directory module they load
# at import time explicitly, because a missing one fails at runtime, not here.

AGENT_SUPPORT_SCRIPT_DIRS: tuple[str, ...] = (
    # changelog-agent.md, epic-supervisor.md, build-single-ticket/SKILL.md
    "changelog",
    # retrospective-agent.md
    "retrospective",
    # retrospective-agent.md — generate_health_report.py sits next to
    # agent_telemetry.py, so the directory deploys as a unit.
    "agent-health",
)

AGENT_SUPPORT_SCRIPT_FILES: tuple[str, ...] = (
    # architect-review.md, architecture-diagram-author.md
    "next_diagram_seq.py",
    # roadmap-query/SKILL.md, roadmap-steward/SKILL.md
    "roadmap_query.py",
    # NOT referenced by any template directly, but roadmap_query.py loads it via
    # importlib at MODULE SCOPE (spec_from_file_location against its own parent
    # directory), so roadmap_query.py cannot even be imported without it.
    "roadmap_query_audit.py",
    # package-audit/SKILL.md
    "package_audit.py",
    # plan-feature.js / finalize-feature.js invoke this at every interactive
    # gate (read/write pause-resume records). No deploy phase shipped it before
    # BP-900g-6, so both workflows died at their first gate in a consumer
    # install. Module-scope imports are stdlib only (argparse, json, logging,
    # subprocess, sys, time) — no sibling module to co-deploy.
    "pause_store.py",
    # fast-lane-ship.js's context-bundle dispatch (BO-2400c-1-ii/-iii) invokes
    # this module's `assemble-bundle` CLI subcommand once per run to build the
    # layered LLM context bundle (assemble_context_bundle) — the live lane's
    # only production call site as of BO-2400c-1. A second runner,
    # fast-lane-build.js, once referenced this module too, but was an orphan
    # nothing dispatched (KI-BO-005: no CLI entry point existed, so the call was
    # a silent no-op); it was never this deploy justification and was deleted
    # under BO-2400c-1-v.
    # No deploy phase shipped this file before BP-900g-6. Module-scope imports
    # are stdlib only (argparse, json, logging, sys, pathlib, typing) — no
    # sibling module to co-deploy.
    "injection_builders.py",
    # ACD-2100b-5: templates/skills/plan-feature/SKILL.md's pre-flight
    # invokes this script (by its deployed path) before the plan-feature
    # workflow starts. No deploy phase shipped scripts/worktree/ before this,
    # so the deployed skill would have found nothing there. Listed as a
    # single file (not the whole scripts/worktree/ directory) because its
    # sibling sweep_processes.py/__init__.py import scripts/config_loader.py,
    # which no phase deploys — pulling in the whole directory here would trip
    # the intra-package closure guard (AC BP-900g-8) over an unrelated,
    # pre-existing gap. This script's own module-scope imports are stdlib
    # only (argparse, json, logging, subprocess, sys, pathlib) — no sibling
    # module to co-deploy.
    "worktree/check_workspace_setup_permission.py",
)


def build_agent_support_scripts(target_root: Path, config: dict[str, Any],
                                dry_run: bool, force: bool) -> int:
    """Deploy agent-support scripts to ``<target_root>/scripts/``.

    Copies the directories in ``AGENT_SUPPORT_SCRIPT_DIRS`` (recursively, all
    ``.py``) and the individual files in ``AGENT_SUPPORT_SCRIPT_FILES`` from the
    package ``scripts/`` tree, preserving relative layout so that
    ``scripts/<name>`` in a template resolves to the same path in the consumer
    install.

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
    # - 2026-08-14 [BrainCandy/BP-900g-5]:
    #   Added build_agent_support_scripts() phase, emptying KNOWN_UNDEPLOYED_ALLOWLIST.
    #   Six agent capabilities (changelog-agent, retrospective-agent,
    #   architect-review, the roadmap skills, package-audit) referenced scripts that
    #   no phase deployed, so they failed at their first command in every consumer
    #   install. Driven off a module-level spec that build.py's manifest helper
    #   imports, so the deployed set and the declared set cannot diverge.
    #   (#BP-900g-5)
    # - 2026-08-14 [BrainCandy/BP-900g-6]:
    #   Added pause_store.py and injection_builders.py to AGENT_SUPPORT_SCRIPT_FILES.
    #   Both are referenced (via {{config.output_root}}/scripts/...) by the
    #   plan-feature.js and finalize-feature.js pause-resume gates and by the
    #   fast-lane-build.js context-assembly step, but presence-checked source
    #   files only pass this guard if they are also reachable from a deployed
    #   consumer tree — no phase shipped either script before this. Checked
    #   both for module-scope imports of undeployed siblings (the ac_parent_id.py
    #   lesson from BP-900g-4): neither has one — both import stdlib only.
    #   (#BP-900g-6)
    """
    import build_phases as _bp

    scripts_src = _bp.PACKAGE_ROOT / "scripts"
    written = 0

    for dir_name in AGENT_SUPPORT_SCRIPT_DIRS:
        src_dir = scripts_src / dir_name
        if not src_dir.is_dir():
            # BP-900g-9 (n_location_rule: all). A declared source DIRECTORY
            # going missing is the same dropped promise as a declared file:
            # was warn-and-continue, which let it vanish from the deployed
            # tree while the build exited 0. Record and keep going so one
            # run reports the whole remediation set; build.py raises once at
            # the end.
            _bp.record_deploy_failure("build_agent_support_scripts", dir_name, src_dir)
            continue
        for src_file in sorted(src_dir.rglob("*.py")):
            rel = src_file.relative_to(scripts_src).as_posix()
            written += _copy_agent_support_file(src_file, target_root, rel, dry_run, force)

    for file_name in AGENT_SUPPORT_SCRIPT_FILES:
        src_file = scripts_src / file_name
        if not src_file.is_file():
            # BP-900g-9 (n_location_rule: all). Note this guards the DECLARED
            # AGENT_SUPPORT_SCRIPT_FILES list only; the rglob loop just above
            # iterates what exists on disk, where a missing file is not a
            # dropped promise and must stay a skip.
            _bp.record_deploy_failure("build_agent_support_scripts", file_name, src_file)
            continue
        written += _copy_agent_support_file(
            src_file, target_root, file_name, dry_run, force
        )

    return written


def _copy_agent_support_file(src_file: Path, target_root: Path, rel: str,
                             dry_run: bool, force: bool) -> int:
    """Copy one agent-support script to ``<target_root>/scripts/<rel>``.

    Args:
        src_file: Absolute path to the source script.
        target_root: Absolute path to the target project root directory.
        rel: Path of the script relative to the package ``scripts/`` directory.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites an existing file.

    Returns:
        1 when a file was written (or would be in dry-run mode), else 0.
    """
    import build_phases as _bp

    output_path = target_root / "scripts" / rel

    if not _bp._should_overwrite(output_path, force):
        return 0

    if _bp._files_content_identical(src_file, output_path):
        _bp._uptodate_count += 1
        return 0

    if dry_run:
        print(f"  [DRY-RUN] would copy scripts/{rel}")
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, output_path)
    except OSError as exc:
        _bp._log.warning(
            "build_agent_support_scripts: failed to copy %s → %s: %s",
            src_file,
            output_path,
            exc,
        )
        raise
    print(f"  scripts/{rel}")
    return 1


def build_build_orchestration_scripts(target_root: Path, config: dict[str, Any],
                                      dry_run: bool, force: bool) -> int:
    """Deploy build-orchestration scripts to ``<target_root>/scripts/build_orchestration/``.

    Copies every ``.py`` file from the package's ``scripts/build_orchestration/``
    to the consumer project.  ``fast_lane.py`` is invoked directly by the build-ac
    agent at Step 2b.1 (``select_connected``); before this phase existed no build
    phase deployed the directory, so the deployed agent died at that command with
    "can't open file" while build.py itself exited 0 (Class B deploy gap, the same
    shape ``build_knowledge_scripts`` closed for ``harvest_learnings.py``).

    The whole directory is deployed rather than just ``fast_lane.py`` so that
    sibling-module imports keep resolving.  ``fast_lane.py`` reaches its
    ``ac_store`` helpers via ``Path(__file__).parent.parent / "ac_store"``, which
    resolves correctly in the deployed tree because ``build_ac_store`` deploys
    ``scripts/ac_store/`` alongside it.

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
    # - 2026-08-14 [BrainCandy/BP-900g-4]:
    #   Added build_build_orchestration_scripts() phase. Deploys .py files from
    #   scripts/build_orchestration/ to consumer scripts/build_orchestration/.
    #   Closes the deploy gap that made /build-ac fail at Step 2b.1 in every
    #   consumer install. Scans the directory dynamically rather than using a
    #   hardcoded file list, so a new module added there cannot silently go
    #   undeployed. (#BP-900g-4)
    """
    import build_phases as _bp

    src_dir = _bp.PACKAGE_ROOT / "scripts" / "build_orchestration"
    output_dir = target_root / "scripts" / "build_orchestration"
    written = 0

    if not src_dir.is_dir():
        # BP-900g-9 (n_location_rule: all). This is the phase's OWN declared
        # source directory, not a glob of what happens to exist on disk — its
        # absence is a dropped promise, the same shape already closed for the
        # sibling loops above. Record it and skip ONLY the glob loop below —
        # do NOT return early. This function has a SECOND declared dependency,
        # `_deploy_fast_lane_release_dependency()`, and accumulate-then-raise
        # exists precisely so both absences are recorded from ONE run instead
        # of trickling out one per build-fix-build cycle (that was the bug:
        # an early `return 0` here skipped the call below on the same pass).
        _bp.record_deploy_failure(
            "build_build_orchestration_scripts", "scripts/build_orchestration", src_dir
        )
    else:
        for src_file in sorted(src_dir.glob("*.py")):
            if not src_file.is_file():
                continue

            output_path = output_dir / src_file.name

            if not _bp._should_overwrite(output_path, force):
                continue

            if _bp._files_content_identical(src_file, output_path):
                _bp._uptodate_count += 1
                continue

            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/build_orchestration/{src_file.name}")
                written += 1
            else:
                try:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, output_path)
                except OSError as exc:
                    _bp._log.warning(
                        "build_build_orchestration_scripts: failed to copy %s → %s: %s",
                        src_file,
                        output_path,
                        exc,
                    )
                    raise
                print(f"  scripts/build_orchestration/{src_file.name}")
                written += 1

    written += _deploy_fast_lane_release_dependency(target_root, dry_run, force)

    return written


def _deploy_fast_lane_release_dependency(target_root: Path, dry_run: bool,
                                         force: bool) -> int:
    """Deploy ``check_changelog_presence.py`` to ``<target>/scripts/release/``.

    ``fast_lane.py`` imports ``check_changelog_presence`` at MODULE SCOPE
    (KI-BO-001 / BO-2400f-4-i: the module is imported rather than its
    ``EXEMPT_PREFIXES`` list, so the changelog-requirement decision re-reads the
    merge check's own rule at call time instead of freezing a copy). It reaches
    it by putting ``<scripts>/release`` on ``sys.path``.

    Nothing else deploys ``scripts/release/``. Without this, the deployed
    ``fast_lane.py`` is present but dies at import with ``ModuleNotFoundError:
    No module named 'check_changelog_presence'`` — which kills the whole module,
    not just the changelog path, so ``select_connected``, ``mark_done`` and both
    lean gates go with it and the fast lane is inert in every consumer install.

    This is the ``ac_parent_id.py`` situation exactly (see ``build_ac_store``'s
    deploy_map), and the same class ``done_proof.py`` hit before it: a
    file-presence check cannot catch it, only executing the deployed copy can.
    Caught by BP-900g-4's deployed-execution test, which is why that test exists.

    Args:
        target_root: Absolute path to the target project root directory.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites an existing file.

    Returns:
        1 when the file was written (or would be in dry-run mode), else 0.
    """
    import build_phases as _bp

    src_file = _bp.PACKAGE_ROOT / "scripts" / "release" / "check_changelog_presence.py"
    output_path = target_root / "scripts" / "release" / "check_changelog_presence.py"

    if not src_file.is_file():
        # BP-900g-9 (n_location_rule: all). A single declared path rather than a
        # loop, but the same promise: fast_lane.py's release dependency is
        # declared, so its absence is a dropped promise, not a skip.
        _bp.record_deploy_failure(
            "build_build_orchestration_scripts",
            "scripts/release/check_changelog_presence.py",
            src_file,
        )
        return 0

    if not _bp._should_overwrite(output_path, force):
        return 0

    if _bp._files_content_identical(src_file, output_path):
        _bp._uptodate_count += 1
        return 0

    if dry_run:
        print("  [DRY-RUN] would copy scripts/release/check_changelog_presence.py")
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, output_path)
    except OSError as exc:
        _bp._log.warning(
            "build_build_orchestration_scripts: failed to copy %s → %s: %s",
            src_file,
            output_path,
            exc,
        )
        raise

    print("  scripts/release/check_changelog_presence.py")
    return 1


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
    import build_phases as _bp

    templates_scripts_src = _bp.TEMPLATES_DIR / "scripts"
    if not templates_scripts_src.exists():
        return 0

    output_dir = target_root / "scripts"
    written = 0

    # Shallow scan — only top-level .py files; subdirectories have their own phases
    for src_file in sorted(templates_scripts_src.glob("*.py")):
        if not src_file.is_file():
            continue

        output_path = output_dir / src_file.name

        if not _bp._should_overwrite(output_path, force):
            continue

        if _bp._files_content_identical(src_file, output_path):
            _bp._uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/{src_file.name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _bp._log.warning(
                    "build_template_standalone_scripts: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/{src_file.name}")
            written += 1

    return written


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved the agent-support, build-
#   orchestration and template-standalone script deploy phases (plus their
#   AGENT_SUPPORT_SCRIPT_DIRS / AGENT_SUPPORT_SCRIPT_FILES deploy
#   declarations) verbatim from build_phases.py into this new sibling module
#   to bring build_phases.py under the 400-counted-line check-file-size
#   limit. Re-exported from build_phases.py so build.py's manifest
#   derivation and every test import keeps working. (#refactor/build-phases-size-limit)
# - 2026-08-31 [python-coder]: Fixed a BP-900g-9 review finding.
#   build_build_orchestration_scripts()'s own fail-closed branch did
#   `record_deploy_failure(...); return 0` when its declared source directory
#   was absent -- correct for that check alone, but the early return also
#   skipped the call to _deploy_fast_lane_release_dependency() that follows
#   it in the SAME function, so when BOTH declared sources were absent only
#   one failure was recorded per build instead of both -- one
#   build-fix-build cycle per source rather than both surfacing together.
#   Guarded the glob loop with `else:` instead of returning early so the
#   fast-lane dependency check always runs; corrected the in-code comment
#   that had justified the old early return. Added
#   test_bp_900g_9_build_orchestration_and_fast_lane_dependency_both_named_in_one_run
#   to unit_tests/test_bp_900g_9.py; confirmed it fails on the pre-fix code
#   via a `git stash` of this file. (#BP-900g-9)
# - 2026-09-21 [python-coder/EPIC-StartingNewWorkTheProperWayAlways]: Ported
#   the ACD-2100b-5 entry ("worktree/check_workspace_setup_permission.py")
#   into AGENT_SUPPORT_SCRIPT_FILES. It existed on the branch's pre-split
#   build_phases.py but was absent from main's file-size-ratchet refactor
#   (GE-127b-1), which took this module's shape from an earlier branch state
#   that predated ACD-2100b-5. Without it, the deployed plan-feature skill's
#   workspace-setup pre-flight (invoked by its deployed path) is dead in
#   every consumer install. Carried the file's own single-file-not-directory
#   justification across unchanged: its siblings import
#   scripts/config_loader.py, which no phase deploys, so pulling in the whole
#   scripts/worktree/ directory would trip the intra-package closure guard
#   (AC BP-900g-8) over an unrelated, pre-existing gap. (#ACD-2100b-5)
# ===========================================================================
