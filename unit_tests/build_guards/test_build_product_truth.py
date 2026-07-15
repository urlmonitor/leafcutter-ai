"""
MODULE: test_build_product_truth
GOAL: Behavioral tests for the build_product_truth() deploy phase.
BUSINESS CONTEXT: The /plan-feature workflow's product-truth phase invokes
    docs/product-truth/scripts/generate_product_truth.py (and validate_*) at
    runtime via `python docs/product-truth/scripts/...`. Those scripts and
    their JSON schemas must be deployed into the consumer project's
    docs/product-truth/ tree by build.py, or the phase can only no-op in a
    fresh consumer / worktree. This test exercises the REAL phase against the
    REAL package source (per the repo's real-artifact spot-check convention),
    deploying into an isolated tmpdir.
ARCHITECTURE: Import-based — calls build_phases.build_product_truth directly
    with a tmpdir as target_root. Asserts the .py + .json files are deployed
    byte-identically, that the copy is glob-driven (all source .py deployed,
    not a hardcoded subset), and that a second run is idempotent.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import build_product_truth  # noqa: E402

_MINIMAL_CONFIG: dict = {"output_root": ".leafcutter"}


class TestBuildProductTruth(unittest.TestCase):
    """build_product_truth() deploys product-truth scripts + schemas."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.consumer = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, force: bool = True) -> int:
        return build_product_truth(self.consumer, _MINIMAL_CONFIG, dry_run=False, force=force)

    def test_deploys_generator_and_validator(self) -> None:
        """The two named generator/validator scripts land in the consumer tree."""
        self._run()
        dest_dir = self.consumer / "docs" / "product-truth" / "scripts"
        for name in ("generate_product_truth.py", "validate_product_truth.py"):
            self.assertTrue(
                (dest_dir / name).is_file(),
                f"Expected product-truth script not deployed: {name} (looked in {dest_dir})",
            )

    def test_deploys_all_source_scripts_via_glob(self) -> None:
        """Every *.py in the package source is deployed (glob, not a hardcoded list).

        This proves new generator/validator scripts added later are picked up
        automatically without editing the phase.
        """
        self._run()
        src_scripts = {p.name for p in (_PT_SRC / "scripts").glob("*.py")}
        dest_dir = self.consumer / "docs" / "product-truth" / "scripts"
        deployed = {p.name for p in dest_dir.glob("*.py")}
        self.assertEqual(
            src_scripts,
            deployed,
            "Deployed product-truth scripts must match the full source *.py set.",
        )

    def test_deploys_all_source_schemas_via_glob(self) -> None:
        """Every *.json schema in the package source is deployed."""
        self._run()
        src_schemas = {p.name for p in (_PT_SRC / "schemas").glob("*.json")}
        dest_dir = self.consumer / "docs" / "product-truth" / "schemas"
        deployed = {p.name for p in dest_dir.glob("*.json")}
        self.assertEqual(
            src_schemas,
            deployed,
            "Deployed product-truth schemas must match the full source *.json set.",
        )

    def test_deployed_scripts_byte_identical_to_source(self) -> None:
        """Deployed scripts are copied verbatim (no template compilation)."""
        self._run()
        dest_dir = self.consumer / "docs" / "product-truth" / "scripts"
        for src_file in (_PT_SRC / "scripts").glob("*.py"):
            deployed = (dest_dir / src_file.name).read_bytes()
            self.assertEqual(
                src_file.read_bytes(),
                deployed,
                f"Deployed {src_file.name} differs from package source.",
            )

    def test_second_build_is_idempotent(self) -> None:
        """A second build writes zero files (compare-before-write guard)."""
        self._run()
        second = self._run()
        self.assertEqual(
            second,
            0,
            "Second build_product_truth run must write zero files (idempotent).",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
