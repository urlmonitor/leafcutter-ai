"""
MODULE: test_ge_120e_3_ii
AC: GE-120e-3-ii — "A merge whose own resolution introduces the fault is
    still blocked, and no check treats a merge as grounds to skip."
GOAL: TDD red-baseline tests proving two real commit_guardian checks
    (check_contract_shrinking.py, check_doc_frontmatter.py) still object to a
    fault the AUTHOR introduces while resolving a merge conflict — never to
    content that merely arrives alongside that merge unchanged — and that
    neither check treats "a merge is under way" as a reason to stop looking.

BUSINESS CONTEXT: check_contract_shrinking.py was already hardened
    (`_merge_scoped_paths`) against the false-positive shape where an
    unscoped `git diff --cached` blames the merge author for every test the
    INCOMING branch ever deleted or skipped. check_doc_frontmatter.py has
    received no equivalent treatment — it validates every staged `.md` file
    unconditionally, with no awareness of MERGE_HEAD at all. This file proves
    both checks against real, out-of-process git operations: one arm shows
    the already-hardened check still blocking correctly; the other shows the
    unhardened check's real gap.

ARCHITECTURE / DEVIATION FROM THE TICKET'S OWN INSTRUCTION — RECORDED
    EXPLICITLY per Source-of-Truth Discipline: the ticket's Implementation
    Notes say "REUSE GE-120c-1'S OUT-OF-PROCESS HARNESS and the deployed
    layout." GE-120c-1 (unit_tests/portability/_deployed_check_harness.py /
    unit_tests/portability/harness.py) does not exist anywhere in this tree
    as of this ticket (confirmed: both GE-120c-1 and GE-120e-3 are
    `work_status: todo` in the AC store; see tickets 12 and 32). Unlike
    GE-120e-3-i (which blocked entirely for this reason — see that ticket's
    Comments), THIS ticket's subject is two checks that already exist as
    real, deployed production scripts
    (templates/scripts/commit_guardian/check_contract_shrinking.py,
    templates/scripts/commit_guardian/check_doc_frontmatter.py), so no new
    architecture needs to be invented or guessed at. This file therefore
    builds its own small, self-contained out-of-process harness (real
    `git init`/`git merge` in a throwaway temp repo, real `subprocess.run`
    invocations of the canonical check scripts) rather than importing a
    module that does not exist. This mirrors the pattern
    unit_tests/portability/test_ge120c1i_setup_failure_reporting.py already
    uses to stand up real git state for ITS OWN AC. Both checks are invoked
    as separate OS processes with real MERGE_HEAD state — never by importing
    a function and calling it directly, and never by hand-writing a
    synthetic diff string (HOOK_TEST_DIFF), because HOOK_TEST_DIFF bypasses
    the MERGE_HEAD probe entirely (see check_contract_shrinking.py's
    _get_weakening_diff — it short-circuits to the raw diff whenever
    HOOK_TEST_DIFF is set), which would make it structurally impossible to
    exercise the merge-scoping this AC is about.

FIXTURE DESIGN — "SAME REPOSITORY" READING: the AC's own coverage note
    requires the blocked arm and the not-blocked arm to run "against the
    same repository." Two fixtures are built here
    (_build_authored_fault_repo, _build_carried_in_only_repo) from the
    IDENTICAL base-repo recipe (_init_base_repo) so that the only variable
    between them is authorship of the fault content, never the repository's
    shape, its files, or its history depth. Both fixtures are built ONCE, at
    module scope (setUpModule/tearDownModule), and read-only from every test
    method — the checks under test only run `git diff --cached` variants and
    never mutate the fixture repos, so sharing them across tests is safe and
    keeps this module's real-git-operation cost paid once (per GE-120e-3's
    own runtime guidance: "Build each repository ONCE per sweep").

ACCEPTED NARROWING — RECORDED EXPLICITLY per this AC's own it_requirements:
    under GE-120e-1's definition, resolving a conflict by taking an incoming
    deletion verbatim matches an incoming state and is therefore NOT the
    author's own content. So an author who accepts an incoming test deletion
    unchanged and separately edits production code is no longer blocked by
    the contract-shrinking rule (see
    test_ge120e3ii_identical_content_arriving_unchanged_is_not_blocked_in_the_same_case,
    the check_contract_shrinking half — this is observed as already-correct,
    intentional behaviour, not a defect). This is the observed false
    positive being removed on purpose; if it is later judged too wide, the
    fix belongs in GE-120e-1's definition of authored content, never in an
    exemption clause on either of these two checks.

WHAT IS RED TODAY vs. WHAT IS ALREADY GREEN (read before "fixing" anything):
    - check_contract_shrinking.py: ALREADY merge-scoped correctly
      (`_merge_scoped_paths`, landed in a prior ticket). Its assertions in
      this file are expected to PASS today — they are a regression guard,
      not a red baseline, for that half of the AC.
    - check_doc_frontmatter.py: has NO merge-scoping at all. It validates
      every staged `.md` file returned by `git diff --cached --name-status`
      unconditionally. Its assertions in
      test_ge120e3ii_objection_names_the_resolution_and_not_the_carried_in_work
      and
      test_ge120e3ii_identical_content_arriving_unchanged_is_not_blocked_in_the_same_case
      are the genuine RED baseline this ticket exists to close: it currently
      also names bystander content it never should, and currently blocks a
      merge that carries in identical bad frontmatter with no author
      resolution at all. python-coder should add a `_merge_scoped_paths`-
      style narrowing to check_doc_frontmatter.py, per architect-review's
      sign-off comment on this ticket, mirroring the pattern already proven
      in check_contract_shrinking.py so the two checks share one idiom.

COVERAGE NOTE COMPLIANCE ("both arms in one test against one repository"):
    test_ge120e3ii_identical_content_arriving_unchanged_is_not_blocked_in_the_same_case
    is the test that literally runs both arms (blocked + not-blocked) inside
    one method, for both checks, and is therefore the test that cannot pass
    against a check that has been switched off for merges entirely. The
    other test_ge120e3ii_* methods assert one arm each (matching this
    ticket's own test_spec names verbatim) but are not, on their own,
    sufficient evidence of the criterion — read them alongside the combined
    test, not instead of it.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/34, GE-120e-3-ii]:
  Initial TDD red-baseline. Written against the REAL, already-deployed
  check_contract_shrinking.py and check_doc_frontmatter.py — no shared
  GE-120c-1 harness exists yet (see ARCHITECTURE section above for the
  documented deviation). check_doc_frontmatter.py's two merge-scoping gaps
  are the expected red state; check_contract_shrinking.py's assertions are
  expected to already pass (regression guard, not new red).
====================================================================
"""
# @ac-tag: GE-120e-3-ii

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup — the canonical (source-tree) commit_guardian scripts under test.
# Deliberately NOT the .leafcutter/ deployed symlink: that symlink resolves
# into the MAIN tree's build output (see CLAUDE.md, "Worktrees do not inherit
# .pre-commit-config.yaml..."), not this worktree's own templates/, so it
# would test someone else's code. templates/scripts/commit_guardian/ is what
# python-coder edits for this ticket and what build.py deploys FROM.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CONTRACT_SHRINKING = _COMMIT_GUARDIAN_DIR / "check_contract_shrinking.py"
_DOC_FRONTMATTER = _COMMIT_GUARDIAN_DIR / "check_doc_frontmatter.py"

