"""
MODULE: unit_tests/portability/test_ge_122d_6.py
GOAL: Minimal RED test-first stub for AC GE-122d-6 — "The commit-time
    numbering check is wired into the live registry and fires on a real
    commit".
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-6.yaml

Asserts the primary (angle: criterion) test_spec descriptor
(``test_ge122d6_contested_commit_is_blocked_in_a_real_built_install``):
in a working copy produced by the real ``scripts/build.py``, a staged change
introducing a second claimant of an already-claimed number is committed
through the ORDINARY commit path — no skip flag, no environment override, no
direct invocation of the check script — and the commit must NOT complete.

Per this AC's coverage note: "covered only by making real commits in a real
built working copy and observing what the commit path does" — this test
therefore performs a real ``git init`` + real ``pre-commit install`` +
real commit against the deployed ``.pre-commit-config.yaml``, never a direct
call to check_identifier_uniqueness.py.

The built copy's registry is narrowed to a WHITELIST before the commit
(``_ge122_build_commit_helpers.strip_environment_confound_hooks``): the
self-healing hook plus any hook invoking check_identifier_uniqueness. This
is test-isolation of an ephemeral scratch fixture from ~50 UNRELATED hooks
tuned for this package's own self-hosted, fully-tracked checkout (confirmed
empirically: several crash or fail-closed against a bare git-init'd tempdir
for reasons that have nothing to do with identifier uniqueness) — it is not
an exemption of the check under test, which the whitelist explicitly
preserves whenever it is registered.

RED AT AUTHORING TIME: verified 2026-08-25 (this AC's own notes) and
directly confirmed by grep before authoring this file —
check_identifier_uniqueness.py appears in NEITHER
templates/scripts/commit_guardian/commit_guardian.json's hooks_manifest.hooks
NOR the deployed .pre-commit-config.yaml. So the ordinary commit path never
reaches the check, and a contested-number commit completes cleanly instead
of being blocked.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge122_build_commit_helpers import (  # noqa: E402
    build_and_wire_ordinary_commit_path,
    attempt_ordinary_commit,
    stage_paths,
)


class TestGe122d6ContestedCommitIsBlocked(unittest.TestCase):
    def test_ge122d6_contested_commit_is_blocked_in_a_real_built_install(self) -> None:
        # covers: GE-122d-6
        # angle: criterion
        """A staged change introducing a second claimant of an
        already-claimed number, committed through the ordinary commit path
        in a real built working copy, must not complete.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "built_copy"
            build_result = build_and_wire_ordinary_commit_path(target_dir)
            self.assertEqual(
                0,
                build_result.returncode,
                msg=(
                    "Precondition failed: build.py must succeed before the commit-time "
                    f"registration can be exercised.\nstdout:\n{build_result.stdout}"
                    f"\nstderr:\n{build_result.stderr}"
                ),
            )

            # Introduce a contested number: two ADR files both claiming the
            # same decision number, an ordinary adopter-visible change.
            frontmatter = (
                "---\n"
                "description: Fixture ADR for GE-122d-6 test isolation.\n"
                "created: '2026-08-31'\n"
                "last_updated: '2026-08-31'\n"
                "type: reference\n"
                "status: active\n"
                "---\n"
            )
            adr_dir = target_dir / "docs" / "architecture" / "adrs"
            adr_dir.mkdir(parents=True, exist_ok=True)
            (adr_dir / "ADR-777-first-claimant.md").write_text(
                frontmatter + "# ADR-777: First claimant\n\nStatus: accepted\n", encoding="utf-8",
            )
            (adr_dir / "ADR-777-second-claimant.md").write_text(
                frontmatter + "# ADR-777: Second claimant\n\nStatus: accepted\n", encoding="utf-8",
            )

            stage_paths(
                target_dir,
                [
                    "docs/architecture/adrs/ADR-777-first-claimant.md",
                    "docs/architecture/adrs/ADR-777-second-claimant.md",
                ],
            )
            commit_result = attempt_ordinary_commit(
                target_dir, "test: introduce contested ADR-777 (GE-122d-6 fixture)"
            )

            self.assertNotEqual(
                0,
                commit_result.returncode,
                msg=(
                    "A commit introducing a contested number must NOT complete through the "
                    "ordinary commit path. It completed cleanly instead, which is exactly "
                    "the silent no-op GE-122d-6 exists to detect: "
                    "check_identifier_uniqueness.py is registered nowhere in the deployed "
                    f"pre-commit registry.\nstdout:\n{commit_result.stdout}"
                    f"\nstderr:\n{commit_result.stderr}"
                ),
            )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/GE-122d-6 fast-lane build set]: Initial minimal
#   RED stub. Confirmed via direct grep of both commit_guardian.json
#   manifests and .pre-commit-config.yaml that check_identifier_uniqueness
#   is registered nowhere; expected to fail because the contested-ADR commit
#   completes (returncode 0) instead of being blocked.
# ====================================================================
