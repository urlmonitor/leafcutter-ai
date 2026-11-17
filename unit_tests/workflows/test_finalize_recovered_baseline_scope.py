"""FIN-100c-15: recoveredBaselineFailures is scoped to the recovery block.

The declaration must live inside the `if (baselineFailures === null &&
postMergeFailures.length > 0) { ... }` block, with no wider-scope declaration.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows.test_finalize_baseline_recovery import (  # noqa: E402
    _HARNESS_TIMEOUT,
    _base_label_responses,
    _extract_baseline_failures,
    _find_triage_call,
)

_JS_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "workflows-js" / "finalize-feature.js"
_OPENER = re.compile(r"if\s*\(\s*baselineFailures\s*===\s*null\s*&&\s*postMergeFailures\.length\s*>\s*0\s*\)\s*\{")
_DECL = re.compile(r"\b(?:let|const|var)\s+recoveredBaselineFailures\b")


def _src() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    """Blank out // comments so comment text cannot satisfy or defeat matches."""
    return re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), src)


def _block_span(src: str) -> tuple[int, int]:
    m = _OPENER.search(src)
    assert m, "recovery block opener `if (baselineFailures === null && postMergeFailures.length > 0) {` not found"
    depth, i = 1, m.end()
    while i < len(src) and depth:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    return m.end(), i


def test_recoveredbaselinefailures_declared_inside_recovery_block():
    # covers: FIN-100c-15
    # angle: criterion
    src = _code_only(_src())
    start, end = _block_span(src)
    decls = [m.start() for m in _DECL.finditer(src)]
    assert len(decls) == 1, f"expected exactly one declaration, found {len(decls)}"
    assert start <= decls[0] < end, "recoveredBaselineFailures must be declared inside the recovery block"


def test_no_vestigial_wider_scope_declaration_remains():
    # covers: FIN-100c-15
    # angle: discrimination
    # Wrong version: adding an inner declaration while leaving the outer one.
    src = _code_only(_src())
    start, end = _block_span(src)
    outside = [m.start() for m in _DECL.finditer(src) if not (start <= m.start() < end)]
    assert outside == [], "vestigial declaration of recoveredBaselineFailures outside the recovery block"
    outside_uses = [m.start() for m in re.finditer(r"\brecoveredBaselineFailures\b", src)
                    if not (start <= m.start() < end)]
    assert outside_uses == [], "recoveredBaselineFailures referenced outside the recovery block"


def test_recovery_behavior_unchanged_after_scope_narrowing():
    # covers: FIN-100c-15
    # angle: reachability
    recovered = ["tests/bar.py::test_two", "tests/baz.py::test_three"]
    ok = run_workflow_under_e2(
        _JS_PATH,
        label_responses=_base_label_responses(
            targeted_rerun_response={"status": "ok", "recovered_failures": recovered}),
        timeout=_HARNESS_TIMEOUT,
    )
    call = _find_triage_call(ok)
    assert call is not None
    val, err = _extract_baseline_failures(call)
    assert err is None and val == recovered
    bad = run_workflow_under_e2(
        _JS_PATH,
        label_responses=_base_label_responses(
            targeted_rerun_response={"status": "checkout_failed", "recovered_failures": None}),
        timeout=_HARNESS_TIMEOUT,
    )
    call = _find_triage_call(bad)
    assert call is not None
    val, err = _extract_baseline_failures(call)
    assert err is None and val is None
