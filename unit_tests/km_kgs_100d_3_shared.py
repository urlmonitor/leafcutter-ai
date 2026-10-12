"""
MODULE: km_kgs_100d_3_shared
GOAL: Shared temp-project builders, CLI runners and output readers for the
    KM-KGS-100d-3 / KM-KGS-100d-3-i / GE-118f test family (a labelled
    relationship entry becomes an edge; an entry the builder cannot turn into
    an edge is reported and counted).
BUSINESS CONTEXT: Every document written here is serialised with
    ``yaml.safe_dump`` (PyYAML's own block-list shape, dashes at column 0) and
    is read back from disk by the REAL knowledge_query.py CLI -- never a
    hand-indented literal and never a dict handed straight to extract_edges
    (docs/how-to/real-artifact-fixtures.md). Not named ``test_*.py`` so
    pytest never collects it; it carries no test functions and no tags.
ARCHITECTURE: Target documents are written TWICE -- once as a real file whose
    node id is its filename stem, and once as an "alias" document whose
    frontmatter ``id`` is the raw repo-relative path string. A related_docs
    edge therefore survives the membership filter whether the implementation
    keeps the raw path string as the target (today's bare-form behaviour) or
    reduces it to a filename stem (the ``_PATH_FIELDS`` treatment), so these
    tests pin the AC's behaviour rather than one implementation's choice of
    target spelling.

FIGURE CONTRACT THE DECLINE TESTS PIN (the AC says only "a machine-readable
    declined figure beside the edge count"; these are the names the tests read):
        JSON  : top-level integer key ``entries_declined``
        text  : ``Entries declined: N`` on the ``Surfaces: ... Edges: ...``
                summary line
    When ``entries_declined`` / ``Entries declined:`` is absent the readers
    fall back to the pre-existing ``declined`` / ``Declined:`` figure, so an
    implementation that folds the new count into that figure is also accepted.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
KNOWLEDGE_QUERY_SCRIPT = SCRIPTS_DIR / "knowledge_query.py"
REAL_PATHS_JSON = REPO_ROOT / "config" / "paths.json"

# A surface that exists only in the test configuration, with a name that is
# NOT a substring of any path the fixtures write, so a diagnostic naming the
# surface cannot be satisfied by the document path alone.
EXTRA_SURFACE = "zz_surface"
EXTRA_SURFACE_DIR = "notes_dir"

BARE_NAME = "explanation-doc"
LABELLED_NAME = "reference-doc"


def subprocess_env() -> dict:
    """Environment for subprocess CLI runs: real environ plus forced UTF-8."""
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return env


def write_paths_json(root: Path, extra_surfaces: dict | None = None) -> Path:
    """Write config/paths.json: the REAL one, optionally plus extra surfaces.

    Loaded with json and re-serialised with json.dump, so the shipped surface
    declarations (docs/adrs/components ``edge_fields``) are the real ones.
    """
    data = json.loads(REAL_PATHS_JSON.read_text(encoding="utf-8"))
    for name, cfg in (extra_surfaces or {}).items():
        data["surfaces"][name] = cfg
    dest = root / "config" / "paths.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return dest


def write_doc(path: Path, frontmatter: dict, body: str = "Fixture body.\n") -> Path:
    """Write a markdown document whose frontmatter is yaml.safe_dump output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dumped = yaml.safe_dump(frontmatter, sort_keys=False)
    path.write_text(f"---\n{dumped}---\n\n{body}", encoding="utf-8")
    return path


def raw_path(directory: str, name: str) -> str:
    """Repo-relative posix path string a related_docs entry would carry."""
    return f"{directory}/{name}.md"


def write_target_docs(root: Path, directory: str, names: list[str]) -> None:
    """Write each target as a real file (id = stem) plus an alias (id = raw path)."""
    for name in names:
        raw = raw_path(directory, name)
        write_doc(root / raw, {"title": f"Target {name}"})
        write_doc(
            root / directory / f"alias-{name}.md",
            {"id": raw, "title": f"Alias of {raw}"},
        )


