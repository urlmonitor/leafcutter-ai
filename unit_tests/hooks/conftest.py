"""
conftest.py for unit_tests/hooks/

Adds the worktree root to sys.path so hook test modules can import helpers
without relying on cwd.
"""
import sys
from pathlib import Path

# unit_tests/hooks/conftest.py -> parents[2] = worktree root
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
