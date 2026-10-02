"""
MODULE: package_root_lookup
GOAL: Give hooks living in the ``commit_guardian/hooks/`` subdirectory an
    importable home for the shared root-resolution functions
    (``find_project_root``, ``resolve_package_root``, re-exported from
    ``_resolve_root.py``) and own the spawn-consistency hook's
    warn-and-fall-back root policy, ``resolve_package_root_or_project_root``.
BUSINESS CONTEXT: ``scripts/ci/check_declaring_files.py`` (AC BP-900h-4)
    treats a bare ``from _resolve_root import ...`` as naming a module that
    sits NEXT TO the importing file. That is true for every hook directly in
    ``commit_guardian/``, but ``hooks/check_agent_spawn_consistency.py``
    (AC INF-600k-1) lives one level down, so its import made the inspection
    demand a ``hooks/_resolve_root.py`` that does not (and must not) exist,
    failing the consumer install simulation. Here the import IS a sibling
    import, so the inspection resolves it against the real
    ``commit_guardian/_resolve_root.py``; the hook then imports this
    non-underscore module from its parent directory. No declaring file is
    exempted and ``_resolve_root.py`` is not duplicated into ``hooks/``.
ARCHITECTURE: A sibling module in ``commit_guardian/``, deployed alongside
    the hooks by ``build_commit_guardian()`` exactly like
    ``agent_spawn_external_callers.py`` and ``card_mermaid_parser.py``, and
    imported by the hook through the adjacent ``sys.path`` entry the hook
    already sets up. The two re-exported names ARE the ``_resolve_root``
    functions. ``resolve_package_root_or_project_root`` is the spawn hook's own
    policy wrapper, moved here unchanged from the hook: on a missing manifest
    it WARNS and falls back to the repo root instead of blocking (see its
    docstring).
"""

from __future__ import annotations

import sys
from pathlib import Path

from _resolve_root import find_project_root, resolve_package_root

__all__ = ["find_project_root", "resolve_package_root", "resolve_package_root_or_project_root"]


def resolve_package_root_or_project_root(hook_file: Path) -> Path:
    """Resolve the package root the GE-113c-1-vi way (AC INF-600k-1).

    Delegates to ``_resolve_root.resolve_package_root()`` — the SAME lookup
    check_agent_registry.py uses — rather than a hand-rolled ``git
    rev-parse`` (the prior placeholder). Unlike check_agent_registry.py, this
    hook's own policy on a miss is WARN, not block: it validates spawn
    consistency, and AC INF-600k-1 does not require blocking the commit when
    no manifest can be found. This mirrors check_build_drift.py's /
    check_output_drift.py's warn-and-continue policy on the identical
    missing-manifest condition (a fresh clone with no manifest yet must not
    self-block) rather than check_agent_registry.py's block policy (a
    different gate's different criterion — see ``_resolve_root.py``'s own
    "POLICY IS NOT SHARED" docstring note).

    Args:
        hook_file: The calling hook's own ``__file__`` path, the anchor for the
            manifest-root search.

    Returns:
        The resolved package root, or ``_resolve_root.find_project_root()``
        (the repo root) with a WARNING to stderr when no manifest could be
        located. Never raises, never returns ``None``.
    """
    package_root, tried = resolve_package_root(hook_file)
    if package_root is not None:
        return package_root
    tried_str = "\n  ".join(tried)
    print(
        "[check-agent-spawn-consistency] WARNING: no .build_manifest.json "
        f"resolved a package root; falling back to the repo root. Tried:\n  {tried_str}",
        file=sys.stderr,
    )
    return find_project_root()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 15:10 [python-coder]: Initial creation. Fixes the CI
#   "DECLARING FILES CHECK FAILED ... hooks/_resolve_root.py" failure
#   (Consumer install simulation, BP-900h-4 tests) without touching the
#   inspection: the only underscore-prefixed import the hooks/-nested hook
#   made was _resolve_root, and moving it behind this sibling module makes
#   the inspection's "import names a sibling" rule literally true.
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# - 2026-09-30 16:00 [python-coder/INF-600k-1]: Moved the spawn hook's
#   _resolve_package_root() here as resolve_package_root_or_project_root(hook_file)
#   (pure move; policy and WARNING text identical; the hook's _HOOK_FILE is now
#   the hook_file argument) so the hook shrinks under GE-127f-2's
#   grew-while-over-limit rule. (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
