"""
MODULE: test_ge_120e_1
AC: GE-120e-1 — "A check that works out its own change set works out the
    author's change, not everything the staged tree happens to hold"
GOAL: TDD red-baseline tests for the shared authored-change-set derivation
    this AC requires. `check_contract_shrinking.py` and
    `check_doc_frontmatter.py` (via `frontmatter_validators.py`) each
    ALREADY carry their own, independently duplicated implementation of the
    same "diff differs from both merge parents" idiom (landed under
    GE-120e-1-i / GE-111f / GE-120e-3-ii, at `_merge_scoped_paths()` and
    `merge_scoped_md_paths()` respectively — read at test-authoring time and
    confirmed byte-for-byte the same algorithm, hand-copied twice). This AC's
    own last Gherkin clause is exactly the gap that duplication leaves open:
    "every check that works out its own change set takes it from one shared
    source rather than computing a private one." The empirical read at
    authoring time also found BOTH checks currently fall back to the
    UNSCOPED (whole-staged-tree) diff whenever the derivation cannot be
    determined ("None ... the caller then uses the unscoped diff — the
    stricter behaviour", verbatim from both docstrings) — the exact
    could-not-check-vs-widen anti-pattern this AC's Implementation Notes
    forbid ("A git failure must NOT degrade to using the whole staged
    tree").

BUSINESS CONTEXT: Ticket 28 of EPIC-TrustThatAGreenCheckActuallyChecked.
    source_ac: GE-120e-1. The AC's own `test_spec` supplies the six test
    names used below (five behavioral + the mandatory reachability test);
    it declares no exact API for the shared source. architect-review's own
    2026-08-31 sign-off comment on this ticket originally proposed "a
    `_resolve_change_set.py`-style module" exposing "one small dataclass ...
    carrying the base/head refs plus lazily-derivable `.text_diff()` and
    `.name_status()` accessors" — but a same-day pr-reviewer finding (H-1)
    found that ``unit_tests/portability/test_ge_120e_4_i.py`` (ticket 36,
    GE-120e-4-i) had ALREADY established a different, more specific contract
    for this exact module (`_authored_change.py` / `get_authored_change()` /
    `AuthoredChange`, with `states` provenance and `diff_text`/`name_status`
    as plain data attributes rather than lazy methods, and in-band
    `could_not_check`/`error` instead of a `None` sentinel), and asked
    GE-120e-1's implementer to honour it. This file was updated in that
    remediation pass to match — see Source-of-Truth Discipline Rule 1
    ("test drift": the assumed shape below was the stale one; the fix is
    updating this file's assertions, not production).

CONTRACT ASSUMED (documented here so a reader does not have to reverse it
    out of assertions — reconciled with ticket 36's pre-established
    contract, see BUSINESS CONTEXT above):
    - Module: templates/scripts/commit_guardian/_authored_change.py
    - `get_authored_change(cwd: Path | None = None) -> AuthoredChange`
      Never returns None. Reports a could-not-check outcome IN BAND via
      `.could_not_check = True` (with `.error` describing what failed) —
      NEVER a widened/unscoped fallback.
    - `AuthoredChange` dataclass/object with (all plain data attributes,
      not methods):
        - `.paths: list[str]` — the authored (self-relative-to-both-states)
          path set.
        - `.states: list[str]` — the commit-ish(es) the derivation was
          computed against (`["HEAD"]`, or `["HEAD", "MERGE_HEAD"]` during
          a merge).
        - `.diff_text: str` — full text diff, scoped to `.paths` during
          a merge; the ordinary (single-state) `git diff --cached` output
          byte-for-byte when there is only one state to compare against.
        - `.name_status: list[tuple[str, str]]` — `(path, status)` pairs,
          same scoping rule.
        - `.could_not_check: bool` / `.error: str | None` — in-band
          could-not-check reporting.

WHY THESE FIXTURES ARE REAL GIT, NOT MOCKS: every assertion below is on the
    combined stdout+stderr of a REAL subprocess invocation of the checks (or
    of `get_authored_change()` against a REAL repository state), per this AC's
    own "Coverage note" ("cover this by executing the check as a process
    against a real repository ... reading the check's source does not cover
    this criterion") and this repo's Real-Artifact Behavioral Test Mandate.
    Fixtures use `git worktree add` off THIS repository (never a synthetic
    minimal repo) because `check_doc_frontmatter.py` needs the real
    `docs/components.json` / `docs/FRONTMATTER.md` rules this repo ships —
    same reasoning as the sibling `test_ge_120e_1_i.py` file.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-31 [EPIC-TrustThatAGreenCheckActuallyChecked/28, GE-120e-1,
  pr-reviewer remediation]: Reconciled this file's assumed contract with
  ticket 36's (`unit_tests/portability/test_ge_120e_4_i.py`) pre-established
  one — renamed the module/function/class under test from
  `_resolve_change_set.py`/`get_change_set()`/`ChangeSet` to
  `_authored_change.py`/`get_authored_change()`/`AuthoredChange`, switched
  `.text_diff()`/`.name_status()` method calls to `.diff_text`/`.name_status`
  attribute reads, `base_ref`/`head_ref` to `.states`, and the `None`
  could-not-check sentinel to `.could_not_check`/`.error`. No test's
  observable-behaviour assertions (process exit codes, stdout/stderr
  content) changed — only the direct-import assertions that reached into
  the shared module's own shape. (#EPIC-TrustThatAGreenCheckActuallyChecked/28)
- 2026-08-31 [EPIC-TrustThatAGreenCheckActuallyChecked/28, GE-120e-1,
  test-writer]: Initial TDD red-baseline. `_resolve_change_set.py` does not
  exist yet, so every test that imports it fails via ModuleNotFoundError —
  the genuine red state for this ticket's actual deliverable. Tests A/B/F
  (carried-in absence, author-verdict stability, reachability) build real
  merge/ordinary fixtures via `git worktree add`; test E additionally
  injects a real fake-`git` shim on PATH to force the SECOND git call in the
  existing merge-scoping idiom to fail, reproducing the documented
  fall-back-to-unscoped-diff anti-pattern both checks currently ship.
====================================================================
"""
# @ac-tag: GE-120e-1

