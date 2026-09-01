"""
MODULE: unit_tests/portability/test_ge_122d_3_ii.py
GOAL: Minimal RED test-first stub for AC GE-122d-3-ii — "A new project's
    first commit works because the roots are there, not because absence is
    excused".
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3-ii.yaml

Asserts the "criterion" test_spec descriptor
(``test_ge122d3ii_install_leaves_every_namespace_root_present_as_a_real_directory``,
angle: criterion): after the real base install (``scripts/build.py``) into a
project built from a genuinely EMPTY directory, with no opt-in
documentation-seeding step performed, every namespace root the whole-
collection uniqueness pass is responsible for exists as a real directory —
including ``docs/architecture/adrs/`` and ``docs/architecture/diagrams/``,
the two roots named by KI-BO-030 as currently unscaffolded by a plain
install.

Built from an EMPTY directory, never a copy of this repository — a copy
already contains every root and cannot reproduce the condition (per this
AC's own coverage note and it_requirements).

RED AT AUTHORING TIME: KI-BO-030 (referenced in this AC's doc_links, verified
2026-08-25 in the AC's own it_requirements) records that
``scripts/build.py``'s base install path does not create
``docs/architecture/adrs/`` or ``docs/architecture/diagrams/`` in a target
project — this test's directory-existence assertions fail with a plain
AssertionError.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge122_build_commit_helpers import run_build  # noqa: E402


class TestGe122d3iiScaffoldedNamespaceRoots(unittest.TestCase):
    def test_ge122d3ii_install_leaves_every_namespace_root_present_as_a_real_directory(self) -> None:
        # covers: GE-122d-3-ii
        # angle: criterion
        """Every namespace root the uniqueness pass holds itself responsible
        for exists as a real directory after a base install into an EMPTY
        project — a git-trackable directory, not merely a resolvable path.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "fresh_adopter_project"
            build_result = run_build(target_dir)

            self.assertEqual(
                0,
                build_result.returncode,
                msg=(
                    "Precondition failed: the real build.py itself must succeed "
                    f"against an empty target before scaffolding can be asserted."
                    f"\nstdout:\n{build_result.stdout}\nstderr:\n{build_result.stderr}"
                ),
            )

            expected_roots = [
                target_dir / "docs" / "acceptance-criteria",
                target_dir / "docs" / "architecture" / "adrs",
                target_dir / "docs" / "architecture" / "diagrams",
                target_dir / "tickets",
            ]
            missing = [str(root) for root in expected_roots if not root.is_dir()]
            self.assertEqual(
                [],
                missing,
                msg=(
                    "The following namespace root(s) were NOT scaffolded by a base "
                    f"install into an empty project (KI-BO-030): {missing}. GE-122d-3-ii "
                    "requires the install to create every root the uniqueness pass is "
                    "responsible for — an absent root must never be reported as an "
                    "inspected count of zero."
                ),
            )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/GE-122d-6 fast-lane build set]: Initial minimal
#   RED stub. Verified via direct Read of scripts/build_phases.py plus the
#   AC's own KI-BO-030 reference that a base install does not scaffold
#   docs/architecture/adrs/ or docs/architecture/diagrams/ — expected to fail
#   with a plain AssertionError naming the missing roots.
# ====================================================================
