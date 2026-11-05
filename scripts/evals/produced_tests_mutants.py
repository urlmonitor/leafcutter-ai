"""
MODULE: scripts/evals/produced_tests_mutants.py
GOAL: The run-based assertion kinds of the produced-tests mode: a produced test is judged by
    RUNNING it against altered copies of the code under test, never by how its source reads.
BUSINESS CONTEXT: TQ-200d-1 (review fix H-2..H-5). A static check of a test's source is gameable:
    a constant, an unused literal or ``assert True`` all satisfy it. The only honest verdict on "this
    test would catch the wrong version" is that the test FAILS when the wrong version is in place and
    PASSES on the fixed code. A regression test of existing code is judged the same way: it must
    reach the existing function and fail on its wrong result, which an instrumented copy records.
ARCHITECTURE: Sibling of produced_tests_scoring.py (registry) and produced_tests_runs.py
    (sandbox, pytest). ``module_swapped`` puts a variant of a module in the sandbox and restores
    the original bytes in finally. ``fails_on_mutants`` runs the test on the fixed code, then on each
    mutant copy the row names (``mutants`` in the spec, held back from the agent). ``fails_on_wrong_result``
    runs test B against a copy of the target module whose function appends the running test's id to
    a marker file once it has returned. An assertion is {"passed", "detail"}.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import produced_tests_runs as runs
from produced_tests_runs import RowContext

ABSENCE_RE = re.compile(r"ImportError|ModuleNotFoundError|NameError|cannot import name|No module named|has no attribute")
ASSERTION_RE = re.compile(r"^E\s+(?:assert\b|AssertionError)", re.MULTILINE)
CALLS_ENV = "EVAL_TARGET_CALLS"
FAILING = ("failure", "error")
INSTRUMENT = r'''

import os as _eval_os

_eval_original = {target}


def {target}(*args, **kwargs):
    result = _eval_original(*args, **kwargs)
    with open(_eval_os.environ["{env}"], "a", encoding="utf-8") as _eval_handle:
        _eval_handle.write(_eval_os.environ.get("PYTEST_CURRENT_TEST", "") + "\n")
    return result
'''


@contextmanager
def module_swapped(ctx: RowContext, module: str, source: str) -> Iterator[None]:
    """Put *source* in the sandbox as *module* and restore the original bytes afterwards, even on error."""
    target = ctx.sandbox / module
    original = target.read_bytes()
    try:
        target.write_text(source, encoding="utf-8", newline="\n")
        yield
    finally:
        target.write_bytes(original)


def _names(ctx: RowContext, spec: dict) -> list[str]:
    """The produced test files a spec runs: the ones it names, else every one in the output."""
    return list(spec.get("files") or sorted(ctx.test_files))


def fails_on_mutants(ctx: RowContext, spec: dict) -> dict:
    """The produced test passes on the fixed code and FAILS against every mutant of the module (runs, H-2..H-4)."""
    module, names = spec["module"], _names(ctx, spec)
    fixed = runs.run_pytest(ctx, names)
    if not runs.all_green(fixed):
        return {"passed": False, "detail": f"the produced test does not pass on the fixed code, so it proves nothing about a mutant: {runs.first_problem(fixed)}"}
    survivors = []
    for rel in spec["mutants"]:
        with module_swapped(ctx, module, (ctx.fixture_dir / rel).read_text(encoding="utf-8")):
            outcome = runs.run_pytest(ctx, names)
        if not any(c["status"] in FAILING for c in outcome["cases"]):
            survivors.append(Path(rel).stem)
    if survivors:
        return {"passed": False, "detail": f"the produced test still passes against the mutant(s) {survivors} of {module}, so it would let that wrong version through"}
    return {"passed": True, "detail": f"passes on the fixed code and fails against all {len(spec['mutants'])} mutant(s) of {module}"}


def produced_test_green(ctx: RowContext, spec: dict) -> dict:
    """The produced test runs and passes on the fixture project as it stands (a skip or xfail is not a pass)."""
    outcome = runs.run_pytest(ctx, _names(ctx, spec))
    if not runs.all_green(outcome):
        return {"passed": False, "detail": f"the produced test does not pass on the fixture: {runs.first_problem(outcome)}"}
    return {"passed": True, "detail": f"{len(outcome['cases'])} produced test(s) pass on the fixture"}


def _reached(lines: list[str], case: str) -> bool:
    """True when the instrumented function returned during the running case (pytest's current-test id)."""
    return any(f"::{case} (" in line for line in lines)


def fails_on_wrong_result(ctx: RowContext, spec: dict) -> dict:
    """Test B is red by reaching the existing code and failing an assertion on its result, never before it (TQ-500f-3, H-5)."""
    name, target = spec["file"], spec["target"]
    module = spec.get("module", f"{target}.py")
    if name not in ctx.test_files:
        return {"passed": False, "detail": f"the output holds no test file {name!r}"}
    marker = ctx.work_dir / "target_calls.txt"
    marker.unlink(missing_ok=True)
    instrumented = (ctx.sandbox / module).read_text(encoding="utf-8") + INSTRUMENT.format(target=target, env=CALLS_ENV)
    with module_swapped(ctx, module, instrumented):
        outcome = runs.run_pytest(ctx, [name], {CALLS_ENV: str(marker)})
    lines = marker.read_text(encoding="utf-8").splitlines() if marker.is_file() else []
    failing = [c for c in outcome["cases"] if c["status"] in FAILING]
    if not outcome["cases"]:
        return {"passed": False, "detail": f"{name} collected no test ({outcome['output'].strip()[-120:]})"}
    if not failing:
        return {"passed": False, "detail": f"{name} passes or is skipped on today's code, so it shows no wrong result from {target}()"}
    absent = [c for c in failing if c["status"] == "error" or ABSENCE_RE.search(c["text"])]
    if absent:
        first = absent[0]["text"].strip().splitlines()[-1][:160] if absent[0]["text"].strip() else "collection error"
        return {"passed": False, "detail": f"{name} fails only at import or on a missing name (absence), never on {target}()'s result: {first}"}
    good = [c for c in failing if _reached(lines, c["name"]) and ASSERTION_RE.search(c["text"])]
    if not good:
        return {"passed": False, "detail": f"{name} fails, but not on an assertion made after {target}() returned (it failed before the call, via pytest.fail, or on an error of its own)"}
    return {"passed": True, "detail": f"{name} reaches {target}() and fails on a wrong result: {good[0]['text'].strip().splitlines()[0][:120]}"}
