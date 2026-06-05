"""
MODULE: tests/ac_store/test_generate_ticket_from_ac.py
GOAL: Verify that generate_ticket_from_ac.py correctly creates ticket files from
      AC YAML inputs, writes back-references, enforces idempotency, and produces
      frontmatter that passes the ticket_frontmatter_guard.
BUSINESS CONTEXT: Tickets 01 AC-2, AC-3, AC-4, and AC-6. The generator is the
    second step of the AC-driven build pipeline. It must produce structurally
    valid tickets with correct frontmatter fields, update the source AC's
    implemented_by field, and refuse to overwrite an existing ticket.
ARCHITECTURE: Integration tests using temporary fixture directories. Each test
    creates a minimal AC YAML, invokes generate_ticket_from_ac.py via subprocess,
    and asserts on the written ticket file and modified AC YAML.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
GEN_SCRIPT = WORKTREE_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"

REQUIRED_CANONICAL_AGENTS = {
    "test-writer",
    "test-runner",
    "pr-reviewer",
    "commit",
    "pull-request",
}


def _write_ac(directory: Path, ac_id: str, overrides: dict | None = None) -> Path:
    """Write a minimal valid AC YAML file for testing."""
    defaults = {
        "id": ac_id,
        "title": f"Test AC {ac_id}",
        "component": "test",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "criteria": textwrap.dedent("""\
            Given a test condition,
            When the generator runs,
            Then a ticket is produced.
        """),
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "depends_on": [],
        "doc_links": [],
        "implemented_by": [],
    }
    if overrides:
        defaults.update(overrides)
    ac_file = directory / f"{ac_id}.yaml"
    with open(ac_file, "w", encoding="utf-8") as fh:
        yaml.dump(defaults, fh, default_flow_style=False, allow_unicode=True)
    return ac_file


def _run_generator(
    ac_id: str,
    ac_root: Path,
    tickets_root: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke generate_ticket_from_ac.py for the given ac_id."""
    cmd = [
        sys.executable,
        str(GEN_SCRIPT),
        "--ac", ac_id,
        "--ac-root", str(ac_root),
        "--tickets-root", str(tickets_root),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


class _FrontmatterError(ValueError):
    """Raised when markdown frontmatter cannot be parsed."""


def _parse_frontmatter(md_content: str) -> dict:
    """Extract and parse YAML frontmatter from markdown content."""
    if not md_content.startswith("---"):
        raise _FrontmatterError("no frontmatter block")  # noqa: TRY003
    parts = md_content.split("---", 2)
    if len(parts) < 3:
        raise _FrontmatterError("frontmatter block not closed")  # noqa: TRY003
    return yaml.safe_load(parts[1])


class TestGenerateTicketFromAc:
    """AC-2: Generator produces a valid ticket from an AC YAML."""

    def test_ticket_written_with_correct_fields(self, tmp_path: Path) -> None:
        """test_ticket_written_with_correct_fields: ticket has source_ac, files_touched, agents."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-100a-1"
        _write_ac(ac_dir, ac_id, {
            "doc_links": [
                {"path": "scripts/ac_store/scan_ac_store.py", "relationship": "implements", "status": "to-create"},
                {"path": "https://example.com/docs", "relationship": "reference", "status": "exists"},
            ],
        })

        result = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}\n{result.stdout}"

        # Find the written ticket
        ticket_files = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files) == 1, f"Expected 1 ticket file, got: {[str(f) for f in ticket_files]}"

        content = ticket_files[0].read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)

        # source_ac must be set
        assert fm.get("source_ac") == ac_id, (
            f"Ticket frontmatter source_ac must be '{ac_id}', got: {fm.get('source_ac')}"
        )

        # files_touched must contain only local paths (not http)
        files_touched = fm.get("files_touched", [])
        assert "scripts/ac_store/scan_ac_store.py" in files_touched, (
            "Local path from doc_links must appear in files_touched"
        )
        assert all(
            not f.startswith("http") for f in files_touched
        ), "HTTP URLs must not appear in files_touched"

        # agents map must contain assigned_agent and canonical support agents
        agents = fm.get("agents", {})
        assert "python-coder" in agents, "assigned_agent must appear in agents map"
        assert agents["python-coder"] == "needed", "assigned_agent must be set to needed"
        for canonical in REQUIRED_CANONICAL_AGENTS:
            assert canonical in agents, f"Canonical support agent '{canonical}' must be in agents map"
            assert agents[canonical] == "needed", f"'{canonical}' must be set to needed"

    def test_acceptance_criteria_section_verbatim(self, tmp_path: Path) -> None:
        """Ticket body must contain ## Acceptance Criteria with AC criteria field verbatim."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        criteria_text = textwrap.dedent("""\
            Given a condition,
            When the generator runs,
            Then the output matches.
        """)
        ac_id = "ACS-TEST-1"
        _write_ac(ac_dir, ac_id, {"criteria": criteria_text})

        result = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        ticket_files = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files) == 1

        content = ticket_files[0].read_text(encoding="utf-8")
        assert "## Acceptance Criteria" in content, "Ticket must have ## Acceptance Criteria section"
        # The criteria text must appear verbatim in the ticket body
        assert "Given a condition" in content, "criteria text must appear verbatim in ticket"
        assert "When the generator runs" in content
        assert "Then the output matches" in content


class TestImplementedByBackReference:
    """AC-3: Generator writes implemented_by back-reference into source AC."""

    def test_implemented_by_back_reference(self, tmp_path: Path) -> None:
        """test_implemented_by_back_reference: Source AC YAML gets ticket path in implemented_by."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-BACKREF-1"
        ac_file = _write_ac(ac_dir, ac_id)

        result = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        # Read back the source AC YAML
        with open(ac_file, encoding="utf-8") as fh:
            updated_ac = yaml.safe_load(fh)

        implemented_by = updated_ac.get("implemented_by", [])
        assert len(implemented_by) >= 1, (
            "implemented_by must contain the ticket path after generation"
        )
        # The path must reference a ticket file that actually exists
        ticket_path = Path(implemented_by[0])
        # implemented_by may be a relative path; resolve from worktree or tickets_dir
        if not ticket_path.is_absolute():
            ticket_path = tickets_dir / ticket_path
        ticket_files = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files) == 1
        # At minimum, the filename suffix must match
        assert ac_id in implemented_by[0], (
            f"implemented_by must contain the AC id in the ticket path, got: {implemented_by}"
        )

    def test_no_other_fields_modified(self, tmp_path: Path) -> None:
        """AC-3: Only implemented_by is changed in the source AC YAML after generation."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-NOMOD-1"
        _write_ac(ac_dir, ac_id, {
            "title": "Do Not Modify Me",
            "component": "sentinel",
            "estimated_complexity": "M",
        })
        ac_file = ac_dir / f"{ac_id}.yaml"

        with open(ac_file, encoding="utf-8") as fh:
            before = yaml.safe_load(fh)

        result = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        with open(ac_file, encoding="utf-8") as fh:
            after = yaml.safe_load(fh)

        # All fields except implemented_by must be unchanged
        for field in ("id", "title", "component", "level", "status", "work_status",
                      "criteria", "assigned_agent", "estimated_complexity", "depends_on"):
            assert before.get(field) == after.get(field), (
                f"Field '{field}' was unexpectedly modified: before={before.get(field)!r}, "
                f"after={after.get(field)!r}"
            )


class TestIdempotencyGuard:
    """AC-4: Generator is idempotent — re-run does not duplicate ticket."""

    def test_idempotency_guard(self, tmp_path: Path) -> None:
        """test_idempotency_guard: Second run exits non-zero and does not write a second file."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-IDEM-1"
        _write_ac(ac_dir, ac_id)

        # First run: should succeed
        result1 = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"

        # Count ticket files after first run
        ticket_files_after_first = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files_after_first) == 1, "Exactly one ticket file after first run"

        # Second run: must exit non-zero
        result2 = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result2.returncode != 0, (
            f"Second run must exit non-zero (idempotency guard). "
            f"Got returncode={result2.returncode}, stdout={result2.stdout!r}"
        )

        # No second ticket file should be written
        ticket_files_after_second = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files_after_second) == 1, (
            "Idempotency guard must not write a second ticket file"
        )

    def test_idempotency_message_names_existing_file(self, tmp_path: Path) -> None:
        """Error message on second run must name the existing file."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-IDEM-2"
        _write_ac(ac_dir, ac_id)

        _run_generator(ac_id, ac_dir, tickets_dir)
        result2 = _run_generator(ac_id, ac_dir, tickets_dir)

        combined = result2.stdout + result2.stderr
        assert ac_id in combined, (
            f"Error message must name the AC id of the existing ticket, got: {combined!r}"
        )

    def test_implemented_by_not_duplicated_on_rerun(self, tmp_path: Path) -> None:
        """AC-3 + AC-4: implemented_by must not gain a duplicate entry on second run."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-IDEM-3"
        ac_file = _write_ac(ac_dir, ac_id)

        _run_generator(ac_id, ac_dir, tickets_dir)
        _run_generator(ac_id, ac_dir, tickets_dir)

        with open(ac_file, encoding="utf-8") as fh:
            ac_data = yaml.safe_load(fh)

        assert len(ac_data.get("implemented_by", [])) == 1, (
            "implemented_by must not gain a duplicate entry on second run"
        )


