"""
MODULE: _done_proof_reachability_gate
GOAL: The BO-2900d-1 / BO-2900a-3 reachability gate -- refuse an otherwise
    eligible done verdict when a linked test proves a unit only by importing
    it directly and nothing else can reach that unit.
BUSINESS CONTEXT: ``_apply_reachability_gate`` establishes conditions (1) and
    (2) of the ``no_entry_point_reaches_code`` refusal (the unit defines no
    ``main()`` of its own, and no other project file imports it) from the
    functions in this module, then delegates condition (3) to
    ``_done_proof_automation_gate`` and the BO-2900d-1 exemption seam.
ARCHITECTURE: A fifth sibling extraction out of done_proof.py, alongside
    _done_proof_phase_helpers.py, _done_proof_composite.py,
    _done_proof_entry_point_gate.py and _done_proof_automation_gate.py, for
    the same file-size-ratchet reason. Moved verbatim, no behaviour change;
    every name is re-exported from done_proof.py so existing imports keep
    working. Follows the sibling convention for the circular import:
    done_proof.py imports this module at TOP LEVEL, so this module's need
    for ``done_proof._is_excluded_path`` is satisfied by a LOCAL
    ``from done_proof import ...`` inside each function that needs it.
    Added to build_ac_store's deploy_map in scripts/build_phases_ac_store.py
    so the deployed check_done_proof hook does not crash with
    ModuleNotFoundError.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

from _done_proof_automation_gate import (  # BO-2900a-3 rework
    build_no_entry_point_refusal,
    unit_is_invoked_by_automation,
)

# BO-2900d-1: shared reachability-exemption seam directory.
#
# _reachability_inventory.py lives beside check_done_proof.py under the
# sibling commit_guardian/ directory in BOTH layouts this module runs in:
#     <repo>/scripts/ac_store/<this file>           -> ../commit_guardian
#     <repo>/.leafcutter/scripts/ac_store/<this file> -> ../commit_guardian
# The import itself is guarded by try/except ImportError directly at its call
# site inside _apply_reachability_gate() below (the codebase's own
# optional-dependency idiom) rather than behind an unguarded helper function:
# BP-900h-4's declaring-files scan treats a bare import of a leading-underscore
# name as declaring a sibling file the importing script "cannot run without"
# UNLESS the import itself sits inside a try/except ImportError. Guarding at
# the true import site also degrades to "no exemptions" (fail-open per the
# error-handling policy: an unreadable/absent exemption mechanism must never
# itself grant a pass, and must never crash the eligibility oracle).
_COMMIT_GUARDIAN_DIR = Path(__file__).resolve().parent.parent / "commit_guardian"

# Matches a module's own runtime entry-point guard.
_MAIN_GUARD_RE = re.compile(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:')


def _local_import_module_names(test_file: Path) -> set[str]:
    """Return bare (non-dotted) module names imported at the top of *test_file*.

    Uses :mod:`ast` (never a text-match of import statements) so a bare
    ``import foo`` or ``from foo import bar`` is recognised regardless of
    formatting.  Dotted imports (``import pkg.sub``, third-party or stdlib
    packages) are excluded — this gate only reasons about single-file
    project-local modules reached the same way the fixture units in
    BO-2900d-1's own test_spec are: a flat ``sys.path.insert`` plus a bare
    module import.

    Args:
        test_file: Path to the covers-tagged test file to scan.

    Returns:
        Set of bare module name strings.  Empty when the file cannot be
        read or does not parse as Python.
    """
    try:
        text = test_file.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "." not in alias.name:
                    names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0 and "." not in node.module:
                names.add(node.module)
    return names


def _is_within(path: Path, root: Path) -> bool:
    """True when *path* is *root* itself or lives under it."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


_SYS_PATH_INSERT_RE = re.compile(
    r"""sys\.path\.insert\(\s*0\s*,\s*['"]([^'"]+)['"]\s*\)"""
)


def _sys_path_insert_dirs(test_file: Path) -> list[Path]:
    """Return directories the test file inserts onto ``sys.path`` via a literal.

    Matches ``sys.path.insert(0, "<literal path>")`` (the exact form the
    fixture units in BO-2900d-1's test_spec use to make a bare import
    resolve). Only literal string arguments are recognised — this is a
    static hint, not an execution of the test file.

    Args:
        test_file: Path to the covers-tagged test file to scan.

    Returns:
        List of existing directory Paths, in the order they appear in the
        file (mirroring Python's own sys.path search order). Empty when the
        file cannot be read or inserts no literal directory.
    """
    try:
        text = test_file.read_text(encoding="utf-8")
    except OSError:
        return []
    dirs: list[Path] = []
    for match in _SYS_PATH_INSERT_RE.finditer(text):
        candidate = Path(match.group(1))
        if candidate.is_dir():
            dirs.append(candidate)
    return dirs


