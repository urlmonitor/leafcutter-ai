"""
MODULE: _declaring_files_derivation
GOAL: Derive, from a deployed guardrail's OWN source (never a hand-typed
    list), the per-guardrail declaring-file inventory AC BP-900h-4 requires —
    one record per (guardrail, declaring file) pair, each carrying
    declaring_file / read_by / expected_at / ownership / derivation. Also
    home to the file-walk orchestration (parse every deployed ``*.py`` file,
    build the cross-module constants map, assemble entries) and the
    presence-check / merge helpers ``check_declaring_files.py`` composes.
BUSINESS CONTEXT: On 2026-08-18 five declaring files were confirmed absent
    from a genuine consumer install while every build test passed, because
    every build test to date installs into leafcutter's own self-hosted
    workspace, where the package source tree sits beside the deployed output
    root and each missing file resolves anyway by accident. This module is
    the mechanical deriver behind ``check_declaring_files.py``'s presence
    check — it walks the DEPLOYED tree's own Python source (AST, not a
    hand-maintained list) looking for the exact resolver shape the 2026-08-18
    and 2026-08-25 regressions share.
ARCHITECTURE: The two AST-recognition scans themselves (file-anchored
    ancestor-walk config literals; local underscore-prefixed helper-module
    imports) live in the sibling module ``_declaring_files_scan`` — see that
    module's own ARCHITECTURE note for the resolver-shape distinctions. This
    module owns everything else: reading and parsing the deployed tree,
    building the cross-module path-constants map, assembling per-file
    entries into the final inventory, and the merge / presence-check helpers
    ``check_declaring_files.py``'s CLI composes directly.
"""

from __future__ import annotations

import ast
from pathlib import Path

from _declaring_files_scan import (
    _CONFIG_PATH_RE,
    _config_declaring_files,
    _extract_path_literal,
    _helper_module_declaring_files,
)

_DERIVATION_CONFIG = "static-scan:file-anchored-ancestor-walk"
_DERIVATION_HELPER = "static-scan:local-helper-import"


def _module_path_constants(tree: ast.Module) -> dict[str, str]:
    """Pure: map module-level ``NAME = <path-literal-expression>`` (or
    ``NAME: TYPE = <...>``) assignments to their resolved string, so a later
    ``ancestor / _SCHEMA_RELATIVE_PATH`` reference inside a qualifying
    function can be resolved back to its value (the ``done_proof.py`` /
    ``_SCHEMA_RELATIVE_PATH`` shape). When the value is a call (the
    ``_get(section, key, default)`` config-accessor shape, e.g.
    ``config.py``'s ``AGENT_REGISTRY_PATH``), falls back to the LAST
    call argument that itself resolves to a config-path literal — the
    accessor's own hardcoded default.
    """
    constants: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        target: ast.expr | None = None
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value_node = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value_node = node.target, node.value

        if not isinstance(target, ast.Name) or value_node is None:
            continue

        resolved = _extract_path_literal(value_node)
        if resolved is None and isinstance(value_node, ast.Call):
            for arg in reversed(value_node.args):
                candidate = _extract_path_literal(arg)
                if candidate is not None and _CONFIG_PATH_RE.match(candidate):
                    resolved = candidate
                    break
        if resolved is not None:
            constants[target.id] = resolved
    return constants


