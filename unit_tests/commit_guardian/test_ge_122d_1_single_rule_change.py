"""
MODULE: unit_tests/commit_guardian/test_ge_122d_1_single_rule_change.py
GOAL: Cover GE-122d-1's ``test_single_rule_change_propagates_to_all_three_stages``
    descriptor: a number shape previously accepted is made contested by an
    edit in exactly ONE place; both real stage entry points are re-invoked,
    with no second or third definition edited, and both must report the
    newly contested case.
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
BUSINESS CONTEXT: GE-122d-1's own amended_by history records that the prior
    version of this test ran the commit-time CLI with ``cwd`` set to a
    NON-GIT tempdir. ``_get_staged_paths()`` (shared by both stages) shells
    out to ``git diff --cached --name-only`` and returns ``None`` when that
    call fails (e.g. "not a git repository"); both stages then fall back to
    their literal ``not verdict.passed`` whole-collection outcome rather
    than a real attribution decision. The prior test's BEFORE/AFTER
    assertions therefore only ever exercised that fallback branch -- a code
    path real production invocations never take, since both stages are
    always run inside the repository whose collection they inspect. "AFTER
    the single-place extension ... exit 1" held only OUTSIDE a git
    repository, which is the opposite of the condition the AC's criteria
    describes.
    This rewrite builds a real git repository, STAGES a real file, and
    keeps that exact staged change set constant across the BEFORE and AFTER
    invocations -- so the one variable that changes between the two
    measurements is the single-place rule edit itself, and the attribution
    machinery (``compute_commit_disposition``, shared by both real stages)
    is genuinely exercised rather than bypassed by a fail-open fallback.
    THE CHOSEN "PREVIOUSLY ACCEPTED" SHAPE: two ADR filenames whose numeric
    segments are the same integer under two different string spellings --
    ``ADR-001-alpha.md`` and ``ADR-1-beta.md``. Confirmed empirically
    (2026-09-01, against the current deployed layout) that today's
    ``scan_decisions`` treats these as two DIFFERENT numbers (raw string
    comparison of the regex capture group, ``"001" != "1"``), so this
    fixture reports a clean (non-blocking) verdict at both real stages
    before any edit. The single-place extension made by this test --
    widening ``scan_decisions``'s ``number_of`` callable from
    ``lambda m: m.group(1)`` to ``lambda m: str(int(m.group(1)))`` in
    ``_uniqueness_scanners.py`` -- is exactly the "ONE place" both real
    stage entry points resolve their sibling scanner import from (see
    check_identifier_uniqueness_authoring.py's ARCHITECTURE note: both the
    commit-time module and the authoring-time module load the SAME file on
    disk), so editing that one file's one line is a real single-place
    extension, never a simulated one.
ARCHITECTURE: Copies the real templates into a scratch dir shaped like the
    deployed layout (``hooks/`` sibling to ``scripts/commit_guardian/``,
    matching test_ge_122d_1_no_stage_disagreement.py's precedent). Builds
    one real git repository holding the leading-zero ADR pair, commits it,
    then stages a trivial re-write of ONE of the two files -- this staged
    change set is held constant across both the BEFORE and AFTER
    measurements. Both real stage entry points are invoked as actual
    subprocesses (commit-time via its documented CLI usage; authoring-time
    via the real PostToolUse JSON-on-stdin shape) with ``cwd`` set to the
    fixture repo root -- load-bearing for the same
    ``_get_staged_paths``-resolves-cwd reason documented in the sibling
    disagreement-matrix test.

DOC_LINKS:
  - templates/scripts/commit_guardian/_uniqueness_scanners.py
  - templates/hooks/check_identifier_uniqueness_authoring.py
  - unit_tests/commit_guardian/test_ge_122d_1_no_stage_disagreement.py

DECISION HISTORY:
  - 2026-09-01 [test-writer/GE-122d-1]: Rewritten from scratch. The prior
    version's non-git tempdir defect is documented above and in this AC's
    own amended_by history. Verified RED against a reintroduction of the
    ``verdict.passed`` vs ``blocking`` defect before confirming GREEN
    against the current (fixed) hook -- see the sign-off comment for the
    exact mutation diff and captured red output.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AUTHORING_SRC = _REPO_ROOT / "templates" / "hooks" / "check_identifier_uniqueness_authoring.py"
_SHARED_SRC_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

_OLD_NUMBER_OF = "lambda m: m.group(1)"
_NEW_NUMBER_OF = "lambda m: str(int(m.group(1)))"

_SUBPROCESS_TIMEOUT_SECONDS = 30


class TestSingleRuleChangePropagatesToBothRealStages(unittest.TestCase):
    def setUp(self) -> None:
        self._scratch_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._scratch_tmp.cleanup)
        scratch_root = Path(self._scratch_tmp.name)

        self.scripts_dir = scratch_root / "deploy" / "scripts" / "commit_guardian"
        self.scripts_dir.mkdir(parents=True)
        for src in _SHARED_SRC_DIR.glob("*.py"):
            shutil.copy2(src, self.scripts_dir / src.name)

        hooks_dir = scratch_root / "deploy" / "hooks"
        hooks_dir.mkdir(parents=True)
        self.authoring_script = hooks_dir / _AUTHORING_SRC.name
        shutil.copy2(_AUTHORING_SRC, self.authoring_script)

        self.commit_script = self.scripts_dir / "check_identifier_uniqueness.py"
        self.scanners_path = self.scripts_dir / "_uniqueness_scanners.py"

        self._fixture_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._fixture_tmp.cleanup)
        self.fixture_root = Path(self._fixture_tmp.name)
        self._build_leading_zero_git_fixture()

    def _build_leading_zero_git_fixture(self) -> None:
        """A real git repo, scaffolding all four GE-122 namespaces, holding
        two ADR files that name the SAME integer under two different
        digit-string spellings -- committed, then with ONE of the two
        STAGED (a change set held constant across BEFORE and AFTER)."""
        (self.fixture_root / "docs" / "acceptance-criteria").mkdir(parents=True)
        adrs = self.fixture_root / "docs" / "architecture" / "adrs"
        adrs.mkdir(parents=True)
        (self.fixture_root / "docs" / "architecture" / "diagrams").mkdir(parents=True)
        tickets_dir = self.fixture_root / "tickets"
        tickets_dir.mkdir(parents=True)
        (tickets_dir / "ticket_lifecycle.json").write_text(json.dumps({"folders": []}), encoding="utf-8")

        self.adr_alpha = adrs / "ADR-001-alpha.md"
        self.adr_beta = adrs / "ADR-1-beta.md"
        self.adr_alpha.write_text("# alpha\n", encoding="utf-8")
        self.adr_beta.write_text("# beta\n", encoding="utf-8")

        subprocess.run(
            ["git", "init", "-q"], cwd=self.fixture_root, check=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS
        )
        subprocess.run(
            ["git", "config", "user.email", "test-writer@example.com"],
            cwd=self.fixture_root,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        subprocess.run(
            ["git", "config", "user.name", "test-writer"],
            cwd=self.fixture_root,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=self.fixture_root, check=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "leading-zero ADR pair, accepted"],
            cwd=self.fixture_root,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

        # Stage a trivial re-write of ONE of the two files. This staged
        # change set is held CONSTANT across the BEFORE and AFTER
        # measurements below -- the single variable that changes between
        # them is the scanner edit itself, never the git state.
        self.adr_beta.write_text("# beta (touched)\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", str(self.adr_beta)],
            cwd=self.fixture_root,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

    def _run_commit_stage(self) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL commit-time CLI entry point as a subprocess,
        with cwd set to the fixture repo root (load-bearing for
        ``_get_staged_paths``)."""
        return subprocess.run(
            [sys.executable, str(self.commit_script)],
            cwd=self.fixture_root,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )

    def _run_authoring_stage(self) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL authoring-time hook as a subprocess, fed the
        real PostToolUse JSON payload shape on stdin, with cwd set to the
        fixture repo root."""
        payload = json.dumps({"tool_input": {"file_path": str(self.adr_beta)}})
        return subprocess.run(
            [sys.executable, str(self.authoring_script)],
            cwd=self.fixture_root,
            input=payload,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )

    def _apply_single_place_extension(self) -> None:
        content = self.scanners_path.read_text(encoding="utf-8")
        self.assertIn(
            _OLD_NUMBER_OF,
            content,
            "The expected single-place extension seam "
            "(_uniqueness_scanners.py's scan_decisions number_of lambda) is not "
            "present in the form this test expects -- the seam this AC requires "
            "may have moved or already been renamed. Update this test's constants.",
        )
        self.scanners_path.write_text(content.replace(_OLD_NUMBER_OF, _NEW_NUMBER_OF), encoding="utf-8")

    def test_single_rule_change_propagates_to_both_real_stages(self) -> None:
        # covers: GE-122d-1
        # angle: reachability
        # --- BEFORE: the leading-zero shape is accepted (not contested) at
        # BOTH real stages, with the staged change set already in place ---
        before_commit = self._run_commit_stage()
        self.assertEqual(
            before_commit.returncode,
            0,
            "BEFORE the single-place extension, the commit-time stage (real "
            f"CLI subprocess) must report exit 0. Got exit "
            f"{before_commit.returncode}, stderr:\n{before_commit.stderr}",
        )

        before_authoring = self._run_authoring_stage()
        self.assertEqual(
            before_authoring.returncode,
            0,
            "BEFORE the single-place extension, the authoring stage (real "
            f"PostToolUse subprocess) must also report exit 0 (non-blocking). "
            f"Got exit {before_authoring.returncode}, stderr:\n{before_authoring.stderr}",
        )

        # --- THE SINGLE-PLACE EXTENSION (made in ONE file) ---
        self._apply_single_place_extension()

        # --- AFTER: no second or third definition of the rule was touched,
        # and the staged change set is UNCHANGED from the BEFORE measurement ---
        after_commit = self._run_commit_stage()
        self.assertEqual(
            after_commit.returncode,
            1,
            "AFTER the single-place extension, the commit-time stage (real "
            "CLI subprocess, same staged change set as BEFORE) must report "
            f"exit 1 (blocking). Got exit {after_commit.returncode}, "
            f"stdout:\n{after_commit.stdout}\nstderr:\n{after_commit.stderr}",
        )

        after_authoring = self._run_authoring_stage()
        self.assertEqual(
            after_authoring.returncode,
            2,
            "AFTER the single-place extension -- made ONLY in "
            "_uniqueness_scanners.py, never in the authoring hook module -- the "
            "authoring stage (real PostToolUse subprocess, same staged change "
            "set as BEFORE) must ALSO report exit 2 (blocking). If this fails "
            "while the commit-time subprocess above reports blocking, the two "
            "real stages hold independent copies of the rule (GE-122d-1's "
            f"coverage note names this exact failure). Got exit "
            f"{after_authoring.returncode}, stderr:\n{after_authoring.stderr}",
        )
        self.assertIn("1 is claimed by more than one artifact", after_authoring.stderr)


if __name__ == "__main__":
    unittest.main()
