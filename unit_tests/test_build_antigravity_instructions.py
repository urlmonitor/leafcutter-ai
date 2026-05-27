"""
MODULE: test_build_antigravity_instructions
GOAL: Unit tests for build_antigravity_instructions phase logic, verifying compilation of ANTIGRAVITY.md.template.
"""

import sys
from pathlib import Path
import tempfile
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import build_antigravity_instructions
import build_phases

@pytest.fixture
def target_root(tmp_path):
    return tmp_path / "target"

@pytest.fixture
def mock_templates_dir(tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True)
    
    # Create the template file
    (templates_dir / "ANTIGRAVITY.md.template").write_text("Test Antigravity Instructions {{config.docs_root}}", encoding="utf-8")
    
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)
    return templates_dir

def test_build_antigravity_instructions_default(target_root, mock_templates_dir):
    config = {"docs_root": "docs/"}

    # Phase receives output_root in production (build.py passes .leafcutter/ path)
    output_root = target_root / ".leafcutter"
    written = build_antigravity_instructions(output_root, config, dry_run=False, force=True)

    assert written == 1

    # Output lands under output_root/gemini/ (no dot prefix inside .leafcutter)
    output_path = output_root / "gemini" / "instructions.md"
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "Test Antigravity Instructions docs/"

def test_build_antigravity_instructions_disabled(target_root, mock_templates_dir):
    config = {
        "docs_root": "docs/",
        "platforms": {
            "claude": True,
            "antigravity": False
        }
    }

    output_root = target_root / ".leafcutter"
    written = build_antigravity_instructions(output_root, config, dry_run=False, force=True)

    assert written == 0
    assert not (output_root / "gemini" / "instructions.md").exists()

def test_build_antigravity_instructions_no_template(target_root, mock_templates_dir):
    config = {"docs_root": "docs/"}

    (mock_templates_dir / "ANTIGRAVITY.md.template").unlink()

    output_root = target_root / ".leafcutter"
    written = build_antigravity_instructions(output_root, config, dry_run=False, force=True)

    assert written == 0
    assert not (output_root / "gemini" / "instructions.md").exists()
