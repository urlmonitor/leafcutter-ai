"""
MODULE: unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py
GOAL: Behavioral coverage for ACS-200f-3 — when mark_ac_done.py reports an AC
    marked done, the record's own top-level ``work_status`` key really is
    ``done``, prose quoting ``work_status: todo`` is untouched, and every other
    line (including its line ending) is byte-identical.

=== The defect (KI-ACS-20260925-mark-ac-done-reports-success-without-writing-the-key) ===

``mark_ac_done`` did ``raw_text.replace("work_status: todo", "work_status: done", 1)``
— an unanchored substring replace — so a ``notes: |`` block quoting that text
above the real key was edited instead of the key, and the tool still printed
``marked <ID> work_status=done`` and exited 0. It also used ``read_text`` /
``write_text`` with default newline translation, so on Windows every LF line
was rewritten as CRLF.

=== Fixture authenticity ===

Every record is real bytes on disk in ``tmp_path``, written with an explicit
line ending, and the real CLI is run as a subprocess (``python mark_ac_done.py
--ac <ID> --ac-root <tmp store>``). Assertions read the file back as raw bytes
and re-parse it with ``yaml.safe_load``; nothing is mocked and no source is
grepped.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MARK_AC_DONE_CLI = _REPO_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"

_AC_ID = "ZZ-100a-1"

# The prose line quoting the literal sits ABOVE the real key, which is exactly
# the shape that made the unanchored replace edit the wrong occurrence.
_RECORD_LINES = [
    f"id: {_AC_ID}",
    "title: \"Synthetic AC whose prose quotes the key\"",
    "component: ac-store",
    "level: L2",
    "status: active",
    "notes: |",
    "  Reset to work_status: todo after the revert of the earlier fix.",
    "criteria: |",
    "  Given a record",
    "  When it is marked",
    "  Then it is done",
    "work_status: todo",
    "readiness: approved",
]
_KEY_INDEX = _RECORD_LINES.index("work_status: todo")


def _write_record(ac_root: Path, newline: str) -> Path:
    """Write the synthetic record to disk with an explicit line ending.

    Args:
        ac_root: Root of the synthetic AC store.
        newline: The line ending to use for every line (``"\\n"`` or ``"\\r\\n"``).

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "ac-store"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{_AC_ID}.yaml"
    path.write_bytes(newline.join(_RECORD_LINES).encode("utf-8") + newline.encode("utf-8"))
    return path


def _run_cli(ac_root: Path) -> subprocess.CompletedProcess:
    """Run the real mark_ac_done CLI against *ac_root*.

    Args:
        ac_root: Root of the synthetic AC store.

    Returns:
        The completed process, with text stdout/stderr captured.
    """
    return subprocess.run(
        [sys.executable, str(_MARK_AC_DONE_CLI), "--ac", _AC_ID, "--ac-root", str(ac_root)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _differing_line_indices(before: bytes, after: bytes) -> list[int]:
    """Return the indices of lines that differ byte-wise (line endings included).

    Args:
        before: Original file bytes.
        after: File bytes after the CLI ran.

    Returns:
        Sorted list of differing line indices; a length mismatch counts every
        extra index as differing.
    """
    old = before.splitlines(keepends=True)
    new = after.splitlines(keepends=True)
    width = max(len(old), len(new))
    return [
        i for i in range(width)
        if i >= len(old) or i >= len(new) or old[i] != new[i]
    ]


def test_prose_literal_above_key_is_untouched_and_key_flips(tmp_path: Path) -> None:
    """The real key flips to done; the prose quoting 'work_status: todo' does not change."""
    # covers: ACS-200f-3
    ac_root = tmp_path / "acs"
    path = _write_record(ac_root, "\n")
    before = path.read_bytes()

    result = _run_cli(ac_root)

    assert result.returncode == 0, result.stderr
    after = path.read_bytes()
    data = yaml.safe_load(after.decode("utf-8"))
    assert data["work_status"] == "done"
    assert "Reset to work_status: todo after the revert" in data["notes"]
    assert _differing_line_indices(before, after) == [_KEY_INDEX]


def test_crlf_record_stays_crlf_and_only_one_line_changes(tmp_path: Path) -> None:
    """A CRLF record keeps CRLF on every line; only the work_status line differs."""
    # covers: ACS-200f-3
    ac_root = tmp_path / "acs"
    path = _write_record(ac_root, "\r\n")
    before = path.read_bytes()

    result = _run_cli(ac_root)

    assert result.returncode == 0, result.stderr
    after = path.read_bytes()
    lines = after.splitlines(keepends=True)
    assert all(line.endswith(b"\r\n") for line in lines)
    assert b"\r\r\n" not in after
    assert _differing_line_indices(before, after) == [_KEY_INDEX]
    assert lines[_KEY_INDEX] == b"work_status: done\r\n"
    assert yaml.safe_load(after.decode("utf-8"))["work_status"] == "done"


def test_lf_record_stays_lf_and_only_one_line_changes(tmp_path: Path) -> None:
    """An LF record gains no CR bytes; only the work_status line differs."""
    # covers: ACS-200f-3
    ac_root = tmp_path / "acs"
    path = _write_record(ac_root, "\n")
    before = path.read_bytes()

    result = _run_cli(ac_root)

    assert result.returncode == 0, result.stderr
    after = path.read_bytes()
    assert b"\r" not in after
    assert _differing_line_indices(before, after) == [_KEY_INDEX]
    assert after.splitlines(keepends=True)[_KEY_INDEX] == b"work_status: done\n"
