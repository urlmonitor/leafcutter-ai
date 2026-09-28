"""
MODULE: test_km_kgs_100c_1
GOAL: TDD stubs for KM-KGS-100c-1 -- every surface declared in the config is
      ingested, however many there are, proven by provenance rather than by
      a check that cannot fail.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100c-1.yaml.
    This L2's own promise was previously "proven" by
    contributing_surfaces == declared_surfaces, which is true by
    construction (KM-KGS-100c-1-ii) and can be satisfied by a synthetic
    hub node alone (KM-KGS-100c-1-i). These tests prove ingestion by
    provenance on the real repository, prove the count is derived from
    configuration alone (0/1/3 extra surfaces, no code change), prove
    optional-absent surfaces are skipped without aborting the build, and
    prove that omitting a surface from configuration stops it being read.
    The hub-masking case and the stray-label case themselves are
    KM-KGS-100c-1-i's and -ii's own tests and are NOT repeated here.

ASSUMED API NAMES (see the test-writer's report for the full contract):
  - knowledge_query.check_surface_set(km, project_root, paths_json) ->
    list[str]: failure messages, empty when the map is fully accounted
    for. Exercised here on the real repository and on the reused
    stray-label fixture; the exact message format is pinned in
    KM-KGS-100c-1-i's and -ii's own test files.
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
    add_extra_directory_surfaces,
    build_stray_label_fixture,
    remove_surface_from_config,
    select_solo_file_surface,
)

sys.path.insert(0, str(SCRIPTS_DIR))

from knowledge_query import build_knowledge_map, load_surfaces_with_meta  # noqa: E402


def test_real_repository_every_existing_path_declared_surface_contributes_by_provenance(capsys):
    # covers: KM-KGS-100c-1
    # angle: real_artifact
    """The expected set is computed from configuration -- every declared
    surface whose path exists -- and must equal contributing_surfaces; each
    member must be backed by a node whose path is really inside that
    surface's own declared path. A missing repo root/paths.json fails
    naming the path (no pytest.skip)."""
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    km = build_knowledge_map(REPO_ROOT, REAL_PATHS_JSON)
    surfaces_meta = load_surfaces_with_meta(REPO_ROOT, REAL_PATHS_JSON)
    expected = {name for name, info in surfaces_meta.items() if info["path"].exists()}

    assert km.contributing_surfaces == expected, (
        f"contributing_surfaces must equal every declared surface whose path "
        f"exists ({len(expected)} surfaces): expected={sorted(expected)}, "
        f"got={sorted(km.contributing_surfaces)}"
    )

    failures = check_surface_set(km, REPO_ROOT, REAL_PATHS_JSON)
    assert failures == [], f"the real repository must pass the surface-set check: {failures}"

    for surface in expected:
        declared_path = surfaces_meta[surface]["path"]
        matching = [
            n
            for n in km.nodes
            if n.surface == surface
            and (n.path == declared_path or declared_path in n.path.parents)
        ]
        assert matching, f"surface {surface!r} has no node whose path is its own declared path"

    missing_root = Path("/definitely/not/a/real/leafcutter/path/xyz123")
    with pytest.raises(SystemExit):
        build_knowledge_map(missing_root, missing_root / "config" / "paths.json")
    captured = capsys.readouterr()
    assert str(missing_root / "config" / "paths.json") in captured.err


@pytest.mark.parametrize("extra_count", [0, 1, 3])
def test_every_declared_surface_is_ingested_whatever_the_surface_count(tmp_path, extra_count):
    # covers: KM-KGS-100c-1
    # angle: criterion
    """The stray-label fixture, reused (not rebuilt), with N fictional extra
    directory surfaces added programmatically. contributing_surfaces must
    equal the derived config's own existing-path set, and the count grows
    by exactly N with no code change."""
    project_root = build_stray_label_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    baseline_meta = load_surfaces_with_meta(project_root, paths_json)
    baseline_expected = {name for name, info in baseline_meta.items() if info["path"].exists()}

    extra_names = [f"extra_{i}" for i in range(extra_count)]
    if extra_names:
        add_extra_directory_surfaces(project_root, extra_names)

    km = build_knowledge_map(project_root, paths_json)
    surfaces_meta = load_surfaces_with_meta(project_root, paths_json)
    expected = {name for name, info in surfaces_meta.items() if info["path"].exists()}

    assert km.contributing_surfaces == expected
    assert len(expected) == len(baseline_expected) + extra_count

    for name in extra_names:
        matching = [n for n in km.nodes if n.surface == name]
        assert matching, f"extra surface {name!r} produced no node"
        extra_dir = (project_root / name).resolve()
        assert all(extra_dir in n.path.resolve().parents for n in matching)


def test_optional_absent_surface_is_skipped_and_a_missing_non_optional_path_does_not_abort(tmp_path):
    # covers: KM-KGS-100c-1
    # angle: boundary
    """On the reused stray-label fixture (no docs/architecture/components/,
    no config/skill_registry.json), optional-absent surfaces are excluded
    from declared_surfaces with no surface-set failure, the build does not
    abort, and non-optional surfaces with no path in this project are not
    reported as 'path exists, nothing read'."""
    from knowledge_query import check_surface_set  # local: not yet defined at collection time

    project_root = build_stray_label_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    raw_config = json.loads(REAL_PATHS_JSON.read_text(encoding="utf-8"))

    optional_absent = {
        name
        for name, cfg in raw_config["surfaces"].items()
        if cfg.get("_optional") and not (project_root / cfg["path"]).exists()
    }
    assert optional_absent, "fixture must have at least one optional-absent surface"

    km = build_knowledge_map(project_root, paths_json)  # must not raise / SystemExit
    assert optional_absent.isdisjoint(km.declared_surfaces)

    failures = check_surface_set(km, project_root, paths_json)
    text = "\n".join(failures)
    for name in optional_absent:
        assert name not in text

    non_optional_missing = {
        name
        for name, cfg in raw_config["surfaces"].items()
        if not cfg.get("_optional") and not (project_root / cfg["path"]).exists()
    }
    assert non_optional_missing, "fixture must have a non-optional surface with no path present"
    for name in non_optional_missing:
        assert name not in text


def test_no_surface_is_read_that_was_not_declared(tmp_path):
    # covers: KM-KGS-100c-1
    # angle: criterion
    """Omitting the one surface whose declared path is a file outside every
    other declared surface's path (chosen programmatically -- the agent
    registry in the real config) removes every item and label it produced,
    while the unaltered copy still reads them."""
    project_root = build_stray_label_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    raw_config = json.loads(REAL_PATHS_JSON.read_text(encoding="utf-8"))
    omitted = select_solo_file_surface(project_root, raw_config["surfaces"])

    km_before = build_knowledge_map(project_root, paths_json)
    assert any(n.surface == omitted for n in km_before.nodes), (
        f"the unaltered config must still read {omitted!r} items"
    )

    remove_surface_from_config(project_root, omitted)
    km_after = build_knowledge_map(project_root, paths_json)

    assert not any(n.surface == omitted for n in km_after.nodes)
    omitted_path = (project_root / raw_config["surfaces"][omitted]["path"]).resolve()
    assert not any(n.path.resolve() == omitted_path for n in km_after.nodes)
    assert omitted not in km_after.declared_surfaces
    assert omitted not in km_after.contributing_surfaces
