"""
MODULE: build_closure_guard
GOAL: Own the BP-900g-8 intra-package closure guard's deploy-path-to-source
    resolution: given a Set-B deploy path (a ``scripts/<...>``,
    ``config/<...>`` or ``docs/<...>`` entry from
    ``build._get_source_deployable_scripts``), resolve the real source file
    and the closure-analysis root to walk it from
    (``_source_file_for_deploy_path``), and attribute a missing-dependency
    finding to the build_phases.py phase that would have to carry it
    (``_phase_for_deploy_path``).
BUSINESS CONTEXT: Extracted out of ``scripts/build.py`` to keep that file
    under the GE-127b-1 file-size ratchet (it must not grow past its pinned
    main baseline; see ``unit_tests/test_km_kgs_100a_3_xi.py::
    test_over_limit_build_wiring_files_do_not_grow_vs_main``). This block
    grew a ~40-line special case for ACD-2100b-5 (rooting
    ``check_workspace_setup_permission.py``'s closure at
    ``package_root / ".leafcutter"`` so its registry-path read resolves to
    the already-declared ``config/agent_registry.json`` rather than a
    spurious ``.leafcutter/config/agent_registry.json`` no deploy phase
    declares) that pushed build.py over the ratchet, the same pressure
    ``build_phases_ac_store.py``, ``build_phases_workflows.py``, and
    ``build_phases_local_change.py`` were split out to relieve. No behaviour
    change from the pre-split implementation.
ARCHITECTURE: Sibling module to ``build.py``, imported by it
    (``_source_file_for_deploy_path`` and ``_phase_for_deploy_path`` land on
    the ``build`` module namespace via that import, so existing test access
    via ``build._source_file_for_deploy_path`` is unaffected). Deliberately
    does NOT import anything back from ``build.py`` itself — the closure
    guard's own preflight caller, ``build._check_intra_package_closure_guard``,
    stays in ``build.py`` because it needs ``build._get_source_deployable_
    scripts``, a function this module must not depend on (doing so would
    create a circular import, since ``build.py`` imports this module at load
    time, well before ``_get_source_deployable_scripts`` is defined in it).
    This module's own two entry points need only ``build_phases``'
    ``AC_STORE_DEPLOY_MAP``, ``AGENT_SUPPORT_SCRIPT_DIRS``, and
    ``AGENT_SUPPORT_SCRIPT_FILES`` -- a lower-layer dependency, not build.py.
"""

from __future__ import annotations

from pathlib import Path

from build_phases import (
    AC_STORE_DEPLOY_MAP,
    AGENT_SUPPORT_SCRIPT_DIRS,
    AGENT_SUPPORT_SCRIPT_FILES,
)

_AC_STORE_DEST_TO_SOURCE: dict[str, str] = {
    dest_name: src_rel for src_rel, dest_name in AC_STORE_DEPLOY_MAP
}

# Deploy-path prefix -> owning build_phases.py phase function name, used only
# to attribute a closure-guard finding to the phase that would have to carry
# the missing dependency (AC BP-900g-8's Gherkin requires naming the phase).
# Attribution is diagnostic, not load-bearing for the pass/fail verdict.
_CLOSURE_GUARD_PHASE_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("scripts/ac_store/", "build_ac_store"),
    ("scripts/commit_guardian/", "build_commit_guardian"),
    ("scripts/feedback/", "build_feedback"),
    ("scripts/knowledge/", "build_knowledge_scripts"),
    ("scripts/build_orchestration/", "build_build_orchestration_scripts"),
)

# AC BP-900g-8-ii review finding: `config/` and `docs/` are NOT reliable
# phase discriminators by prefix. `config/feedback_categories.yaml` is
# deployed by build_feedback, not build_ac_store, and several phases write
# files under `docs/` (not only build_components_registry). A prefix
# heuristic over these two directories was correct only by coincidence --
# every `config/` entry the guard could see on the day it was written
# happened to be a build_ac_store "core config" file, and the only `docs/`
# entry was docs/components.json. Mapping by the file's EXACT deploy-path
# name (derived from the same core-config tuples _get_source_deployable_
# scripts/_get_source_paths_for_guard already enumerate) keeps this hint
# honest for a name it does not recognise, rather than confidently naming
# the wrong phase. This only affects the human-readable remediation hint in
# the abort message -- never the pass/fail verdict.
_CONFIG_FILE_PHASE_BY_NAME: dict[str, str] = {
    "ac_store_schema.json": "build_ac_store",
    "agent_registry.json": "build_ac_store",
    "doc_types.json": "build_ac_store",
    "diagram_types.json": "build_ac_store",
    "skill_registry.json": "build_ac_store",
    "guardrail_gates.yaml": "build_ac_store",
    "paths.json": "build_ac_store",
    "phase_deferral.yaml": "build_ac_store",
    "feedback_categories.yaml": "build_feedback",
    "knowledge_sink.json": "build_knowledge_sink_declaration",
    "entry_kind_vocabulary.json": "build_knowledge_scripts",
    "reachability_exemptions.yaml": "build_config_scaffolds",
    "roadmap.schema.json": "build_commit_guardian",
}
_DOCS_FILE_PHASE_BY_NAME: dict[str, str] = {
    "components.json": "build_components_registry",
    "roadmap.json": "build_roadmap",
}


