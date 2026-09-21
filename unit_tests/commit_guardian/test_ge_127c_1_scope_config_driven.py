"""
MODULE: unit_tests/commit_guardian/test_ge_127c_1_scope_config_driven.py
COVERS: GE-127c-1 -- "The outcome states which kinds of file it measured, so
    a kind that was never measured is not read as having passed"

GOAL: RED test-first stubs for the scope-IS-CONFIG-DRIVEN half of GE-127c-1:
    proof that the set of "measured" kinds tracks commit_guardian.json's own
    checked_extensions / line_limits, rather than any set an implementation
    could bake into itself. Two descriptors share this theme:

    - the decisive before/after pinned-config pair (changing what's in
      scope moves the stated set of measured kinds, with nothing else about
      the run changed), and
    - the newly-scoped .js/.ts boundary (each newly-widened kind is judged
      at ITS OWN configured limit, never a silently inherited default).

    Both descriptors are immune to a hardcoded-set implementation for the
    same underlying reason: they each force the config the outcome must
    read to differ from what a source-baked set could have anticipated.

    See test_ge_127c_1_scope_declaration.py's module docstring for the
    production-module context this AC as a whole targets, and
    _ge_127c_1_scope_fixture.py for every shared helper.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127c-1.yaml and its parents GE-127c.yaml / GE-127.yaml.

DECISION HISTORY
- 2026-09-14 [GE-127c-1/test-writer]: Initial authoring of all seven RED
    test stubs per GE-127c-1's test_spec, in test_ge_127c_1.py. Verified RED
    via `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127c_1.py"`.
- 2026-09-14 [GE-127c-1/test-writer]: Split out of test_ge_127c_1.py (579
    counted lines, over the 400-line check-file-size limit this AC itself
    widened) into this file, grouped by what these two descriptors prove:
    the scope in force is what config says, not what an implementation
    happens to hardcode. Pure move -- no assertion changed, including the
    two hard-won corrections this descriptor carries verbatim: the "before"
    arm is pinned via copy_commit_guardian(file_size_overrides=...) rather
    than reading the real production config, and it asserts via
    asserts_kind_not_measured (never asserts_kind_measured, which cannot
    distinguish "measured" from "explicitly not measured"). Re-verified RED
    via `python -m pytest
    unit_tests/commit_guardian/test_ge_127c_1_scope_config_driven.py -v`.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127c_1_scope_fixture import (  # noqa: E402
    asserts_kind_measured,
    asserts_kind_not_measured,
    content,
    copy_commit_guardian,
    init_repo,
    new_repo,
    run_check,
    run_direct,
    stage_all,
)

# ---------------------------------------------------------------------------
# 3. THE DECISIVE ANTI-GREP DESCRIPTOR -- changing the scope in force moves
#    the stated set of measured kinds
# ---------------------------------------------------------------------------


class TestChangingScopeInForceMovesTheStatedSetOfMeasuredKinds(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        init_repo(self.root)

    def test_ge_127c_1_changing_the_scope_in_force_moves_the_stated_set_of_measured_kinds(self):
        # covers: GE-127c-1
        # angle: real_artifact
        """THE DECISIVE ANTI-GREP DESCRIPTOR. BOTH arms of this before/after
        pair run against a fixture configuration this test itself pins --
        NEITHER arm reads the real, production commit_guardian.json's scope.
        The "before" copy explicitly pins checked_extensions to [".py",
        ".sql"] (with matching line_limits); the "after" copy is identical
        except for ONE added entry, ".sh" (nothing else changes -- same
        repo, same staged files). This is deliberate: this AC's own
        it_requirements pin .sh INTO the real production scope, so a
        "before" arm that instead inherited the real config would assert
        the opposite of what the sibling deployed-scope descriptor
        (in test_ge_127c_1_deployed_reachability.py) requires -- two
        descriptors making mutually exclusive demands on one file. Pinning
        both arms here makes this descriptor immune to the real scope
        changing in either direction, which is the whole point of a
        scope-is-config-driven test.

        Run the "before" copy and capture the stated set of measured kinds
        and the verdict for one file of a kind (.sh) outside that pinned
        scope. Then run the "after" copy, where .sh has been added with a
        deliberately tiny configured limit of 5 for a 10-line file. The
        stated set must now include .sh and the file must be measured
        (here: refused). No implementation carrying a set of kinds written
        into itself -- however that set is spelled -- can pass this,
        because the SAME two runs against the SAME staged content only
        differ in a config file this test edits between them.

        DEMONSTRATES: check_file_size.py never states any measured-kinds
        set at all until this AC is implemented, so asserts_kind_measured
        is False both before AND after the scope change -- the "after"
        assertion is what fails until the outcome-declaration behaviour
        exists.
        """
        (self.root / "in_scope.py").write_text(content(5), encoding="utf-8")
        (self.root / "probe.sh").write_text(content(10), encoding="utf-8")
        stage_all(self.root)

        cg_before = copy_commit_guardian(
            file_size_overrides={
                "checked_extensions": [".py", ".sql"],
                "line_limits": {".py": 400, ".sql": 600},
            }
        )
        self.addCleanup(shutil.rmtree, cg_before, ignore_errors=True)
        before_result = run_direct(cg_before, self.root)
        before_combined = before_result.stdout + before_result.stderr

        self.assertNotIn(
            "probe.sh",
            before_combined,
            msg=f"An out-of-scope file must not be named at all. Got: {before_combined!r}",
        )
        self.assertTrue(
            asserts_kind_not_measured(before_combined, ".sh"),
            msg=(
                "Before .sh is added to the scope in force, the outcome must "
                f"explicitly state .sh was NOT measured. Got: {before_combined!r}"
            ),
        )

        cg_after = copy_commit_guardian(
            file_size_overrides={
                "checked_extensions": [".py", ".sql", ".sh"],
                "line_limits": {".py": 400, ".sql": 600, ".sh": 5},
            }
        )
        self.addCleanup(shutil.rmtree, cg_after, ignore_errors=True)
        after_result = run_direct(cg_after, self.root)
        after_combined = after_result.stdout + after_result.stderr

        self.assertIn(
            "probe.sh",
            after_combined,
            msg=f"probe.sh must now be named as measured. Got: {after_combined!r}",
        )
        self.assertTrue(
            asserts_kind_measured(after_combined, ".sh"),
            msg=(
                "After .sh is added to the scope in force (nothing else "
                f"changed), the outcome must state .sh was measured. Got: {after_combined!r}"
            ),
        )
        self.assertNotEqual(
            0,
            after_result.returncode,
            msg=(
                "probe.sh (10 lines) now exceeds its newly-configured "
                f"5-line limit and must be refused. Got: "
                f"stdout={after_result.stdout!r} stderr={after_result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 5. Boundary: newly-scoped .js / .ts kinds judged at THEIR OWN pinned limits
# ---------------------------------------------------------------------------


class TestNewlyScopedJsAndTsKindsAreMeasuredAtTheirOwnLimits(unittest.TestCase):
    def test_ge_127c_1_the_newly_scoped_javascript_and_typescript_kinds_are_measured_at_their_own_limits(self):
        # covers: GE-127c-1
        # angle: boundary
        """Guards the silent-inheritance hazard. At the pinned scope (.js
        limit 1000, .ts limit 400 -- see this AC's it_requirements), a .js
        file at 999 counted lines must commit cleanly and one at 1001 must
        be refused; a .ts file at 399 must commit cleanly and one at 401
        must be refused. An implementation that adds .js/.ts to
        checked_extensions WITHOUT a matching line_limits entry silently
        inherits DEFAULT_LINE_LIMIT (400): under.js at 999 lines would then
        be wrongly refused (999 > 400) even though it is well under its
        real 1000-line limit -- that is exactly what the first assertion
        below catches.

        Run against the REAL, unmodified production check_file_size.py and
        commit_guardian.json (no fixture override) -- this tests whether
        the real scope has actually been widened, not merely whether the
        comparison logic can honor a fixture that already has the right
        numbers.

        RED TODAY: .js and .ts are not in CHECKED_EXTENSIONS at all today,
        so neither file is ever checked -- both commits complete with exit
        0 regardless of length, and the second assertion (over.js / over.ts
        must be refused) fails.
        """
        under_root = new_repo("ge127c1_boundary_under_")
        self.addCleanup(shutil.rmtree, under_root, ignore_errors=True)
        (under_root / "under.js").write_text(content(999), encoding="utf-8")
        (under_root / "under.ts").write_text(content(399), encoding="utf-8")
        stage_all(under_root)
        under_result = run_check(under_root)
        self.assertEqual(
            0,
            under_result.returncode,
            msg=(
                "under.js (999 lines, below its pinned 1000-line limit) and "
                "under.ts (399 lines, below its pinned 400-line limit) must "
                "commit cleanly at the pinned scope -- a refusal here would "
                "mean .js/.ts silently inherited DEFAULT_LINE_LIMIT (400) "
                f"instead of their own pinned limits. Got: "
                f"stdout={under_result.stdout!r} stderr={under_result.stderr!r}"
            ),
        )

        over_root = new_repo("ge127c1_boundary_over_")
        self.addCleanup(shutil.rmtree, over_root, ignore_errors=True)
        (over_root / "over.js").write_text(content(1001), encoding="utf-8")
        (over_root / "over.ts").write_text(content(401), encoding="utf-8")
        stage_all(over_root)
        over_result = run_check(over_root)
        over_combined = over_result.stdout + over_result.stderr
        self.assertNotEqual(
            0,
            over_result.returncode,
            msg=(
                "over.js (1001 > 1000) and over.ts (401 > 400) must both be "
                f"refused at the pinned scope. Got: stdout={over_result.stdout!r} "
                f"stderr={over_result.stderr!r}"
            ),
        )
        self.assertIn("over.js", over_combined, msg=f"Outcome must name over.js. Got: {over_combined!r}")
        self.assertIn("over.ts", over_combined, msg=f"Outcome must name over.ts. Got: {over_combined!r}")


if __name__ == "__main__":
    unittest.main()