_GIT_TIMEOUT = 30
_CHECK_TIMEOUT = 30

_BASE_APP_PY = "def base():\n    return 1\n"
_TOPIC_APP_PY_SUFFIX = "\n\n\ndef topic_addition():\n    return 2\n"


# ---------------------------------------------------------------------------
# Small out-of-process harness (see module docstring, ARCHITECTURE section,
# for why this is inline rather than importing GE-120c-1's not-yet-built
# shared harness).
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git subprocess in *cwd*.

    Args:
        args: git subcommand and arguments, WITHOUT the leading "git".
        cwd: Working directory for the git invocation.
        check: Raise CalledProcessError on non-zero exit when True. Merge
            commands that are expected to conflict must pass check=False.

    Returns:
        subprocess.CompletedProcess: The completed git invocation.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=check,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        logger.warning("git %s failed in %s: %s", args, cwd, exc)
        raise


def _write(path: Path, content: str) -> None:
    """Write *content* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to write fixture file %s: %s", path, exc)
        raise


def _run_check(check_path: Path, repo_dir: Path) -> subprocess.CompletedProcess:
    """Invoke *check_path* as a real, separate OS process with cwd=repo_dir.

    This is the production entry point exactly as the commit path invokes
    it (a plain `python <script>.py` subprocess reading `git diff --cached`
    from its own cwd) — never an import-and-call of an internal function.

    Args:
        check_path: Absolute path to the check script to run.
        repo_dir: The real git working tree to run the check against.

    Returns:
        subprocess.CompletedProcess: exit code + captured stdout/stderr.
    """
    try:
        return subprocess.run(
            [sys.executable, str(check_path)],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=_CHECK_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Failed to run check %s in %s: %s", check_path, repo_dir, exc)
        raise


def _doc_md(title: str, status: str) -> str:
    """Return a docs/*.md file with valid frontmatter EXCEPT for *status*.

    `type: how-to` and `components: []` are chosen deliberately: both are
    valid against this repository's real config/doc_types.json and
    commit_guardian.json, so the ONLY thing that can trip
    check_doc_frontmatter in any fixture built from this helper is the
    status value — keeping the objection text deterministic and specific to
    the property under test.
    """
    return (
        "---\n"
        f'title: "{title}"\n'
        "type: how-to\n"
        f"status: {status}\n"
        "created: 2026-01-01\n"
        "last_updated: 2026-01-01\n"
        "components: []\n"
        "---\n"
        f"{title} body.\n"
    )


def _init_base_repo(repo_dir: Path) -> None:
    """Create a fresh, minimal real git repo with one commit on `main`.

    Contains: app.py (production), tests/test_thing.py (the file a conflict
    will be resolved on), tests/test_bystander.py (carried-in-only
    candidate), docs/foo.md (the frontmatter file a conflict will be
    resolved on) — all with valid, unremarkable content.
    """
    repo_dir.mkdir(parents=True, exist_ok=True)
    _git(["init"], repo_dir)
    _git(["symbolic-ref", "HEAD", "refs/heads/main"], repo_dir)
    _git(["config", "user.email", "ge120e3ii-test@example.com"], repo_dir)
    _git(["config", "user.name", "GE-120e-3-ii Test"], repo_dir)
    _write(repo_dir / "app.py", _BASE_APP_PY)
    _write(repo_dir / "tests" / "test_thing.py", "def test_thing():\n    assert True\n")
    _write(repo_dir / "tests" / "test_bystander.py", "def test_bystander():\n    assert True\n")
    _write(repo_dir / "docs" / "foo.md", _doc_md("Foo", "active"))
    _git(["add", "-A"], repo_dir)
    _git(["commit", "-m", "base"], repo_dir)


def _build_authored_fault_repo(tmp_root: Path) -> Path:
    """Build the BLOCKED-arm fixture: a real merge conflict on both
    tests/test_thing.py and docs/foo.md, resolved by the "author" in a way
    that matches NEITHER parent (a genuine authored resolution), plus
    bystander content (tests/test_bystander.py deletion, docs/bystander.md
    addition) that arrives from the merge untouched by that resolution.

    Returns:
        Path: the repo directory, left with MERGE_HEAD present (staged,
        uncommitted) so a check run against it sees a genuine in-progress
        merge — the only window in which MERGE_HEAD exists at all.
    """
    repo_dir = tmp_root / "authored-fault"
    _init_base_repo(repo_dir)

    _git(["checkout", "-b", "topic_authored"], repo_dir)
    _write(repo_dir / "tests" / "test_thing.py", "def test_thing():\n    assert 'topic' == 'topic'\n")
    _write(repo_dir / "docs" / "foo.md", _doc_md("Foo", "migrating"))
    _git(["add", "-A"], repo_dir)
    _git(["commit", "-m", "topic: conflicting edits"], repo_dir)

    (repo_dir / "tests" / "test_bystander.py").unlink()
    _write(repo_dir / "docs" / "bystander.md", _doc_md("Bystander", "not_a_real_status"))
    _write(repo_dir / "app.py", _BASE_APP_PY + _TOPIC_APP_PY_SUFFIX)
    _git(["add", "-A"], repo_dir)
    _git(["commit", "-m", "topic: carried-in additions (never touched by resolution)"], repo_dir)

    _git(["checkout", "main"], repo_dir)
    _write(repo_dir / "tests" / "test_thing.py", "def test_thing():\n    assert 'main' == 'main'\n")
    _write(repo_dir / "docs" / "foo.md", _doc_md("Foo", "draft"))
    _git(["add", "-A"], repo_dir)
    _git(["commit", "-m", "main: conflicting edits"], repo_dir)

    merge = _git(["merge", "topic_authored", "--no-commit", "--no-ff"], repo_dir, check=False)
    if merge.returncode == 0:
        raise AssertionError(
            "Fixture invalid: expected a real two-sided merge conflict on "
            "tests/test_thing.py and docs/foo.md, but git reported a clean "
            f"merge. This fixture, not the check under test, is broken.\n"
            f"stdout:\n{merge.stdout}\nstderr:\n{merge.stderr}"
        )
    if not (repo_dir / ".git" / "MERGE_HEAD").exists():
        raise AssertionError(
            "Fixture invalid: MERGE_HEAD absent after a conflicting merge — "
            "the fixture cannot exercise the in-progress-merge window this "
            "AC requires."
        )

    # --- The author's own resolution ---------------------------------
    # Deletes tests/test_thing.py outright: this matches NEITHER parent
    # (main kept it with different content; topic kept it with different
    # content), so it is genuinely authored per GE-120e-1's definition.
    _git(["rm", "-f", "tests/test_thing.py"], repo_dir)
    # Rewrites docs/foo.md's frontmatter with a status value matching
    # NEITHER parent ("draft" nor "migrating") and that
    # check_doc_frontmatter's own enum rejects.
    _write(repo_dir / "docs" / "foo.md", _doc_md("Foo", "bogus_status_zzz"))
    _git(["add", "docs/foo.md"], repo_dir)

    return repo_dir


def _build_carried_in_only_repo(tmp_root: Path) -> Path:
    """Build the NOT-BLOCKED-arm fixture: the SAME kind of fault (a deleted
    test file; an invalid frontmatter status) arriving via a clean,
    conflict-free merge — main never touches the affected files, so nothing
    requires the "author" (the person performing the merge) to resolve
    anything. The final content matches the incoming branch (topic_carried)
    exactly.

    Built from the identical `_init_base_repo` recipe as
    `_build_authored_fault_repo`, so the only variable between the two
    fixtures is authorship of the fault content, never the repository shape.

    Returns:
        Path: the repo directory, left with MERGE_HEAD present (staged,
        uncommitted, no conflicts to resolve).
    """
    repo_dir = tmp_root / "carried-in-only"
    _init_base_repo(repo_dir)

    _git(["checkout", "-b", "topic_carried"], repo_dir)
    (repo_dir / "tests" / "test_thing.py").unlink()
    _write(repo_dir / "docs" / "foo.md", _doc_md("Foo", "also_bogus_status"))
    _write(repo_dir / "app.py", _BASE_APP_PY + _TOPIC_APP_PY_SUFFIX)
    _git(["add", "-A"], repo_dir)
    _git(["commit", "-m", "topic: carried-in fault, no author resolution anywhere"], repo_dir)

    _git(["checkout", "main"], repo_dir)
    merge = _git(["merge", "topic_carried", "--no-commit", "--no-ff"], repo_dir, check=False)
    if merge.returncode != 0:
        raise AssertionError(
            "Fixture invalid: expected a CLEAN, conflict-free merge (main "
            "never touches tests/test_thing.py, docs/foo.md, or app.py on "
            "this branch), but git reported a conflict. This fixture, not "
            f"the check under test, is broken.\nstdout:\n{merge.stdout}\n"
            f"stderr:\n{merge.stderr}"
        )
    if not (repo_dir / ".git" / "MERGE_HEAD").exists():
        raise AssertionError(
            "Fixture invalid: MERGE_HEAD absent — this arm must still be a "
            "real merge in progress, just one with nothing to resolve."
        )
    return repo_dir


# ---------------------------------------------------------------------------
# Module-level fixtures — built ONCE, shared read-only across every test in
# this module (see module docstring, FIXTURE DESIGN).
# ---------------------------------------------------------------------------
_TMP_HOLDER: dict[str, tempfile.TemporaryDirectory] = {}
_AUTHORED_FAULT_REPO: Path | None = None
_CARRIED_IN_ONLY_REPO: Path | None = None
_SETUP_ERROR: str | None = None


def setUpModule() -> None:  # noqa: N802 - unittest module-fixture protocol
    global _AUTHORED_FAULT_REPO, _CARRIED_IN_ONLY_REPO, _SETUP_ERROR
    tmp = tempfile.TemporaryDirectory(prefix="ge120e3ii-")
    _TMP_HOLDER["tmp"] = tmp
    tmp_root = Path(tmp.name)
    try:
        _AUTHORED_FAULT_REPO = _build_authored_fault_repo(tmp_root)
        _CARRIED_IN_ONLY_REPO = _build_carried_in_only_repo(tmp_root)
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError, AssertionError) as exc:
        logger.warning("GE-120e-3-ii fixture setup failed: %s", exc)
        _SETUP_ERROR = str(exc)


def tearDownModule() -> None:  # noqa: N802 - unittest module-fixture protocol
    tmp = _TMP_HOLDER.pop("tmp", None)
    if tmp is not None:
        tmp.cleanup()


class TestGE120e3iiMergeResolutionFault(unittest.TestCase):
    """Real-repo, real-subprocess coverage of GE-120e-3-ii's two arms."""

    def setUp(self) -> None:
        if _SETUP_ERROR is not None:
            self.fail(f"Module fixture setup failed: {_SETUP_ERROR}")
        if not _CONTRACT_SHRINKING.exists():
            self.fail(f"check_contract_shrinking.py not found at {_CONTRACT_SHRINKING}")
        if not _DOC_FRONTMATTER.exists():
            self.fail(f"check_doc_frontmatter.py not found at {_DOC_FRONTMATTER}")

    def test_ge120e3ii_test_deleted_by_the_authors_resolution_still_blocks(self) -> None:
        # covers: GE-120e-3-ii
        """AC-1 (arm A(i)): a test file removed by the author's own conflict
        resolution — matching NEITHER merge parent — still trips
        check_contract_shrinking, and the commit is blocked.

        Expected to already PASS: check_contract_shrinking.py's
        _merge_scoped_paths was hardened in a prior ticket. This is a
        regression guard for that hardening, not new red for this ticket.
        """
        outcome = _run_check(_CONTRACT_SHRINKING, _AUTHORED_FAULT_REPO)
        combined = outcome.stdout + outcome.stderr
        self.assertNotEqual(
            0,
            outcome.returncode,
            "check_contract_shrinking.py must block a commit whose merge "
            f"resolution deletes tests/test_thing.py. Output:\n{combined}",
        )
        self.assertIn("test_thing.py", combined)

    def test_ge120e3ii_frontmatter_typed_during_resolution_still_blocks(self) -> None:
        # covers: GE-120e-3-ii
        """AC-1 (arm A(ii)): frontmatter the author typed while resolving a
        conflict — an invalid status value matching NEITHER parent — still
        trips check_doc_frontmatter, and the commit is blocked."""
        outcome = _run_check(_DOC_FRONTMATTER, _AUTHORED_FAULT_REPO)
        combined = outcome.stdout + outcome.stderr
        self.assertNotEqual(
            0,
            outcome.returncode,
            "check_doc_frontmatter.py must block the invalid status "
            f"frontmatter the author wrote resolving docs/foo.md. Output:\n{combined}",
        )
        self.assertIn("docs/foo.md", combined)
        self.assertIn("bogus_status_zzz", combined)

    def test_ge120e3ii_objection_names_the_resolution_and_not_the_carried_in_work(self) -> None:
        # covers: GE-120e-3-ii
        """AC-2: the objection identifies the author's own resolved content
        and mentions none of the bystander content that arrived alongside
        it purely via the merge (never touched during resolution).

        RED today for check_doc_frontmatter: it validates every staged .md
        file unconditionally (no merge-scoping — see module docstring), so
        it currently ALSO names docs/bystander.md, which arrived untouched
        from topic_authored. Fixing this requires the same
        _merge_scoped_paths-style narrowing check_contract_shrinking already
        has (per architect-review's sign-off comment on this ticket).
        check_contract_shrinking's half of this assertion is expected to
        already pass.
        """
        contract_outcome = _run_check(_CONTRACT_SHRINKING, _AUTHORED_FAULT_REPO)
        contract_combined = contract_outcome.stdout + contract_outcome.stderr
        self.assertIn("test_thing.py", contract_combined)
        self.assertNotIn(
            "test_bystander.py",
            contract_combined,
            "check_contract_shrinking named carried-in content "
            "(tests/test_bystander.py) that the author never touched.",
        )

        fm_outcome = _run_check(_DOC_FRONTMATTER, _AUTHORED_FAULT_REPO)
        fm_combined = fm_outcome.stdout + fm_outcome.stderr
        self.assertIn("docs/foo.md", fm_combined)
        self.assertNotIn(
            "docs/bystander.md",
            fm_combined,
            "check_doc_frontmatter named carried-in content "
            "(docs/bystander.md) that the author never touched — it "
            "validates every staged .md file unconditionally today, with "
            "no merge-scoping at all. This is the gap AC GE-120e-3-ii "
            "exists to close.",
        )

    def test_ge120e3ii_identical_content_arriving_unchanged_is_not_blocked_in_the_same_case(
        self,
    ) -> None:
        # covers: GE-120e-3-ii
        """AC-3 + coverage note: BOTH arms in one test, against the same
        repository recipe. The identical KIND of fault (a deleted test
        file; an invalid frontmatter status) blocks when the author
        resolves it (authored-fault fixture) and must NOT block when it
        arrives unchanged from a merge parent with no resolution of the
        author's own (carried-in-only fixture) — same checks, same
        predicate, only authorship differs. This is the test that cannot
        pass against a check switched off for merges entirely: the
        not-blocked assertions below would ALSO pass on such a check, but
        the blocked assertions would not.

        RED today for check_doc_frontmatter (same gap as the previous
        test): it blocks the carried-in-only fixture too, having no
        merge-scoping to exempt content matching a parent verbatim.
        check_contract_shrinking's assertions are expected to already pass.
        """
        # --- Arm 1: authored resolution — must be blocked -----------------
        blocked = _run_check(_CONTRACT_SHRINKING, _AUTHORED_FAULT_REPO)
        blocked_fm = _run_check(_DOC_FRONTMATTER, _AUTHORED_FAULT_REPO)
        self.assertNotEqual(
            0, blocked.returncode,
            "authored-fault arm must block (check_contract_shrinking).",
        )
        self.assertNotEqual(
            0, blocked_fm.returncode,
            "authored-fault arm must block (check_doc_frontmatter).",
        )

        # --- Arm 2: carried-in, unauthored — must NOT be blocked -----------
        not_blocked = _run_check(_CONTRACT_SHRINKING, _CARRIED_IN_ONLY_REPO)
        self.assertEqual(
            0,
            not_blocked.returncode,
            "check_contract_shrinking blocked a merge in which the test "
            "deletion arrived unchanged from the incoming branch, with no "
            "resolution of the author's own. Output:\n"
            f"{not_blocked.stdout}{not_blocked.stderr}",
        )

        not_blocked_fm = _run_check(_DOC_FRONTMATTER, _CARRIED_IN_ONLY_REPO)
        self.assertEqual(
            0,
            not_blocked_fm.returncode,
            "check_doc_frontmatter blocked a merge in which the invalid "
            "frontmatter arrived unchanged from the incoming branch, with "
            "no resolution of the author's own — the discriminator must be "
            "authorship, not the mere presence of bad frontmatter. "
            f"Output:\n{not_blocked_fm.stdout}{not_blocked_fm.stderr}",
        )

    def test_ge120e3ii_no_check_skips_inspection_while_a_merge_is_in_progress(self) -> None:
        # covers: GE-120e-3-ii
        """AC-4: neither check treats a merge-in-progress as grounds to skip
        inspecting the author's own content. Confirms MERGE_HEAD is
        genuinely present at invocation time (the only real window in which
        this property is even observable — see GE-120c-1-i's identical
        requirement) and that both checks still object to the author's own
        fault in that exact window. This guards against a future "fix" for
        AC-2/AC-3 that (wrongly) makes a check skip entirely during a merge
        instead of scoping correctly to authored content — a check that
        consults MERGE_HEAD to decide WHETHER to inspect would pass this
        file's other assertions just as happily by skipping everything, so
        this test's job is to make that failure mode observable on its own.
        """
        self.assertTrue(
            (_AUTHORED_FAULT_REPO / ".git" / "MERGE_HEAD").exists(),
            "Fixture invalid: MERGE_HEAD must be present for this "
            "assertion to mean anything.",
        )

        contract_outcome = _run_check(_CONTRACT_SHRINKING, _AUTHORED_FAULT_REPO)
        self.assertNotEqual(
            0,
            contract_outcome.returncode,
            "check_contract_shrinking must still inspect and object while "
            "a merge is genuinely in progress — a merge changes "
            "attribution, never whether content is inspected.",
        )

        fm_outcome = _run_check(_DOC_FRONTMATTER, _AUTHORED_FAULT_REPO)
        self.assertNotEqual(
            0,
            fm_outcome.returncode,
            "check_doc_frontmatter must still inspect and object while a "
            "merge is genuinely in progress.",
        )


class TestGE120e3iiReachableFromEntryPoint(unittest.TestCase):
    """test_ge_120e_3_ii_reachable_from_entry_point: this AC's test_spec
    authored no dedicated entry-point declaration (its own 'angle:
    reachability' note says so explicitly) — this test resolves it: both
    checks are dispatched exactly as the commit path dispatches them, as a
    separate OS process, never as an imported function call.
    """

    def setUp(self) -> None:
        if _SETUP_ERROR is not None:
            self.fail(f"Module fixture setup failed: {_SETUP_ERROR}")
        if not _CONTRACT_SHRINKING.exists() or not _DOC_FRONTMATTER.exists():
            self.fail(
                "check_contract_shrinking.py / check_doc_frontmatter.py not "
                "found at canonical path."
            )

    def test_ge_120e_3_ii_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-3-ii
        contract_outcome = _run_check(_CONTRACT_SHRINKING, _AUTHORED_FAULT_REPO)
        self.assertIsInstance(contract_outcome, subprocess.CompletedProcess)
        self.assertNotEqual(
            0,
            contract_outcome.returncode,
            "Dispatching check_contract_shrinking.py as a real subprocess "
            "against the authored-fault fixture must produce a non-zero "
            "exit — importing _scan_diff() directly would not exercise the "
            "real CLI entry point this AC requires.",
        )

        fm_outcome = _run_check(_DOC_FRONTMATTER, _AUTHORED_FAULT_REPO)
        self.assertIsInstance(fm_outcome, subprocess.CompletedProcess)
        self.assertNotEqual(
            0,
            fm_outcome.returncode,
            "Dispatching check_doc_frontmatter.py as a real subprocess "
            "against the authored-fault fixture must produce a non-zero "
            "exit.",
        )


if __name__ == "__main__":
    unittest.main()
