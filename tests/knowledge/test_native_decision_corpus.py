"""Independent source fidelity check for the published decision corpus."""

from importlib import import_module
from pathlib import Path

import yaml


def test_native_decision_real_corpus_preserves_all_authored_records():
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # test type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    paths = sorted((root / "docs/decisions").glob("dec-*.yaml"))
    before = {path: path.read_bytes() for path in paths}
    source = {yaml.safe_load(data)["id"]: yaml.safe_load(data) for data in before.values()}
    assert paths
    assert len(paths) == len(source)
    # Reviewed anchors: the two decisions published with the criteria library (2026-10-05).
    assert {"dec-93c1c730463c1f3c", "dec-a070edfb6465bced"} <= set(source)
    records = import_module("knowledge.native_types.decision").extract(root)
    assert len(records) == len(paths)
    assert {record.native_id: record.metadata for record in records} == source
    assert {record.source_path for record in records} == {
        path.relative_to(root).as_posix() for path in paths
    }
    assert all(
        record.derived["index_freshness"] == "upstream_source_validation_required"
        for record in records
    )
    assert all(path.read_bytes() == data for path, data in before.items())
