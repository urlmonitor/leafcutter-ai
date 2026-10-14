"""
MODULE: test_acd_2500a_2_v
GOAL: Red-first specification of ACD-2500a-2-v: a documentation trigger on an L1
    with no matching documentation requirement is reported by trigger and expected
    specialist, and the check never creates a documentation record
    (scripts/ac_store/requirement_rule_check.py, family "documentation trigger to
    documentation requirement mapping", ticket 14).
BUSINESS CONTEXT: product-owner sets documentation triggers on an L1; the rule check
    (not the IT PO template) now owns whether each has a requirement. Expected
    specialist per trigger: how-to and reference-doc -> documentation-expert;
    sequence-diagram, state-diagram, component-diagram -> architecture-diagram-author.
ARCHITECTURE: Real CLI via main(argv) / subprocess over yaml.safe_dump records.
    Coverage matching (architect note D4, chosen default): a trigger is covered when
    any record in the checked folder, other than the L1 declaring it, has
    assigned_agent equal to the mapped specialist; counting is per specialist. An L1
    with `documentation_triggers: []` and no `documentation_rationale` is reported; an
    L1 where the key is absent or null is not (legacy L1s would all fail). The
    documentation records here declare a `.md` file so the specialist-versus-surface
    family of ACD-2500a-3 has nothing to say about them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_DOC_TRIGGERS,
    REPO_ROOT,
    check_store,
    cli_argv,
    finding_text,
    findings_for,
    hierarchy,
    make_store,
    run_cli_subprocess,
    snapshot_tree,
)

_L1 = "ACD-9990a"
_DIAGRAM_AGENT = "architecture-diagram-author"
_DOC_AGENT = "documentation-expert"
_EXPECTED_SPECIALIST = {
    "how-to": _DOC_AGENT,
    "sequence-diagram": _DIAGRAM_AGENT,
    "state-diagram": _DIAGRAM_AGENT,
    "component-diagram": _DIAGRAM_AGENT,
    "reference-doc": _DOC_AGENT,
}


def _doc_record(agent: str) -> dict:
    """Child override: a documentation requirement assigned to `agent`."""
    return {
        "assigned_agent": agent,
        "declared_files": [{"path": "docs/_fixture_doc_2500a_2_v.md", "state": "to_be_created"}],
    }


def _records(triggers, *, agents=(), rationale=None, with_triggers=True) -> list[dict]:
    """L0 + L1 declaring `triggers`, plus one documentation child per agent in `agents`
    and a plain python-coder child (so the folder is never empty of non-doc work)."""
    l1: dict = {}
    if with_triggers:
        l1["documentation_triggers"] = list(triggers)
    if rationale is not None:
        l1["documentation_rationale"] = rationale
    child = {n: _doc_record(agent) for n, agent in enumerate(agents, start=2)}
    return hierarchy("ACD-9990", 1 + len(agents), l1=l1, child=child)


def _doc_findings(report: dict) -> list[dict]:
    return findings_for(report, rule_family=FAMILY_DOC_TRIGGERS)


def _mixed_store(tmp_path):
    """The AC's scenario: triggers [sequence-diagram, reference-doc]; one diagram
    requirement, no documentation-expert requirement."""
    return make_store(
        tmp_path, _records(["sequence-diagram", "reference-doc"], agents=[_DIAGRAM_AGENT])
    )


def test_missing_reference_doc_reported_by_trigger_and_specialist(tmp_path):
    # covers: ACD-2500a-2-v
    # angle: criterion
    """One 'needs a decision' finding on the L1 names the trigger 'reference-doc' and
    the expected specialist documentation-expert; it is the only finding."""
    store = _mixed_store(tmp_path)

    exit_code, report = check_store(store)

    assert len(report["findings"]) == 1, report["findings"]
    finding = report["findings"][0]
    assert finding["rule_family"] == FAMILY_DOC_TRIGGERS
    assert finding["rule_family"] == "documentation trigger to documentation requirement mapping"
    assert finding["disposition"] == "needs a decision"
    assert finding["record_id"] == _L1 and finding["file"] == store.rel(_L1)
    text = finding_text(finding)
    assert "reference-doc" in text and _DOC_AGENT in text
    assert report["verdict"] == "failed" and exit_code == 1


def test_covered_trigger_not_reported(tmp_path):
    # covers: ACD-2500a-2-v
    # angle: criterion
    """No finding mentions 'sequence-diagram' (its diagram requirement exists). Control:
    once a documentation-expert requirement is added too, the folder yields no
    documentation finding at all and passes."""
    store = _mixed_store(tmp_path / "partial")
    _, report = check_store(store)
    assert all("sequence-diagram" not in finding_text(f) for f in _doc_findings(report))
    assert len(_doc_findings(report)) == 1  # the control row failed for reference-doc only

    full = make_store(
        tmp_path / "full",
        _records(["sequence-diagram", "reference-doc"], agents=[_DIAGRAM_AGENT, _DOC_AGENT]),
    )
    exit_code, full_report = check_store(full)

    assert _doc_findings(full_report) == []
    assert full_report["verdict"] == "passed" and exit_code == 0


def test_one_specialist_record_covers_both_of_its_triggers(tmp_path):
    # covers: ACD-2500a-2-v
    # angle: boundary
    """Counting is per specialist (note D4): a single documentation-expert record covers
    both how-to and reference-doc, while an architecture-diagram-author record covers
    none of them."""
    both = make_store(tmp_path / "both", _records(["how-to", "reference-doc"], agents=[_DOC_AGENT]))
    _, covered = check_store(both)
    assert _doc_findings(covered) == []

    wrong = make_store(
        tmp_path / "wrong", _records(["how-to", "reference-doc"], agents=[_DIAGRAM_AGENT])
    )
    _, uncovered = check_store(wrong)
    triggers_named = sorted(
        t for f in _doc_findings(uncovered) for t in ("how-to", "reference-doc")
        if t in finding_text(f)
    )
    assert triggers_named == ["how-to", "reference-doc"]


def test_no_documentation_record_created(tmp_path):
    # covers: ACD-2500a-2-v
    # angle: criterion
    """The folder's file set and every byte in it are unchanged after the run, and the
    finding is still raised (so the check ran and chose not to create anything)."""
    store = _mixed_store(tmp_path)
    before = snapshot_tree(store.folder)

    _, report = check_store(store)

    assert len(_doc_findings(report)) == 1
    after = snapshot_tree(store.folder)
    assert sorted(after) == sorted(before)
    assert after == before


def test_trigger_specialist_map_covers_all_five(tmp_path):
    # covers: ACD-2500a-2-v
    # angle: real_artifact
    """The shipped schema enum is exactly the five triggers; for each one, an L1 with no
    documentation record is reported naming the AC's expected specialist, a record
    assigned the OTHER specialist does not cover it, and the right specialist does."""
    schema = json.loads((REPO_ROOT / "config" / "ac_store_schema.json").read_text(encoding="utf-8"))
    enum = schema["properties"]["documentation_triggers"]["oneOf"][0]["items"]["enum"]
    assert sorted(enum) == sorted(_EXPECTED_SPECIALIST)

    for trigger in enum:
        expected = _EXPECTED_SPECIALIST[trigger]
        other = _DIAGRAM_AGENT if expected == _DOC_AGENT else _DOC_AGENT

        bare = make_store(tmp_path / f"{trigger}-bare", _records([trigger]))
        _, report = check_store(bare)
        findings = _doc_findings(report)
        assert len(findings) == 1, (trigger, report["findings"])
        text = finding_text(findings[0])
        assert trigger in text and expected in text, (trigger, text)

        wrong = make_store(tmp_path / f"{trigger}-wrong", _records([trigger], agents=[other]))
        _, wrong_report = check_store(wrong)
        assert len(_doc_findings(wrong_report)) == 1, (trigger, wrong_report["findings"])

        right = make_store(tmp_path / f"{trigger}-right", _records([trigger], agents=[expected]))
        _, right_report = check_store(right)
        assert _doc_findings(right_report) == [], (trigger, right_report["findings"])


@pytest.mark.parametrize(
    ("variant", "reported"),
    [
        ("rationale", False),   # empty triggers + stated rationale
        ("no_rationale", True),  # empty triggers, no rationale
        ("key_absent", False),  # legacy L1: no documentation_triggers key at all
    ],
)
def test_empty_triggers_rationale_rule(tmp_path, variant, reported):
    # covers: ACD-2500a-2-v
    # angle: boundary
    """Empty trigger list + a stated documentation_rationale: no finding. Empty list and
    no rationale: reported once, on the L1. An L1 without the key (legacy) is not
    reported (note D4)."""
    if variant == "rationale":
        records = _records([], rationale="Pure refactor; no new behaviour to document.")
    elif variant == "no_rationale":
        records = _records([])
    else:
        records = _records([], with_triggers=False)
    store = make_store(tmp_path, records)

    exit_code, report = check_store(store)

    findings = _doc_findings(report)
    if reported:
        assert len(findings) == 1, report["findings"]
        assert findings[0]["record_id"] == _L1
        assert findings[0]["disposition"] == "needs a decision"
        assert report["verdict"] == "failed" and exit_code == 1
    else:
        assert findings == [], report["findings"]
        assert report["verdict"] == "passed" and exit_code == 0


def test_acd_2500a_2_v_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-2-v
    # angle: reachability
    """Real CLI subprocess over the AC scenario: exit 1, one documentation finding on
    stdout naming 'reference-doc' and documentation-expert, and the folder untouched."""
    store = _mixed_store(tmp_path)
    before = snapshot_tree(store.folder)

    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)

    assert run.exit_code == 1, run.stderr
    assert run.report["verdict"] == "failed"
    findings = _doc_findings(run.report)
    assert len(findings) == 1 and len(run.report["findings"]) == 1
    assert "reference-doc" in finding_text(findings[0]) and _DOC_AGENT in finding_text(findings[0])
    assert snapshot_tree(store.folder) == before
