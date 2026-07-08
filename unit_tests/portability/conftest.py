"""
conftest.py for unit_tests/portability/

Adds the EPIC-WorktreeQualityGateGuard worktree root to sys.path so that
portability unit tests can import from the scripts/ package using the
package-qualified form:

    import scripts.commit_guardian.verify_precommit_active as _vpa

This is needed because pytest's rootdir resolves to the parent workspace
directory, not the worktree root. The sys.path entry here makes scripts/
discoverable as a namespace package (PEP 420 / Python 3.3+).
"""
import sys
from pathlib import Path

# worktree root is three levels up from this file:
# unit_tests/portability/conftest.py → parent × 3 = EPIC-WorktreeQualityGateGuard/
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKTREE_ROOT))
