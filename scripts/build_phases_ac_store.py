"""
MODULE: build_phases_ac_store
GOAL: Deploy the AC (Acceptance Criteria) pipeline scripts and their
    documentation — the phases that were previously defined inline in
    build_phases.py.
BUSINESS CONTEXT: build_phases.py is grandfathered many times over the
    400-content-line check-file-size limit, and the GE-127b-1 ratchet refuses
    any change that leaves an already-oversized file longer than it was. This
    module carries the AC-store deploy declaration and its two phase
    functions out of build_phases.py to restore headroom, with no behaviour
    change, exactly as build_phases_knowledge.py and
    build_phases_product_truth.py did for their own phases.
ARCHITECTURE: One module-level constant, ``AC_STORE_DEPLOY_MAP`` (the single,
    explicit, human-readable deploy declaration for ``build_ac_store`` — AC
    BP-900g-8 Set B), and two public phase functions, ``build_ac_store`` and
    ``build_ac_store_docs``, re-exported from build_phases.py so every
    existing caller (notably build.py, which imports both from
    ``build_phases``, and ``_manifest_ac_store_scripts``, which derives
    Set C directly from ``AC_STORE_DEPLOY_MAP``) keeps working unchanged.
    Both functions share the standard phase signature
    (target_root, config, dry_run, force) and defer their imports of
    build_phases's private write/deploy helpers (``PACKAGE_ROOT``,
    ``_should_overwrite``, ``_files_content_identical``, ``record_deploy_failure``,
    ``_write``) and shared ``_uptodate_count`` module state to function scope,
    to avoid a circular import at module load time (build_phases.py imports
    this module at its own top level).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# AC-store deploy declaration (AC BP-900g-8 Set B / BP-900g-5's fifth
# it_requirement).
# ---------------------------------------------------------------------------
# Format: (source_path_relative_to_PACKAGE_ROOT, deploy_filename_under
# <output_root>/scripts/ac_store/). This is the single, explicit, human-
# readable deploy declaration for build_ac_store() -- the AC's Set B
# (deploy_declaration). It is a module-level constant (rather than a local
# variable inside build_ac_store()) specifically so that build.py's
# `_manifest_ac_store_scripts` (Set C, the guard's model of what has been
# deployed) can be DERIVED FROM it, per BP-900g-5's fifth it_requirement:
# "Make the manifest derive FROM the deploy_map so the two cannot diverge."
# Before this, `_manifest_ac_store_scripts` scanned every file physically
# present in scripts/ac_store/ regardless of whether this map actually
# deployed it -- a guard whose view of "deployed" was really "exists in the
# source directory" could never detect a file present in source but absent
# from this map, which is exactly the defect class BP-900g-8 exists to close.
#
# `_component_migration_map.py` is included here per AC BP-900g-8: it is
# resolved by generate_ticket_from_ac.py's `_load_migration_map()` via
# `importlib.util.spec_from_file_location` at import time, but was never
# listed here, so every consumer install shipped generate_ticket_from_ac.py
# without its sibling and silently degraded (a WARNING, not a crash -- see
# `_load_migration_map`'s except clause). Adding it here is NECESSARY but not
# SUFFICIENT to satisfy the AC: the derived, transitive closure check in
# build.py (`_check_intra_package_closure_guard`) is the actual mechanism that
# would have caught this gap on its own, and is what prevents a future sibling
# reference from silently reproducing this same defect.
AC_STORE_DEPLOY_MAP: tuple[tuple[str, str], ...] = (
    ("scripts/ac_store/scan_ac_store.py",            "scan_ac_store.py"),
    ("scripts/ac_store/generate_ticket_from_ac.py",  "generate_ticket_from_ac.py"),
    ("scripts/ac_store/_component_migration_map.py", "_component_migration_map.py"),
    # generate_ticket_from_ac.py's 22 _gtfa_* siblings. The 4035-line original
    # was split to clear the 400-line size gate; what remains at that path is a
    # 386-line re-export shell that is USELESS without every one of these. Omit
    # one and the deployed generator dies at import -- loudly, unlike the
    # importlib try/except degradation above, because the shell imports them
    # unconditionally.
    #
    # The shell resolves them via importlib.import_module under a prefix
    # COMPUTED from its own __name__ (it must work both package-qualified and
    # as a bare directory import). A computed name is undecidable statically,
    # so build.py's derived closure guard cannot see these from the call site;
    # the shell carries an `if TYPE_CHECKING:` block of relative imports purely
    # so the analyser can. That block is what keeps the guard able to check
    # this list at all -- see unit_tests/ac_store/test_gtfa_sibling_closure_guard.py.
    ("scripts/ac_store/_gtfa_agents_inputs.py",       "_gtfa_agents_inputs.py"),
    ("scripts/ac_store/_gtfa_agents_map.py",          "_gtfa_agents_map.py"),
    ("scripts/ac_store/_gtfa_body.py",                "_gtfa_body.py"),
    ("scripts/ac_store/_gtfa_cli.py",                 "_gtfa_cli.py"),
    ("scripts/ac_store/_gtfa_cli_parser.py",          "_gtfa_cli_parser.py"),
    ("scripts/ac_store/_gtfa_components.py",          "_gtfa_components.py"),
    ("scripts/ac_store/_gtfa_config.py",              "_gtfa_config.py"),
    ("scripts/ac_store/_gtfa_constants.py",           "_gtfa_constants.py"),
    ("scripts/ac_store/_gtfa_contracts.py",           "_gtfa_contracts.py"),
    ("scripts/ac_store/_gtfa_decision_history.py",    "_gtfa_decision_history.py"),
    ("scripts/ac_store/_gtfa_doc_gates.py",           "_gtfa_doc_gates.py"),
    ("scripts/ac_store/_gtfa_doc_genre.py",           "_gtfa_doc_genre.py"),
    ("scripts/ac_store/_gtfa_files_touched.py",       "_gtfa_files_touched.py"),
    ("scripts/ac_store/_gtfa_frontmatter.py",         "_gtfa_frontmatter.py"),
    ("scripts/ac_store/_gtfa_implemented_by.py",      "_gtfa_implemented_by.py"),
    ("scripts/ac_store/_gtfa_paths.py",               "_gtfa_paths.py"),
    ("scripts/ac_store/_gtfa_phases.py",              "_gtfa_phases.py"),
    ("scripts/ac_store/_gtfa_report.py",              "_gtfa_report.py"),
    ("scripts/ac_store/_gtfa_seams.py",               "_gtfa_seams.py"),
    ("scripts/ac_store/_gtfa_store.py",               "_gtfa_store.py"),
    ("scripts/ac_store/_gtfa_test_descriptors.py",    "_gtfa_test_descriptors.py"),
    ("scripts/ac_store/_gtfa_tests_section.py",       "_gtfa_tests_section.py"),
    ("scripts/ac_store/ac_prioritizer.py",            "ac_prioritizer.py"),
    ("scripts/ac_store/mark_ac_done.py",              "mark_ac_done.py"),
    ("scripts/ac_store/scan_ac_orphans.py",           "scan_ac_orphans.py"),
    # done_proof.py backs the check_done_proof commit-guardian hook and the
    # fast-lane green+coverage gate; it MUST deploy or the (required) CI
    # done-proof check crashes with ModuleNotFoundError in the deployed layout.
    ("scripts/ac_store/done_proof.py",                "done_proof.py"),
    # test_enforcement.py is imported by done_proof.py (shared COVERS_TAG_RE seam,
    # BO-2500e-1).  It MUST deploy alongside done_proof.py — if absent, the
    # deployed check_done_proof hook crashes with ModuleNotFoundError at runtime.
    ("scripts/ac_store/test_enforcement.py",          "test_enforcement.py"),
    # _done_proof_phase_helpers.py was extracted out of done_proof.py by
    # BP-100n-4 to get that file under its size cap, and done_proof.py imports
    # it at MODULE scope. Same fast-lane gate, same failure: it MUST deploy or
    # the REQUIRED CI done-proof check crashes with ModuleNotFoundError in the
    # deployed layout. Note the second copy of this list that also needs the
    # name — unit_tests/ac_store/test_bp_1100g_3_ii.py::_MODULE_FILES builds its
    # own simulated deployed tree and does not read this map.
    ("scripts/ac_store/_done_proof_phase_helpers.py", "_done_proof_phase_helpers.py"),
    # ac_parent_id.py provides derive_parent_id, imported at module scope by
    # scripts/build_orchestration/fast_lane.py. Without it the deployed
    # fast_lane.py exists but dies at import with ModuleNotFoundError, so
    # /build-ac Step 2b.1 fails even though the file is present — a
    # file-presence check cannot catch this, only executing it can (BP-900g-4).
    ("scripts/ac_store/ac_parent_id.py",              "ac_parent_id.py"),
    # ac_coverage_resolver.py backs the ac-fulfillment-gate agent template's
    # Step 1 coverage-resolution seam (ACD-1900b-5-i). It MUST deploy or
    # the gate's CLI invocation crashes with ModuleNotFoundError in the
    # deployed layout even though unit tests -- which import from source --
    # stay green.
    ("scripts/ac_store/ac_coverage_resolver.py",      "ac_coverage_resolver.py"),
    # The following seven were added per BP-900a-1: all seven source files
    # already existed in scripts/ac_store/ but were never wired into this
    # deploy_map, so consumer installs were missing 7 of the 13 AC-store
    # scripts the AC requires (deploy_map completeness gap, not a
    # missing-source gap).
    ("scripts/ac_store/validate_ac_schema.py",        "validate_ac_schema.py"),
    # _ac_components.py is imported by validate_ac_schema.py
    # (`from _ac_components import components_field_errors, load_registry_ids`).
    # It was present in source but absent from this map -- discovered by AC
    # BP-900g-8's derived closure guard, not by manual audit -- so consumer
    # installs shipped validate_ac_schema.py without a sibling it imports at
    # module load time, which crashes with ModuleNotFoundError (an import
    # statement fails loudly, unlike the importlib.util try/except pattern
    # used elsewhere in this file).
    ("scripts/ac_store/_ac_components.py",            "_ac_components.py"),
    ("scripts/ac_store/ac_triage.py",                 "ac_triage.py"),
    ("scripts/ac_store/create_ac_workflow.py",        "create_ac_workflow.py"),
    ("scripts/ac_store/cross_reference_audit.py",     "cross_reference_audit.py"),
    # cross_reference_audit.py's own sibling modules (BP-900a-1-style gap: MUST deploy or it crashes with ModuleNotFoundError).
    ("scripts/ac_store/_xref_ac_store.py",            "_xref_ac_store.py"),
    ("scripts/ac_store/_xref_tickets.py",             "_xref_tickets.py"),
    ("scripts/ac_store/_xref_matching.py",            "_xref_matching.py"),
    ("scripts/ac_store/_xref_report.py",              "_xref_report.py"),
    ("scripts/ac_store/_xref_apply.py",               "_xref_apply.py"),
    ("scripts/ac_store/backfill_readiness.py",        "backfill_readiness.py"),
    ("scripts/ac_store/fix_ac_orphans.py",            "fix_ac_orphans.py"),
    ("scripts/ac_store/__init__.py",                  "__init__.py"),
    ("scripts/build_ac_mode_detection.py",            "build_ac_mode_detection.py"),
    ("scripts/goal_to_epic.py",                       "goal_to_epic.py"),
    # goal_to_epic.py's 14 siblings. It imports every one of them at MODULE
    # scope, so a deploy that ships the entry point without all fourteen does
    # not degrade -- it raises ModuleNotFoundError on first use. Two of them
    # (epic_ac_phases, epic_phases) arrive only transitively via epic_pipeline
    # and are exactly as load-bearing as the twelve named directly.
    ("scripts/ac_store/epic_ac_phases.py",            "epic_ac_phases.py"),
    ("scripts/ac_store/epic_ac_store.py",             "epic_ac_store.py"),
    ("scripts/ac_store/epic_assembly.py",             "epic_assembly.py"),
    ("scripts/ac_store/epic_cli.py",                  "epic_cli.py"),
    ("scripts/ac_store/epic_dependencies.py",         "epic_dependencies.py"),
    ("scripts/ac_store/epic_errors.py",               "epic_errors.py"),
    ("scripts/ac_store/epic_master_plan.py",          "epic_master_plan.py"),
    ("scripts/ac_store/epic_naming.py",               "epic_naming.py"),
    ("scripts/ac_store/epic_phases.py",               "epic_phases.py"),
    ("scripts/ac_store/epic_pipeline.py",             "epic_pipeline.py"),
    ("scripts/ac_store/epic_readiness.py",            "epic_readiness.py"),
    ("scripts/ac_store/epic_readiness_gate.py",       "epic_readiness_gate.py"),
    ("scripts/ac_store/epic_runtime.py",              "epic_runtime.py"),
    ("scripts/ac_store/epic_tickets.py",              "epic_tickets.py"),
)


def build_ac_store(target_root: Path, config: dict[str, Any],
                   dry_run: bool, force: bool) -> int:
    """Deploy AC pipeline scripts to ``<output_root>/scripts/ac_store/``.

    Copies the AC-pipeline Python scripts from their source locations in
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

    The source → destination mappings are:

    - ``scripts/ac_store/scan_ac_store.py``
      → ``<output_root>/scripts/ac_store/scan_ac_store.py``
    - ``scripts/ac_store/generate_ticket_from_ac.py``
      → ``<output_root>/scripts/ac_store/generate_ticket_from_ac.py``
    - ``scripts/ac_store/_component_migration_map.py``
      → ``<output_root>/scripts/ac_store/_component_migration_map.py``
    - ``scripts/ac_store/ac_prioritizer.py``
      → ``<output_root>/scripts/ac_store/ac_prioritizer.py``
    - ``scripts/ac_store/mark_ac_done.py``
      → ``<output_root>/scripts/ac_store/mark_ac_done.py``
    - ``scripts/ac_store/scan_ac_orphans.py``
      → ``<output_root>/scripts/ac_store/scan_ac_orphans.py``
    - ``scripts/ac_store/validate_ac_schema.py``
      → ``<output_root>/scripts/ac_store/validate_ac_schema.py``
    - ``scripts/ac_store/_ac_components.py``
      → ``<output_root>/scripts/ac_store/_ac_components.py``
    - ``scripts/ac_store/ac_triage.py``
      → ``<output_root>/scripts/ac_store/ac_triage.py``
    - ``scripts/ac_store/create_ac_workflow.py``
      → ``<output_root>/scripts/ac_store/create_ac_workflow.py``
    - ``scripts/ac_store/cross_reference_audit.py``
      → ``<output_root>/scripts/ac_store/cross_reference_audit.py``
    - ``scripts/ac_store/_xref_ac_store.py``
      → ``<output_root>/scripts/ac_store/_xref_ac_store.py``
    - ``scripts/ac_store/_xref_tickets.py``
      → ``<output_root>/scripts/ac_store/_xref_tickets.py``
    - ``scripts/ac_store/_xref_matching.py``
      → ``<output_root>/scripts/ac_store/_xref_matching.py``
    - ``scripts/ac_store/_xref_report.py``
      → ``<output_root>/scripts/ac_store/_xref_report.py``
    - ``scripts/ac_store/_xref_apply.py``
      → ``<output_root>/scripts/ac_store/_xref_apply.py``
    - ``scripts/ac_store/backfill_readiness.py``
      → ``<output_root>/scripts/ac_store/backfill_readiness.py``
    - ``scripts/ac_store/fix_ac_orphans.py``
      → ``<output_root>/scripts/ac_store/fix_ac_orphans.py``
    - ``scripts/ac_store/__init__.py``
      → ``<output_root>/scripts/ac_store/__init__.py``
    - ``scripts/ac_store/done_proof.py``
      → ``<output_root>/scripts/ac_store/done_proof.py``
    - ``scripts/ac_store/test_enforcement.py``
      → ``<output_root>/scripts/ac_store/test_enforcement.py``
    - ``scripts/ac_store/ac_parent_id.py``
      → ``<output_root>/scripts/ac_store/ac_parent_id.py``
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
    # - 2026-08-17 [python-coder/EPIC-DeploymentCompleteness/BP-900a-1]:
    #   Added validate_ac_schema.py, ac_triage.py, create_ac_workflow.py,
    #   cross_reference_audit.py, backfill_readiness.py, fix_ac_orphans.py, and
    #   __init__.py to deploy_map, closing a deploy_map completeness gap — all
    #   seven source files already existed in scripts/ac_store/ but were never
    #   wired into the deploy list, so consumer installs were missing 7 of the
    #   13 AC-store scripts the AC requires. (#BP-900a-1)
    # - 2026-08-25 [python-coder/BP-900g-8]: Extracted the inline deploy_map
    #   list into the module-level AC_STORE_DEPLOY_MAP constant so build.py's
    #   _manifest_ac_store_scripts (Set C, the guard's model of what has been
    #   deployed) can derive from it directly (BP-900g-5's fifth
    #   it_requirement — Set C must derive FROM Set B, never scan the source
    #   directory independently of it). Added _component_migration_map.py to
    #   the map: generate_ticket_from_ac.py resolves this sibling via
    #   importlib.util.spec_from_file_location at import time
    #   (_load_migration_map), but it was never listed here, so every consumer
    #   install shipped generate_ticket_from_ac.py without it — a gap that
    #   degrades silently (a WARNING, not a crash) rather than surfacing at
    #   deploy time. Adding this one entry is NECESSARY but explicitly NOT
    #   SUFFICIENT per the AC: the new derived, transitive closure guard in
    #   build.py (_check_intra_package_closure_guard, via
    #   build_referential_integrity.compute_intra_package_closure) is the
    #   mechanism that independently catches this class of gap by reading the
    #   code rather than trusting this list to stay complete. Proof the
    #   mechanism is not merely enumerating the one known instance: running the
    #   new closure guard against this map (before this entry was added) also
    #   surfaced a SECOND, previously-unknown instance of the same defect --
    #   validate_ac_schema.py does `from _ac_components import
    #   components_field_errors, load_registry_ids`, and _ac_components.py was
    #   likewise present in source but absent from this map. Both entries are
    #   now present; see the _ac_components.py entry above for detail.
    #   (#BP-900g-8)
    # - 2026-09-01 [python-coder]: Added a deploy block for
    #   config/phase_deferral.yaml, mirroring the existing
    #   config/ac_store_schema.json block immediately above it.
    #   generate_ticket_from_ac.py's _build_agents_map now reads this
    #   declaration the same way it already reads config/guardrail_gates.yaml
    #   (TKT-600b-1), and a missing declaration must REFUSE generation rather
    #   than fall back to a built-in default -- so an undeployed declaration
    #   would make every consumer-install generation call refuse. (#TKT-600b-1)
    """
    import build_phases as _bp  # noqa: PLC0415

    # Resolve the module-level AC_STORE_DEPLOY_MAP (source-relative strings) to
    # absolute (source_path, dest_name) pairs. AC_STORE_DEPLOY_MAP is the single
    # explicit deploy declaration (AC BP-900g-8 Set B); build.py's
    # _manifest_ac_store_scripts derives Set C from this SAME constant so the
    # two can never diverge (BP-900g-5's fifth it_requirement).
    deploy_map = [
        (_bp.PACKAGE_ROOT / src_rel, dest_name) for src_rel, dest_name in AC_STORE_DEPLOY_MAP
    ]

    output_dir = target_root / "scripts" / "ac_store"
    written = 0

    for src_file, dest_name in deploy_map:
        if not src_file.is_file():
            # BP-900g-9: was warn-and-continue, which let a declared entry
            # vanish from the deployed tree while the build exited 0. Record
            # and keep going so one run reports the whole remediation set;
            # build.py raises once at the end.
            _bp.record_deploy_failure("build_ac_store", dest_name, src_file)
            continue

        output_path = output_dir / dest_name

        if not _bp._should_overwrite(output_path, force):
            continue

        if _bp._files_content_identical(src_file, output_path):
            _bp._uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/ac_store/{dest_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _bp._log.warning(
                    "build_ac_store: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/ac_store/{dest_name}")
            written += 1

    # BP-1100g-3-ii: done_proof.py reads config/ac_store_schema.json to learn
    # the single taught set of proof kinds (BP-1100g-1). The DEPLOYED copy has
    # to be able to read it too, and in the self-hosting workspace layout it
    # cannot reach the package's own config/ by walking up -- .leafcutter/ sits
    # BESIDE leafcutter-ai/ there, not inside it, so no ancestor of the deployed
    # module holds the file. Deploying the schema next to the deployed scripts
    # is what makes the module's upward search succeed from every layout.
    # Without this the loader fail-softs to an empty permitted set and every
    # correctly-tagged test is reported as declaring an unrecognised kind.
    # Mirrors build_feedback's config/feedback_categories.yaml deployment.
    #
    # AC BP-900g-8-ii widened this to every "core config" file a deployed
    # ac_store script reads at runtime, once the intra-package dependency
    # closure was taught to see non-code (data/config) reads on the same
    # terms as module imports: ``generate_ticket_from_ac.py`` (deployed here)
    # reads ``config/agent_registry.json`` and ``config/guardrail_gates.yaml``
    # via its own ``_DEFAULT_AGENT_REGISTRY`` / ``_DEFAULT_GUARDRAIL_GATES``
    # module-level fallbacks; ``injection_builders.py`` (deployed by
    # ``build_agent_support_scripts``) reads ``config/agent_registry.json``
    # and ``config/paths.json``; the commit-guardian doc-type guardrail
    # (deployed by ``build_commit_guardian``) reads ``config/doc_types.json``
    # via an ancestor-directory walk that finds it here. None of the four new
    # entries were deployed anywhere before this AC -- confirmed absent from
    # a deployed output root on 2026-08-18 (this AC's own regression date) --
    # so turning the widened closure guard on without also shipping them
    # would abort every clean build.
    #
    # config/diagram_types.json is a LATER addition to this same tuple
    # (AC BP-900g-8-ii TDD rework): its reader, the commit-guardian
    # diagram_type_validators.py::_find_diagram_types_json ancestor walk, is
    # the IDENTICAL shape to doc_type_validators.py's doc_types.json walk,
    # but degrades SILENTLY to a built-in constant on failure rather than
    # raising -- so nothing ever crashed to reveal it was undeployed, and it
    # was genuinely absent (no second, unrelated reader put it in the
    # manifest "by luck" the way doc_types.json's was). Deployed through this
    # SAME core-config mechanism rather than a bespoke path, per this AC's
    # own doc_links relevance note: "extend that derivation rather than
    # adding a second, parallel one".
    #
    # config/skill_registry.json is a SECOND later addition, surfaced by
    # turning the corrected (BP-900g-8-ii) closure guard on across the whole
    # package rather than confined to the two named `*_types.json` files:
    # three deployed commit-guardian scripts (_package_surface_registry.py,
    # check_package_surface_declaration.py, check_surface_components_e3.py)
    # read it via a fallback dict literal keyed the same way
    # config/agent_registry.json and docs/roadmap.json are, and it was never
    # deployed anywhere -- confirmed absent from every deploy phase before
    # this fix (AC BP-900g-8-ii's own "enumerate, do not skip" constraint).
    for core_config_name in (
        "ac_store_schema.json",
        "agent_registry.json",
        "doc_types.json",
        "diagram_types.json",
        "skill_registry.json",
        "guardrail_gates.yaml",
        "paths.json",
    ):
        core_config_src = _bp.PACKAGE_ROOT / "config" / core_config_name
        if not core_config_src.is_file():
            continue
        core_config_output = target_root / "config" / core_config_name
        if _bp._write(
            core_config_output,
            core_config_src.read_text(encoding="utf-8"),
            dry_run,
            force,
        ):
            written += 1
            if not dry_run:
                print(f"  config/{core_config_name}")

    # TKT-600b-1: generate_ticket_from_ac.py's _build_agents_map reads
    # config/phase_deferral.yaml the same way it already reads
    # config/guardrail_gates.yaml -- by walking up from its own deployed
    # location. A declaration that exists only in the package source tree
    # and is never copied to the deployed config/ directory would silently
    # resolve to "file not found" in every consumer install, and the AC
    # requires a missing declaration to REFUSE rather than fall back to a
    # built-in default -- so every consumer generation call would refuse.
    # Deploying it here, mirroring config/ac_store_schema.json immediately
    # above, is what makes the declaration resolvable from the deployed
    # layout.
    phase_deferral_src = _bp.PACKAGE_ROOT / "config" / "phase_deferral.yaml"
    if phase_deferral_src.is_file():
        phase_deferral_output = target_root / "config" / "phase_deferral.yaml"
        if _bp._write(
            phase_deferral_output,
            phase_deferral_src.read_text(encoding="utf-8"),
            dry_run,
            force,
        ):
            written += 1
            if not dry_run:
                print("  config/phase_deferral.yaml")

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
    import build_phases as _bp  # noqa: PLC0415
    from template_compiler import inject_config  # noqa: PLC0415

    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    docs_template_dir = _bp.TEMPLATES_DIR / "docs"
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
            # BP-900g-9 (n_location_rule: all). Was a bare print(f"[WARNING]
            # ...") rather than _log.warning — precisely why every
            # grep-based audit of this file for warn-and-continue sites
            # missed it. Record and keep going so one run reports the whole
            # remediation set; build.py raises once at the end.
            _bp.record_deploy_failure("build_ac_store_docs", display_name, template_path)
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


# DECISION HISTORY
# - 2026-09-14 [python-coder/bp-size-split]: Moved AC_STORE_DEPLOY_MAP,
#   build_ac_store and build_ac_store_docs verbatim from build_phases.py into
#   this new sibling module to bring build_phases.py under the
#   400-counted-line check-file-size limit. Re-exported from build_phases.py
#   so build.py and every test import keeps working. (#refactor/build-phases-size-limit)
# - 2026-06-17 [python-coder/EPIC-AcPipelineDeployGaps/03]: Added
#   build_ac_store() phase. Copies six AC pipeline scripts
#   (scan_ac_store.py, generate_ticket_from_ac.py, ac_prioritizer.py,
#   mark_ac_done.py, build_ac_mode_detection.py, goal_to_epic.py) to
#   <target_root>/scripts/ac_store/, closing the portable-skill/missing-script
#   gap for ac-scanner and build-ac per ADR-013. (#EPIC-AcPipelineDeployGaps/03)
# - 2026-08-18 [python-coder]: Added ac_coverage_resolver.py to build_ac_store's
#   deploy_map. This new AC-store module backs the ac-fulfillment-gate agent
#   template's Step 1 coverage-resolution seam (ACD-1900b-5-i); without a
#   deploy_map entry it would exist in the source tree but not the deployed
#   layout, so the deployed gate's CLI invocation would crash with
#   ModuleNotFoundError even though unit tests importing from source stay
#   green. (#ACD-1900b-5-i)
