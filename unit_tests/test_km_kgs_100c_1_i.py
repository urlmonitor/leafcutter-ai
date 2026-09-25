"""
MODULE: test_km_kgs_100c_1_i
GOAL: TDD stubs for KM-KGS-100c-1-i -- a declared surface counts as
      contributing only when items were read from its own path; a
      component-hub node sharing the "components" label must not make an
      empty "components" surface look like it contributed.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100c-1-i.yaml.
    build_knowledge_map today computes contributing_surfaces purely from
    node.surface labels, so the ~40 component-hub nodes (labelled
    "components") can stand in for a real read from the "components"
    surface's own path even when that path produced nothing. These tests
    build a temp project where that gap is directly observable: the empty-
    components fixture (a hub exists, the surface's own path is empty).

ASSUMED API NAMES (see the test-writer's report for the full contract):
  - knowledge_query.check_surface_set(km, project_root, paths_json) ->
    list[str]: failure messages. A "not contributing" failure reads
    "declared surface '<name>' has an existing path but contributed no
    items"; empty list means the check passed.
  - knowledge_query.SYNTHETIC_SURFACE_LABELS: frozenset[str] -- exercised
    in KM-KGS-100c-1-ii's own test file, not here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from km_kgs_100c_1_shared import (
    NOT_CONTRIBUTING_RE,
    REAL_PATHS_JSON,
    REPO_ROOT,
    SCRIPTS_DIR,
    add_one_component_document,
    build_empty_components_fixture,
)

sys.path.insert(0, str(SCRIPTS_DIR))

from knowledge_query import build_knowledge_map, load_surfaces_with_meta  # noqa: E402


def test_component_hubs_do_not_make_an_empty_components_surface_contribute(tmp_path):
    # covers: KM-KGS-100c-1-i
    # angle: criterion
    """A hub node labelled 'components' survives, but an empty components/
    directory must not count as that surface contributing."""
    project_root = build_empty_components_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"

    km = build_knowledge_map(project_root, paths_json)

    assert "tickets" in km.contributing_surfaces
    assert "components" not in km.contributing_surfaces, (
        "the 'components' surface must not be counted as contributing when "
        "only a synthetic hub node carries that label"
    )

    hub_nodes = [n for n in km.nodes if n.id == "build-pipeline" and n.surface == "components"]
    assert hub_nodes, "the component hub node must still be on the map"

    membership_edges = [
        e
        for e in km.edges
        if e.source_id == "T-1"
        and e.edge_type == "component_membership"
        and e.target_id == "build-pipeline"
    ]
    assert membership_edges, "the component_membership edge from T-1 must still end on the hub"


def test_surface_set_check_names_components_as_existing_path_with_nothing_read(tmp_path):
    # covers: KM-KGS-100c-1-i
    # angle: criterion
    """The surface-set check's failure set is exactly {'components'}: tickets
    and docs contributed, and every other declared surface's path is absent
    from this fixture so the parent's 'whose path exists' clause excludes
    them from the comparison entirely."""
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    project_root = build_empty_components_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    km = build_knowledge_map(project_root, paths_json)

    failures = check_surface_set(km, project_root, paths_json)
    assert failures, "the check must report a failure for the empty components surface"

    not_contributing = {m.group(1) for m in (NOT_CONTRIBUTING_RE.search(f) for f in failures) if m}
    assert not_contributing == {"components"}, (
        f"expected exactly {{'components'}} to be reported as declared-path-"
        f"exists-but-nothing-read; got {not_contributing} from {failures}"
    )
    assert any("components" in f for f in failures)


def test_one_component_document_makes_components_contribute_and_check_pass(tmp_path):
    # covers: KM-KGS-100c-1-i
    # angle: criterion
    """Adding one real component document (the criteria's rebuild) makes
    'components' contribute and clears the surface-set check."""
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    project_root = build_empty_components_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    add_one_component_document(project_root)

    km = build_knowledge_map(project_root, paths_json)
    assert "components" in km.contributing_surfaces

    failures = check_surface_set(km, project_root, paths_json)
    assert failures == [], f"the check must pass once components has a real item: {failures}"


def test_real_repository_contribution_is_proven_by_an_item_read_from_the_surface_path(capsys):
    # covers: KM-KGS-100c-1-i
    # angle: real_artifact
    """On the real repository, every contributing surface is backed by a
    node whose path lies inside that surface's own declared path -- never
    by a hub alone -- and a missing repo root/paths.json fails naming the
    path (no pytest.skip)."""
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    km = build_knowledge_map(REPO_ROOT, REAL_PATHS_JSON)
    failures = check_surface_set(km, REPO_ROOT, REAL_PATHS_JSON)
    assert failures == [], f"the real repository must pass the surface-set check: {failures}"

    surfaces_meta = load_surfaces_with_meta(REPO_ROOT, REAL_PATHS_JSON)
    for surface in km.contributing_surfaces:
        declared_path = surfaces_meta[surface]["path"]
        matching = [
            n
            for n in km.nodes
            if n.surface == surface
            and (n.path == declared_path or declared_path in n.path.parents)
        ]
        assert matching, (
            f"surface {surface!r} is in contributing_surfaces but no node's "
            f"path lies inside its declared path {declared_path}"
        )

    missing_root = Path("/definitely/not/a/real/leafcutter/path/xyz123")
    with pytest.raises(SystemExit):
        build_knowledge_map(missing_root, missing_root / "config" / "paths.json")
    captured = capsys.readouterr()
    assert str(missing_root / "config" / "paths.json") in captured.err
