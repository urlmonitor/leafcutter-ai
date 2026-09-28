"""
MODULE: km_kgs_100c_1_shared
GOAL: Shared temp-project fixture builders for the KM-KGS-100c-1 family
      (parent -1, and children -i, -ii): the "empty-components" fixture
      (KM-KGS-100c-1-i) and the "stray-label" fixture (KM-KGS-100c-1-ii).
BUSINESS CONTEXT: KM-KGS-100c-1's test_rationale asks that the stray-label
    fixture be "reused through the shared helper and not rebuilt" by the
    parent's own tests, and KM-KGS-100c-1-i/-ii each ask to reuse "the
    shared temp-project helper" rather than hand-rolling a project per
    test file. This module is that helper for the -1/-i/-ii trio, built on
    top of km_kgs_100d_4_shared's copy_real_paths_json/write_registry_json
    so every fixture starts from a BYTE COPY of the real config/paths.json
    (never a hand-authored surfaces dict) -- a config that fails to
    declare a surface correctly must not be able to pass these tests.
    Not named test_*.py so pytest's collector never treats it as a test
    module in its own right; it carries no # covers:/# angle: tags because
    it contains no test functions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from km_kgs_100d_4_shared import copy_real_paths_json, write_registry_json

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
REAL_PATHS_JSON = REPO_ROOT / "config" / "paths.json"

# ASSUMED message formats emitted by the coder's check_surface_set() (see the
# test-writer's report for the full contract). Kept here so every test file
# in the family parses failures the same way.
NOT_CONTRIBUTING_RE = re.compile(
    r"declared surface '([^']+)' has an existing path but contributed no items"
)
STRAY_LABEL_RE = re.compile(r"node '([^']+)' has surface label '([^']+)'")


def write_ticket_with_fields(
    tickets_dir: Path, ticket_id: str, *, components=None, files_touched=None
) -> Path:
    """Write a minimal ticket .md with optional components/files_touched lists."""
    tickets_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---\n",
        f"id: {ticket_id}\n",
        f"title: Fixture ticket {ticket_id}\n",
        "agents:\n",
        "  python-coder: needed\n",
        "depends_on: []\n",
    ]
    for field_name, values in (("components", components), ("files_touched", files_touched)):
        values = values or []
        if values:
            lines.append(f"{field_name}:\n")
            for value in values:
                lines.append(f"  - {value}\n")
        else:
            lines.append(f"{field_name}: []\n")
    lines += ["---\n\n", f"# {ticket_id}\n\nFixture body.\n"]
    path = tickets_dir / f"{ticket_id}.md"
    path.write_text("".join(lines), encoding="utf-8")
    return path


def build_empty_components_fixture(tmp_path: Path) -> Path:
    """KM-KGS-100c-1-i's "empty-components fixture".

    Byte copy of the real config/paths.json; tickets/T-1.md declares
    component "build-pipeline" (so a hub node is created); an EMPTY
    docs/architecture/components/ directory (path exists, nothing to
    read); one docs/overview.md so the docs surface -- whose own path
    must exist to contain the components folder -- reads a real item.
    No other declared surface's path exists in this project.
    """
    copy_real_paths_json(tmp_path)
    write_ticket_with_fields(tmp_path / "tickets", "T-1", components=["build-pipeline"])
    (tmp_path / "docs" / "architecture" / "components").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "overview.md").write_text(
        "# Overview\n\nFixture doc.\n", encoding="utf-8"
    )
    return tmp_path


def add_one_component_document(project_root: Path) -> Path:
    """Add one real file to the empty-components fixture's components dir."""
    doc = project_root / "docs" / "architecture" / "components" / "build-pipeline.md"
    doc.write_text("# build-pipeline\n\nFixture component doc.\n", encoding="utf-8")
    return doc


def build_stray_label_fixture(tmp_path: Path) -> Path:
    """KM-KGS-100c-1-ii's "stray-label fixture" (also reused by KM-KGS-100c-1).

    Byte copy of the real config/paths.json (declares agents and tickets;
    no surface named "files" or "gizmos"); config/agent_registry.json
    holding agent "python-coder"; tickets/T-1.md whose frontmatter lists
    components ["build-pipeline"] and files_touched ["scripts/foo.py"];
    and a real scripts/foo.py. The real builder alone (no injection here)
    produces a "python-coder" agents node, a "T-1" tickets node, a
    "build-pipeline" components hub, and a "scripts/foo.py" files node.
    """
    copy_real_paths_json(tmp_path)
    write_registry_json(
        tmp_path / "config" / "agent_registry.json",
        "agents",
        [{"id": "python-coder", "name": "Python Coder"}],
    )
    write_ticket_with_fields(
        tmp_path / "tickets",
        "T-1",
        components=["build-pipeline"],
        files_touched=["scripts/foo.py"],
    )
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "foo.py").write_text("# fixture\n", encoding="utf-8")
    return tmp_path


def load_paths_json(paths_json: Path) -> dict:
    """Parse a paths.json file into a dict (real json.loads, never a literal)."""
    return json.loads(paths_json.read_text(encoding="utf-8"))


def write_paths_json(paths_json: Path, data: dict) -> Path:
    """Serialize *data* back to *paths_json* via the real json.dumps."""
    paths_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return paths_json


def add_extra_directory_surfaces(project_root: Path, names: list[str]) -> Path:
    """Add each name in *names* to config/paths.json as a directory surface.

    Each surface's path is "<name>/" under *project_root*, materialized
    with one <name>.md file so the surface has something real to read.
    Returns the rewritten paths.json path.
    """
    paths_json = project_root / "config" / "paths.json"
    data = load_paths_json(paths_json)
    for name in names:
        folder = project_root / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.md").write_text(
            f"# {name}\n\nFixture extra surface.\n", encoding="utf-8"
        )
        data["surfaces"][name] = {"path": f"{name}/", "edge_fields": []}
    return write_paths_json(paths_json, data)


def remove_surface_from_config(project_root: Path, name: str) -> Path:
    """Delete surface *name* from config/paths.json's surfaces map."""
    paths_json = project_root / "config" / "paths.json"
    data = load_paths_json(paths_json)
    data["surfaces"].pop(name, None)
    return write_paths_json(paths_json, data)


def select_solo_file_surface(project_root: Path, raw_surfaces: dict) -> str:
    """Return the declared surface whose resolved path is an existing file
    lying outside every other declared surface's existing directory tree.

    This is the AC's "the one surface whose declared path is a file that
    lies outside every other declared surface's path", chosen
    programmatically from the fixture's actual on-disk state rather than
    hardcoded to a name.
    """
    existing_dirs = [
        (project_root / cfg["path"]).resolve()
        for cfg in raw_surfaces.values()
        if cfg["path"].endswith("/") and (project_root / cfg["path"]).exists()
    ]
    candidates = []
    for name, cfg in raw_surfaces.items():
        if cfg["path"].endswith("/"):
            continue
        resolved = (project_root / cfg["path"]).resolve()
        if not resolved.exists():
            continue
        if any(existing_dir in resolved.parents for existing_dir in existing_dirs):
            continue
        candidates.append(name)
    assert len(candidates) == 1, f"expected exactly one solo file surface, got {candidates}"
    return candidates[0]
