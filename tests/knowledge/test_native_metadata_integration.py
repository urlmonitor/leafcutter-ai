"""Cross-type mapping behavior and publication readback boundaries, KM-400a-3-i."""

from datetime import date

import pytest

from knowledge.adapters.domain_schema import display_properties
from knowledge.adapters.native_verification import verify_rows
from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference
from knowledge.native_properties import decode
from knowledge.native_types.common import NativeRecord
from knowledge.projection import native_metadata


def _entity(identifier, kind="AcceptanceCriterion"):
    return Entity(
        canonical_id=identifier,
        kind=kind,
        title="Original caption",
        summary="Original summary",
        source=SourceReference(repository_id="repo", source_sha="a" * 40, path="record.yaml"),
    )


def test_authored_and_derived_fields_survive_payload_and_physical_projection():
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: seam
    raw = {
        "id": "author-id",
        "title": "Author title",
        "created": date(2026, 6, 5),
        "criteria": "Full exact criteria",
        "test_spec": [{"name": "A", "requires_db": True}],
        "components": ["finalize", "finalize"],
        "_native_derived/derived/template": "Authored collision",
    }
    derived = {"template_frontmatter": {"name": "Different template", "created": date(2026, 6, 6)}}
    original = _entity("AC-1")
    value = native_metadata.apply_record(
        original, NativeRecord("AcceptanceCriterion", "AC-1", "record.yaml", raw, derived=derived)
    )
    retained = Entity.model_validate_json(value.model_dump_json())
    props = display_properties(retained, ["finalize"])
    assert decode(props) == raw
    assert decode({**props, "_native_shape": props["_native_derived_shape"]}) == {
        "derived": derived
    }
    assert props["criteria"] == raw["criteria"]
    assert props["components"] == ["finalize"]
    assert props["/components"] == ["finalize", "finalize"]
    assert value.canonical_id == original.canonical_id and value.source == original.source
    assert value.title == original.title and value.summary == original.summary
    assert not original.properties


def test_distinct_native_types_keep_colliding_names_and_explicit_memberships(tmp_path, monkeypatch):
    # covers: KM-400a-1-iv
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # angle: seam
    (tmp_path / "record.yaml").write_text("source")
    records = [
        NativeRecord(
            kind,
            "same",
            "record.yaml",
            {"name": "same", "components": ["finalize", "finalize", "unknown"]},
        )
        for kind in ("Agent", "Skill")
    ]
    monkeypatch.setattr(native_metadata, "collect", lambda *args, **kwargs: records)
    snapshot = ProjectionSnapshot(
        repository_id="repo",
        source_sha="a" * 40,
        generation_id="one",
        nodes=[_entity("same", "SourceFile"), _entity("finalize", "Component")],
    )
    result = native_metadata.enrich(snapshot, tmp_path)
    assert {node.canonical_id for node in result.nodes} == {
        "same",
        "finalize",
        "Agent:same",
        "Skill:same",
    }
    assert {(edge.source_id, edge.target_id) for edge in result.edges} == {
        ("Agent:same", "finalize"),
        ("Skill:same", "finalize"),
    }
    assert len(snapshot.nodes) == 2 and snapshot.edges == []


@pytest.mark.parametrize(
    "actual",
    [
        [],
        [{"key": "other", "props": {"key": "other", "priority": "high"}}],
        [{"key": "one", "props": {"key": "one", "priority": "low"}}],
        [{"key": "one", "props": {"key": "one"}}],
    ],
)
def test_property_readback_rejects_missing_or_changed_data(actual):
    # covers: KM-400a-3-i
    # angle: failure
    with pytest.raises(ValueError, match="readback"):
        verify_rows([{"key": "one", "priority": "high"}], actual)


def test_native_record_flag_cannot_bypass_decision_approval():
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # angle: seam
    from knowledge.projection.validation import validate_snapshot
    from tests.knowledge.test_native_decision import _minimal

    raw = _minimal()
    raw["approval"]["approval_status"] = "proposed"
    entity = _entity("Decision:" + raw["id"], "Decision")
    entity.properties["native_record"] = True
    entity = native_metadata.apply_record(
        entity, NativeRecord("Decision", raw["id"], "record.yaml", raw)
    )
    snapshot = ProjectionSnapshot(
        repository_id="repo", source_sha="a" * 40, generation_id="one", nodes=[entity]
    )
    with pytest.raises(ValueError, match="[Dd]ecision"):
        validate_snapshot(snapshot)


def test_scoped_native_import_keeps_declared_component_filter_and_reports_unresolved(
    tmp_path, monkeypatch
):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # angle: seam
    (tmp_path / "record.yaml").write_text("source")
    raw = {"components": ["finalize", "finalize"]}
    monkeypatch.setattr(
        native_metadata,
        "collect",
        lambda *a, **kw: [NativeRecord("Document", "document", "record.yaml", raw)],
    )
    snapshot = ProjectionSnapshot(repository_id="repo", source_sha="a" * 40, generation_id="one")
    result = native_metadata.enrich(snapshot, tmp_path)
    props = display_properties(result.nodes[0], [])
    assert props["components"] == ["finalize"]
    assert props["/components"] == ["finalize", "finalize"]
    assert result.edges == []
    assert (
        "optional_unresolved:Document:document:component_membership:finalize" in result.diagnostics
    )


def test_reference_readers_reach_projection_without_refreshing_historical_evidence(
    tmp_path, monkeypatch
):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # angle: seam
    monkeypatch.setattr(native_metadata, "collect", lambda *a, **kw: [])
    nodes = [_entity("file", "SourceFile"), _entity("test", "Test")]
    for node in nodes:
        node.properties.update(missing=True, future={"nullable": None, "empty": []})
    snapshot = ProjectionSnapshot(
        repository_id="repo", source_sha="a" * 40, generation_id="one", nodes=nodes
    )
    result = native_metadata.enrich(snapshot, tmp_path)
    for original, node in zip(nodes, result.nodes):
        props = display_properties(node, [])
        assert decode(props) == original.model_dump(mode="python")
        assert node.source == original.source and node.canonical_id == original.canonical_id
        assert props["/properties/missing"] is True
    assert result.edges == []
    assert 'native_metadata_counts:{"SourceFile":1,"Test":1}' in result.diagnostics
