"""
MODULE: tests/ac_store/test_mark_ac_done.py
GOAL: Verify that mark_ac_done.py correctly marks ACs as work_status: done,
      is idempotent, and rejects invalid inputs with appropriate exit codes.
BUSINESS CONTEXT: Ticket 03 AC-1 through AC-4. mark_ac_done.py is the closure
    mechanism that sets work_status: done on AC YAML files after a ticket is
    merged. Must handle --ticket and --ac modes, be idempotent, reject missing
    ACs, and reject tickets without source_ac field.
ARCHITECTURE: Integration tests using temporary fixture directories. Each test
    creates minimal AC YAML files and/or ticket markdown files, invokes
    mark_ac_done.py via subprocess, and asserts on the modified AC YAML and
    exit codes.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
MARK_SCRIPT = WORKTREE_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"


def _make_ac_yaml(ac_root: Path, ac_id: str, work_status: str = "todo") -> Path:
    """Create a minimal AC YAML file for testing."""
    ac_file = ac_root / f"{ac_id}.yaml"
    ac_data = {
        "id": ac_id,
        "status": "active",
        "work_status": work_status,
        "title": f"Test AC {ac_id}",
        "description": "A test acceptance criterion",
        "criteria": ["Given ... When ... Then ..."],
    }
    ac_file.write_text(yaml.dump(ac_data), encoding="utf-8")
    return ac_file


def _make_ticket_md(ticket_dir: Path, ticket_name: str, source_ac: str | None) -> Path:
    """Create a minimal ticket markdown file for testing."""
    ticket_file = ticket_dir / ticket_name
    frontmatter_lines = ["---", 'title: "Test Ticket"', "status: done"]
    if source_ac is not None:
        frontmatter_lines.append(f"source_ac: {source_ac}")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")
    frontmatter_lines.append("# Test Ticket")
    ticket_file.write_text("\n".join(frontmatter_lines), encoding="utf-8")
    return ticket_file


class TestMarkAcDoneViaTicketPath:
    def test_marks_done_via_ticket_path(self, tmp_path):
        # covers: ACD-600a-1
        """AC-1: mark_ac_done marks the source AC done given a ticket path."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        ac_file = _make_ac_yaml(ac_root, "ACS-100a-1", work_status="todo")

        ticket_dir = tmp_path / "tickets"
        ticket_dir.mkdir()
        ticket_file = _make_ticket_md(
            ticket_dir, "TICKET-20260605-ACS-100a-1.md", source_ac="ACS-100a-1"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ticket", str(ticket_file),
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"
        ac_data = yaml.safe_load(ac_file.read_text())
        assert ac_data["work_status"] == "done", f"Expected work_status=done, got {ac_data['work_status']}"
        assert "ACS-100a-1" in result.stdout
        assert "work_status=done" in result.stdout

    def test_marks_done_via_ac_id(self, tmp_path):
        # covers: ACD-600a-1
        """AC-1 (--ac mode): mark_ac_done marks an AC done given its ID directly."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        ac_file = _make_ac_yaml(ac_root, "ACS-100a-1", work_status="todo")

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "ACS-100a-1",
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"
        ac_data = yaml.safe_load(ac_file.read_text())
        assert ac_data["work_status"] == "done", f"Expected work_status=done, got {ac_data['work_status']}"


class TestMarkAcDoneIdempotent:
    def test_idempotent(self, tmp_path):
        # covers: ACD-600a-2
        """AC-2: mark_ac_done is idempotent — calling it on an already-done AC exits 0."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        _make_ac_yaml(ac_root, "ACS-100a-1", work_status="done")

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "ACS-100a-1",
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0 (idempotent), got {result.returncode}. stderr: {result.stderr}"
        assert "no-op" in result.stdout.lower() or "already" in result.stdout.lower(), \
            f"Expected no-op log line. stdout: {result.stdout}"


class TestMarkAcDoneRejectsInvalidInputs:
    def test_missing_ac_exits_1(self, tmp_path):
        # covers: ACD-600a-3
        """AC-3: mark_ac_done exits 1 and emits error when AC ID does not exist."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "NONEXISTENT",
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, f"Expected exit 1 for missing AC, got {result.returncode}"
        assert "NONEXISTENT" in result.stderr, f"Expected AC ID in stderr. stderr: {result.stderr}"
        assert "not found" in result.stderr.lower(), f"Expected 'not found' in stderr. stderr: {result.stderr}"

    def test_ticket_without_source_ac_exits_1(self, tmp_path):
        # covers: ACD-600a-4
        """AC-4: mark_ac_done exits 1 when ticket has no source_ac field."""
        ticket_dir = tmp_path / "tickets"
        ticket_dir.mkdir()
        ticket_file = _make_ticket_md(
            ticket_dir, "TICKET-20260605-manual.md", source_ac=None
        )

        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ticket", str(ticket_file),
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, f"Expected exit 1 for ticket without source_ac, got {result.returncode}"
        assert "source_ac" in result.stderr.lower(), \
            f"Expected 'source_ac' mentioned in stderr. stderr: {result.stderr}"


class TestMarkAcDoneDryRun:
    def test_dry_run_does_not_modify_file(self, tmp_path):
        # covers: ACD-600a-1
        """--dry-run flag must not modify the AC YAML file."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        ac_file = _make_ac_yaml(ac_root, "ACS-100a-1", work_status="todo")
        original_content = ac_file.read_text()

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "ACS-100a-1",
                "--ac-root", str(ac_root),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0 for dry-run, got {result.returncode}. stderr: {result.stderr}"
        assert ac_file.read_text() == original_content, \
            "Expected file unchanged after --dry-run, but file was modified"


# ---------------------------------------------------------------------------
# BO-202 (F6): a composite AC (covered_by holds child AC ids) is never marked
# done on diff evidence alone. Real temp store, real CLI, real check_done_proof.
# ---------------------------------------------------------------------------

CHECK_DONE_PROOF = WORKTREE_ROOT / "scripts" / "commit_guardian" / "check_done_proof.py"
_PARENT = "ZZ-202a"
_CHILD_A = "ZZ-202a-1"
_CHILD_B = "ZZ-202a-2"
_PASSING_TEST = "def test_synthetic_covering_test():\n    # covers: {ac_id}\n    assert 1 + 1 == 2\n"


def _write_ac(ac_root: Path, ac_id: str, work_status: str, covered_by: list[str]) -> Path:
    """Write a real AC record (serialized by yaml.safe_dump) into the temp store."""
    ac_root.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id, "title": f"Synthetic {ac_id}", "component": "ac-store",
        "level": "L2", "status": "active", "work_status": work_status,
        "readiness": "approved", "priority": "medium", "depends_on": [],
        "criteria": "Given a\nWhen b\nThen c\n", "covered_by": covered_by,
        "implemented_by": [], "superseded_by": None,
    }
    path = ac_root / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _write_covering_test(test_root: Path, ac_id: str) -> None:
    """Write a real passing pytest file carrying a covers tag for *ac_id*."""
    test_root.mkdir(parents=True, exist_ok=True)
    name = "test_" + ac_id.lower().replace("-", "_") + ".py"
    (test_root / name).write_text(_PASSING_TEST.format(ac_id=ac_id), encoding="utf-8")


