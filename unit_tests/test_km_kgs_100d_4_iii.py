"""
MODULE: test_km_kgs_100d_4_iii
GOAL: TDD stubs for KM-KGS-100d-4-iii -- a relationship value that is not a
      file in this project is reported on stderr and counted, never silently
      lost.
BUSINESS CONTEXT: These tests build the map through a byte copy of the real
    config/paths.json and the public build_knowledge_map()/shipped CLI --
    never a hand-built edge dict -- per the epic's real-config-only rule.

ASSUMED API NAMES / FORMATS (none of this exists yet; the coder must
    implement exactly these so this file's tests go green):
  - render_json's payload gains a top-level integer key 'declined'
    (reused by KM-KGS-100d-4-ii, which asserts it stays 0 there).
  - render_text's summary line gains a 'Declined: <n>' label alongside the
    existing Edges figure.
  - Each declined value is announced on stderr as ONE line per value, in
    the pipe-delimited, key=value form:
        DECLINED | surface=<surface> | doc=<repo-relative path> |
        field=<field> | value=<value as read> | reason=<reason text>
    Chosen so a value containing spaces or punctuation (e.g. free-text PR
    titles) never breaks parsing. The two reasons this record produces are
    the literal strings 'not a file path in this project' and
    'absolute path outside this project'.
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

from knowledge_query import build_knowledge_map  # noqa: E402

_KM_EX_050_DOC_REL = "docs/acceptance-criteria/example-component/KM-EX-050.yaml"
_NOT_A_PATH_REASON = "not a file path in this project"
_FOREIGN_ABS_REASON = "absolute path outside this project"


def _build_decline_project(tmp_path):
    """The decline fixture shared by most tests in this module.

    KM-EX-050 names four implemented_by values: a bare hex commit SHA, a
    free-text PR title, a foreign absolute path, and one real repo path.
    Only the last is path-shaped; the other three must be declined.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-049.yaml").write_text(
        "id: KM-EX-049\ntitle: Prerequisite\nimplemented_by: []\n",
        encoding="utf-8",
    )
    (acs_dir / "KM-EX-050.yaml").write_text(
        "id: KM-EX-050\n"
        "title: Names four implemented_by values\n"
        "implemented_by:\n"
        "- ac564814\n"
        '- "PR #53 feat(build): hook integrity check"\n'
        "- /home/someone/projects/other/tickets/T-9.md\n"
        "- scripts/foo.py\n"
        "depends_on:\n"
        "- KM-EX-049\n"
        "components:\n"
        "- build-pipeline\n",
        encoding="utf-8",
    )

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "foo.py").write_text("# real file\n", encoding="utf-8")

    return tmp_path, config_dir / "paths.json"


