"""
Tests for scripts/set_ticket_status.py — ticket status transition script.

These tests were written BEFORE the implementation exists (TDD red-baseline).
All tests are expected to fail with ImportError or AssertionError until
python-coder implements scripts/set_ticket_status.py.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Helper — build a minimal ticket file with specified frontmatter
# ---------------------------------------------------------------------------

_TICKET_TEMPLATE = """\
---
title: "Test Ticket"
status: {status}
components:
  - infrastructure
created: 2026-01-01
depends_on: []
agents:
{agents}
---

# Test ticket body
"""

_TICKET_TEMPLATE_NO_STATUS = """\
---
title: "Test Ticket"
components:
  - infrastructure
created: 2026-01-01
depends_on: []
agents:
  python-coder: signed_off
---

# Test ticket body (no status field)
"""


def _make_ticket(tmp_dir: Path, status: str, agents: str = "  python-coder: signed_off") -> Path:
    """Write a ticket file with the specified status and agents map.

    Args:
        tmp_dir: Temporary directory path to write the file into.
        status: The status value to set in frontmatter.
        agents: YAML agents block (indented).

    Returns:
        Path to the written ticket file.
    """
    content = _TICKET_TEMPLATE.format(status=status, agents=agents)
    ticket_path = tmp_dir / "test_ticket.md"
    ticket_path.write_text(content, encoding="utf-8")
    return ticket_path


def _make_ticket_no_status(tmp_dir: Path) -> Path:
    """Write a ticket file with no status field in frontmatter.

    Args:
        tmp_dir: Temporary directory path to write the file into.

    Returns:
        Path to the written ticket file.
    """
    ticket_path = tmp_dir / "test_ticket_no_status.md"
    ticket_path.write_text(_TICKET_TEMPLATE_NO_STATUS, encoding="utf-8")
    return ticket_path


def _run_script(ticket_path: Path, status: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run set_ticket_status.py as a subprocess.

    Args:
        ticket_path: Absolute path to the ticket file.
        status: Target status to set.
        extra_args: Optional additional CLI arguments (e.g. ["--force"]).

    Returns:
        CompletedProcess with returncode, stdout, stderr.
    """
    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "set_ticket_status.py"
    cmd = [sys.executable, str(script), "--ticket", str(ticket_path), "--status", status]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


