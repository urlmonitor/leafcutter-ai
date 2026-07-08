"""
conftest.py for unit_tests/workflows/

Adds the leafcutter-ai repo root to sys.path so that workflow unit tests can
import from the scripts/ package using the package-qualified form:

    from scripts.finalize_preflight import resolve_preflight_target

This is needed because pytest's rootdir resolves to the parent `leafcutter/`
workspace directory, not to `leafcutter-ai/`. The sys.path entry here makes
`leafcutter-ai/scripts/` discoverable as a package.
"""
import sys
from pathlib import Path

# leafcutter-ai/ is three levels up from this file (unit_tests/workflows/conftest.py)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
