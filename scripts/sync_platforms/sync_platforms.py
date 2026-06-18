"""
MODULE: sync_platforms
GOAL: Bidirectional sync of agents and skills across active platform directories.
BUSINESS CONTEXT: Leafcutter supports multiple platforms (Claude, Gemini, Cursor, etc.).
    To avoid divergent states, this script ensures that newly created or recently modified
    skills and agents are synchronised across all active platforms (as defined in skills_config.json).
    If run within the leafcutter source repository, it also syncs updates back to the source templates.
ARCHITECTURE:
    ```mermaid
    graph TD
        Start[Start Sync] --> FindConfig[Find skills_config.json]
        FindConfig --> ParseConfig[Parse active platforms]
        ParseConfig --> IdentifyDirs[Identify platform directories]
        IdentifyDirs --> SyncAgents[Sync Agents based on mtime]
        IdentifyDirs --> SyncSkills[Sync Skills based on mtime]
        SyncAgents --> CheckSourceRepo{In Source Repo?}
        SyncSkills --> CheckSourceRepo
        CheckSourceRepo -- Yes --> SyncToTemplates[Sync to leafcutter-ai/templates/]
        CheckSourceRepo -- No --> End[Complete]
        SyncToTemplates --> End
    ```
"""

import json
import shutil
import logging
from pathlib import Path
from typing import List, Optional

# Set up standard logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PLATFORM_DIRS = {
    "claude": ".claude",
    "antigravity": ".gemini",
    "cursor": ".cursor",
    "copilot": ".github",
    "cline": ".cline"
}

def find_skills_config(project_root: Path) -> Optional[Path]:
    """Find the skills_config.json file in the project.

    Searches known platform directories first, then falls back to a recursive search.

    Args:
        project_root: The root directory of the project.

    Returns:
        Path to the skills_config.json file if found, None otherwise.
    """
    for platform_dir in PLATFORM_DIRS.values():
        config_path = project_root / platform_dir / "skills_config.json"
        if config_path.is_file():
            return config_path
    
    # Fallback to recursive search
    try:
        for path in project_root.rglob("skills_config.json"):
            if path.is_file():
                return path
    except OSError as exc:
        logger.warning("Recursive search for skills_config.json failed: %s", exc)

    return None

def get_active_platforms(config_path: Path) -> List[str]:
    """Parse the configuration file to determine active platforms.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        List of active platform names (e.g., 'claude', 'antigravity').
    """
    active_platforms = []
    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
        
        platforms = config.get("platforms", {})
        for platform, is_active in platforms.items():
            if is_active and platform in PLATFORM_DIRS:
                active_platforms.append(platform)
                
    except Exception as e:
        logger.error(f"\033[91mFailed to parse config {config_path}: {e}\033[0m")
        
    return active_platforms

def sync_directories(source_dir: Path, target_dir: Path) -> int:
    """Synchronise files from source_dir to target_dir based on mtime.

    Args:
        source_dir: The directory to read files from.
        target_dir: The directory to sync files to.

    Returns:
        Number of files synced.
    """
    synced_count = 0
    if not source_dir.exists():
        return synced_count
        
    target_dir.mkdir(parents=True, exist_ok=True)
    
    for item in source_dir.rglob("*"):
        if not item.is_file():
            continue
            
        rel_path = item.relative_to(source_dir)
        target_item = target_dir / rel_path
        
        # If target doesn't exist, or source is newer, copy it
        if not target_item.exists() or item.stat().st_mtime > target_item.stat().st_mtime:
            target_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target_item)
            synced_count += 1
            logger.debug(f"Synced {item} -> {target_item}")
            
    return synced_count

def perform_multi_way_sync(directories: List[Path]) -> int:
    """Perform a multi-way synchronisation across all provided directories.
    
    Ensures that the latest version of any file across all directories
    is propagated to all other directories.

    Args:
        directories: List of directory paths to synchronise.

    Returns:
        Total number of file sync operations performed.
    """
    total_synced = 0
    valid_dirs = [d for d in directories if d.exists()]
    
    if len(valid_dirs) < 2:
        return 0
        
    # We will sync from every valid dir to every other valid dir
    for source in valid_dirs:
        for target in valid_dirs:
            if source != target:
                total_synced += sync_directories(source, target)
                
    return total_synced

def sync_platforms() -> None:
    """Main execution function to sync platforms and source templates."""
    project_root = Path(__file__).resolve().parent.parent.parent
    
    config_path = find_skills_config(project_root)
    if not config_path:
        logger.warning("\033[93mNo skills_config.json found. Cannot determine active platforms.\033[0m")
        return
        
    active_platforms = get_active_platforms(config_path)
    if not active_platforms:
        logger.warning("\033[93mNo active platforms found in configuration.\033[0m")
        return
        
    logger.info(f"\033[96mActive platforms identified: {', '.join(active_platforms)}\033[0m")
    
    agent_dirs = []
    skill_dirs = []
    
    for platform in active_platforms:
        platform_dir = PLATFORM_DIRS.get(platform)
        if platform_dir:
            agent_dirs.append(project_root / platform_dir / "agents")
            skill_dirs.append(project_root / platform_dir / "skills")
            
    total_agents = perform_multi_way_sync(agent_dirs)
    total_skills = perform_multi_way_sync(skill_dirs)
    
    total_synced = total_agents + total_skills

    # One-way sync from source templates to platform outputs
    leafcutter_templates = project_root / "templates"
    is_source_repo = leafcutter_templates.is_dir()
    if is_source_repo:
        logger.info("\033[96mLeafcutter source repository detected. Syncing templates to platforms (one-way only).\033[0m")
        template_agent_dir = leafcutter_templates / "agents"
        template_skill_dir = leafcutter_templates / "skills"
        
        for agent_target in agent_dirs:
            total_synced += sync_directories(template_agent_dir, agent_target)
            
        for skill_target in skill_dirs:
            total_synced += sync_directories(template_skill_dir, skill_target)
    
    
    if total_synced > 0:
        logger.info(f"✨ \033[92mSync complete! Synchronised {total_synced} files across platforms.\033[0m ✨")
    else:
        logger.info("✨ \033[92mAll platforms are up to date! No files needed synchronisation.\033[0m ✨")

if __name__ == "__main__":
    sync_platforms()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-22 10:00 [python-coder/Ticket-10]: Initial implementation of bidirectional
#   platform sync logic to keep multiple platform directories (Claude, Gemini, etc.)
#   and source templates aligned. Uses mtime for newer-file detection.
#   (#TICKETLESS reason=initial-sync-implementation)
# - 2026-06-03 10:00 [python-coder/EPIC-TemplateDocViolations/03]: Added missing HH:MM
#   time component and tail-tag to initial entry to comply with check_documentation
#   pre-commit hook format requirements. (#EPIC-TemplateDocViolations/03)
# ====================================================================
