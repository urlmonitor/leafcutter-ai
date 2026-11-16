"""
MODULE: unit_tests/ac_store/test_km_adm_005_3_composite_ratchet.py
GOAL: KM-ADM-005-3 - the untagged-done count (scripts/ac_store/untagged_done_count.py) leaves out a finished
    L0, L1 or docs-only composite whose children the done gate proves, under the new fourth ground
    "proved through its children (tags read, tests not run)".
BUSINESS CONTEXT: The ratchet counted a composite as untested although the done gate proves it through its
    children (open known issue KI-ACS-20261014). Code L2 composites stay counted by design.

MEASUREMENT CALL (extends the one fixed by the KM-ADM-005-1 tests; the record names no new signature):
    untagged_done_count.measure(ac_root, test_roots) -> result
    result.exclusions[<new ground>]: int         how many composites left under the new ground
    result.excluded_ids[<new ground>]: list[str] the ids that left, sorted (fixed here by the test writer;
                                                 used only by test_measurement_lists_the_excluded_ids_...)
    untagged_done_count.PUBLISHED_GROUNDS        gains exactly one member beside the two existing grounds;
                                                 tests find the new ground as the set difference, so its
                                                 constant name is not pinned.

ARCHITECTURE: Every fixture store is real YAML written with yaml.safe_dump in a tmp dir. Every fixture test
    tree is real .py/.js files carrying real covers lines. The done gate's composite rule is patched at run
    time on the _done_proof_composite module (flat and package-style names). No build.py is spawned.
    A test that asserts "stays counted" always carries a positive control that leaves the count, so it is red
    until the new ground exists, for that reason and no other.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
GROUND_SUPERSEDED = "superseded"
GROUND_WAIVED = "waived: declared test-free with a stated reason"
OLD_GROUNDS = frozenset({GROUND_SUPERSEDED, GROUND_WAIVED})
REASON = "Docs-only change; no executable behaviour to test."
LIVE_AC_ROOT = REPO / "docs" / "acceptance-criteria"
LIVE_TEST_ROOTS = [REPO / "unit_tests", REPO / "tests", REPO / "leafcutter-web"]
RATCHET_FILE = REPO / "unit_tests" / "docs" / "test_artifact_graph_covers_scope.py"
SUCCESSOR = "ZZ-900"


@pytest.fixture(scope="module")
def udc():
    """The measurement module, imported flat the way the deployed store imports its siblings."""
    sys.path.insert(0, str(REPO / "scripts" / "ac_store"))
    return importlib.import_module("untagged_done_count")


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _rec(ac_id: str, **fields) -> dict:
    data = {"id": ac_id, "title": f"Fixture {ac_id}", "component": "x", "level": "L2", "status": "active",
            "work_status": "done", "test_required": True, "change_target": "code"}
    data.update(fields)
    return data


def _family(parent_id: str, child_suffixes: list[str], level: str = "L1", child_level: str = "L2",
            listed: list[str] | None = None, **parent_fields) -> dict[str, dict]:
    """A composite and its children (all done); covered_by lists `listed` (default: every child)."""
    child_ids = [f"{parent_id}-{s}" for s in child_suffixes]
    records = {parent_id: _rec(parent_id, level=level, covered_by=child_ids if listed is None else listed,
                               **parent_fields)}
    for cid in child_ids:
        records[cid] = _rec(cid, level=child_level, parent=parent_id)
    return records


def _successor() -> dict[str, dict]:
    """A real, not-finished record that a valid supersession can name."""
    return {SUCCESSOR: _rec(SUCCESSOR, work_status="todo")}


def _retire(record: dict, successors: list[str] | None = None) -> dict:
    record.update(status="superseded_by", superseded_by=[SUCCESSOR] if successors is None else successors)
    return record


def _tag_text(tags: list[str]) -> str:
    return "".join(f"def test_{i}():\n    # covers: {t}\n    pass\n" for i, t in enumerate(tags)) or "# no tags\n"


def _store(tmp_path: Path, name: str, records: dict[str, dict], covers: list[str] | None = None,
           files: dict[str, str] | None = None) -> tuple[Path, list[Path]]:
    """Write the records under a store and real test files under one test root; return (ac_root, [root])."""
    base = tmp_path / name
    ac_root = base / "acs"
    ac_root.mkdir(parents=True)
    for ac_id, data in records.items():
        (ac_root / f"{ac_id}.yaml").write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                                               encoding="utf-8")
    tests = base / "tests_root"
    tests.mkdir()
    (tests / "test_tags.py").write_text(_tag_text(covers or []), encoding="utf-8")
    for rel, text in (files or {}).items():
        (tests / rel).write_text(text, encoding="utf-8")
    return ac_root, [tests]


def _all_ids(records: dict[str, dict]) -> list[str]:
    return [i for i, r in records.items() if r.get("work_status") == "done"]


def _new_ground(udc) -> str:
    """The one ground added to PUBLISHED_GROUNDS beside the two existing ones (red until it exists)."""
    new = set(udc.PUBLISHED_GROUNDS) - OLD_GROUNDS
    assert len(new) == 1, f"PUBLISHED_GROUNDS must gain exactly one new ground; found {sorted(new)}"
    return next(iter(new))


def _check(udc, result, left: int, untagged: list[str]) -> None:
    """Exact counts: `left` composites under the new ground, exactly `untagged` still counted, sum holds."""
    ground = _new_ground(udc)
    assert result.exclusions.get(ground, 0) == left, f"exclusions: {dict(result.exclusions)}"
    assert sorted(result.untagged) == sorted(untagged), f"untagged: {result.untagged}"
    assert result.unexplained_shortfall == 0
    result.assert_sum()


def _patch_rule(monkeypatch, fn) -> None:
    """Replace the done gate's composite rule at run time, on every name the module may be loaded under."""
    importlib.import_module("_done_proof_composite")
    patched = 0
    for name in ("_done_proof_composite", "scripts.ac_store._done_proof_composite"):
        module = sys.modules.get(name)
        if module is not None:
            monkeypatch.setattr(module, "_unproven_composite_children", fn)
            patched += 1
    assert patched, "the gate's composite module is not loaded"