from __future__ import annotations

import logging
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root
_COMMIT_GUARDIAN_TEMPLATES = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_CONTRACT_SHRINKING = _COMMIT_GUARDIAN_TEMPLATES / "check_contract_shrinking.py"
_CHECK_DOC_FRONTMATTER = _COMMIT_GUARDIAN_TEMPLATES / "check_doc_frontmatter.py"

_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from build_phases import build_commit_guardian  # type: ignore[import]
    _BUILD_PHASES_OK = True
except (ImportError, ModuleNotFoundError):
    build_commit_guardian = None  # type: ignore[assignment]
    _BUILD_PHASES_OK = False

if str(_COMMIT_GUARDIAN_TEMPLATES) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_TEMPLATES))

# ---------------------------------------------------------------------------
# THE SHARED MODULE THIS AC MUST DELIVER. See module docstring "CONTRACT
# ASSUMED". Not expected to exist yet — this import is the primary red
# signal for this ticket.
# ---------------------------------------------------------------------------
try:
    from _authored_change import get_authored_change  # type: ignore[import]
    _SHARED_MODULE_OK = True
except ImportError:
    get_authored_change = None  # type: ignore[assignment]
    _SHARED_MODULE_OK = False

_SHARED_MODULE_MISSING_MSG = (
    "templates/scripts/commit_guardian/_authored_change.py could not be "
    "imported (even with that directory on sys.path). GE-120e-1 requires "
    "exactly one shared module exposing get_authored_change() (and an "
    "AuthoredChange result carrying .paths / .states / .diff_text / "
    ".name_status / .could_not_check / .error) that BOTH "
    "check_contract_shrinking.py and check_doc_frontmatter.py consume in "
    "place of their current private, independently-duplicated "
    "_merge_scoped_paths() / merge_scoped_md_paths() implementations. See "
    "this test file's module docstring 'CONTRACT ASSUMED' for the exact "
    "shape assumed."
)

_GIT_ENV_OVERRIDES = {
    "PRE_COMMIT_ALLOW_NO_CONFIG": "1",
}

try:
    import shutil
    _REAL_GIT = shutil.which("git")
except OSError:
    _REAL_GIT = None


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------
def _run(cmd: list[str], cwd: Path, timeout: int = 30, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **_GIT_ENV_OVERRIDES}
    if extra_env:
        env.update(extra_env)
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Command %s failed to run in %s: %s", cmd, cwd, exc)
        raise


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = _run(["git", *args], cwd=cwd)
    if result.returncode != 0:
        logger.warning(
            "git %s failed (rc=%s) in %s: %s", args, result.returncode, cwd,
            result.stderr,
        )
    return result