def _resolve_candidate_unit(
    module_name: str, test_file: Path, project_root: Path, test_root: Path
) -> Path | None:
    """Find the ``.py`` file *module_name* resolves to when imported by *test_file*.

    A bare module name can exist at more than one path in a project (two
    unrelated units both named ``helpers.py`` is entirely legal Python). A
    project-wide search that just picks "the first file with this name" is
    ambiguous exactly there, and would silently attribute one test's import
    to a different, same-named unit elsewhere in the tree. Resolution
    therefore mirrors how the import actually resolves at runtime: prefer a
    directory the test itself inserted onto ``sys.path`` (see
    :func:`_sys_path_insert_dirs`) — the same directories Python's own
    import machinery would search first for that test. Only when the test
    inserts no such directory does this fall back to a project-wide search,
    accepting the ambiguity as a best-effort default for tests that resolve
    their import some other way (e.g. an installed/editable package).

    Args:
        module_name: Bare module name imported by *test_file*.
        test_file: The covers-tagged test file doing the importing.
        project_root: Root directory to search recursively (fallback only).
        test_root: Excluded from the search — a module physically living
            inside the test tree is test-support code, not implementing code.

    Returns:
        The resolved path, or ``None`` when no matching file exists.
    """
    from done_proof import _is_excluded_path

    for sys_path_dir in _sys_path_insert_dirs(test_file):
        candidate = sys_path_dir / f"{module_name}.py"
        if candidate.is_file() and not _is_excluded_path(candidate):
            return candidate

    try:
        matches = sorted(project_root.rglob(f"{module_name}.py"))
    except OSError:
        return None
    for candidate in matches:
        if _is_excluded_path(candidate):
            continue
        if _is_within(candidate, test_root):
            continue
        return candidate
    return None


def _has_entry_point_of_its_own(module_path: Path) -> bool:
    """True when *module_path* defines its own ``if __name__ == "__main__":`` guard."""
    try:
        text = module_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(_MAIN_GUARD_RE.search(text))


def _is_imported_elsewhere(
    module_name: str, module_path: Path, project_root: Path, test_root: Path
) -> bool:
    """True when some OTHER project file (outside test_root) genuinely imports
    *module_name*.

    Per the BO-2900a-3 constraint, this is established from the import graph
    built by AST-parsing each candidate file — via the same
    :func:`_local_import_module_names` seam used to inspect a linked test's
    own imports — never from a text scan of import statements. A regex
    search for the literal words ``import <name>`` would also match a
    docstring, comment, or log string that merely mentions the import
    spelling without containing a real ``ast.Import``/``ast.ImportFrom``
    node; parsing the syntax tree cannot be fooled that way. A test
    importing the unit does not count (excluded via *test_root*) — that is
    exactly the case this gate exists to catch.

    Args:
        module_name: The bare module name to search for.
        module_path: The candidate unit's own path (excluded from the search).
        project_root: Root directory to search recursively.
        test_root: Excluded from the search.

    Returns:
        ``True`` iff some other project file's parsed AST contains a real
        import of the module by name.
    """
    from done_proof import _is_excluded_path

    try:
        candidates = project_root.rglob("*.py")
    except OSError:
        return False
    for candidate in candidates:
        if _is_excluded_path(candidate):
            continue
        if candidate == module_path or _is_within(candidate, test_root):
            continue
        if module_name in _local_import_module_names(candidate):
            return True
    return False


def _infer_project_root(ac_root: Path, test_root: Path) -> Path:
    """Return the common ancestor of *ac_root* and *test_root*.

    Both are conventionally rooted at the same project, so their common
    ancestor bounds the reachability scan to that project rather than the
    whole filesystem. Falls back to *test_root* on the rare filesystem where
    the two share no common path (e.g. different drives on Windows).
    """
    try:
        return Path(
            os.path.commonpath([str(ac_root.resolve()), str(test_root.resolve())])
        )
    except ValueError:
        return test_root.resolve()


def _find_no_entry_point_unit(
    linked_tests: list[dict], project_root: Path, test_root: Path
) -> str | None:
    """Return the repo-relative path of a linked test's unit with no way in.

    For each Python linked test, inspects the bare module names it imports
    directly. A candidate unit "has no way in" when BOTH hold: it defines no
    ``if __name__ == "__main__":`` of its own, AND no other project file
    (outside the test tree) imports it. Only Python linked tests are
    inspected — this gate does not extend to the TypeScript/JS path.

    Args:
        linked_tests: Covers-tagged test dicts for the AC being evaluated.
        project_root: Root directory bounding the reachability scan.
        test_root: The project's test tree, excluded from candidate
            resolution and from the "imported elsewhere" search.

    Returns:
        The first no-way-in unit's path, relative to *project_root* when
        possible (absolute otherwise); ``None`` when every resolvable
        candidate has a way in.
    """
    for test in linked_tests:
        test_file = Path(test["file"])
        if test_file.suffix != ".py":
            continue
        for module_name in sorted(_local_import_module_names(test_file)):
            candidate = _resolve_candidate_unit(
                module_name, test_file, project_root, test_root
            )
            if candidate is None:
                continue
            if _has_entry_point_of_its_own(candidate):
                continue
            if _is_imported_elsewhere(module_name, candidate, project_root, test_root):
                continue
            try:
                return str(candidate.relative_to(project_root))
            except ValueError:
                return str(candidate)
    return None


