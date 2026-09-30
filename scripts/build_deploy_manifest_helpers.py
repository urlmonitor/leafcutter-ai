"""
MODULE: build_deploy_manifest_helpers
GOAL: Compute, per deploy phase, the set of script paths that phase will
    write -- ten small scanners, one per phase that writes ``.py`` files to
    a target project.
BUSINESS CONTEXT: Extracted from build.py, which was already over the
    check-file-size ratchet (an already-oversized file may be worked on but
    must not end up longer than it stood at HEAD) before the BP-1500g-1
    change that grew it further. This family of ten independent,
    single-purpose scanners is wholly unrelated to BP-1500g-1's ownership-
    attribution change, so it is what moves to make room -- the same shape
    PR #769 used when it extracted the knowledge phases out of
    build_phases.py.

    ``build.py``'s own ``_get_source_deployable_scripts`` (which unions all
    ten of these into the full declared "Set B" deployable-scripts manifest)
    and ``_get_source_paths_for_guard`` (the SOURCE-namespace mirror of the
    same enumeration) deliberately STAY in build.py rather than moving here
    too: unit_tests/test_bp_900g_8_ii.py asserts, by exact byte-for-byte text
    match against ``scripts/build.py``'s own on-disk content, that the
    "core config" deploy tuple those two functions each contain appears
    TWICE inside that physical file (once in each function) -- moving either
    function out of build.py would make that fixture assumption false and
    fail the test. The ten helpers below carry no such tuple and no such
    assumption, so only they moved.
ARCHITECTURE: Ten ``_manifest_<phase>_scripts(package_root: Path) -> set[str]``
    functions, each returning the deploy-namespace paths one build phase
    will write, called only by build.py's own
    ``_get_source_deployable_scripts`` (which imports them from here). None
    of the ten is called by name from anywhere else -- confirmed by
    inspection of every test that references the deployable-scripts
    manifest, which all call ``_get_source_deployable_scripts`` /
    ``_get_source_paths_for_guard`` rather than any individual
    ``_manifest_*`` helper -- so none needs to be re-exported from build.py.
    Depends on ``build_phases.AC_STORE_DEPLOY_MAP`` and
    ``build_phases.AGENT_SUPPORT_SCRIPT_DIRS`` / ``AGENT_SUPPORT_SCRIPT_FILES``,
    imported directly (no circular-import concern: build_phases does not
    import this module). Pure move: no behaviour change.
"""

from __future__ import annotations

from pathlib import Path

from build_phases import (
    AC_STORE_DEPLOY_MAP,
    AGENT_SUPPORT_SCRIPT_DIRS,
    AGENT_SUPPORT_SCRIPT_FILES,
)


def _manifest_ac_store_scripts(package_root: Path) -> set[str]:  # noqa: ARG001
    """Return ``scripts/ac_store/<name>`` entries for every AC_STORE_DEPLOY_MAP entry.

    Derives Set C (the guard's model of what has been deployed) directly from
    ``build_phases.AC_STORE_DEPLOY_MAP`` -- the SAME constant ``build_ac_store``
    iterates to perform the actual copy -- per BP-900g-5's fifth
    it_requirement: "Make the manifest derive FROM the deploy_map so the two
    cannot diverge."

    Before this (BP-900g-8), this function scanned every file physically
    present in ``package_root/scripts/ac_store/`` regardless of whether
    ``build_ac_store`` actually deployed it. That made the guard's view of
    "deployed" really mean "exists in the source directory" -- structurally
    incapable of detecting a file present in source but absent from the deploy
    map, which is exactly the defect class BP-900g-8 closes
    (``_component_migration_map.py`` was such a file).

    Args:
        package_root: Present for interface parity with the other
            ``_manifest_*`` helpers; unused because ``AC_STORE_DEPLOY_MAP`` is
            already resolved relative to ``build_phases.PACKAGE_ROOT``.

    Returns:
        Set of ``scripts/ac_store/<name>`` strings, one per
        ``AC_STORE_DEPLOY_MAP`` entry.
    """
    return {f"scripts/ac_store/{dest_name}" for _src_rel, dest_name in AC_STORE_DEPLOY_MAP}


