"""
MODULE: test_build_hooks
GOAL: Unit tests for build_hooks phase logic.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import build_hooks, get_uptodate_count, reset_uptodate_count
import build_phases


@pytest.fixture
def mock_templates_dir(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    hooks_dir = templates_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    (hooks_dir / "hook_one.py").write_text("# hook one\nprint('one')\n", encoding="utf-8")
    (hooks_dir / "hook_two.py").write_text("# hook two\nprint('two')\n", encoding="utf-8")
    (hooks_dir / "__pycache__").mkdir()

    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)
    return templates_dir


def test_build_hooks_default_platforms(tmp_path, mock_templates_dir):
    output_root = tmp_path / "output"
    config = {}

    written = build_hooks(output_root, config, dry_run=False, force=True)

    # 2 hooks * 2 active platforms (claude + antigravity) = 4
    assert written == 4

    assert (output_root / "hooks" / "hook_one.py").exists()
    assert (output_root / "hooks" / "hook_two.py").exists()
    assert (output_root / "gemini" / "hooks" / "hook_one.py").exists()
    assert (output_root / "gemini" / "hooks" / "hook_two.py").exists()

    assert (output_root / "hooks" / "hook_one.py").read_text(encoding="utf-8") == "# hook one\nprint('one')\n"


def test_build_hooks_dry_run(tmp_path, mock_templates_dir):
    output_root = tmp_path / "output"
    config = {}

    written = build_hooks(output_root, config, dry_run=True, force=True)

    assert written == 4
    assert not (output_root / "hooks").exists()


def test_build_hooks_compare_before_write(tmp_path, mock_templates_dir):
    output_root = tmp_path / "output"
    config = {}

    build_hooks(output_root, config, dry_run=False, force=True)
    reset_uptodate_count()

    written = build_hooks(output_root, config, dry_run=False, force=True)

    assert written == 0
    assert get_uptodate_count() == 4


def test_build_hooks_skips_underscore_prefixed(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    hooks_dir = templates_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    (hooks_dir / "_helper.py").write_text("# internal helper", encoding="utf-8")
    (hooks_dir / "real_hook.py").write_text("# real hook", encoding="utf-8")

    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)

    output_root = tmp_path / "output"
    written = build_hooks(output_root, {}, dry_run=False, force=True)

    # Only real_hook.py * 2 platforms = 2
    assert written == 2
    assert not (output_root / "hooks" / "_helper.py").exists()
    assert (output_root / "hooks" / "real_hook.py").exists()


def test_build_hooks_no_template_dir(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True)
    # No hooks/ subdirectory
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)

    output_root = tmp_path / "output"
    written = build_hooks(output_root, {}, dry_run=False, force=True)

    assert written == 0
