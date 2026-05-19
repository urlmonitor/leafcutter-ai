"""Unit tests for onboarding agent environment detection logic.

Tests use mock subprocess/file states to verify detection logic without
requiring a real Docker daemon, database, or Poetry environment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Inline environment detection helpers (mirrors onboarding-agent logic)
# ---------------------------------------------------------------------------

def detect_docker_state(run_fn: Any = None) -> dict[str, Any]:
    """Detect Docker Compose service state.

    Args:
        run_fn: Callable for subprocess.run (injectable for testing).

    Returns:
        Dict with 'running' (bool) and 'services' (list of str).
    """
    run_fn = run_fn or subprocess.run
    try:
        result = run_fn(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"running": True, "services": result.stdout.strip().splitlines()}
        return {"running": False, "services": []}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"running": False, "services": []}


def detect_env_file(project_root: Path) -> bool:
    """Check if .env file exists at project_root.

    Args:
        project_root: Project root directory.

    Returns:
        True if .env file exists.
    """
    return (project_root / ".env").exists()


def detect_poetry_state(run_fn: Any = None) -> dict[str, Any]:
    """Check Poetry dependency state.

    Args:
        run_fn: Callable for subprocess.run (injectable for testing).

    Returns:
        Dict with 'ok' (bool) and 'message' (str).
    """
    run_fn = run_fn or subprocess.run
    try:
        result = run_fn(
            ["poetry", "check"],
            capture_output=True, text=True, timeout=30
        )
        ok = result.returncode == 0
        return {"ok": ok, "message": result.stdout.strip() or result.stderr.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"ok": False, "message": "Poetry not found"}


def detect_alembic_state(run_fn: Any = None) -> dict[str, Any]:
    """Check Alembic migration state.

    Args:
        run_fn: Callable for subprocess.run (injectable for testing).

    Returns:
        Dict with 'at_head' (bool) and 'current' (str).
    """
    run_fn = run_fn or subprocess.run
    try:
        result = run_fn(
            ["poetry", "run", "alembic", "current"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"at_head": False, "current": "error"}
        at_head = "(head)" in result.stdout
        return {"at_head": at_head, "current": result.stdout.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"at_head": False, "current": "unavailable"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDockerDetection:
    """Tests for detect_docker_state()."""

    def test_docker_running(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(
            returncode=0, stdout='{"Service":"timescaledb","State":"running"}'
        ))
        result = detect_docker_state(run_fn=mock_run)
        assert result["running"] is True

    def test_docker_down(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        result = detect_docker_state(run_fn=mock_run)
        assert result["running"] is False

    def test_docker_not_installed(self) -> None:
        mock_run = MagicMock(side_effect=FileNotFoundError)
        result = detect_docker_state(run_fn=mock_run)
        assert result["running"] is False
        assert result["services"] == []


class TestEnvFileDetection:
    """Tests for detect_env_file()."""

    def test_env_file_present(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("DB=test\n")
        assert detect_env_file(tmp_path) is True

    def test_env_file_missing(self, tmp_path: Path) -> None:
        assert detect_env_file(tmp_path) is False


class TestPoetryDetection:
    """Tests for detect_poetry_state()."""

    def test_poetry_ok(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="All set!", stderr=""))
        result = detect_poetry_state(run_fn=mock_run)
        assert result["ok"] is True

    def test_poetry_check_fails(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="Package missing"))
        result = detect_poetry_state(run_fn=mock_run)
        assert result["ok"] is False
        assert "missing" in result["message"].lower()

    def test_poetry_not_found(self) -> None:
        mock_run = MagicMock(side_effect=FileNotFoundError)
        result = detect_poetry_state(run_fn=mock_run)
        assert result["ok"] is False
        assert "not found" in result["message"].lower()


class TestAlembicDetection:
    """Tests for detect_alembic_state()."""

    def test_at_head(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(
            returncode=0, stdout="abc123ef (head)\n"
        ))
        result = detect_alembic_state(run_fn=mock_run)
        assert result["at_head"] is True

    def test_behind_head(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(
            returncode=0, stdout="abc123ef\n"
        ))
        result = detect_alembic_state(run_fn=mock_run)
        assert result["at_head"] is False

    def test_alembic_error(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="error"))
        result = detect_alembic_state(run_fn=mock_run)
        assert result["at_head"] is False
