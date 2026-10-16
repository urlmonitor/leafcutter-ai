"""
MODULE: build_phases_script_deploy_standalone
GOAL: Deploy the top-level ``templates/scripts/*.py`` standalone-script phase
    (``build_template_standalone_scripts``) and its NAMED-entry deploy-promise
    check, split out of ``build_phases_script_deploy.py``.
BUSINESS CONTEXT: BO-4300a-1 ("Every route that asks gets the same kind of
    workspace from the same maker") added the one workspace maker
    (``worktree.py``) plus its resolver and helper modules as NAMED entries
    to this deploy phase rather than leaving them to the shallow glob alone.
    That growth pushed ``build_phases_script_deploy.py`` over the package's
    400-counted-line check-file-size limit, so this thematically-adjacent
    phase moved out to a new sibling file -- the same "further split when a
    change pushes an already-large file over the ratchet" pattern
    ``build_phases_script_deploy.py`` itself was created by
    (bp-size-split, 2026-09-14).
ARCHITECTURE: One public phase function, ``build_template_standalone_scripts``,
    plus its private check helper ``_check_named_standalone_scripts`` and the
    module-level ``NAMED_STANDALONE_SCRIPTS`` deploy declaration. Re-exported
    from ``build_phases_script_deploy.py`` so every existing caller
    (``build_phases.py``, which re-exports it again for ``build.py``, and
    ``build_deploy_manifest_helpers.py``, which imports
    ``NAMED_STANDALONE_SCRIPTS`` directly) keeps working unchanged. Defers its
    import of ``build_phases``'s private write/deploy helpers
    (``TEMPLATES_DIR``, ``_should_overwrite``, ``_files_content_identical``,
    ``record_deploy_failure``, ``_log``, ``_uptodate_count``) to function
    scope, matching ``build_phases_script_deploy.py``'s own established
    pattern for avoiding a circular import at module load time.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

# NAMED_STANDALONE_SCRIPTS (BO-4300a-1): the maker every workspace-creation
# route must go through (worktree.py), its separate uncached project-root
# resolver module (workspace_root.py), and the two helper modules worktree.py
# imports (worktree_git.py for git/marker/install-build primitives,
# worktree_admin.py for the locate/list/remove verbs) -- named explicitly
# rather than left to the shallow glob alone, per this AC's own
# Implementation Notes ("the maker is added as a NAMED entry to the
# standalone-scripts deploy... not left to the shallow glob alone. The
# resolver module gets its OWN named entry in both places... any further
# helper module the maker imports needs a named entry too."). The shallow
# glob in build_template_standalone_scripts() below still deploys these four
# files (they are ordinary top-level templates/scripts/*.py files), but this
# tuple is the single source of truth _check_named_standalone_scripts() and
# _manifest_template_standalone_scripts() (build_deploy_manifest_helpers.py)
# both consult, so a file silently renamed or removed from templates/scripts/
# is recorded as a dropped promise (BP-900g-9) rather than a silent shrink of
# the deployed set.
NAMED_STANDALONE_SCRIPTS: tuple[str, ...] = (
    "worktree.py",
    "workspace_root.py",
    "worktree_git.py",
    "worktree_admin.py",
    "worktree_answer.py",
    "worktree_paths.py",
    "worktree_layout.py",
    "worktree_readiness.py",
    "worktree_canaries.py",
    "worktree_identity.py",
    "worktree_ensure_state.py",
    "worktree_remove.py",
    "worktree_migrate.py",
)


def build_template_standalone_scripts(target_root: Path, config: dict[str, Any],
                                      dry_run: bool, force: bool) -> int:
    """Deploy standalone Python scripts from ``templates/scripts/`` to ``<target_root>/scripts/``.

    Copies Python files (``*.py``) from ``templates/scripts/`` (excluding
    subdirectories) to the consumer project's ``scripts/`` directory.

    Currently deploys:

    - (``setup_ticket_worktree.py`` was retired by BO-4300f-2: the maker below
      is the only workspace script an install delivers.)
    - ``templates/scripts/worktree.py`` → ``scripts/worktree.py`` (NAMED entry,
      see ``NAMED_STANDALONE_SCRIPTS``): the one maker BO-4300a-1 requires
      every workspace-creation route to go through.
    - ``templates/scripts/workspace_root.py`` → ``scripts/workspace_root.py``
      (NAMED entry): worktree.py's separate, uncached project-root resolver
      module, deployed beside it so a hook can import it without the maker's
      own CLI.
    - ``templates/scripts/worktree_git.py`` → ``scripts/worktree_git.py``
      (NAMED entry): worktree.py's git-subprocess/marker-registry/install-
      build helper module.
    - ``templates/scripts/worktree_admin.py`` → ``scripts/worktree_admin.py``
      (NAMED entry): worktree.py's own locate/list/remove helper module.
    - ``templates/scripts/worktree_answer.py`` → ``scripts/worktree_answer.py``
      (NAMED entry): the BO-4300c-2 result-contract table and stdout discipline.
    - ``templates/scripts/worktree_paths.py`` → ``scripts/worktree_paths.py``
      (NAMED entry): native/POSIX path spelling (BO-4300b-5).
    - ``templates/scripts/worktree_layout.py`` → ``scripts/worktree_layout.py``
      (NAMED entry): the landing place, ``--landing-root`` validation and
      install-config derivation (BO-4300b-2, ADR-018 A1.12).
    - ``templates/scripts/worktree_readiness.py`` → ``scripts/worktree_readiness.py``
      (NAMED entry): the readiness proofs (BO-4300c-1, BO-4300b-4).
    - ``templates/scripts/worktree_canaries.py`` → ``scripts/worktree_canaries.py``
      (NAMED entry): the per-stage canary proofs worktree_readiness imports.
    - ``templates/scripts/worktree_identity.py`` → ``scripts/worktree_identity.py``
      (NAMED entry): the one naming table, legacy-line and occupant checks (BO-4300a-2, d-3, d-4).
    - ``templates/scripts/worktree_remove.py`` → ``scripts/worktree_remove.py``
      (NAMED entry, BO-4300e): the remove verb and the definite locate answer.
    - ``templates/scripts/worktree_migrate.py`` → ``scripts/worktree_migrate.py``
      (NAMED entry, BO-4300f-3): the ``migrate-legacy`` cut-over verb.
    - ``templates/scripts/worktree_ensure_state.py`` → ``scripts/worktree_ensure_state.py``
      (NAMED entry): the lock, set-aside and half-made handling (BO-4300d-1, d-2).

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files. After the shallow glob,
    ``_check_named_standalone_scripts()`` verifies every ``NAMED_STANDALONE_
    SCRIPTS`` entry was actually among the source files found, recording a
    deploy failure for any that is not (BP-900g-9 "dropped promise" shape).

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
    # - 2026-09-27 23:57 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
    #   Added NAMED_STANDALONE_SCRIPTS (worktree.py, workspace_root.py,
    #   worktree_git.py, worktree_admin.py) and _check_named_standalone_scripts()
    #   so the one maker and its resolver/helper modules are explicit, checked
    #   deploy promises rather than riding the shallow glob alone. Then split
    #   this phase into its own sibling module (this file) because adding it
    #   pushed build_phases_script_deploy.py over the 400-line ratchet.
    #   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
    # - 2026-09-30 22:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
    #   Added worktree_answer.py and worktree_paths.py as NAMED entries (the
    #   maker's answer table and path-spelling modules; BO-4300c-2 / b-5).
    #   (ADR-018)
    # - 2026-09-30 23:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
    #   Added worktree_layout.py as a NAMED entry (landing place, override
    #   validation, config derivation; BO-4300b-2). (ADR-018)
    # - 2026-10-01 00:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
    #   Added worktree_readiness.py as a NAMED entry (BO-4300c-1). (ADR-018)
    # - 2026-10-09 12:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
    #   Added worktree_canaries.py as a NAMED entry (worktree_readiness imports it). (ADR-018)
    # - 2026-10-10 09:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
    #   Added worktree_identity.py as a NAMED entry (BO-4300a-2, d-3, d-4). (ADR-018)
    # - 2026-10-12 09:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
    #   Added worktree_ensure_state.py as a NAMED entry (BO-4300d-1, d-2). (ADR-018)
    #   Added worktree_remove.py as a NAMED entry (BO-4300e). (ADR-018)
    #   Added worktree_migrate.py as a NAMED entry (BO-4300f-3). (ADR-018)
    """
    import build_phases as _bp

    templates_scripts_src = _bp.TEMPLATES_DIR / "scripts"
    if not templates_scripts_src.exists():
        for name in NAMED_STANDALONE_SCRIPTS:
            _bp.record_deploy_failure(
                "build_template_standalone_scripts", name, templates_scripts_src / name
            )
        return 0

    output_dir = target_root / "scripts"
    written = 0

    # Shallow scan — only top-level .py files; subdirectories have their own phases.
    # GE-132a-1: the remedy-declaration seed rides along, because the deployed
    # shared loader (_remedy_declarations.py) falls back to scripts/precommit-autofix.json.
    seed = templates_scripts_src / "precommit-autofix.json"
    for src_file in sorted([*templates_scripts_src.glob("*.py"), seed]):
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

    _check_named_standalone_scripts(templates_scripts_src)

    return written


def _check_named_standalone_scripts(templates_scripts_src: Path) -> None:
    """Record a deploy failure for any ``NAMED_STANDALONE_SCRIPTS`` entry missing from source.

    The shallow glob in ``build_template_standalone_scripts`` already deploys
    every top-level ``templates/scripts/*.py`` file dynamically; this check
    exists so the maker and its resolver/helper modules are EXPLICIT, checked
    promises (BP-900g-9 "n_location_rule: all") rather than an accident of
    what happens to be in the directory -- a file renamed or deleted there
    must be reported the same way any other dropped promise is, not silently
    absorbed into "the glob just deployed fewer files this time".

    Args:
        templates_scripts_src: Absolute path to the package's
            ``templates/scripts/`` directory (already confirmed to exist by
            the caller).
    """
    import build_phases as _bp

    for name in NAMED_STANDALONE_SCRIPTS:
        if not (templates_scripts_src / name).is_file():
            _bp.record_deploy_failure(
                "build_template_standalone_scripts", name, templates_scripts_src / name
            )


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-27 23:57 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
#   Split out of build_phases_script_deploy.py (bringing it back under the
#   400-counted-line check-file-size limit) after adding
#   NAMED_STANDALONE_SCRIPTS / _check_named_standalone_scripts pushed that
#   file over the ratchet. Re-exported from build_phases_script_deploy.py so
#   build_phases.py's re-export chain and build_deploy_manifest_helpers.py's
#   direct import both keep working unchanged.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-28 02:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
#   Fixed pr-reviewer H-1 (2026-09-28 00:43): the 2026-09-27 entry above (both
#   copies -- in this file's own docstring block and in this trailing block)
#   was missing the mandatory HH:MM, which the doc hook's timestamp check
#   rejects. Added the timestamp; no functional change.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-28 02:42 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
#   Fixed pr-reviewer H-1 (2026-09-28 02:15): the tail-tag validator
#   (templates/scripts/commit_guardian/doc_validators.py's _get_added_dh_lines/
#   _validate_tail_tag) only inspects an entry's FIRST line (the one matching
#   "- YYYY-MM-DD HH:MM [Author]:") for the tag; this file's own two entries
#   above put the tag on the LAST continuation line of a multi-line, #-wrapped
#   entry, so the check saw a tag-less first line. Duplicated the existing
#   tag onto each entry's first line (kept the original trailing copy too,
#   append-only) so the same-line requirement is met without deleting or
#   rewording any prior entry. No functional change to this module.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-10-09 12:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
#   Added worktree_canaries.py as a NAMED entry (worktree_readiness imports
#   it; the deployed maker would otherwise crash with ModuleNotFoundError). (ADR-018)
# ===========================================================================
