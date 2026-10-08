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


def _report_only(
    reason: str, refusal_cause: str, module_path: Path, entry_point: str
) -> None:
    """Announce a reachability finding WITHOUT refusing the verdict.

    The rule is report-only pending its own repair; see the DECISION HISTORY entry
    of 2026-09-30 for why, and for the conditions under which it is re-armed. Every
    finding is still printed in full so the population stays countable and a later
    sweep can measure whether re-arming would be safe.

    Args:
        reason: Operator-facing sentence, identical to the refusal text it replaces.
        refusal_cause: The cause this WOULD have refused with.
        module_path: The unit the finding is about.
        entry_point: The ``<module>:main`` spec that was or was not entered.
    """
    print(
        f"[check-done-proof] REPORT-ONLY reachability finding "
        f"({refusal_cause}, unit {module_path.stem}, entry point {entry_point}): "
        f"{reason}. This does NOT block; the rule is suspended pending repair of its "
        f"own observer, which cannot see a proof that drives the unit as a subprocess.",
        file=sys.stderr,
    )


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
        *verdict*, ALWAYS unchanged. This rule is REPORT-ONLY as of 2026-09-30:
        every finding it would have refused on is printed by :func:`_report_only`
        and the verdict is passed through untouched. It cannot currently fail an
        AC. See the DECISION HISTORY entry for the defect that suspended it and
        the conditions for re-arming.
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
            _report_only(reason, "observation_unavailable", module_path, entry_point)
            continue
        if not observation["entered_entry_point"]:
            _report_only(
                f"the proof for {offending_test} reached the code by "
                f"direct import instead of through {entry_point}",
                "proof_not_through_entry_point",
                module_path,
                entry_point,
            )
            continue
    return verdict


# DECISION HISTORY
# ================================================================================
# - 2026-09-30 [BrainCandy]: SUSPENDED TO REPORT-ONLY. Both refusal paths now
#   print and continue instead of returning eligible: False. Three measured
#   reasons, any one of which is sufficient:
#     1. It accepts the ritual it exists to refuse. The gate passes target_spec=""
#        to _observe_reachability, so reached_through is structurally always False
#        and the predicate degenerates to entered_entry_point. A proof that calls
#        main(["noop"]) and then calls the function directly is ACCEPTED; an
#        ordinary direct-import proof is REFUSED. Verified by execution.
#     2. It cannot see the proof shape this repository mandates. _gtfa_constants
#        _REACHABILITY_ASSERTS instructs authors to "invoke the production entry
#        point ... as a subprocess/dispatch" and NOT to import directly; 164 ticket
#        files carry that instruction. sys.setprofile observes only the runner's own
#        process, so a subprocess proof is invisible: a pure spawn resolves no entry
#        point and passes silently, a hybrid spawn is refused outright.
#     3. It names the wrong unit. _detect_module_entry_point picks the
#        alphabetically first import defining a main, with no tie to the AC's
#        implemented_by; 29 of 54 in-scope ACs that declare a file are judged
#        against a different one. KM-KGS-100e-1 (implemented_by _ac_components.py)
#        is refused naming backfill_components:main.
#   Suspension, not removal: findings are still printed in full so the population
#   remains countable. Re-arm only when the observer follows the process tree
#   (BO-2900a-2, still todo, specifies hosting it in the existing pytest run rather
#   than a second bespoke runner) and the unit is resolved from the AC rather than
#   from the proof's import list. Analysis:
#   docs/analysis/2026-09-29-the-entry-point-gate-refuses-the-proof-it-wants-and-
#   accepts-the-one-it-does-not-3-scoping-recommendation.md
# ================================================================================
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
