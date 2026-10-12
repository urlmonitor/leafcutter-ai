"""
MODULE: unit_tests/feedback/test_submit_feedback_sink_report.py
GOAL: Prove that every successful submit_feedback.py run names, on stderr, the
      resolved absolute file its record was appended to -- while the stdout
      feedback-id contract and the stderr sidecar id-recovery fallback stay
      exactly as callers parse them today.
BUSINESS CONTEXT: KI-FC-001 measured 787 feedback records spread over 18
      feedback.jsonl files, with 1 in the sink people check. Nothing at the
      call site said which file a submission went to, so the split stayed
      invisible for four months. AC INF-500d-4-ii.
ARCHITECTURE: Every test runs the REAL script entry point
      (templates/scripts/feedback/submit_feedback.py, the canonical source) as
      a subprocess and reads its actual stdout/stderr. Each run's cwd, --jsonl
      target and TMPDIR (where the sidecar lands) are inside pytest's tmp_path,
      so no test writes into a real workspace sink or leaves a cwd-relative
      file in a checkout. No build.py is spawned.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "feedback" / "submit_feedback.py"
_SOURCE_CATEGORIES = _REPO_ROOT / "templates" / "config" / "feedback_categories.yaml"

_SINK_PREFIX = "[submit_feedback] sink: "
_FEEDBACK_ID_RE = re.compile(r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$")
# The exact pattern the signoff skill (§2a Call 2) and live-surface-tester grep
# stderr with to recover the id when stdout capture fails (KI-FC-002).
_SIDECAR_GREP_RE = re.compile(r"sidecar:[^ ]*feedback_id_[0-9]*.txt")
# The literal relative override ticket-supervisor.md passes to every call.
_TICKET_SUPERVISOR_JSONL = "debugging/logs/feedback.jsonl"


def _run(script: Path, cwd: Path, tmpdir: Path, jsonl: str | None) -> subprocess.CompletedProcess:
    """Run one agent-mode submission and return the completed process."""
    args = [
        sys.executable, str(script),
        "--ticket", "tickets/00_inbox/TICKET-sink-report-probe.md",
        "--phase", "python-coder",
        "--category", "complete",
        "--note", "sink report probe",
    ]
    if jsonl is not None:
        args += ["--jsonl", jsonl]
    env = dict(os.environ, TMPDIR=str(tmpdir))
    return subprocess.run(args, capture_output=True, text=True, timeout=60, cwd=str(cwd), env=env)


def _sink_lines(stderr: str) -> list[str]:
    """Return the stderr lines that carry the sink report."""
    return [line for line in stderr.splitlines() if line.startswith(_SINK_PREFIX)]


def _dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create and return (cwd, tmpdir) scratch directories under tmp_path."""
    work = tmp_path / "work"
    tmpdir = tmp_path / "tmpdir"
    work.mkdir()
    tmpdir.mkdir()
    return work, tmpdir


class TestSinkIsReported:
    """INF-500d-4-ii: the resolved absolute sink is named on every successful run."""

    def test_relative_jsonl_override_reports_resolved_absolute_sink(self, tmp_path: Path) -> None:
        # covers: INF-500d-4-ii
        work, tmpdir = _dirs(tmp_path)
        result = _run(_SOURCE_SCRIPT, work, tmpdir, _TICKET_SUPERVISOR_JSONL)
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

        lines = _sink_lines(result.stderr)
        assert len(lines) == 1, f"expected exactly one sink line on stderr, got: {result.stderr!r}"
        reported = Path(lines[0][len(_SINK_PREFIX):])
        expected = (work / _TICKET_SUPERVISOR_JSONL).resolve()
        assert reported.is_absolute(), f"sink path is not absolute: {reported}"
        assert reported == expected, f"reported {reported}, record went to {expected}"
        assert result.stdout.strip() in reported.read_text(encoding="utf-8")

    def test_default_sink_is_reported(self, tmp_path: Path) -> None:
        # covers: INF-500d-4-ii
        work, tmpdir = _dirs(tmp_path)
        project = tmp_path / "proj"
        (project / ".claude").mkdir(parents=True)
        deployed = project / ".leafcutter" / "scripts" / "feedback" / "submit_feedback.py"
        deployed.parent.mkdir(parents=True)
        shutil.copy2(_SOURCE_SCRIPT, deployed)
        config_dir = project / ".leafcutter" / "config"
        config_dir.mkdir(parents=True)
        shutil.copy2(_SOURCE_CATEGORIES, config_dir / "feedback_categories.yaml")

        result = _run(deployed, work, tmpdir, None)
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

        lines = _sink_lines(result.stderr)
        assert len(lines) == 1, f"expected exactly one sink line on stderr, got: {result.stderr!r}"
        reported = Path(lines[0][len(_SINK_PREFIX):])
        expected = (project / "debugging" / "logs" / "feedback.jsonl").resolve()
        assert reported == expected, f"reported {reported}, default sink is {expected}"
        assert result.stdout.strip() in reported.read_text(encoding="utf-8")


class TestExistingCallerContractsUnchanged:
    """INF-500d-4-ii: the id on stdout and the sidecar fallback on stderr still parse."""

    def test_stdout_is_exactly_the_feedback_id(self, tmp_path: Path) -> None:
        # covers: INF-500d-4-ii
        work, tmpdir = _dirs(tmp_path)
        result = _run(_SOURCE_SCRIPT, work, tmpdir, _TICKET_SUPERVISOR_JSONL)
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

        assert result.stdout.endswith("\n")
        stdout_lines = result.stdout.splitlines()
        assert len(stdout_lines) == 1, f"stdout must be the id alone, got: {result.stdout!r}"
        assert _FEEDBACK_ID_RE.match(stdout_lines[0]), f"not a feedback id: {stdout_lines[0]!r}"
        assert "sink" not in result.stdout
        assert "feedback.jsonl" not in result.stdout

    def test_sidecar_recovery_pattern_still_finds_only_the_sidecar(self, tmp_path: Path) -> None:
        # covers: INF-500d-4-ii
        work, tmpdir = _dirs(tmp_path)
        result = _run(_SOURCE_SCRIPT, work, tmpdir, _TICKET_SUPERVISOR_JSONL)
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

        # grep -o semantics: matched per line, every match returned.
        matches = [m for line in result.stderr.splitlines() for m in _SIDECAR_GREP_RE.findall(line)]
        assert len(matches) == 1, f"sidecar grep must find exactly one path, got {matches!r}"
        sidecar = Path(matches[0][len("sidecar:"):])
        assert sidecar.read_text(encoding="utf-8") == result.stdout.strip()
        # The first match (live-surface-tester pipes through `head -1`) is the sidecar.
        for line in _sink_lines(result.stderr):
            assert not _SIDECAR_GREP_RE.search(line), f"sink line matches the sidecar grep: {line!r}"
        assert _sink_lines(result.stderr), "sink line missing, so this check proved nothing"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-08 [quick-fix/INF-500d-4-ii]: Initial tests. Run the real source
#   script as a subprocess; the relative-override case uses the literal
#   --jsonl ticket-supervisor.md passes, the default case runs a copied
#   deployed layout so no test touches a real sink. (#INF-500d-4-ii)
# ====================================================================
