"""
MODULE: build_phases_ac_store_docs
GOAL: Install the AC (Acceptance Criteria) Traceability Store documentation
    into a target project.
BUSINESS CONTEXT: scripts/build_phases_ac_store.py -- itself already an
    earlier extraction out of build_phases.py -- was pushed to 408
    content-line count by a merge that landed two new AC_STORE_DEPLOY_MAP
    entries (_done_proof_kind_support.py's sibling _kind_plugin.py) on top of
    its existing content, one line over the check-file-size hook's
    400-content-line limit. Trimming comments could not honestly close an
    8-line gap when the two new deploy_map entries alone account for more
    than that. Carrying build_ac_store_docs() out to its own sibling module
    restores headroom with no behaviour change, exactly as
    build_phases_knowledge.py and build_phases_product_truth.py did for
    their own phases.
ARCHITECTURE: One public phase function, ``build_ac_store_docs``, re-exported
    from build_phases_ac_store.py (which itself is re-exported from
    build_phases.py), so every existing caller -- notably build.py, which
    imports it from ``build_phases`` -- keeps working unchanged. It shares
    the standard phase signature (target_root, config, dry_run, force) and
    defers its imports of build_phases's private write/deploy helpers
    (``TEMPLATES_DIR``, ``record_deploy_failure``) to function scope, to
    avoid a circular import at module load time (build_phases.py imports
    build_phases_ac_store, which in turn imports this module, at its own top
    level).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


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
# - 2026-09-28 [python-coder/merge-driven-split, EPIC-AProofThatReachedThe
#   CodeByDirectImport/BO-2900a-3]: Extracted build_ac_store_docs() out of
#   scripts/build_phases_ac_store.py into this new sibling module, moved
#   verbatim with no behaviour change. Needed to land a `git merge
#   origin/main` into this ticket's branch: the conflict-resolved
#   AC_STORE_DEPLOY_MAP (keeping both this ticket's
#   _done_proof_entry_point_gate.py / _done_proof_automation_gate.py entries
#   and main's done_proof_kind_support.py / _kind_plugin.py entries) pushed
#   build_phases_ac_store.py to 408 content lines, 8 over the check-file-size
#   hook's 400-content-line limit, and main's copy already sat exactly at the
#   cap with no comment-only trimming margin left. Re-exported from
#   build_phases_ac_store.py so build_phases.py's existing
#   ``from build_phases_ac_store import build_ac_store_docs`` -- and every
#   other caller -- keeps working unchanged. (#BO-2900a-3)
