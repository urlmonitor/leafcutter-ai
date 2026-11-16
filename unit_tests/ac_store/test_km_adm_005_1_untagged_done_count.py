"""
MODULE: unit_tests/ac_store/test_km_adm_005_1_untagged_done_count.py
GOAL: KM-ADM-005-1 - the untagged-done count (scripts/ac_store/untagged_done_count.py) leaves out the
    finished records the done gate waives, and reports each exclusion as a count paired with its ground.
BUSINESS CONTEXT: The ratchet counted every finished record no test tags, so every legitimate test-free
    close (declared test_required false with a stated reason) tripped it.

MEASUREMENT CALL (fixed here by the test writer; the record names no signature; every test uses it):
    untagged_done_count.measure(ac_root: Path, test_roots: Sequence[Path]) -> result
    result.finished: int            finished (work_status done) records enumerated
    result.tagged: int              finished records some '# covers:' tag names
    result.untagged: list[str]      ids of finished, unwaived, unsuperseded records no tag names
    result.exclusions: Mapping[str, int]  ground string -> count (explained exclusions only)
    result.unexplained_shortfall: int     excluded records whose ground is not on PUBLISHED_GROUNDS
    result.sum_holds: bool          untagged + sum(exclusions) + tagged == finished
    result.assert_sum() -> None     raises AssertionError when sum_holds is False
    untagged_done_count.PUBLISHED_GROUNDS: collection of the legitimate grounds (membership tested)

ARCHITECTURE: A temp store (yaml.safe_dump records) and temp test roots (real files carrying '# covers:'
    tags) are measured. The shared predicate is patched at its source (_done_proof_phase_helpers) and at
    every name the measurement module may have bound it to.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
GROUND_SUPERSEDED = "superseded"
GROUND_WAIVED = "waived: declared test-free with a stated reason"
REASON = "Docs-only change; no executable behaviour to test."
LIVE_AC_ROOT = REPO / "docs" / "acceptance-criteria"
LIVE_TEST_ROOTS = [REPO / "unit_tests", REPO / "tests", REPO / "leafcutter-web"]


@pytest.fixture(scope="module")
def udc():
    """The measurement module, imported flat the way the deployed store imports its siblings."""
    sys.path.insert(0, str(REPO / "scripts" / "ac_store"))
    return importlib.import_module("untagged_done_count")


def _record(ac_id: str, **fields) -> str:
    data = {"id": ac_id, "title": f"Fixture {ac_id}", "component": "x", "level": "L3", "status": "active",
            "work_status": "done"}
    data.update(fields)
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _store(tmp_path: Path, records: dict[str, str], covers: list[str] | None = None) -> tuple[Path, list[Path]]:
    """Write records (id -> yaml text) under a store and one real test file carrying the `covers` lines."""
    ac_root = tmp_path / "acs"
    ac_root.mkdir()
    for ac_id, text in records.items():
        (ac_root / f"{ac_id}.yaml").write_text(text, encoding="utf-8")
    tests = tmp_path / "tests_root"
    tests.mkdir()
    body = "".join(f"def test_{i}():\n    # covers: {tag}\n    pass\n" for i, tag in enumerate(covers or []))
    (tests / "test_tags.py").write_text(body or "# no tags\n", encoding="utf-8")
    return ac_root, [tests]


def _waived(ac_id: str) -> str:
    return _record(ac_id, test_required=False, test_rationale=REASON)


def _patch_predicate(monkeypatch, udc, verdict: bool) -> None:
    def fake(_ac_info):
        return verdict

    for name in ("_done_proof_phase_helpers", "scripts.ac_store._done_proof_phase_helpers"):
        if name in sys.modules:
            monkeypatch.setattr(sys.modules[name], "is_covers_tag_waived", fake)
    importlib.import_module("_done_proof_phase_helpers")
    monkeypatch.setattr(sys.modules["_done_proof_phase_helpers"], "is_covers_tag_waived", fake)
    if hasattr(udc, "is_covers_tag_waived"):
        monkeypatch.setattr(udc, "is_covers_tag_waived", fake)


def test_a_waived_done_record_is_not_counted_untagged(tmp_path, udc):
    # covers: KM-ADM-005-1
    # angle: criterion
    """A done test-free record with a real reason and no tag is waived; a done test_required true record is untagged."""
    ac_root, roots = _store(tmp_path, {"ZZ-1": _waived("ZZ-1"), "ZZ-2": _record("ZZ-2", test_required=True)})
    result = udc.measure(ac_root, roots)
    assert result.untagged == ["ZZ-2"]
    assert dict(result.exclusions) == {GROUND_WAIVED: 1}
    assert result.finished == 2


def test_waiver_decision_is_the_shared_predicate_not_a_copy(tmp_path, udc, monkeypatch):
    # covers: KM-ADM-005-1
    # angle: seam
    """With is_covers_tag_waived patched False a real waiver is untagged; patched True a reasonless record is excluded."""
    ac_root, roots = _store(tmp_path, {"ZZ-1": _waived("ZZ-1"), "ZZ-2": _record("ZZ-2", test_required=False)})
    _patch_predicate(monkeypatch, udc, False)
    refused = udc.measure(ac_root, roots)
    assert sorted(refused.untagged) == ["ZZ-1", "ZZ-2"], "a re-typed conjunction ignores the patched predicate"
    _patch_predicate(monkeypatch, udc, True)
    accepted = udc.measure(ac_root, roots)
    assert accepted.untagged == [], "the reasonless record must be excluded when the shared predicate says so"
    assert dict(accepted.exclusions) == {GROUND_WAIVED: 2}


def test_each_exclusion_is_reported_with_its_exact_ground(tmp_path, udc):
    # covers: KM-ADM-005-1
    # angle: criterion
    """One superseded and two waived done records report 1 under 'superseded' and 2 under the waived ground."""
    records = {"ZZ-1": _record("ZZ-1", status="superseded_by"), "ZZ-2": _waived("ZZ-2"), "ZZ-3": _waived("ZZ-3")}
    result = udc.measure(*_store(tmp_path, records))
    assert GROUND_SUPERSEDED == "superseded"
    assert GROUND_WAIVED == "waived: declared test-free with a stated reason"
    assert {g: n for g, n in dict(result.exclusions).items() if n} == {GROUND_SUPERSEDED: 1, GROUND_WAIVED: 2}


def test_exclusion_without_a_published_ground_is_an_unexplained_shortfall(tmp_path, udc, monkeypatch):
    # covers: KM-ADM-005-1
    # angle: failure
    """With the waived ground off the published list the two waived records are a shortfall and the sum check fails."""
    records = {"ZZ-1": _waived("ZZ-1"), "ZZ-2": _waived("ZZ-2"), "ZZ-3": _record("ZZ-3", test_required=True)}
    ac_root, roots = _store(tmp_path, records)
    monkeypatch.setattr(udc, "PUBLISHED_GROUNDS", frozenset({GROUND_SUPERSEDED}))
    result = udc.measure(ac_root, roots)
    assert result.unexplained_shortfall == 2
    assert result.untagged == ["ZZ-3"], "the shortfall must not silently shrink or grow the untagged list"
    assert result.sum_holds is False
    with pytest.raises(AssertionError):
        result.assert_sum()


def test_untagged_plus_exclusions_plus_tagged_equals_finished_records(tmp_path, udc):
    # covers: KM-ADM-005-1
    # angle: boundary
    """A mixed store (quoted id, comma covers list, hierarchical id) and the live store both satisfy the sum."""
    quoted = _record("GE-1", test_required=True).replace("id: GE-1", 'id: "GE-1"')
    assert yaml.safe_load(quoted)["id"] == "GE-1"
    records = {
        "GE-1": quoted,
        "BO-2500a-8-i": _record("BO-2500a-8-i", test_required=True),
        "ZZ-3": _record("ZZ-3", test_required=True),
        "ZZ-4": _record("ZZ-4", status="superseded_by"),
        "ZZ-5": _waived("ZZ-5"),
        "ZZ-6": _record("ZZ-6", test_required=True),
        "ZZ-7": _record("ZZ-7", work_status="todo"),
    }
    ac_root, roots = _store(tmp_path, records, covers=["GE-1, BO-2500a-8-i", "ZZ-3"])
    result = udc.measure(ac_root, roots)
    assert (result.finished, result.tagged, result.untagged) == (6, 3, ["ZZ-6"])
    assert sum(dict(result.exclusions).values()) == 2
    assert len(result.untagged) + sum(dict(result.exclusions).values()) + result.tagged == result.finished
    live = udc.measure(LIVE_AC_ROOT, LIVE_TEST_ROOTS)
    assert live.sum_holds, "the live store does not satisfy untagged + exclusions + tagged == finished"
    assert live.finished > 0


def test_finished_test_free_record_without_a_stated_reason_is_still_untagged(tmp_path, udc):
    # covers: KM-ADM-005-1
    # angle: discrimination
    """test_required false with an absent, null, empty, spaces-only or NBSP-only reason is untagged, never excluded."""
    variants = {
        "ZZ-1": _record("ZZ-1", test_required=False),
        "ZZ-2": _record("ZZ-2", test_required=False, test_rationale=None),
        "ZZ-3": _record("ZZ-3", test_required=False, test_rationale=""),
        "ZZ-4": _record("ZZ-4", test_required=False, test_rationale="   "),
        "ZZ-5": _record("ZZ-5", test_required=False, test_rationale=" "),
    }
    result = udc.measure(*_store(tmp_path, variants))
    assert sorted(result.untagged) == sorted(variants), "a waiver was taken on test_required alone or on a blank reason"
    assert {g: n for g, n in dict(result.exclusions).items() if n} == {}
