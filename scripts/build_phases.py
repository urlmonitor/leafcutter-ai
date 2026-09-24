"""
MODULE: build_phases
GOAL: Own the state shared by every build phase of the leafcutter build
    system, and present one stable import surface for all of them.
BUSINESS CONTEXT: Templates for agents, skills, workflows, rules, hooks, and
    ticket lifecycle folders are stored under leafcutter/templates/.
    Each phase function reads a template sub-directory, compiles or copies the
    files, and writes them to the correct output path in the target project.
    The phase functions themselves now live in sibling ``build_phases_*.py``
    modules (see ARCHITECTURE); this module keeps the state they all share and
    re-exports every name, so ``from build_phases import <anything>`` and
    ``build_phases.<anything>`` both keep working exactly as before.
ARCHITECTURE: Facade + shared primitives.

    This module owns, and is the single home of:
      - the path constants every phase resolves against -- ``PACKAGE_ROOT``,
        ``TEMPLATES_DIR``, ``REGISTRY_PATH``, ``SKILLS_TEMPLATE_DIR`` -- which
        are derived from ``Path(__file__)`` at import time;
      - the up-to-date counter (``_uptodate_count`` + ``reset_uptodate_count``
        / ``get_uptodate_count``) that main() reports per run;
      - the declared-deploy failure registry (``DeployFailure``,
        ``DeployDeclarationError``, ``record_deploy_failure``,
        ``get_deploy_failures``, ``reset_deploy_failures``,
        ``raise_if_deploy_failures``) -- BP-900g-9's fail-closed accumulator;
      - the write helpers ``_should_overwrite`` / ``_write`` /
        ``_files_content_identical``.

    The phase functions live in these sibling modules, each re-exported below:
      - ``build_phases_agents_skills``   -- build_agents, build_skills, and the
        components-table injection helpers
      - ``build_phases_workflows``       -- build_workflow_scripts,
        build_workflows, build_workflow_tools, _emit_workflow_variant
      - ``build_phases_lifecycle``       -- build_hooks, build_commands,
        build_rules, build_ticket_lifecycle, build_commit_guardian
      - ``build_phases_ac_store``        -- AC_STORE_DEPLOY_MAP, build_ac_store,
        build_ac_store_docs
      - ``build_phases_docs``            -- build_doc_compliance, build_vision,
        build_components_registry, build_ui_context, build_feedback,
        build_antigravity_instructions, build_sync_platforms
      - ``build_phases_agent_validation``-- validate_agent_self_description,
        build_agent_cards
      - ``build_phases_script_deploy``   -- AGENT_SUPPORT_SCRIPT_DIRS/FILES and
        the agent-support / build-orchestration / template-standalone deploys
      - ``build_phases_reachability``    -- check_command_reachability (the
        BP-900g-1 command-side guard) and its helpers
      - ``build_phases_collisions``      -- detect_deploy_collisions and
        _compute_phase_mappings (the BP-100m guard)
      - ``build_phases_clean``           -- clean_stale_artifacts
      - ``build_phases_knowledge``, ``build_phases_product_truth``,
        ``build_phases_self_description``, ``build_precommit`` -- extracted
        earlier, unchanged by the BP size split.

    HOW A SIBLING MODULE REACHES SHARED STATE -- read before editing one.
    Every extracted phase function does a FUNCTION-SCOPED ``import
    build_phases as _bp`` and refers to ``_bp.TEMPLATES_DIR``, ``_bp._write``,
    ``_bp.record_deploy_failure`` and friends. It must NOT use a module-level
    ``from build_phases import TEMPLATES_DIR``: many tests do
    ``monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp)`` and then call
    the phase through this facade, and a module-level ``from`` import would
    bind a stale value at import time and silently ignore the patch -- the
    phase would read the real templates tree while the test believed it was
    reading a fixture. ``tests/test_build_clean.py`` carries a standing
    comment about exactly that no-op. The function-scoped form is also what
    keeps the import graph acyclic: this module imports the siblings at module
    level, and they import it back only at call time.

    ONE CALLER NEEDS MORE THAN THAT. ``build_helpers._load_build_phases_module()``
    loads this file via ``spec_from_file_location`` under a name derived from
    ``package_root``, so that repeated calls against different package roots in
    one process do not read each other's templates. A sibling module imported
    by BARE name cannot see that alternate module object, so
    ``_compute_phase_mappings`` takes its templates root as an explicit
    argument and the wrapper below binds THIS module's own ``TEMPLATES_DIR``.
    See that wrapper and the note in ``build_phases_collisions``.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
REGISTRY_PATH = PACKAGE_ROOT / "config" / "agent_registry.json"
SKILLS_TEMPLATE_DIR = TEMPLATES_DIR / "skills"

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level up-to-date counter (reset by build.py before each CLI run)
# ---------------------------------------------------------------------------

# Counts files whose on-disk content was byte-identical to the new content
# and were therefore skipped by _write or _files_content_identical.  main()
# in build.py resets this via reset_uptodate_count() and reads it via
# get_uptodate_count() to emit "Up-to-date: N files (unchanged)". Sibling
# phase modules increment it as `_bp._uptodate_count += 1`, rebinding the
# attribute on THIS module -- the same counter main() reads.
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
    skipped and False is returned.  Both the guard's comparison and the actual
    write operate on the same value -- ``content.encode("utf-8")`` -- with no
    newline translation applied in either direction.  The file on disk is
    therefore byte-identical to ``content`` on every platform, Windows
    included: a line-feed in ``content`` is never widened to a carriage-return
    + line-feed pair, and an existing file's on-disk bytes (CRLF or otherwise)
    are compared exactly as they are, never normalised back to LF first.  This
    eliminates mtime churn and spurious ``git status`` entries for unchanged
    files.  Unreadable files fall through to an unconditional write (OSError
    is caught and silently ignored).

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
    data = content.encode("utf-8")
    # Compare-before-write: skip if the on-disk content is byte-identical.
    # Runs only for real writes; dry-run always returns True (intent) above.
    if target.exists():
        try:
            if target.read_bytes() == data:
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                return False
        except OSError:
            pass  # Unreadable file -- fall through to write.
        announce_if_local_change_replaced(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return True


def _files_content_identical(src: Path, dst: Path) -> bool:
    """Return True when src and dst exist and have byte-identical content.

    Uses SHA-256 hashes to compare binary files without loading both into
    memory simultaneously when files are large.

    When the files differ and ``dst`` already exists, calls
    ``announce_if_local_change_replaced(dst)`` before returning — every
    caller's pattern is ``if _files_content_identical(...): skip else:
    shutil.copy2(...)``, so a False return always precedes an overwrite
    (ACD-2100d-2-i). This is the single instrumentation point for all
    ``shutil.copy2``-based call sites in this module.

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
        identical = _sha256(src) == _sha256(dst)
    except OSError:
        return False
    if not identical:
        announce_if_local_change_replaced(dst)
    return identical


