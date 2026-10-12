"""
MODULE: scripts/ac_store/_declared_files_path_form.py
GOAL: Lexical path-form refusals for the ACD-1600c-4 declared_files seam --
    absolute/escaping paths, backslashes, regenerated-copy roots, and
    non-canonical spellings (H-1) -- plus `load_build_definition`, the real
    regenerated-root -> source-root mapping these refusals match against.
BUSINESS CONTEXT: Extracted out of scripts/ac_store/declared_files.py, which
    must stay under the check-file-size ratchet (400 content-lines); the H-1
    review-finding fix (normalise-to-match, refuse-non-canonical-spelling,
    ACD-1600c-4-iii) would have pushed that file to 410. This family is
    already the seam's single largest, most self-contained piece (one
    read-only concern: is this declared path spelled and placed the way the
    store requires), so it is what moves -- mirroring the same
    "carry the glue in a sibling, not the oversized file" pattern
    _declared_files_bridge.py already established for check_ac_schema.py.
ARCHITECTURE: `declared_files.py` imports and re-exposes `path_form_errors`
    and `load_build_definition` from here unchanged -- the seam's public
    API (unit_tests/ac_store/_declared_files_fixtures.py's SEAM CONTRACT)
    is unaffected; callers still reach both names as `declared_files.*`.
    Canonical source is directly at scripts/ac_store/ (tracked in git, no
    templates/ counterpart), same as declared_files.py itself; listed in
    build_phases_ac_store.AC_STORE_DEPLOY_MAP immediately after
    declared_files.py so it deploys alongside its only importer
    (ADR-026 safety rule 2: deploy-manifest-first).

DECISION HISTORY:
  - 2026-09-28 [python-coder/ACD-1600c-4]: Created, extracting
    _is_absolute_or_escaping, _regenerated_copy_error, path_form_errors,
    _shim_map_roots, _iter_gitignore_shim_roots, _probe_source_prefix, and
    load_build_definition out of declared_files.py (pure move, no behaviour
    change to any of them beyond the H-1 fix landing in the same pass:
    _canonical_form and its two call sites -- the regenerated-root match now
    compares the canonicalised, case-folded path so a leading './', a
    repeated '/', or a case-varied spelling of a regenerated root can no
    longer escape the refusal; a path that is non-canonical on its own
    terms, and not itself a regenerated-copy match, is now refused too,
    naming the canonical spelling, rather than silently accepted).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# scripts/ac_store/_declared_files_path_form.py -> repo root is two parents up.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_SHIM_BLOCK_MARKER = "shims underneath"


def _is_absolute_or_escaping(path: str) -> bool:
    """Return True for a POSIX-absolute path or one escaping the repo root.

    Lexical only -- no filesystem access, no symlink resolution.
    """
    if path.startswith("/"):
        return True
    if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
        return True  # Windows drive-letter absolute path (C:\ or C:/).
    return ".." in path.split("/")


def _canonical_form(path: str) -> str:
    """Collapse a leading './', repeated '/', and a trailing '/'.

    Lexical only, case preserved -- this is the ONE canonical spelling a
    declared path must use (H-1: a non-canonical spelling must never be
    silently accepted or silently normalised through).
    """
    result = path
    while result.startswith("./"):
        result = result[2:]
    while "//" in result:
        result = result.replace("//", "/")
    if len(result) > 1 and result.endswith("/"):
        result = result[:-1]
    return result


def _regenerated_copy_error(
    record_id: str, path: str, build_definition: dict[str, str | None]
) -> str | None:
    """Return one refusal message when `path` sits under a regenerated root.

    H-1: matched on the CANONICALISED, case-folded form of `path` (a leading
    './', repeated '/', or a case-varied spelling of a regenerated root must
    not escape this refusal) -- the message still echoes `path` exactly as
    declared, and the mapped source is built from the canonical remainder.
    """
    canonical = _canonical_form(path)
    canonical_fold = canonical.lower()
    for regenerated_prefix, source_prefix in build_definition.items():
        if not canonical_fold.startswith(regenerated_prefix.lower()):
            continue
        if source_prefix is None:
            return (
                f"{record_id}: declared path '{path}' is inside a copy the "
                "build regenerates, and no source could be determined."
            )
        mapped = source_prefix + canonical[len(regenerated_prefix):]
        return (
            f"{record_id}: declared path '{path}' is inside a copy the "
            f"build regenerates; declare '{mapped}' instead."
        )
    return None


def path_form_errors(
    record_id: str,
    declared_files_value: Any,
    *,
    build_definition: dict[str, str | None] | None = None,
) -> list[str]:
    """One message per entry whose path form is refused.

    Purely lexical: no existence check, no symlink resolution. Refuses an
    absolute path or one that escapes the repository root, any path
    containing a backslash, any path under a regenerated-copy root (per
    `build_definition`, defaulting to `load_build_definition()`'s real
    mapping, matched case-insensitively on the canonical form -- H-1), and
    any OTHER path whose own spelling is non-canonical (a leading './', an
    internal '//', or a trailing '/') -- refused naming the canonical
    spelling, never silently normalised through (H-1).

    Args:
        record_id: The AC id, for message attribution.
        declared_files_value: The raw `declared_files` field value.
        build_definition: Regenerated-root -> source-root mapping. Defaults
            to `load_build_definition()` when not supplied.

    Returns:
        One message per offending entry; empty when every path is clean.
    """
    if build_definition is None:
        build_definition = load_build_definition()
    if not isinstance(declared_files_value, list):
        return []

    errors: list[str] = []
    for entry in declared_files_value:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if not path:
            continue  # Reported by declared_files_shape_errors already.
        if "\\" in path:
            errors.append(
                f"{record_id}: declared path '{path}' must use forward "
                "slashes, not backslashes."
            )
            continue
        if _is_absolute_or_escaping(path):
            errors.append(
                f"{record_id}: declared path '{path}' must be relative to "
                "the repository root and stay inside it."
            )
            continue
        regen_error = _regenerated_copy_error(record_id, path, build_definition)
        if regen_error:
            errors.append(regen_error)
            continue
        canonical = _canonical_form(path)
        if canonical != path:  # H-1: non-canonical spelling, refused not normalised.
            errors.append(
                f"{record_id}: declared path '{path}' is not in canonical "
                f"form; declare '{canonical}' instead."
            )
    return errors


def _shim_map_roots(repo_root: Path) -> list[str] | None:
    """Regenerated-root entries read from the build's real in-code
    definition: `build_helpers.shim_map` -- the SAME module-level table
    `install_shims()` iterates to create each shim, and
    `_compute_output_mappings()` reuses to key output_mappings the same way
    (see that constant's own comment: "the SINGLE source of truth"). This is
    the primary source; `_iter_gitignore_shim_roots()` below is only a
    fallback for a layout where scripts/build_helpers.py -- a build-engine
    file never shipped to a consumer install, unlike scripts/ac_store/ -- is
    not reachable.

    Args:
        repo_root: Repository root to import scripts/build_helpers.py from.

    Returns:
        `[canonical_rel, ...]` in shim_map order, or None when
        scripts/build_helpers.py cannot be imported from repo_root.
    """
    scripts_dir = repo_root / "scripts"
    if not (scripts_dir / "build_helpers.py").is_file():
        return None
    scripts_str = str(scripts_dir)
    added = scripts_str not in sys.path
    if added:
        sys.path.insert(0, scripts_str)
    try:
        import build_helpers  # type: ignore[import-not-found]
    except ImportError as exc:
        print(
            f"declared_files: WARNING: cannot import build_helpers from "
            f"{scripts_dir} ({exc}); falling back to .gitignore-derived "
            "regenerated roots.",
            file=sys.stderr,
        )
        return None
    finally:
        if added:
            sys.path.remove(scripts_str)
    return [canonical_rel for canonical_rel, _output_rel in build_helpers.shim_map]


def _iter_gitignore_shim_roots(repo_root: Path) -> list[str]:
    """Fallback regenerated-root entries from the project's own .gitignore.

    Used only when `_shim_map_roots()` cannot import
    scripts/build_helpers.py (e.g. a deployed consumer install, where that
    build-engine file is not shipped). Reads the block immediately following
    the "# .claude/* shims underneath." comment -- data the build already
    maintains there for the exact same shims, so a new regenerated root is
    still picked up automatically without a second, hand-maintained list.

    Args:
        repo_root: Repository root to read .gitignore from.

    Returns:
        Root path strings (no trailing slash), in .gitignore order.
    """
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return []
    try:
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(
            f"declared_files: WARNING: cannot read {gitignore}: {exc}",
            file=sys.stderr,
        )
        return []

    roots: list[str] = []
    in_block = False
    for line in lines:
        stripped = line.strip()
        if _SHIM_BLOCK_MARKER in stripped:
            in_block = True
            continue
        if not in_block:
            continue
        if not stripped:
            break
        if stripped.startswith("#"):
            continue
        roots.append(stripped.rstrip("/"))
    return roots


def _probe_source_prefix(root_entry: str, repo_root: Path) -> str | None:
    """Find the templates/ directory a regenerated root is compiled from.

    Probes the naming conventions this project's own template layout
    actually uses (a bare basename under templates/, under
    templates/scripts/, or with underscores swapped for the hyphenated
    template directory name), rather than a hand-maintained pair list.
    """
    basename = root_entry.rsplit("/", 1)[-1]
    candidates = (
        f"templates/scripts/{basename}/",
        f"templates/{basename}/",
        f"templates/{basename.replace('_', '-')}/",
    )
    for candidate in candidates:
        if (repo_root / candidate).is_dir():
            return candidate
    return None


def load_build_definition(repo_root: Path | None = None) -> dict[str, str | None]:
    """Real {regenerated_root_prefix: source_root_prefix} mapping.

    Read from this project's own build deploy definition:
    `build_helpers.shim_map` (the build's real in-code list of every
    canonical, regenerated root) when importable, else the `.gitignore`
    "shims underneath" block it also maintains -- never a second,
    hand-maintained root list of this module's own. Either way, each root's
    templates/ source is found by probing this project's actual on-disk
    layout, not a hand-maintained pair list.

    Args:
        repo_root: Repository root to read the definition from. Defaults to
            this module's own repository (three parents up from this file).

    Returns:
        Mapping of regenerated-root prefix (trailing slash) to source-root
        prefix (trailing slash), or None when no source could be determined
        for a root the build does regenerate.
    """
    root = repo_root if repo_root is not None else _REPO_ROOT
    roots = _shim_map_roots(root)
    if roots is None:
        roots = _iter_gitignore_shim_roots(root)
    return {f"{entry}/": _probe_source_prefix(entry, root) for entry in roots}
