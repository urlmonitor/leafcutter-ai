"""
MODULE: test_master_plan_generation
GOAL: Unit tests for generate_master_plan() and its helpers in goal_to_epic.py.
      Verifies that the EPIC folder receives a Master_Plan.md with the correct
      frontmatter, sections, and content derived from the assembled ticket files.
TICKET: EPIC-AcParentChildLinkEnforcement/07_TICKET-20260607-ACD-1200a-7.md
COVERS: ACD-1200a-7
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from goal_to_epic import (  # noqa: E402
    generate_master_plan,
    _read_ticket_frontmatter,
    _collect_master_plan_data,
    _render_master_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ticket(
    epic_folder: Path,
    prefix: str,
    name: str,
    title: str,
    source_ac: str,
    agents: dict[str, str] | None = None,
    components: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> Path:
    """Write a stub ticket file with YAML frontmatter and return its path."""
    if agents is None:
        agents = {"python-coder": "needed", "commit": "needed"}
    if components is None:
        components = ["ac-driven-dev"]
    if depends_on is None:
        depends_on = []

    agents_yaml = "\n".join(f"  {k}: {v}" for k, v in agents.items())
    components_yaml = "\n".join(f"- {c}" for c in components)
    if depends_on:
        depends_on_yaml = "depends_on:\n" + "\n".join(f"- {d}" for d in depends_on)
    else:
        depends_on_yaml = "depends_on: []"

    content = (
        f"---\n"
        f"title: {title}\n"
        f"source_ac: {source_ac}\n"
        f"agents:\n{agents_yaml}\n"
        f"components:\n{components_yaml}\n"
        f"{depends_on_yaml}\n"
        f"---\n\n"
        f"# {title}\n"
    )
    path = epic_folder / f"{prefix}_{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _read_ticket_frontmatter
# ---------------------------------------------------------------------------


class TestReadTicketFrontmatter:
    """Unit tests for _read_ticket_frontmatter()."""

    def test_parses_well_formed_frontmatter(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (helper contract)
        """Reads title and source_ac from a well-formed ticket file."""
        ticket = tmp_path / "01_ticket.md"
        ticket.write_text(
            "---\ntitle: My Feature\nsource_ac: ACD-001\n---\n\n# Body\n",
            encoding="utf-8",
        )
        result = _read_ticket_frontmatter(ticket)
        assert result.get("title") == "My Feature"
        assert result.get("source_ac") == "ACD-001"

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (helper robustness)
        """Returns {} when the ticket file does not exist."""
        result = _read_ticket_frontmatter(tmp_path / "nonexistent.md")
        assert result == {}

    def test_returns_empty_dict_when_no_frontmatter(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (helper robustness)
        """Returns {} when the file has no YAML front-matter block."""
        ticket = tmp_path / "ticket.md"
        ticket.write_text("# Just a body\nNo frontmatter here.\n", encoding="utf-8")
        result = _read_ticket_frontmatter(ticket)
        assert result == {}

    def test_parses_agents_map(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (helper contract)
        """Reads the agents map from the frontmatter."""
        ticket = tmp_path / "ticket.md"
        ticket.write_text(
            "---\nagents:\n  python-coder: needed\n  commit: not_needed\n---\n",
            encoding="utf-8",
        )
        result = _read_ticket_frontmatter(ticket)
        assert result.get("agents") == {"python-coder": "needed", "commit": "not_needed"}


# ---------------------------------------------------------------------------
# _collect_master_plan_data
# ---------------------------------------------------------------------------


class TestCollectMasterPlanData:
    """Unit tests for _collect_master_plan_data()."""

    def test_collects_ticket_titles_and_source_acs(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7
        """The returned tickets list contains titles and source ACs from each file."""
        epic_folder = tmp_path / "EPIC-Test"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "first-ticket", "Feature One", "ACD-001")
        _make_ticket(epic_folder, "02", "second-ticket", "Feature Two", "ACD-002")

        data = _collect_master_plan_data(
            epic_folder=epic_folder,
            topo_order=["ACD-001", "ACD-002"],
            dep_graph={"ACD-001": [], "ACD-002": []},
            goal_ac_id="ACD-000",
            goal_summary="Summary text.",
            epic_name="Test",
        )

        assert len(data["tickets"]) == 2
        titles = [t["title"] for t in data["tickets"]]
        assert "Feature One" in titles
        assert "Feature Two" in titles
        source_acs = [t["source_ac"] for t in data["tickets"]]
        assert "ACD-001" in source_acs
        assert "ACD-002" in source_acs

    def test_collects_agents_from_needed_and_signed_off(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (agent assignments)
        """Only needed/signed_off agents are included; not_needed is excluded."""
        epic_folder = tmp_path / "EPIC-Agents"
        epic_folder.mkdir()
        _make_ticket(
            epic_folder, "01", "ticket-a", "Ticket A", "ACD-001",
            agents={"python-coder": "signed_off", "sql-coder": "not_needed", "commit": "needed"},
        )

        data = _collect_master_plan_data(
            epic_folder=epic_folder,
            topo_order=["ACD-001"],
            dep_graph={"ACD-001": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Agents",
        )

        assert "python-coder" in data["agents"]
        assert "commit" in data["agents"]
        assert "sql-coder" not in data["agents"]

    def test_collects_components(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (components)
        """Components from all ticket files are merged into a sorted list."""
        epic_folder = tmp_path / "EPIC-Components"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "t1", "T1", "ACD-001", components=["comp-b"])
        _make_ticket(epic_folder, "02", "t2", "T2", "ACD-002", components=["comp-a", "comp-b"])

        data = _collect_master_plan_data(
            epic_folder=epic_folder,
            topo_order=["ACD-001", "ACD-002"],
            dep_graph={"ACD-001": [], "ACD-002": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Components",
        )

        assert data["components"] == ["comp-a", "comp-b"]

    def test_master_plan_md_file_excluded_from_tickets(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (robustness)
        """Master_Plan.md file inside the epic folder is NOT counted as a ticket."""
        epic_folder = tmp_path / "EPIC-Exclusion"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "real-ticket", "Real Ticket", "ACD-001")
        # Simulate a pre-existing Master_Plan.md
        (epic_folder / "Master_Plan.md").write_text("---\nstatus: in_progress\n---\n", encoding="utf-8")

        data = _collect_master_plan_data(
            epic_folder=epic_folder,
            topo_order=["ACD-001"],
            dep_graph={"ACD-001": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Exclusion",
        )

        assert len(data["tickets"]) == 1


# ---------------------------------------------------------------------------
# _render_master_plan
# ---------------------------------------------------------------------------


class TestRenderMasterPlan:
    """Unit tests for _render_master_plan()."""

    def _make_data(self, **overrides: object) -> dict:
        base = {
            "goal_ac_id": "ACD-000",
            "goal_summary": "This epic builds the feature.",
            "epic_name": "MyFeature",
            "tickets": [
                {
                    "num": "01",
                    "file": "01_ticket-a.md",
                    "title": "Ticket A",
                    "source_ac": "ACD-001",
                    "depends_on": [],
                    "agents": ["python-coder"],
                },
                {
                    "num": "02",
                    "file": "02_ticket-b.md",
                    "title": "Ticket B",
                    "source_ac": "ACD-002",
                    "depends_on": ["ACD-001"],
                    "agents": ["python-coder", "commit"],
                },
            ],
            "agents": {"python-coder": ["01", "02"], "commit": ["02"]},
            "components": ["ac-driven-dev"],
            "dep_graph": {"ACD-001": [], "ACD-002": ["ACD-001"]},
            "topo_order": ["ACD-001", "ACD-002"],
        }
        base.update(overrides)
        return base

    def test_frontmatter_has_epic_name(self) -> None:
        # covers: ACD-1200a-7
        """Rendered content starts with YAML frontmatter containing epic_name."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert content.startswith("---\n")
        assert "epic_name: EPIC-MyFeature" in content

    def test_frontmatter_has_created_date(self) -> None:
        # covers: ACD-1200a-7
        """Frontmatter contains the created date."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "created: 2026-06-08" in content

    def test_frontmatter_has_status_in_progress(self) -> None:
        # covers: ACD-1200a-7
        """Frontmatter status is 'in_progress' for a freshly generated plan."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "status: in_progress" in content

    def test_frontmatter_has_source_ac(self) -> None:
        # covers: ACD-1200a-7
        """Frontmatter contains the source_ac (goal AC id)."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "source_ac: ACD-000" in content

    def test_goal_section_contains_summary(self) -> None:
        # covers: ACD-1200a-7
        """## Goal section contains the goal summary paragraph."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "## Goal" in content
        assert "This epic builds the feature." in content

    def test_tickets_section_contains_ticket_titles(self) -> None:
        # covers: ACD-1200a-7
        """## Tickets section contains each ticket title."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "## Tickets" in content
        assert "Ticket A" in content
        assert "Ticket B" in content

    def test_tickets_section_contains_source_ac_ids(self) -> None:
        # covers: ACD-1200a-7
        """## Tickets section contains the source AC IDs."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "ACD-001" in content
        assert "ACD-002" in content

    def test_dependencies_section_present(self) -> None:
        # covers: ACD-1200a-7
        """## Dependencies section is present in the rendered output."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "## Dependencies" in content

    def test_agent_assignments_section_present(self) -> None:
        # covers: ACD-1200a-7
        """## Agent Assignments section lists the assigned agents."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        assert "## Agent Assignments" in content
        assert "python-coder" in content

    def test_frontmatter_parseable_as_yaml(self) -> None:
        # covers: ACD-1200a-7
        """The YAML frontmatter block is syntactically valid."""
        content = _render_master_plan(self._make_data(), "2026-06-08")
        lines = content.splitlines()
        # Find frontmatter block
        assert lines[0] == "---"
        end_idx = next(i for i, line in enumerate(lines[1:], 1) if line == "---")
        fm_text = "\n".join(lines[1:end_idx])
        parsed = yaml.safe_load(fm_text)
        assert isinstance(parsed, dict)
        assert parsed.get("epic_name") == "EPIC-MyFeature"