# ---------------------------------------------------------------------------
# Phase re-exports — the stable import surface.
# Underscore names here are NOT incidental: build_helpers.py reaches five off
# the module object and several tests import them directly. Dropping one is a
# breaking change, not a tidy-up.
# ---------------------------------------------------------------------------

from build_phases_deploy_failures import (  # noqa: E402, F401  # re-exported
    DeployFailure,
    DeployDeclarationError,
    reset_deploy_failures,
    record_deploy_failure,
    get_deploy_failures,
    raise_if_deploy_failures,
)
from build_phases_local_change import (  # noqa: E402, F401  # re-exported for callers
    set_local_change_baseline,
    announce_if_local_change_replaced,
)
from build_precommit import (  # noqa: E402, F401  # re-exported for callers
    build_precommit_config,
    _render_hook_yaml,
    _strip_package_managed_blocks,
    _find_decision_history_index,
    _build_output_lines,
)
from build_phases_self_description import (  # noqa: E402, F401  # re-exported
    _self_desc_field_hint,
)
from build_phases_knowledge import (  # noqa: E402, F401  # re-exported for callers
    build_knowledge_scripts,
    build_knowledge_sink_declaration,
    # INF-700a-1-i. Authored directly in the sibling module, never here, for the
    # same file-size reason that produced the extraction above.
    check_knowledge_routing_wiring,
)
from build_phases_product_truth import (  # noqa: E402, F401  # re-exported for callers
    build_product_truth,
)
from build_phases_agents_skills import (  # noqa: E402, F401  # re-exported for callers
    _build_components_table,
    _inject_components_table,
    build_agents,
    _skill_is_deprecated,
    _skill_deploy_files,
    build_skills,
)
from build_phases_workflows import (  # noqa: E402, F401  # re-exported for callers
    _emit_workflow_variant,
    build_workflow_scripts,
    build_workflows,
    build_workflow_tools,
)
from build_phases_lifecycle import (  # noqa: E402, F401  # re-exported for callers
    build_hooks,
    build_commands,
    build_rules,
    build_ticket_lifecycle,
    build_commit_guardian,
    _deploy_commit_guardian_config_files,
)
from build_phases_ac_store import (  # noqa: E402, F401  # re-exported for callers
    AC_STORE_DEPLOY_MAP,
    build_ac_store,
    build_ac_store_docs,
)
from build_phases_docs import (  # noqa: E402, F401  # re-exported for callers
    build_doc_compliance,
    build_vision,
    build_components_registry,
    build_ui_context,
    build_feedback,
    build_antigravity_instructions,
    build_sync_platforms,
)
from build_phases_agent_validation import (  # noqa: E402, F401  # re-exported
    validate_agent_self_description,
    build_agent_cards,
)
from build_phases_background_worker import build_background_worker  # noqa: E402, F401
from build_phases_script_deploy import (  # noqa: E402, F401  # re-exported for callers
    AGENT_SUPPORT_SCRIPT_DIRS,
    AGENT_SUPPORT_SCRIPT_FILES,
    build_agent_support_scripts,
    _copy_agent_support_file,
    build_build_orchestration_scripts,
    _deploy_fast_lane_release_dependency,
    build_template_standalone_scripts,
)
from build_phases_reachability import (  # noqa: E402, F401  # re-exported for callers
    _HANDOFF_TARGET_RE,
    _handoff_target_resolves,
    _resolve_declared_workflows_enabled,
    check_command_reachability,
)
from build_phases_collisions import (  # noqa: E402, F401  # re-exported for callers
    detect_deploy_collisions,
    _per_platform_mappings,
)
from build_phases_collisions import (  # noqa: E402
    _compute_phase_mappings as _compute_phase_mappings_impl,
)
from build_phases_clean import (  # noqa: E402, F401  # re-exported for callers
    _MANAGED_ARTIFACT_DIRS,
    clean_stale_artifacts,
)