# ---------------------------------------------------------------------------
# the three-way conjunction
# ---------------------------------------------------------------------------


def test_composite_leaves_the_count_only_when_a_b_and_c_all_hold(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: (a) only, ignoring (b); (a)+(b) ignoring (c) incl. mixed/absent change_target;
    a rule that trusts covered_by alone and never consults the gate."""
    records: dict[str, dict] = {}
    records.update(_family("ZZ-100a", ["1", "2"]))  # control: a, b, c all hold
    records.update(_family("ZZ-200a", ["1", "2"]))  # (a) broken: child 2 is done but untagged
    records.update(_family("ZZ-300a", ["1", "2"], listed=["ZZ-300a-1"]))  # (b) broken: live child 2 unlisted
    records.update(_family("ZZ-400a-1", ["i", "ii"], level="L2", child_level="L3"))  # (c) broken: code L2
    records.update(_family("ZZ-500a-1", ["i", "ii"], level="L2", child_level="L3",
                           change_target=["docs", "code"]))  # (c) broken: mixed list
    mixed_absent = _family("ZZ-600a-1", ["i", "ii"], level="L2", child_level="L3")
    del mixed_absent["ZZ-600a-1"]["change_target"]  # (c) broken: absent change_target
    records.update(mixed_absent)
    records.update(_family("ZZ-700", ["a"], level="L0", child_level="L1"))  # control: an L0 qualifies
    covers = [i for i in _all_ids(records) if i not in {"ZZ-200a-2"} and not _is_composite(records, i)]
    ac_root, roots = _store(tmp_path, "conj", records, covers)
    result = udc.measure(ac_root, roots)
    _check(udc, result, left=2, untagged=["ZZ-200a", "ZZ-200a-2", "ZZ-300a", "ZZ-400a-1", "ZZ-500a-1", "ZZ-600a-1"])


def _is_composite(records: dict[str, dict], ac_id: str) -> bool:
    return bool(records[ac_id].get("covered_by"))


def test_composite_whose_every_child_is_retired_is_not_vacuously_proved(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: a vacuous proof when every child is retired; an empty list of live children read
    as 'no unproven child' without asking the gate rule."""
    records = {SUCCESSOR: _successor()[SUCCESSOR]}
    records.update(_family("ZZ-100a", ["1"]))
    _retire(records["ZZ-100a-1"])
    records.update(_family("ZZ-200a", ["1", "2"]))  # control: one retired child plus one proved live child
    _retire(records["ZZ-200a-1"])
    covers = ["ZZ-200a-2"]
    result = udc.measure(*_store(tmp_path, "retired", records, covers))
    _check(udc, result, left=1, untagged=["ZZ-100a"])
    assert result.exclusions[GROUND_SUPERSEDED] == 2
    # With its own tag the all-retired composite is tagged, never under the new ground.
    own = udc.measure(*_store(tmp_path, "retired_own", records, covers + ["ZZ-100a"]))
    _check(udc, own, left=1, untagged=[])


def test_test_paths_in_covered_by_are_not_read_as_children(tmp_path, udc, monkeypatch):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: test paths read as children; any non-empty covered_by treated as a composite."""
    records = _family("ZZ-100a", ["1"], listed=["ZZ-100a-1", "unit_tests/ac_store/test_x.py"])
    records.update({"ZZ-200a": _rec("ZZ-200a", level="L1",
                                    covered_by=["unit_tests/a/test_y.py", "tests/b.test.ts"])})
    ac_root, roots = _store(tmp_path, "paths", records, ["ZZ-100a-1"])
    real = udc.measure(ac_root, roots)
    _check(udc, real, left=1, untagged=["ZZ-200a"])
    seen: list[str] = []

    def accept_all(data, *_args, **_kwargs):
        seen.append(str(data.get("id")))
        return []

    _patch_rule(monkeypatch, accept_all)
    patched = udc.measure(ac_root, roots)
    _check(udc, patched, left=1, untagged=["ZZ-200a"])
    assert seen == ["ZZ-100a"], f"the gate rule was asked about a path-only record: {seen}"


def test_gate_tag_set_is_built_from_the_ratchets_test_roots_not_the_repo_root(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: a tag set built from the gate's repo-root default; a tag set from the ratchet's
    own collect_covers_tags, which also reads .js files."""
    records: dict[str, dict] = {}
    for parent in ("ZZ-100a", "ZZ-200a", "ZZ-300a"):
        records.update(_family(parent, ["1", "2"]))
    outside = tmp_path / "outside_root"
    outside.mkdir()
    (outside / "test_elsewhere.py").write_text(_tag_text(["ZZ-100a-2"]), encoding="utf-8")
    js = "// covers: ZZ-200a-2\n"
    covers = ["ZZ-100a-1", "ZZ-200a-1", "ZZ-300a-1", "ZZ-300a-2"]
    ac_root, roots = _store(tmp_path, "roots", records, covers, files={"spec.js": js})
    result = udc.measure(ac_root, roots)
    # ZZ-200a-2 is tagged for the ratchet (the .js file) but not for the gate; ZZ-100a-2 is tagged nowhere here.
    assert "ZZ-200a-2" not in result.untagged
    _check(udc, result, left=1, untagged=["ZZ-100a", "ZZ-100a-2", "ZZ-200a"])


# ---------------------------------------------------------------------------
# bucket order
# ---------------------------------------------------------------------------


def test_each_finished_record_lands_in_exactly_one_bucket_in_the_fixed_order(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: the new test placed before tagged/superseded/waived; a composite counted both as
    tagged and under the new ground; an untagged remainder that still lists an excluded record."""
    records = _successor()
    records.update(_family("ZZ-100a", ["1", "2"]))  # tagged by its own covers line
    records.update(_family("ZZ-200a", ["1", "2"]))
    _retire(records["ZZ-200a"])  # superseded
    records.update(_family("ZZ-300a", ["1", "2"], test_required=False, test_rationale=REASON))  # waived
    records.update(_family("ZZ-400a", ["1", "2"]))  # plain proved composite
    children = [i for i in _all_ids(records) if i.count("-") == 2]
    result = udc.measure(*_store(tmp_path, "order", records, children + ["ZZ-100a"]))
    ground = _new_ground(udc)
    assert dict(result.exclusions) == {GROUND_SUPERSEDED: 1, GROUND_WAIVED: 1, ground: 1}
    assert (result.finished, result.tagged, result.untagged) == (12, 9, [])
    result.assert_sum()


# ---------------------------------------------------------------------------
# the worked cases
# ---------------------------------------------------------------------------


def test_proved_l1_with_two_tagged_done_children_leaves_the_count(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: criterion
    """A finished L1 whose two finished children are tagged by a collected test leaves, counted once."""
    records = _family("ZZ-100a", ["1", "2"])
    result = udc.measure(*_store(tmp_path, "proved", records, ["ZZ-100a-1", "ZZ-100a-2"]))
    _check(udc, result, left=1, untagged=[])
    assert (result.finished, result.tagged) == (3, 2)


def test_child_with_work_status_todo_keeps_the_parent_counted_even_when_tagged(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong version caught: tag-only judging that ignores the child's work_status."""
    records = _family("ZZ-100a", ["1", "2"])
    records["ZZ-100a-2"]["work_status"] = "todo"
    covers = ["ZZ-100a-1", "ZZ-100a-2"]
    held = udc.measure(*_store(tmp_path, "todo_child", records, covers))
    _check(udc, held, left=0, untagged=["ZZ-100a"])
    records["ZZ-100a-2"]["work_status"] = "done"
    freed = udc.measure(*_store(tmp_path, "done_child", records, covers))
    _check(udc, freed, left=1, untagged=[])


def test_untagged_composite_grandchild_keeps_the_parent_counted(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: direct children only, no recursion; a child judged by its own work_status alone
    without descending into its covered_by."""
    records = _family("ZZ-100a", ["1"])
    records["ZZ-100a-1"]["covered_by"] = ["ZZ-100a-1-i"]
    records["ZZ-100a-1-i"] = _rec("ZZ-100a-1-i", level="L3", parent="ZZ-100a-1", work_status="todo")
    todo = udc.measure(*_store(tmp_path, "gc_todo", records, []))
    _check(udc, todo, left=0, untagged=["ZZ-100a", "ZZ-100a-1"])
    records["ZZ-100a-1-i"]["work_status"] = "done"
    untagged = udc.measure(*_store(tmp_path, "gc_untagged", records, []))
    _check(udc, untagged, left=0, untagged=["ZZ-100a", "ZZ-100a-1", "ZZ-100a-1-i"])
    proved = udc.measure(*_store(tmp_path, "gc_proved", records, ["ZZ-100a-1-i"]))
    _check(udc, proved, left=1, untagged=["ZZ-100a-1"])  # the code L2 child itself stays counted


def test_code_schema_pipeline_config_prompt_l2_composite_stays_counted(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: code L2s excluded because the gate rule was applied at every level; an absent or
    mixed change_target treated as docs. The docs control leaves, so the test is red before the ground exists."""
    records: dict[str, dict] = {}
    stay: list[str] = []
    for n, target in enumerate(["code", "schema", "pipeline", "config", "prompt", None, ["docs", "code"]], 1):
        parent = f"ZZ-10{n}a-1"
        family = _family(parent, ["i", "ii"], level="L2", child_level="L3", change_target=target)
        if target is None:
            del family[parent]["change_target"]
        records.update(family)
        stay.append(parent)
    records.update(_family("ZZ-108a-1", ["i", "ii"], level="L2", child_level="L3", change_target="docs"))
    covers = [i for i in _all_ids(records) if i.count("-") == 3]
    result = udc.measure(*_store(tmp_path, "l2", records, covers))
    _check(udc, result, left=1, untagged=stay)


def test_docs_l2_composite_with_proved_children_leaves_the_count(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: criterion
    """Wrong version caught: a level-only rule that keeps counting docs aggregators (string and one-member list)."""
    records = _family("ZZ-101a-1", ["i", "ii"], level="L2", child_level="L3", change_target="docs")
    records.update(_family("ZZ-102a-1", ["i", "ii"], level="L2", child_level="L3", change_target=["docs"]))
    covers = [i for i in _all_ids(records) if i.count("-") == 3]
    result = udc.measure(*_store(tmp_path, "docs_l2", records, covers))
    _check(udc, result, left=2, untagged=[])


def test_incomplete_covered_by_keeps_the_parent_counted_and_superseded_omission_does_not(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: an incomplete covered_by accepted; completeness read from covered_by or finished
    records only; a superseded child counted as live; an invalid supersession treated as retired."""
    records = _successor()
    # A: live child 2 on disk (id-derived parent), unlisted
    records.update(_family("ZZ-100a", ["1", "2"], listed=["ZZ-100a-1"]))
    # B: live record ZZ-777 reaches ZZ-200a through its parent field only (its own id derives no parent), unlisted
    records.update(_family("ZZ-200a", ["1"]))
    records["ZZ-777"] = _rec("ZZ-777", level="L2", parent="ZZ-200a")
    # C: the unlisted sibling is validly superseded (not finished), so it does not hold the parent back
    records.update(_family("ZZ-300a", ["1"]))
    records["ZZ-300a-3"] = _retire(_rec("ZZ-300a-3", level="L2", parent="ZZ-300a", work_status="todo"))
    # D: the unlisted sibling's supersession names a record that does not exist: invalid, so live
    records.update(_family("ZZ-400a", ["1"]))
    records["ZZ-400a-3"] = _retire(_rec("ZZ-400a-3", level="L2", parent="ZZ-400a", work_status="todo"),
                                   ["ZZ-NOPE"])
    covers = ["ZZ-100a-1", "ZZ-100a-2", "ZZ-200a-1", "ZZ-777", "ZZ-300a-1", "ZZ-400a-1"]
    result = udc.measure(*_store(tmp_path, "complete", records, covers))
    _check(udc, result, left=1, untagged=["ZZ-100a", "ZZ-200a", "ZZ-400a"])


def test_prose_covers_line_the_gate_pattern_rejects_does_not_prove_the_parent(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong version caught: the ratchet's loose covers reading used to build the set passed to the gate rule."""
    records = _family("ZZ-100a", ["1"])
    records.update(_family("ZZ-200a", ["1"]))
    prose = '"""Notes.\ncovers: ZZ-100a-1\n"""\n'  # no comment marker: the gate's pattern rejects it
    result = udc.measure(*_store(tmp_path, "prose", records, ["ZZ-200a-1"], files={"test_prose.py": prose}))
    assert "ZZ-100a-1" not in result.untagged, "the ratchet's own reading must count the prose-tagged child"
    _check(udc, result, left=1, untagged=["ZZ-100a"])


# ---------------------------------------------------------------------------
# run-time lookup of the gate's rule
# ---------------------------------------------------------------------------


def test_patching_the_gate_composite_rule_flips_the_verdict_both_ways(tmp_path, udc, monkeypatch):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: a re-typed copy of the gate rule; the rule bound by from-import so a run-time patch
    is ignored; a ratchet-side child check of work_status, tag or waiver that overrides the rule's answer."""
    records = _family("ZZ-100a", ["1", "2"])  # proved
    records.update(_family("ZZ-200a", ["1", "2"]))
    records["ZZ-200a-2"]["work_status"] = "todo"  # (b) and (c) hold, a child is unfinished
    ac_root, roots = _store(tmp_path, "patch", records, ["ZZ-100a-1", "ZZ-100a-2", "ZZ-200a-1", "ZZ-200a-2"])
    baseline = udc.measure(ac_root, roots)
    _check(udc, baseline, left=1, untagged=["ZZ-200a"])
    calls: list[str] = []

    def everything_unproven(data, *_args, **_kwargs):
        calls.append(str(data["id"]))
        return [f"{data['id']}-unproven"]

    _patch_rule(monkeypatch, everything_unproven)
    refused = udc.measure(ac_root, roots)
    _check(udc, refused, left=0, untagged=["ZZ-100a", "ZZ-200a"])
    assert sorted(calls) == ["ZZ-100a", "ZZ-200a"], "the rule is consulted once per qualifying composite"

    def nothing_unproven(data, *_args, **_kwargs):
        return []

    _patch_rule(monkeypatch, nothing_unproven)
    accepted = udc.measure(ac_root, roots)
    _check(udc, accepted, left=2, untagged=[])


# ---------------------------------------------------------------------------
# published output
# ---------------------------------------------------------------------------


def test_ground_wording_says_tags_read_and_tests_not_run_and_claims_no_pass(tmp_path, udc):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: a ground worded 'tests pass'; 'proved'/'verified' without the qualifier; an
    exclusions key that differs from the constant on PUBLISHED_GROUNDS."""
    ground = _new_ground(udc)
    lowered = ground.lower()
    assert "tags read" in lowered and "tests not run" in lowered, ground
    assert not re.search(r"pass|verified", lowered), f"the ground claims a pass: {ground!r}"
    records = _family("ZZ-100a", ["1", "2"])
    result = udc.measure(*_store(tmp_path, "wording", records, ["ZZ-100a-1", "ZZ-100a-2"]))
    assert set(result.exclusions) == {ground}


def test_measurement_lists_the_excluded_ids_sorted_beside_the_count(tmp_path, udc, monkeypatch, capsys):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: a count without the ids; an id list that is unsorted or includes a record excluded
    under another ground."""
    records = _successor()
    for parent in ("ZZ-300a", "ZZ-100a", "ZZ-200a"):  # written in unsorted order
        records.update(_family(parent, ["1"]))
    records.update(_family("ZZ-400a", ["1"]))
    _retire(records["ZZ-400a"])  # excluded under another ground
    covers = [i for i in _all_ids(records) if i.count("-") == 2]
    ac_root, roots = _store(tmp_path, "ids", records, covers)
    result = udc.measure(ac_root, roots)
    ground = _new_ground(udc)
    assert result.exclusions[ground] == 3
    assert list(result.excluded_ids[ground]) == ["ZZ-100a", "ZZ-200a", "ZZ-300a"]

    spec = importlib.util.spec_from_file_location("_km_adm_005_3_ratchet_module", RATCHET_FILE)
    ratchet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ratchet)
    monkeypatch.setattr(ratchet, "_TEST_ROOTS", roots)
    ratchet.test_untagged_done_ac_backlog_does_not_grow(ac_root=ac_root)
    lines = [line for line in capsys.readouterr().out.splitlines() if ground in line]
    assert len(lines) == 1, f"the ground must be printed once, beside its count and ids: {lines}"
    positions = [lines[0].find(i) for i in ("ZZ-100a", "ZZ-200a", "ZZ-300a")]
    assert -1 not in positions and positions == sorted(positions), lines[0]
    assert "3" in lines[0].replace("ZZ-100a", "").replace("ZZ-200a", "").replace("ZZ-300a", "")
    assert "ZZ-400a" not in lines[0]


def test_new_ground_is_published_and_the_sum_still_holds_on_a_fixture_and_the_live_store(tmp_path, udc, monkeypatch):
    # covers: KM-ADM-005-3
    # angle: discrimination
    """Wrong versions caught: a ground missing from PUBLISHED_GROUNDS; a second list kept apart from it; a
    bucket that counts a composite twice or not at all."""
    ground = _new_ground(udc)
    records: dict[str, dict] = {}
    for parent in ("ZZ-100a", "ZZ-200a", "ZZ-300a"):
        records.update(_family(parent, ["1", "2"]))
    covers = [i for i in _all_ids(records) if i.count("-") == 2]
    ac_root, roots = _store(tmp_path, "published", records, covers)
    result = udc.measure(ac_root, roots)
    assert result.exclusions[ground] == 3
    assert result.unexplained_shortfall == 0
    assert len(result.untagged) + sum(result.exclusions.values()) + result.tagged == result.finished == 9
    result.assert_sum()
    monkeypatch.setattr(udc, "PUBLISHED_GROUNDS", frozenset(OLD_GROUNDS))
    unpublished = udc.measure(ac_root, roots)
    assert unpublished.unexplained_shortfall == 3
    with pytest.raises(AssertionError):
        unpublished.assert_sum()
    monkeypatch.undo()
    live = udc.measure(LIVE_AC_ROOT, LIVE_TEST_ROOTS)
    assert live.sum_holds and live.unexplained_shortfall == 0
    assert live.exclusions.get(ground, 0) > 0, "no finished composite of the live store left under the new ground"
