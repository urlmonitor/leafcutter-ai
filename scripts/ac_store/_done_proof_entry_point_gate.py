"""
MODULE: _done_proof_entry_point_gate
GOAL: BO-2900a-1's mechanical entry-point reachability gate -- refuse an
    otherwise-eligible criterion whose covers-tagged proof reached its
    implementing code by direct import instead of through the unit's own
    runtime way in.
BUSINESS CONTEXT: A criterion's covers-tagged test can PASS while never
    once entering the unit's own operator-invocable command surface (a
    module-level ``main(argv)``) -- reaching the implementing function by a
    bare, direct import instead. That proof executes real code and passes,
    so the pre-existing pass/fail gate alone would mark the criterion
    eligible; this gate adds the third condition (BO-2900a-1) that catches
    exactly that gap, MECHANICALLY, with no new keyword argument on
    ``verify_done_eligible``. Distinct from the sibling BO-2900a-1-i opt-in
    gate (``_maybe_reachability_verdict`` in _done_proof_phase_helpers.py),
    which requires an explicit caller-supplied {"target", "entry_point"}
    pair and is never invoked by any real caller today; and distinct from
    the sibling BO-2900a-3 no-way-in-anywhere gate (``_apply_reachability_gate``
    in done_proof.py), which this rule scope-fences away from when no
    linked test's unit defines a ``main`` at all.
ARCHITECTURE: A THIRD sibling extraction out of done_proof.py, alongside
    _done_proof_phase_helpers.py, for the same file-size-ratchet reason
    (done_proof.py was already at its ratcheted content-line length, and
    _done_proof_phase_helpers.py was already close to its own 400-line
    absolute cap -- adding this gate to either file would have pushed it
    over). ``done_proof.verify_done_eligible`` imports
    ``_apply_entry_point_reachability_gate`` from THIS module at top level.

    CIRCULAR-IMPORT NOTE: mirrors _done_proof_phase_helpers.py's own
    documented seam. done_proof.py imports this module's
    ``_apply_entry_point_reachability_gate`` at TOP LEVEL, so this module's
    own need for done_proof.py symbols (``_local_import_module_names``,
    ``_resolve_candidate_unit``, ``_observe_reachability``) is satisfied by
    a LOCAL ``from done_proof import ...`` inside each function body that
    needs one, never at this module's own top level -- a top-level import
    here would deadlock done_proof's own import of this module.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _module_defines_main(module_path: Path) -> bool:
    """True when *module_path* defines a module-level ``main`` function.

    AST-only (never filename, folder, docstring, or an ``if __name__`` text
    match). Fails closed to ``False`` when the file cannot be read or
    parsed -- a candidate this cannot inspect is never treated as exposing
    a way in.

    Args:
        module_path: Path to the ``.py`` file to inspect.

    Returns:
        ``True`` iff a module-level (or async) function literally named
        ``main`` is defined at the top of *module_path*.
    """
    try:
        source = module_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: done_proof: cannot read {module_path}: {exc}", file=sys.stderr)
        return False
    try:
        tree = ast.parse(source, filename=str(module_path))
    except SyntaxError as exc:
        print(f"WARNING: done_proof: cannot parse {module_path}: {exc}", file=sys.stderr)
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
        for node in tree.body
    )


def _detect_module_entry_point(
    test_file: Path, project_root: Path, test_root: Path
) -> tuple[Path, str] | None:
    """Mechanically detect the runtime way in a linked test's unit exposes.

    BO-2900a-1: "the unit exposes a runtime way in" is decided by AST
    inspection -- a module-level function (or async function) literally
    named ``main`` -- never by filename, folder, docstring, or an
    ``if __name__`` text match. Checked in two places, in order:

    1. *test_file* itself -- this AC family's single-file fixture
       convention, where the implementing function, ``main``, and the
       covers-tagged proof test all live in one module.
    2. Each bare module *test_file* imports, resolved the SAME way the
       sibling BO-2900a-3 no-entry-point gate resolves candidate units
       (:func:`done_proof._local_import_module_names` /
       :func:`done_proof._resolve_candidate_unit`) -- the codebase's normal
       separate test/implementation layout (e.g. ``fast_lane.main``,
       scripts/build_orchestration/fast_lane.py:925), the case a same-file
       -only check would never catch.

    Args:
        test_file: Path to the linked test's own source file.
        project_root: Root directory bounding the imported-module search
            (see :func:`done_proof._resolve_candidate_unit`).
        test_root: The project's test tree, excluded from imported-module
            resolution -- a module physically living inside the test tree
            is test-support code, not implementing code.

    Returns:
        ``(module_path, "<module-stem>:main")`` for the first module found
        to define a module-level ``main`` -- *test_file* itself, or the
        first of its imports that resolves to one; ``None`` when neither
        does, handing off to the BO-2900a-3 scope fence rather than risking
        a false refusal.
    """
    if _module_defines_main(test_file):
        return test_file, f"{test_file.stem}:main"

    from done_proof import _local_import_module_names, _resolve_candidate_unit

    for module_name in sorted(_local_import_module_names(test_file)):
        candidate = _resolve_candidate_unit(module_name, test_file, project_root, test_root)
        if candidate is None:
            continue
        if _module_defines_main(candidate):
            return candidate, f"{candidate.stem}:main"
    return None


def _apply_entry_point_reachability_gate(
    verdict: dict, *, py_linked: list[dict], project_root: Path, test_root: Path
) -> dict:
    """Refuse an otherwise-eligible verdict whose proof never entered its own way in.

    Only called when *verdict* is already ``eligible: True`` (all linked
    tests passing). For each Python linked test, mechanically detects
    whether its unit -- the test's own module, or a module it imports --
    defines a runtime way in (see :func:`_detect_module_entry_point`). When
    no linked test's unit defines one, this rule does not fire at all --
    the scope fence to BO-2900a-3 (a genuinely no-way-in unit is judged
    separately, never by this rule).

    When a way in is found, whether it was entered is CONSUMED from the
    execution-derived observation (:func:`done_proof._observe_reachability`
    -- watching the test's own run, never re-derived from source text). A
    test whose own run never entered the detected ``main`` is refused with
    ``refusal_cause: "proof_not_through_entry_point"`` and a reason naming
    "direct import" -- textually distinct from the a-1-i gate's own
    "entered but not reached" reason for the same refusal_cause family. A
    test whose observation could not be made at all, OR whose isolated
    re-execution did not pass (the bare re-run this observation is based on
    bypasses pytest fixtures/conftest/parametrize the original, already
    -passing run used, so an execution failure there is not comparable to
    "did not enter"), fails closed with ``refusal_cause:
    "observation_unavailable"`` rather than being misreported as a direct
    -import refusal.

    Args:
        verdict: The eligibility verdict computed so far (``eligible: True``).
        py_linked: The AC's Python covers-tagged linked test dicts, each
            carrying ``file`` and ``function``.
        project_root: Root directory bounding imported-module resolution.
        test_root: Root directory of the test tree.

    Returns:
        *verdict* unchanged when no linked test's unit defines a runtime
        way in, or every way in found was entered by its own proof test; an
        ``eligible: False`` verdict carrying ``refusal_cause``, ``unit``,
        ``entry_point``, and ``offending_test`` otherwise.
    """
    from done_proof import _observe_reachability

    for test in py_linked:
        test_file = Path(test["file"])
        detected = _detect_module_entry_point(test_file, project_root, test_root)
        if detected is None:
            continue
        module_path, entry_point = detected
        observation = _observe_reachability(test_file, test["function"], "", entry_point)
        offending_test = f"{test_file}::{test['function']}"
        if not observation["observation_ok"] or not observation["passed"]:
            reason = (
                f"reachability observation unavailable for {offending_test}"
                if not observation["observation_ok"]
                else (
                    f"isolated re-execution of {offending_test} did not pass; "
                    f"cannot determine whether it reached {entry_point}"
                )
            )
            return {
                **verdict,
                "eligible": False,
                "reason": reason,
                "refusal_cause": "observation_unavailable",
                "unit": module_path.stem,
                "entry_point": entry_point,
                "offending_test": offending_test,
            }
        if not observation["entered_entry_point"]:
            return {
                **verdict,
                "eligible": False,
                "reason": (
                    f"the proof for {offending_test} reached the code by "
                    f"direct import instead of through {entry_point}"
                ),
                "refusal_cause": "proof_not_through_entry_point",
                "unit": module_path.stem,
                "entry_point": entry_point,
                "offending_test": offending_test,
            }
    return verdict


# DECISION HISTORY
# ================================================================================
# - 2026-09-25 [python-coder/BO-2900a-1]: Created this sibling module (a
#   THIRD extraction out of done_proof.py, alongside _done_proof_phase_helpers.py)
#   for _module_defines_main, _detect_module_entry_point, and
#   _apply_entry_point_reachability_gate -- the mechanical, auto-detected
#   entry-point gate the 2026-09-07 reachability_spec addendum in
#   done_proof.py explicitly scoped out. First attempt placed these in
#   _done_proof_phase_helpers.py, but that pushed the sibling file's own
#   content length (425) over its 400-line absolute cap (its own HEAD length,
#   325, was under the cap, so the growth-while-oversized ratchet did not
#   apply -- the absolute limit did). A dedicated new module keeps both
#   existing files at their prior lengths. Added to build_ac_store's
#   deploy_map in scripts/build_phases_ac_store.py in the same change, so
#   the deployed check_done_proof hook (which imports done_proof, which
#   imports this module) does not crash with ModuleNotFoundError. (#BO-2900a-1)
# ================================================================================
