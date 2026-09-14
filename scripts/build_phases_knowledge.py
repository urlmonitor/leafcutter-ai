"""
MODULE: build_phases_knowledge
GOAL: Deploy the knowledge-plane build phases (knowledge scripts + the
    knowledge-emission sink declaration) that were previously defined inline
    in build_phases.py.
BUSINESS CONTEXT: build_phases.py is grandfathered ~7x over the 400-content-line
    check-file-size limit (2753 lines at the time of this extraction), and the
    GE-127b-1 ratchet refuses any change that leaves an already-oversized file
    longer than it was. That was blocking two in-flight ACs
    (INF-400c-4-iii, adding a build phase, and INF-400c-4-i, needing a
    deploy-manifest entry) in the same file. This module carries the two most
    recently added, thematically-adjacent knowledge-plane phase functions out
    of build_phases.py to restore headroom, with no behaviour change.
ARCHITECTURE: Two public phase functions, re-exported from build_phases.py so
    every existing caller (notably build.py, which imports
    ``build_knowledge_scripts`` and ``build_knowledge_sink_declaration`` from
    ``build_phases``) keeps working unchanged — the same re-export pattern
    build_phases.py already uses for build_precommit_config from
    build_precommit.py. Both functions share the standard phase signature
    (target_root, config, dry_run, force) and defer their imports of
    build_phases's private write/deploy helpers (``PACKAGE_ROOT``,
    ``_should_overwrite``, ``_files_content_identical``, ``record_deploy_failure``,
    ``_write``) and shared ``_uptodate_count`` module state to function scope,
    to avoid a circular import at module load time (build_phases.py imports
    this module at its own top level).

    This module lives alongside build_phases.py, build_precommit.py, and
    template_compiler.py directly under ``scripts/`` in the leafcutter-ai
    package source. None of those "build engine" files are themselves copied
    anywhere by any build phase — a consumer install runs
    ``python leafcutter-ai/scripts/build.py --target-dir .`` directly against
    the cloned package source, and ``scripts/`` is already on ``sys.path`` at
    that point (the same mechanism that already makes the ``build_precommit``
    re-export work). So this module ships and resolves at import time exactly
    the way build_precommit.py already does, with no deploy-manifest entry
    required.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


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
    # - 2026-09-09 [python-coder/bp-extract]: Moved from build_phases.py (started
    #   line 3162) into this new sibling module, unchanged, to relieve the
    #   GE-127b-1 file-size ratchet blocking INF-400c-4-iii and INF-400c-4-i.
    #   Re-exported from build_phases.py so build.py's existing import keeps
    #   working. (#INF-400c-4-iii, #INF-400c-4-i)
    """
    import build_phases as _bp

    knowledge_src = _bp.PACKAGE_ROOT / "scripts" / "knowledge"
    deploy_scripts = ["harvest_learnings.py"]
    output_dir = target_root / "scripts" / "knowledge"
    written = 0

    for script_name in deploy_scripts:
        src_file = knowledge_src / script_name
        if not src_file.is_file():
            # BP-900g-9 (n_location_rule: all).
            _bp.record_deploy_failure("build_knowledge_scripts", script_name, src_file)
            continue

        output_path = output_dir / script_name

        if not _bp._should_overwrite(output_path, force):
            continue

        if _bp._files_content_identical(src_file, output_path):
            _bp._uptodate_count += 1
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


