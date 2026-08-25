"""
MODULE: unit_tests/commit_guardian/test_ge_122a_1_i.py
GOAL: RED test-first stubs for GE-122a-1-i -- "A collision is found even when
    only one claimant is in the current change set". This ticket EXTENDS the
    already-green templates/scripts/commit_guardian/check_identifier_uniqueness.py
    (GE-122a-1): the whole-collection walk (`run_uniqueness_pass`) already
    exists and already scans the ENTIRE on-disk collection regardless of the
    git change set. What does NOT exist yet is the commit-time DISPOSITION
    layer this AC requires: attribution (BLOCK vs REPORT-ONLY) must be
    diff-scoped even though inspection is not.
BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1-i.yaml
    and
    tickets/00_inbox/epics/EPIC-GE122UniquenessPassAndRepair/02_TICKET-20260818-GE-122a-1-i.md.
    The AC's own Coverage Note rules out any test that stages BOTH claimants:
    such a test cannot distinguish a whole-collection pass from a
    changed-files pass and therefore proves nothing about this criterion.
    Every test below therefore stages EXACTLY the claimant subset the
    Gherkin names (one / neither) via REAL `git` operations against a REAL
    on-disk git repository fixture -- never a mock of git or of the scanning
    walk.

CONTRACT UNDER TEST (fixed here because this specific behavior does not exist
in check_identifier_uniqueness.py yet -- this is the explicit target
python-coder must satisfy; it extends, and does not narrow, the
six-consumer verdict contract already pinned by test_ge_122a_1.py):

    IMPORTANT -- value-typed, not string-typed. A sibling AC in this same
    tree, GE-122d-3 ("outcome must be a distinct VALUE in the pass's return
    type ... not an exit code plus prose") and GE-122d-3-i ("a caller can
    tell them apart by inspecting the returned outcome value alone, with no
    string matching and no reliance on the exit code") forbid exactly the
    printed-label contract an earlier draft of this file pinned. Attribution
    is therefore fixed here as a property a caller reads off the returned
    object, never a substring a caller must grep out of stdout/stderr.

    1. A new, importable function `compute_commit_disposition(verdict,
       staged_paths)` takes the EXISTING `run_uniqueness_pass(collection_root)`
       verdict (called exactly once -- per this ticket's Implementation
       Notes, "Must not add a second collection walk... reuse GE-122a-1's
       single pass and filter its verdict") plus the current change set
       (an iterable of staged file paths, as returned by
       `git diff --cached --name-only` -- the same staged-diff convention
       already used by `check_ac_schema.py`'s `_get_staged_ac_paths`, named
       in this AC's doc_links as the precedent for changed-files scoping).
    2. It returns a `CommitDisposition` object exposing:
         disposition.blocking            -> bool. True iff at least one
             finding, in any namespace, has at least one claimant path in
             `staged_paths` (that finding is ATTRIBUTED).
         disposition.unattributed_count  -> int. Count of findings (across
             all namespaces) with NO claimant path in `staged_paths`.
         disposition.findings            -> iterable of per-finding objects,
             each exposing (at minimum):
               .namespace   -> str, the namespace name the finding came from.
               .number      -> str, the contested identifier (same value as
                               the source Finding.number).
               .paths       -> list[str], EVERY claimant path for that
                               number (same value as the source
                               Finding.paths -- attribution never narrows
                               which paths are reported).
               .attributed  -> bool. True iff at least one of `.paths` is in
                               `staged_paths`.
       A caller must be able to determine BLOCK vs REPORT-ONLY, and which
       specific findings drove that decision, purely by reading these typed
       fields -- no string matching against any printed output is part of
       this contract.
    3. `check_identifier_uniqueness.py`'s CLI entry point (`main()`) must use
       `compute_commit_disposition` (fed by the real `git diff --cached
       --name-only` staged set) to decide its own exit code: non-zero when
       `disposition.blocking` is True, 0 otherwise (even when
       `unattributed_count > 0` -- a reported-but-unattributed backlog must
       never block, per this AC's it_requirements decision). This is the
       one part of the contract that is legitimately behavioral rather than
       value-typed: the exit code IS the observable interface of a
       pre-commit hook, and it is asserted directly below via subprocess,
       never via a string match on hook output.
    4. A staged record whose claimed number no other on-disk record claims
       produces NO Finding at all (already guaranteed by the existing
       `run_uniqueness_pass` contract) and therefore appears nowhere in
       `disposition.findings` either.

Any correct implementation may choose its own internal representation for
`CommitDisposition` / the per-finding wrapper (a dataclass, a namedtuple, a
plain object) as long as the attribute-access surface above holds -- these
tests only read the documented attributes and never introspect private
internals.

ARCHITECTURE / EXERCISE STRATEGY:
  - All four tests build a REAL on-disk `git init`-ed repository under a
    tempdir (never `origin/main`, `main`, or a hardcoded SHA -- see the
    caution against exactly that mistake on PR #462) and drive the ACTUAL
    git index via `git add` / `git commit`.
  - The PRIMARY assertions for "was this finding attributed / how many are
    unattributed / which paths does it name" are made by dynamically
    importing check_identifier_uniqueness.py (the same
    importlib.util.spec_from_file_location convention test_ge_122a_1.py
    already uses) and calling `run_uniqueness_pass` + `compute_commit_disposition`
    directly against the fixture repo, then reading the RETURNED VALUE's
    typed attributes -- never a regex over printed text.
  - The block / do-not-block DISPOSITION is additionally asserted end-to-end
    by invoking the SOURCE-TREE script as a subprocess (never a mock of
    `main()`) and checking its exit code -- this is the one place a
    behavioral, process-boundary assertion belongs, because the exit code
    is a pre-commit hook's actual contract with git. No test asserts on any
    printed string as its primary or sole evidence.
  - This ticket does not touch the build/deploy manifest (that is
    GE-122a-1's already-covered concern), so these tests exercise the
    source-tree script directly.
  - AC-format fixtures are produced with yaml.safe_dump (per
    docs/reference/fixture-policy.md's Fixture Authenticity Rule); a
    hand-typed YAML literal is explicitly rejected by that policy because it
    reproduces the author's indentation bias rather than the real
    serializer's column-0 output -- the exact defect class that hid the
    files_touched parser bug in EPIC-PhantomDoneFilesTouched.

DECISION HISTORY
- 2026-08-18 [GE-122a-1-i/test-writer]: Initial authoring of all four RED
  test stubs pinned attribution as literal printed substrings
  ("ATTRIBUTED" / "UNATTRIBUTED") in main()'s stdout/stderr.
- 2026-08-18 [GE-122a-1-i/test-writer, revision]: Coordinator flagged that
  the printed-label contract directly contradicts GE-122d-3 / GE-122d-3-i's
  binding requirement that outcome be a distinct VALUE in the return type,
  inspectable with no string matching and no reliance on the exit code.
  Rewrote all four tests to assert attribution via a new
  `compute_commit_disposition()` return value's typed `.attributed` /
  `.blocking` / `.unattributed_count` fields (imported and called directly,
  the way test_ge_122a_1.py already does), keeping the exit-code assertion
  (still asserted, still correct) but demoting it to a secondary check
  where it would otherwise coincidentally pass today. Verified RED via
  `AC_ENFORCE_STRICT=1 python3 -m pytest unit_tests/commit_guardian/test_ge_122a_1_i.py -q`:
  all four fail with `AttributeError: module 'check_identifier_uniqueness'
  has no attribute 'compute_commit_disposition'` or an exit-code
  AssertionError -- see the test-writer sign-off comment for the exact
  captured output.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Canonical paths -- templates/scripts/commit_guardian/ is the source of
# truth (ADR-001: template-is-canonical, .leafcutter/ is a build output).
# This ticket does not touch the deploy manifest, so tests run the
# SOURCE-TREE copy directly (GE-122a-1's own test suite already covers
# deployed-layout parity for this module).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"

_SUBPROCESS_TIMEOUT_SECONDS = 60
_CLEAN_ENV_TEMPLATE = {"PATH": "/usr/bin:/bin:/usr/local/bin"}


def _load_module():
    """Dynamically import check_identifier_uniqueness from its canonical path.

    Mirrors test_ge_122a_1.py's own `_load_module` convention exactly so both
    test files agree on how the module under test is located and loaded.

    Returns:
        The loaded module, or None if the canonical file does not exist yet.
    """
    if not _CANONICAL.exists():
        return None
    spec = _ilu.spec_from_file_location("check_identifier_uniqueness", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_identifier_uniqueness"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def _require_mod(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if the module under test could not be loaded.

    Args:
        test_case: The calling TestCase instance.
    """
    if _mod is None:
        test_case.fail(
            f"check_identifier_uniqueness.py not found at canonical path "
            f"{_CANONICAL}. Ensure GE-122a-1 has already been implemented "
            "(this ticket only EXTENDS that module)."
        )


