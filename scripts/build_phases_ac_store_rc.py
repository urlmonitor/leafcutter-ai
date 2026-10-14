"""
MODULE: build_phases_ac_store_rc
GOAL: Declare the deploy tuples of the requirement rule check's fourteen modules
    (ACD-2500a-1, ACD-2500b-1-i) and the two G4 modules (ACD-2500d-5-i, ACD-2500c-1-i), sixteen in
    all, kept out of build_phases_ac_store.py so that file's size ratchet is not charged sixteen lines.
BUSINESS CONTEXT: build_phases_ac_store.py measures over the 400-line limit, so each
    line added there must be paid for by deleting two. The rule check ships as sixteen
    flat modules (twelve ACD-2500a ones plus _rc_test_intent and its parser _test_intent, the
    deterministic design_prepass and the _rc_design_grounding family); declaring them here costs
    the map file one line (the splat).
ARCHITECTURE: One module-level constant, ``RULE_CHECK_DEPLOY_MAP``, in the same
    (source relative to PACKAGE_ROOT, deploy filename under <output_root>/scripts/ac_store/)
    shape as ``AC_STORE_DEPLOY_MAP``, which splices it in with ``*RULE_CHECK_DEPLOY_MAP``.
    Everything the sixteen modules import is already declared in that map
    (validate_ac_schema, _ac_components, declared_files, _declared_files_path_form,
    assignment_quality, ac_parent_id, _component_migration_map, yaml_safe_loader), so the
    derived closure guard needs nothing else. Build-time only: never deployed itself.
"""

from __future__ import annotations

RULE_CHECK_DEPLOY_MAP: tuple[tuple[str, str], ...] = tuple(
    (f"scripts/ac_store/{name}.py", f"{name}.py")
    for name in (
        "requirement_rule_check", "_rc_report", "_rc_records", "_rc_record_schema", "_rc_edit",
        "_rc_backlinks", "_rc_components", "_rc_contracts", "_rc_readiness", "_rc_doc_triggers",
        "_rc_declared", "_rc_changed", "_rc_test_intent", "_test_intent",
        "design_prepass", "_rc_design_grounding",
    )
)
