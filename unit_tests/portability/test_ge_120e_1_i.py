"""
MODULE: test_ge_120e_1_i
AC: GE-120e-1-i — "An empty authored change set is inspected as empty, never
    widened back to the whole staged tree"
GOAL: TDD red-baseline tests for the anti-pattern GE-120e-1-i forbids: a check
    that works out its own change set must NOT fall back to the whole staged
    diff when the narrowed (authored) change set comes back empty.

BUSINESS CONTEXT: Ticket 29 of EPIC-TrustThatAGreenCheckActuallyChecked.
    source_ac: GE-120e-1-i. test_spec (AC YAML) is authoritative over the
    ticket body's derived Gherkin and supplies the four test names used below.

WHY TWO CHECKS, NOT ONE: the AC's own doc_links name
    check_contract_shrinking.py as "the natural subject for the fixture", but
    an EMPIRICAL PROBE run at test-authoring time (git worktree + a real merge
    with zero authored content, carrying in a bad-frontmatter doc + a staged
    test-file deletion + a production-file edit) found:

    - check_contract_shrinking.py ALREADY exits 0 on this exact fixture today.
      Its private `_merge_scoped_paths()` / `_get_weakening_diff()` helpers
      (added under GE-111f, a different and earlier ticket) already narrow to
      the intersection of both parents' diffs and already treat an empty
      intersection as an explicit "" rather than falling back — the very
      property this AC pins down, already true for this one check by
      accident of a prior, unrelated fix.
    - check_doc_frontmatter.py has NO merge-awareness at all
      (`get_staged_md_files()` runs a flat, unscoped
      `git diff --cached --name-status`) and BLOCKS on this exact fixture
      today, reporting the carried-in doc's missing frontmatter fields as
      though the merge author had written it.

    A test written ONLY against check_contract_shrinking.py would be GREEN
    before any implementation work here — a false, already-satisfied red
    baseline (CLAUDE.md "TDD Order" + this agent's own red-baseline mandate).
    GE-120e-1's own AC requires the shared source to be consumed by BOTH
    named self-deriving checks ("MIGRATE BOTH OBSERVED CONSUMERS IN THE SAME
    CHANGE"), so asserting both checks pass on this fixture is squarely
    inside this AC's scope, not an extension of it — and it is the only
    formulation of AC-1/AC-2 that is genuinely RED today.

ARCHITECTURE / DEPENDENCIES:
    - Tests 1 and 2 build ONE real second working copy of this repository via
      `git worktree add` (never a synthetic minimal repo — check_doc_frontmatter
      needs the real docs/FRONTMATTER.md and docs/components.json this repo
      ships), stage a real merge with `git merge --no-commit --no-ff` so
      MERGE_HEAD is set and the index reflects the merge before it is
      committed, and run the checks as real subprocesses. This satisfies the
      AC's coverage note ("cover it by executing the check as a process
      against a repository in that state") and the Real-Artifact Behavioral
      Test Mandate: the fixture is a real git repository, not a mock.
    - Test 3 depends on GE-120a-1's shared could-not-check outcome vocabulary
      module. GE-120a-1 has since landed it at
      templates/scripts/commit_guardian/check_outcome.py (module-level
      string constants OUTCOME_OK / OUTCOME_COULD_NOT_CHECK + an
      emit_result() writer — NOT an Outcome enum, and NOT
      `_check_outcome.py` with a leading underscore; both were this test's
      earlier, pre-GE-120a-1-landing guess and are corrected here per
      architect-review's 2026-08-25 21:52 re-review comment on this ticket).
      That module does NOT yet define a third `OUTCOME_NOTHING_TO_INSPECT`
      constant — this AC's own instruction is to ADD one to GE-120a-1's
      existing module rather than invent a parallel vocabulary or module.
      This test imports the REAL check_outcome module (inserting
      templates/scripts/commit_guardian/ onto sys.path, matching the
      import-resolution the checks themselves rely on when run as scripts)
      and fails via an explicit self.fail() naming the still-missing
      constant — the same convention already used in this epic by
      test_ge_120c1i_setup_failure_reporting.py and test_ge_120e_2_i.py.
    - Test 4 (reachability) deploys the commit_guardian scripts into the SAME
      second working copy via `build_phases.build_commit_guardian()` (the
      fast, direct-call deploy path already used by
      unit_tests/portability/test_build_deployment.py) and re-runs the
      DEPLOYED copy of check_doc_frontmatter.py against the same merge
      fixture — proving the widening defect (and, once fixed, its absence)
      is reachable from the actual deployed entry point per ADR-001
      template/deployed parity, not only from the source tree.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/29, GE-120e-1-i]:
  Initial TDD red-baseline. Empirically verified RED via a standalone probe
  (git worktree + real merge fixture, see module docstring) before writing
  this file: check_contract_shrinking.py exits 0 (not useful as the sole
  fixture target), check_doc_frontmatter.py exits 1 and names the carried-in
  doc — genuinely red. Test 3 is red via ImportError (GE-120a-1's outcome
  vocabulary does not exist). Confirmed by running this file directly (see
  sign-off comment for the captured red_baseline).
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/29, GE-120e-1-i,
  test-writer re-run]: GE-120a-1 landed its shared outcome-vocabulary module
  between this file's authoring and python-coder's attempt on this ticket —
  but at a different name/shape than test 3 guessed (`check_outcome.py`,
  plain string constants OUTCOME_OK / OUTCOME_COULD_NOT_CHECK, not
  `_check_outcome.py` with an `Outcome` enum). architect-review's 2026-08-25
  21:52 re-review comment on this ticket flagged the stale import and
  instructed: fix the test's import, do not create a `_check_outcome.py`
  shim. Per Source-of-Truth Discipline Rule 1, this is TEST DRIFT
  (classification: test_drift) — the real module is correct and matches
  GE-120a-1's own AC; only this test's speculative import path was wrong.
  Fixed test 3 to import the real `check_outcome` module (via sys.path
  insertion of templates/scripts/commit_guardian/, matching how the check
  scripts themselves resolve the sibling import) and to assert against its
  real string-constant API. The test remains genuinely RED: check_outcome.py
  does not yet define the third `OUTCOME_NOTHING_TO_INSPECT` constant this
  AC requires be added to it, so test 3 still fails via an explicit
  self.fail() naming that gap, not via ImportError against a module that no
  longer matches the real one.
====================================================================
"""
# @ac-tag: GE-120e-1-i

