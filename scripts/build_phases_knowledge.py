"""
MODULE: build_phases_knowledge
GOAL: Deploy the knowledge-plane build phases (knowledge scripts + the
    knowledge-emission sink declaration) that were previously defined inline
    in build_phases.py, and hold the deploy-manifest helpers that describe
    what those phases (plus one other) ship.
BUSINESS CONTEXT: build_phases.py is grandfathered ~7x over the 400-content-line
    check-file-size limit (2753 lines at the time of this extraction), and the
    GE-127b-1 ratchet refuses any change that leaves an already-oversized file
    longer than it was. That was blocking two in-flight ACs
    (INF-400c-4-iii, adding a build phase, and INF-400c-4-i, needing a
    deploy-manifest entry) in the same file. This module carries the two most
    recently added, thematically-adjacent knowledge-plane phase functions out
    of build_phases.py to restore headroom, with no behaviour change.

    scripts/build.py (a SEPARATE file, also grandfathered over its own
    check-file-size limit) later hit the same GE-127b-1 refusal for a
    legitimate +18-line deploy-manifest fix (AC INF-400c-5, H-1). That fix
    could not fund its own growth from budget elsewhere, so
    ``_manifest_knowledge_scripts`` -- the deploy-manifest helper describing
    exactly what ``build_knowledge_scripts`` above ships -- moved here
    alongside the phase it describes (its natural home, not merely a place to
    shed lines). ``_manifest_workflow_tool_scripts`` moved in the SAME commit,
    as a whole, self-contained function of the same kind, because the
    knowledge helper alone did not recover enough of build.py's own budget.
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

    ``_manifest_knowledge_scripts`` and ``_manifest_workflow_tool_scripts``
    are imported DIRECTLY by build.py (``from build_phases_knowledge import
    _manifest_knowledge_scripts, _manifest_workflow_tool_scripts``), not
    re-exported through build_phases.py — scripts/build_phases.py was
    intentionally left untouched by this extraction. Both are self-contained
    (package_root in, a set[str] out; no dependency on build_phases's private
    state), so unlike the two phase functions above they need no deferred
    import to avoid a circular-import at module load time.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)


def build_knowledge_scripts(target_root: Path, config: dict[str, Any],
                             dry_run: bool, force: bool) -> int:
    """Deploy knowledge scripts + the entry_kind vocabulary config.

    Copies ``scripts/knowledge/harvest_learnings.py``,
    ``scripts/knowledge/emit_knowledge.py``, and
    ``scripts/knowledge/entry_kind_vocabulary.py`` from the package source to
    the consumer project's ``<target_root>/scripts/knowledge/``, then copies
    the static ``config/entry_kind_vocabulary.json`` declaration to
    ``<target_root>/config/entry_kind_vocabulary.json`` -- mirroring
    ``build_feedback``'s ``config/feedback_categories.yaml`` deployment (a
    static asset copied alongside its scripts in the same phase), NOT
    ``build_knowledge_sink_declaration``'s pattern (which GENERATES its JSON
    content per-install; this vocabulary file is a fixed, tracked source
    asset with no install-specific values, so a verbatim copy is correct).

    ``harvest_learnings.py`` was previously the only script deployed here
    (Class B gap, EPIC-BuildGuardFalsePositive/03). ``emit_knowledge.py`` and
    ``entry_kind_vocabulary.py`` are added per AC INF-400c-5's H-1 fix: a
    fast-lane pr-review found both new scripts AND their JSON config were
    absent from every deploy manifest, so a fresh ``build.py`` run left a
    shipped emit surface invoking ``emit_knowledge.py`` failing on a missing
    file, or ImportError-ing on its missing sibling module, or silently
    rejecting every ``entry_kind`` once ``load_vocabulary()`` found no config
    and returned ``{}``.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode),
        across both the scripts/knowledge/ scripts and the vocabulary config.

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
    # - 2026-09-14 [python-coder/INF-400c-5, H-1 fix]: A fast-lane pr-review
    #   found the fast-lane build of INF-400c-5/-i/-iii had authored
    #   scripts/knowledge/emit_knowledge.py, scripts/knowledge/
    #   entry_kind_vocabulary.py, and config/entry_kind_vocabulary.json but
    #   never added any of the three to a deploy manifest, so all three were
    #   silently absent after any ``build.py`` run -- invisible to the 120
    #   green tests because every one of them resolved these paths via
    #   ``_REPO_ROOT`` (the source tree), never a deployed ``target_root``.
    #   Added the two new scripts to this phase's deploy list and the JSON
    #   config as a static-asset copy (build_feedback's
    #   config/feedback_categories.yaml pattern), and registered all three in
    #   scripts/build.py's ``_manifest_knowledge_scripts()`` and
    #   ``_get_source_deployable_scripts`` / ``_get_source_paths_for_guard``
    #   core-config tuples (the closure guard would otherwise abort every
    #   build once it started analysing ``entry_kind_vocabulary.py``'s own
    #   ``Path(__file__)``-rooted reference to the JSON file -- see build.py's
    #   own DECISION HISTORY for that half of the fix).
    #   (#TICKETLESS reason=fast-lane-pr-review-fix-INF-400c-5-H1)
    """
    import build_phases as _bp

    knowledge_src = _bp.PACKAGE_ROOT / "scripts" / "knowledge"
    deploy_scripts = [
        "harvest_learnings.py",
        "emit_knowledge.py",
        "entry_kind_vocabulary.py",
        "harvest_result.py",
        "sink_resolution.py",
        "capture_write.py",
        "harvest_cli.py",
    ]
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

    # AC INF-400c-5, H-1 fix: the static entry_kind vocabulary declaration --
    # a fixed, tracked source asset with no install-specific values (unlike
    # config/knowledge_sink.json, which build_knowledge_sink_declaration()
    # GENERATES per-install) -- so it is copied verbatim, mirroring
    # build_feedback's config/feedback_categories.yaml deployment.
    vocab_src = _bp.PACKAGE_ROOT / "config" / "entry_kind_vocabulary.json"
    if vocab_src.is_file():
        vocab_output = target_root / "config" / "entry_kind_vocabulary.json"
        vocab_text = vocab_src.read_text(encoding="utf-8")
        if _bp._write(vocab_output, vocab_text, dry_run, force):
            written += 1
            if not dry_run:
                print("  config/entry_kind_vocabulary.json")
    else:
        # BP-900g-9 (n_location_rule: all).
        _bp.record_deploy_failure(
            "build_knowledge_scripts", "entry_kind_vocabulary.json", vocab_src
        )

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


def check_knowledge_routing_wiring(
    workflows_dir: Path, guardrail_config: dict[str, Any]
) -> dict[str, list[str]]:
    """Report which deployed workflow artefacts lack a knowledge-routing declaration.

    Build-time guard for AC INF-700a-1-i ("no way of finishing work is left
    quietly without a routing step"). Enumerates every ``*.js`` file directly
    under ``workflows_dir`` (the candidate set is ALWAYS derived from the real
    artefacts on disk, never from the config -- a candidate set read from the
    config is the hand-maintained copy the AC forbids, and it goes stale the
    first time a completion path is added, which is the exact event this
    guard exists to catch) and checks each name against
    ``guardrail_config["knowledge_routing_wiring"]``'s two declared lists:
    ``wired`` (a flat list of file names) and ``excluded`` (a list of
    ``{"path": ..., "reason": ...}`` dicts, one entry per deliberately-unwired
    path). Mirrors ``check_command_reachability``'s "verdicts empty means ok"
    contract, one layer down: here the caller checks ``result["unwired"]``.

    Args:
        workflows_dir: Absolute path to the directory holding the real
            workflow ``.js`` artefacts (e.g. ``templates/workflows-js/``).
        guardrail_config: The parsed ``config/guardrail_gates.yaml`` mapping
            (or any dict carrying the same ``knowledge_routing_wiring``
            shape) -- read for its ``wired``/``excluded`` declarations only.
            An absent or malformed section is treated as declaring nothing
            wired and nothing excluded, so every real artefact reports as
            unwired -- fail closed, never fail silent.

    Returns:
        ``{"examined": [<names examined, sorted>], "unwired": [<names
        neither wired nor excluded>]}``. An empty ``"unwired"`` list is the
        "build may proceed" verdict.

    Pure function relative to its arguments: the only filesystem access is
    listing ``workflows_dir`` (a directory-listing glob, not a content read),
    matching this module's existing ``check_command_reachability`` precedent
    of leaving directory enumeration unwrapped and reserving try/except for
    actual file reads.

    # DECISION HISTORY
    # - 2026-09-14 [python-coder/INF-700a-1-i]: Added check_knowledge_routing_wiring()
    #   as the enumerate-from-artefacts half of the anti-partial-wiring guard;
    #   build.py wires it as a post-deploy abort gate mirroring
    #   _check_command_reachability_guard's existing shape.
    #   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700a-1-i)
    """
    examined = sorted(p.name for p in workflows_dir.glob("*.js"))

    section = guardrail_config.get("knowledge_routing_wiring")
    section = section if isinstance(section, dict) else {}

    wired_names = section.get("wired")
    wired = set(wired_names) if isinstance(wired_names, list) else set()

    excluded_entries = section.get("excluded")
    excluded_entries = excluded_entries if isinstance(excluded_entries, list) else []
    excluded = {
        entry.get("path")
        for entry in excluded_entries
        if isinstance(entry, dict) and entry.get("path")
    }

    unwired = [name for name in examined if name not in wired and name not in excluded]
    return {"examined": examined, "unwired": unwired}


def describe_knowledge_routing_examination(result: dict[str, list[str]]) -> str:
    """Render the residual-disclosure message required on a PASSING guard run.

    AC INF-700a-1-i's residual clause: a workflow-artefact-only guard cannot
    see a completion path shipped only as a skill or only as a command, and
    "the detection says which kinds of artefact it examined and which kinds
    it cannot see, in its own output" -- on a PASSING run specifically, so a
    reader of a green build never concludes every future way of completing
    work is covered. This guard's candidate set (see
    ``check_knowledge_routing_wiring`` above) is a glob over
    ``templates/workflows-js/*.js``; it structurally cannot enumerate a
    completion path that carries no ``.js`` workflow artefact -- one shipped
    only as a skill (``templates/skills/*/SKILL.md``) or only as a command
    (``templates/commands/*.md``).

    Args:
        result: The dict returned by ``check_knowledge_routing_wiring()``,
            read here only for its ``"examined"`` list (file names, already
            sorted).

    Returns:
        A two-line disclosure string: the examined artefact kind (with its
        count and names) and the artefact kinds this guard cannot see.

    # DECISION HISTORY
    # - 2026-09-14 [python-coder/INF-700a-1-i-H1]: Added on pr-reviewer
    #   finding H-1: the guard printed nothing on its passing path, so a
    #   green build implied coverage (of skill-only / command-only
    #   completion paths) it structurally does not have. Kept as its own
    #   pure function -- and out of scripts/build.py -- because build.py is
    #   already at its file-size ratchet ceiling; build.py only calls this
    #   and prints the result.
    """
    examined = result.get("examined", [])
    examined_desc = ", ".join(examined) if examined else "(none found)"
    return (
        "[KNOWLEDGE ROUTING GUARD] examined artefact kind: workflow "
        f"(templates/workflows-js/*.js) -- {len(examined)} examined: {examined_desc}\n"
        "[KNOWLEDGE ROUTING GUARD] cannot see artefact kinds: skill "
        "(templates/skills/*/SKILL.md), command (templates/commands/*.md) -- "
        "a completion path shipped only as one of these carries no workflow "
        "artefact and is outside this guard's enumeration; this passing run "
        "does not vouch for that residual."
    )


def check_knowledge_routing_wiring_guard(output_root: Path) -> int:
    """Post-deploy guard: abort the build when a completion path is neither wired nor excluded (AC INF-700a-1-i).

    Mirrors ``build.py``'s ``_check_command_reachability_guard`` existing
    shape: enumerate real artefacts, abort on an unlisted one. The candidate
    set is derived from the PACKAGE SOURCE's ``templates/workflows-js/*.js``
    (per this AC's own it_requirements: "THE ENUMERATION DERIVES FROM THE
    ARTEFACTS"), not from any deployed copy -- those artefacts are what a
    build ships, regardless of which platforms it deploys workflow scripts
    to. The declared wiring/exclusion lists are read from the DEPLOYED
    ``<output_root>/config/guardrail_gates.yaml`` so this guard is checking
    exactly the policy the build just produced.

    Args:
        output_root: Absolute path to the consolidated, already-deployed
            output directory (e.g. ``<target>/.leafcutter``).

    Returns:
        0 if every real workflow artefact is wired or excluded (build may
        proceed). 1 if one or more artefacts are unwired (build must abort).

    # DECISION HISTORY
    # - 2026-09-14 [python-coder/INF-700a-1-i]: Added
    #   _check_knowledge_routing_wiring_guard() in build.py, wired as a
    #   post-deploy abort gate mirroring _check_command_reachability_guard's
    #   existing shape.
    #   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700a-1-i)
    # - 2026-09-14 [python-coder/inf-700a-1]: Moved from build.py (unchanged
    #   behaviour, dropped the leading underscore since it now lives in a
    #   sibling module) to relieve the GE-127b-1 file-size ratchet blocking
    #   this ticket -- build.py measured 1976 content lines against a
    #   1915-line ceiling. Uses the same deferred ``import build_phases as
    #   _bp`` pattern this module's other functions use for PACKAGE_ROOT, to
    #   avoid the circular import build_phases.py's own top-level import of
    #   this module would otherwise create. build.py's ``main()`` keeps the
    #   call site, now importing this function by name instead of defining
    #   it locally.
    #   (#TICKETLESS reason=ac-scoped-fastlane-build-inf-700a-1)
    """
    guardrail_config_path = output_root / "config" / "guardrail_gates.yaml"
    if not guardrail_config_path.is_file():
        # Nothing deployed to check against yet (e.g. a minimal/partial
        # build that skips build_ac_store). Fail closed would block builds
        # that never had this policy file to begin with; there is nothing
        # for this guard to police in that case.
        return 0

    try:
        guardrail_config = yaml.safe_load(
            guardrail_config_path.read_text(encoding="utf-8")
        ) or {}
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"[KNOWLEDGE ROUTING GUARD] Could not read {guardrail_config_path}: {exc}",
            file=sys.stderr,
        )
        return 1

    import build_phases as _bp

    workflows_dir = _bp.PACKAGE_ROOT / "templates" / "workflows-js"
    if not workflows_dir.is_dir():
        return 0

    result = check_knowledge_routing_wiring(workflows_dir, guardrail_config)
    unwired = result.get("unwired", [])
    if not unwired:
        # AC INF-700a-1-i residual clause: disclose on the PASSING path too.
        print(describe_knowledge_routing_examination(result))
        return 0

    print(
        "[KNOWLEDGE ROUTING GUARD] Build aborted: workflow artefact(s) with "
        "no knowledge-routing declaration detected.",
        file=sys.stderr,
    )
    for name in unwired:
        print(
            f"[KNOWLEDGE ROUTING GUARD]  artefact: templates/workflows-js/{name}\n"
            "[KNOWLEDGE ROUTING GUARD]  reason:   neither listed under "
            "knowledge_routing_wiring.wired nor knowledge_routing_wiring.excluded "
            "in config/guardrail_gates.yaml",
            file=sys.stderr,
        )
    return 1


def _manifest_knowledge_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/knowledge/<name>`` entries for knowledge scripts deployed by build_knowledge_scripts.

    AC INF-400c-5, H-1 fix: ``emit_knowledge.py`` and
    ``entry_kind_vocabulary.py`` were authored alongside ``harvest_learnings.py``
    but never added here, so a fast-lane pr-review found both silently absent
    from every deployed install. Must be kept in parity with
    ``build_knowledge_scripts()``'s own ``deploy_scripts`` list above -- a
    mismatch trips the manifest/deploy parity guard.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/knowledge/<name>`` strings for deployable knowledge scripts.

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]: Added to
    #   scripts/build.py, deriving the deployable-scripts manifest entry for
    #   harvest_learnings.py.
    # - 2026-09-14 [python-coder/INF-400c-5, H-1 fix]: Extended with
    #   emit_knowledge.py and entry_kind_vocabulary.py, matching
    #   build_knowledge_scripts()'s own deploy_scripts list.
    # - 2026-09-14 [python-coder/GE-127b-1 fix]: Moved from scripts/build.py
    #   (unchanged) into this sibling module, alongside the
    #   build_knowledge_scripts() phase it describes -- its natural home, not
    #   merely a place to shed lines. scripts/build.py had grown +18 content
    #   lines for a legitimate deploy-manifest fix (this same AC INF-400c-5,
    #   H-1) while already over its own check-file-size limit, and the
    #   GE-127b-1 ratchet refuses any growth of an already-oversized file --
    #   the fix could not fund its own growth from budget elsewhere in that
    #   file. build.py now imports this function directly
    #   (``from build_phases_knowledge import _manifest_knowledge_scripts``)
    #   rather than through a build_phases.py re-export, since
    #   scripts/build_phases.py was intentionally left untouched by this
    #   extraction. (#INF-400c-5)
    """
    result: set[str] = set()
    knowledge_src = package_root / "scripts" / "knowledge"
    for fname in (
        "harvest_learnings.py",
        "emit_knowledge.py",
        "entry_kind_vocabulary.py",
        "harvest_result.py",
        "sink_resolution.py",
        "capture_write.py",
        "harvest_cli.py",
    ):
        if (knowledge_src / fname).is_file():
            result.add(f"scripts/knowledge/{fname}")
    return result


def _manifest_workflow_tool_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/<name>`` entries for workflow-tool scripts deployed by build_workflow_tools.

    Scans the package source for the workflow-tool scripts and returns
    manifest entries for those that exist.  Must be kept in parity with the
    ``deploy_scripts`` list inside ``build_workflow_tools()`` in
    ``build_phases.py`` — a mismatch trips the manifest/deploy parity guard.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/<name>`` strings for deployable workflow-tool scripts.

    # DECISION HISTORY
    # - 2026-09-14 [python-coder/GE-127b-1 fix]: Moved from scripts/build.py
    #   (unchanged) into this sibling module as the second, self-contained
    #   ``_manifest_*`` function extracted alongside
    #   ``_manifest_knowledge_scripts`` -- that helper alone did not recover
    #   enough of scripts/build.py's own check-file-size budget to fund the
    #   AC INF-400c-5, H-1 deploy-manifest fix's +18-line growth while
    #   build.py was already over its GE-127b-1 ratchet limit. This function
    #   has no thematic relationship to the knowledge plane; it moved here
    #   purely because it is "the same kind of thing" as
    #   ``_manifest_knowledge_scripts`` (an ordinary, self-contained
    #   deploy-manifest helper with no dependency on build_phases's private
    #   state) and moving one complete function is preferable to shaving
    #   pieces of several. build.py imports it directly from this module
    #   (``from build_phases_knowledge import _manifest_workflow_tool_scripts``),
    #   not through a build_phases.py re-export, since scripts/build_phases.py
    #   was intentionally left untouched by this extraction. (#INF-400c-5)
    # - 2026-09-17 12:00 [python-coder/KM-KGS-100a-3-xi]: Added
    #   knowledge_query.py's new sibling module knowledge_frontmatter_reader.py
    #   right after it in this tuple, since build_workflow_tools deploys the
    #   two side by side and _guard_source_paths_workflow_tools (build.py) now
    #   delegates to this function -- a single source of truth for the set
    #   instead of a second, duplicated tuple. (#TICKETLESS
    #   reason=km-kgs-100a-3-xi-fastlane)
    """
    result: set[str] = set()
    scripts_src = package_root / "scripts"
    for fname in (
        "add_component.py",
        "knowledge_query.py",
        "knowledge_frontmatter_reader.py",
        "set_ticket_status.py",
        "ticket_prioritizer.py",
        "port_registry.py",
        "live_surface_startup.py",
        "generate_doc_index.py",
    ):
        if (scripts_src / fname).is_file():
            result.add(f"scripts/{fname}")
    return result


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
# - 2026-09-14 [python-coder/GE-127b-1 fix]: Added _manifest_knowledge_scripts
#   and _manifest_workflow_tool_scripts, moved verbatim from scripts/build.py,
#   to fund that file's own +18-line legitimate growth (AC INF-400c-5, H-1
#   deploy-manifest fix) while it was already over the GE-127b-1
#   check-file-size ratchet limit. build.py now imports both names directly
#   from this module rather than through a build_phases.py re-export (that
#   file was intentionally left untouched). Behaviour-preserving: same
#   functions, same signatures, same call sites in build.py's
#   ``_get_source_deployable_scripts`` and (for the knowledge script names
#   only, via ``build_knowledge_scripts``'s own deploy_scripts list, unrelated
#   to this move) ``_get_source_paths_for_guard``. (#INF-400c-5)
# ===========================================================================