def _manifest_commit_guardian_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/commit_guardian/<rel>`` entries for all template .py files.

    Scans ``templates/scripts/commit_guardian/`` (canonical) and returns one
    manifest entry per ``.py`` file, matching what ``build_commit_guardian``
    deploys to the target project.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/commit_guardian/<rel>`` strings, or empty set when
        the source directory is absent.
    """
    result: set[str] = set()
    src = package_root / "templates" / "scripts" / "commit_guardian"
    if src.is_dir():
        for f in src.rglob("*"):
            if f.is_file() and f.suffix == ".py":
                result.add(f"scripts/commit_guardian/{f.relative_to(src).as_posix()}")
        # AC BP-900g-8-ii: commit_guardian.json is deployed verbatim alongside
        # the .py files (build_commit_guardian's rglob copies every file in
        # this directory, .json included) and is read at runtime by several
        # of them (e.g. check_hook_parity.py). The .py-only filter above never
        # registered it, so the widened intra-package closure -- which now
        # sees this read the same way it sees a module import -- reported it
        # as an undeployed dependency even though the phase already ships it.
        if (src / "commit_guardian.json").is_file():
            result.add("scripts/commit_guardian/commit_guardian.json")
    return result


def _manifest_feedback_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/feedback/<name>`` entries for all source .py files.

    Scans ``templates/scripts/feedback/`` (the canonical tracked source
    introduced in ADR-016) so that the manifest is correct on a fresh clone
    where ``scripts/feedback/`` (a gitignored build output) does not yet exist.
    This mirrors ``_manifest_commit_guardian_scripts``, which scans
    ``templates/scripts/commit_guardian/`` for the same reason.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/feedback/<name>`` strings, or empty set when absent.
    """
    result: set[str] = set()
    src = package_root / "templates" / "scripts" / "feedback"
    if src.is_dir():
        for f in src.rglob("*"):
            if f.is_file() and f.suffix == ".py":
                result.add(f"scripts/feedback/{f.relative_to(src).as_posix()}")
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
    """
    result: set[str] = set()
    scripts_src = package_root / "scripts"
    for fname in (
        "add_component.py",
        "knowledge_query.py",
        "set_ticket_status.py",
        "ticket_prioritizer.py",
        "port_registry.py",
        "live_surface_startup.py",
        "generate_doc_index.py",
    ):
        if (scripts_src / fname).is_file():
            result.add(f"scripts/{fname}")
    return result


def _manifest_knowledge_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/knowledge/<name>`` entries for knowledge scripts deployed by build_knowledge_scripts.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/knowledge/<name>`` strings for deployable knowledge scripts.
    """
    result: set[str] = set()
    knowledge_src = package_root / "scripts" / "knowledge"
    for fname in ("harvest_learnings.py",):
        if (knowledge_src / fname).is_file():
            result.add(f"scripts/knowledge/{fname}")
    return result


def _manifest_build_orchestration_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/build_orchestration/<name>`` entries for all source ``.py`` files.

    Scans ``package_root/scripts/build_orchestration/`` and returns one manifest
    entry per Python file, matching what ``build_build_orchestration_scripts``
    deploys to the target project.  The scan is dynamic (rather than a hardcoded
    file list) so a module added to that directory cannot silently drop out of the
    deployable set and reintroduce the BP-900g-4 gap.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/build_orchestration/<name>`` strings, or empty set when
        the directory is absent.
    """
    result: set[str] = set()
    src = package_root / "scripts" / "build_orchestration"
    if src.is_dir():
        for f in src.glob("*.py"):
            if f.is_file():
                result.add(f"scripts/build_orchestration/{f.name}")
    return result


def _manifest_agent_support_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/<rel>`` entries for the scripts ``build_agent_support_scripts`` deploys.

    Derived from the SAME module-level spec the deploy phase iterates
    (``AGENT_SUPPORT_SCRIPT_DIRS`` / ``AGENT_SUPPORT_SCRIPT_FILES`` in
    build_phases), so the declared set and the deployed set cannot drift apart.
    A manifest that disagrees with what is actually deployed is the BP-900g-4
    defect; deriving both from one spec removes the opportunity.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/<rel>`` strings, or empty set when the sources are absent.
    """
    result: set[str] = set()
    scripts_src = package_root / "scripts"

    for dir_name in AGENT_SUPPORT_SCRIPT_DIRS:
        src_dir = scripts_src / dir_name
        if src_dir.is_dir():
            for f in src_dir.rglob("*.py"):
                if f.is_file():
                    result.add(f"scripts/{f.relative_to(scripts_src).as_posix()}")

    for file_name in AGENT_SUPPORT_SCRIPT_FILES:
        if (scripts_src / file_name).is_file():
            result.add(f"scripts/{file_name}")

    return result


