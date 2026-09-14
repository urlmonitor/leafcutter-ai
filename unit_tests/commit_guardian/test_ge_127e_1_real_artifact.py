"""
MODULE: unit_tests/commit_guardian/test_ge_127e_1_real_artifact.py
COVERS: GE-127e-1 -- "The refusal accounts for what is inside the file it
    refused, and names a division of that file in terms of those same parts"

GOAL: RED test-first stub for the real-artifact descriptor. Per this
    repo's Fixture Authenticity Rule and CLAUDE.md's real-artifact
    behavioral spot-check convention, an extractor written only against a
    fixture of uniform generated definitions inherits that fixture's own
    bias -- the documented shape of this repository's worst phantom-done
    incidents. This descriptor copies an ACTUAL tracked, already-oversized
    repository file (scripts/build_phases.py -- 2671 counted / 400 limit,
    confirmed oversized in this worktree at authoring time, and already the
    established real-oversized-file fixture in this same directory's
    test_ge_127b_1.py) into the fixture repository VERBATIM and asserts the
    same three properties as the generated-fixture descriptors.

THE DEFECT THIS FILE IS RED AGAINST. check_file_size.py's refusal is a
    fixed two-sentence block for every input, including a real tracked
    file -- no ``Parts:``, no ``Division:``, for any input today.

DECISION HISTORY
- 2026-09-14 [GE-127e-1/test-writer]: Initial authoring of one RED test
    stub per GE-127e-1's test_spec. Verified RED via
    `AC_ENFORCE_STRICT=1 python -m pytest
    unit_tests/commit_guardian/test_ge_127e_1_real_artifact.py -v` --
    see the test-writer sign-off comment on the ticket for the exact
    captured failures.
"""

from __future__ import annotations

import sys
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_1_fixture as fx  # noqa: E402


class TestRealTrackedOverLimitFileIsDescribedInTermsOfItsOwnParts(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            fx._REAL_OVERSIZED_FILE.exists(),
            msg=f"Fixture sanity: {fx._REAL_OVERSIZED_FILE} must exist in this worktree.",
        )
        self.real_content = fx._REAL_OVERSIZED_FILE.read_text(encoding="utf-8")
        self.assertGreater(
            fx.count_content_lines(self.real_content),
            fx._PY_LIMIT,
            msg="Fixture sanity: the real file must already be over its permitted length.",
        )

        self.root = fx.fresh_repo_dir("ge127e1_real_artifact_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

        target = self.root / "real_oversized_copy.py"
        target.write_text("x = 1\n", encoding="utf-8")
        fx.commit_all(self.root, "establish placeholder under-limit file")

        target.write_text(self.real_content, encoding="utf-8")
        fx.stage_all(self.root)

    def test_ge_127e_1_a_real_tracked_over_limit_source_file_is_described_in_terms_of_its_own_parts(self):
        # covers: GE-127e-1
        # angle: real_artifact
        """REAL ARTIFACT, NOT A GENERATED FIXTURE. Refusing a verbatim copy
        of a real, already-oversized tracked .py file must produce a
        description whose named parts are locatable in the real file's own
        bytes, whose portions sum to at least half the quoted length, and
        whose division (if named) reconciles with that quoted length --
        exactly as for a generated fixture, but against code carrying
        decorators, nested classes, module-level constants, and a decision
        -history block that a part extractor written only against uniform
        generated definitions can fail on.

        RED TODAY: no ``Parts:``/``Division:`` block is printed for any
        input, real or generated.
        """
        result = fx.run_check(self.root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"Fixture sanity: must be refused. Got: {combined!r}")

        quoted_length, _limit = fx.extract_quoted_length_and_limit(combined)
        named = fx.extract_named_portions(combined)
        self.assertTrue(
            named,
            msg=f"The refusal must name at least one part of the real file. Got: {combined!r}",
        )
        for name, _portion in named:
            self.assertIn(
                name,
                self.real_content,
                msg=f"Named part {name!r} could not be located in the real file's own content.",
            )

        portion_sum = sum(portion for _name, portion in named)
        self.assertGreaterEqual(
            portion_sum,
            quoted_length / 2,
            msg=(
                f"Named parts' portions ({portion_sum}) must account for at "
                f"least half of the quoted measured length ({quoted_length})."
            ),
        )

        named_map = dict(named)
        for names, length in fx.extract_sides(combined):
            for name in names:
                self.assertIn(name, named_map, msg=f"Side part {name!r} is not one of the printed parts.")
            self.assertEqual(
                sum(named_map[name] for name in names),
                length,
                msg=f"Side length ({length}) must equal the sum of its own named parts' portions.",
            )


if __name__ == "__main__":
    unittest.main()
