"""
MODULE: test_tq500g5_reference_drift
GOAL: Keep docs/reference/wrong-version-runs.md and consumer-test-sweep.md in step
    with the code: every result word, stop value, sweep reason and loosened/weakened
    "what" string the code can emit must appear on those pages, and their relative
    links must resolve.
BUSINESS CONTEXT: TQ-500g-5. The vocabularies are read FROM THE CODE (module
    constants, or string constants found by ast where the code has no constant), so
    a new word added to the code and not documented turns this red.
AC: TQ-500g-5
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts" / "build_orchestration"
REF = ROOT / "docs" / "reference"
RUNS_PAGE = REF / "wrong-version-runs.md"
SWEEP_PAGE = REF / "consumer-test-sweep.md"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _cs_guards  # noqa: E402
import _cs_runs  # noqa: E402
import _wvr_verdict  # noqa: E402


def _tree(name: str) -> ast.Module:
    return ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))


def _func(tree: ast.Module, name: str) -> ast.AST:
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _strs(node: ast.AST) -> set[str]:
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def result_words() -> set[str]:
    """Every result word: the verdict module's sets, read_one's returns, the runner's row() calls."""
    words = set(_wvr_verdict.NON_BLOCKING) | set(_wvr_verdict.UNFINISHED)
    for node in ast.walk(_func(_tree("_wvr_verdict.py"), "read_one")):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            first = node.value.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                words.add(first.value)
    for fname in ("wrong_version_runner.py", "_wvr_scope.py"):
        for node in ast.walk(_tree(fname)):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "row" and len(node.args) >= 3:
                arg = node.args[2]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    words.add(arg.value)
    return words


def stop_values() -> set[str]:
    """The ``stopped_at`` values: string second arguments of the gate's ``_shape`` calls."""
    stops = set()
    for node in ast.walk(_tree("wrong_version_gate.py")):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_shape" and len(node.args) > 1:
            arg = node.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                stops.add(arg.value)
    return stops


def sweep_reasons() -> set[str]:
    """The sweep's ``reason`` values: strings assigned to ``reason`` in consumer_sweep.py."""
    reasons = set()
    for node in ast.walk(_tree("consumer_sweep.py")):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "reason" for t in node.targets):
            reasons |= _strs(node.value)
        if isinstance(node, ast.keyword) and node.arg == "reason" and isinstance(node.value, ast.Constant):
            reasons.add(node.value.value)
    reasons.discard("")
    return reasons


def what_strings() -> set[str]:
    """The ``what`` strings of loosened items and weakened/removed items."""
    found = set(_cs_guards._WHAT.values()) | set(_cs_runs._WHAT.values())
    for node in ast.walk(_tree("_cs_runs.py")):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "what" for t in node.targets):
            found |= _strs(node.value)
    for node in ast.walk(_func(_tree("_cs_asserts.py"), "_items_for")):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.add(first.value)
    return found


def missing_words(words, text: str) -> list[str]:
    """The words that do not occur in *text*, sorted."""
    return sorted(w for w in words if w not in text)


def broken_links(page: Path) -> list[str]:
    """Relative markdown links on *page* whose target file does not exist."""
    bad = []
    for target in re.findall(r"\]\(([^)\s]+)\)", page.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        if not (page.parent / target.split("#", 1)[0]).exists():
            bad.append(target)
    return bad


def _both() -> str:
    return RUNS_PAGE.read_text(encoding="utf-8") + SWEEP_PAGE.read_text(encoding="utf-8")


def test_ac_tq500g5_vocabularies_are_nonempty_and_known():
    # covers: TQ-500g-5
    # angle: boundary
    # Guards against the extraction silently finding nothing (a vacuous pass).
    words = result_words()
    assert {"caught", "survived", "did_not_load", "not_applied", "invalid", "not_run",
            "not_in_scope", "not_applicable"} <= words
    assert stop_values() == {"sweep", "write"}
    assert {"unlisted", "weakened", "loosened", "inconclusive"} <= sweep_reasons()
    assert len(what_strings()) >= 6


def test_ac_tq500g5_result_words_documented_on_runs_page():
    # covers: TQ-500g-5
    # angle: criterion
    assert missing_words(result_words(), RUNS_PAGE.read_text(encoding="utf-8")) == []


def test_ac_tq500g5_stop_values_documented_on_runs_page():
    # covers: TQ-500g-5
    # angle: criterion
    text = RUNS_PAGE.read_text(encoding="utf-8")
    assert missing_words({f'"{s}"' if f'"{s}"' in text else f"`{s}`" for s in stop_values()}, text) == []


def test_ac_tq500g5_sweep_reasons_and_what_strings_documented():
    # covers: TQ-500g-5
    # angle: criterion
    text = _both()
    assert missing_words(sweep_reasons(), text) == []
    assert missing_words(what_strings(), SWEEP_PAGE.read_text(encoding="utf-8")) == []


def test_ac_tq500g5_relative_links_resolve():
    # covers: TQ-500g-5
    # angle: failure
    assert broken_links(RUNS_PAGE) == []
    assert broken_links(SWEEP_PAGE) == []


def test_ac_tq500g5_removing_a_word_is_detected():
    # covers: TQ-500g-5
    # angle: discrimination
    # Catches: a missing_words that always returns [] (the drift tests would never go red).
    text = RUNS_PAGE.read_text(encoding="utf-8")
    assert missing_words(result_words(), text) == []
    assert missing_words(result_words(), text.replace("did_not_load", "")) == ["did_not_load"]
