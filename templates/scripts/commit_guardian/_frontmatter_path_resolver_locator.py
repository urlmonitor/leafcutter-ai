"""
MODULE: _frontmatter_path_resolver_locator
GOAL: Resolve the project root so frontmatter_validators.py can import the
    sibling top-level module scripts/frontmatter_path_resolver.py, across
    every layout this repository's commit-guardian hook runs in.
BUSINESS CONTEXT: frontmatter_validators.py's validate_paths() must call
    resolve_frontmatter_path_entry() to classify each related_docs /
    related_code / architecture_diagrams entry (GE-118d). That resolver
    lives in scripts/frontmatter_path_resolver.py, a NEW top-level,
    verbatim-copy-tier module -- never under templates/scripts/commit_guardian/
    or its compiled deploy targets, see that module's own docstring for the
    placement rationale. frontmatter_validators.py therefore needs to reach
    OUT of its own directory to import it, in every layout the guard runs
    from: the raw templates/ source tree, a real build.py deploy (where
    ``<target>/scripts/commit_guardian`` is a SYMLINK whose realpath is
    ``<target>/.leafcutter/scripts/commit_guardian`` -- so a naive
    ``Path(__file__).resolve().parent.parent`` lands in
    ``.leafcutter/scripts/`` and misses the real top-level
    ``scripts/frontmatter_path_resolver.py`` entirely), and a self-hosted
    dev workspace build.
ARCHITECTURE: A sibling module inside templates/scripts/commit_guardian/ --
    build_commit_guardian (scripts/build_phases_lifecycle.py) copies every
    file in that directory verbatim (via ``cg_dir.rglob("*")``) to
    ``<output_root>/scripts/commit_guardian/``, so this file needs no entry
    of its own in any hardcoded deploy_map; it deploys purely by being a
    sibling of frontmatter_validators.py, the same way ``_resolve_root.py``
    and ``_ac_store_locator.py`` already do.

    Two candidates, in priority order (mirroring
    ``_ac_store_locator.resolve_ac_store_dir()``'s own two-candidate shape
    exactly -- see that module's docstring for why each candidate exists):

    1. The immediate sibling ``frontmatter_path_resolver.py`` next to this
       file's own directory (``_HERE.parent / "frontmatter_path_resolver.py"``)
       -- correct for the deployed layout and a self-hosted dev workspace
       build, where ``build_workflow_tools()`` (despite its own docstring's
       ``<target_root>/scripts/`` wording) is actually invoked with
       ``output_root`` as its ``target_root`` argument, so the resolver
       lands at ``<output_root>/scripts/frontmatter_path_resolver.py`` --
       a TRUE sibling of ``<output_root>/scripts/commit_guardian/``, the
       realpath ``Path(__file__).resolve()`` reports even when
       ``<target_root>/scripts/commit_guardian`` is a SYMLINK to it.
    2. A project-root walk from THIS FILE'S OWN location (never
       ``Path.cwd()``, and never ``_resolve_root.find_project_root()``'s
       ``git rev-parse --show-toplevel`` preference -- both report an
       unrelated repository when the current process's working directory
       has been set to a scratch git repo, e.g. a unit test that
       ``git init``'s a throwaway directory as the subprocess ``cwd`` for
       the SOURCE-tree guard invocation; see ``_ac_store_locator.py``'s own
       docstring for the identical hazard on ``ac_store/``) looking for a
       ``.git`` directory or a ``CLAUDE.md`` file, then
       ``<project_root>/scripts/frontmatter_path_resolver.py``. This is the
       shape of the raw ``templates/scripts/commit_guardian/`` source tree,
       where candidate 1 resolves to a nonexistent
       ``templates/scripts/frontmatter_path_resolver.py`` and the real
       module lives at the true project root's ``scripts/`` directory
       instead -- not a sibling of this file at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def resolve_frontmatter_path_resolver_module() -> Path | None:
    """Return the path to scripts/frontmatter_path_resolver.py, if found.

    Tries the immediate-sibling candidate first (deployed / self-hosted
    layout), then falls back to a project-root walk from this file's own
    resolved location (source-tree layout) -- see the module docstring for
    why each candidate exists and why neither uses ``Path.cwd()``.

    Returns:
        Path | None: The first candidate path that actually exists, or
            ``None`` when neither does.
    """
    sibling = _HERE.parent / "frontmatter_path_resolver.py"
    if sibling.is_file():
        return sibling

    for ancestor in [_HERE, *_HERE.parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            candidate = ancestor / "scripts" / "frontmatter_path_resolver.py"
            return candidate if candidate.is_file() else None
    return None


def ensure_frontmatter_path_resolver_on_syspath() -> None:
    """Insert the resolved module's directory onto ``sys.path``, if found.

    A no-op when :func:`resolve_frontmatter_path_resolver_module` finds no
    candidate -- the caller's subsequent
    ``from frontmatter_path_resolver import ...`` then raises
    ``ModuleNotFoundError`` normally, with no fallback swallowed here.
    """
    module_path = resolve_frontmatter_path_resolver_module()
    if module_path is not None:
        scripts_dir = str(module_path.parent)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