from __future__ import annotations

import logging
import subprocess
import sys
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

# ---------------------------------------------------------------------------
# GE-120a-1's shared could-not-check outcome vocabulary. GE-120a-1 has landed
# this at templates/scripts/commit_guardian/check_outcome.py: module-level
# string constants OUTCOME_OK / OUTCOME_COULD_NOT_CHECK plus an emit_result()
# writer (NOT an Outcome enum, and the filename has NO leading underscore —
# corrected here per architect-review's 2026-08-25 21:52 comment on this
# ticket after this test's earlier, pre-landing guess of `_check_outcome.py`
# / `Outcome` proved stale; see DECISION HISTORY above). Per this AC's own
# it_requirements ("REUSE GE-120a-1'S OUTPUT VOCABULARY FOR THE DISTINCTION
# ... add it to GE-120a-1's vocabulary ... rather than inventing a parallel
# one"), the "nothing of the author's to inspect" value must be a THIRD
# constant (`OUTCOME_NOTHING_TO_INSPECT`) added to this SAME module — not a
# new module, not an enum. The check scripts in this directory resolve this
# sibling import by relying on their own directory being on sys.path (see
# check_ac_parent_covered_by.py's `from check_outcome import ...`), so this
# test inserts templates/scripts/commit_guardian/ onto sys.path to match.
# ---------------------------------------------------------------------------
if str(_COMMIT_GUARDIAN_TEMPLATES) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_TEMPLATES))

try:
    from check_outcome import (  # type: ignore[import]
        OUTCOME_COULD_NOT_CHECK,
        OUTCOME_OK,
    )
    _OUTCOME_VOCAB_OK = True
except ImportError:
    OUTCOME_COULD_NOT_CHECK = None  # type: ignore[assignment]
    OUTCOME_OK = None  # type: ignore[assignment]
    _OUTCOME_VOCAB_OK = False

try:
    from check_outcome import OUTCOME_NOTHING_TO_INSPECT  # type: ignore[import]
    _NOTHING_TO_INSPECT_OK = True