def _phase_for_deploy_path(deploy_path: str) -> str:
    """Return the build_phases.py phase function name that owns *deploy_path*.

    Args:
        deploy_path: A ``scripts/<...>`` deploy-namespace path, e.g. one
            returned in a script's intra-package closure.

    Returns:
        The best-effort ``build_<name>`` phase function name responsible for
        deploying paths with this prefix. Falls back to a joined label naming
        the remaining candidate phases when no prefix matches, since
        attribution here is diagnostic rather than authoritative.
    """
    for prefix, phase in _CLOSURE_GUARD_PHASE_BY_PREFIX:
        if deploy_path.startswith(prefix):
            return phase
    for dir_name in AGENT_SUPPORT_SCRIPT_DIRS:
        if deploy_path.startswith(f"scripts/{dir_name}/"):
            return "build_agent_support_scripts"
    if deploy_path in {f"scripts/{f}" for f in AGENT_SUPPORT_SCRIPT_FILES}:
        return "build_agent_support_scripts"
    # AC BP-900g-8-ii: non-code (config/docs) deploy paths, added once the
    # closure guard was taught to see data-file reads. Matched by EXACT
    # filename, not prefix -- see the DECISION comment above
    # _CONFIG_FILE_PHASE_BY_NAME for why a `config/`/`docs/` prefix match is
    # not a safe discriminator on its own.
    if deploy_path.startswith("config/"):
        name = deploy_path[len("config/"):]
        return _CONFIG_FILE_PHASE_BY_NAME.get(
            name, "an unmapped config/-writing phase (see build_phases.py)"
        )
    if deploy_path.startswith("docs/"):
        name = deploy_path[len("docs/"):]
        return _DOCS_FILE_PHASE_BY_NAME.get(
            name, "an unmapped docs/-writing phase (see build_phases.py)"
        )
    return "build_workflow_tools or build_template_standalone_scripts"