class TestSetTicketStatusTransitions(unittest.TestCase):
    """Tests for basic status transition behavior of set_ticket_status.py."""

    def setUp(self) -> None:
        """Create a temporary directory for test ticket files."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self._tmp.cleanup()

    def test_todo_to_in_progress_updates_frontmatter(self) -> None:
        """BO-400b-1: Script updates frontmatter status from todo to in_progress.

        Given a ticket with status: todo, invoking with --status in_progress
        must rewrite the frontmatter status field and preserve all other content.
        """
        # covers: BO-400b-1
        # covers: BO-400a-1
        ticket = _make_ticket(self.tmp_dir, "todo")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: in_progress", content)
        self.assertNotIn("status: todo", content)
        self.assertIn("# Test ticket body", content)  # body preserved

    def test_same_status_is_noop(self) -> None:
        """BO-400b-2: Invoking with the current status is an idempotent no-op.

        Given status: in_progress, invoking with --status in_progress must exit 0,
        print "(no change)", and not modify the file.
        """
        # covers: BO-400b-2
        # covers: BO-400a-1-i
        ticket = _make_ticket(self.tmp_dir, "in_progress")
        mtime_before = ticket.stat().st_mtime
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        self.assertIn("no change", result.stdout.lower())
        mtime_after = ticket.stat().st_mtime
        self.assertEqual(mtime_before, mtime_after, "File should not be modified for no-op transition")

    def test_done_transition_blocked_by_needed_agents(self) -> None:
        """BO-400b-1-i: Script refuses done transition when agents have needed status.

        Given a ticket with test-runner: needed and commit: needed, invoking
        --status done without --force must exit 1 and not modify the file.
        """
        # covers: BO-400b-1-i
        # covers: BO-400a-2-i
        agents = "  test-runner: needed\n  commit: needed"
        ticket = _make_ticket(self.tmp_dir, "in_progress", agents=agents)
        content_before = ticket.read_text(encoding="utf-8")
        result = _run_script(ticket, "done")
        self.assertEqual(result.returncode, 1, f"Expected exit 1, got {result.returncode}")
        self.assertIn("Cannot set done", result.stdout + result.stderr)
        content_after = ticket.read_text(encoding="utf-8")
        self.assertEqual(content_before, content_after, "File must not be modified on rejected transition")

    def test_done_transition_forced_bypasses_parity(self) -> None:
        """BO-400b-1-i (--force): --force bypasses the parity check for done transition.

        Given a ticket with needed agents, --status done --force must exit 0
        and update status to done.
        """
        # covers: BO-400b-1-i
        agents = "  test-runner: needed\n  commit: needed"
        ticket = _make_ticket(self.tmp_dir, "in_progress", agents=agents)
        result = _run_script(ticket, "done", extra_args=["--force"])
        self.assertEqual(result.returncode, 0, f"Expected exit 0 with --force, got {result.returncode}. stderr: {result.stderr}")
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: done", content)

    def test_invalid_transition_rejected_without_force(self) -> None:
        """BO-400b-2: Invalid transitions (done -> in_progress) are rejected without --force.

        Script must exit 1 and print an error message about invalid transition.
        """
        # covers: BO-400b-2
        ticket = _make_ticket(self.tmp_dir, "done")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 1, f"Expected exit 1, got {result.returncode}")
        self.assertIn("Invalid transition", result.stdout + result.stderr)

    def test_missing_status_field_treated_as_todo(self) -> None:
        """BO-400b-2-i: Missing status field is treated as todo.

        Given a ticket with no status: field, invoking --status in_progress must
        insert status: in_progress and print the '(absent, treated as todo)' variant.
        """
        # covers: BO-400b-2-i
        ticket = _make_ticket_no_status(self.tmp_dir)
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: in_progress", content)
        output = result.stdout + result.stderr
        self.assertIn("absent", output.lower())

    def test_git_staging_on_success(self) -> None:
        """BO-400b-3: Successful update stages the modified file via git add.

        After a successful status update, git status --porcelain must show the
        ticket file as staged-modified (M in the index column).
        """
        # covers: BO-400b-3
        # This test requires a git repo context; skip if running outside git
        try:
            git_check = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                cwd=str(self.tmp_dir.parent.parent.parent),
            )
            if git_check.returncode != 0:
                self.skipTest("Not running inside a git repository")
        except FileNotFoundError:
            self.skipTest("git not available")

        ticket = _make_ticket(self.tmp_dir, "todo")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        git_status = subprocess.run(
            ["git", "status", "--porcelain", str(ticket)],
            capture_output=True,
            text=True,
            cwd=str(self.tmp_dir.parent.parent.parent),
        )
        # File should be staged (M in first column) after a successful update
        self.assertIn("M", git_status.stdout[:2], f"Expected staged file, got: {git_status.stdout!r}")

    def test_no_staging_on_noop(self) -> None:
        """BO-400b-3 (no-op): No staging on same-status no-op call.

        When the transition is a no-op (same status), git add must NOT be called
        and the file must not appear as staged.
        """
        # covers: BO-400b-3
        ticket = _make_ticket(self.tmp_dir, "in_progress")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        # On a no-op, the file is unchanged — it should not appear as staged
        # (if it was previously staged, it would appear as ' M'; if untracked, '??')
        git_status = subprocess.run(
            ["git", "status", "--porcelain", str(ticket)],
            capture_output=True,
            text=True,
            cwd=str(self.tmp_dir.parent.parent.parent),
        )
        # Either not staged (empty output) or untracked — not M in index column
        if git_status.stdout.strip():
            self.assertNotEqual("M", git_status.stdout[0], "File must not be staged on no-op")

    def test_no_staging_on_rejection(self) -> None:
        """BO-400b-3 (rejection): No staging on a rejected transition.

        When the transition is rejected (invalid), git add must NOT be called.
        """
        # covers: BO-400b-3
        ticket = _make_ticket(self.tmp_dir, "done")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 1, "Expected exit 1 for invalid transition")
        # File must not be staged after rejection
        git_status = subprocess.run(
            ["git", "status", "--porcelain", str(ticket)],
            capture_output=True,
            text=True,
            cwd=str(self.tmp_dir.parent.parent.parent),
        )
        if git_status.stdout.strip():
            self.assertNotEqual("M", git_status.stdout[0], "File must not be staged on rejection")


class TestSetTicketStatusArchiveAcs(unittest.TestCase):
    """Named tests for BO-400a and BO-400c ACs — archive-readiness and in-place update behaviors.

    These tests cover ACs that were previously unlinked to any named test (test backfill).
    The set_ticket_status.py script is already implemented; tests for BO-400a-2, BO-400a-3,
    BO-400c-1, BO-400c-4 verify its existing behavior. BO-400c-2 and BO-400c-2-i cover
    scan_epic_archive_readiness(), and the --scan-epic CLI mode that wires it into the
    finalize-feature-archive-check surface (review finding H-2).
    """

    def setUp(self) -> None:
        """Create a temporary directory for test ticket files."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self._tmp.cleanup()

    def test_ac_bo400a2_done_transition_succeeds_when_all_agents_signed_off(self) -> None:
        # covers: BO-400a-2
        """BO-400a-2: Script permits in_progress -> done without --force when all agents complete.

        Given a ticket with status: in_progress and all agents in {signed_off, not_needed},
        invoking --status done must exit 0 and write status: done to the frontmatter.
        """
        agents = "  python-coder: signed_off\n  test-runner: not_needed"
        ticket = _make_ticket(self.tmp_dir, "in_progress", agents=agents)
        result = _run_script(ticket, "done")
        self.assertEqual(
            result.returncode,
            0,
            f"Expected exit 0 for all-agents-complete done transition. stderr: {result.stderr}",
        )
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: done", content)
        self.assertNotIn("status: in_progress", content)

    def test_ac_bo400a3_status_read_from_frontmatter_not_folder_position(self) -> None:
        # covers: BO-400a-3
        """BO-400a-3: Status is read from YAML frontmatter, not inferred from folder position.

        A ticket file stored at the epic root (not in a done/ subfolder) but with
        frontmatter status: done must be recognized as status: done when parsed by
        the underlying _get_current_status() function.
        """
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        epic_root_ticket = self.tmp_dir / "01_ticket.md"
        epic_root_ticket.write_text(
            "---\ntitle: Root Ticket\nstatus: done\n---\n# body at epic root\n",
            encoding="utf-8",
        )
        content = epic_root_ticket.read_text(encoding="utf-8")
        parts = _sts._extract_frontmatter_block(content)
        self.assertIsNotNone(parts, "Expected to successfully parse frontmatter block")
        _, yaml_block, _ = parts  # type: ignore[misc]
        status = _sts._get_current_status(yaml_block)
        self.assertEqual(
            status,
            "done",
            "Status must be read from frontmatter status: field, not from folder position",
        )

    def test_ac_bo400c1_ticket_file_not_moved_to_done_subfolder(self) -> None:
        # covers: BO-400c-1
        """BO-400c-1: set_ticket_status.py does NOT move the ticket file to a done/ subfolder.

        After invoking with --status done the ticket file must remain at its original path.
        No done/ subfolder must be created by the script.
        """
        agents = "  python-coder: signed_off"
        ticket = _make_ticket(self.tmp_dir, "in_progress", agents=agents)
        original_path = ticket

        result = _run_script(ticket, "done")
        self.assertEqual(
            result.returncode,
            0,
            f"Expected exit 0 for done transition. stderr: {result.stderr}",
        )
        self.assertTrue(original_path.exists(), "Ticket must remain at its original path")
        done_subdir = self.tmp_dir / "done"
        self.assertFalse(done_subdir.exists(), "Script must NOT create a done/ subfolder")

    def test_ac_bo400c2_archive_readiness_reports_all_clear_when_all_done(self) -> None:
        # covers: BO-400c-2
        """BO-400c-2: scan_epic_archive_readiness() returns all_clear: true when all tickets done.

        Given an epic folder where all ticket files are at the root (no done/ subfolder)
        and every file has frontmatter status: done, the function must return:
          {all_clear: True, ok_count: 3, missing_count: 0, missing_tickets: []}
        Master_Plan.md must be excluded from the count.
        """
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        epic_dir = self.tmp_dir / "EPIC-Test"
        epic_dir.mkdir()
        for i in range(1, 4):
            (epic_dir / f"0{i}_ticket.md").write_text(
                f"---\ntitle: Ticket {i}\nstatus: done\n---\n# body\n",
                encoding="utf-8",
            )
        (epic_dir / "Master_Plan.md").write_text(
            "---\ntitle: Master Plan\n---\n# plan\n",
            encoding="utf-8",
        )

        result = _sts.scan_epic_archive_readiness(str(epic_dir))  # type: ignore[attr-defined]

        self.assertTrue(result["all_clear"], "Expected all_clear: True when all tickets done")
        self.assertEqual(result["ok_count"], 3)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["missing_tickets"], [])

    def test_ac_bo400c2i_mixed_state_both_root_and_done_subfolder_scanned(self) -> None:
        # covers: BO-400c-2-i
        """BO-400c-2-i: Mixed state — tickets in done/ subfolder and at root are BOTH scanned.

        Given:
          - done/01_ticket.md  with status: done  (legacy, already moved)
          - 02_ticket.md       with status: done  (new convention, at root)
          - 03_ticket.md       with status: in_progress (still active)
        scan_epic_archive_readiness() must return:
          {all_clear: False, ok_count: 2, missing_count: 1}
        with missing_tickets listing 03_ticket.md with current_status: in_progress.
        """
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        epic_dir = self.tmp_dir / "EPIC-Mixed"
        epic_dir.mkdir()
        done_dir = epic_dir / "done"
        done_dir.mkdir()

        (done_dir / "01_ticket.md").write_text(
            "---\ntitle: Ticket 1\nstatus: done\n---\n# legacy done\n",
            encoding="utf-8",
        )
        (epic_dir / "02_ticket.md").write_text(
            "---\ntitle: Ticket 2\nstatus: done\n---\n# root done\n",
            encoding="utf-8",
        )
        (epic_dir / "03_ticket.md").write_text(
            "---\ntitle: Ticket 3\nstatus: in_progress\n---\n# active\n",
            encoding="utf-8",
        )

        result = _sts.scan_epic_archive_readiness(str(epic_dir))  # type: ignore[attr-defined]

        self.assertFalse(result["all_clear"], "Expected all_clear: False — one ticket not done")
        self.assertEqual(result["ok_count"], 2)
        self.assertEqual(result["missing_count"], 1)
        missing_paths = [m["path"] for m in result["missing_tickets"]]
        self.assertTrue(
            any("03_ticket.md" in p for p in missing_paths),
            f"Expected 03_ticket.md in missing_tickets; got: {missing_paths}",
        )

    def test_ac_bo400c4_done_transition_uses_script_not_git_mv(self) -> None:
        # covers: BO-400c-4
        """BO-400c-4: Completion is expressed via set_ticket_status.py (not git mv).

        When invoking set_ticket_status.py to mark a ticket done, the file must be
        updated in-place. The file must remain at its original filesystem path —
        no git mv operation must be performed.
        """
        agents = "  python-coder: signed_off\n  test-runner: not_needed"
        ticket = _make_ticket(self.tmp_dir, "in_progress", agents=agents)
        original_name = ticket.name

        result = _run_script(ticket, "done")
        self.assertEqual(
            result.returncode,
            0,
            f"Expected exit 0. stderr: {result.stderr}",
        )
        self.assertTrue(ticket.exists(), "File must still exist at original path — no git mv")
        self.assertEqual(ticket.name, original_name, "Filename must not change — no git mv")
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: done", content)


