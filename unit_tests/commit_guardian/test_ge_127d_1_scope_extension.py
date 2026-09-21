"""
MODULE: unit_tests/commit_guardian/test_ge_127d_1_scope_extension.py
COVERS: GE-127d-1 -- "The published rule and the enforced rule are checked
    against each other, and no fact the standard accepts about a change is
    left without effect on its verdict"

GOAL: RED test-first descriptors for the two facts H-2 (pr-reviewer 10:45,
    independently reproduced by ac-validator 11:05) found missing from
    `check_file_size_rule_parity.py`. The AC's own Gherkin names three
    compound facts a published surface may state about the size rule --
    "which kinds", "when it applies", "how long" -- and the ticket's own
    `Expects From: GE-127a-1` contract separately names the enforced
    when-it-applies behaviour and the per-kind limits (FILE_LINE_LIMITS) as
    inputs this record must consume. `test_ge_127d_1.py` already covers
    "which kinds" (see its own sibling `_ge_127d_1_fixture.py` docstring for
    that scope decision); this file covers the other two.

WHY A SIBLING FILE, NOT AN ADDITION TO test_ge_127d_1.py: that file is
    already at its 400-line ratchet capacity (407 lines); growing it further
    would refuse its own commit under GE-127b-1's ratchet. Test-runner
    invocations that use the LITERAL pattern `-p "test_ge_127d_1.py"` will
    NOT discover this file -- re-run with `-p "test_ge_127d_1*.py"`.

SCOPE, PER DESCRIPTOR:
    - "when it applies": whether a surface's exemption-vs-no-exemption claim
      (new-files-only vs every-changed-file) agrees with the REAL enforced
      behaviour. This fact is not stored in commit_guardian.json anywhere --
      it is pure code behaviour (the ratchet in `_classify_file` applies to
      MODIFIED files too) -- so each descriptor first EXERCISES the real,
      unmodified `check_file_size.py` against a live git scenario to prove
      the enforced fact behaviourally (per this AC's own "evaluate the
      enforced side by EXERCISING the gate" constraint), then runs the
      (currently unextended) parity gate and requires it to catch a surface
      that claims otherwise.
    - "how long": whether a surface's claimed numeric per-kind line limit
      agrees with the REAL, enforced `file_size.line_limits` in
      commit_guardian.json (mirroring FILE_LINE_LIMITS in the real package).
      This IS a config value, read directly, exactly as the existing "which
      kinds" comparison already reads `checked_extensions` -- no additional
      exercising is required for this one.

ANCHOR-HEURISTIC NOTE (pr-reviewer 10:45, medium finding): both surface
    texts here are single-purpose (state only the file-size rule, nothing
    else), so `_relevant_excerpt`'s anchor-token narrowing is never
    triggered either way -- this test does not rely on, and does not probe,
    the DEFAULT-vs-ENFORCED distinction that finding flags as fragile.

BOTH DESCRIPTORS BELOW ARE RED TODAY: the shipped
    `check_file_size_rule_parity.py` reads only `CHECKED_EXTENSIONS` (see
    its own module docstring, "SCOPE OF THE FACT COMPARED: which KINDS...")
    and exits 0 whenever kinds agree, regardless of what a surface claims
    about when the rule applies or how long a file may be.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127d-1.yaml and its parent GE-127d.yaml.

DECISION HISTORY
- 2026-09-21 [GE-127d-1/test-writer]: Initial authoring of the two H-2
    descriptors (when-it-applies, how-long), split from test_ge_127d_1.py
    per that file's own ratchet capacity.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_1_fixture as fx  # noqa: E402


def _build_tree(root: Path, *, checked_extensions: list[str], line_limit: int, readme_text: str, comment_text: str) -> Path:
    """Compose a reconciliation fixture tree with ARBITRARY surface texts.

    Unlike `_ge_127d_1_fixture.build_fixture_tree`, which always writes
    kinds-only prose via `surface_text()`, this helper accepts the caller's
    own README/`_comment` text verbatim, so a "when it applies" or "how
    long" claim can be embedded without disturbing the "which kinds" claim.
    """
    dest = fx.copy_production_modules(root)
    line_limits = {ext: line_limit for ext in checked_extensions}
    config = {
        "file_size": {
            "_comment": comment_text,
            "line_limits": line_limits,
            "default_limit": line_limit,
            "checked_extensions": checked_extensions,
            "published_rule_surfaces": ["README.md", "commit_guardian.json"],
        }
    }
    (dest / "commit_guardian.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (dest / "README.md").write_text(readme_text, encoding="utf-8")
    return dest


class TestWhenItAppliesClaimDisagreeingWithEnforcedBehaviourRefusesCommit(unittest.TestCase):
    """H-2, WHEN-IT-APPLIES AXIS. A surface claiming a new-files-only
    exemption, while the real ratchet enforces every changed file, must be
    caught -- the exact drift class this AC exists to prevent (a future
    edit reintroducing that exemption in prose while GE-127b-1's ratchet
    stays intact in code).
    """

    def test_ge_127d_1_a_when_it_applies_claim_disagreeing_with_the_enforced_behaviour_refuses_the_commit(self):
        # covers: GE-127d-1
        # angle: criterion
        """ORACLE STEP (exercise the REAL, unmodified check_file_size.py):
        a pre-existing, tracked .py file that grows past its limit must be
        refused -- proving behaviourally that the rule applies to MODIFIED
        files, not only newly added ones.

        GATE STEP: with that enforced fact established, a fixture tree
        whose README.md claims the OPPOSITE ("new files only") -- while
        agreeing with the enforced kinds and while commit_guardian.json's
        own `_comment` states the rule correctly -- must be refused by
        `check_file_size_rule_parity.py`, naming README.md.

        RED BASELINE: today's gate compares only "which kinds"; kinds agree
        here, so it exits 0 regardless of the when-it-applies claim.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = fx.copy_production_modules(root)

            # ORACLE: prove the enforced fact behaviourally, via a real repo.
            fx.init_repo(root)
            tracked = root / "tracked.py"
            tracked.write_text("a = 1\nb = 2\n", encoding="utf-8")  # 2 lines, within limit=5
            fx.git(["add", "tracked.py"], root)
            initial_commit = fx.git(["commit", "-m", "initial"], root)
            self.assertEqual(0, initial_commit.returncode, msg=f"fixture setup: initial commit must succeed. Got: {initial_commit.stdout!r}{initial_commit.stderr!r}")

            # Config needed for check_file_size.py itself (limit=5 for .py).
            config = {"file_size": {"_comment": "", "line_limits": {".py": 5}, "default_limit": 5, "checked_extensions": [".py"], "published_rule_surfaces": ["README.md", "commit_guardian.json"]}}
            (dest / "commit_guardian.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
            (dest / "README.md").write_text("placeholder\n", encoding="utf-8")

            tracked.write_text("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\n", encoding="utf-8")  # grew to 6 > limit=5
            fx.git(["add", "tracked.py"], root)
            oracle = fx.run([fx.PYTHON, str(dest / "check_file_size.py")], root)
            self.assertNotEqual(
                0,
                oracle.returncode,
                msg=(
                    "ORACLE FAILED: a pre-existing tracked file growing past its limit "
                    f"was not refused -- cannot establish the enforced fact. Got: {oracle.stdout!r}{oracle.stderr!r}"
                ),
            )

            # GATE STEP: README wrongly claims a new-files-only exemption.
            (dest / "README.md").write_text(
                "Enforces line limits on .py files. Applies only to newly added files; "
                "modifications to existing large files are exempt as an incremental "
                "refactor path.\n",
                encoding="utf-8",
            )
            config["file_size"]["_comment"] = (
                "Enforces line limits on .py files. Applies to every changed file of a "
                "covered kind, not only newly added ones.\n"
            )
            (dest / "commit_guardian.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

            result = fx.run_direct(root)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                0,
                result.returncode,
                msg=(
                    "a surface claiming a new-files-only exemption, while the enforced "
                    f"behaviour applies to every changed file, must be refused. Got: {combined!r}"
                ),
            )
            self.assertIn("README.md", combined, msg=f"the outcome must name the offending surface. Got: {combined!r}")


class TestHowLongClaimDisagreeingWithEnforcedLimitRefusesCommit(unittest.TestCase):
    """H-2, HOW-LONG AXIS. A surface's claimed numeric per-kind limit must
    agree with the real, enforced `file_size.line_limits` -- read directly,
    exactly as the existing "which kinds" comparison already reads
    `checked_extensions`.
    """

    def test_ge_127d_1_a_how_long_claim_disagreeing_with_the_enforced_limit_refuses_the_commit(self):
        # covers: GE-127d-1
        # angle: criterion
        """README.md claims ".py files: 400 lines max" while the real
        enforced `file_size.line_limits['.py']` is 5; commit_guardian.json's
        own `_comment` states the CORRECT number, so only README disagrees.
        Kinds and when-it-applies both agree everywhere in this fixture, so
        the only drift is the numeric claim.

        RED BASELINE: today's gate never reads a claimed number at all.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme_text = (
                "Enforces line limits on .py files. Applies to every changed file of a "
                "covered kind, not only newly added ones. Python (.py) files: 400 lines "
                "max per file.\n"
            )
            comment_text = (
                "Enforces line limits on .py files. Applies to every changed file of a "
                "covered kind, not only newly added ones. Python (.py) files: 5 lines "
                "max per file.\n"
            )
            _build_tree(root, checked_extensions=[".py"], line_limit=5, readme_text=readme_text, comment_text=comment_text)

            result = fx.run_direct(root)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                0,
                result.returncode,
                msg=(
                    "README.md claims a 400-line limit while the enforced limit is 5; "
                    f"this disagreement must refuse the commit. Got: {combined!r}"
                ),
            )
            self.assertIn("README.md", combined, msg=f"the outcome must name the offending surface. Got: {combined!r}")


if __name__ == "__main__":
    unittest.main()
