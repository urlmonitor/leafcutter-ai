"""
MODULE: unit_tests/commit_guardian/bp_100k_3/test_bp_100k_3_exemption_registry.py
GOAL: AC-5 of BP-100k-3, the exemption registry: check_build_drift.py and
    check_output_drift.py, each executed against the same declared
    exemption, both report it as exempt (first half), and an exemption entry
    with no stated ground is rejected so its artifact falls through to a
    coverage gap (second half).
CONTRACT: the output and exit-code contract these tests hold the gates to is
    stated in the module docstring of ``_support.py`` in this package.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/commit_guardian/test_bp_100k_3.py when that file was split;
  both classes take their workspace and synthetic package from
  SyntheticPackageTestCase.
"""

from __future__ import annotations

import unittest

from unit_tests.commit_guardian.bp_100k_3._support import (
    SyntheticPackageTestCase,
    _deploy_commit_guardian_dir,
    _exemption_config,
    _run_hook,
    _write_manifest,
)


# ---------------------------------------------------------------------------
# AC-5 (first half): both gates honour the same exemption registry.
# ---------------------------------------------------------------------------


class TestBothGatesHonourSameExemptionRegistry(SyntheticPackageTestCase):
    """AC-5: check_build_drift.py and check_output_drift.py, each executed
    against the same declared exemption, both report it as exempt."""

    def setUp(self) -> None:
        super().setUp()

        self.build_exempt = self.pkg_root / "templates" / "agents" / "exempt_shared.md"
        self.build_exempt.write_bytes(b"# shared exempt build artifact\n")
        self.build_exempt_key = self.build_exempt.relative_to(self.workspace).as_posix()

        self.output_exempt = self.workspace / ".claude" / "agents" / "exempt_shared_output.md"
        self.output_exempt.write_bytes(b"# shared exempt deployed output\n")
        self.output_exempt_key = self.output_exempt.relative_to(self.workspace).as_posix()

        _write_manifest(self.pkg_root, {}, {})
        deployed_dir = _deploy_commit_guardian_dir(self.workspace)
        self.build_hook = deployed_dir / "check_build_drift.py"
        self.output_hook = deployed_dir / "check_output_drift.py"

    def test_both_gates_honour_the_same_exemption_registry(self) -> None:
        # covers: BP-100k-3
        shared_ground = "shared exemption ground text honoured by both gate families"
        shared_config = _exemption_config(
            [
                {"path": self.build_exempt_key, "ground": shared_ground},
                {"path": self.output_exempt_key, "ground": shared_ground},
            ]
        )

        result_build = _run_hook(self.build_hook, self.workspace, exemption_config=shared_config)
        result_output = _run_hook(self.output_hook, self.workspace, exemption_config=shared_config)

        combined_build = result_build.stdout + result_build.stderr
        combined_output = result_output.stdout + result_output.stderr

        self.assertIn(
            f"UNCOMPARABLE: EXEMPT {self.build_exempt_key}",
            combined_build,
            msg=f"check-build-drift did not honour the shared exemption registry. Output:\n{combined_build}",
        )
        self.assertIn(shared_ground, combined_build, msg=f"Ground missing from check-build-drift output. Output:\n{combined_build}")

        self.assertIn(
            f"UNCOMPARABLE: EXEMPT {self.output_exempt_key}",
            combined_output,
            msg=f"check-output-drift did not honour the shared exemption registry. Output:\n{combined_output}",
        )
        self.assertIn(shared_ground, combined_output, msg=f"Ground missing from check-output-drift output. Output:\n{combined_output}")


# ---------------------------------------------------------------------------
# AC-5 (second half): a groundless entry is rejected, not silently honoured.
# ---------------------------------------------------------------------------


class TestExemptionEntryWithoutGroundIsRejected(SyntheticPackageTestCase):
    """AC-5: an exemption entry carrying no stated ground is rejected — the
    artifact falls through to a coverage gap, never a silent exemption."""

    def setUp(self) -> None:
        super().setUp()

        self.artifact = self.pkg_root / "templates" / "agents" / "would_be_exempt.md"
        self.artifact.write_bytes(b"# candidate for exemption\n")
        self.key = self.artifact.relative_to(self.workspace).as_posix()

        _write_manifest(self.pkg_root, {}, {})
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_build_drift.py"

    def test_exemption_entry_without_a_ground_is_rejected(self) -> None:
        # covers: BP-100k-3
        cases = [
            ("missing ground key", {"path": self.key}),
            ("empty-string ground", {"path": self.key, "ground": ""}),
            ("whitespace-only ground", {"path": self.key, "ground": "   "}),
        ]
        for label, entry in cases:
            with self.subTest(case=label):
                config = _exemption_config([entry])
                result = _run_hook(self.hook, self.workspace, exemption_config=config)
                combined = result.stdout + result.stderr

                self.assertIn(
                    f"REJECTED EXEMPTION ENTRY: {self.key}",
                    combined,
                    msg=f"A groundless exemption entry ({label}) was not rejected. Output:\n{combined}",
                )
                self.assertNotIn(
                    f"UNCOMPARABLE: EXEMPT {self.key}",
                    combined,
                    msg=(
                        f"A groundless exemption entry ({label}) silently exempted "
                        f"the artifact instead of being rejected. Output:\n{combined}"
                    ),
                )
                self.assertIn(
                    f"UNCOMPARABLE: GAP {self.key}",
                    combined,
                    msg=(
                        f"A rejected exemption entry ({label}) must fall through to "
                        f"a coverage gap, not be suppressed entirely. Output:\n{combined}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
