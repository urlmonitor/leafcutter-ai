"""
MODULE: test_sync_platforms.py
GOAL: Unit tests for the bidirectional platform synchronisation script.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch

# Add the sync_platforms directory to sys.path to allow importing
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "templates" / "scripts" / "sync_platforms"
sys.path.insert(0, str(SCRIPT_DIR))

try:
    import sync_platforms
except ImportError:
    pytest.fail("Could not import sync_platforms. Check sys.path.")

@pytest.fixture
def temp_project(tmp_path):
    """Fixture providing a temporary project structure."""
    return tmp_path

def test_find_skills_config_in_platform_dir(temp_project):
    """Test finding skills_config.json in a known platform directory."""
    claude_dir = temp_project / ".claude"
    claude_dir.mkdir()
    config_file = claude_dir / "skills_config.json"
    config_file.touch()

    found = sync_platforms.find_skills_config(temp_project)
    assert found == config_file

def test_find_skills_config_fallback(temp_project):
    """Test finding skills_config.json via fallback recursive search."""
    some_dir = temp_project / "some_random_dir" / "deep"
    some_dir.mkdir(parents=True)
    config_file = some_dir / "skills_config.json"
    config_file.touch()

    found = sync_platforms.find_skills_config(temp_project)
    assert found == config_file

def test_find_skills_config_not_found(temp_project):
    """Test when skills_config.json does not exist."""
    found = sync_platforms.find_skills_config(temp_project)
    assert found is None

def test_get_active_platforms(temp_project):
    """Test parsing active platforms from config."""
    config_file = temp_project / "skills_config.json"
    config_data = {
        "platforms": {
            "claude": True,
            "cursor": False,
            "antigravity": True,
            "unknown_platform": True
        }
    }
    config_file.write_text(json.dumps(config_data))

    active = sync_platforms.get_active_platforms(config_file)
    
    assert "claude" in active
    assert "antigravity" in active
    assert "cursor" not in active
    assert "unknown_platform" not in active
    assert len(active) == 2

def test_get_active_platforms_invalid_json(temp_project, caplog):
    """Test parsing invalid config file."""
    config_file = temp_project / "skills_config.json"
    config_file.write_text("invalid json")

    active = sync_platforms.get_active_platforms(config_file)
    assert active == []
    assert "Failed to parse config" in caplog.text

def test_sync_directories_file_missing_on_target(temp_project):
    """Test syncing when target file does not exist."""
    source_dir = temp_project / "source"
    target_dir = temp_project / "target"
    
    source_dir.mkdir()
    target_dir.mkdir()
    
    source_file = source_dir / "test.txt"
    source_file.write_text("hello")
    
    count = sync_platforms.sync_directories(source_dir, target_dir)
    assert count == 1
    
    target_file = target_dir / "test.txt"
    assert target_file.exists()
    assert target_file.read_text() == "hello"

def test_sync_directories_source_newer(temp_project):
    """Test syncing when source file is newer than target."""
    source_dir = temp_project / "source"
    target_dir = temp_project / "target"
    
    source_dir.mkdir()
    target_dir.mkdir()
    
    source_file = source_dir / "test.txt"
    source_file.write_text("new content")
    
    target_file = target_dir / "test.txt"
    target_file.write_text("old content")
    
    # Make target file artificially older
    old_time = source_file.stat().st_mtime - 100
    os.utime(target_file, (old_time, old_time))
    
    count = sync_platforms.sync_directories(source_dir, target_dir)
    assert count == 1
    assert target_file.read_text() == "new content"

def test_sync_directories_target_newer(temp_project):
    """Test no sync when target file is newer than source."""
    source_dir = temp_project / "source"
    target_dir = temp_project / "target"
    
    source_dir.mkdir()
    target_dir.mkdir()
    
    source_file = source_dir / "test.txt"
    source_file.write_text("old content")
    
    target_file = target_dir / "test.txt"
    target_file.write_text("new content")
    
    # Make source file artificially older
    old_time = target_file.stat().st_mtime - 100
    os.utime(source_file, (old_time, old_time))
    
    count = sync_platforms.sync_directories(source_dir, target_dir)
    assert count == 0
    assert target_file.read_text() == "new content"

def test_perform_multi_way_sync(temp_project):
    """Test multi-way sync across multiple directories."""
    dir1 = temp_project / "dir1"
    dir2 = temp_project / "dir2"
    dir3 = temp_project / "dir3"
    
    for d in [dir1, dir2, dir3]:
        d.mkdir()
        
    (dir1 / "file_a.txt").write_text("A")
    (dir2 / "file_b.txt").write_text("B")
    
    total = sync_platforms.perform_multi_way_sync([dir1, dir2, dir3])
    
    assert total == 4
    for d in [dir1, dir2, dir3]:
        assert (d / "file_a.txt").exists()
        assert (d / "file_b.txt").exists()

@patch('sync_platforms.find_skills_config')
@patch('sync_platforms.get_active_platforms')
@patch('sync_platforms.perform_multi_way_sync')
def test_sync_platforms_main_flow(mock_multi_sync, mock_get_active, mock_find_config, temp_project):
    """Test the main sync_platforms function flow."""
    mock_find_config.return_value = temp_project / "skills_config.json"
    mock_get_active.return_value = ["claude", "cursor"]
    mock_multi_sync.return_value = 5
    
    with patch('sync_platforms.Path') as mock_path:
        # Mock __file__ resolution
        mock_file = mock_path.return_value
        mock_file.resolve.return_value.parent.parent.parent = temp_project
        
        # When calling Path() it should behave correctly or just mock it to not break
        # The main code just does Path(__file__).resolve().parent.parent.parent
        # So mocking Path to return something where that chain equals temp_project is enough
        
        sync_platforms.sync_platforms()
        
        mock_find_config.assert_called_once_with(temp_project)
        mock_get_active.assert_called_once_with(temp_project / "skills_config.json")
        assert mock_multi_sync.call_count == 2  # Once for agents, once for skills

@patch('sync_platforms.find_skills_config')
@patch('sync_platforms.get_active_platforms')
@patch('sync_platforms.perform_multi_way_sync')
def test_sync_platforms_with_source_repo(mock_multi_sync, mock_get_active, mock_find_config, temp_project):
    """Test sync_platforms includes source repo templates when present."""
    mock_find_config.return_value = temp_project / "skills_config.json"
    mock_get_active.return_value = ["claude"]
    mock_multi_sync.return_value = 2
    
    # Create source repo structure
    templates_dir = temp_project / "leafcutter-ai" / "templates"
    templates_dir.mkdir(parents=True)
    
    with patch('sync_platforms.Path') as mock_path:
        # Mock __file__ resolution
        mock_file = mock_path.return_value
        mock_file.resolve.return_value.parent.parent.parent = temp_project
        
        sync_platforms.sync_platforms()
        
        # Verify perform_multi_way_sync was called with lists including the templates dir
        agents_call = mock_multi_sync.call_args_list[0][0][0]
        skills_call = mock_multi_sync.call_args_list[1][0][0]
        
        assert any("leafcutter-ai" in str(d) and "agents" in str(d) for d in agents_call)
        assert any("leafcutter-ai" in str(d) and "skills" in str(d) for d in skills_call)

