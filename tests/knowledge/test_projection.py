"""Immutable source projection integration at the real Git boundary."""

import asyncio
import importlib
import json
import subprocess

import pytest
import yaml


def git(root, *args, input=None):
    return subprocess.run(
        ["git", "-C", str(root), *args], input=input, text=True, capture_output=True, check=True
    ).stdout.strip()


def commit(root):
    git(root, "add", ".")
    tree = git(root, "write-tree")
    sha = git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit-tree",
        tree,
        input="synthetic test fixture\n",
    )
    git(root, "update-ref", "refs/heads/main", sha)
    return sha


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "config").mkdir()
    (tmp_path / "docs/acs").mkdir(parents=True)
    surfaces = {
        "acs": {
            "path": "docs/acs/",
            "edge_fields": ["components", "depends_on", "covered_by"],
            "file_path_fields": ["covered_by"],
        },
        "components": {"path": "docs/components.json", "edge_fields": []},
    }
    (tmp_path / "config/paths.json").write_text(
        json.dumps({"surfaces": surfaces}), encoding="utf-8"
    )
    (tmp_path / "docs/components.json").write_text(
        json.dumps({"components": {"knowledge_management": {"name": "Knowledge"}}}),
        encoding="utf-8",
    )
    (tmp_path / "docs/acs/criterion.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "KM-FIX-1",
                "title": "Original title",
                "component": "knowledge-management",
                "status": "active",
                "readiness": "approved",
                "priority": "medium",
                "criteria": "Given a snapshot\nWhen indexed\nThen its identity is preserved",
                "components": ["knowledge_management"],
                "depends_on": [],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path, commit(tmp_path)


def test_projection_reads_commit_not_dirty_checkout_and_reuses_identity(repository):
    # covers: KM-400a-1
    # covers: KM-400b-1
    # angle: real_artifact
    loader = importlib.import_module("knowledge.projection.canonical_loader")
    root, sha = repository
    (root / "docs/acs/criterion.yaml").write_text("id: malicious-dirty\n", encoding="utf-8")
    first = loader.load_snapshot(root, "repo", sha)
    second = loader.load_snapshot(root, "repo", sha)
    ac = next(n for n in first.nodes if n.canonical_id == "KM-FIX-1")
    assert ac.title == "Original title" and ac.source.source_sha == sha
    assert ac.source.path == "docs/acs/criterion.yaml"
    assert first.generation_id == second.generation_id
    assert any(
        e.source_id == "KM-FIX-1" and e.edge_type == "component_membership" for e in first.edges
    )


def test_duplicate_canonical_id_rejects_snapshot(repository):
    # covers: KM-400b-2
    # angle: failure
    loader = importlib.import_module("knowledge.projection.canonical_loader")
    root, _ = repository
    (root / "docs/acs/duplicate.yaml").write_bytes((root / "docs/acs/criterion.yaml").read_bytes())
    sha = commit(root)
    with pytest.raises(ValueError, match="duplicate"):
        loader.load_snapshot(root, "repo", sha)


def test_required_missing_reference_rejects_before_loader_drops_edge(repository):
    # covers: KM-400b-2
    # angle: failure
    loader = importlib.import_module("knowledge.projection.canonical_loader")
    root, _ = repository
    target = root / "docs/acs/criterion.yaml"
    data = yaml.safe_load(target.read_text())
    data["depends_on"] = ["KM-DOES-NOT-EXIST"]
    target.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="KM-DOES-NOT-EXIST"):
        loader.load_snapshot(root, "repo", commit(root))


def test_rename_keeps_id_and_deleted_entity_disappears(repository):
    # angle: real_artifact
    # covers: KM-400b-4
    # angle: criterion
    loader = importlib.import_module("knowledge.projection.canonical_loader")
    root, sha = repository
    old = loader.load_snapshot(root, "repo", sha)
    path = root / "docs/acs/criterion.yaml"
    path.rename(path.with_name("renamed.yaml"))
    renamed = loader.load_snapshot(root, "repo", commit(root))
    assert next(n for n in renamed.nodes if n.canonical_id == "KM-FIX-1").source.path.endswith(
        "renamed.yaml"
    )
    path.with_name("renamed.yaml").unlink()
    removed = loader.load_snapshot(root, "repo", commit(root))
    assert "KM-FIX-1" not in {n.canonical_id for n in removed.nodes}
    assert "KM-FIX-1" in {n.canonical_id for n in old.nodes}


def test_git_source_resolver_uses_sha_and_blocks_traversal(repository):
    # covers: KM-400d-2
    # angle: failure
    c = importlib.import_module("knowledge.contracts")
    resolver = importlib.import_module("knowledge.adapters.git_source")
    root, sha = repository
    (root / "docs/acs/criterion.yaml").write_text("dirty", encoding="utf-8")
    source = c.SourceReference(repository_id="repo", source_sha=sha, path="docs/acs/criterion.yaml")
    text = asyncio.run(resolver.GitSourceResolver(root).read(source, 4096))
    assert "Original title" in text and "dirty" not in text
    with pytest.raises(ValueError):
        bad = source.model_copy(update={"path": "../outside"})
        asyncio.run(resolver.GitSourceResolver(root).read(bad, 4096))
