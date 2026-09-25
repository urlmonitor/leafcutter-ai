"""
MODULE: test_km_kgs_100d_4_ii
GOAL: TDD stubs for KM-KGS-100d-4-ii -- a file a relationship names that does
      not exist stays on the map as a files-surface node, explicitly marked
      missing, and the missing count is reported in both renderers.
BUSINESS CONTEXT: These tests build the map through a byte copy of the real
    config/paths.json and the public build_knowledge_map()/shipped CLI --
    never a hand-built edge dict -- per the epic's real-config-only rule.

ASSUMED API NAMES (none of this exists yet; the coder must implement exactly
    these names so this file's tests go green):
  - NodeRecord gains a boolean field ``missing`` (explicit True/False on
    every 'files'-surface node; default False elsewhere).
  - The new surface name is 'files'.
  - render_json's payload gains two new top-level integer keys:
    'files_nodes' (total files-surface node count) and 'missing_files'
    (the subset marked missing).
  - render_text's summary line gains 'Files: <n>' and 'Missing: <n>'
    labels alongside the existing Edges figure.
  - render_json's payload also gains a top-level 'declined' integer key
    (owned by KM-KGS-100d-4-iii); this file only asserts it stays 0 here.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"
_KNOWLEDGE_QUERY_SCRIPT = _SCRIPTS_DIR / "knowledge_query.py"

sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map, validate_edges_integrity  # noqa: E402


def _build_missing_file_project(tmp_path):
    """The missing-file fixture shared by every test in this module.

    KM-EX-040 names scripts/removed_tool.py (never created) in
    implemented_by; ticket T-2 names the same path in files_touched.
    KM-EX-041 names scripts/foo.py (a real file) in implemented_by.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-040.yaml").write_text(
        "id: KM-EX-040\n"
        "title: Names a removed tool\n"
        "implemented_by:\n"
        "- scripts/removed_tool.py\n",
        encoding="utf-8",
    )
    (acs_dir / "KM-EX-041.yaml").write_text(
        "id: KM-EX-041\n"
        "title: Names an existing tool\n"
        "implemented_by:\n"
        "- scripts/foo.py\n",
        encoding="utf-8",
    )

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir(parents=True)
    (tickets_dir / "T-2.md").write_text(
        "---\n"
        "id: T-2\n"
        "title: Names the same removed tool\n"
        "agents:\n"
        "  python-coder: needed\n"
        "depends_on: []\n"
        "files_touched:\n"
        "  - scripts/removed_tool.py\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "foo.py").write_text("# real file\n", encoding="utf-8")
    # scripts/removed_tool.py is deliberately never created.

    return tmp_path, config_dir / "paths.json"


def _run_cli_json(project_root, cwd=None):
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
        cwd=cwd,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    return json.loads(result.stdout)


def _run_cli_text(project_root):
    result = subprocess.run(
        [
            sys.executable,
            str(_KNOWLEDGE_QUERY_SCRIPT),
            "--project-root",
            str(project_root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    return result.stdout


def _assert_text_counts(text, files, missing):
    files_match = re.search(r"Files:\s*(\d+)", text)
    missing_match = re.search(r"Missing:\s*(\d+)", text)
    assert files_match and int(files_match.group(1)) == files, (
        f"text summary must state 'Files: {files}' explicitly; got: {text!r}"
    )
    assert missing_match and int(missing_match.group(1)) == missing, (
        f"text summary must state 'Missing: {missing}' explicitly "
        f"(zero included); got: {text!r}"
    )


def test_missing_file_is_one_node_marked_missing_with_both_edges(tmp_path):
    # covers: KM-KGS-100d-4-ii
    # angle: criterion
    """One files-surface node for the missing path; missing is True by identity."""
    project_root, paths_json = _build_missing_file_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    matches = [n for n in km.nodes if n.id == "scripts/removed_tool.py"]
    assert len(matches) == 1, (
        f"expected exactly one node id 'scripts/removed_tool.py'; got "
        f"{len(matches)} (files-surface nodes for missing files do not exist yet)"
    )
    node = matches[0]
    assert node.surface == "files"
    assert node.missing is True, "missing mark must be True by identity, not truthy"

    targets = [e for e in km.edges if e.target_id == "scripts/removed_tool.py"]
    sources = {e.source_id for e in targets}
    assert sources == {"KM-EX-040", "T-2"}


def test_existing_file_is_marked_present_explicitly(tmp_path):
    # covers: KM-KGS-100d-4-ii
    # angle: criterion
    """A referenced file that exists on disk is marked missing is False."""
    project_root, paths_json = _build_missing_file_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    matches = [n for n in km.nodes if n.id == "scripts/foo.py"]
    assert len(matches) == 1
    assert matches[0].missing is False, "present mark must be explicit False, not None"


def test_json_export_carries_missing_mark_on_every_files_node(tmp_path):
    # covers: KM-KGS-100d-4-ii
    # angle: reachability
    """The shipped CLI's JSON export carries a boolean 'missing' on every files node."""
    project_root, _ = _build_missing_file_project(tmp_path)
    payload = _run_cli_json(project_root)

    files_nodes = {n["id"]: n for n in payload["nodes"] if n["surface"] == "files"}
    assert "scripts/removed_tool.py" in files_nodes
    assert "scripts/foo.py" in files_nodes
    for node_id, node in files_nodes.items():
        assert isinstance(node.get("missing"), bool), (
            f"files node {node_id!r} JSON export must carry a boolean "
            f"'missing' key; got {node.get('missing')!r}"
        )
    assert files_nodes["scripts/removed_tool.py"]["missing"] is True
    assert files_nodes["scripts/foo.py"]["missing"] is False


def test_files_node_counts_stated_in_both_renderers_zero_included(tmp_path):
    # covers: KM-KGS-100d-4-ii
    # angle: boundary
    """Three fixtures: (missing, 2/1), (both present, 2/0), (none referenced, 0/0)."""
    # (a) the missing-file fixture
    project_a, _ = _build_missing_file_project(tmp_path / "a")
    payload_a = _run_cli_json(project_a)
    text_a = _run_cli_text(project_a)
    assert payload_a.get("files_nodes") == 2
    assert payload_a.get("missing_files") == 1
    _assert_text_counts(text_a, files=2, missing=1)

    # (b) same fixture with scripts/removed_tool.py created
    (project_a / "scripts" / "removed_tool.py").write_text(
        "# now exists\n", encoding="utf-8"
    )
    payload_b = _run_cli_json(project_a)
    text_b = _run_cli_text(project_a)
    assert payload_b.get("files_nodes") == 2
    assert payload_b.get("missing_files") == 0
    _assert_text_counts(text_b, files=2, missing=0)

    # (c) a fixture whose ACs name no file
    root_c = tmp_path / "c"
    config_dir_c = root_c / "config"
    config_dir_c.mkdir(parents=True)
    (config_dir_c / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())
    acs_dir_c = root_c / "docs" / "acceptance-criteria" / "example-component"
    acs_dir_c.mkdir(parents=True)
    (acs_dir_c / "KM-EX-042.yaml").write_text(
        "id: KM-EX-042\ntitle: Names no file\nimplemented_by: []\n",
        encoding="utf-8",
    )
    payload_c = _run_cli_json(root_c)
    text_c = _run_cli_text(root_c)
    assert payload_c.get("files_nodes") == 0
    assert payload_c.get("missing_files") == 0
    _assert_text_counts(text_c, files=0, missing=0)


def test_missing_file_edges_are_kept_not_dropped_or_declined(tmp_path):
    # covers: KM-KGS-100d-4-ii
    # angle: failure
    """Both edges to the missing file survive validation; declined stays 0."""
    project_root, paths_json = _build_missing_file_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    result = validate_edges_integrity(km, project_root, paths_json)
    kept = [e for e in result.validated_edges if e.target_id == "scripts/removed_tool.py"]
    assert len(kept) == 2, (
        "both edges to the missing file must be in validated_edges, not dropped"
    )
    dropped = [e for e in result.dropped_edges if e.target_id == "scripts/removed_tool.py"]
    assert dropped == []

    payload = _run_cli_json(project_root)
    assert payload.get("declined") == 0, (
        "a missing file is a real node, never grounds to decline a value "
        f"(KM-KGS-100d-4-iii's territory); got declined={payload.get('declined')!r}"
    )


def test_existence_is_judged_under_project_root_not_cwd(tmp_path):
    # covers: KM-KGS-100d-4-ii
    # angle: boundary
    """Existence must be tested under --project-root, never the process cwd."""
    project_root, _ = _build_missing_file_project(tmp_path / "proj")
    other_cwd = tmp_path / "elsewhere"
    other_cwd.mkdir(parents=True)
    (other_cwd / "scripts").mkdir()
    (other_cwd / "scripts" / "removed_tool.py").write_text(
        "# only present here, not under project_root\n", encoding="utf-8"
    )

    payload = _run_cli_json(project_root, cwd=other_cwd)
    files_nodes = {n["id"]: n for n in payload["nodes"] if n["surface"] == "files"}
    assert files_nodes["scripts/removed_tool.py"]["missing"] is True, (
        "existence must be judged relative to --project-root, not the cwd the "
        "process happens to be launched from"
    )


# Measured 2026-09-25: 149 of 650 distinct AC-only file references are
# missing on disk. The test_spec only requires ">0", so the floor pinned
# here is deliberately conservative; the real count is stated in the
# failure message rather than hard-pinned, so authors may clean files up.
_REPO_MISSING_FLOOR = 1


def test_real_repository_missing_files_are_counted_and_match_disk():
    # covers: KM-KGS-100d-4-ii
    # angle: real_artifact
    """Real repository: every files node's missing mark matches os.path.exists."""
    assert _REPO_ROOT.exists(), f"repo root must exist: {_REPO_ROOT}"
    payload = _run_cli_json(_REPO_ROOT)

    files_nodes = [n for n in payload["nodes"] if n["surface"] == "files"]
    assert files_nodes, (
        "expected at least one files-surface node from the real repository "
        "(files-surface nodes do not exist yet)"
    )
    for node in files_nodes:
        assert isinstance(node.get("missing"), bool), (
            f"files node {node['id']!r} missing a boolean 'missing' key"
        )
        on_disk = (_REPO_ROOT / node["id"]).exists()
        assert node["missing"] is (not on_disk), (
            f"node {node['id']!r} missing={node['missing']!r} disagrees with "
            f"os.path.exists()={on_disk!r}"
        )

    missing_count = sum(1 for n in files_nodes if n["missing"] is True)
    assert missing_count >= _REPO_MISSING_FLOOR, (
        f"expected >= {_REPO_MISSING_FLOOR} missing files nodes (149 of 650 "
        f"AC-only references measured 2026-09-25); got {missing_count} of "
        f"{len(files_nodes)} files nodes total"
    )
    assert payload.get("files_nodes") == len(files_nodes)
    assert payload.get("missing_files") == missing_count