def _apply_reachability_gate(
    verdict: dict, *, ac_id: str, linked_tests: list[dict], ac_root: Path, test_root: Path
) -> dict:
    """Apply the BO-2900d-1 reachability gate to an otherwise-eligible verdict.

    Intended to run only when *verdict* is already ``eligible: True`` (leaf
    path, all linked tests passing) — an EARLIER gate in the same
    composition (BO-2900a-1's ``_apply_entry_point_reachability_gate``) may
    already have refused the verdict for its OWN, distinct
    ``refusal_cause`` before this function ever runs. This function must
    not overwrite that refusal with its own, different "no way in" verdict
    for the same unit (BO-2900e-1 requires two disjoint refusal_cause
    values, never one merged verdict), so an already-ineligible *verdict*
    is returned unchanged, restoring this function's documented
    precondition mechanically rather than by convention alone. When
    *verdict* is eligible, finds the first linked unit whose module defines
    no ``main()`` of its own AND is not genuinely imported elsewhere (see
    :func:`_find_no_entry_point_unit` -- conditions (1) and (2)); when none
    exists, returns *verdict* unchanged. When one exists, condition (3) is
    checked next: :func:`_done_proof_automation_gate.unit_is_invoked_by_automation`
    answers "does some real automation script run this unit as a program?"
    against the shared BO-2900b-1/BO-2900b-3 ``collected_invocations()``
    seam; a unit that IS run as a program by automation does not satisfy
    this condition, so the refusal does not fire at all and *verdict* is
    returned unchanged. Only when all three conditions hold does this
    function check the shared reachability-exemption seam (BO-2900d-1): a
    recorded, reasoned exemption for that exact unit releases the refusal
    and is announced on the returned verdict (never silently absorbed); the
    absence of one refuses the criterion with ``refusal_cause:
    "no_entry_point_reaches_code"`` and ``clearing_actions`` naming the two
    ways the verdict flips (see
    :func:`_done_proof_automation_gate.build_no_entry_point_refusal`).

    Args:
        verdict: The eligibility verdict computed so far. May already be
            ``eligible: False`` (an earlier gate's refusal, passed through
            unchanged) or ``eligible: True`` (the case this gate evaluates).
        ac_id: The AC identifier being evaluated (for the refusal message).
        linked_tests: The AC's Python covers-tagged linked tests.
        ac_root: Root directory of the AC YAML store.
        test_root: Root directory of the test tree.

    Returns:
        *verdict* unchanged when it arrived already ineligible, when no
        no-way-in unit is found, when the unit IS run as a program by real
        automation (condition (3) fails), or when the unit is exempted
        (with exemption details attached); an ``eligible: False`` verdict
        carrying ``refusal_cause``, ``unit``, and ``clearing_actions``
        otherwise.
    """
    if not verdict.get("eligible"):
        return verdict
    project_root = _infer_project_root(ac_root, test_root)
    unit = _find_no_entry_point_unit(linked_tests, project_root, test_root)
    if unit is None:
        return verdict

    exemptions: list[dict] = []
    exempt_verdict = False
    invocation_collector = None
    if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
        sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
    try:
        from _reachability_inventory import (
            ReachabilityRegistryError,
            collected_invocations,
            is_exempt,
            load_exemptions,
        )
    except ImportError as exc:
        print(
            f"WARNING: done_proof: reachability-exemption seam unavailable, "
            f"treating {unit} as unexempted: {exc}", file=sys.stderr,
        )
    else:
        registry_path = project_root / "config" / "reachability_exemptions.yaml"
        try:
            exemptions = load_exemptions(registry_path)
        except ReachabilityRegistryError as exc:
            print(
                f"WARNING: done_proof: cannot load {registry_path}: {exc}", file=sys.stderr,
            )
        exempt_verdict, invocation_collector = is_exempt(unit, exemptions), collected_invocations

    # BO-2900a-3 condition (3): a unit run as a program by real automation
    # does not satisfy "no automation runs it" -- verdict unchanged.
    if unit_is_invoked_by_automation(unit, project_root, test_root, invocation_collector):
        return verdict

    if exempt_verdict:
        matched_reason = next(
            (e.get("reason") for e in exemptions if e.get("item") == unit), ""
        )
        exempted = dict(verdict)
        exempted["exemption"] = {"item": unit, "reason": matched_reason}
        return exempted

    return build_no_entry_point_refusal(verdict, ac_id=ac_id, unit=unit)