def _compute_phase_mappings(
    output_root: Path,
    config: dict[str, Any],
) -> list[tuple[Path, Path]]:
    """Enumerate (source_template, resolved_target) pairs for the artifact phases.

    Thin wrapper over ``build_phases_collisions._compute_phase_mappings`` that
    binds THIS module's ``TEMPLATES_DIR``. That binding is the whole point of
    the wrapper, and it is not cosmetic:
    ``build_helpers._load_build_phases_module()`` loads this file by PATH under
    a synthetic per-``package_root`` name so that two package roots in one
    process cannot read each other's templates, then calls this function off
    that module object. The implementation lives in a sibling imported by BARE
    name, whose own ``import build_phases`` would resolve to a different module
    object with a different ``TEMPLATES_DIR`` -- silently enumerating the wrong
    package's templates. Reading ``TEMPLATES_DIR`` here, in the correctly-rooted
    module, and passing it down keeps that caller correct; reading it as a
    module global (rather than capturing it at import time) keeps
    ``monkeypatch.setattr(build_phases, "TEMPLATES_DIR", ...)`` working too.

    Args:
        output_root: Absolute path to the consolidated output directory
            (e.g. ``<target>/.leafcutter``).
        config: Build configuration dict; reads ``config["platforms"]``.

    Returns:
        Flat list of (source_template_path, resolved_target_path) pairs,
        in artifact phase order.
    """
    return _compute_phase_mappings_impl(output_root, config, templates_dir=TEMPLATES_DIR)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Split this module into ten new