def _source_file_for_deploy_path(
    package_root: Path, deploy_path: str
) -> tuple[Path, Path, str] | None:
    """Resolve a Set-B deploy path to the source file and closure namespace to analyse.

    Args:
        package_root: Absolute path to the leafcutter package root.
        deploy_path: A ``scripts/<...>`` entry from ``_get_source_deployable_scripts``.

    Returns:
        A ``(source_file, root, deploy_prefix)`` triple. Closure entries are
        computed relative to *root* and then prefixed with *deploy_prefix*, so
        the resulting strings land in the SAME deploy namespace as
        *deploy_path* itself and can be compared against Set B directly.
        *deploy_prefix* is ``""`` for every family whose source layout already
        mirrors its deploy layout. Returns None when no real source file can be
        located (the guard skips rather than crashes).
    """
    if deploy_path.startswith("scripts/ac_store/"):
        dest_name = deploy_path[len("scripts/ac_store/"):]
        src_rel = _AC_STORE_DEST_TO_SOURCE.get(dest_name)
        if src_rel is not None:
            return package_root / src_rel, package_root, ""

    # doc-compliance is the one family whose source directory name differs from
    # its deploy directory name (``templates/doc-compliance/`` ->
    # ``scripts/doc_compliance/``, hyphen vs underscore). No choice of closure
    # root can bridge that, so this family carries an explicit prefix.
    #
    # It must be checked BEFORE the `direct` fallback below. In a worktree that
    # has run install_shims, ``<package_root>/scripts/doc_compliance`` exists as
    # a SYMLINK into the deployed .leafcutter tree — so the fallback would
    # resolve it, follow the link, and analyse BUILD OUTPUT as though it were
    # source, returning dependencies prefixed ``.leafcutter/`` that match
    # nothing in Set B. That produced 14 phantom "undeployed dependency"
    # findings on a tree where nothing was actually missing.
    if deploy_path.startswith("scripts/doc_compliance/"):
        rel = deploy_path[len("scripts/doc_compliance/"):]
        dc_source = package_root / "templates" / "doc-compliance" / rel
        if dc_source.is_file():
            return (
                dc_source,
                package_root / "templates" / "doc-compliance",
                "scripts/doc_compliance/",
            )

    # Template-mirrored categories (commit_guardian, feedback, sync_platforms,
    # template-standalone): source lives under templates/<deploy_path>;
    # stripping the templates/ prefix on the CLOSURE ROOT (not the path itself)
    # makes the returned dependency strings land directly in deploy namespace.
    templated = package_root / "templates" / deploy_path
    if templated.is_file():
        return templated, package_root / "templates", ""

    # ACD-2100b-5 path-form mismatch (found alongside AC BP-900g-8-ii, worktree
    # merge 2026-09-14): check_workspace_setup_permission.py has NO sibling-module
    # import (its own build_phases.py deploy-declaration comment says so — stdlib
    # only), so nothing here needs the package_root-relative module namespace the
    # "direct" family fallback below gives every other standalone script. Its only
    # intra-package reference is a runtime DATA read of the agent registry
    # (REGISTRY_RELATIVE_PATH = Path(".leafcutter") / "config" /
    # "agent_registry.json"), and it is deliberately written the way the DEPLOYED
    # script sees it — relative to the deploy OUTPUT ROOT — because the script must
    # discover the real repo root dynamically via git, never via a fixed
    # __file__-anchored parent walk. Rooting the closure at package_root itself (the
    # "direct" fallback) makes this candidate resolve with a spurious literal
    # ".leafcutter/" segment baked into the reported dependency string whenever
    # package_root already contains a built ``.leafcutter/`` directory (true for a
    # self-hosted, previously-built tree, and ONLY reachable in that case: this
    # candidate is resolved by the guard's `_eval_static_path` evaluator against
    # the process's OWN cwd, and only exists on disk pre-build in the self-hosted
    # case) — a path nothing in Set B declares, because Set B's
    # "config/agent_registry.json" entry is itself already expressed relative to
    # the deploy output root. Rooting THIS script's closure at
    # ``package_root / ".leafcutter"`` instead makes the same candidate resolve to
    # "config/agent_registry.json", the form already declared — so this is a
    # declaration/wiring correction, not a change to the closure algorithm itself
    # (build_referential_integrity.py is untouched). ".leafcutter" is hardcoded
    # rather than read from config here because the guard runs pre-build, before
    # any target-specific config is available to this preflight, and because the
    # only context in which this candidate is even resolvable (see above) is the
    # package's own self-hosted default-configured install.
    #
    # KNOWN LIMITATION: if this file ever gains a sibling-module import, that
    # dependency's closure entry would be computed relative to
    # ``package_root / ".leafcutter"`` too, and would fail to resolve (silently
    # dropped, not reported) rather than being checked against Set B. Acceptable
    # today because no such import exists; a future author adding one must revisit
    # this special case.
    if deploy_path == "scripts/worktree/check_workspace_setup_permission.py":
        worktree_setup_source = package_root / deploy_path
        if worktree_setup_source.is_file():
            return worktree_setup_source, package_root / ".leafcutter", ""

    # Everything else (build_orchestration, knowledge, agent-support,
    # workflow-tool scripts): source and deploy namespaces coincide directly
    # under package_root.
    #
    # Only reached by families whose source genuinely lives at this path. Any
    # future family that does NOT must be given an explicit branch above, or a
    # deployed symlink here will silently stand in for its source.
    direct = package_root / deploy_path
    if direct.is_file():
        return direct, package_root, ""

    return None


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-08-25 [python-coder/BP-900g-8]: Initial authoring of
#   _source_file_for_deploy_path and _phase_for_deploy_path inside
#   scripts/build.py, alongside _check_intra_package_closure_guard.
# - 2026-09-14 [python-coder/ACD-2100b-5]: Added the
#   check_workspace_setup_permission.py special case rooting its closure at
#   package_root / ".leafcutter" so its registry-path data read resolves to
#   the already-declared "config/agent_registry.json" form.
# - 2026-09-22 [python-coder/EPIC-StartingNewWorkTheProperWayAlways]:
#   Extracted _AC_STORE_DEST_TO_SOURCE, _CLOSURE_GUARD_PHASE_BY_PREFIX,
#   _CONFIG_FILE_PHASE_BY_NAME, _DOCS_FILE_PHASE_BY_NAME,
#   _phase_for_deploy_path, and _source_file_for_deploy_path out of
#   scripts/build.py into this sibling module, to bring build.py back under
#   the GE-127b-1 file-size ratchet's pinned main baseline (1803 content
#   lines) after the ACD-2100b-5 special case pushed it to 1862. No
#   behaviour change; build.py imports both public names back so existing
#   `build._source_file_for_deploy_path` test access is unaffected.
#   (#GE-127b-1/build-py-ratchet)
# ===========================================================================
