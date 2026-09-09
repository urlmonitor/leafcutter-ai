"""
MODULE: test_ge_120g_1_i
AC: GE-120g-1-i — "The leave-it-as-you-found-it rule binds a check by the
    role it declares, so a check declared to fix as it goes is not caught
    by it and no judging check can be let off it"

GOAL: TDD red-baseline tests for the role-scoping half of GE-120g-1's
    leave-it-as-you-found-it guarantee. The declared-role vocabulary this
    AC is written over already exists in this repository's own
    .pre-commit-config.yaml as a naming convention: hooks named
    ``check-*`` are the judging tier, hooks named ``transform-*`` are the
    tier declared to fix what they find as they go (see e.g.
    ``transform-doc-frontmatter``, ``transform-component-vocab``,
    ``transform-doc-index`` versus the much larger ``check-*`` population).
    This file's fixtures reuse exactly that convention rather than
    inventing one, per this AC's own doc_link relevance note that the
    split "already exists on every registered entry".

CLAUSE (a) UNDER TEST — behavioral, genuinely red today. GE-120g-1-i's
    first clause requires that a fixing check's alteration is "not
    reported as a breach" of the leave-it-as-found rule on an ORDINARY
    commit (no extra command, no extra flag, nothing invoked by hand).
    `pre-commit`'s own generic dirty-check — "files were modified by this
    hook" — is role-blind: it fails a hook's FIRST attempt whenever it
    changes tracked content, whether that hook is a `transform-*` autofix
    hook or a `check-*` judging hook. So today, a `transform-*` hook that
    does exactly what its own role promises (fixes a file in place) is
    refused on the very first ordinary commit exactly like a judging
    hook would be — there is no role-aware carve-out yet. This is
    reproduced for real below: a real git repo, the real run_hook.py, and
    a real `pre-commit install` + `git commit`.

CLAUSE (b) UNDER TEST — a brand-new, unlisted judging check must still be
    bound; and no waiver mechanism may excuse a declared-judging check.
    No exemption/waiver list of any kind exists anywhere in this
    component today (verified: no field or file under
    templates/scripts/commit_guardian/ names any check as exempt from
    anything). Because `pre-commit`'s dirty-check is applied uniformly
    with no notion of a waiver, a brand-new `check-*` hook that nobody has
    named on any list is, today, bound by exactly the same undiscriminating
    enforcement as every other hook — this half of the AC is presently
    true only as an accident of there being no differentiation at all
    (see GE-120g-1's own notes: "how many judging checks alter the working
    copy by some route other than the compiled-module cache has not been
    measured"). The test for this clause is written to the AC's own
    wording and will catch a regression the moment a role-aware
    enforcement mechanism ships with a waiver escape hatch, even though it
    may pass today for the less interesting reason that nothing
    discriminates by role at all yet.

WHY THIS MUST BE EXERCISED FOR REAL, OUT OF PROCESS — see
    unit_tests/commit_guardian/test_ge_120g_1.py's module docstring; the
    same discipline applies here. No commit_guardian module is imported;
    only the real, unmodified run_hook.py is copied to disk and driven
    through a real `pre-commit install` + `git commit`.

====================================================================
DECISION HISTORY
====================================================================
- 2026-09-09 [test-writer/GE-120g-1-i]: Initial TDD red-baseline. Reused
  the check-*/transform-* naming convention already present in the real
  .pre-commit-config.yaml as the declared-role vocabulary, rather than
  inventing a new role field no production code reads yet. Clause (a) is
  asserted behaviorally and is genuinely red today (pre-commit's own
  dirty-check is role-blind). Clause (b) is asserted behaviorally too but
  is honestly expected to be green today for the reason given above — its
  value is as a regression guard once GE-120g-1 lands a real,
  role-differentiating enforcement mechanism, not as today's red evidence
  (that load is carried by clause (a) and by
  unit_tests/commit_guardian/test_ge_120g_1.py).
====================================================================
"""
# @ac-tag: GE-120g-1-i

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]  # unit_tests/commit_guardian/ -> worktree root
_REAL_RUN_HOOK = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "run_hook.py"
_SUBPROCESS_TIMEOUT_SECONDS = 60

_TRANSFORM_CHECK_SOURCE = '''
import pathlib

here = pathlib.Path(__file__).resolve().parent
repo_root = here.parent.parent  # scripts/commit_guardian/ -> repo root
tracked = repo_root / "tracked.txt"
content = tracked.read_text(encoding="utf-8") if tracked.exists() else ""
if not content.endswith("fixed-by-transform\\n"):
    tracked.write_text(content + "fixed-by-transform\\n", encoding="utf-8")
print("FIXED: transform check applied its fix")
'''