class TestScanEpicArchiveReadinessHardening(unittest.TestCase):
    """Review-remediation tests for scan_epic_archive_readiness() (H-1, semantic parity).

    Covers the H-1 false-all-clear defect (a mistyped/non-existent epic path must not
    report ready) and the semantics the finalize-feature-archive-check skill documents
    but the original function did not implement: README.md exclusion, deferred-as-ready,
    and legacy done/ backward-compat.
    """

    def setUp(self) -> None:
        """Create a temporary directory for test epic folders."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self._tmp.cleanup()

    def test_nonexistent_epic_dir_raises_not_false_all_clear(self) -> None:
        # covers: BO-400c-2
        """H-1: a non-existent epic directory must raise, not return all_clear: True.

        The original implementation globbed a missing path (yielding nothing) and
        returned {all_clear: True}, giving a green archive signal for a typo. The
        hardened function raises FileNotFoundError so a mistyped path can never be
        mistaken for a ready-to-archive epic.
        """
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        missing = self.tmp_dir / "EPIC-DoesNotExist"
        self.assertFalse(missing.exists())
        with self.assertRaises(FileNotFoundError):
            _sts.scan_epic_archive_readiness(str(missing))

    def test_existing_empty_epic_dir_is_all_clear(self) -> None:
        # covers: BO-400c-2
        """An existing-but-empty epic dir stays all_clear: True (skill §4 contract).

        The H-1 fix targets non-existent paths only; a genuinely empty (but present)
        epic folder has nothing blocking archival and must still report ready.
        """
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        empty = self.tmp_dir / "EPIC-Empty"
        empty.mkdir()
        result = _sts.scan_epic_archive_readiness(str(empty))
        self.assertTrue(result["all_clear"])
        self.assertEqual(result["ok_count"], 0)
        self.assertEqual(result["missing_count"], 0)

    def test_readme_excluded_from_count(self) -> None:
        # covers: BO-400c-2
        """README.md is excluded from the readiness count (skill §2.1)."""
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        epic = self.tmp_dir / "EPIC-Readme"
        epic.mkdir()
        (epic / "01_ticket.md").write_text(
            "---\ntitle: T1\nstatus: done\n---\n# body\n", encoding="utf-8"
        )
        (epic / "README.md").write_text(
            "---\ntitle: Readme\n---\n# not a ticket\n", encoding="utf-8"
        )
        result = _sts.scan_epic_archive_readiness(str(epic))
        self.assertTrue(result["all_clear"], "README.md must not count as a missing ticket")
        self.assertEqual(result["ok_count"], 1)

    def test_deferred_counts_as_ready(self) -> None:
        # covers: BO-400c-2
        """status: deferred counts as ready-to-archive (skill §2.1)."""
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        epic = self.tmp_dir / "EPIC-Deferred"
        epic.mkdir()
        (epic / "01_ticket.md").write_text(
            "---\ntitle: T1\nstatus: done\n---\n# body\n", encoding="utf-8"
        )
        (epic / "02_ticket.md").write_text(
            "---\ntitle: T2\nstatus: deferred\n---\n# body\n", encoding="utf-8"
        )
        result = _sts.scan_epic_archive_readiness(str(epic))
        self.assertTrue(result["all_clear"], "deferred must count as ready")
        self.assertEqual(result["ok_count"], 2)
        self.assertEqual(result["missing_count"], 0)

    def test_legacy_done_subfolder_no_status_treated_done(self) -> None:
        # covers: BO-400c-2-i
        """A legacy done/ ticket with no status: field is treated as done (skill §4)."""
        import scripts.set_ticket_status as _sts  # type: ignore[import]

        epic = self.tmp_dir / "EPIC-LegacyDone"
        epic.mkdir()
        done_dir = epic / "done"
        done_dir.mkdir()
        (done_dir / "01_ticket.md").write_text(
            "---\ntitle: Legacy\n---\n# moved under old convention, no status field\n",
            encoding="utf-8",
        )
        (epic / "02_ticket.md").write_text(
            "---\ntitle: T2\nstatus: done\n---\n# body\n", encoding="utf-8"
        )
        result = _sts.scan_epic_archive_readiness(str(epic))
        self.assertTrue(
            result["all_clear"],
            "legacy done/ ticket without status: must be treated as done",
        )
        self.assertEqual(result["ok_count"], 2)


class TestScanEpicCli(unittest.TestCase):
    """H-2: exercise the wired --scan-epic CLI path, not just the bare function.

    The finalize-feature-archive-check skill invokes
    `set_ticket_status.py --scan-epic <dir>` and consumes its JSON stdout; these
    tests run that exact command so the wired call path — not only the library
    function — is covered.
    """

    def setUp(self) -> None:
        """Create a temporary directory for test epic folders."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self._tmp.cleanup()

    def _run_scan(self, epic_dir: Path) -> subprocess.CompletedProcess:
        """Run set_ticket_status.py --scan-epic as a subprocess."""
        script = Path(__file__).resolve().parent.parent.parent / "scripts" / "set_ticket_status.py"
        return subprocess.run(
            [sys.executable, str(script), "--scan-epic", str(epic_dir)],
            capture_output=True,
            text=True,
        )

    def test_cli_all_clear_exits_0_and_prints_json(self) -> None:
        # covers: BO-400c-2
        """--scan-epic on an all-done epic exits 0 and prints all_clear JSON."""
        import json as _json

        epic = self.tmp_dir / "EPIC-AllDone"
        epic.mkdir()
        for i in range(1, 3):
            (epic / f"0{i}_ticket.md").write_text(
                f"---\ntitle: T{i}\nstatus: done\n---\n# body\n", encoding="utf-8"
            )
        result = self._run_scan(epic)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        payload = _json.loads(result.stdout)
        self.assertTrue(payload["all_clear"])
        self.assertEqual(payload["ok_count"], 2)

    def test_cli_missing_ticket_exits_1(self) -> None:
        # covers: BO-400c-2-i
        """--scan-epic on an epic with a not-done ticket exits 1 and lists it."""
        import json as _json

        epic = self.tmp_dir / "EPIC-Mixed"
        epic.mkdir()
        (epic / "01_ticket.md").write_text(
            "---\ntitle: T1\nstatus: done\n---\n# body\n", encoding="utf-8"
        )
        (epic / "02_ticket.md").write_text(
            "---\ntitle: T2\nstatus: in_progress\n---\n# body\n", encoding="utf-8"
        )
        result = self._run_scan(epic)
        self.assertEqual(result.returncode, 1, f"stderr: {result.stderr}")
        payload = _json.loads(result.stdout)
        self.assertFalse(payload["all_clear"])
        self.assertEqual(payload["missing_count"], 1)
        missing_paths = [m["path"] for m in payload["missing_tickets"]]
        self.assertTrue(any("02_ticket.md" in p for p in missing_paths))

    def test_cli_nonexistent_dir_exits_2(self) -> None:
        # covers: BO-400c-2
        """H-1 at the CLI boundary: a non-existent epic dir exits 2, prints no JSON."""
        missing = self.tmp_dir / "EPIC-Typo"
        result = self._run_scan(missing)
        self.assertEqual(result.returncode, 2, f"stdout: {result.stdout}")
        self.assertNotIn("all_clear", result.stdout)
        self.assertIn("does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 12:00 [test-writer/BO-400]: Red-baseline tests written before
  set_ticket_status.py exists. All tests expected to fail with FileNotFoundError
  (script absent) or non-zero returncode assertions until python-coder implements
  scripts/set_ticket_status.py per BO-400b spec.
====================================================================
"""
