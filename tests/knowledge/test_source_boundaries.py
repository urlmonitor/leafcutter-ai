"""Regression requirements for canonical validation and exact source locators."""

import asyncio
import subprocess

import pytest
import yaml

from tests.knowledge.test_projection import commit
from tests.knowledge import test_projection

repository = test_projection.repository


@pytest.mark.parametrize(
    "failure", [OSError("sensitive detail"), subprocess.TimeoutExpired("sensitive detail", 1)]
)
def test_git_process_failure_is_contextual_without_raw_error(monkeypatch, tmp_path, failure):
    # covers: KM-400b-2
    # angle: failure
    from knowledge.adapters import git_source

    def unavailable(*args, **kwargs):
        raise failure

    monkeypatch.setattr(git_source.subprocess, "run", unavailable)
    with pytest.raises(ValueError, match="Git source process could not complete") as raised:
        git_source.git(tmp_path, "status")
    assert "sensitive detail" not in str(raised.value)


def test_noncanonical_ac_documents_do_not_collide_and_keep_file_references(repository):
    # covers: KM-400a-1
    # covers: KM-400b-2
    # angle: real_artifact
    from knowledge.projection.canonical_loader import load_snapshot

    root, _ = repository
    for directory in ("one", "two"):
        folder = root / "docs/acs" / directory
        folder.mkdir()
        (folder / "PROJECT_CONTEXT.md").write_text("# Context\nNoncanonical guidance\n")
    criterion = root / "docs/acs/criterion.yaml"
    data = yaml.safe_load(criterion.read_text())
    data["covered_by"] = ["docs/acs/one/PROJECT_CONTEXT.md"]
    criterion.write_text(yaml.safe_dump(data))
    from scripts.knowledge_query import build_knowledge_map

    unfiltered = build_knowledge_map(root, root / "config/paths.json")
    assert sum(node.id == "PROJECT_CONTEXT" for node in unfiltered.nodes) == 2
    snapshot = load_snapshot(root, "repo", commit(root))
    acs = [node for node in snapshot.nodes if node.kind == "AcceptanceCriterion"]
    assert [node.canonical_id for node in acs] == ["KM-FIX-1"]
    document = next(
        node for node in snapshot.nodes if node.canonical_id == "docs/acs/one/PROJECT_CONTEXT.md"
    )
    assert document.kind == "SourceFile"
    assert document.source.path == "docs/acs/one/PROJECT_CONTEXT.md"
    assert any(edge.target_id == document.canonical_id for edge in snapshot.edges)
    assert "excluded_noncanonical_ac_documents:2" in snapshot.diagnostics


def test_implementation_file_links_preserve_canonical_component_and_ac_targets(repository):
    # covers: KM-400a-1
    # angle: real_artifact
    import json
    from knowledge.projection.canonical_loader import load_snapshot
    from knowledge.projection.validation import validate_snapshot

    root, _ = repository
    config_path = root / "config/paths.json"
    config = json.loads(config_path.read_text())
    config["surfaces"]["components"]["path"] = "docs/components/"
    config["surfaces"]["acs"]["edge_fields"].append("implemented_by")
    config["surfaces"]["acs"]["file_path_fields"].append("implemented_by")
    config_path.write_text(json.dumps(config))
    folder = root / "docs/components"
    folder.mkdir()
    (folder / "component.md").write_text("---\nid: component-doc\ntitle: Component\n---\n")
    criterion = root / "docs/acs/criterion.yaml"
    data = yaml.safe_load(criterion.read_text())
    target = {**data, "id": "KM-FIX-2"}
    (criterion.parent / "target.yaml").write_text(yaml.safe_dump(target))
    data["implemented_by"] = ["docs/components/component.md", "docs/acs/target.yaml"]
    criterion.write_text(yaml.safe_dump(data))
    snapshot = load_snapshot(root, "repo", commit(root))
    links = [edge for edge in snapshot.edges if edge.edge_type == "implemented_by"]
    assert {edge.target_id for edge in links} == {"component-doc", "KM-FIX-2"}
    component_link = next(edge for edge in links if edge.target_id == "component-doc")
    component_link.source_id, component_link.target_id = (
        component_link.target_id,
        component_link.source_id,
    )
    with pytest.raises(ValueError, match="endpoint kinds"):
        validate_snapshot(snapshot)


