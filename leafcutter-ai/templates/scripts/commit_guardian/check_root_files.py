"""
Pre-commit hook to block commits that add new files to the root directory.

MODULE: check_root_files.py
GOAL: Block commits that add unauthorized new files to the root directory.
BUSINESS CONTEXT: Keeps the project root clean and enforces organization into respective folders.
ARCHITECTURE: Not needed.

Only files that are defined in an allowed list (e.g., config files, environment files)
are permitted to reside in the root directory.

Exit Codes:
    0 - No forbidden root files found
    1 - Forbidden root files found
"""

import subprocess
import sys
from pathlib import Path

# Fix import path when running from root
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import ALLOWED_ROOT_FILES, ALLOWED_ROOT_EXTENSIONS

# Backwards-compatible alias used by check_documentation.py
ALLOWED_EXTENSIONS = ALLOWED_ROOT_EXTENSIONS

def get_staged_new_files() -> list[str]:
    """Get all staged new files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    staged_files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            # Only check formally added (A), or modified (M) files just in case
            if status.startswith("A") or status.startswith("M") or status.startswith("R"):
                staged_files.append(filepath)

    return staged_files

def main() -> int:
    # Ensure header output works on Windows
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    staged_files = get_staged_new_files()
    if not staged_files:
        return 0

    failed_files = []
    for filepath in staged_files:
        path = Path(filepath)
        
        # A file is in the root directory if it has exactly one part
        if len(path.parts) == 1:
            if path.name not in ALLOWED_ROOT_FILES and path.suffix not in ALLOWED_EXTENSIONS:
                failed_files.append(filepath)

    if failed_files:
        print("\n🚫 Root Directory Check Failed")
        print("You are trying to commit unauthorized files to the root directory:")
        for f in failed_files:
            print(f"  ❌ {f}")
        print("\nAll project files (scripts, code, docs) should be organized into their respective folders.")
        print(f"If this file belongs in the root directory, add it to ALLOWED_ROOT_FILES in {__file__}\n")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-14 16:00 [Agent]: Initial implementation of root file checks.
====================================================================
"""
