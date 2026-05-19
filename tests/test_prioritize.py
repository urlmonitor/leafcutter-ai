"""
Unit tests for .agents/skills/ticket-prioritizer/scripts/prioritize.py.

Tests cover:
- YAML frontmatter parsing
- Done detection (status field and done/ directory)
- DAG construction
- Cycle detection
- Ready/blocked partitioning
- Priority sorting
- JSON and human-readable output formatting
"""

import json
import sys
import textwrap
from pathlib import Path

import pytest

# Add the prioritizer scripts directory to path
_SCRIPTS_DIR = (
    Path(__file__).resolve()
    .parent  # tests/
    .parent  # repo root
    / "templates"
    / "skills"
    / "ticket-prioritizer"
    / "scripts"
)
sys.path.insert(0, str(_SCRIPTS_DIR))

import prioritize  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ticket(
    tmp_path: Path,
    name: str,
    status: str = "todo",
    priority: str = "medium",
    depends_on: list[str] | None = None,
    subdir: str | None = None,
    tags: list[str] | None = None,
    parked_field: bool = False,
) -> Path:
    """Create a minimal ticket .md file in tmp_path.

    Args:
        tmp_path: Root directory to write into.
        name: Filename (e.g. '01_base.md').
        status: Ticket status field value.
        priority: Ticket priority field value.
        depends_on: List of dependency filenames.
        subdir: Optional subdirectory to place the file in.
        tags: Optional list of tag strings to include in the frontmatter.
        parked_field: When True, includes ``parked: true`` in the frontmatter.

    Returns:
        Path to the created file.
    """
    deps_lines = ""
    if depends_on:
        dep_items = "\n".join(f"  - {d}" for d in depends_on)
        deps_lines = f"depends_on:\n{dep_items}"
    else:
        deps_lines = "depends_on: []"

    tags_lines = ""
    if tags:
        tag_items = "\n".join(f"  - {t}" for t in tags)
        tags_lines = f"tags:\n{tag_items}"

    parked_line = "parked: true" if parked_field else ""

    # Build frontmatter lines, omitting blank entries
    extra_lines = "\n".join(
        line for line in [tags_lines, parked_line] if line
    )

    content = textwrap.dedent(f"""\
        ---
        title: "Ticket {name}"
        status: {status}
        priority: {priority}
        {deps_lines}
        {extra_lines}
        components:
          - infrastructure
        created: 2026-05-13
        ---

        # {name}
    """)
    target_dir = tmp_path / subdir if subdir else tmp_path
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / name
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_parses_simple_scalar(self):
        text = "---\nstatus: todo\n---\n"
        fm = prioritize.parse_frontmatter(text)
        assert fm["status"] == "todo"

    def test_parses_list_block(self):
        text = "---\ndepends_on:\n  - a.md\n  - b.md\n---\n"
        fm = prioritize.parse_frontmatter(text)
        assert fm["depends_on"] == ["a.md", "b.md"]

    def test_parses_inline_list(self):
        text = "---\ndepends_on: [a.md, b.md]\n---\n"
        fm = prioritize.parse_frontmatter(text)
        assert fm["depends_on"] == ["a.md", "b.md"]

    def test_empty_list(self):
        text = "---\ndepends_on: []\n---\n"
        fm = prioritize.parse_frontmatter(text)
        assert fm["depends_on"] == []

    def test_no_frontmatter_returns_empty(self):
        text = "No frontmatter here\n# Just a heading\n"
        fm = prioritize.parse_frontmatter(text)
        assert fm == {}

    def test_boolean_coercion(self):
        text = "---\nflag: true\n---\n"
        fm = prioritize.parse_frontmatter(text)
        assert fm["flag"] is True

    def test_null_coercion(self):
        text = "---\ndomain: null\n---\n"
        fm = prioritize.parse_frontmatter(text)
        assert fm["domain"] is None


# ---------------------------------------------------------------------------
# Done detection
# ---------------------------------------------------------------------------