def build_project(
    root: Path,
    directory: str,
    entries: list,
    target_names: list[str] | None = None,
    source_id: str = "src-doc",
    extra_surfaces: dict | None = None,
) -> str:
    """Build a temp project holding one source document with ``related_docs``.

    Args:
        root: Temp project root.
        directory: Repo-relative directory (no trailing slash) the documents
            live in; it must be (inside) a declared surface's path.
        entries: The literal ``related_docs`` list serialised by yaml.safe_dump.
        target_names: Names to write as targets (real file + alias each).
        source_id: Frontmatter id (and filename stem) of the source document.
        extra_surfaces: Surfaces added to the real paths.json copy.

    Returns:
        The source document's node id.
    """
    write_paths_json(root, extra_surfaces)
    write_target_docs(root, directory, list(target_names or []))
    write_doc(
        root / directory / f"{source_id}.md",
        {"id": source_id, "title": f"Source {source_id}", "related_docs": entries},
    )
    return source_id


def extra_surface_config() -> dict:
    """The test-only surface declaring related_docs, derived like any other."""
    return {EXTRA_SURFACE: {"path": f"{EXTRA_SURFACE_DIR}/", "edge_fields": ["related_docs"]}}


def run_cli(
    project_root: Path,
    extra_args: list[str] | None = None,
    script: Path = KNOWLEDGE_QUERY_SCRIPT,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Run a knowledge_query.py CLI (source tree by default) as a real subprocess."""
    args = [sys.executable, str(script), "--project-root", str(project_root)]
    args += list(extra_args or [])
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=subprocess_env(),
    )


def run_json(project_root: Path, extra_args: list[str] | None = None, script: Path = KNOWLEDGE_QUERY_SCRIPT):
    """Run the CLI with --format json; return (CompletedProcess, parsed payload).

    The payload is parsed from stdout with no cleanup, so any diagnostic
    leaking onto stdout makes this raise (stdout must stay parseable).
    """
    result = run_cli(project_root, ["--format", "json", *(extra_args or [])], script=script)
    assert result.returncode == 0, f"exit {result.returncode}; stderr: {result.stderr}"
    return result, json.loads(result.stdout)


def related_docs_edges(payload: dict, source_id: str) -> list[tuple[str, str]]:
    """Ordered (target, type) of every related_docs edge leaving *source_id*."""
    return [
        (e["target"], e["type"])
        for e in payload["edges"]
        if e["source"] == source_id and e["type"] == "related_docs"
    ]


def target_matches(target: str, directory: str, name: str) -> bool:
    """True when *target* is either spelling of the doc: raw path or its stem."""
    return target in (raw_path(directory, name), name)


def summary_line(text_stdout: str) -> str:
    """The ``Surfaces: N   Nodes: N   Edges: N ...`` line of the text renderer."""
    for line in text_stdout.splitlines():
        if line.startswith("Surfaces:"):
            return line
    return ""


def declined_from_json(payload: dict):
    """The declined-entries figure of a JSON payload (None when absent)."""
    if "entries_declined" in payload:
        return payload["entries_declined"]
    return payload.get("declined")


def declined_from_text(text_stdout: str):
    """The declined-entries figure on the text summary line (None when absent)."""
    line = summary_line(text_stdout)
    match = re.search(r"Entries declined:\s*(\d+)", line, re.IGNORECASE) or re.search(
        r"Declined:\s*(\d+)", line
    )
    return int(match.group(1)) if match else None


def edges_from_text_summary(text_stdout: str):
    """The ``Edges: N`` figure on the text summary line (None when absent)."""
    match = re.search(r"Edges:\s*(\d+)", summary_line(text_stdout))
    return int(match.group(1)) if match else None


def stderr_lines_naming(stderr: str, *needles: str) -> list[str]:
    """Stderr lines containing every needle."""
    return [ln for ln in stderr.splitlines() if all(n in ln for n in needles)]


def declined_mapping(directory: str, tag: str) -> dict:
    """A two-key labelled mapping -- a shape the shared resolver refuses (GE-118d-2)."""
    return {
        f"first-label-{tag}": raw_path(directory, f"declined-{tag}-first"),
        f"second-label-{tag}": raw_path(directory, f"declined-{tag}-second"),
    }