# ---------------------------------------------------------------------------
# Real-git fixture helpers -- no mocking of git or of the filesystem walk.
# ---------------------------------------------------------------------------


def _git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Run a real `git` subprocess against a fixture repository.

    Args:
        args: Argument list appended after `git` (e.g. ["add", "."]).
        cwd: Working directory to run git in.

    Returns:
        The completed subprocess result. Raises via check=True on failure so
        a broken fixture setup surfaces immediately rather than masquerading
        as a red test result.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={**_CLEAN_ENV_TEMPLATE, "HOME": str(cwd)},
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _init_git_repo(root: Path) -> None:
    """Initialize a real git repository with a usable local identity.

    Args:
        root: Directory to initialize as a git repository.
    """
    _git(["init", "-q"], root)
    _git(["config", "user.email", "fixture@example.invalid"], root)
    _git(["config", "user.name", "Fixture Author"], root)


def _write_ac_yaml(path: Path, data: dict) -> None:
    """Write an AC YAML fixture using the REAL serializer (yaml.safe_dump).

    Per docs/reference/fixture-policy.md, a hand-typed YAML string is
    rejected as a fixture for a serialized format: it reproduces the
    author's indentation model rather than PyYAML's actual column-0 output.

    Args:
        path: Destination file path (parents created as needed).
        data: The AC record fields to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _resolve_non_ac_namespaces(root: Path) -> None:
    """Make the decisions, diagrams, and work-items namespaces resolvable.

    THIS COMMENT MUST NOT BE "TIDIED AWAY": every test in this file builds a
    fixture collection that only ever populates docs/acceptance-criteria/ --
    the other three namespaces (decisions, diagrams, work-items) are never
    touched, because this file's collisions are deliberately scoped to
    acceptance-criteria only (see the module docstring). Before GE-122e-3
    (2026-08-25), an entirely-missing namespace root/config fail-opened to
    NamespaceVerdict(passed=True, findings=[]) and `compute_commit_disposition`
    derived `.blocking` solely from attributed findings, so the other three
    namespaces being unresolvable was invisible to every assertion here.
    GE-122e-3 fixed BOTH of those: an unresolvable namespace now reports
    passed=False with an EMPTY findings list, and `.blocking` is now True
    whenever ANY namespace is unresolvable -- regardless of what is staged,
    per _commit_disposition.py's own "an unresolvable namespace is a
    misconfiguration of the gate itself, not a per-file collision that
    attribution can excuse" contract decision. Without this helper, EVERY
    "does NOT block" assertion in this file (TestNeitherClaimantStaged,
    TestUnattributedDoesNotBlockContrast, TestNewUncontestedRecordProducesNoFinding)
    fails not because of any bug in attribution, but because
    docs/architecture/adrs/, docs/architecture/diagrams/, and
    tickets/ticket_lifecycle.json simply do not exist in the fixture -- three
    namespaces reported as unresolvable, unconditionally blocking. This is
    the SAME incomplete-fixture defect already fixed once, the same way, in
    test_ge_122a_1.py's own `_build_fixture_collection` (see that function's
    docstring for the identical precedent) -- do not reintroduce a fourth
    copy of it by removing this call from a test's setUp.

    Deliberately builds each namespace in its legitimately-EMPTY-but-RESOLVED
    shape (an existing empty directory / a lifecycle config that declares
    zero folders) rather than populating it with fixture data of its own --
    see GE-122e-3's "THE CONTRACT DECISION"
    (unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py) for why an
    existing-but-empty root still passes cleanly, distinct from a root that
    was never created at all.

    Args:
        root: The fixture git repository root (already `git init`-ed).
    """
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
    tickets_root = root / "tickets"
    tickets_root.mkdir(parents=True, exist_ok=True)
    lifecycle_path = tickets_root / "ticket_lifecycle.json"
    # tickets/ticket_lifecycle.json MUST exist for the work-items namespace to
    # resolve at all -- scan_work_items reports passed=False (unresolvable)
    # when this file is missing, unreadable, or unparsable (see
    # _work_items_scanner.py's DECISION HISTORY, GE-122e-3), and an
    # unresolvable namespace now unconditionally blocks every commit
    # regardless of the staged set. Declaring zero folders keeps this
    # namespace genuinely empty (this file plants no work-item collisions)
    # while still being a config that WAS successfully read and parsed.
    with open(lifecycle_path, "w", encoding="utf-8") as fh:
        json.dump({"folders": []}, fh)


def _staged_paths(root: Path) -> set:
    """Return the REAL git-index staged file paths as resolved absolute Paths.

    Uses `git diff --cached --name-only`, the same staged-diff convention
    documented in this AC's doc_links (`check_ac_schema.py`'s
    `_get_staged_ac_paths`). This is the actual git index being queried --
    never a hand-maintained list standing in for "what's staged".

    Args:
        root: The fixture git repository root.

    Returns:
        Set of resolved absolute Path objects for every staged file.
    """
    result = _git(["diff", "--cached", "--name-only"], root)
    return {(root / line.strip()).resolve() for line in result.stdout.splitlines() if line.strip()}


def _run_uniqueness_script(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke the source-tree check_identifier_uniqueness.py as a subprocess.

    Used ONLY for the exit-code (block / do-not-block) assertions -- the
    one part of this contract that is legitimately process-boundary
    behavior. Value-level assertions (attribution, counts, paths) are made
    via direct import instead; see `_mod`.

    Args:
        cwd: Directory to run the script in (must be a git working tree --
            the script under test is expected to call
            `git diff --cached --name-only` relative to this directory).

    Returns:
        The completed subprocess result (never raises on non-zero exit --
        the exit code itself is the observation under test).
    """
    return subprocess.run(
        [sys.executable, str(_CANONICAL)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**_CLEAN_ENV_TEMPLATE, "HOME": str(cwd)},
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _find_disposition_finding(disposition, number: str):
    """Return the disposition finding matching `number`, or None.

    Args:
        disposition: The object returned by `compute_commit_disposition`.
        number: The contested identifier to look for (e.g. "GE-119").

    Returns:
        The matching finding object, or None if not present.
    """
    for finding in disposition.findings:
        if str(finding.number) == number:
            return finding
    return None


class _RealGitRepoTestCase(unittest.TestCase):
    """Shared tempdir + git-repo scaffolding for the behavioral tests."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _init_git_repo(self.root)
        # See _resolve_non_ac_namespaces's own docstring: without this, the
        # decisions/diagrams/work-items namespaces are unresolvable and
        # unconditionally block every disposition built from this fixture,
        # regardless of the acceptance-criteria attribution logic under test.
        _resolve_non_ac_namespaces(self.root)
        self.ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"


# ---------------------------------------------------------------------------
# Test 1: only one claimant staged -- the distinguishing scenario the AC's
# own Coverage Note requires (staging both claimants would prove nothing).
# ---------------------------------------------------------------------------


class TestOnlyOneClaimantStaged(_RealGitRepoTestCase):
    def test_collision_reported_when_only_one_claimant_is_staged(self):
        # covers: GE-122a-1-i
        """Two records both declare "GE-119" and are committed together (the
        historical baseline -- both "sat unmodified" for the purposes of
        this run). The CURRENT change set then touches and stages ONLY ONE
        of the two claimants. `compute_commit_disposition` must report the
        contested identifier with BOTH claimant paths -- including the path
        absent from the staged change set -- and its `.attributed` value
        must be True (readable directly off the returned finding, no string
        matching). The disposition's `.blocking` must also be True, and the
        real subprocess exit code must be non-zero.

        FAILS TODAY: `compute_commit_disposition` does not exist on the
        module at all, so this raises `AttributeError` before any value
        assertion is reached.
        """
        path_a = self.ac_dir / "GE-119-alpha.yaml"
        path_b = self.ac_dir / "GE-119-beta.yaml"
        _write_ac_yaml(path_a, {"id": "GE-119", "level": "L2", "title": "Alpha claimant"})
        _write_ac_yaml(path_b, {"id": "GE-119", "level": "L2", "title": "Beta claimant"})
        _git(["add", "."], self.root)
        _git(["commit", "-m", "both claimants committed together"], self.root)

        # The current change set touches and stages ONLY path_a. path_b sits
        # committed and untouched -- it appears in no diff, exactly as the
        # AC's Gherkin requires.
        with open(path_a, "a", encoding="utf-8") as fh:
            fh.write("# touched by the current change set\n")
        _git(["add", str(path_a.relative_to(self.root))], self.root)

        staged = _staged_paths(self.root)
        verdict = _mod.run_uniqueness_pass(self.root)
        disposition = _mod.compute_commit_disposition(verdict, staged)

        finding = _find_disposition_finding(disposition, "GE-119")
        self.assertIsNotNone(
            finding,
            msg=f"Expected a disposition finding for GE-119. Got: {list(disposition.findings)}",
        )
        reported_paths = {Path(p).resolve() for p in finding.paths}
        self.assertEqual(
            reported_paths,
            {path_a.resolve(), path_b.resolve()},
            msg=(
                "The finding must name BOTH claimant paths, including the "
                f"unstaged one. Got: {reported_paths}"
            ),
        )
        self.assertTrue(
            finding.attributed,
            msg="finding.attributed must be True: at least one claimant is staged.",
        )
        self.assertTrue(
            disposition.blocking,
            msg="disposition.blocking must be True when any finding is attributed.",
        )

        # Secondary, behavioral, process-boundary check: the real CLI must
        # also exit non-zero. This is asserted in addition to (never instead
        # of) the value-typed checks above.
        result = _run_uniqueness_script(self.root)
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A contested number with at least one claimant in the change "
                f"set must BLOCK the commit (non-zero exit). "
                f"stdout={result.stdout} stderr={result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# Test 2: neither claimant staged -- reported, not blocking.
# ---------------------------------------------------------------------------


class TestNeitherClaimantStaged(_RealGitRepoTestCase):
    def test_collision_reported_when_neither_claimant_is_staged(self):
        # covers: GE-122a-1-i
        """Both claimants of "GE-119" are committed and NEITHER is touched
        by the current change set (nothing is staged). `compute_commit_disposition`
        must still report the contested identifier with both claimant paths
        -- the change set may never be used to decide WHAT IS INSPECTED,
        only what is attributed -- with `.attributed` False, `.blocking`
        False, and `.unattributed_count` equal to 1. The real subprocess
        exit code must be 0 (non-blocking).

        FAILS TODAY: `compute_commit_disposition` does not exist yet, so
        this raises `AttributeError`.
        """
        path_a = self.ac_dir / "GE-119-alpha.yaml"
        path_b = self.ac_dir / "GE-119-beta.yaml"
        _write_ac_yaml(path_a, {"id": "GE-119", "level": "L2", "title": "Alpha claimant"})
        _write_ac_yaml(path_b, {"id": "GE-119", "level": "L2", "title": "Beta claimant"})
        _git(["add", "."], self.root)
        _git(["commit", "-m", "both claimants committed together, never touched again"], self.root)
        # Nothing staged this run: `git diff --cached --name-only` is empty.

        staged = _staged_paths(self.root)
        self.assertEqual(set(), staged, msg="Fixture sanity check: nothing should be staged this run.")

        verdict = _mod.run_uniqueness_pass(self.root)
        disposition = _mod.compute_commit_disposition(verdict, staged)

        finding = _find_disposition_finding(disposition, "GE-119")
        self.assertIsNotNone(
            finding,
            msg=f"Expected a disposition finding for GE-119. Got: {list(disposition.findings)}",
        )
        reported_paths = {Path(p).resolve() for p in finding.paths}
        self.assertEqual(
            reported_paths,
            {path_a.resolve(), path_b.resolve()},
            msg=f"The finding must name both claimant paths even though neither is staged. Got: {reported_paths}",
        )
        self.assertFalse(
            finding.attributed,
            msg="finding.attributed must be False: neither claimant is staged.",
        )
        self.assertFalse(
            disposition.blocking,
            msg="disposition.blocking must be False when no finding is attributed.",
        )
        self.assertEqual(
            1,
            disposition.unattributed_count,
            msg=f"Expected exactly one unattributed finding, got {disposition.unattributed_count}.",
        )

        # Secondary, behavioral, process-boundary check.
        result = _run_uniqueness_script(self.root)
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A contested number with NO claimant in the change set must "
                f"NOT block the commit. stdout={result.stdout} stderr={result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# Test 3: explicit contrast -- blocking vs non-blocking disposition.
# ---------------------------------------------------------------------------


class TestUnattributedDoesNotBlockContrast(unittest.TestCase):
    """test_unattributed_collision_reports_but_does_not_block_commit.

    Builds BOTH scenarios side by side in independent fixture repos and
    asserts the `.blocking` / `.unattributed_count` contrast directly on the
    returned disposition VALUES, because the disposition rule (attribution
    is diff-scoped, inspection is not) is only meaningfully covered by
    observing both dispositions diverge on otherwise-identical collections.
    The real exit-code contrast is asserted too, as a secondary,
    process-boundary confirmation of the same rule.
    """

    def setUp(self) -> None:
        _require_mod(self)

    def test_unattributed_collision_reports_but_does_not_block_commit(self):
        # covers: GE-122a-1-i
        """The neither-claimant-staged case must yield `disposition.blocking
        is False` and `disposition.unattributed_count == 1`, while the
        one-claimant-staged case -- built identically otherwise -- must
        yield `disposition.blocking is True`. Both dispositions are asserted
        in the same test so the contrast itself is the evidence, per this
        AC's it_requirements decision ("a contested number with at least one
        claimant in the change set BLOCKS... with no claimant... is
        REPORTED... and does NOT block"). The corresponding real exit codes
        (non-zero vs zero) are asserted as well, but as a secondary
        confirmation alongside the value-typed disposition.

        FAILS TODAY: `compute_commit_disposition` does not exist, so this
        raises `AttributeError` on the first call.
        """
        with tempfile.TemporaryDirectory() as blocking_dir, tempfile.TemporaryDirectory() as reported_dir:
            blocking_root = Path(blocking_dir)
            reported_root = Path(reported_dir)
            fixtures = {}

            for root in (blocking_root, reported_root):
                _init_git_repo(root)
                # See _resolve_non_ac_namespaces's own docstring: without
                # this, both fixtures' decisions/diagrams/work-items
                # namespaces are unresolvable and unconditionally block,
                # masking the attribution contrast this test exists to prove.
                _resolve_non_ac_namespaces(root)
                ac_dir = root / "docs" / "acceptance-criteria" / "fixture-component"
                path_a = ac_dir / "GE-119-alpha.yaml"
                path_b = ac_dir / "GE-119-beta.yaml"
                _write_ac_yaml(path_a, {"id": "GE-119", "level": "L2", "title": "Alpha claimant"})
                _write_ac_yaml(path_b, {"id": "GE-119", "level": "L2", "title": "Beta claimant"})
                _git(["add", "."], root)
                _git(["commit", "-m", "both claimants committed together"], root)
                fixtures[root] = (path_a, path_b)

            # blocking_root: stage a touch to ONE claimant this run.
            blocking_path_a, _blocking_path_b = fixtures[blocking_root]
            with open(blocking_path_a, "a", encoding="utf-8") as fh:
                fh.write("# touched by the current change set\n")
            _git(["add", str(blocking_path_a.relative_to(blocking_root))], blocking_root)

            # reported_root: nothing staged this run.

            blocking_staged = _staged_paths(blocking_root)
            reported_staged = _staged_paths(reported_root)

            blocking_verdict = _mod.run_uniqueness_pass(blocking_root)
            reported_verdict = _mod.run_uniqueness_pass(reported_root)

            blocking_disposition = _mod.compute_commit_disposition(blocking_verdict, blocking_staged)
            reported_disposition = _mod.compute_commit_disposition(reported_verdict, reported_staged)

            self.assertTrue(
                blocking_disposition.blocking,
                msg="One-claimant-staged disposition.blocking must be True.",
            )
            self.assertFalse(
                reported_disposition.blocking,
                msg="Neither-claimant-staged disposition.blocking must be False.",
            )
            self.assertEqual(
                1,
                reported_disposition.unattributed_count,
                msg=f"Expected exactly one unattributed finding, got {reported_disposition.unattributed_count}.",
            )
            self.assertEqual(
                0,
                blocking_disposition.unattributed_count,
                msg=(
                    "The one-claimant-staged case's single finding IS "
                    "attributed, so unattributed_count must be 0, got "
                    f"{blocking_disposition.unattributed_count}."
                ),
            )

            # Secondary, behavioral, process-boundary confirmation.
            blocking_result = _run_uniqueness_script(blocking_root)
            reported_result = _run_uniqueness_script(reported_root)
            self.assertNotEqual(
                0,
                blocking_result.returncode,
                msg=f"One-claimant-staged case must BLOCK. stdout={blocking_result.stdout} stderr={blocking_result.stderr}",
            )
            self.assertEqual(
                0,
                reported_result.returncode,
                msg=(
                    "Neither-claimant-staged case must NOT block. "
                    f"stdout={reported_result.stdout} stderr={reported_result.stderr}"
                ),
            )


# ---------------------------------------------------------------------------
# Test 4: a new, uncontested record produces no finding at all.
# ---------------------------------------------------------------------------


class TestNewUncontestedRecordProducesNoFinding(_RealGitRepoTestCase):
    def test_new_uncontested_record_produces_no_finding(self):
        # covers: GE-122a-1-i
        """A change set that adds a record claiming an identifier no other
        record claims must produce NO disposition finding for that record at
        all, and must not itself block.

        Paired, in the SAME collection and the SAME run, with an unrelated
        pre-existing "GE-119" collision that neither claimant touches this
        run (an unattributed finding). This keeps the test from being a
        vacuous carry-over check: an implementation that has not yet learned
        to compute attribution at all would ALSO fail the paired assertions
        on the unrelated GE-119 finding's `.attributed` value and
        `disposition.blocking`, so passing every assertion here requires
        genuinely correct attribution logic, not just "an uncontested
        record produces no Finding" (which the unmodified GE-122a-1
        implementation already guarantees on its own).

        FAILS TODAY: `compute_commit_disposition` does not exist, so this
        raises `AttributeError`.
        """
        contested_a = self.ac_dir / "GE-119-alpha.yaml"
        contested_b = self.ac_dir / "GE-119-beta.yaml"
        _write_ac_yaml(contested_a, {"id": "GE-119", "level": "L2", "title": "Alpha claimant"})
        _write_ac_yaml(contested_b, {"id": "GE-119", "level": "L2", "title": "Beta claimant"})
        _git(["add", "."], self.root)
        _git(["commit", "-m", "pre-existing collision, committed together"], self.root)

        new_path = self.ac_dir / "GE-777-new.yaml"
        _write_ac_yaml(new_path, {"id": "GE-777", "level": "L2", "title": "New uncontested record"})
        _git(["add", str(new_path.relative_to(self.root))], self.root)
        # Only GE-777 is staged this run -- neither GE-119 claimant is
        # touched, so the pre-existing collision must be unattributed.

        staged = _staged_paths(self.root)
        verdict = _mod.run_uniqueness_pass(self.root)
        disposition = _mod.compute_commit_disposition(verdict, staged)

        self.assertIsNone(
            _find_disposition_finding(disposition, "GE-777"),
            msg=f"An uncontested new record must produce no disposition finding. Got: {list(disposition.findings)}",
        )
        unrelated_finding = _find_disposition_finding(disposition, "GE-119")
        self.assertIsNotNone(
            unrelated_finding,
            msg="The unrelated pre-existing GE-119 collision must still be reported.",
        )
        self.assertFalse(
            unrelated_finding.attributed,
            msg="Neither GE-119 claimant is staged this run; attributed must be False.",
        )
        self.assertFalse(
            disposition.blocking,
            msg="Staging only the uncontested new record must not cause disposition.blocking to be True.",
        )

        # Secondary, behavioral, process-boundary confirmation.
        result = _run_uniqueness_script(self.root)
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A change set adding only an uncontested record, alongside "
                "an unattributed pre-existing collision, must not block the "
                f"commit. stdout={result.stdout} stderr={result.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
