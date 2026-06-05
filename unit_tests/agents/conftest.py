"""
conftest.py for unit_tests/agents/

Adds the leafcutter-ai repo root to sys.path so that agent unit tests can
import from the scripts/ package using the package-qualified form:

    from scripts.build_ac_mode_detection import detect_ac_mode

This is needed because pytest's rootdir resolves to the parent `leafcutter/`
workspace directory, not to `leafcutter-ai/`. The sys.path entry here makes
`leafcutter-ai/scripts/` discoverable as a package.
"""
import sys
from pathlib import Path

# leafcutter-ai/ is two levels up from this file (unit_tests/agents/conftest.py)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