def _run_mark(ac_root: Path, *extra: str, ac: str = _PARENT):
    """Run the real mark_ac_done CLI in a fresh process (no AC_ENFORCE_STRICT)."""
    env = {k: v for k, v in os.environ.items() if k != "AC_ENFORCE_STRICT"}
    env["LEAFCUTTER_AC_STORE_ROOT"] = str(ac_root)
    target = ["--ac", ac] if ac else []
    return subprocess.run(
        [sys.executable, str(MARK_SCRIPT), *target, "--ac-root", str(ac_root), *extra],
        capture_output=True, text=True, timeout=300, cwd=str(WORKTREE_ROOT), env=env, check=False,
    )


def _work_status(path: Path) -> str:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["work_status"]


class TestCompositeAcRule:
    def test_composite_with_todo_children_goes_in_progress(self, tmp_path):
        # covers: BO-202
        # angle: criterion
        """AC-3: a todo composite with unfinished children goes in_progress, exit 0, names them."""
        ac_root, test_root = tmp_path / "acceptance-criteria", tmp_path / "tests"
        parent = _write_ac(ac_root, _PARENT, "todo", [_CHILD_A, _CHILD_B])
        _write_ac(ac_root, _CHILD_A, "todo", [])
        _write_ac(ac_root, _CHILD_B, "todo", [])
        test_root.mkdir()

        result = _run_mark(ac_root, "--test-root", str(test_root))

        assert result.returncode == 0, result.stderr
        assert _work_status(parent) == "in_progress"
        output = result.stdout + result.stderr
        assert _CHILD_A in output and _CHILD_B in output

    def test_composite_with_all_children_proven_goes_done_and_passes_check_done_proof(self, tmp_path):
        # covers: BO-202
        # angle: real_artifact
        """AC-2: all children done and covered -> parent done; real check_done_proof accepts the store."""
        # green_at_baseline (guard): today's writer also marks this done.
        ac_root, test_root = tmp_path / "acceptance-criteria", tmp_path / "tests"
        parent = _write_ac(ac_root, _PARENT, "todo", [_CHILD_A, _CHILD_B])
        for child in (_CHILD_A, _CHILD_B):
            _write_ac(ac_root, child, "done", [])
            _write_covering_test(test_root, child)

        result = _run_mark(ac_root, "--test-root", str(test_root))

        assert result.returncode == 0, result.stdout + result.stderr
        assert _work_status(parent) == "done"
        proof = subprocess.run(
            [sys.executable, str(CHECK_DONE_PROOF), "--mode", "ci",
             "--ac-root", str(ac_root), "--test-root", str(test_root)],
            capture_output=True, text=True, timeout=120, cwd=str(WORKTREE_ROOT), check=False,
        )
        assert proof.returncode == 0, proof.stdout + proof.stderr
        assert _PARENT not in proof.stdout + proof.stderr

    def test_leaf_behaviour_is_unchanged(self, tmp_path):
        # covers: BO-202
        # angle: boundary
        """AC-5: a leaf (covered_by only a test path) is marked done as before, with and without --test-root."""
        # green_at_baseline (guard)
        for with_root in (False, True):
            base = tmp_path / ("with" if with_root else "without")
            ac_root, test_root = base / "acceptance-criteria", base / "tests"
            leaf = _write_ac(ac_root, _CHILD_A, "todo", ["tests/test_x.py"])
            extra: tuple[str, ...] = ()
            if with_root:
                _write_covering_test(test_root, _CHILD_A)
                extra = ("--test-root", str(test_root))
            result = _run_mark(ac_root, *extra, ac=_CHILD_A)
            assert result.returncode == 0, result.stdout + result.stderr
            assert f"marked {_CHILD_A} work_status=done" in result.stdout
            assert _work_status(leaf) == "done"

    def test_already_done_unproven_composite_is_refused(self, tmp_path):
        # covers: BO-202
        # angle: failure
        """AC-4: a done composite with an unproven child is refused (non-zero), file untouched."""
        ac_root, test_root = tmp_path / "acceptance-criteria", tmp_path / "tests"
        parent = _write_ac(ac_root, _PARENT, "done", [_CHILD_A, _CHILD_B])
        _write_ac(ac_root, _CHILD_A, "done", [])
        _write_covering_test(test_root, _CHILD_A)
        _write_ac(ac_root, _CHILD_B, "todo", [])
        before = parent.read_bytes()

        # Without --test-root (the finalize-feature call) and with it.
        for extra in ((), ("--test-root", str(test_root))):
            result = _run_mark(ac_root, *extra)
            assert result.returncode != 0, (extra, result.stdout + result.stderr)
            assert _CHILD_B in result.stdout + result.stderr
            assert parent.read_bytes() == before

    def test_composite_without_test_root_never_goes_done(self, tmp_path):
        # covers: BO-202
        # angle: failure
        """AC-5: called as finalize-feature does (--ticket, no --test-root) a composite is never written done."""
        ac_root = tmp_path / "acceptance-criteria"
        parent = _write_ac(ac_root, _PARENT, "todo", [_CHILD_A, _CHILD_B])
        _write_ac(ac_root, _CHILD_A, "done", [])
        _write_ac(ac_root, _CHILD_B, "todo", [])
        ticket = _make_ticket_md(tmp_path, "TICKET-20261006-composite.md", source_ac=_PARENT)

        result = _run_mark(ac_root, "--ticket", str(ticket), ac="")

        assert _work_status(parent) != "done", result.stdout + result.stderr
        assert _work_status(parent) == "in_progress"
        assert result.returncode == 0, result.stderr
        assert _CHILD_A in result.stdout + result.stderr

    def test_mark_ac_done_and_check_done_proof_share_one_composite_helper(self):
        # covers: BO-202
        # angle: seam
        """AC-1: both modules resolve _composite_child_ids to the same function object."""
        sys.path.insert(0, str(WORKTREE_ROOT / "scripts" / "ac_store"))
        sys.path.insert(0, str(WORKTREE_ROOT / "scripts" / "commit_guardian"))
        try:
            import check_done_proof
            import mark_ac_done
        finally:
            del sys.path[:2]
        assert hasattr(mark_ac_done, "_composite_child_ids"), "mark_ac_done must import the shared composite helper"
        assert mark_ac_done._composite_child_ids is check_done_proof._composite_child_ids