def _run_cli(project_root, fmt="json"):
    result = subprocess.run(
        [
            sys.executable,
            str(_KNOWLEDGE_QUERY_SCRIPT),
            "--format",
            fmt,
            "--project-root",
            str(project_root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return result


def _parse_decline_lines(stderr_text):
    """Parse 'DECLINED | surface=X | doc=Y | field=Z | value=V | reason=R' lines."""
    parsed = []
    for line in stderr_text.splitlines():
        if not line.startswith("DECLINED"):
            continue
        fields = {}
        for part in line.split("|")[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key.strip()] = value.strip()
        parsed.append(fields)
    return parsed


def test_only_the_repo_path_value_yields_an_implemented_by_edge(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: criterion
    """Exactly one implemented_by edge from KM-EX-050, to the real repo path."""
    project_root, paths_json = _build_decline_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    implemented_by_edges = [
        e for e in km.edges if e.source_id == "KM-EX-050" and e.edge_type == "implemented_by"
    ]
    assert len(implemented_by_edges) == 1, (
        f"expected exactly one implemented_by edge from KM-EX-050 (three of "
        f"four values are not path-shaped); got {len(implemented_by_edges)}"
    )
    assert implemented_by_edges[0].target_id == "scripts/foo.py"


def test_no_node_is_created_for_a_declined_value(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: criterion
    """No node exists for the SHA, the free-text PR title, or the foreign path."""
    project_root, paths_json = _build_decline_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)
    node_ids = {n.id for n in km.nodes}

    declined_values = {
        "ac564814",
        "PR #53 feat(build): hook integrity check",
        "/home/someone/projects/other/tickets/T-9.md",
    }
    for value in declined_values:
        assert value not in node_ids, f"no node should be created for declined value {value!r}"
    assert "tickets/T-9.md" not in node_ids, (
        "no repo-relative form of the foreign path may be recovered as a node either"
    )


def test_each_declined_value_is_named_on_stderr_with_reason(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: criterion
    """The shipped CLI names each declined value, its surface, doc, field, reason."""
    project_root, _ = _build_decline_project(tmp_path)
    result = _run_cli(project_root, fmt="json")
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    json.loads(result.stdout)  # stdout must stay parseable

    declines = _parse_decline_lines(result.stderr)
    assert len(declines) == 3, (
        f"expected exactly three decline lines; got {len(declines)}:\n{result.stderr}"
    )

    by_value = {d.get("value"): d for d in declines}
    expectations = {
        "ac564814": _NOT_A_PATH_REASON,
        "PR #53 feat(build): hook integrity check": _NOT_A_PATH_REASON,
        "/home/someone/projects/other/tickets/T-9.md": _FOREIGN_ABS_REASON,
    }
    for value, expected_reason in expectations.items():
        assert value in by_value, f"no decline line names value {value!r}:\n{result.stderr}"
        decline = by_value[value]
        assert decline.get("surface") == "acs"
        assert decline.get("doc") == _KM_EX_050_DOC_REL
        assert decline.get("field") == "implemented_by"
        assert decline.get("reason") == expected_reason


def test_declined_figure_beside_edge_count_reconciles_in_both_renderers(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: criterion
    """The declined figure is 3 in JSON and text, matches stderr, stable across runs."""
    project_root, _ = _build_decline_project(tmp_path)

    json_result_1 = _run_cli(project_root, fmt="json")
    json_result_2 = _run_cli(project_root, fmt="json")
    text_result_1 = _run_cli(project_root, fmt="text")
    text_result_2 = _run_cli(project_root, fmt="text")
    for result in (json_result_1, json_result_2, text_result_1, text_result_2):
        assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"

    payload_1 = json.loads(json_result_1.stdout)
    payload_2 = json.loads(json_result_2.stdout)
    assert payload_1.get("declined") == 3
    assert payload_2.get("declined") == 3

    decline_lines_1 = _parse_decline_lines(json_result_1.stderr)
    assert payload_1["declined"] == len(decline_lines_1)

    for text_result in (text_result_1, text_result_2):
        match = re.search(r"Declined:\s*(\d+)", text_result.stdout)
        assert match and int(match.group(1)) == 3, (
            f"text summary must carry 'Declined: 3' beside the edge count; "
            f"got: {text_result.stdout!r}"
        )


def test_zero_declines_is_stated_explicitly(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: boundary
    """A fixture with only a real path reports declined=0 explicitly, no decline lines."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-050.yaml").write_text(
        "id: KM-EX-050\ntitle: Names only a real file\nimplemented_by:\n- scripts/foo.py\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "foo.py").write_text("# real\n", encoding="utf-8")

    json_result = _run_cli(tmp_path, fmt="json")
    text_result = _run_cli(tmp_path, fmt="text")
    assert json_result.returncode == 0 and text_result.returncode == 0

    payload = json.loads(json_result.stdout)
    assert payload.get("declined") == 0, (
        f"zero declines must be stated as an explicit 0, not omitted; got "
        f"{payload.get('declined')!r}"
    )
    match = re.search(r"Declined:\s*(\d+)", text_result.stdout)
    assert match and int(match.group(1)) == 0
    assert _parse_decline_lines(json_result.stderr) == []


def test_build_exits_zero_and_other_edges_of_the_criterion_survive(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: failure
    """A decline never fails the build; KM-EX-050's other edges are unaffected."""
    project_root, _ = _build_decline_project(tmp_path)
    result = _run_cli(project_root, fmt="json")
    assert result.returncode == 0, f"a decline must not fail the build; stderr: {result.stderr}"

    payload = json.loads(result.stdout)
    edges = [e for e in payload["edges"] if e["source"] == "KM-EX-050"]
    depends_on = [e for e in edges if e["type"] == "depends_on"]
    component = [e for e in edges if e["type"] == "component_membership"]
    assert any(e["target"] == "KM-EX-049" for e in depends_on), (
        "depends_on edge to KM-EX-049 must survive a decline elsewhere on the same node"
    )
    assert any(e["target"] == "build-pipeline" for e in component), (
        "component_membership edge must survive a decline elsewhere on the same node"
    )


def test_path_shape_rule_keeps_real_files_and_on_map_ids_and_declines_the_rest(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: boundary
    """Existence arm (Makefile/.gitignore), hex arm, on-map AC id, off-map AC id."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-051.yaml").write_text(
        "id: KM-EX-051\ntitle: On-map AC\nimplemented_by: []\n", encoding="utf-8"
    )
    (acs_dir / "KM-EX-052.yaml").write_text(
        "id: KM-EX-052\n"
        "title: Path-shape rule fixture\n"
        "implemented_by:\n"
        "- Makefile\n"
        "- .gitignore\n"
        "- deadbeef\n"
        "- KM-EX-051\n"
        "- ACD-300f-5\n",
        encoding="utf-8",
    )
    (tmp_path / "Makefile").write_text("# root-level extensionless file\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")

    km = build_knowledge_map(tmp_path, config_dir / "paths.json")
    edges = [e for e in km.edges if e.source_id == "KM-EX-052" and e.edge_type == "implemented_by"]
    targets = {e.target_id for e in edges}
    assert targets == {"Makefile", ".gitignore", "KM-EX-051"}, (
        f"deadbeef and ACD-300f-5 must be declined, not on-map ids; got {targets}"
    )
    node_ids = {n.id for n in km.nodes}
    assert "Makefile" in node_ids and ".gitignore" in node_ids
    assert "deadbeef" not in node_ids and "ACD-300f-5" not in node_ids

    result = _run_cli(tmp_path, fmt="json")
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload.get("declined") == 2, (
        f"exactly deadbeef and ACD-300f-5 must be declined; got {payload.get('declined')!r}"
    )


def test_foreign_absolute_path_is_not_recovered_by_suffix(tmp_path):
    # covers: KM-KGS-100d-4-iii
    # angle: boundary
    """A foreign absolute path whose tail matches a real repo file is still declined."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-053.yaml").write_text(
        "id: KM-EX-053\n"
        "title: Foreign absolute path with a matching tail\n"
        "implemented_by:\n"
        "- /home/someone/projects/leafcutter-ai/scripts/foo.py\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "foo.py").write_text(
        "# real, unrelated to the foreign path's author intent\n", encoding="utf-8"
    )

    km = build_knowledge_map(tmp_path, config_dir / "paths.json")
    edges = [e for e in km.edges if e.source_id == "KM-EX-053"]
    assert edges == [], (
        "the foreign absolute path must be declined outright, not recovered by "
        f"suffix-matching its tail; got edges {edges}"
    )
    assert not any(
        e.target_id == "scripts/foo.py" for e in km.edges if e.source_id == "KM-EX-053"
    )

    result = _run_cli(tmp_path, fmt="json")
    declines = _parse_decline_lines(result.stderr)
    matches = [d for d in declines if d.get("value") == "/home/someone/projects/leafcutter-ai/scripts/foo.py"]
    assert matches, f"expected a decline line naming the foreign absolute path:\n{result.stderr}"
    assert matches[0]["reason"] == _FOREIGN_ABS_REASON


def test_real_repository_declines_reconcile_with_diagnostic_lines():
    # covers: KM-KGS-100d-4-iii
    # angle: real_artifact
    """Real repository: declined figure reconciles with stderr; no declined value is a node id."""
    assert _REPO_ROOT.exists(), f"repo root must exist: {_REPO_ROOT}"
    result = _run_cli(_REPO_ROOT, fmt="json")
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    payload = json.loads(result.stdout)

    declines = _parse_decline_lines(result.stderr)
    declined = payload.get("declined")
    assert declined is not None, "expected a top-level 'declined' figure in the real JSON export"
    assert declined == len(declines), (
        f"declined figure {declined} must reconcile with the {len(declines)} stderr "
        f"decline lines (about 34 expected from the 2026-09-25 evidence, not pinned)"
    )

    node_ids = {n["id"] for n in payload["nodes"]}
    for decline in declines:
        assert decline.get("reason") in (_NOT_A_PATH_REASON, _FOREIGN_ABS_REASON), (
            f"unexpected decline reason: {decline!r}"
        )
        assert decline.get("value") not in node_ids, (
            f"declined value {decline.get('value')!r} must not equal any node id"
        )
