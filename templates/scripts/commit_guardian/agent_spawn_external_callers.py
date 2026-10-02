"""
MODULE: agent_spawn_external_callers
GOAL: Single shared definition of "recognized external caller" for a
    spawned_by entry that is not a registry agent id -- the literal "user"
    trigger, or the filename of a workflow that really exists on disk under
    the package's templates/workflows-js/ source directory (falling back to
    the deployed .claude/workflows/ directory only when the source directory
    itself is entirely absent).
BUSINESS CONTEXT: registry_validator.py (build-time / check-agent-registry
    validation) and check_agent_spawn_consistency.py (the pre-commit hook)
    both classify a spawned_by entry that is not a registry agent id. Before
    AC INF-600k-1 the two files each held an independent closed literal set,
    _EXTERNAL_CALLERS = {"user", "finalize-feature.js"}, so a real workflow
    filename such as "fast-lane-ship.js" was rejected as an unknown agent by
    both (see BO-2400a-1-i, whose command-step-runner had to ship with
    spawned_by: ["user"] instead of naming its real spawning workflow). This
    module is the ONE definition both callers use, derived from files that
    really exist on disk rather than a second hand-maintained list, so the
    two checks cannot diverge again and a new workflow file is recognized
    with no code edit.
ARCHITECTURE: A plain top-level module with no package ``__init__``
    dependency, so it can be loaded two different ways from two different
    layouts without either caller needing the other's loading mechanism:
      - registry_validator.py's sibling spawn_bidirectionality_validator.py
        loads it via commit_guardian_module_loader.load_commit_guardian_module(),
        a SCOPED importlib.util.spec_from_file_location read of THIS file's
        tracked source location, templates/scripts/commit_guardian/ -- never
        a sys.path insert of the GITIGNORED scripts/commit_guardian/ build
        output, which is absent on a fresh clone (see
        commit_guardian_module_loader.py's own docstring for the incident
        this fixed: a prior sys.path-based design broke registry validation
        silently on a fresh clone).
      - check_agent_spawn_consistency.py (the standalone pre-commit hook,
        deployed with no leafcutter-internal package on its Python path)
        inserts this file's own directory onto sys.path and imports it as a
        bare top-level module, preserving that hook's "no leafcutter-internal
        imports" portability constraint.
    Deployed via build_commit_guardian(), which copies the whole
    templates/scripts/commit_guardian/ tree verbatim, so this file always
    lands next to the hook that needs it in every layout: the template
    source tree, this repo's tracked scripts/ round-trip copy, and a
    consumer project's deployed .leafcutter/ copy.
"""

from __future__ import annotations

from pathlib import Path

_LITERAL_EXTERNAL_TRIGGERS = frozenset({"user"})
_WORKFLOW_SOURCE_SUBDIR = ("templates", "workflows-js")
_WORKFLOW_DEPLOYED_SUBDIR = (".claude", "workflows")


def is_recognized_external_caller(name: str, package_root: Path) -> bool:
    """Classify a spawned_by entry that is not a known registry agent id.

    Args:
        name: The spawned_by entry to classify (e.g. "user",
            "fast-lane-ship.js", or an arbitrary non-agent name).
        package_root: Absolute path to the package root under which
            templates/workflows-js/ (authoritative source) or
            .claude/workflows/ (deployed fallback) is looked up.

    Returns:
        True when name is the literal "user" trigger, or the filename of a
        workflow file that really exists on disk. False otherwise -- name
        is then an unknown agent.
    """
    if name in _LITERAL_EXTERNAL_TRIGGERS:
        return True
    return name in _real_workflow_filenames(package_root)


def _real_workflow_filenames(package_root: Path) -> frozenset[str]:
    """Return the set of real workflow filenames under *package_root*.

    The tracked package source, templates/workflows-js/, is the sole
    authority whenever it exists -- even if it is empty. The deployed
    .claude/workflows/ output is read only as a fallback when the source
    directory is entirely absent (a consumer layout running the deployed
    hook with no templates/ tree of its own). A name present only in the
    deployed directory is therefore never accepted while the source
    directory exists.

    Args:
        package_root: Absolute path to the package root.

    Returns:
        Frozenset of ``*.js`` filenames (name only, not full path) found in
        the authoritative directory. Empty frozenset when neither directory
        is present or readable.
    """
    source_dir = package_root.joinpath(*_WORKFLOW_SOURCE_SUBDIR)
    if source_dir.is_dir():
        return _js_filenames(source_dir)
    deployed_dir = package_root.joinpath(*_WORKFLOW_DEPLOYED_SUBDIR)
    if deployed_dir.is_dir():
        return _js_filenames(deployed_dir)
    return frozenset()


def _js_filenames(directory: Path) -> frozenset[str]:
    """Return the ``*.js`` filenames directly inside *directory*.

    Args:
        directory: Absolute path to a directory expected to hold workflow
            ``*.js`` files.

    Returns:
        Frozenset of filenames (e.g. "fast-lane-ship.js"). Empty frozenset
        on any OSError (permission denied, race with concurrent deletion) --
        an unreadable workflow directory must never crash the calling
        validator or hook.
    """
    try:
        return frozenset(
            entry.name
            for entry in directory.iterdir()
            if entry.is_file() and entry.suffix == ".js"
        )
    except OSError:
        return frozenset()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-28 14:00 [python-coder]: Initial creation. Single shared
#   classification of a spawned_by entry that is not a registry agent id,
#   consumed by both scripts/registry_validator.py and
#   templates/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py
#   (AC INF-600k-1). Replaces the two independently-maintained closed
#   literal sets, {"user", "finalize-feature.js"}, with one rule derived
#   from real files on disk under templates/workflows-js/ (falling back to
#   .claude/workflows/ only when the source directory is entirely absent).
#   "finalize-feature.js" needs no literal entry any more -- it is a real
#   file under templates/workflows-js/ and is accepted by the directory read
#   like any other workflow. (#TICKETLESS reason=inf-600k-1-workflow-callers)
# - 2026-09-28 15:00 [python-coder]: Corrected the ARCHITECTURE section: a
#   pr-reviewer finding caught that registry_validator.py's original sys.path
#   insert of the gitignored scripts/commit_guardian/ broke on a fresh clone.
#   registry_validator.py's caller now loads this file via the new
#   commit_guardian_module_loader.py, which reads the TRACKED
#   templates/scripts/commit_guardian/ source by file path -- documented
#   accurately in place of the old (incorrect) `commit_guardian.<mod>` claim.
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