class TestIsDonePath:
    def test_done_dir_is_done(self, tmp_path):
        p = tmp_path / "done" / "01_ticket.md"
        assert prioritize.is_done_path(p) is True

    def test_09_done_dir_is_done(self, tmp_path):
        p = tmp_path / "09_done" / "01_ticket.md"
        assert prioritize.is_done_path(p) is True

    def test_todo_dir_is_not_done(self, tmp_path):
        p = tmp_path / "01_todo" / "EPIC-Foo" / "02_ticket.md"
        assert prioritize.is_done_path(p) is False

    def test_99_rejected_is_done(self, tmp_path):
        p = tmp_path / "99_rejected" / "01_ticket.md"
        assert prioritize.is_done_path(p) is True


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_single_ticket_no_deps(self, tmp_path):
        path = make_ticket(tmp_path, "01_base.md")
        tickets = [{"path": path, "frontmatter": {"title": "Base", "status": "todo", "depends_on": []}, "done": False}]
        graph = prioritize.build_graph(tickets)
        assert "01_base.md" in graph
        assert graph["01_base.md"]["depends_on"] == []

    def test_depends_on_preserved(self, tmp_path):
        path = make_ticket(tmp_path, "02_dep.md", depends_on=["01_base.md"])
        tickets = [{"path": path, "frontmatter": {"title": "Dep", "status": "todo", "depends_on": ["01_base.md"]}, "done": False}]
        graph = prioritize.build_graph(tickets)
        assert graph["02_dep.md"]["depends_on"] == ["01_base.md"]


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestDetectCycle:
    def test_no_cycle(self, tmp_path):
        pa = make_ticket(tmp_path, "a.md")
        pb = make_ticket(tmp_path, "b.md", depends_on=["a.md"])
        tickets = [
            {"path": pa, "frontmatter": {"title": "A", "status": "todo", "depends_on": []}, "done": False},
            {"path": pb, "frontmatter": {"title": "B", "status": "todo", "depends_on": ["a.md"]}, "done": False},
        ]
        graph = prioritize.build_graph(tickets)
        assert prioritize.detect_cycle(graph) is None

    def test_direct_cycle(self, tmp_path):
        pa = make_ticket(tmp_path, "a.md", depends_on=["b.md"])
        pb = make_ticket(tmp_path, "b.md", depends_on=["a.md"])
        tickets = [
            {"path": pa, "frontmatter": {"title": "A", "status": "todo", "depends_on": ["b.md"]}, "done": False},
            {"path": pb, "frontmatter": {"title": "B", "status": "todo", "depends_on": ["a.md"]}, "done": False},
        ]
        graph = prioritize.build_graph(tickets)
        cycle = prioritize.detect_cycle(graph)
        assert cycle is not None
        assert len(cycle) >= 2

    def test_transitive_cycle(self, tmp_path):
        pa = make_ticket(tmp_path, "a.md", depends_on=["c.md"])
        pb = make_ticket(tmp_path, "b.md", depends_on=["a.md"])
        pc = make_ticket(tmp_path, "c.md", depends_on=["b.md"])
        tickets = [
            {"path": pa, "frontmatter": {"title": "A", "status": "todo", "depends_on": ["c.md"]}, "done": False},
            {"path": pb, "frontmatter": {"title": "B", "status": "todo", "depends_on": ["a.md"]}, "done": False},
            {"path": pc, "frontmatter": {"title": "C", "status": "todo", "depends_on": ["b.md"]}, "done": False},
        ]
        graph = prioritize.build_graph(tickets)
        cycle = prioritize.detect_cycle(graph)
        assert cycle is not None


# ---------------------------------------------------------------------------
# Ready/blocked computation
# ---------------------------------------------------------------------------


