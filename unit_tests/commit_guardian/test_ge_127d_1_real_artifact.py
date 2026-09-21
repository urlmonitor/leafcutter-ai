"""
MODULE: unit_tests/commit_guardian/test_ge_127d_1_real_artifact.py
COVERS: GE-127d-1 -- "The published rule and the enforced rule are checked
    against each other, and no fact the standard accepts about a change is
    left without effect on its verdict"

GOAL: Real-artifact regression descriptors (CLAUDE.md's "Real-artifact
    behavioral spot-check" convention; BP-1100f-2). The existing "how long"
    descriptor in `test_ge_127d_1_scope_extension.py` invented its own
    phrasing ("Python (.py) files: 400 lines max per file.") to exercise
    `_LIMIT_PATTERN`. That invented phrasing matches the pattern; the REAL
    surfaces the shipped gate watches -- `commit_guardian.json`'s
    `file_size._comment` ("... .py 400 (unchanged), .sql 600 (unchanged),
    ...") and README.md's schema-table row (`` `line_limits` | object |
    `{".py": 400, ".sql": 600}` ``) -- do not. Neither real surface ever
    places the literal word "line"/"lines" immediately after a digit run,
    so `_LIMIT_PATTERN` extracts ZERO claims from either real surface,
    mutated or not. A synthetic fixture that happens to match a regex the
    real data never matches reproduces exactly the bug-hiding bias
    CLAUDE.md's convention warns against: the invented-phrasing descriptor
    was green while the gate stayed blind on the actual on-disk data
    format it exists to watch.

    This file derives its fixture bytes from the REAL, on-disk
    `commit_guardian.json` and `README.md` (read via `Path.read_text`,
    never hand-typed), per the Fixture Authenticity Rule (test-writer
    skill 2h.2): the test proves the gate against the actual artifact, not
    against the test author's mental model of what that artifact says.

SCOPE:
    - `TestRealSurfaceLimitClaimMutationIsCaught`: takes the REAL
      `file_size._comment`, mutates ONE stated number (`.py 400` ->
      `.py 999`) while leaving the enforced `line_limits['.py']` in the
      fixture tree at 400, and asserts the gate refuses. RED TODAY:
      `_LIMIT_PATTERN` finds no claim in either the original or the
      mutated real text (no "line"/"lines" word follows any digit run in
      this phrasing), so the gate reports agreement (exit 0) regardless of
      the mutation -- the exact "genuine regression ships silently"
      failure this ticket's own comment describes.
    - `TestRealSurfaceYieldsNonEmptyLimitClaims`: asserts the gate's own
      `_extract_limit_claims`, run directly against the REAL (unmutated)
      `_comment`, returns a NON-EMPTY claim set. A gate that extracts zero
      claims from a surface plainly stating seven per-kind limits has
      examined nothing and calls it agreement -- worth pinning on its own,
      not only via the mutation descriptor above (per this ticket's own
      "your judgement" prompt). RED TODAY for the same underlying reason:
      the real surface yields `{}`.

BOTH DESCRIPTORS CONFIRMED RED TODAY by running the shipped
    `_extract_limit_claims` directly against the real, unmutated
    `commit_guardian.json` `_comment` text before authoring this file: it
    returns `{}`, and a hand-mutated copy of that same text also returns
    `{}` -- the mutation has zero effect on what the gate can see.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127d-1.yaml and its parent GE-127d.yaml.

DECISION HISTORY
- 2026-09-21 [GE-127d-1/test-writer]: Initial authoring, pinning the real-
    artifact gap pr-reviewer (10:45) and ac-validator (11:05) independently
    found in the invented-phrasing "how long" descriptor.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_1_fixture as fx  # noqa: E402

_REAL_COMMIT_GUARDIAN_JSON = fx._COMMIT_GUARDIAN_SRC / "commit_guardian.json"
_REAL_README = fx._COMMIT_GUARDIAN_SRC / "README.md"


def _load_real_config() -> dict:
    """Read and parse the REAL, on-disk commit_guardian.json verbatim."""
    return json.loads(_REAL_COMMIT_GUARDIAN_JSON.read_text(encoding="utf-8"))


class TestRealSurfaceLimitClaimMutationIsCaught(unittest.TestCase):
    """Real-artifact regression: mutate ONE real claimed number, leave the
    real enforced limit untouched in the fixture tree, and require a
    refusal.
    """

    def test_ge_127d_1_a_mutated_real_comment_limit_claim_refuses_the_commit(self):
        # covers: GE-127d-1
        # angle: real_artifact
        """MUTATION, DERIVED FROM THE REAL SURFACE (not hand-typed): the
        real `file_size._comment` states "`.py 400 (unchanged)`"; the copy
        used here states "`.py 999 (unchanged)`" instead, while the
        fixture tree's enforced `line_limits['.py']` stays 400 -- the
        exact drift class this ticket's comment names (a genuine
        regression -- someone bumps the enforced limit, or here,
        symmetrically, edits the published comment -- and leaves the other
        side stale).

        RED BASELINE: `_LIMIT_PATTERN` never matches this real phrasing
        (no "line"/"lines" word follows the digit run), so the gate finds
        zero limit claims in the mutated text too and exits 0 -- the
        mutation has NO effect on the verdict, which is exactly the bug.
        """
        real_config = _load_real_config()
        real_comment = real_config["file_size"]["_comment"]
        real_readme = _REAL_README.read_text(encoding="utf-8")

        needle = ".py 400 (unchanged)"
        self.assertIn(
            needle,
            real_comment,
            msg=(
                "fixture assumption stale: the real commit_guardian.json "
                f"_comment no longer contains {needle!r} -- update this "
                "mutation to match the real surface's current phrasing."
            ),
        )
        self.assertEqual(
            1,
            real_comment.count(needle),
            msg=f"expected exactly one occurrence of {needle!r} to mutate unambiguously. Got: {real_comment.count(needle)}",
        )
        mutated_comment = real_comment.replace(needle, ".py 999 (unchanged)")
        self.assertNotEqual(real_comment, mutated_comment, msg="mutation had no effect on the real comment text")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = fx.copy_production_modules(root)

            mutated_config = json.loads(json.dumps(real_config))  # deep copy, real shape preserved
            mutated_config["file_size"]["_comment"] = mutated_comment
            # The ENFORCED limit stays exactly as real production has it --
            # only the published claim text is mutated.
            self.assertEqual(
                400,
                mutated_config["file_size"]["line_limits"].get(".py"),
                msg="fixture sanity: the enforced .py limit must stay at the real value (400)",
            )

            (dest / "commit_guardian.json").write_text(json.dumps(mutated_config, indent=2), encoding="utf-8")
            (dest / "README.md").write_text(real_readme, encoding="utf-8")

            result = fx.run_direct(root)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                0,
                result.returncode,
                msg=(
                    "a real-format surface whose claimed .py limit (999) contradicts "
                    "the enforced limit (400) must refuse the commit, naming the "
                    f"disagreement. Got exit={result.returncode!r} output={combined!r}"
                ),
            )
            self.assertIn(
                "commit_guardian.json",
                combined,
                msg=f"the outcome must name the offending surface. Got: {combined!r}",
            )


class TestRealSurfaceYieldsNonEmptyLimitClaims(unittest.TestCase):
    """The gate's own extraction function must find SOMETHING in a surface
    that plainly states seven per-kind limits -- "examined nothing looks
    like found nothing" is a failure worth pinning directly, not only via
    the mutation descriptor above.
    """

    def test_ge_127d_1_the_real_unmutated_comment_yields_a_non_empty_limit_claim_set(self):
        # covers: GE-127d-1
        # angle: boundary
        """Runs the gate's REAL `_extract_limit_claims` (the shipped
        module, copied verbatim into a throwaway fixture directory, never
        re-implemented here) against the REAL, unmutated
        `file_size._comment`, which plainly states seven per-kind limits
        (.py, .sql, .js, .mjs, .ts, .tsx, .sh). The boundary pinned here is
        empty-vs-non-empty: a gate that extracts `{}` from a surface
        stating seven limits has examined nothing and calls it agreement.

        RED BASELINE: `_LIMIT_PATTERN` requires a "line"/"lines" word
        immediately after the digit run; this real phrasing never has
        one, so extraction returns `{}` today.
        """
        real_config = _load_real_config()
        real_comment = real_config["file_size"]["_comment"]
        real_readme = _REAL_README.read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = fx.copy_production_modules(root)
            # config.py raises FileNotFoundError at IMPORT TIME if
            # commit_guardian.json is absent beside it -- write the real,
            # unmutated config (and README, one of its two configured
            # published_rule_surfaces) so the module import below succeeds.
            (dest / "commit_guardian.json").write_text(json.dumps(real_config, indent=2), encoding="utf-8")
            (dest / "README.md").write_text(real_readme, encoding="utf-8")

            driver = dest / "_driver.py"
            driver.write_text(
                "import sys, json\n"
                f"sys.path.insert(0, {str(dest)!r})\n"
                "from check_file_size_rule_parity import _extract_limit_claims, _in_scope_portion\n"
                f"comment = {real_comment!r}\n"
                "claims = _extract_limit_claims(_in_scope_portion(comment))\n"
                "print(json.dumps(claims))\n",
                encoding="utf-8",
            )
            result = fx.run([fx.PYTHON, str(driver)], root)

        self.assertEqual(
            0, result.returncode, msg=f"the driver itself must run cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        claims = json.loads(result.stdout.strip())
        self.assertTrue(
            claims,
            msg=(
                "the real, unmutated file_size._comment plainly states seven "
                "per-kind line limits (.py 400, .sql 600, .js 1000, .mjs 1000, "
                ".ts 400, .tsx 400, .sh 400), yet _extract_limit_claims found "
                f"none. Got: {claims!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
