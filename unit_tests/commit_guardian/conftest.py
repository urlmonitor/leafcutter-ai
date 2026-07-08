"""
conftest.py for unit_tests/commit_guardian/

Adds the leafcutter-ai repo root to sys.path so that commit_guardian unit
tests can import from the scripts/ package using the package-qualified form:

    import scripts.commit_guardian.verify_precommit_active as _vpa

This is needed because pytest's rootdir resolves to the parent ``leafcutter/``
workspace directory, not to ``leafcutter-ai/`` (the actual repo root). The
sys.path entry here makes ``leafcutter-ai/scripts/`` discoverable as a package.
"""
import sys
from pathlib import Path

# leafcutter-ai/ is three levels up from this file (unit_tests/commit_guardian/conftest.py)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
