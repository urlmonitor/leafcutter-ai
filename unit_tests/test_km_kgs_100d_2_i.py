"""
MODULE: test_km_kgs_100d_2_i
GOAL: Prove KM-KGS-100d-2-i -- "a relationship pointing at a missing target
      is dropped, not rendered as a dead end" -- which was work_status: done
      but had no test, no test_spec and no '# covers:' tag anywhere in the
      repo (phantom-done, caught by check-done-proof).
BUSINESS CONTEXT: The behaviour already holds under the path-keyed
    file-node code now in place, so these tests are expected to PASS
    against the current implementation; this file only supplies the missing
    proof. Built through a byte copy of the real config/paths.json and the
    public build_knowledge_map()/shipped CLI -- never a hand-built edge
    dict. The drop happens in knowledge_query._filter_dangling_edges(),
    which runs INSIDE _collect_all_ex() before validate_edges_integrity()
    is ever called, so the dropped edge never reaches
    EdgeIntegrityResult.dropped_edges -- these tests therefore assert at
    the public level (the built map and the JSON export), not on
    dropped_edges, per the documented architecture note in
    _filter_dangling_edges' own docstring.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"
_KNOWLEDGE_QUERY_SCRIPT = _SCRIPTS_DIR / "knowledge_query.py"

sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map  # noqa: E402


def _build_dangling_target_project(tmp_path):
    """Two dangling-target scenarios (acs depends_on, docs related_docs) plus
    a contrast case: implemented_by naming a missing FILE is kept, not
    dropped (KM-KGS-100d-4-ii), so the two behaviours don't blur together.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-020.yaml").write_text(
        "id: KM-EX-020\n"
        "title: Depends on a missing criterion\n"
        "depends_on:\n"
        "- KM-EX-999\n"
        "components:\n"
        "- build-pipeline\n",
        encoding="utf-8",
    )
    (acs_dir / "KM-EX-021.yaml").write_text(
        "id: KM-EX-021\n"
        "title: Names a missing FILE, not a missing id (contrast case)\n"
        "implemented_by:\n"
        "- scripts/does_not_exist_030.py\n",
        encoding="utf-8",
    )

    (tmp_path / "docs" / "some-doc.md").write_text(
        "---\n"
        "id: SOME-DOC\n"
        "title: Some doc\n"
        "related_docs:\n"
        "  - NONEXISTENT-DOC-STEM\n"
        "components:\n"
        "  - build-pipeline\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )

    return tmp_path, config_dir / "paths.json"


def _run_cli_json(project_root):
    result = subprocess.run(
        [
            sys.executable,
            str(_KNOWLEDGE_QUERY_SCRIPT),
            "--format",
            "json",
            "--project-root",
            str(project_root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    return json.loads(result.stdout)


def test_acs_depends_on_to_missing_criterion_is_dropped_and_other_edges_survive(tmp_path):
    # covers: KM-KGS-100d-2-i
    # angle: criterion
    """A depends_on naming an id with no node: the edge is dropped, no node created, other edges survive."""
    project_root, paths_json = _build_dangling_target_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    dangling = [e for e in km.edges if e.source_id == "KM-EX-020" and e.target_id == "KM-EX-999"]
    assert dangling == [], "the depends_on edge to a non-existent id must not survive"
    assert "KM-EX-999" not in {n.id for n in km.nodes}, (
        "no node may be created just because an edge named this id"
    )
    assert any(
        e.source_id == "KM-EX-020" and e.edge_type == "component_membership" and e.target_id == "build-pipeline"
        for e in km.edges
    ), "KM-EX-020's other edge (component_membership) must still be present"


def test_docs_related_docs_to_missing_doc_is_dropped_and_other_edges_survive(tmp_path):
    # covers: KM-KGS-100d-2-i
    # angle: criterion
    """The same drop holds for a non-acs surface/field: docs' related_docs."""
    project_root, paths_json = _build_dangling_target_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    dangling = [
        e for e in km.edges if e.source_id == "SOME-DOC" and e.target_id == "NONEXISTENT-DOC-STEM"
    ]
    assert dangling == [], "the related_docs edge to a non-existent doc stem must not survive"
    assert "NONEXISTENT-DOC-STEM" not in {n.id for n in km.nodes}
    assert any(
        e.source_id == "SOME-DOC" and e.edge_type == "component_membership" and e.target_id == "build-pipeline"
        for e in km.edges
    ), "SOME-DOC's other edge (component_membership) must still be present"


def test_dropped_edges_absent_from_json_export_and_no_phantom_nodes(tmp_path):
    # covers: KM-KGS-100d-2-i
    # angle: reachability
    """The shipped CLI's JSON export never renders the dangling relationship as a dead end."""
    project_root, _ = _build_dangling_target_project(tmp_path)
    payload = _run_cli_json(project_root)

    node_ids = {n["id"] for n in payload["nodes"]}
    assert "KM-EX-999" not in node_ids
    assert "NONEXISTENT-DOC-STEM" not in node_ids
    for edge in payload["edges"]:
        assert edge["target"] not in ("KM-EX-999", "NONEXISTENT-DOC-STEM"), (
            f"no edge may target a missing id in the export: {edge}"
        )
        assert edge["target"] in node_ids, (
            f"every exported edge target must be a real node id (never a dead end): {edge}"
        )


def test_build_exits_zero_despite_dangling_targets(tmp_path):
    # covers: KM-KGS-100d-2-i
    # angle: failure
    """The build never fails solely because a relationship named a missing target."""
    project_root, _ = _build_dangling_target_project(tmp_path)
    payload = _run_cli_json(project_root)
    assert payload["nodes"] and payload["edges"] is not None


def test_missing_file_path_value_is_kept_not_dropped_contrast_case(tmp_path):
    # covers: KM-KGS-100d-2-i
    # angle: boundary
    """Contrast: a file-path value naming a missing FILE is NOT dropped -- it becomes
    a 'files' node marked missing (KM-KGS-100d-4-ii), so the two behaviours never blur."""
    project_root, paths_json = _build_dangling_target_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    kept = [
        e for e in km.edges
        if e.source_id == "KM-EX-021" and e.target_id == "scripts/does_not_exist_030.py"
    ]
    assert len(kept) == 1, "a missing FILE's edge must be kept, unlike a missing id's edge"
    node_ids = {n.id: n for n in km.nodes}
    assert "scripts/does_not_exist_030.py" in node_ids, "the missing file must become a real node"
    node = node_ids["scripts/does_not_exist_030.py"]
    assert node.surface == "files"
    assert node.missing is True


def test_dropping_is_deterministic_across_repeated_builds(tmp_path):
    # covers: KM-KGS-100d-2-i
    # angle: boundary
    """The same inputs yield the same validated edge set on every run."""
    project_root, paths_json = _build_dangling_target_project(tmp_path)
    km1 = build_knowledge_map(project_root, paths_json)
    km2 = build_knowledge_map(project_root, paths_json)
    assert set(km1.edges) == set(km2.edges)
    assert {n.id for n in km1.nodes} == {n.id for n in km2.nodes}


def test_real_repository_every_edge_endpoint_is_a_node():
    # covers: KM-KGS-100d-2-i
    # angle: real_artifact
    """Real repository: every edge's source and target are real node ids -- never a dead end."""
    assert _REPO_ROOT.exists(), f"repo root must exist: {_REPO_ROOT}"
    payload = _run_cli_json(_REPO_ROOT)
    node_ids = {n["id"] for n in payload["nodes"]}
    assert len(payload["edges"]) > 0, "expected a non-empty edge set (result must not be vacuous)"
    offending = [
        e for e in payload["edges"] if e["source"] not in node_ids or e["target"] not in node_ids
    ]
    assert offending == [], (
        f"every edge must have both endpoints as real node ids; offending: {offending[:5]}"
    )