#   sibling build_phases_*.py modules, moving every phase function out and
#   leaving the shared state plus a full re-export surface behind. This file
#   measured 2671 content lines (the check-file-size hook's own counter)
#   against the 400-line limit, so the GE-127b-1 ratchet refused any change
#   that left it longer -- the same pressure that forced the build_precommit /
#   build_phases_knowledge / build_phases_product_truth extractions, applied to
#   the remainder. Extracted functions reach shared state through a
#   FUNCTION-SCOPED `import build_phases as _bp` so
#   `monkeypatch.setattr(build_phases, "TEMPLATES_DIR", ...)` still takes
#   effect. _compute_phase_mappings gained an explicit templates_dir parameter
#   and the binding wrapper above, because build_helpers's by-path load cannot
#   be seen by a bare-name sibling. See the ARCHITECTURE docstring.
#   (#refactor/build-phases-size-limit)
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
# - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
#   Extended build_feedback() to deploy aggregate.py and resolve_feedback.py
#   alongside the three previously-deployed feedback scripts. Added three new
#   phases: build_workflow_tools() (deploys add_component.py, knowledge_query.py,
#   set_ticket_status.py, ticket_prioritizer.py from scripts/ to consumer scripts/),
#   build_knowledge_scripts() (deploys harvest_learnings.py to scripts/knowledge/),
#   and build_template_standalone_scripts() (deploys .py files from templates/scripts/
#   to scripts/, primarily setup_ticket_worktree.py). All new phases use the
#   shutil.copy2 + compare-before-write pattern established by build_ac_store.
#   Kept here rather than relocated by the 2026-09-14 split: it describes four
#   phases that now live in three different modules, so moving it to any one of
#   them would strip the history of the other two.
#   (#EPIC-BuildGuardFalsePositive/03)
# - 2026-08-26 [python-coder/TICKET-20260826-BP-1100g-4]: Verified, made NO
#   functional change. BP-1100g-4 adds a new commit_guardian hook module,
#   templates/scripts/commit_guardian/check_proof_promise_claim.py, that
#   imports done_proof.collect_test_tag_records (the same seam
#   check_done_proof.py already uses). That module deploys wholesale via
#   build_commit_guardian's directory copy of templates/scripts/commit_guardian/
#   (now in build_phases_lifecycle.py), not via AC_STORE_DEPLOY_MAP (now in
#   build_phases_ac_store.py), so it needs no entry of its own there. Its one
#   runtime dependency — done_proof.py, and done_proof.py's own dependency
#   test_enforcement.py — were already added to AC_STORE_DEPLOY_MAP by
#   BP-1100g-3, so the import chain already resolves in the deployed layout
#   with no further change. Confirmed by running the deployed hook via
#   run_hook.py after a fresh build.py pass
#   (unit_tests/commit_guardian/test_bp_1100g_4.py's reachability test). This
#   is the DEPLOY-MANIFEST OBLIGATION check the AC's own Implementation Notes
#   require — recorded here since it resolved to "no change needed" rather than
#   a new deploy_map line, so the verification would otherwise leave no trace.
#   (#TICKET-20260826-BP-1100g-4)
# - 2026-09-07 [python-coder]: Added build_knowledge_sink_declaration(), a new
#   internal-phase writing config/knowledge_sink.json under the consolidated
#   output root: an absolute, build-time-fixed declaration of this install's
#   knowledge-emission sink at <project_root>/debugging/logs/
#   knowledge_emissions.jsonl (project_root == the internal-phase's own
#   target_root parameter, .parent — one level above the consolidated output
#   root per _run_phases's calling convention). Derived entirely from the
#   already-resolved --target-dir argument, never from filesystem discovery,
#   so a nested consumer install's sink lands at the consumer's own root and
#   a workspace install's sink lands beside the rest of that install's
#   deployed content rather than beside the package sources. Deliberately
#   NOT placed under build_feedback's own <output_root>/debugging/logs/
#   (which that phase creates eagerly on every build) so the sink's own
#   parent directory does not spring into existence merely because a build
#   ran. Always prints a NOTE naming the declared sink, since a build cannot
#   tell whether its target is an already-installed project's own root or a
#   separate working directory of a different install with a sink
#   elsewhere. (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-v)
# - 2026-09-09 [python-coder/bp-extract]: Extracted build_knowledge_scripts()
#   and build_knowledge_sink_declaration() to a new sibling module,
#   build_phases_knowledge.py, with NO behaviour change. This module measured
#   2753 content lines (the check-file-size hook's own counter) against the
#   400-line limit; the GE-127b-1 ratchet refuses any change that leaves an
#   already-oversized file longer than it was, which was blocking
#   INF-400c-4-iii (adds a build phase) and INF-400c-4-i (needs a
#   deploy-manifest entry in this same file) from committing. Both names are
#   re-exported here via `from build_phases_knowledge import (...)`, the same
#   pattern already used for build_precommit_config / build_precommit.py, so
#   build.py's existing `from build_phases import build_knowledge_scripts,
#   build_knowledge_sink_declaration` keeps working unchanged.
#   (#INF-400c-4-iii, #INF-400c-4-i)
# - 2026-09-09 [python-coder/04_TICKET-20260909-UXP-700a-1-ii]: Added
#   _scaffold_product_truth_record(), called from build_product_truth(), to
#   write flows/mock-data/mockups/index.json write-if-absent on a fresh
#   install (UXP-700a-1-ii's overwrite guard needs this to exist first).
#   This entry was briefly load-bearing, and no longer is -- recorded because
#   the reason is worth keeping. unit_tests/build_guards/test_bp_100k_2.py's
#   _derive_extra_package_dirs() regex-scans source text for a literal
#   PACKAGE_ROOT / "seg1" / "seg2" chain, to learn which extra source dir its
#   synthetic-package fixture must copy beyond the wholesale-copied
#   templates/scripts/config trees. It scanned only this file. When
#   build_product_truth moved out to build_phases_product_truth.py on
#   2026-09-10, the last real chain went with it and the ONLY remaining match
#   here was the prose of this very comment -- so a derivation advertised as
#   reading the real source was in fact satisfied by a sentence, and deleting
#   the sentence would have silently stopped the fixture copying that tree.
#   Fixed on 2026-09-14: the fixture now globs scripts/build_phases*.py, so it
#   derives from executable code again (build_phases_product_truth.py's own
#   `_bp.PACKAGE_ROOT / "docs" / "product-truth"`), and still yields
#   ["docs/product-truth"]. Nothing in this comment is depended upon now.
#   (#EPIC-TruthfulProjectRecord/04)
# - 2026-09-13 [python-coder/BP-1000a-7]: Fixed _write()'s compare-before-write
#   guard and the write itself to operate on raw UTF-8 bytes instead of text
#   mode. Previously target.write_text(content, encoding="utf-8") let Python's
#   text-mode newline translation widen every LF in content to os.linesep, so
#   on Windows every deployed text artifact landed CRLF while its source
#   template stayed LF, producing check-hook-parity / check-output-drift
#   divergence. Worse, the guard's own target.read_text(encoding="utf-8")
#   applies universal-newline translation on read on every platform,
#   normalising the on-disk CRLF back to LF before the comparison -- so a
#   CRLF file compared equal to LF content and was skipped as "unchanged,"
#   meaning neither a plain re-run (write-if-absent, never reaches the guard)
#   nor a forced re-run (reaches the guard, compares equal, skips) could ever
#   repair it. The docstring already promised a
#   byte-identical comparison; the implementation did not deliver it. Fix:
#   encode content once, compare target.read_bytes() against those bytes,
#   and write with target.write_bytes() so the guard and the writer act on
#   the literal same value with no newline translation anywhere. Narrowed
#   the guard's except clause to OSError only, since a bytes read cannot
#   raise UnicodeDecodeError. Landing this rewrites every previously-CRLF-
#   deployed artifact once, on the next build, which is expected.
#   (#BP-1000a-7)
# ====================================================================
