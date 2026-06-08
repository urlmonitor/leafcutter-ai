"""
MODULE: test_goal_to_epic_master_plan
GOAL: Unit tests for the generate_master_plan() function and its helpers
    in goal_to_epic.py (ACD-1200a-8).
BUSINESS CONTEXT: Verifies that the EPIC folder assembly step produces a
    well-formed Master_Plan.md that /build-feature can parse to drive an epic.
ARCHITECTURE: Pure unit tests — use tmp_path to create ephemeral filesystem
    fixtures. No subprocess calls; import goal_to_epic directly.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from goal_to_epic import (  # noqa: E402
    _read_ac_criteria,
    _read_ticket_title,
    generate_master_plan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ticket(path: Path, title: str) -> None:
    """Write a minimal ticket file with YAML frontmatter containing title."""
    path.write_text(
        textwrap.dedent(f"""\
        ---
        title: {title}
        status: todo
        agents:
          python-coder: needed
        ---

        # {title}

        ## Sign-offs

        - [ ] python-coder
        """),
        encoding="utf-8",
    )


def _make_ac_yaml(path: Path, ac_id: str, criteria: str) -> None:
    """Write a minimal AC YAML file."""
    data = {
        "id": ac_id,
        "title": f"Title for {ac_id}",
        "criteria": criteria,
        "status": "active",
    }
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# _read_ticket_title tests
# ---------------------------------------------------------------------------


def test_read_ticket_title_returns_frontmatter_title(tmp_path):
    """_read_ticket_title extracts the title from valid YAML frontmatter."""
    ticket = tmp_path / "01_TICKET-foo.md"
    _make_ticket(ticket, "My Test Ticket")
    assert _read_ticket_title(ticket) == "My Test Ticket"


def test_read_ticket_title_falls_back_to_stem_on_missing_title(tmp_path):
    """_read_ticket_title returns the file stem when no title field exists."""
    ticket = tmp_path / "02_TICKET-bar.md"
    ticket.write_text("---\nstatus: todo\n---\n\n# bar\n", encoding="utf-8")
    # title field absent → stem fallback
    assert _read_ticket_title(ticket) == "02_TICKET-bar"


def test_read_ticket_title_falls_back_when_no_frontmatter(tmp_path):
    """_read_ticket_title returns the file stem when no frontmatter block exists."""
    ticket = tmp_path / "03_TICKET-baz.md"
    ticket.write_text("# Just some content\n", encoding="utf-8")
    assert _read_ticket_title(ticket) == "03_TICKET-baz"


def test_read_ticket_title_falls_back_on_missing_file(tmp_path):
    """_read_ticket_title returns the file stem gracefully when file is missing."""
    ticket = tmp_path / "04_TICKET-missing.md"
    # Do not create the file — OSError path
    result = _read_ticket_title(ticket)
    assert result == "04_TICKET-missing"


# ---------------------------------------------------------------------------
# _read_ac_criteria tests
# ---------------------------------------------------------------------------


def test_read_ac_criteria_returns_criteria_text(tmp_path):
    """_read_ac_criteria returns the criteria string for a known AC id."""
    store_root = tmp_path / "ac-store"
    store_root.mkdir()
    _make_ac_yaml(store_root / "ACD-1200a.yaml", "ACD-1200a", "Given X\nWhen Y\nThen Z")
    result = _read_ac_criteria("ACD-1200a", store_root)
    assert "Given X" in result
    assert "Then Z" in result


def test_read_ac_criteria_returns_empty_for_unknown_id(tmp_path):
    """_read_ac_criteria returns an empty string when the AC id is not in the store."""
    store_root = tmp_path / "ac-store"
    store_root.mkdir()
    result = _read_ac_criteria("ACD-NONEXISTENT", store_root)
    assert result == ""


def test_read_ac_criteria_skips_malformed_yaml(tmp_path):
    """_read_ac_criteria silently skips unreadable YAML files."""
    store_root = tmp_path / "ac-store"
    store_root.mkdir()
    bad_yaml = store_root / "broken.yaml"
    bad_yaml.write_text("id: [unclosed bracket\n", encoding="utf-8")
    result = _read_ac_criteria("ACD-1200a", store_root)
    assert result == ""


# ---------------------------------------------------------------------------
# generate_master_plan tests
# ---------------------------------------------------------------------------


def test_generate_master_plan_writes_file(tmp_path):
    """generate_master_plan creates a Master_Plan.md in the epic folder."""
    epic_folder = tmp_path / "EPIC-TestEpic"
    epic_folder.mkdir()

    t1 = epic_folder / "01_TICKET-alpha.md"
    t2 = epic_folder / "02_TICKET-beta.md"
    _make_ticket(t1, "Alpha Ticket")
    _make_ticket(t2, "Beta Ticket")

    plan_path = generate_master_plan(
        epic_folder=epic_folder,
        epic_name="TestEpic",
        source_ac_id="ACD-1200a",
        goal_criteria="Given a goal\nWhen executed\nThen epic is built",
        numbered_tickets=[t1, t2],
        dep_graph={"ACD-1200a-1": [], "ACD-1200a-2": ["ACD-1200a-1"]},
        leaf_ids=["ACD-1200a-1", "ACD-1200a-2"],
    )

    assert plan_path.exists()
    assert plan_path.name == "Master_Plan.md"


def test_generate_master_plan_contains_epic_name_and_source_ac(tmp_path):
    """Master_Plan.md includes the epic name and source AC id."""
    epic_folder = tmp_path / "EPIC-MyEpic"
    epic_folder.mkdir()
    t1 = epic_folder / "01_TICKET-a.md"
    _make_ticket(t1, "A Ticket")

    generate_master_plan(
        epic_folder=epic_folder,
        epic_name="MyEpic",
        source_ac_id="ACD-9999",
        goal_criteria="Some criteria",
        numbered_tickets=[t1],
        dep_graph={"ACD-9999-1": []},
        leaf_ids=["ACD-9999-1"],
    )

    content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
    assert "EPIC-MyEpic" in content
    assert "source_ac: ACD-9999" in content


def test_generate_master_plan_contains_criteria(tmp_path):
    """Master_Plan.md includes the goal criteria text."""
    epic_folder = tmp_path / "EPIC-CriteriaTest"
    epic_folder.mkdir()
    t1 = epic_folder / "01_TICKET-x.md"
    _make_ticket(t1, "X Ticket")

    criteria = "Given something\nWhen triggered\nThen outcome"
    generate_master_plan(
        epic_folder=epic_folder,
        epic_name="CriteriaTest",
        source_ac_id="ACD-0001",
        goal_criteria=criteria,
        numbered_tickets=[t1],
        dep_graph={"ACD-0001-1": []},
        leaf_ids=["ACD-0001-1"],
    )

    content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
    assert "Given something" in content
    assert "Then outcome" in content


def test_generate_master_plan_lists_tickets_with_titles(tmp_path):
    """Master_Plan.md lists all sub-ticket filenames with their titles."""
    epic_folder = tmp_path / "EPIC-ListTest"
    epic_folder.mkdir()
    t1 = epic_folder / "01_TICKET-first.md"
    t2 = epic_folder / "02_TICKET-second.md"
    _make_ticket(t1, "First Ticket Title")
    _make_ticket(t2, "Second Ticket Title")

    generate_master_plan(
        epic_folder=epic_folder,
        epic_name="ListTest",
        source_ac_id="ACD-0002",
        goal_criteria="criteria",
        numbered_tickets=[t1, t2],
        dep_graph={"ACD-0002-1": [], "ACD-0002-2": []},
        leaf_ids=["ACD-0002-1", "ACD-0002-2"],
    )

    content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
    assert "01_TICKET-first.md: First Ticket Title" in content
    assert "02_TICKET-second.md: Second Ticket Title" in content


def test_generate_master_plan_expresses_depends_on_as_filenames(tmp_path):
    """Master_Plan.md expresses dependency graph edges as ticket filenames."""
    epic_folder = tmp_path / "EPIC-DepTest"
    epic_folder.mkdir()
    t1 = epic_folder / "01_TICKET-base.md"
    t2 = epic_folder / "02_TICKET-dependent.md"
    _make_ticket(t1, "Base Ticket")
    _make_ticket(t2, "Dependent Ticket")

    generate_master_plan(
        epic_folder=epic_folder,
        epic_name="DepTest",
        source_ac_id="ACD-0003",
        goal_criteria="criteria",
        numbered_tickets=[t1, t2],
        dep_graph={
            "ACD-0003-1": [],
            "ACD-0003-2": ["ACD-0003-1"],
        },
        leaf_ids=["ACD-0003-1", "ACD-0003-2"],
    )

    content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
    assert "01_TICKET-base.md depends_on: []" in content
    assert "02_TICKET-dependent.md depends_on: [01_TICKET-base.md]" in content


def test_generate_master_plan_is_idempotent(tmp_path):
    """Calling generate_master_plan twice produces identical content."""
    epic_folder = tmp_path / "EPIC-IdempotentTest"
    epic_folder.mkdir()
    t1 = epic_folder / "01_TICKET-foo.md"
    _make_ticket(t1, "Foo Ticket")

    kwargs = dict(
        epic_folder=epic_folder,
        epic_name="IdempotentTest",
        source_ac_id="ACD-0004",
        goal_criteria="some criteria",
        numbered_tickets=[t1],
        dep_graph={"ACD-0004-1": []},
        leaf_ids=["ACD-0004-1"],
    )

    plan1 = generate_master_plan(**kwargs)
    mtime1 = plan1.stat().st_mtime

    plan2 = generate_master_plan(**kwargs)
    mtime2 = plan2.stat().st_mtime

    # Idempotent: file was not rewritten (mtime unchanged)
    assert mtime1 == mtime2
    assert plan1.read_text(encoding="utf-8") == plan2.read_text(encoding="utf-8")


def test_generate_master_plan_uses_fallback_when_no_criteria(tmp_path):
    """Master_Plan.md includes a fallback message when goal_criteria is empty."""
    epic_folder = tmp_path / "EPIC-NoCriteriaTest"
    epic_folder.mkdir()
    t1 = epic_folder / "01_TICKET-foo.md"
    _make_ticket(t1, "Foo Ticket")

    generate_master_plan(
        epic_folder=epic_folder,
        epic_name="NoCriteriaTest",
        source_ac_id="ACD-0005",
        goal_criteria="",
        numbered_tickets=[t1],
        dep_graph={"ACD-0005-1": []},
        leaf_ids=["ACD-0005-1"],
    )

    content = (epic_folder / "Master_Plan.md").read_text(encoding="utf-8")
    assert "No criteria text found" in content
    assert "ACD-0005" in content
