"""
MODULE: test_km_kgs_100c_1_ii
GOAL: TDD stubs for KM-KGS-100c-1-ii -- a node on a surface that is neither
      declared nor one of the map's named synthetic surfaces fails the
      surface-set check, naming the label and the node.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100c-1-ii.yaml.
    build_knowledge_map today only adds a label to contributing_surfaces
    when it is already in the declared set, so an undeclared/stray label
    never enters that set and never fails today's subset check -- it is
    true by construction. No real reader emits a stray label, so the
    failing case is built by wrapping the REAL builder's output
    (km._replace) and appending one node, after first asserting the real
    builder produced every other expected node.

ASSUMED API NAMES (see the test-writer's report for the full contract):
  - knowledge_query.check_surface_set(km, project_root, paths_json) ->
    list[str]: failure messages. A "stray label" failure reads "node
    '<id>' has surface label '<label>', which is neither a declared
    surface nor a synthetic surface label".
  - knowledge_query.SYNTHETIC_SURFACE_LABELS: frozenset[str], expected to
    equal exactly {'components', 'files'}.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from km_kgs_100c_1_shared import (
    REAL_PATHS_JSON,
    REPO_ROOT,
    SCRIPTS_DIR,
    STRAY_LABEL_RE,
    add_extra_directory_surfaces,
    build_stray_label_fixture,
)

sys.path.insert(0, str(SCRIPTS_DIR))

from knowledge_query import NodeRecord, build_knowledge_map  # noqa: E402


def _make_stray_node(node_id: str, surface: str) -> NodeRecord:
    return NodeRecord(id=node_id, surface=surface, title=node_id, description="", path=Path("nowhere"))


def test_stray_label_fails_the_check_naming_label_and_node(tmp_path):
    # covers: KM-KGS-100c-1-ii
    # angle: criterion
    """PRECONDITION: the real builder alone produces python-coder, T-1,
    build-pipeline and scripts/foo.py. The stray is then injected by
    wrapping that real output; no real reader emits a stray label."""
    project_root = build_stray_label_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    km = build_knowledge_map(project_root, paths_json)

    ids_by_surface = {(n.id, n.surface) for n in km.nodes}
    assert ("python-coder", "agents") in ids_by_surface
    assert ("T-1", "tickets") in ids_by_surface
    assert ("build-pipeline", "components") in ids_by_surface
    assert ("scripts/foo.py", "files") in ids_by_surface

    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    wrapped = km._replace(nodes=km.nodes + [_make_stray_node("stray-1", "gizmos")])
    failures = check_surface_set(wrapped, project_root, paths_json)
    text = "\n".join(failures)
    assert "gizmos" in text
    assert "stray-1" in text


def test_components_and_files_labels_raise_no_failure_and_removing_stray_passes(tmp_path):
    # covers: KM-KGS-100c-1-ii
    # angle: criterion
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    project_root = build_stray_label_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    km = build_knowledge_map(project_root, paths_json)
    wrapped = km._replace(nodes=km.nodes + [_make_stray_node("stray-1", "gizmos")])

    failures = check_surface_set(wrapped, project_root, paths_json)
    offending_labels = {m.group(2) for m in (STRAY_LABEL_RE.search(f) for f in failures) if m}
    assert offending_labels == {"gizmos"}, (
        f"only 'gizmos' may be named as offending; got {offending_labels} from {failures}"
    )

    unwrapped_failures = check_surface_set(km, project_root, paths_json)
    assert unwrapped_failures == [], (
        f"the unwrapped real build must pass the check: {unwrapped_failures}"
    )


def test_synthetic_labels_are_one_named_collection_and_files_is_never_declared():
    # covers: KM-KGS-100c-1-ii
    # angle: seam
    from knowledge_query import SYNTHETIC_SURFACE_LABELS  # local: not yet defined

    assert SYNTHETIC_SURFACE_LABELS == frozenset({"components", "files"})

    real_config = json.loads(REAL_PATHS_JSON.read_text(encoding="utf-8"))
    assert "files" not in real_config["surfaces"], (
        "'files' must never be declared in config/paths.json -- it is a "
        "synthetic, never-traversed label"
    )


def test_check_reads_declared_labels_from_configuration_not_from_code(tmp_path):
    # covers: KM-KGS-100c-1-ii
    # angle: boundary
    """Two configs differ only by a fictional 'widgets' surface; only the
    configuration flips the verdict, proving no surface name is hard-coded."""
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    project_a = build_stray_label_fixture(tmp_path / "a")
    add_extra_directory_surfaces(project_a, ["widgets"])
    paths_a = project_a / "config" / "paths.json"
    km_a = build_knowledge_map(project_a, paths_a)
    failures_a = check_surface_set(km_a, project_a, paths_a)
    assert not any("widgets" in f for f in failures_a), (
        f"a real widgets surface must not be flagged once it is declared: {failures_a}"
    )

    project_b = build_stray_label_fixture(tmp_path / "b")
    paths_b = project_b / "config" / "paths.json"
    km_b = build_knowledge_map(project_b, paths_b)
    wrapped_b = km_b._replace(nodes=km_b.nodes + [_make_stray_node("widget-1", "widgets")])
    failures_b = check_surface_set(wrapped_b, project_b, paths_b)
    assert any("widgets" in f for f in failures_b), (
        f"an undeclared widgets label must be flagged when the config doesn't declare it: {failures_b}"
    )


def test_restricted_build_limits_declared_set_to_the_filtered_surface(tmp_path):
    # covers: KM-KGS-100c-1-ii
    # angle: boundary
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    project_root = build_stray_label_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    km = build_knowledge_map(project_root, paths_json, surface_filter="tickets")

    assert km.declared_surfaces == frozenset({"tickets"})

    failures = check_surface_set(km, project_root, paths_json)
    assert failures == [], f"a restricted map with only synthetic/declared labels must pass: {failures}"

    wrapped = km._replace(nodes=km.nodes + [_make_stray_node("agent-stray", "agents")])
    failures_wrapped = check_surface_set(wrapped, project_root, paths_json)
    text = "\n".join(failures_wrapped)
    assert "agents" in text
    assert "agent-stray" in text


def test_real_repository_passes_and_an_injected_stray_fails(capsys):
    # covers: KM-KGS-100c-1-ii
    # angle: real_artifact
    from knowledge_query import (  # local: not yet defined at collection time
        SYNTHETIC_SURFACE_LABELS,
        check_surface_set,
    )

    for kwargs in ({}, {"surface_filter": "acs"}):
        km = build_knowledge_map(REPO_ROOT, REAL_PATHS_JSON, **kwargs)
        failures = check_surface_set(km, REPO_ROOT, REAL_PATHS_JSON)
        assert failures == [], f"real repo build {kwargs} must pass the check: {failures}"
        allowed = km.declared_surfaces | SYNTHETIC_SURFACE_LABELS
        stray_nodes = [n for n in km.nodes if n.surface not in allowed]
        assert not stray_nodes, f"unexpected stray-labelled nodes: {stray_nodes}"

    km_unrestricted = build_knowledge_map(REPO_ROOT, REAL_PATHS_JSON)
    wrapped = km_unrestricted._replace(
        nodes=km_unrestricted.nodes + [_make_stray_node("stray-1", "gizmos")]
    )
    failures = check_surface_set(wrapped, REPO_ROOT, REAL_PATHS_JSON)
    text = "\n".join(failures)
    assert "gizmos" in text
    assert "stray-1" in text

    missing_root = Path("/definitely/not/a/real/leafcutter/path/xyz123")
    with pytest.raises(SystemExit):
        build_knowledge_map(missing_root, missing_root / "config" / "paths.json")
    captured = capsys.readouterr()
    assert str(missing_root / "config" / "paths.json") in captured.err
