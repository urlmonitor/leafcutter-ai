"""
MODULE: commit_guardian_module_loader
GOAL: Load a commit_guardian template-source module by name, preferring its
    TRACKED location, templates/scripts/commit_guardian/<name>.py, via a
    scoped importlib.util.spec_from_file_location load.
BUSINESS CONTEXT: scripts/commit_guardian/ is a GITIGNORED build output --
    install_shims()'s copy-strategy fallback of .leafcutter/scripts/commit_guardian/
    on layouts without symlink support (see .gitignore's BP-016 note) -- absent
    on a fresh clone until build.py has run once. A module that needs a
    commit_guardian/ helper at IMPORT TIME, not build time (e.g.
    registry_validator.py, imported by build.py and by the consumer's
    check_agent_registry.py pre-commit hook before any build has run), must
    load it from the tracked source, templates/scripts/commit_guardian/, first
    -- never via a global sys.path insert (which would make every one of the
    ~25 generically-named private modules under commit_guardian/
    bare-importable process-wide). A prior sys.path-based design broke
    exactly this: on a fresh clone, scripts/commit_guardian/ does not exist,
    so registry_validator.py's module-level import raised
    ModuleNotFoundError -- caught by check_agent_registry.py's broad
    `except ImportError`, silently skipping registry validation entirely.
    The gitignored deployed copy is consulted ONLY when the tracked source is
    entirely absent at this file's own location -- mirroring
    agent_spawn_external_callers.py's own source-primary/deployed-fallback
    pattern for templates/workflows-js/ vs .claude/workflows/ -- so a minimal
    test double that copies scripts/ (including its own already-built
    scripts/commit_guardian/) without templates/ still resolves correctly,
    while a genuine fresh clone (templates/ present, scripts/commit_guardian/
    absent) is unaffected: the tracked source always wins when present.
ARCHITECTURE: load_commit_guardian_module(name) tries
    <this file's parent>/../templates/scripts/commit_guardian/<name>.py, then
    <this file's parent>/commit_guardian/<name>.py. This file lives at
    scripts/commit_guardian_module_loader.py in BOTH the leafcutter-ai source
    repo and a consumer install (the package cloned at <repo>/leafcutter/),
    so both relative paths are identical in both layouts -- package_root
    differs, but this file's own position relative to its siblings does not.
    Raises ImportError (fail loudly) naming both paths tried, rather than
    silently degrading a caller's behaviour, when neither location resolves.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_TEMPLATES_COMMIT_GUARDIAN = (
    Path(__file__).resolve().parent.parent / "templates" / "scripts" / "commit_guardian"
)
_DEPLOYED_COMMIT_GUARDIAN = Path(__file__).resolve().parent / "commit_guardian"


def load_commit_guardian_module(name: str) -> ModuleType:
    """Load <name>.py from commit_guardian, tracked source preferred.

    Args:
        name: Module stem, e.g. "agent_spawn_external_callers" (no .py suffix).

    Returns:
        The loaded module object.

    Raises:
        ImportError: If <name>.py is missing from both the tracked source and
            the deployed fallback, or its import spec/loader cannot be built.
    """
    candidates = (
        _TEMPLATES_COMMIT_GUARDIAN / f"{name}.py",
        _DEPLOYED_COMMIT_GUARDIAN / f"{name}.py",
    )
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot construct an import spec for {path}.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    tried = ", ".join(str(c) for c in candidates)
    raise ImportError(f"Cannot locate {name}.py. Tried: {tried}.")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-28 15:00 [python-coder]: Initial creation, in response to a
#   pr-reviewer BLOCKING finding on AC INF-600k-1: registry_validator.py's
#   sys.path insert of the gitignored scripts/commit_guardian/ build output
#   broke on a fresh clone (ModuleNotFoundError, silently swallowed by
#   check_agent_registry.py's `except ImportError`). This loader reads the
#   TRACKED templates/scripts/commit_guardian/ source directly via
#   importlib.util.spec_from_file_location, resolved relative to this file's
#   own location so it works unchanged in the source repo and a consumer
#   install.
# - 2026-09-28 15:30 [python-coder]: Added the deployed-copy fallback after
#   unit_tests/build_orchestration/test_bo2400a_1_iii_step_kinds.py regressed:
#   its fixture copies only scripts/ (including an already-present
#   scripts/commit_guardian/) into a minimal package layout with no
#   templates/ at all. The tracked source still wins whenever present (a
#   genuine fresh clone is unaffected); the deployed copy is consulted only
#   when it is entirely absent. (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