# ---------------------------------------------------------------------------
# generate_master_plan (integration)
# ---------------------------------------------------------------------------


class TestGenerateMasterPlan:
    """ACD-1200a-7: generate_master_plan writes Master_Plan.md in the epic folder."""

    def _setup_epic_folder(self, tmp_path: Path) -> tuple[Path, list[str], dict]:
        """Create a minimal epic folder with two ticket stubs."""
        epic_folder = tmp_path / "EPIC-Test"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "ticket-a", "Ticket A", "ACD-001")
        _make_ticket(
            epic_folder, "02", "ticket-b", "Ticket B", "ACD-002",
            depends_on=["ACD-001"],
        )
        topo_order = ["ACD-001", "ACD-002"]
        dep_graph = {"ACD-001": [], "ACD-002": ["ACD-001"]}
        return epic_folder, topo_order, dep_graph

    def test_creates_master_plan_file(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7
        """Master_Plan.md is written at the root of the epic folder."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        result = generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary="The goal summary.",
            epic_name="Test",
        )

        assert result == (epic_folder / "Master_Plan.md").resolve()
        assert (epic_folder / "Master_Plan.md").exists()

    def test_master_plan_contains_goal_summary(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7
        """Master_Plan.md body includes the goal summary text."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary="Unique summary text for the goal.",
            epic_name="Test",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "Unique summary text for the goal." in content

    def test_master_plan_contains_ordered_ticket_list(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7
        """Master_Plan.md tickets section lists tickets with titles and AC IDs."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Test",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "Ticket A" in content
        assert "Ticket B" in content
        assert "ACD-001" in content
        assert "ACD-002" in content

    def test_master_plan_frontmatter_valid_yaml(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7
        """Frontmatter block in the generated Master_Plan.md is valid YAML."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Test",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        lines = content.splitlines()
        assert lines[0] == "---"
        end_idx = next(i for i, line in enumerate(lines[1:], 1) if line == "---")
        fm = yaml.safe_load("\n".join(lines[1:end_idx]))
        assert isinstance(fm, dict)
        assert fm.get("epic_name") == "EPIC-Test"
        assert fm.get("source_ac") == "ACD-000"

    def test_master_plan_uses_provided_created_date(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7
        """The created: frontmatter field reflects the provided date."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Test",
            created_date="2026-01-15",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "created: 2026-01-15" in content

    def test_master_plan_contains_dependency_graph(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (dependency graph section)
        """Dependencies section reflects the AC-level dep_graph."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Test",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "## Dependencies" in content

    def test_master_plan_contains_agent_assignments(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (agents section)
        """Agent Assignments section includes agents from the ticket files."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Test",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "## Agent Assignments" in content
        assert "python-coder" in content

    def test_overwrites_existing_master_plan(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (idempotency)
        """Calling generate_master_plan twice overwrites the first file."""
        epic_folder, topo_order, dep_graph = self._setup_epic_folder(tmp_path)

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary="First run.",
            epic_name="Test",
        )
        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=topo_order,
            dep_graph=dep_graph,
            goal_ac_id="ACD-000",
            goal_summary="Second run — updated.",
            epic_name="Test",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "Second run — updated." in content
        assert "First run." not in content

    def test_empty_dep_graph_renders_no_dependencies_note(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-7 (edge case: no deps)
        """When dep_graph has no edges, the dependencies section says so."""
        epic_folder = tmp_path / "EPIC-NoDeps"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "solo-ticket", "Solo Ticket", "ACD-001")

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=["ACD-001"],
            dep_graph={},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="NoDeps",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "No inter-ticket dependencies" in content


# ---------------------------------------------------------------------------
# Edge-case tests for generate_master_plan
# ---------------------------------------------------------------------------


class TestMasterPlanEdgeCases:
    """Edge-case tests for generate_master_plan() and its helpers."""

    # ------------------------------------------------------------------
    # Epic with zero tickets (empty ticket list)
    # ------------------------------------------------------------------

    def test_zero_tickets_produces_valid_master_plan(self, tmp_path: Path) -> None:
        """An epic folder with no ticket files produces a Master_Plan.md without crashing."""
        epic_folder = tmp_path / "EPIC-Empty"
        epic_folder.mkdir()
        # No ticket files in the folder.

        result = generate_master_plan(
            epic_folder=epic_folder,
            topo_order=[],
            dep_graph={},
            goal_ac_id="ACD-000",
            goal_summary="No tickets yet.",
            epic_name="Empty",
        )

        assert result.exists(), "Master_Plan.md must be written even with zero tickets"
        content = result.read_text(encoding="utf-8")
        assert "## Tickets" in content
        assert "No inter-ticket dependencies" in content

    def test_zero_tickets_table_has_header_only(self, tmp_path: Path) -> None:
        """With zero tickets the Tickets table header is present but has no data rows."""
        epic_folder = tmp_path / "EPIC-ZeroRows"
        epic_folder.mkdir()

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=[],
            dep_graph={},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="ZeroRows",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        lines = content.splitlines()
        # Find the table header line
        header_lines = [l for l in lines if "| # |" in l]
        assert header_lines, "Tickets table header must appear even with zero tickets"
        # Data rows in the table would start with "| " followed by a digit.
        data_rows = [l for l in lines if l.startswith("| ") and l[2].isdigit()]
        assert data_rows == [], (
            f"Expected zero ticket data rows, found: {data_rows}"
        )

    # ------------------------------------------------------------------
    # Epic with a single ticket that has no depends_on
    # ------------------------------------------------------------------

    def test_single_ticket_no_depends_on(self, tmp_path: Path) -> None:
        """A single ticket with no depends_on produces correct output."""
        epic_folder = tmp_path / "EPIC-Solo"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "solo-ticket", "Solo Ticket", "ACD-001",
                     depends_on=[])

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=["ACD-001"],
            dep_graph={"ACD-001": []},
            goal_ac_id="ACD-000",
            goal_summary="One ticket, no deps.",
            epic_name="Solo",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        assert "Solo Ticket" in content
        # The dep entry should show "no dependencies"
        assert "ACD-001 (no dependencies)" in content

    def test_single_ticket_depends_on_column_shows_dash(self, tmp_path: Path) -> None:
        """The Depends On column for a ticket with no deps shows '—'."""
        epic_folder = tmp_path / "EPIC-SoloDash"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "solo", "Solo", "ACD-001", depends_on=[])

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=["ACD-001"],
            dep_graph={"ACD-001": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="SoloDash",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        # The table row for ticket 01 should end with "| — |" (em-dash) when no deps.
        assert "| — |" in content or "| —\n" in content or " | — |" in content

    # ------------------------------------------------------------------
    # Ticket with depends_on referencing a nonexistent ticket
    # ------------------------------------------------------------------

    def test_depends_on_nonexistent_ticket_does_not_crash(self, tmp_path: Path) -> None:
        """A ticket that references a nonexistent AC in depends_on is handled gracefully."""
        epic_folder = tmp_path / "EPIC-BadDep"
        epic_folder.mkdir()
        # Ticket references "ACD-GHOST" which is not in the epic folder.
        _make_ticket(epic_folder, "01", "ticket-a", "Ticket A", "ACD-001",
                     depends_on=["ACD-GHOST"])

        # dep_graph also reflects a reference to a node outside the set.
        result = generate_master_plan(
            epic_folder=epic_folder,
            topo_order=["ACD-001"],
            dep_graph={"ACD-001": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="BadDep",
        )

        assert result.exists(), "Master_Plan.md must still be written"
        content = result.read_text(encoding="utf-8")
        # The depends_on reference from ticket frontmatter is passed through as-is.
        assert "ACD-GHOST" in content

    # ------------------------------------------------------------------
    # Ticket YAML files that are malformed / unparseable
    # ------------------------------------------------------------------

    def test_malformed_ticket_frontmatter_skips_gracefully(self, tmp_path: Path) -> None:
        """A ticket with malformed YAML frontmatter falls back to empty dict without crashing."""
        epic_folder = tmp_path / "EPIC-Malformed"
        epic_folder.mkdir()
        # Write a ticket whose frontmatter is broken YAML.
        malformed = epic_folder / "01_broken.md"
        malformed.write_text(
            "---\ntitle: [broken: yaml: content: here\n---\n\n# Body\n",
            encoding="utf-8",
        )

        # Should not raise; malformed frontmatter falls back to empty dict.
        result = generate_master_plan(
            epic_folder=epic_folder,
            topo_order=["ACD-BROKEN"],
            dep_graph={"ACD-BROKEN": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="Malformed",
        )

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "## Tickets" in content
        # The filename stem should appear as the title fallback.
        assert "01_broken" in content

    def test_ticket_with_no_frontmatter_uses_filename_as_title(self, tmp_path: Path) -> None:
        """A ticket file with no YAML frontmatter uses its filename stem as the title."""
        epic_folder = tmp_path / "EPIC-NoFM"
        epic_folder.mkdir()
        no_fm = epic_folder / "01_plain-ticket.md"
        no_fm.write_text("# Just a heading\nNo frontmatter.\n", encoding="utf-8")

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=["ACD-001"],
            dep_graph={},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="NoFM",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        # Title fallback: ticket_file.stem → "01_plain-ticket"
        assert "01_plain-ticket" in content

    # ------------------------------------------------------------------
    # Epic folder path that doesn't exist
    # ------------------------------------------------------------------

    def test_nonexistent_epic_folder_raises_oserror(self, tmp_path: Path) -> None:
        """Passing a non-existent epic_folder path raises OSError (cannot write file)."""
        nonexistent = tmp_path / "EPIC-DoesNotExist"
        # Do NOT create the folder.

        import pytest as _pytest
        with _pytest.raises(OSError):
            generate_master_plan(
                epic_folder=nonexistent,
                topo_order=[],
                dep_graph={},
                goal_ac_id="ACD-000",
                goal_summary=".",
                epic_name="DoesNotExist",
            )

    # ------------------------------------------------------------------
    # All tickets having the same component
    # ------------------------------------------------------------------

    def test_duplicate_components_deduplicated_in_frontmatter(self, tmp_path: Path) -> None:
        """When all tickets share the same component it appears only once in the plan."""
        epic_folder = tmp_path / "EPIC-SameComp"
        epic_folder.mkdir()
        _make_ticket(epic_folder, "01", "t1", "T1", "ACD-001", components=["shared-comp"])
        _make_ticket(epic_folder, "02", "t2", "T2", "ACD-002", components=["shared-comp"])
        _make_ticket(epic_folder, "03", "t3", "T3", "ACD-003", components=["shared-comp"])

        generate_master_plan(
            epic_folder=epic_folder,
            topo_order=["ACD-001", "ACD-002", "ACD-003"],
            dep_graph={"ACD-001": [], "ACD-002": [], "ACD-003": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="SameComp",
        )

        content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
        # "shared-comp" should appear as a component exactly once in the frontmatter list.
        fm_lines = content.split("---")[1].splitlines()
        comp_lines = [l for l in fm_lines if "shared-comp" in l]
        assert len(comp_lines) == 1, (
            f"Expected 'shared-comp' to appear once in frontmatter; "
            f"found {len(comp_lines)} times: {comp_lines}"
        )

    def test_all_same_component_collected_once_in_data(self, tmp_path: Path) -> None:
        """_collect_master_plan_data deduplicates components from repeated tickets."""
        epic_folder = tmp_path / "EPIC-SameCompData"
        epic_folder.mkdir()
        for prefix, name, ac in [("01", "ta", "ACD-001"), ("02", "tb", "ACD-002")]:
            _make_ticket(epic_folder, prefix, name, f"Ticket {ac}", ac,
                         components=["only-component"])

        data = _collect_master_plan_data(
            epic_folder=epic_folder,
            topo_order=["ACD-001", "ACD-002"],
            dep_graph={"ACD-001": [], "ACD-002": []},
            goal_ac_id="ACD-000",
            goal_summary=".",
            epic_name="SameCompData",
        )

        assert data["components"] == ["only-component"], (
            f"Expected ['only-component'], got {data['components']}"
        )