_NEW_JUDGING_CHECK_SOURCE = '''
import pathlib

here = pathlib.Path(__file__).resolve().parent
audit_log = here / "audit_new_unlisted.log"
existing = audit_log.read_text(encoding="utf-8") if audit_log.exists() else ""
audit_log.write_text(existing + "run\\n", encoding="utf-8")
print("PASSED: brand-new, unlisted judging check found nothing to object to")
'''

_EXEMPT_FLAGGED_JUDGING_CHECK_SOURCE = '''
import pathlib

here = pathlib.Path(__file__).resolve().parent
audit_log = here / "audit_exempt_flagged.log"
existing = audit_log.read_text(encoding="utf-8") if audit_log.exists() else ""
audit_log.write_text(existing + "run\\n", encoding="utf-8")
print("PASSED: judging check declared exempt in the manifest found nothing to object to")
'''


def _fixture_precondition_ok() -> str | None:
    if not _REAL_RUN_HOOK.exists():
        return f"Fixture precondition failed: {_REAL_RUN_HOOK} does not exist."
    if shutil.which("pre-commit") is None:
        return (
            "Fixture precondition failed: 'pre-commit' is not on PATH "
            "(declared dev dependency per requirements-dev.txt; install it "
            "to run this test)."
        )
    return None


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env if env is not None else os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _init_repo(tmp_root: Path) -> None:
    _run(["git", "init", "-q"], cwd=tmp_root)
    _run(["git", "config", "user.email", "test-writer@example.com"], cwd=tmp_root)
    _run(["git", "config", "user.name", "GE-120g-1-i test fixture"], cwd=tmp_root)
    _run(["git", "config", "core.autocrlf", "false"], cwd=tmp_root)


def _install_precommit(tmp_root: Path) -> None:
    install_result = _run(["pre-commit", "install", "-f"], cwd=tmp_root)
    assert install_result.returncode == 0, (
        f"pre-commit install failed: {install_result.stdout}{install_result.stderr}"
    )


