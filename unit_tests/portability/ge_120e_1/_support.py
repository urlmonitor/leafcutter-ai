"""
MODULE: unit_tests/portability/ge_120e_1/_support.py
AC: GE-120e-1 — "A check that works out its own change set works out the
    author's change, not everything the staged tree happens to hold"
GOAL: Shared fixtures, process helpers and path constants for the GE-120e-1
    suite in this package. The tests themselves live in
    ``test_ge_120e_1_criterion.py`` (tests A, B),
    ``test_ge_120e_1_boundary_and_seam.py`` (tests C, D) and
    ``test_ge_120e_1_failure_and_reachability.py`` (tests E, F).

    The suite is the TDD red-baseline for the shared authored-change-set
    derivation this AC requires. `check_contract_shrinking.py` and
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
    names used by this suite (five behavioral + the mandatory reachability
    test); it declares no exact API for the shared source. architect-review's
    own 2026-08-31 sign-off comment on this ticket originally proposed "a
    `_resolve_change_set.py`-style module" exposing "one small dataclass ...
    carrying the base/head refs plus lazily-derivable `.text_diff()` and
    `.name_status()` accessors" — but a same-day pr-reviewer finding (H-1)
    found that ``unit_tests/portability/test_ge_120e_4_i.py`` (ticket 36,
    GE-120e-4-i) had ALREADY established a different, more specific contract
    for this exact module (`_authored_change.py` / `get_authored_change()` /
    `AuthoredChange`, with `states` provenance and `diff_text`/`name_status`
    as plain data attributes rather than lazy methods, and in-band
    `could_not_check`/`error` instead of a `None` sentinel), and asked
    GE-120e-1's implementer to honour it. This suite was updated in that
    remediation pass to match — see Source-of-Truth Discipline Rule 1
    ("test drift": the assumed shape below was the stale one; the fix is
    updating this suite's assertions, not production).

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

WHY THESE FIXTURES ARE REAL GIT, NOT MOCKS: every assertion in this suite is
    on the combined stdout+stderr of a REAL subprocess invocation of the
    checks (or of `get_authored_change()` against a REAL repository state),
    per this AC's own "Coverage note" ("cover this by executing the check as
    a process against a real repository ... reading the check's source does
    not cover this criterion") and this repo's Real-Artifact Behavioral Test
    Mandate. Fixtures use the linked-checkout add off THIS repository (never
    a synthetic minimal repo) because `check_doc_frontmatter.py` needs the
    real `docs/components.json` / `docs/FRONTMATTER.md` rules this repo
    ships — same reasoning as the sibling
    `unit_tests/portability/test_ge_120e_1_i.py` file.

====================================================================
DECISION HISTORY
====================================================================
- 2026-11-16 [split-oversized-tests]: Split from the single
  unit_tests/portability/test_ge_120e_1.py, which stood over the 400-line
  file-size limit and so could not take the class-level attribute
  declarations mypy needed. This module keeps the fixtures, helpers and
  constants; the six tests moved unchanged into three test modules by angle.
  The setUpClass/tearDownClass that four test classes repeated for the
  no-author merge fixture is now NoAuthorMergeTestCase below, which declares
  its fixture attribute for the type checker. The guarded imports lost their
  `# type: ignore` comments: neither `build_phases` nor `_authored_change`
  is resolvable by mypy as a top-level module, so their None fallbacks are
  not type errors.
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
  merge/ordinary fixtures via the linked-checkout add; test E additionally
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
from typing import ClassVar

from unit_tests.build_orchestration._workspace_maker_fixtures import (
    commit_base_files, new_checkout, start_merge, unlink_checkout,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent.parent  # unit_tests/portability/ge_120e_1/ -> worktree root
_COMMIT_GUARDIAN_TEMPLATES = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_CONTRACT_SHRINKING = _COMMIT_GUARDIAN_TEMPLATES / "check_contract_shrinking.py"
_CHECK_DOC_FRONTMATTER = _COMMIT_GUARDIAN_TEMPLATES / "check_doc_frontmatter.py"

_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from build_phases import build_commit_guardian
    _BUILD_PHASES_OK = True
except (ImportError, ModuleNotFoundError):
    build_commit_guardian = None
    _BUILD_PHASES_OK = False

if str(_COMMIT_GUARDIAN_TEMPLATES) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_TEMPLATES))

# ---------------------------------------------------------------------------
# THE SHARED MODULE THIS AC MUST DELIVER. See module docstring "CONTRACT
# ASSUMED". Not expected to exist yet — this import is the primary red
# signal for this ticket.
# ---------------------------------------------------------------------------
try:
    from _authored_change import get_authored_change
    _SHARED_MODULE_OK = True
except ImportError:
    get_authored_change = None
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
    # KI-TQ-012. This fixture builds its scenarios as worktrees OF THE REAL
    # REPOSITORY (the linked-checkout add with cwd=_REPO_ROOT). Worktrees share
    # $GIT_COMMON_DIR/config, so a plain `git config user.email ...` inside one
    # writes to the configuration of the ENTIRE repository family and outlives
    # the fixture — teardown removes the worktree but never unsets the keys.
    # That leaked a fixture identity onto ten real commits in one session,
    # several of them on open pull requests, across worktrees this test has
    # never heard of.
    #
    # Supplying the identity through the environment instead cannot leak: it
    # lives and dies with the subprocess, and no configuration file is written.
    #
    # `git config --worktree` would also scope correctly, but only where
    # extensions.worktreeConfig is enabled — that lives in untracked
    # .git/config, so a fresh CI clone does not have it and the call would
    # fail. The environment works everywhere.
    "GIT_AUTHOR_NAME": "GE-120e-1 fixture",
    "GIT_AUTHOR_EMAIL": "ge120e1-fixture@example.com",
    "GIT_COMMITTER_NAME": "GE-120e-1 fixture",
    "GIT_COMMITTER_EMAIL": "ge120e1-fixture@example.com",
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
# Same shape as test_ge_120e_1_i.py's fixture (kept independent — this suite
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
        new_checkout(_REPO_ROOT, self.root)
        base_sha = commit_base_files(self.root, self.deleted_test_rel, self.prod_file_rel, _run_git)

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

        start_merge(self.root, self._ours_branch, self._theirs_branch, _run_git)
        staged = _run_git(["diff", "--cached", "--name-only"], cwd=self.root).stdout
        for expected in (self.baddoc_rel, self.deleted_test_rel, self.prod_file_rel):
            if expected not in staged:
                message = f"Fixture setup failed: expected {expected!r} staged, got: {staged!r}"
                raise RuntimeError(message)

    def teardown(self) -> None:
        unlink_checkout(_REPO_ROOT, ["--force", str(self.root)], check=False)
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
        new_checkout(_REPO_ROOT, self.root)
        base_sha = commit_base_files(self.root, self.deleted_test_rel, self.prod_file_rel, _run_git)

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

        start_merge(self.root, self._ours_branch, self._theirs_branch, _run_git)

    def build_ordinary_comparison(self, target_root: Path) -> None:
        """Build a SECOND, independent working copy holding ONLY the
        author's own bad doc, committed ordinarily (no merge in progress),
        so its check output can be compared against the merged case."""
        new_checkout(_REPO_ROOT, target_root)
        (target_root / "docs").mkdir(parents=True, exist_ok=True)
        (target_root / self.author_baddoc_rel).write_text(
            "---\nfoo: bar\n---\n# Author's own bad doc\n", encoding="utf-8",
        )
        _run_git(["add", self.author_baddoc_rel], cwd=target_root)
        # Stage only — do NOT commit, so `git diff --cached` sees it exactly
        # like the pre-commit hook would on an ordinary (non-merge) commit.

    def teardown(self) -> None:
        unlink_checkout(_REPO_ROOT, ["--force", str(self.root)], check=False)
        _run_git(["branch", "-D", self._ours_branch], cwd=_REPO_ROOT)
        _run_git(["branch", "-D", self._theirs_branch], cwd=_REPO_ROOT)


# ---------------------------------------------------------------------------
# Shared class setup: tests A, D, E and F each build their own no-author
# merge fixture once per class and remove it afterwards. E and F extend
# setUpClass after calling this one.
# ---------------------------------------------------------------------------
class NoAuthorMergeTestCase(unittest.TestCase):
    """Builds a fresh _NoAuthorMergeFixture per test class and tears it down."""

    fixture: ClassVar[_NoAuthorMergeFixture]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _NoAuthorMergeFixture()
        cls.fixture.build()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()


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