except ImportError:
    OUTCOME_NOTHING_TO_INSPECT = None  # type: ignore[assignment]
    _NOTHING_TO_INSPECT_OK = False

_OUTCOME_VOCAB_MISSING_MSG = (
    "templates/scripts/commit_guardian/check_outcome.py could not be "
    "imported (even with that directory on sys.path). GE-120a-1 was "
    "expected to declare OUTCOME_OK / OUTCOME_COULD_NOT_CHECK there; if "
    "this fires, either GE-120a-1's module regressed or moved, or this "
    "test's import path needs re-deriving against the current tree."
)

_NOTHING_TO_INSPECT_MISSING_MSG = (
    "templates/scripts/commit_guardian/check_outcome.py exists and exposes "
    "OUTCOME_OK / OUTCOME_COULD_NOT_CHECK (GE-120a-1 landed), but does not "
    "yet define a third OUTCOME_NOTHING_TO_INSPECT constant. Per this AC's "
    "own it_requirements ('REUSE GE-120a-1'S OUTPUT VOCABULARY FOR THE "
    "DISTINCTION ... add it to GE-120a-1's vocabulary ... rather than "
    "inventing a parallel one'), the implementer must add "
    "OUTCOME_NOTHING_TO_INSPECT to THIS SAME check_outcome.py module — do "
    "NOT create a separate module or a parallel vocabulary."
)

_GIT_ENV_OVERRIDES = {
    "PRE_COMMIT_ALLOW_NO_CONFIG": "1",
}


def _run(cmd: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**_env_base(), **_GIT_ENV_OVERRIDES},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Command %s failed to run in %s: %s", cmd, cwd, exc)
        raise


def _env_base() -> dict:
    import os
    return dict(os.environ)


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = _run(["git", *args], cwd=cwd)
    if result.returncode != 0:
        logger.warning(
            "git %s failed (rc=%s) in %s: %s", args, result.returncode, cwd,
            result.stderr,
        )
    return result


