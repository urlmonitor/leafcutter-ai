"""
MODULE: unit_tests/ac_store/test_acd_2500c_1_i_review.py
COVERS: ACD-2500c-1-i
GOAL: Red-first pins for two G4 review findings against the "test design grounding" family
    (scripts/ac_store/_rc_design_grounding.py), driven through the real requirement_rule_check
    CLI like test_acd_2500c_1_i.py (helpers imported from it):
    M-2: a record with test_intent AND a markless test_spec is invalid, not legacy (ADR-071: a
        legacy record never carries test_intent): one `needs a decision` finding, kind
        "unmarked-design". A true legacy record (no test_intent) stays not evaluated.
    L-6 (user decision 2026-10-14, "the design lists every test"): a marked design with no entry of
        angle `reachability` gets one finding, kind "no-reachability".
PINNED SCOPE RULE (L-6): a marked record with a test_spec is judged unless `test_required` is false
    or `change_target` is present and names no "code" (a string other than "code", or a list without
    "code"). An absent change_target is judged (code is the default).
RED STATE: the family currently returns [] for the markless record and never looks at angles (an
    ASSERTION red for both).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_acd_2500c_1_i import (  # noqa: E402
    build, design, entry, family, good_entries, one_finding, run,
)


def _no_reachability():
    return [entry(e["name"], e["proves_clause"], e["code_file"], e["to_be_created"], angle="criterion")
            for e in good_entries()]


def test_markless_design_with_test_intent_is_unmarked_design(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: failure
    """M-2: test_intent plus a test_spec with no authorship mark yields exactly one `needs a decision`
    finding of kind unmarked-design naming the record (it used to be skipped as legacy). Controls in the
    same store: a true legacy record (no test_intent) yields nothing, a marked design yields nothing."""
    invalid = design("ZZG-101", marked=False)
    legacy = design("ZZG-102", marked=False)
    del legacy["test_intent"]
    store = build(tmp_path, design("ZZG-100"), invalid, legacy)

    code, report = run(store)

    one_finding(report, "ZZG-101", "unmarked-design")
    assert family(report, "ZZG-102") == [], "a true legacy record stays not evaluated"
    assert family(report, "ZZG-100") == []
    assert code != 0 and report["verdict"] == "failed"


def test_design_without_reachability_entry_is_reported(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: failure
    """L-6: a marked design whose entries carry no angle `reachability` gets exactly one finding of kind
    no-reachability naming the record; the same design with a reachability entry (ZZG-100) passes."""
    store = build(tmp_path, design("ZZG-100"), design("ZZG-101", _no_reachability()))

    _, report = run(store)

    one_finding(report, "ZZG-101", "no-reachability")
    assert family(report, "ZZG-100") == []


def test_non_code_records_are_not_judged_for_reachability(tmp_path):
    # covers: ACD-2500c-1-i
    # angle: boundary
    """Pinned scope: test_required false, or a change_target that names no code, is not judged; a
    change_target list containing code, and an absent change_target, are. The judged control must fire."""
    def rec(rid, **extra):
        return design(rid, _no_reachability(), **extra)

    store = build(
        tmp_path,
        rec("ZZG-100", change_target="docs"),
        rec("ZZG-101", test_required=False),
        rec("ZZG-102", change_target=["code", "docs"]),
        rec("ZZG-103", change_target="code"),
        rec("ZZG-104", change_target=["docs", "prompt"]),
    )

    _, report = run(store)

    assert family(report, "ZZG-100") == []
    assert family(report, "ZZG-101") == []
    assert family(report, "ZZG-104") == []
    one_finding(report, "ZZG-102", "no-reachability")
    one_finding(report, "ZZG-103", "no-reachability")