def build_knowledge_sink_declaration(target_root: Path, config: dict[str, Any],
                                      dry_run: bool, force: bool) -> int:
    """Declare this install's absolute knowledge-emission sink path.

    Writes ``config/knowledge_sink.json`` under the consolidated output root
    (bound to ``target_root`` here per the internal-phase calling convention
    -- see ``_run_phases``), recording the absolute path THIS build fixes as
    the project's knowledge-emission sink: ``<project_root>/debugging/logs/
    knowledge_emissions.jsonl``, where ``project_root`` is exactly one level
    above the consolidated output root this function itself was called with
    (``output_root == project_root / output_root_name``). This is
    deliberately the historical CWD-relative default's own path, anchored
    absolutely -- and deliberately NOT ``build_feedback``'s
    ``<output_root>/debugging/logs/`` (which that phase creates eagerly on
    every build): the sink is a durable operational log the project owns,
    not a build artifact that ``.leafcutter`` gets wiped and regenerated
    around, and its parent directory must not already exist merely because
    a build ran (AC INF-400c-4-v: obtainable without emitting or harvesting,
    and without conjuring anything into existence by asking).

    The path is derived ENTIRELY from ``target_root`` (an absolute argument
    ``build.py`` already resolved from ``--target-dir``) -- never discovered
    by walking the filesystem for a repository or marker file. This is what
    makes a nested consumer install's sink land at the consumer's own root
    and a workspace install's sink land beside the rest of that install's
    deployed content, rather than beside the package sources, in every
    install shape (AC INF-400c-4-v).

    AC INF-400c-4-iii: the SAME declaration also records
    ``operational_telemetry_stream``, the absolute path of the operational
    stream (``<project_root>/debugging/logs/agent_telemetry.jsonl``). One
    artefact names both streams so the knowledge-sink reader
    (``harvest_learnings.py``) and the operational-stream emitter
    (``emit_event.py``) share one anchor instead of each computing its own
    directory and silently drifting apart.

    A NOTE is always printed alongside the write: a build has no reliable way
    to tell whether the directory it was pointed at is an already-installed
    project's own root or a separate, isolated working directory of a
    DIFFERENT install that already has its own sink elsewhere, so every build
    states plainly which is being declared rather than silently doing the
    wrong one only some of the time (AC INF-400c-4-v: "a second sink produced
    in silence is the original defect restored in full").

    Args:
        target_root: Absolute path to the consolidated output directory
            (bound to ``output_root`` by ``_run_phases``'s internal-phase
            calling convention).
        config: Merged config dictionary (accepted for interface parity; not
            consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites an existing declaration.

    Returns:
        1 if the declaration was (or would be, in dry-run mode) written; 0
        when the on-disk declaration is already byte-identical (see
        ``_write``'s compare-before-write guard).

    # DECISION HISTORY
    # - 2026-09-07 [python-coder]: Added build_knowledge_sink_declaration(), a
    #   new internal-phase writing config/knowledge_sink.json under the
    #   consolidated output root: an absolute, build-time-fixed declaration of
    #   this install's knowledge-emission sink at <project_root>/debugging/logs/
    #   knowledge_emissions.jsonl. See build_phases.py's own DECISION HISTORY
    #   for the full original entry (this module did not exist yet).
    #   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-v)
    # - 2026-09-09 [python-coder/bp-extract]: Moved from build_phases.py (started
    #   line 3233, added by PR #743) into this new sibling module, unchanged,
    #   to relieve the GE-127b-1 file-size ratchet blocking INF-400c-4-iii and
    #   INF-400c-4-i. Re-exported from build_phases.py so build.py's existing
    #   import keeps working. (#INF-400c-4-iii, #INF-400c-4-i)
    # - 2026-09-09 [python-coder]: Extended to also write
    #   operational_telemetry_stream into the same config/knowledge_sink.json
    #   artefact (AC INF-400c-4-iii), naming the absolute, build-time-fixed
    #   operational-stream path (<project_root>/debugging/logs/agent_telemetry.jsonl)
    #   alongside the pre-existing knowledge_emission_sink key. This is the one
    #   artefact templates/skills/agent-telemetry/scripts/emit_event.py now reads
    #   for its own --log default, so the knowledge sink and the operational
    #   stream share one anchor instead of drifting as two independently-computed
    #   values. Authored against build_phases.py before PR #769 moved this
    #   function here; re-applied to the post-extraction text rather than
    #   replayed as a remembered diff.
    #   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-iii)
    """
    import build_phases as _bp

    project_root = target_root.parent
    sink_path = project_root / "debugging" / "logs" / "knowledge_emissions.jsonl"
    # AC INF-400c-4-iii: the operational/telemetry stream is declared in this
    # SAME artefact, one absolute path fixed at build time, so emit_event.py
    # (the operational-stream producer) and this knowledge-sink declaration
    # share one anchor instead of drifting as two independently-computed
    # values. Distinct filename, same directory as the historical default.
    operational_stream_path = project_root / "debugging" / "logs" / "agent_telemetry.jsonl"
    content = (
        json.dumps(
            {
                "knowledge_emission_sink": str(sink_path),
                "operational_telemetry_stream": str(operational_stream_path),
            },
            indent=2,
        )
        + "\n"
    )
    output_path = target_root / "config" / "knowledge_sink.json"

    if _bp._write(output_path, content, dry_run, force):
        print(f"  config/knowledge_sink.json -> {sink_path}")
        print(f"  config/knowledge_sink.json -> {operational_stream_path} (operational stream)")
        print(
            "  NOTE: this build declares the knowledge-emission SINK for "
            "THIS working directory. A separate, isolated working directory "
            "of a project that already has an install elsewhere gets its "
            "own, SECOND sink here rather than silently sharing the "
            "original -- see AC INF-400c-4-v."
        )
        return 1
    return 0


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-09 [python-coder/bp-extract]: Created this module by extracting
#   build_knowledge_scripts() and build_knowledge_sink_declaration() from
#   build_phases.py verbatim (no behaviour change). build_phases.py measured
#   2753 content lines (the check-file-size hook's own count) against a
#   400-line limit; the GE-127b-1 ratchet refuses any change that leaves an
#   already-oversized file longer than it was, which was blocking
#   INF-400c-4-iii (adds a build phase) and INF-400c-4-i (needs a
#   deploy-manifest entry in the same file) from committing. Re-exported both
#   names from build_phases.py (same pattern as build_precommit_config /
#   build_precommit.py) so build.py's existing
#   ``from build_phases import build_knowledge_scripts,
#   build_knowledge_sink_declaration`` keeps working unchanged.
#   (#INF-400c-4-iii, #INF-400c-4-i)
# ===========================================================================
