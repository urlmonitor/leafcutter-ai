"""
MODULE: unit_tests/workflows/_acd_2100c_support.py
GOAL: Helpers moved verbatim out of two ACD-2100c test modules that sit over the
    check-file-size limit, so each could take the ACD-300c-4 approval-step label
    (`approval-apply`) and its replies without growing.
ARCHITECTURE: Pure helpers, no tests. `_extract_const_array` comes from
    test_acd_2100c_1.py (extracts a top-level JS const array from
    plan-feature.js's source); `_cancel_answer` comes from test_acd_2100c_5.py
    (builds a resume_answer that cancels at a gate, with an optional channel).
"""

from __future__ import annotations


def _extract_const_array(source: str, name: str) -> str:
    """Extract a top-level `const <name> = [ ... ];` by bracket-counting."""
    marker = f"const {name} = ["
    start = source.index(marker)
    open_idx = source.index("[", start)
    depth = 0
    i = open_idx
    while i < len(source):
        ch = source[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(source) and source[end] == ";":
                    end += 1
                return source[start:end]
        i += 1
    raise AssertionError(f"could not extract const array {name}: unbalanced brackets")


def _cancel_answer(gate_id, channel):
    answer = {"gate_id": gate_id, "action": "cancel"}
    if channel is not None:
        answer["channel"] = channel
    return answer