class _EmptyAuthoredChangeSetFixture:
    """Builds ONE real second working copy of this repository, standing in
    the exact commit shape this AC describes: a merge whose author (the
    branch currently checked out, `ours`) wrote nothing that overlaps with
    the carried-in content from `theirs` — a bad-frontmatter doc, a staged
    test-file deletion, and a production-file edit — while `ours` itself
    made only an unrelated scratch commit.

    Built and torn down ONCE per test class (see setUpClass/tearDownClass on
    the TestCase below) because standing up a real git worktree + three
    commits + a merge costs real wall-clock time; every test method in this
    file only READS the resulting staged index (the checks under test never
    mutate git state), so sharing one fixture across methods is safe and
    keeps each individual test fast.
    """

    def __init__(self) -> None:
        suffix = uuid.uuid4().hex[:10]
        import tempfile
        self.root = Path(tempfile.gettempdir()) / f"ge120e1i-fixture-{suffix}"
        self._ours_branch = f"ge120e1i-ours-{suffix}"
        self._theirs_branch = f"ge120e1i-theirs-{suffix}"
        self.baddoc_rel = "docs/_ge120e1i_probe_baddoc.md"
        self.deleted_test_rel = "unit_tests/_ge120e1i_probe_test.py"
        self.prod_file_rel = "_ge120e1i_probe_prod.py"
        self.scratch_rel = "_ge120e1i_probe_scratch.txt"

    def build(self) -> None:
        _run_git(
            ["worktree", "add", "--detach", str(self.root), "HEAD"], cwd=_REPO_ROOT,
        )
        if not (self.root / ".git").exists():
            raise RuntimeError(
                f"Fixture setup failed: `git worktree add` did not create {self.root}"
            )
        _run_git(["config", "user.email", "ge120e1i-fixture@example.com"], cwd=self.root)
        _run_git(["config", "user.name", "GE-120e-1-i fixture"], cwd=self.root)

        # Base commit c0 — common ancestor holding the file `theirs` will
        # delete, and the production file `theirs` will edit.
        (self.root / self.deleted_test_rel).write_text(
            "def test_probe():\n    assert True\n", encoding="utf-8",
        )
        (self.root / self.prod_file_rel).write_text(
            "def probe_fn():\n    return 1\n", encoding="utf-8",
        )
        _run_git(["add", self.deleted_test_rel, self.prod_file_rel], cwd=self.root)
        _run_git(["commit", "-q", "-m", "base: scratch fixture files"], cwd=self.root)
        base_sha = _run_git(["rev-parse", "HEAD"], cwd=self.root).stdout.strip()

        # `ours` — the author's own branch: one unrelated authored commit
        # that touches none of the content the merge will carry in.
        _run_git(["checkout", "-q", "-b", self._ours_branch], cwd=self.root)
        (self.root / self.scratch_rel).write_text("authored scratch\n", encoding="utf-8")
        _run_git(["add", self.scratch_rel], cwd=self.root)
        _run_git(
            ["commit", "-q", "-m", "author: unrelated scratch change"], cwd=self.root,
        )

        # `theirs` — mainline: carries in a bad-frontmatter doc (new file),
        # a test-file deletion, and a production-file edit. The author of
        # `ours` never touches any of these.
        _run_git(["checkout", "-q", "-b", self._theirs_branch, base_sha], cwd=self.root)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / self.baddoc_rel).write_text(
            "---\nfoo: bar\n---\n# Bad doc\n", encoding="utf-8",
        )
        _run_git(["rm", "-q", self.deleted_test_rel], cwd=self.root)
        (self.root / self.prod_file_rel).write_text(
            "def probe_fn():\n    return 2\n", encoding="utf-8",
        )
        _run_git(["add", self.baddoc_rel, self.prod_file_rel], cwd=self.root)
        _run_git(
            ["commit", "-q", "-m", "mainline: carried-in content"], cwd=self.root,
        )

        # Merge theirs into ours, stopping BEFORE the merge commit so the
        # index reflects exactly what a pre-commit hook would see: staged,
        # with MERGE_HEAD set, nothing yet committed.
        _run_git(["checkout", "-q", "-f", self._ours_branch], cwd=self.root)
        merge_result = _run_git(
            ["merge", self._theirs_branch, "--no-commit", "--no-ff"], cwd=self.root,
        )
        merge_head = _run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=self.root)
        if merge_head.returncode != 0:
            raise RuntimeError(
                "Fixture setup failed: MERGE_HEAD was not set after "
                f"`git merge --no-commit --no-ff` (merge stdout: "
                f"{merge_result.stdout!r}, stderr: {merge_result.stderr!r}). "
                "The fixture does not stand in the commit shape this AC "
                "describes."
            )
        staged = _run_git(["diff", "--cached", "--name-only"], cwd=self.root).stdout
        for expected in (self.baddoc_rel, self.deleted_test_rel, self.prod_file_rel):
            if expected not in staged:
                raise RuntimeError(
                    f"Fixture setup failed: expected {expected!r} to be part "
                    f"of the staged merge, but `git diff --cached --name-only` "
                    f"reported only: {staged!r}"
                )

    def teardown(self) -> None:
        _run_git(
            ["worktree", "remove", "--force", str(self.root)], cwd=_REPO_ROOT,
        )
        _run_git(["branch", "-D", self._ours_branch], cwd=_REPO_ROOT)
        _run_git(["branch", "-D", self._theirs_branch], cwd=_REPO_ROOT)