# ---------------------------------------------------------------------------
# Fixture: a merge with NO author content overlapping the carried-in work.
# Same shape as test_ge_120e_1_i.py's fixture (kept independent — this file
# must stand alone and must not depend on another test module's internals).
# ---------------------------------------------------------------------------
class _NoAuthorMergeFixture:
    """A merge whose author (the checked-out branch) wrote nothing that
    overlaps with mainline's carried-in content: a bad-frontmatter doc, a
    staged test-file deletion, and a production-file edit."""

    def __init__(self) -> None:
        suffix = uuid.uuid4().hex[:10]
        self.root = Path(tempfile.gettempdir()) / f"ge120e1-noauthor-{suffix}"
        self._ours_branch = f"ge120e1-ours-{suffix}"
        self._theirs_branch = f"ge120e1-theirs-{suffix}"
        self.baddoc_rel = "docs/_ge120e1_probe_baddoc.md"
        self.deleted_test_rel = "unit_tests/_ge120e1_probe_test.py"
        self.prod_file_rel = "_ge120e1_probe_prod.py"
        self.scratch_rel = "_ge120e1_probe_scratch.txt"

    def build(self) -> None:
        _run_git(["worktree", "add", "--detach", str(self.root), "HEAD"], cwd=_REPO_ROOT)
        if not (self.root / ".git").exists():
            raise RuntimeError(f"Fixture setup failed: `git worktree add` did not create {self.root}")
        _run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=self.root)
        _run_git(["config", "user.name", "GE-120e-1 fixture"], cwd=self.root)

        (self.root / self.deleted_test_rel).write_text("def test_probe():\n    assert True\n", encoding="utf-8")
        (self.root / self.prod_file_rel).write_text("def probe_fn():\n    return 1\n", encoding="utf-8")
        _run_git(["add", self.deleted_test_rel, self.prod_file_rel], cwd=self.root)
        _run_git(["commit", "-q", "-m", "base: scratch fixture files"], cwd=self.root)
        base_sha = _run_git(["rev-parse", "HEAD"], cwd=self.root).stdout.strip()

        _run_git(["checkout", "-q", "-b", self._ours_branch], cwd=self.root)
        (self.root / self.scratch_rel).write_text("authored scratch\n", encoding="utf-8")
        _run_git(["add", self.scratch_rel], cwd=self.root)
        _run_git(["commit", "-q", "-m", "author: unrelated scratch change"], cwd=self.root)

        _run_git(["checkout", "-q", "-b", self._theirs_branch, base_sha], cwd=self.root)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / self.baddoc_rel).write_text("---\nfoo: bar\n---\n# Bad doc\n", encoding="utf-8")
        _run_git(["rm", "-q", self.deleted_test_rel], cwd=self.root)
        (self.root / self.prod_file_rel).write_text("def probe_fn():\n    return 2\n", encoding="utf-8")
        _run_git(["add", self.baddoc_rel, self.prod_file_rel], cwd=self.root)
        _run_git(["commit", "-q", "-m", "mainline: carried-in content"], cwd=self.root)

        _run_git(["checkout", "-q", "-f", self._ours_branch], cwd=self.root)
        merge_result = _run_git(["merge", self._theirs_branch, "--no-commit", "--no-ff"], cwd=self.root)
        merge_head = _run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=self.root)
        if merge_head.returncode != 0:
            raise RuntimeError(
                "Fixture setup failed: MERGE_HEAD was not set after "
                f"`git merge --no-commit --no-ff` (stdout={merge_result.stdout!r} "
                f"stderr={merge_result.stderr!r})."
            )
        staged = _run_git(["diff", "--cached", "--name-only"], cwd=self.root).stdout
        for expected in (self.baddoc_rel, self.deleted_test_rel, self.prod_file_rel):
            if expected not in staged:
                raise RuntimeError(
                    f"Fixture setup failed: expected {expected!r} staged, got: {staged!r}"
                )

    def teardown(self) -> None:
        _run_git(["worktree", "remove", "--force", str(self.root)], cwd=_REPO_ROOT)
        _run_git(["branch", "-D", self._ours_branch], cwd=_REPO_ROOT)
        _run_git(["branch", "-D", self._theirs_branch], cwd=_REPO_ROOT)