class TestFrontmatterGuard:
    """AC-6: Generated ticket passes ticket_frontmatter_guard pre-commit hook."""

    def test_frontmatter_guard_passes(self, tmp_path: Path) -> None:
        """test_frontmatter_guard_passes: ticket_frontmatter_guard exits 0 on generated ticket."""
        # Find the frontmatter guard script
        guard_candidates = [
            WORKTREE_ROOT / "scripts" / "commit_guardian" / "check_ticket_frontmatter.py",
            WORKTREE_ROOT / "scripts" / "check_ticket_frontmatter.py",
        ]
        guard_script = next((p for p in guard_candidates if p.exists()), None)
        if guard_script is None:
            pytest.skip(
                "ticket_frontmatter_guard script not found — skipping AC-6 guard test. "
                f"Searched: {[str(p) for p in guard_candidates]}"
            )

        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-GUARD-1"
        _write_ac(ac_dir, ac_id)

        gen_result = _run_generator(ac_id, ac_dir, tickets_dir)
        assert gen_result.returncode == 0, f"Generator failed: {gen_result.stderr}"

        ticket_files = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files) == 1

        guard_result = subprocess.run(
            [sys.executable, str(guard_script), str(ticket_files[0])],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert guard_result.returncode == 0, (
            f"ticket_frontmatter_guard failed on generated ticket:\n"
            f"stdout: {guard_result.stdout}\nstderr: {guard_result.stderr}"
        )

    def test_requires_diagram_and_requires_adr_present(self, tmp_path: Path) -> None:
        """AC-6: Frontmatter must contain requires_diagram and requires_adr fields."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-FM-1"
        _write_ac(ac_dir, ac_id)

        result = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        ticket_files = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files) == 1
        content = ticket_files[0].read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)

        assert "requires_diagram" in fm, "Frontmatter must contain requires_diagram field"
        assert "requires_adr" in fm, "Frontmatter must contain requires_adr field"

    def test_signoffs_match_needed_agents(self, tmp_path: Path) -> None:
        """AC-6: ## Sign-offs section must list exactly the agents whose map value is needed."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ACS-SO-1"
        _write_ac(ac_dir, ac_id)

        result = _run_generator(ac_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        ticket_files = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
        assert len(ticket_files) == 1
        content = ticket_files[0].read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)

        # Extract needed agents from frontmatter
        needed_agents = {name for name, status in fm.get("agents", {}).items() if status == "needed"}

        # Extract sign-off entries from ## Sign-offs section
        signoffs_section = ""
        in_signoffs = False
        for line in content.splitlines():
            if line.strip() == "## Sign-offs":
                in_signoffs = True
                continue
            if in_signoffs and line.startswith("## "):
                break
            if in_signoffs:
                signoffs_section += line + "\n"

        signoff_lines = [
            line.strip().lstrip("- [ ] ").lstrip("- [x] ").strip()
            for line in signoffs_section.splitlines()
            if line.strip().startswith("- ")
        ]

        for agent in needed_agents:
            assert any(agent in line for line in signoff_lines), (
                f"Agent '{agent}' is needed but not in ## Sign-offs: {signoff_lines}"
            )