def test_valid_yaml_missing_criteria_is_rejected(repository):
    # covers: KM-400b-2
    # angle: criterion
    root, _ = repository
    path = root / "docs/acs/criterion.yaml"
    value = yaml.safe_load(path.read_text())
    del value["criteria"]
    path.write_text(yaml.safe_dump(value))
    from knowledge.projection.canonical_loader import load_snapshot

    with pytest.raises(ValueError, match="criteria"):
        load_snapshot(root, "repo", commit(root))


def test_yaml_pointer_reads_exact_criterion_not_file_header(repository):
    # covers: KM-400d-2
    # angle: criterion
    root, sha = repository
    from knowledge.adapters.git_source import GitSourceResolver
    from knowledge.contracts import SourceReference

    ref = SourceReference(
        repository_id="repo", source_sha=sha, path="docs/acs/criterion.yaml", locator="/criteria"
    )
    text = asyncio.run(GitSourceResolver(root).read(ref, 4096))
    assert "Then its identity is preserved" in text
    assert "Original title" not in text
    with pytest.raises(ValueError, match="locator"):
        asyncio.run(
            GitSourceResolver(root).read(ref.model_copy(update={"locator": "/unknown"}), 4096)
        )


def test_snapshot_rejects_unknown_types_and_unreviewed_memory():
    # covers: KM-400a-1
    # covers: KM-400c-1
    # angle: criterion
    from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference, Relation
    from knowledge.projection.validation import validate_snapshot

    source = SourceReference(repository_id="repo", source_sha="a" * 40, path="fixture.yaml")
    entity = Entity(canonical_id="x", kind="Invented", title="x", source=source)
    snap = ProjectionSnapshot(
        repository_id="repo", source_sha="a" * 40, generation_id="g", nodes=[entity]
    )
    with pytest.raises(ValueError, match="kind"):
        validate_snapshot(snap)
    entity.kind = "Decision"
    with pytest.raises(ValueError, match="synthetic"):
        validate_snapshot(snap)
    entity.properties["synthetic"] = True
    snap.edges = [Relation(source_id="x", target_id="x", edge_type="INVENTED")]
    with pytest.raises(ValueError, match="relationship"):
        validate_snapshot(snap)


def test_status_reports_requested_and_published_revision_lag(repository, monkeypatch):
    # covers: KM-400e-5
    # angle: criterion
    from types import SimpleNamespace
    from knowledge import cli_sync
    from knowledge.contracts import ProjectionSnapshot

    root, sha = repository

    class Backend:
        async def active(self, repository_id):
            return ProjectionSnapshot(
                repository_id=repository_id, source_sha="a" * 40, generation_id="g"
            )

        async def close(self):
            pass

    monkeypatch.setattr(cli_sync, "writer_backend", lambda root=None: Backend())
    result = asyncio.run(
        cli_sync.run(
            SimpleNamespace(command="status", root=root, repository_id="repo", revision=sha)
        )
    )
    assert result["status"] == "stale"
    assert (
        result["requested_sha"] == sha
        and result["published_sha"] == "a" * 40
        and result["lagging"] is True
    )


def test_component_hub_cites_registry_record_not_directory(repository):
    # covers: KM-400a-1
    # covers: KM-400d-2
    # angle: real_artifact
    from knowledge.projection.canonical_loader import load_snapshot
    from knowledge.adapters.git_source import GitSourceResolver

    root, sha = repository
    snapshot = load_snapshot(root, "repo", sha)
    hub = next(node for node in snapshot.nodes if node.canonical_id == "knowledge_management")
    assert hub.source.path == "docs/components.json"
    assert hub.source.locator == "/components/knowledge_management"
    assert "Knowledge" in asyncio.run(GitSourceResolver(root).read(hub.source, 4096))