class TestCleanAutomergeWithNoAuthoredContentIsNotBlocked(unittest.TestCase):
    """AC-1: the change set it inspects is empty, it raises no objection,
    and the commit is not blocked."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _EmptyAuthoredChangeSetFixture()
        cls.fixture.build()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()

    def test_ge120e1i_clean_automerge_with_no_authored_content_is_not_blocked(
        self,
    ) -> None:
        # covers: GE-120e-1-i
        """Both self-deriving checks named by GE-120e-1 must exit clean on a
        merge whose only own-authored content is an unrelated scratch file,
        even though the carried-in content (a bad-frontmatter doc + a staged
        test deletion) is exactly what each check objects to when it
        believes that content is the author's.

        check_contract_shrinking.py already passes this today (a prior,
        unrelated fix — GE-111f — already narrows its own diff on merges).
        check_doc_frontmatter.py does not: it runs an unscoped
        `git diff --cached --name-status` with no merge-awareness at all, so
        it reports the carried-in doc's missing frontmatter fields as if the
        merge author had written them. THIS is the RED assertion — it fails
        today with exit code 1 and a FRONTMATTER VIOLATION naming the
        carried-in doc, and must be fixed by having both checks consume
        GE-120e-1's shared, non-widening change-set derivation.
        """
        contract_shrinking = _run(
            ["python3", str(_CHECK_CONTRACT_SHRINKING)], cwd=self.fixture.root,
        )
        self.assertEqual(
            0,
            contract_shrinking.returncode,
            "check_contract_shrinking.py must exit clean on a merge with no "
            f"authored content. stdout={contract_shrinking.stdout!r} "
            f"stderr={contract_shrinking.stderr!r}",
        )

        doc_frontmatter = _run(
            ["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.fixture.root,
        )
        self.assertEqual(
            0,
            doc_frontmatter.returncode,
            "check_doc_frontmatter.py must exit clean on a merge with no "
            "authored content — it must not inspect the carried-in doc as "
            f"though the merge author wrote it. stdout="
            f"{doc_frontmatter.stdout!r} stderr={doc_frontmatter.stderr!r}",
        )


class TestEmptyChangeSetDoesNotFallBackToStagedTree(unittest.TestCase):
    """AC-2: it does not fall back to the whole staged tree on finding the
    change set empty."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _EmptyAuthoredChangeSetFixture()
        cls.fixture.build()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()

    def test_ge120e1i_empty_change_set_does_not_fall_back_to_the_staged_tree(
        self,
    ) -> None:
        # covers: GE-120e-1-i
        """The carried-in content known to trip each check
        (docs/_ge120e1i_probe_baddoc.md's missing frontmatter fields;
        unit_tests/_ge120e1i_probe_test.py's deletion) must be named NOWHERE
        in either check's combined output. If an implementation treats an
        empty narrowed set as 'no filter applied' and widens back to the
        full staged diff, the carried-in doc path reappears in the output
        (as it does today for check_doc_frontmatter.py) — this is the exact
        anti-pattern this AC forbids ('if the narrowed set is empty, use the
        staged diff').
        """
        contract_shrinking = _run(
            ["python3", str(_CHECK_CONTRACT_SHRINKING)], cwd=self.fixture.root,
        )
        combined_cs = contract_shrinking.stdout + contract_shrinking.stderr
        self.assertNotIn(
            self.fixture.baddoc_rel, combined_cs,
            "check_contract_shrinking.py's output must never name the "
            "carried-in doc — doing so would mean it widened its scan back "
            f"to the full staged tree. Output: {combined_cs!r}",
        )
        self.assertNotIn(
            self.fixture.deleted_test_rel, combined_cs,
            "check_contract_shrinking.py's output must never name the "
            "carried-in test-file deletion on this fixture — the deletion "
            "is entirely theirs, not the merge author's. Output: "
            f"{combined_cs!r}",
        )

        doc_frontmatter = _run(
            ["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.fixture.root,
        )
        combined_df = doc_frontmatter.stdout + doc_frontmatter.stderr
        self.assertNotIn(
            self.fixture.baddoc_rel, combined_df,
            "check_doc_frontmatter.py's output names the carried-in doc "
            "today — the exact widening-fallback defect this AC forbids. "
            f"Output: {combined_df!r}",
        )


class TestEmptyOutcomeDistinguishableFromCouldNotCheck(unittest.TestCase):
    """AC-3: an empty change set is reported as "nothing of the author's to
    inspect" and is distinguishable in the output from the could-not-check
    outcome GE-120a-1 defines."""

    def test_ge120e1i_empty_outcome_is_distinguishable_from_could_not_check(
        self,
    ) -> None:
        # covers: GE-120e-1-i
        """RED until check_outcome.py defines a third
        OUTCOME_NOTHING_TO_INSPECT constant (see module docstring
        'ARCHITECTURE / DEPENDENCIES' and `_NOTHING_TO_INSPECT_MISSING_MSG`
        above for the exact gap and the required fix location).

        Once it lands: the empty-authored-change-set outcome
        (`OUTCOME_NOTHING_TO_INSPECT`) and GE-120a-1's could-not-check
        outcome (`OUTCOME_COULD_NOT_CHECK`) must be two DISTINCT string
        values, so a reader (or a machine caller, per GE-120a-1's own
        it_requirements: 'machine-readable INDEPENDENTLY of the exit code')
        can tell 'a commit with nothing to inspect' from 'a check that never
        looked' without parsing prose. Reporting both with the SAME value
        collapses this AC's entire distinction, which is the AC's own
        load-bearing clause (see the AC's 'Coverage note' and 'AXIS GUARD'
        in the store notes).
        """
        if not _OUTCOME_VOCAB_OK:
            self.fail(_OUTCOME_VOCAB_MISSING_MSG)
        if not _NOTHING_TO_INSPECT_OK:
            self.fail(_NOTHING_TO_INSPECT_MISSING_MSG)

        # Defensive completeness for when the constant DOES land: the two
        # outcomes this AC cares about must never collapse to one value.
        self.assertNotEqual(
            OUTCOME_NOTHING_TO_INSPECT,
            OUTCOME_COULD_NOT_CHECK,
            "The empty-change-set outcome and the could-not-check outcome "
            "must have distinct values — collapsing them means a reader "
            "cannot tell 'nothing of the author's to inspect' from 'this "
            "check never looked', which is precisely the ambiguity this AC "
            "exists to remove.",
        )
        self.assertNotEqual(
            OUTCOME_NOTHING_TO_INSPECT,
            OUTCOME_OK,
            "The empty-change-set outcome must also be distinguishable from "
            "an ordinary clean pass with content actually inspected — "
            "otherwise a caller cannot tell 'ran and found nothing wrong' "
            "from 'had nothing of the author's to look at'.",
        )


class TestReachableFromDeployedEntryPoint(unittest.TestCase):
    """REQUIRED reachability angle: invoke the DEPLOYED copy of the checks
    (per ADR-001 template/deployed parity — the Implementation Notes on this
    ticket explicitly require verifying the deployed layout, not only the
    source tree) as real subprocesses, and assert the widening-fallback
    defect (and, once fixed, its absence) is reachable there too — not only
    from templates/scripts/commit_guardian/ source.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _EmptyAuthoredChangeSetFixture()
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
                cls.fixture.root / "scripts" / "commit_guardian"
                / "check_doc_frontmatter.py"
            ).exists()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()

    def test_ge_120e_1_i_reachable_from_entry_point(self) -> None:
        # covers: GE-120e-1-i
        """Runs the DEPLOYED (`scripts/commit_guardian/`, not
        `templates/scripts/commit_guardian/`) copy of check_doc_frontmatter.py
        as a real subprocess against the same empty-authored-change-set
        merge fixture, and asserts it does not block. This is the
        production entry point a real pre-commit hook actually invokes
        (ADR-001: templates/ is the canonical SOURCE, scripts/ is what
        `build.py` deploys and what the commit path runs) — importing the
        check's functions directly would not exercise this at all, and
        would not catch a fix that lands only in templates/ without a
        build.py run (the exact 'template-only fix is a no-op in the
        deployed layout' failure mode this ticket's own Implementation
        Notes warn about).
        """
        if not _BUILD_PHASES_OK:
            self.fail(
                "scripts.build_phases.build_commit_guardian could not be "
                "imported — cannot deploy the commit_guardian scripts into "
                "the fixture worktree to test the deployed entry point."
            )
        if not self.deployed_ok:
            self.fail(
                "build_commit_guardian() did not produce "
                f"{self.fixture.root}/scripts/commit_guardian/"
                "check_doc_frontmatter.py — cannot exercise the deployed "
                "entry point."
            )

        deployed_check = (
            self.fixture.root / "scripts" / "commit_guardian"
            / "check_doc_frontmatter.py"
        )
        result = _run(["python3", str(deployed_check)], cwd=self.fixture.root)
        self.assertEqual(
            0,
            result.returncode,
            "The DEPLOYED check_doc_frontmatter.py must exit clean on a "
            "merge with no authored content, exactly like the templates/ "
            "source copy must (test 1) — a fix that only lands in "
            "templates/ without reaching the deployed layout is a no-op "
            f"for every real commit. stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            self.fixture.baddoc_rel, combined,
            "The deployed check must not name the carried-in doc either — "
            f"same widening-fallback prohibition as test 2. Output: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
