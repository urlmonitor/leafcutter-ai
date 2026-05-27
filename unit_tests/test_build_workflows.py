"""
MODULE: test_build_workflows
GOAL: Unit tests for build_workflows phase logic, verifying dual compilation.
"""

import sys
from pathlib import Path
import tempfile
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import build_workflows
import build_phases

@pytest.fixture
def target_root(tmp_path):
    return tmp_path / "target"

@pytest.fixture
def mock_templates_dir(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    workflows_dir = templates_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    
    # Create some dummy workflow files
    (workflows_dir / "test_workflow_1.md").write_text("Test Workflow 1 {{config.docs_root}}", encoding="utf-8")
    (workflows_dir / "test_workflow_2.md").write_text("Test Workflow 2", encoding="utf-8")
    
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)
    return templates_dir

def test_build_workflows_default_platforms(target_root, mock_templates_dir):
    config = {"docs_root": "docs/"}

    # Phase receives output_root in production
    output_root = target_root / ".leafcutter"
    written = build_workflows(output_root, config, dry_run=False, force=True)

    # default platforms is claude and antigravity
    # 2 files each * 2 platforms = 4 files
    assert written == 4

    # Check claude commands (now at output_root/commands/, no .claude/ prefix)
    assert (output_root / "commands" / "test_workflow_1.md").exists()
    assert (output_root / "commands" / "test_workflow_2.md").exists()

    # Check antigravity workflows (now at output_root/gemini/workflows/)
    assert (output_root / "gemini" / "workflows" / "test_workflow_1.md").exists()
    assert (output_root / "gemini" / "workflows" / "test_workflow_2.md").exists()

    # Verify content was injected
    content1 = (output_root / "commands" / "test_workflow_1.md").read_text(encoding="utf-8")
    assert "docs/" in content1

def test_build_workflows_custom_platforms(target_root, mock_templates_dir):
    config = {
        "platforms": {
            "claude": False,
            "antigravity": True,
            "cursor": True,
            "copilot": False,
            "cline": False
        }
    }

    output_root = target_root / ".leafcutter"
    written = build_workflows(output_root, config, dry_run=False, force=True)

    # antigravity and cursor are True -> 4 files
    assert written == 4

    assert not (output_root / "commands").exists()

    # Check antigravity workflows
    assert (output_root / "gemini" / "workflows" / "test_workflow_1.md").exists()

    # Check cursor rules
    assert (output_root / "cursor" / "rules" / "test_workflow_1.md").exists()

def test_build_workflows_missing_templates_dir(target_root, tmp_path, monkeypatch):
    empty_templates = tmp_path / "empty"
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", empty_templates)
    
    written = build_workflows(target_root, {}, dry_run=False, force=True)
    assert written == 0

def test_build_workflows_dry_run(target_root, mock_templates_dir):
    config = {}

    output_root = target_root / ".leafcutter"
    written = build_workflows(output_root, config, dry_run=True, force=True)

    # Should say it would write 4 files
    assert written == 4

    # But files shouldn't exist
    assert not (output_root / "commands").exists()
    assert not (output_root / "gemini").exists()