def iter_deployed_python_files(deployed_root: Path) -> list[Path]:
    """Every deployed ``*.py`` file under *deployed_root*, ``__pycache__`` excluded."""
    return sorted(
        p for p in deployed_root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _parse_deployed_files(
    deployed_root: Path,
) -> dict[Path, ast.Module]:
    """Read and parse every deployed ``*.py`` file once, skipping (never
    raising for) any file this process cannot read or parse — one
    unreadable deployed file must not abort the whole derivation.

    Only the parsed tree is retained: every downstream scan operates on the
    AST alone (see ``_declaring_files_scan._is_file_anchored_ancestor_walk``'s
    docstring for why the source text itself is no longer needed).
    """
    parsed: dict[Path, ast.Module] = {}
    for py_file in iter_deployed_python_files(deployed_root):
        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        parsed[py_file] = tree
    return parsed


def _entries_for_file(
    py_file: Path,
    deployed_root: Path,
    tree: ast.Module,
    global_constants: dict[str, str],
) -> list[dict[str, str]]:
    """Pure (given pre-parsed input): this one file's declaring-file entries.

    Materializes *tree*'s node set exactly once (``all_nodes``) and shares it
    across every full-tree scan below (config-literal function scan,
    ``_resolve_root`` import check, helper-module import/dynamic-load scan,
    import-error-guard scan). Those scans previously each called
    ``ast.walk(tree)`` independently — four full re-traversals of the same
    tree per file — which dominated this module's runtime on a real deployed
    tree (~225 files); sharing one materialized walk cuts that to one
    traversal per file (see DECISION HISTORY).
    """
    read_by = py_file.relative_to(deployed_root).as_posix()
    all_nodes = list(ast.walk(tree))
    entries: dict[tuple[str, str], dict[str, str]] = {}
    for declaring_file in _config_declaring_files(tree, all_nodes, global_constants):
        key = (declaring_file, read_by)
        entries[key] = {
            "declaring_file": declaring_file,
            "read_by": read_by,
            "expected_at": declaring_file,
            "ownership": "ours_to_ship",
            "derivation": _DERIVATION_CONFIG,
        }
    for declaring_file in _helper_module_declaring_files(all_nodes, read_by):
        key = (declaring_file, read_by)
        entries[key] = {
            "declaring_file": declaring_file,
            "read_by": read_by,
            "expected_at": declaring_file,
            "ownership": "ours_to_ship",
            "derivation": _DERIVATION_HELPER,
        }
    return list(entries.values())


def derive_inventory(deployed_root: Path) -> list[dict[str, str]]:
    """Derive the full per-guardrail declaring-file inventory from every
    deployed ``*.py`` file under *deployed_root*.

    Two passes: (1) parse every deployed file once and build a
    cross-module map of module-level path constants (so a config-path
    constant defined in one file, e.g. ``config.py``'s
    ``AGENT_REGISTRY_PATH``, resolves when referenced by name from a
    DIFFERENT file that joins it with a file-anchored-resolved root, e.g.
    ``_signoff_parity_checks.py``); (2) derive each file's entries using
    that shared map.
    """
    parsed = _parse_deployed_files(deployed_root)
    global_constants: dict[str, str] = {}
    for tree in parsed.values():
        global_constants.update(_module_path_constants(tree))

    inventory: dict[tuple[str, str], dict[str, str]] = {}
    for py_file, tree in parsed.items():
        for entry in _entries_for_file(py_file, deployed_root, tree, global_constants):
            key = (entry["declaring_file"], entry["read_by"])
            inventory[key] = entry
    return sorted(inventory.values(), key=lambda e: (e["declaring_file"], e["read_by"]))


def merge_inventory(
    base: list[dict[str, str]], extra: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Pure: merge *extra* entries (e.g. from ``--extra-inventory-json``) on
    top of *base*, keyed by (declaring_file, read_by) so an extra entry can
    override a derived one with the same key.
    """
    merged: dict[tuple[str, str], dict[str, str]] = {
        (e["declaring_file"], e["read_by"]): e for e in base
    }
    for entry in extra:
        merged[(entry["declaring_file"], entry["read_by"])] = entry
    return sorted(merged.values(), key=lambda e: (e["declaring_file"], e["read_by"]))


def find_missing(
    deployed_root: Path, inventory: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Every ``ownership: ours_to_ship`` entry whose ``expected_at`` does not
    resolve to a real file strictly under *deployed_root* — resolution is
    always ``deployed_root / expected_at``, never a search of any ancestor,
    the package checkout, or the caller's cwd (AC BP-900h-4's resolution
    rule). An ``external``-owned entry is never checked.
    """
    missing: list[dict[str, str]] = []
    for entry in inventory:
        if entry.get("ownership") != "ours_to_ship":
            continue
        candidate = deployed_root / entry["expected_at"]
        if not candidate.is_file():
            missing.append(entry)
    return missing


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [python-coder/fast-lane BP-900h-4 build set]: Created. Two
#   narrowly-scoped AST scans (file-anchored ancestor-walk config literals;
#   local underscore-prefixed helper-module imports/literals) reproduce the
#   exact resolver shape behind the 2026-08-18 and 2026-08-25 regressions
#   without hand-typing the five known files, and — critically — without
#   pulling in the codebase's OTHER, differently-resolved config readers
#   (check_paths_integrity.py / check_roadmap_schema.py: git-rev-parse
#   based; check_surface_components_e3.py: Path.cwd()-based) which this AC
#   does not concern itself with (doc_type_validators.py's own docstring
#   draws exactly this __file__-vs-cwd distinction). Verified empirically
#   against a real scripts/build.py --target-dir output before wiring into
#   check_declaring_files.py.
# - 2026-09-07 [python-coder/fast-lane BP-900h-4 build set]: Replaced the
#   text-based _is_file_anchored_ancestor_walk (ast.get_source_segment on
#   every function def — re-splits the whole file's source, uncached, on
#   every call) with an AST-structural check, and consolidated the four
#   independent per-file ast.walk(tree) passes (config-literal function
#   scan, _resolve_root import check, helper-module scan, import-error-guard
#   scan) into one materialized walk shared across all four. Measured on a
#   real ~225-file deployed tree: 7.1s -> ~2.1s per single-layout invocation
#   (~3x), needed for BP-900h-4-i's own multi-layout sweep test file to fit
#   inside the fast-lane done_proof gate's fixed 60s pytest subprocess
#   timeout (it invokes the inspector 10+ times across 4 real layouts).
#   Split the AST-recognition scans themselves into the new sibling module
#   _declaring_files_scan.py in the same pass, since the combination pushed
#   this file to 455 lines (over the 400-line check_file_size limit) — see
#   that module's own DECISION HISTORY.
# ====================================================================