# ---------------------------------------------------------------------------
# Fixture: a merge where the AUTHOR's own branch ALSO wrote content that
# should trip a check (a second, distinct bad-frontmatter doc), alongside
# mainline's unrelated carried-in content. Used to prove the verdict on the
# author's own content is unaffected by whether it lands via an ordinary
# commit or a merge with unrelated carried-in noise.
# ---------------------------------------------------------------------------
class _AuthorAndCarriedInMergeFixture:
    def __init__(self) -> None:
        suffix = uuid.uuid4().hex[:10]
        self.root = Path(tempfile.gettempdir()) / f"ge120e1-author-{suffix}"
        self._ours_branch = f"ge120e1-author-ours-{suffix}"
        self._theirs_branch = f"ge120e1-author-theirs-{suffix}"
        self.author_baddoc_rel = "docs/_ge120e1_probe_authordoc.md"
        self.carried_baddoc_rel = "docs/_ge120e1_probe_carrieddoc.md"
        self.deleted_test_rel = "unit_tests/_ge120e1_probe_author_test.py"
        self.prod_file_rel = "_ge120e1_probe_author_prod.py"

    def build(self) -> None:
        _run_git(["worktree", "add", "--detach", str(self.root), "HEAD"], cwd=_REPO_ROOT)
        if not (self.root / ".git").exists():
            raise RuntimeError(f"Fixture setup failed: `git worktree add` did not create {self.root}")
        _run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=self.root)
        _run_git(["config", "user.name", "GE-120e-1 fixture"], cwd=self.root)

        (self.root / self.deleted_test_rel).write_text("def test_probe():\n    assert True\n", encoding="utf-8")
        (self.root / self.prod_file_rel).write_text("def probe_fn():\n    return 1\n", encoding="utf-8")
        _run_git(["add", self.deleted_test_rel, self.prod_file_rel], cwd=self.root)
        _run_git(["commit", "-q", "-m", "base: scratch fixture files"], cwd=self.root)
        base_sha = _run_git(["rev-parse", "HEAD"], cwd=self.root).stdout.strip()

        _run_git(["checkout", "-q", "-b", self._ours_branch], cwd=self.root)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / self.author_baddoc_rel).write_text(
            "---\nfoo: bar\n---\n# Author's own bad doc\n", encoding="utf-8",
        )
        _run_git(["add", self.author_baddoc_rel], cwd=self.root)
        _run_git(["commit", "-q", "-m", "author: own bad-frontmatter doc"], cwd=self.root)

        _run_git(["checkout", "-q", "-b", self._theirs_branch, base_sha], cwd=self.root)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / self.carried_baddoc_rel).write_text(
            "---\nfoo: bar\n---\n# Carried-in bad doc\n", encoding="utf-8",
        )
        _run_git(["rm", "-q", self.deleted_test_rel], cwd=self.root)
        (self.root / self.prod_file_rel).write_text("def probe_fn():\n    return 2\n", encoding="utf-8")
        _run_git(["add", self.carried_baddoc_rel, self.prod_file_rel], cwd=self.root)
        _run_git(["commit", "-q", "-m", "mainline: carried-in content"], cwd=self.root)

        _run_git(["checkout", "-q", "-f", self._ours_branch], cwd=self.root)
        merge_result = _run_git(["merge", self._theirs_branch, "--no-commit", "--no-ff"], cwd=self.root)
        merge_head = _run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=self.root)
        if merge_head.returncode != 0:
            raise RuntimeError(
                "Fixture setup failed: MERGE_HEAD was not set after "
                f"`git merge --no-commit --no-ff` (stdout={merge_result.stdout!r} "
                f"stderr={merge_result.stderr!r})."
            )

    def build_ordinary_comparison(self, target_root: Path) -> None:
        """Build a SECOND, independent working copy holding ONLY the
        author's own bad doc, committed ordinarily (no merge in progress),
        so its check output can be compared against the merged case."""
        _run_git(["worktree", "add", "--detach", str(target_root), "HEAD"], cwd=_REPO_ROOT)
        if not (target_root / ".git").exists():
            raise RuntimeError(f"Fixture setup failed: could not create {target_root}")
        _run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=target_root)
        _run_git(["config", "user.name", "GE-120e-1 fixture"], cwd=target_root)
        (target_root / "docs").mkdir(parents=True, exist_ok=True)
        (target_root / self.author_baddoc_rel).write_text(
            "---\nfoo: bar\n---\n# Author's own bad doc\n", encoding="utf-8",
        )
        _run_git(["add", self.author_baddoc_rel], cwd=target_root)
        # Stage only — do NOT commit, so `git diff --cached` sees it exactly
        # like the pre-commit hook would on an ordinary (non-merge) commit.

    def teardown(self) -> None:
        _run_git(["worktree", "remove", "--force", str(self.root)], cwd=_REPO_ROOT)
        _run_git(["branch", "-D", self._ours_branch], cwd=_REPO_ROOT)
        _run_git(["branch", "-D", self._theirs_branch], cwd=_REPO_ROOT)


