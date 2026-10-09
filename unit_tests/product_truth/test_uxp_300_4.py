"""
MODULE: test_uxp_300_4
GOAL: When the product-truth validator cannot load a dependency, its refusal
    names the module that actually failed to import (UXP-300-4).
BUSINESS CONTEXT: One try/except ImportError wrapped both `import jsonschema` and
    `from product_truth_contracts import ...`. A missing `referencing` (imported
    by product_truth_contracts) was therefore reported as "jsonschema is not
    installed", sending the operator to reinstall a package already present.
    The host that exposed the bug has since been repaired, so these tests make
    the import fail on purpose instead of relying on the host's installed set.
ARCHITECTURE: Each test runs the real validator in a FRESH subprocess
    (sys.executable -c <bootstrap>). The bootstrap sets the chosen modules to
    None in sys.modules (so importing them raises ImportError), puts the
    validator's own directory on sys.path, and executes it as __main__ with
    --quiet. The jsonschema refusal fires in main() before any store I/O, so no
    store fixture is needed. The test process itself is never polluted.
"""
from __future__ import annotations

import subprocess
import sys
import unittest

from ._bounds_harness import SCRIPTS_DIR

_VALIDATOR = SCRIPTS_DIR / "validate_product_truth.py"

_BOOTSTRAP = """
import runpy, sys
for name in sys.argv[1].split(","):
    sys.modules[name] = None
validator = sys.argv[2]
sys.path.insert(0, sys.argv[3])
sys.argv = [validator, "--quiet"]
runpy.run_path(validator, run_name="__main__")
"""

_FALSE_CLAIM = "jsonschema is required for product-truth validation but is not installed"


def _run_validator_with_blocked(*modules: str) -> tuple[int, str]:
    """Run the validator in a fresh subprocess with `modules` made unimportable."""
    proc = subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP, ",".join(modules), str(_VALIDATOR), str(SCRIPTS_DIR)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _installed_jsonschema_version() -> str:
    proc = subprocess.run(
        [sys.executable, "-c", "import importlib.metadata as m; print(m.version('jsonschema'))"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return proc.stdout.strip()


class TestImportFailureNamesRealModule(unittest.TestCase):
    def test_missing_referencing_is_named_not_reported_as_missing_jsonschema(self) -> None:
        # covers: UXP-300-4
        # angle: failure
        version = _installed_jsonschema_version()
        code, output = _run_validator_with_blocked("referencing", "referencing.exceptions")
        self.assertNotEqual(code, 0, f"validator must refuse to run; output:\n{output}")
        self.assertIn("referencing", output, f"refusal must name the failing module; output:\n{output}")
        self.assertIn(version, output, f"refusal must state the installed jsonschema version; output:\n{output}")
        self.assertNotIn(_FALSE_CLAIM, output, "refusal must not blame jsonschema when jsonschema is importable")

    def test_missing_jsonschema_is_still_reported_as_missing_jsonschema(self) -> None:
        # covers: UXP-300-4
        # angle: boundary
        code, output = _run_validator_with_blocked("jsonschema")
        self.assertNotEqual(code, 0, f"validator must refuse to run; output:\n{output}")
        self.assertIn("jsonschema is required", output)
        self.assertIn("not installed", output)


if __name__ == "__main__":
    unittest.main()