def _manifest_template_standalone_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/<name>`` entries for standalone scripts from ``templates/scripts/``.

    Scans the top-level ``templates/scripts/`` directory (non-recursive) for
    ``.py`` files and returns manifest entries.  These are deployed by
    ``build_template_standalone_scripts``.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/<name>`` strings for deployable template-standalone scripts.
    """
    result: set[str] = set()
    templates_scripts = package_root / "templates" / "scripts"
    if templates_scripts.is_dir():
        for f in templates_scripts.glob("*.py"):
            if f.is_file():
                result.add(f"scripts/{f.name}")
    return result


def _manifest_doc_compliance_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/doc_compliance/<rel>`` entries for the doc-compliance package.

    Mirrors ``build_phases.build_doc_compliance``, which rglobs
    ``templates/doc-compliance/`` and copies every file to
    ``<target>/scripts/doc_compliance/`` preserving relative structure.

    KI-BP-023: this phase had no manifest helper, so none of its files entered
    Set B and the closure loop never called the analyser on any of them --
    an entire deployed Python package (``cli.py`` alone has five sibling
    imports) sat outside the guard with no warning and no error.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/doc_compliance/<rel>`` strings, empty when the source
        directory is absent.
    """
    result: set[str] = set()
    dc_dir = package_root / "templates" / "doc-compliance"
    if dc_dir.is_dir():
        for f in dc_dir.rglob("*.py"):
            if f.is_file():
                rel = f.relative_to(dc_dir).as_posix()
                result.add(f"scripts/doc_compliance/{rel}")
        # AC BP-900g-8-ii: doc_compliance.json is deployed verbatim alongside
        # the .py files (build_doc_compliance's rglob copies every file in
        # this directory) and is read at runtime by config.py. The .py-only
        # filter above never registered it -- same shape as the
        # commit_guardian.json fix just above.
        if (dc_dir / "doc_compliance.json").is_file():
            result.add("scripts/doc_compliance/doc_compliance.json")
    return result


def _manifest_sync_platforms_scripts(package_root: Path) -> set[str]:
    """Return ``scripts/sync_platforms/<rel>`` entries for the sync-platforms package.

    Mirrors ``build_phases.build_sync_platforms``, which rglobs
    ``templates/scripts/sync_platforms/`` into
    ``<target>/scripts/sync_platforms/``.

    KI-BP-023 originally proposed fixing this by switching
    ``_manifest_template_standalone_scripts`` from ``glob`` to ``rglob``. That
    would have been wrong: ``build_template_standalone_scripts`` is
    deliberately non-recursive ("excluding subdirectories"), so its manifest's
    shallow glob correctly mirrors it. Widening the glob would have registered
    ``scripts/<name>`` deploy paths for files that phase never writes, adding
    FALSE entries to Set B and generating spurious findings. A manifest helper
    must mirror its phase, not its directory -- so this is a separate helper.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Set of ``scripts/sync_platforms/<rel>`` strings, empty when the source
        directory is absent.
    """
    result: set[str] = set()
    sp_dir = package_root / "templates" / "scripts" / "sync_platforms"
    if sp_dir.is_dir():
        for f in sp_dir.rglob("*.py"):
            if f.is_file():
                rel = f.relative_to(sp_dir).as_posix()
                result.add(f"scripts/sync_platforms/{rel}")
    return result


# DECISION HISTORY
# ================================================================================
# - 2026-09-14 [python-coder]: Created this module, moving the ten
#   _manifest_*_scripts helpers out of build.py (over the check-file-size
#   ratchet) so it could shrink back under it. _get_source_deployable_scripts
#   and _get_source_paths_for_guard stayed in build.py (see module docstring
#   for why: a fixture assumption in unit_tests/test_bp_900g_8_ii.py counts
#   occurrences of a text anchor inside those two functions' own physical
#   copy in scripts/build.py) and now import these ten from here. Pure move,
#   no behaviour change. (#BP-1500g-1/extract-unrelated-headroom)
# ====================================================================