# ---------------------------------------------------------------------------
# Fake-git shim for the failure-injection test. Forwards every git
# invocation to the REAL git binary except one specific pattern
# ("diff --cached ... --name-only ... MERGE_HEAD"), which it fails
# deliberately — reproducing "the second git call in the merge-scoping
# idiom fails" without touching any repository state.
# ---------------------------------------------------------------------------
def _write_fake_git_shim(bin_dir: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim_path = bin_dir / "git"
    real_git = _REAL_GIT or "/usr/bin/git"
    script = f"""#!/bin/sh
case "$*" in
  *"--name-only"*"MERGE_HEAD"*)
    echo "fake-git: simulated failure resolving the merge-parent side of the diff" >&2
    exit 1
    ;;
esac
exec "{real_git}" "$@"
"""
    shim_path.write_text(script, encoding="utf-8")
    shim_path.chmod(shim_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim_path


# ---------------------------------------------------------------------------
# Test A — angle: criterion
# ---------------------------------------------------------------------------
class TestCarriedInWorkAbsentFromInspectedChangeSet(unittest.TestCase):
    """AC-2/AC-4: the change set inspected holds only content differing from
    every state the commit is built on; carried-in mainline work is absent
    from it, and the check's verdict raises no objection to it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _NoAuthorMergeFixture()
        cls.fixture.build()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()

    def test_ge120e1_carried_in_work_absent_from_inspected_change_set(self) -> None:
        # covers: GE-120e-1
        # angle: criterion
        """RED today via the shared-module import: even though both checks
        already pass this exact fixture individually (GE-120e-1-i landed
        per-check merge-scoping), GE-120e-1's own deliverable is that BOTH
        derive that scoped set from ONE shared module. This test asserts
        both the process-level behavior (subprocess exit + output) AND that
        the shared derivation itself, run against this same fixture,
        produces a path set excluding every carried-in path.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        contract_shrinking = _run(["python3", str(_CHECK_CONTRACT_SHRINKING)], cwd=self.fixture.root)
        self.assertEqual(
            0, contract_shrinking.returncode,
            f"check_contract_shrinking.py must exit clean. stdout={contract_shrinking.stdout!r} "
            f"stderr={contract_shrinking.stderr!r}",
        )
        doc_frontmatter = _run(["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.fixture.root)
        self.assertEqual(
            0, doc_frontmatter.returncode,
            f"check_doc_frontmatter.py must exit clean. stdout={doc_frontmatter.stdout!r} "
            f"stderr={doc_frontmatter.stderr!r}",
        )
        combined = (
            contract_shrinking.stdout + contract_shrinking.stderr
            + doc_frontmatter.stdout + doc_frontmatter.stderr
        )
        for carried in (self.fixture.baddoc_rel, self.fixture.deleted_test_rel):
            self.assertNotIn(
                carried, combined,
                f"Carried-in path {carried!r} must never appear in either check's "
                f"output. Combined output: {combined!r}",
            )

        authored = get_authored_change(cwd=self.fixture.root)
        self.assertFalse(
            authored.could_not_check,
            "get_authored_change() reported could_not_check on a fixture "
            f"with a valid, resolvable merge — the derivation itself failed "
            f"(error={authored.error!r}).",
        )
        self.assertNotIn(
            self.fixture.baddoc_rel, authored.paths,
            f"The shared derivation's own .paths must exclude the carried-in "
            f"doc. Got: {authored.paths!r}",
        )
        self.assertNotIn(
            self.fixture.deleted_test_rel, authored.paths,
            f"The shared derivation's own .paths must exclude the carried-in "
            f"deletion. Got: {authored.paths!r}",
        )


# ---------------------------------------------------------------------------
# Test B — angle: criterion
# ---------------------------------------------------------------------------
class TestVerdictOnAuthorsOwnContentIsUnchanged(unittest.TestCase):
    """AC-4 (second clause): the check's verdict on the SAME author content
    is unchanged whether it is committed ordinarily or alongside carried-in
    mainline noise via a merge."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _AuthorAndCarriedInMergeFixture()
        cls.fixture.build()
        cls.ordinary_root = Path(tempfile.gettempdir()) / f"ge120e1-ordinary-{uuid.uuid4().hex[:10]}"
        cls.fixture.build_ordinary_comparison(cls.ordinary_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()
        _run_git(["worktree", "remove", "--force", str(cls.ordinary_root)], cwd=_REPO_ROOT)

    def test_ge120e1_verdict_on_the_authors_own_content_is_unchanged(self) -> None:
        # covers: GE-120e-1
        # angle: criterion
        """RED via the shared-module import gate. Once implemented: the same
        author-authored bad-frontmatter doc must produce the SAME
        pass/fail status and name the SAME file whether committed alone
        (ordinary commit) or alongside a merge's unrelated carried-in
        content.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        ordinary_result = _run(["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.ordinary_root)
        merged_result = _run(["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.fixture.root)

        self.assertEqual(
            ordinary_result.returncode, merged_result.returncode,
            "check_doc_frontmatter.py's exit code for the author's own bad "
            f"doc must be identical whether ordinary ({ordinary_result.returncode}) "
            f"or merged alongside carried-in noise ({merged_result.returncode}). "
            f"ordinary stdout={ordinary_result.stdout!r} "
            f"merged stdout={merged_result.stdout!r}",
        )
        self.assertNotEqual(
            0, ordinary_result.returncode,
            "Sanity check on the fixture itself: the author's own "
            f"bad-frontmatter doc must be flagged when committed alone. "
            f"stdout={ordinary_result.stdout!r}",
        )
        ordinary_combined = ordinary_result.stdout + ordinary_result.stderr
        merged_combined = merged_result.stdout + merged_result.stderr
        self.assertIn(
            self.fixture.author_baddoc_rel, ordinary_combined,
            f"Ordinary-commit output must name the author's own bad doc. Got: {ordinary_combined!r}",
        )
        self.assertIn(
            self.fixture.author_baddoc_rel, merged_combined,
            f"Merged-commit output must ALSO name the author's own bad doc — "
            f"the verdict on the author's own content must be unchanged by "
            f"the presence of unrelated carried-in content. Got: {merged_combined!r}",
        )
        self.assertNotIn(
            self.fixture.carried_baddoc_rel, merged_combined,
            f"Merged-commit output must NOT name the carried-in doc — only "
            f"the author's own content is in scope. Got: {merged_combined!r}",
        )


# ---------------------------------------------------------------------------
# Test C — angle: boundary
# ---------------------------------------------------------------------------
class TestOrdinaryCommitChangeSetEqualsFullStagedDiff(unittest.TestCase):
    """AC (Implementation Notes) "NO BEHAVIOUR CHANGE ON THE ORDINARY
    COMMIT": with exactly one state to compare against (no merge in
    progress — the one/many boundary this AC narrows around), the derived
    change set must equal today's `git diff --cached` output byte for byte —
    the narrowing must cost nothing on the common path."""

    @classmethod
    def setUpClass(cls) -> None:
        suffix = uuid.uuid4().hex[:10]
        cls.root = Path(tempfile.gettempdir()) / f"ge120e1-ordinary-boundary-{suffix}"
        _run_git(["worktree", "add", "--detach", str(cls.root), "HEAD"], cwd=_REPO_ROOT)
        if not (cls.root / ".git").exists():
            raise RuntimeError(f"Fixture setup failed: could not create {cls.root}")
        _run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=cls.root)
        _run_git(["config", "user.name", "GE-120e-1 fixture"], cwd=cls.root)
        cls.staged_rel = "_ge120e1_probe_ordinary.py"
        (cls.root / cls.staged_rel).write_text("def probe():\n    return 42\n", encoding="utf-8")
        _run_git(["add", cls.staged_rel], cwd=cls.root)
        # Deliberately left staged, uncommitted — the exact state a
        # pre-commit hook inspects.

    @classmethod
    def tearDownClass(cls) -> None:
        _run_git(["worktree", "remove", "--force", str(cls.root)], cwd=_REPO_ROOT)

    def test_ge120e1_ordinary_commit_change_set_equals_full_staged_diff(self) -> None:
        # covers: GE-120e-1
        # angle: boundary
        """RED via the shared-module import gate."""
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        expected_diff = _run_git(["diff", "--cached"], cwd=self.root).stdout
        expected_name_status_raw = _run_git(["diff", "--cached", "--name-status"], cwd=self.root).stdout
        expected_name_status: dict[str, str] = {}
        for line in expected_name_status_raw.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                expected_name_status[parts[-1]] = parts[0]

        authored = get_authored_change(cwd=self.root)
        self.assertFalse(
            authored.could_not_check,
            "get_authored_change() reported could_not_check on an "
            f"ordinary, non-merge staged commit — this is the common path "
            f"and must never fail here (error={authored.error!r}).",
        )
        self.assertEqual(
            expected_diff, authored.diff_text,
            "On an ordinary (single-state) commit, the shared derivation's "
            "diff_text must equal `git diff --cached` byte for byte — "
            "this is the regression budget for every other manifest check.",
        )
        self.assertEqual(
            expected_name_status, dict(authored.name_status),
            "On an ordinary (single-state) commit, the shared derivation's "
            "name_status must equal `git diff --cached --name-status` "
            "parsed identically.",
        )


# ---------------------------------------------------------------------------
# Test D — angle: seam
# ---------------------------------------------------------------------------
class TestBothSelfDerivingChecksInspectTheSameAuthoredSet(unittest.TestCase):
    """AC-5: every check that works out its own change set takes it from
    ONE shared source. Proven behaviorally (not by grep): the REAL shared
    module, when it cannot compute the derivation, must degrade BOTH real
    consumers identically to a could-not-check outcome — proving they
    depend on the same single point rather than two independent private
    implementations that merely happen to agree today."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _NoAuthorMergeFixture()
        cls.fixture.build()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()

    def test_ge120e1_both_self_deriving_checks_inspect_the_same_authored_set(self) -> None:
        # covers: GE-120e-1
        # angle: seam
        """RED via the shared-module import gate. Once implemented: pipe the
        REAL shared module's output into BOTH REAL consumers on the SAME
        fixture, then poison the ONE shared module file itself (replace its
        contents with something that unconditionally raises) and assert
        BOTH consumers — not just one — degrade to a could-not-check
        outcome. If only one consumer is affected, they are not actually
        sharing one source.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        shared_module_path = _COMMIT_GUARDIAN_TEMPLATES / "_authored_change.py"
        original_source = shared_module_path.read_text(encoding="utf-8")
        poisoned_source = (
            "def get_authored_change(cwd=None):\n"
            "    raise RuntimeError('GE-120e-1 test-injected failure')\n"
        )
        try:
            shared_module_path.write_text(poisoned_source, encoding="utf-8")

            contract_shrinking = _run(["python3", str(_CHECK_CONTRACT_SHRINKING)], cwd=self.fixture.root)
            doc_frontmatter = _run(["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.fixture.root)

            cs_combined = contract_shrinking.stdout + contract_shrinking.stderr
            df_combined = doc_frontmatter.stdout + doc_frontmatter.stderr

            self.assertNotIn(
                self.fixture.baddoc_rel, cs_combined,
                "With the shared source poisoned, check_contract_shrinking.py "
                "must not fall back to widening its scan to the carried-in "
                f"content. Output: {cs_combined!r}",
            )
            self.assertNotIn(
                self.fixture.baddoc_rel, df_combined,
                "With the shared source poisoned, check_doc_frontmatter.py "
                "must not fall back to widening its scan to the carried-in "
                f"content either — proving it depends on the SAME shared "
                f"source as check_contract_shrinking.py. Output: {df_combined!r}",
            )
            self.assertTrue(
                "could_not_check" in cs_combined.lower() or "could not" in cs_combined.lower(),
                "check_contract_shrinking.py must report a could-not-check "
                f"outcome when the shared derivation raises. Output: {cs_combined!r}",
            )
            self.assertTrue(
                "could_not_check" in df_combined.lower() or "could not" in df_combined.lower(),
                "check_doc_frontmatter.py must ALSO report a could-not-check "
                f"outcome from the SAME poisoned shared source. Output: {df_combined!r}",
            )
        finally:
            shared_module_path.write_text(original_source, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test E — angle: failure
# ---------------------------------------------------------------------------
class TestGitFailureDoesNotWidenToTheWholeStagedTree(unittest.TestCase):
    """Implementation Notes: "A git failure must NOT degrade to using the
    whole staged tree ... A derivation that cannot be computed is a
    could-not-check outcome, not a wider change set." Proven with a REAL
    fake-git shim on PATH that fails the specific git call the merge-scoping
    derivation needs — not a mocked-out git module."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _NoAuthorMergeFixture()
        cls.fixture.build()
        cls.shim_dir = Path(tempfile.gettempdir()) / f"ge120e1-fakegit-{uuid.uuid4().hex[:10]}"
        _write_fake_git_shim(cls.shim_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()

    def test_ge120e1_git_failure_does_not_widen_to_the_whole_staged_tree(self) -> None:
        # covers: GE-120e-1
        # angle: failure
        """RED both via the shared-module import gate AND (independently)
        against the CURRENT per-check implementations, which are documented
        (verbatim in their own docstrings, read at authoring time) to fall
        back to the unscoped diff when the merge-parent-side git call
        fails — precisely the anti-pattern this test forbids.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        poisoned_path = f"{self.shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"

        contract_shrinking = _run(
            ["python3", str(_CHECK_CONTRACT_SHRINKING)],
            cwd=self.fixture.root,
            extra_env={"PATH": poisoned_path},
        )
        doc_frontmatter = _run(
            ["python3", str(_CHECK_DOC_FRONTMATTER)],
            cwd=self.fixture.root,
            extra_env={"PATH": poisoned_path},
        )

        cs_combined = contract_shrinking.stdout + contract_shrinking.stderr
        df_combined = doc_frontmatter.stdout + doc_frontmatter.stderr

        self.assertNotIn(
            self.fixture.baddoc_rel, cs_combined,
            "When the git call needed to resolve the merge-parent side "
            "fails, check_contract_shrinking.py must NOT widen to the "
            f"unscoped staged diff. Output: {cs_combined!r}",
        )
        self.assertNotIn(
            self.fixture.baddoc_rel, df_combined,
            "When the git call needed to resolve the merge-parent side "
            "fails, check_doc_frontmatter.py must NOT widen to the unscoped "
            f"staged diff either. Output: {df_combined!r}",
        )
        self.assertTrue(
            "could_not_check" in cs_combined.lower() or "could not" in cs_combined.lower(),
            f"check_contract_shrinking.py must report a could-not-check "
            f"outcome on git failure, not a silent pass or a widened scan. "
            f"Output: {cs_combined!r}",
        )
        self.assertTrue(
            "could_not_check" in df_combined.lower() or "could not" in df_combined.lower(),
            f"check_doc_frontmatter.py must report a could-not-check outcome "
            f"on git failure, not a silent pass or a widened scan. "
            f"Output: {df_combined!r}",
        )


# ---------------------------------------------------------------------------
# Test F — angle: reachability (REQUIRED by test_spec)
# ---------------------------------------------------------------------------
class TestReachableFromDeployedEntryPoint(unittest.TestCase):
    """REQUIRED reachability angle: invoke the DEPLOYED copy of the checks
    (per ADR-001 template/deployed parity) as real subprocesses, and assert
    the shared-derivation behaviour is reachable there too — not only from
    templates/scripts/commit_guardian/ source."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _NoAuthorMergeFixture()
        cls.fixture.build()
        cls.deployed_ok = False
        if _BUILD_PHASES_OK:
            written = build_commit_guardian(
                cls.fixture.root,
                {
                    "output_root": ".leafcutter",
                    "agents_dir": ".claude/agents",
                    "skills_dir": ".claude/skills",
                },
                dry_run=False,
                force=True,
            )
            cls.deployed_ok = written > 0 and (
                cls.fixture.root / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
            ).exists() and (
                cls.fixture.root / "scripts" / "commit_guardian" / "_authored_change.py"
            ).exists()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()

    def test_ge_120e_1_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-1
        # angle: reachability
        """Runs the DEPLOYED (`scripts/commit_guardian/`, not
        `templates/scripts/commit_guardian/`) copy of check_doc_frontmatter.py
        as a real subprocess against the same no-author merge fixture, and
        asserts it exits clean without naming the carried-in doc. Importing
        the check's functions directly would not exercise this at all, and
        would not catch a fix that lands only in templates/ without a
        build.py run.
        """
        if not _BUILD_PHASES_OK:
            self.fail(
                "scripts.build_phases.build_commit_guardian could not be "
                "imported — cannot deploy the commit_guardian scripts into "
                "the fixture worktree to test the deployed entry point."
            )
        if not self.deployed_ok:
            self.fail(
                "build_commit_guardian() did not produce a deployed "
                f"{self.fixture.root}/scripts/commit_guardian/ layout "
                "including _authored_change.py — cannot exercise the "
                "deployed entry point for this AC's shared module."
            )

        deployed_check = (
            self.fixture.root / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
        )
        result = _run(["python3", str(deployed_check)], cwd=self.fixture.root)
        self.assertEqual(
            0, result.returncode,
            "The DEPLOYED check_doc_frontmatter.py must exit clean on a "
            f"merge with no authored content. stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            self.fixture.baddoc_rel, combined,
            f"The deployed check must not name the carried-in doc. Output: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