class TestComputeReady:
    def test_independent_ticket_is_ready(self, tmp_path):
        pa = make_ticket(tmp_path, "01_base.md")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        names = [Path(t["path"]).name for t in ready]
        assert "01_base.md" in names
        assert blocked == []

    def test_done_ticket_not_in_ready(self, tmp_path):
        pa = make_ticket(tmp_path, "01_base.md", status="done")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        names = [Path(t["path"]).name for t in ready]
        assert "01_base.md" not in names

    def test_ticket_with_done_dep_is_ready(self, tmp_path):
        make_ticket(tmp_path, "01_base.md", status="done")
        make_ticket(tmp_path, "02_dep.md", depends_on=["01_base.md"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        names = [Path(t["path"]).name for t in ready]
        assert "02_dep.md" in names
        assert blocked == []

    def test_ticket_with_undone_dep_is_blocked(self, tmp_path):
        make_ticket(tmp_path, "01_base.md", status="todo")
        make_ticket(tmp_path, "02_dep.md", depends_on=["01_base.md"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        blocked_names = [Path(t["path"]).name for t in blocked]
        assert "01_base.md" in ready_names
        assert "02_dep.md" in blocked_names

    def test_transitive_blocking(self, tmp_path):
        """A -> B -> C: when A is todo, B and C are both blocked."""
        make_ticket(tmp_path, "01_a.md", status="todo")
        make_ticket(tmp_path, "02_b.md", depends_on=["01_a.md"])
        make_ticket(tmp_path, "03_c.md", depends_on=["02_b.md"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        blocked_names = [Path(t["path"]).name for t in blocked]
        assert "01_a.md" in ready_names
        assert "02_b.md" in blocked_names
        # 03_c is only blocked by 02_b (direct dep), and 02_b is todo
        assert "03_c.md" in blocked_names

    def test_done_in_done_subdir(self, tmp_path):
        """Ticket in done/ subdir counts as done even without status: done."""
        make_ticket(tmp_path, "01_base.md", status="todo", subdir="done")
        make_ticket(tmp_path, "02_dep.md", depends_on=["01_base.md"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        assert "02_dep.md" in ready_names
        assert "01_base.md" not in ready_names


# ---------------------------------------------------------------------------
# Priority sorting
# ---------------------------------------------------------------------------


class TestPrioritySorting:
    def test_critical_before_high(self, tmp_path):
        make_ticket(tmp_path, "02_high.md", priority="high")
        make_ticket(tmp_path, "01_critical.md", priority="critical")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, _, _parked = prioritize.compute_ready(graph)
        names = [Path(t["path"]).name for t in ready]
        assert names.index("01_critical.md") < names.index("02_high.md")

    def test_unlabelled_ranks_lowest(self, tmp_path):
        make_ticket(tmp_path, "01_nopri.md", priority="")
        make_ticket(tmp_path, "02_low.md", priority="low")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, _, _parked = prioritize.compute_ready(graph)
        names = [Path(t["path"]).name for t in ready]
        assert names.index("02_low.md") < names.index("01_nopri.md")


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


class TestFormatJson:
    def test_output_is_valid_json(self, tmp_path):
        make_ticket(tmp_path, "01_base.md", status="done")
        make_ticket(tmp_path, "02_dep.md", depends_on=["01_base.md"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        done_paths = [node["path"] for node in graph.values() if node["done"]]
        output = prioritize.format_json(ready, blocked, done_paths, parked)
        data = json.loads(output)
        assert "ready" in data
        assert "blocked" in data
        assert "done" in data
        assert "parked" in data

    def test_ready_entry_has_required_keys(self, tmp_path):
        make_ticket(tmp_path, "01_ready.md")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        done_paths = [node["path"] for node in graph.values() if node["done"]]
        data = json.loads(prioritize.format_json(ready, blocked, done_paths, parked))
        entry = data["ready"][0]
        assert "path" in entry
        assert "title" in entry
        assert "priority" in entry


class TestFormatHuman:
    def test_shows_ready_heading(self, tmp_path):
        make_ticket(tmp_path, "01_ready.md")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        done_paths = [node["path"] for node in graph.values() if node["done"]]
        output = prioritize.format_human(ready, blocked, done_paths, parked)
        assert "READY TICKETS" in output
        assert "01_ready.md" in output

    def test_shows_blocked_heading(self, tmp_path):
        make_ticket(tmp_path, "01_base.md")
        make_ticket(tmp_path, "02_dep.md", depends_on=["01_base.md"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        done_paths = [node["path"] for node in graph.values() if node["done"]]
        output = prioritize.format_human(ready, blocked, done_paths, parked)
        assert "BLOCKED TICKETS" in output
        assert "02_dep.md" in output


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    def test_json_flag(self, tmp_path):
        make_ticket(tmp_path, "01_base.md")
        exit_code = prioritize.main(["--epic", str(tmp_path), "--json"])
        assert exit_code == 0

    def test_cycle_exits_nonzero(self, tmp_path, capsys):
        make_ticket(tmp_path, "a.md", depends_on=["b.md"])
        make_ticket(tmp_path, "b.md", depends_on=["a.md"])
        exit_code = prioritize.main(["--epic", str(tmp_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "CYCLE DETECTED" in captured.err

    def test_epic_flag_scopes_to_dir(self, tmp_path):
        epic_dir = tmp_path / "EPIC-Test"
        epic_dir.mkdir()
        make_ticket(epic_dir, "01_ticket.md")
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        make_ticket(other_dir, "99_other.md")
        exit_code = prioritize.main(["--epic", str(epic_dir), "--json"])
        assert exit_code == 0

