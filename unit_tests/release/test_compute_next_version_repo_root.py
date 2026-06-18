"""Tests for _resolve_repo_root() submodule topology handling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from scripts.release.compute_next_version import _resolve_repo_root


def _build_tree(tmp_path: Path, git_at_p2: str | None, git_at_p3: bool = False) -> Path:
    """Build a fake directory tree simulating script location.

    Args:
        tmp_path: pytest tmp_path fixture root.
        git_at_p2: "dir" to create .git as a directory, "file" to create .git
            as a file (submodule pointer), None to omit .git at parents[2].
        git_at_p3: If True, create a .git directory at parents[3] (consumer root).

    Returns:
        The path that would be ``Path(__file__).resolve()`` for the script.
    """
    if git_at_p3:
        consumer = tmp_path / "consumer"
        pkg = consumer / "leafcutter"
    else:
        consumer = None
        pkg = tmp_path / "repo"

    script_dir = pkg / "scripts" / "release"
    script_dir.mkdir(parents=True)
    script_file = script_dir / "compute_next_version.py"
    script_file.write_text("# placeholder")

    if git_at_p2 == "dir":
        (pkg / ".git").mkdir()
    elif git_at_p2 == "file":
        (pkg / ".git").write_text("gitdir: ../../.git/modules/leafcutter\n")

    if git_at_p3 and consumer is not None:
        (consumer / ".git").mkdir()

    return script_file


class TestResolveRepoRootGitAsDirectory:
    def test_returns_p2_when_git_is_directory(self, tmp_path: Path) -> None:
        script_file = _build_tree(tmp_path, git_at_p2="dir")
        expected = script_file.parents[2]  # <repo>

        with patch("scripts.release.compute_next_version.Path") as mock_path:
            mock_path.__file__ = str(script_file)
            mock_path.return_value.resolve.return_value = script_file
            mock_path.side_effect = lambda *a, **kw: Path(*a, **kw) if a else mock_path.return_value

            with patch("scripts.release.compute_next_version.__file__", str(script_file)):
                result = _resolve_repo_root()

        assert result == expected


class TestResolveRepoRootGitAsFile:
    def test_returns_p2_when_git_is_file_submodule(self, tmp_path: Path) -> None:
        script_file = _build_tree(tmp_path, git_at_p2="file", git_at_p3=True)
        p2 = script_file.parents[2]  # <consumer>/leafcutter/
        p3 = script_file.parents[3]  # <consumer>/

        with patch("scripts.release.compute_next_version.__file__", str(script_file)):
            result = _resolve_repo_root()

        assert result == p2, f"Expected leafcutter root {p2}, got consumer root {p3}"


class TestResolveRepoRootFallback:
    def test_falls_back_to_p3_when_no_git_at_p2(self, tmp_path: Path) -> None:
        script_file = _build_tree(tmp_path, git_at_p2=None, git_at_p3=True)
        expected = script_file.parents[3]  # <consumer>/

        with patch("scripts.release.compute_next_version.__file__", str(script_file)):
            result = _resolve_repo_root()

        assert result == expected


class TestFindLastVersionTagUsesCorrectRoot:
    def test_uses_repo_root_as_cwd(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock
        from scripts.release.compute_next_version import _find_last_version_tag

        expected_root = tmp_path / "my-repo"
        expected_root.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = "v0.2.5\n"

        with patch("scripts.release.compute_next_version.subprocess.run", return_value=mock_result) as mock_run:
            tag = _find_last_version_tag(expected_root)

        assert tag == "v0.2.5"
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["cwd"] == expected_root
