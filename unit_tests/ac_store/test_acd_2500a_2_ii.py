"""
MODULE: test_acd_2500a_2_ii
GOAL: Red-first specification of ACD-2500a-2-ii: the graph component list
    (`components`) is filled only when the record's namespace component maps to
    exactly one graph id; ambiguity and invalid values are reported, never
    rewritten (scripts/ac_store/requirement_rule_check.py, family
    "non-empty graph component list", ticket 11).
BUSINESS CONTEXT: `component` is the kebab namespace ("ac-driven-dev"); `components`
    holds graph ids ("ac_driven_dev"). Filling the second from the first is only
    safe when there is one candidate. The shipped migration map is one-to-one, so
    the two-candidate case injects a fixture map through `--migration-map FILE`
    (JSON {namespace: id | [ids]}) -- interpretation of architect note section 3
    ("a --migration-map-style parameter"), never a monkeypatch of the shipped dict.
ARCHITECTURE: Real CLI via main(argv) / subprocess over records written by
    yaml.safe_dump. The writer must be field-targeted: the empty `components: []`
    is replaced in place (a second `components:` key would be silently accepted by
    PyYAML, last wins), and every other byte stays.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_COMPONENTS,
    check_store,
    cli_argv,
    finding_text,
    findings_for,
    make_store,
    run_cli_subprocess,
    snapshot_tree,
    valid_record,
)

_A = "ACD-9991"   # namespace ac-driven-dev, empty list, one candidate
_B = "ACD-9992"   # namespace ac-store, empty list, two candidates (fixture map)
_C = "ACD-9993"   # lists the namespace spelling, which is not a graph id


def _records() -> list[dict]:
    return [
        valid_record(_A, level="L0", component="ac-driven-dev", components=[]),
        valid_record(_B, level="L0", component="ac-store", components=[]),
        valid_record(_C, level="L0", component="ac-driven-dev", components=["ac-driven-dev"]),
    ]


def _write_map(tmp_path: Path) -> Path:
    """Fixture namespace-to-graph map: ac-driven-dev -> one id, ac-store -> two."""
    target = tmp_path / "migration_map.fixture.json"
    target.write_text(
        json.dumps({"ac-driven-dev": "ac_driven_dev", "ac-store": ["ac_store", "build_pipeline"]}),
        encoding="utf-8",
    )
    return target


def _strip_key_block(text: str, key: str) -> str:
    """`text` without the column-0 `key:` line and the lines belonging to its value."""
    kept: list[str] = []
    skipping = False
    for line in re.findall(r"[^\n]*\n|[^\n]+", text):
        if line.startswith(f"{key}:"):
            skipping = True
            continue
        if skipping and (line[:1] in (" ", "\t") or re.match(r"-[ \r\n]", line)):
            continue
        skipping = False
        kept.append(line)
    return "".join(kept)


def test_single_mapping_fills_components_and_reports_fixed(tmp_path):
    # covers: ACD-2500a-2-ii
    # angle: criterion
    """With the SHIPPED map (no injection), record A's components becomes
    ['ac_driven_dev'] and it is reported 'fixed' naming the file and the id; every
    other byte of A is unchanged and no second `components:` key appears."""
    store = make_store(tmp_path, [_records()[0]])
    before = store.path(_A).read_bytes().decode("utf-8")

    exit_code, report = check_store(store)

    assert store.read(_A)["components"] == ["ac_driven_dev"]
    after = store.path(_A).read_bytes().decode("utf-8")
    assert after.count("components:") == 1  # replaced in place, not inserted twice
    assert _strip_key_block(after, "components") == _strip_key_block(before, "components")
    assert len(report["findings"]) == 1, report["findings"]
    finding = report["findings"][0]
    assert finding["rule_family"] == FAMILY_COMPONENTS == "non-empty graph component list"
    assert finding["disposition"] == "fixed"
    assert finding["file"] == store.rel(_A) and finding["record_id"] == _A
    assert "ac_driven_dev" in finding_text(finding)
    assert report["verdict"] == "passed" and exit_code == 0


def test_two_candidates_left_unchanged_naming_both(tmp_path):
    # covers: ACD-2500a-2-ii
    # angle: criterion
    """Record B (namespace with two candidate graph ids) is byte-identical after the
    run and reported 'needs a decision' naming BOTH candidate ids; A, in the same
    folder, is still filled (the control row that proves the family ran)."""
    store = make_store(tmp_path, _records())
    b_before = store.path(_B).read_bytes()

    _, report = check_store(store, "--migration-map", str(_write_map(tmp_path)))

    assert store.path(_B).read_bytes() == b_before
    findings = findings_for(report, record_id=_B)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["rule_family"] == FAMILY_COMPONENTS
    assert findings[0]["disposition"] == "needs a decision"
    assert findings[0]["file"] == store.rel(_B)
    text = finding_text(findings[0])
    assert "ac_store" in text and "build_pipeline" in text
    assert store.read(_A)["components"] == ["ac_driven_dev"]  # control: unambiguous still fixed


def test_namespace_spelling_value_reported_not_graph_id(tmp_path):
    # covers: ACD-2500a-2-ii
    # angle: boundary
    """Record C lists 'ac-driven-dev' (namespace spelling): the non-empty list is
    never rewritten (byte-identical) and the single finding is 'needs a decision'
    naming 'ac-driven-dev' as not a graph component id."""
    store = make_store(tmp_path, _records())
    c_before = store.path(_C).read_bytes()

    _, report = check_store(store, "--migration-map", str(_write_map(tmp_path)))

    assert store.path(_C).read_bytes() == c_before
    findings = findings_for(report, record_id=_C)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["rule_family"] == FAMILY_COMPONENTS
    assert findings[0]["disposition"] == "needs a decision"
    assert findings[0]["file"] == store.rel(_C)
    text = finding_text(findings[0])
    assert "ac-driven-dev" in text
    assert "component" in text.lower()
    assert store.read(_C)["components"] == ["ac-driven-dev"]


def test_acd_2500a_2_ii_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-2-ii
    # angle: reachability
    """Real CLI subprocess over A, B and C: exit 1 (two decisions left), exactly one
    'fixed' and two 'needs a decision' entries on stdout, A's fill is on disk and B
    and C are untouched."""
    store = make_store(tmp_path, _records())
    others = {n: snapshot_tree(store.folder)[n] for n in (f"{_B}.yaml", f"{_C}.yaml")}

    run = run_cli_subprocess(
        cli_argv(store, "--migration-map", str(_write_map(tmp_path))), cwd=store.repo_root
    )

    assert run.exit_code == 1, run.stderr
    assert run.report["verdict"] == "failed"
    assert sorted(f["disposition"] for f in run.report["findings"]) == [
        "fixed", "needs a decision", "needs a decision",
    ]
    assert store.read(_A)["components"] == ["ac_driven_dev"]
    after = snapshot_tree(store.folder)
    assert {n: after[n] for n in others} == others