class TestFixingCheckAlterationNotReportedAsBreach(unittest.TestCase):
    """GE-120g-1-i clause (a): a check declared to fix what it finds as it
    goes (the ``transform-*`` role convention) is not caught by the
    leave-it-as-found rule — its own ordinary commit must complete, not
    be refused as though it were a judging-rule breach."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

        commit_guardian_dir = self.tmp_root / "scripts" / "commit_guardian"
        commit_guardian_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REAL_RUN_HOOK, commit_guardian_dir / "run_hook.py")
        (commit_guardian_dir / "transform_check.py").write_text(
            _TRANSFORM_CHECK_SOURCE, encoding="utf-8"
        )
        (self.tmp_root / "tracked.txt").write_text("hello\n", encoding="utf-8")

        precommit_config = (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: transform-fix-tracked\n"
            "        name: Transform Fix Tracked (declared fixing role)\n"
            "        entry: python scripts/commit_guardian/run_hook.py "
            "scripts/commit_guardian/transform_check.py\n"
            "        language: system\n"
            "        pass_filenames: false\n"
            "        always_run: true\n"
        )
        (self.tmp_root / ".pre-commit-config.yaml").write_text(precommit_config, encoding="utf-8")

        _init_repo(self.tmp_root)
        _run(["git", "add", "-A"], cwd=self.tmp_root)
        baseline = _run(["git", "commit", "-m", "baseline"], cwd=self.tmp_root)
        assert baseline.returncode == 0, f"baseline commit failed: {baseline.stdout}{baseline.stderr}"
        _install_precommit(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge_120g_1_i_fixing_check_commit_completes_on_first_ordinary_attempt(self) -> None:
        # covers: GE-120g-1-i
        # angle: criterion
        """A change staged for the transform (fixing) check to fix, then an
        ordinary commit — no extra command, no extra flag, nothing invoked
        by hand. The fixing check's alteration must not be reported as a
        breach of the judging-rule, so the FIRST ordinary commit attempt
        must complete. Today `pre-commit`'s own dirty-check is role-blind
        and refuses the first attempt regardless of declared role, so this
        must currently FAIL."""
        (self.tmp_root / "tracked.txt").write_text("hello\nneeds-a-fix\n", encoding="utf-8")
        _run(["git", "add", "tracked.txt"], cwd=self.tmp_root)

        head_before = _run(["git", "rev-parse", "HEAD"], cwd=self.tmp_root).stdout.strip()
        commit_result = _run(["git", "commit", "-m", "ordinary change needing a fix"], cwd=self.tmp_root)
        combined = commit_result.stdout + commit_result.stderr
        head_after = _run(["git", "rev-parse", "HEAD"], cwd=self.tmp_root).stdout.strip()

        self.assertEqual(
            0,
            commit_result.returncode,
            "A fixing-role check's alteration must not be reported as a "
            "breach of the judging leave-it-as-found rule — the ordinary "
            f"commit must complete on the first attempt.\n{combined}",
        )
        self.assertNotEqual(
            head_before,
            head_after,
            f"HEAD did not move — the commit did not actually complete.\n{combined}",
        )


class TestNewUnlistedJudgingCheckStillBound(unittest.TestCase):
    """GE-120g-1-i clause (b): a check newly added and named on no list
    anywhere, declaring the judging role, is bound by the leave-it-as-found
    rule from the moment it declares that role — and no judging check may
    be excused from it by any entry, flag, list, or ground."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

        commit_guardian_dir = self.tmp_root / "scripts" / "commit_guardian"
        commit_guardian_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REAL_RUN_HOOK, commit_guardian_dir / "run_hook.py")
        (commit_guardian_dir / "new_unlisted_check.py").write_text(
            _NEW_JUDGING_CHECK_SOURCE, encoding="utf-8"
        )
        (self.tmp_root / "tracked.txt").write_text("hello\n", encoding="utf-8")

        precommit_config = (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: check-brand-new-unlisted\n"
            "        name: Brand New Unlisted Judging Check\n"
            "        entry: python scripts/commit_guardian/run_hook.py "
            "scripts/commit_guardian/new_unlisted_check.py\n"
            "        language: system\n"
            "        pass_filenames: false\n"
            "        always_run: true\n"
        )
        (self.tmp_root / ".pre-commit-config.yaml").write_text(precommit_config, encoding="utf-8")

        _init_repo(self.tmp_root)

        # Seed: run once outside the guarded path, so the byproduct is
        # already tracked content before the real test attempt (mirrors
        # GE-120g-1's mandatory seeding order).
        check_script = commit_guardian_dir / "new_unlisted_check.py"
        seed_result = _run([sys.executable, str(check_script)], cwd=self.tmp_root)
        assert seed_result.returncode == 0, f"seeding run failed: {seed_result.stdout}{seed_result.stderr}"
        _run(["git", "add", "-A"], cwd=self.tmp_root)
        baseline = _run(["git", "commit", "-m", "baseline"], cwd=self.tmp_root)
        assert baseline.returncode == 0, f"baseline commit failed: {baseline.stdout}{baseline.stderr}"
        _install_precommit(self.tmp_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge_120g_1_i_unlisted_judging_check_alteration_still_caught(self) -> None:
        # covers: GE-120g-1-i
        # angle: criterion
        """A judging check that is brand new and named on no list anywhere
        must be bound by the leave-it-as-found rule from the moment it
        declares the judging role. Its side effect (appending to its own
        audit file) must still be caught the same as any other judging
        check's would be — an ordinary commit must not silently succeed
        while leaving that new content behind."""
        (self.tmp_root / "tracked.txt").write_text("hello\nworld\n", encoding="utf-8")
        _run(["git", "add", "tracked.txt"], cwd=self.tmp_root)

        commit_result = _run(["git", "commit", "-m", "ordinary change"], cwd=self.tmp_root)
        combined = commit_result.stdout + commit_result.stderr
        status_after = _run(["git", "status", "--porcelain"], cwd=self.tmp_root).stdout

        commit_silently_succeeded_with_leftovers = (
            commit_result.returncode == 0 and status_after != ""
        )
        self.assertFalse(
            commit_silently_succeeded_with_leftovers,
            "A brand-new, unlisted judging check's alteration must be "
            "caught, not silently let through as a successful commit that "
            f"leaves new content behind. git status --porcelain after:\n"
            f"{status_after!r}\nFull pre-commit output:\n{combined}",
        )

    def test_ge_120g_1_i_no_exemption_mechanism_lets_a_judging_check_off(self) -> None:
        # covers: GE-120g-1-i
        # angle: boundary
        """No entry, flag, list, or ground anywhere in the commit_guardian
        component may excuse a declared-judging check from the
        leave-it-as-found rule. Proved behaviorally: a plausible
        exemption-shaped entry (an ``exempt``/``waiver`` field naming this
        very check) is added to the manifest ``run_hook.py`` reads
        (``commit_guardian.json``'s ``hooks_manifest.hooks[]``), the named
        judging check is made to alter tracked content, and an ordinary
        commit is run. The alteration must still be reverted — the
        exemption-shaped entry must be ignored — because ``run_hook.py``'s
        ``_is_fixing_role`` only ever reads the ``tier`` field and only ever
        treats the literal ``"transform"`` tier as fixing; every other tier
        value, including one spelled ``"exempt"`` itself, still takes the
        judging (revert) path. A test that only grepped for the word
        "exempt" in the source tree could not tell "no exemption mechanism
        exists" apart from "an exemption mechanism exists but sits in a file
        this test didn't look at" — this asserts the runner's actual
        behavior instead."""
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp_root = Path(tmp_name)
            commit_guardian_dir = tmp_root / "scripts" / "commit_guardian"
            commit_guardian_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_REAL_RUN_HOOK, commit_guardian_dir / "run_hook.py")
            (commit_guardian_dir / "exempt_flagged_check.py").write_text(
                _EXEMPT_FLAGGED_JUDGING_CHECK_SOURCE, encoding="utf-8"
            )
            (tmp_root / "tracked.txt").write_text("hello\n", encoding="utf-8")

            manifest = {
                "hooks_manifest": {
                    "hooks": [
                        {
                            "id": "check-exempt-flagged",
                            "tier": "exempt",
                            "exempt": True,
                            "waiver": "approved pending refactor — must not be honored",
                            "entry": (
                                "python scripts/commit_guardian/run_hook.py "
                                "scripts/commit_guardian/exempt_flagged_check.py"
                            ),
                        }
                    ]
                }
            }
            (commit_guardian_dir / "commit_guardian.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

            precommit_config = (
                "repos:\n"
                "  - repo: local\n"
                "    hooks:\n"
                "      - id: check-exempt-flagged\n"
                "        name: Judging Check Declared Exempt In The Manifest\n"
                "        entry: python scripts/commit_guardian/run_hook.py "
                "scripts/commit_guardian/exempt_flagged_check.py\n"
                "        language: system\n"
                "        pass_filenames: false\n"
                "        always_run: true\n"
            )
            (tmp_root / ".pre-commit-config.yaml").write_text(precommit_config, encoding="utf-8")

            _init_repo(tmp_root)
            _run(["git", "add", "-A"], cwd=tmp_root)
            baseline = _run(["git", "commit", "-m", "baseline"], cwd=tmp_root)
            assert baseline.returncode == 0, f"baseline commit failed: {baseline.stdout}{baseline.stderr}"
            _install_precommit(tmp_root)

            (tmp_root / "tracked.txt").write_text("hello\nworld\n", encoding="utf-8")
            _run(["git", "add", "tracked.txt"], cwd=tmp_root)

            audit_log = commit_guardian_dir / "audit_exempt_flagged.log"
            commit_result = _run(["git", "commit", "-m", "ordinary change"], cwd=tmp_root)
            combined = commit_result.stdout + commit_result.stderr
            status_after = _run(["git", "status", "--porcelain"], cwd=tmp_root).stdout
            audit_log_survived = audit_log.exists()
            audit_log_in_history = _run(
                ["git", "show", "HEAD:scripts/commit_guardian/audit_exempt_flagged.log"],
                cwd=tmp_root,
            ).returncode == 0

            # Two distinct ways an "exempt" entry could be wrongly honored:
            # (1) left as an untracked leftover (caught by status_after), or
            # (2) treated as a FIXING alteration and folded straight into the
            # commit (clean status, but the file now exists on disk and is
            # part of HEAD) — status alone cannot tell these apart from a
            # correctly-reverted run, so both are checked directly.
            commit_silently_succeeded_with_leftovers = (
                commit_result.returncode == 0 and status_after != ""
            )
            self.assertFalse(
                commit_silently_succeeded_with_leftovers,
                "A manifest entry naming a judging check as exempt/waived "
                "must not excuse it from the leave-it-as-found rule — its "
                "own alteration must still be reverted on an ordinary "
                f"commit, not silently left behind.\ngit status --porcelain "
                f"after:\n{status_after!r}\nFull pre-commit output:\n{combined}",
            )
            self.assertFalse(
                audit_log_survived or audit_log_in_history,
                "The exempt-flagged judging check's own alteration must be "
                "reverted, not accepted into the commit as though it were a "
                "fixing check's legitimate fix. audit log exists on disk: "
                f"{audit_log_survived}; audit log present in HEAD: "
                f"{audit_log_in_history}.\nFull pre-commit output:\n{combined}",
            )


if __name__ == "__main__":
    unittest.main()
