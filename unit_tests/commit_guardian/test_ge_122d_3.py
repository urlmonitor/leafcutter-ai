"""
MODULE: unit_tests/commit_guardian/test_ge_122d_3.py
GOAL: RED test-first stubs for GE-122d-3 -- "A pass that could not see the
    whole collection never reports success". Pins the commit-time half of the
    three-stage contract (the shared-build half lives in
    unit_tests/build_guards/test_ge_122d_3.py; the authoring-time half lives
    in unit_tests/hooks/test_ge_122d_3.py).

THE GAP THIS AC CLOSES (distinct from GE-122e-3, already fixed): GE-122e-3
    covers a namespace ROOT/CONFIG being entirely missing or unreadable (a
    misconfiguration -- the root itself was never resolved). This AC covers a
    DIFFERENT, narrower failure: the namespace root DOES exist and IS being
    walked, but ONE ARTIFACT INSIDE IT cannot be read (OSError/PermissionError)
    or cannot be parsed (malformed content) -- see
    _uniqueness_scanners.py::_read_yaml_id's existing try/except blocks, which
    TODAY print a WARNING and fail OPEN at the file level: the file still
    counts toward inspected_count but contributes no claim, and the namespace
    can still report ``passed=True`` if no other file collides. That fail-open
    is exactly the shape GE-120a-1's sibling policy forbids ("a check that
    could not perform its inspection reports a degraded outcome, not a clean
    pass") -- reproduced directly against this branch before writing a single
    test below:

        # docs/acceptance-criteria/fixture-component/a.yaml -> {"id": "GE-1"}
        # docs/acceptance-criteria/fixture-component/b.yaml -> "id: [unterminated"
        # docs/acceptance-criteria/fixture-component/c.yaml -> {"id": "GE-2"}
        run_uniqueness_pass(root).namespaces["acceptance-criteria"]
          -> NamespaceVerdict(passed=True, inspected_count=3, findings=[])

    i.e. today a MALFORMED record in an otherwise-clean namespace is
    INDISTINGUISHABLE from a genuinely clean namespace of 3 files -- exactly
    the "pass that could not see the whole collection reports success" bug
    this AC exists to close. ``NamespaceVerdict`` has no field at all today
    that could carry "one artifact was unreadable"; ``passed`` is a plain
    bool, which the ticket's own Implementation Notes reject outright as the
    return shape ("A boolean return makes both criteria unsatisfiable").

THE CONTRACT DECISION (this module's central design question, answered
    explicitly rather than picked implicitly by whichever coder lands first --
    see test_ge_122e_3_root_resolution.py's own "THE CONTRACT DECISION" for
    the precedent this follows):

    1. ``NamespaceVerdict`` gains two ADDITIVE fields (both with defaults, so
       every existing call site across six downstream ACs -- GE-122a-1-i,
       GE-122c-1, GE-122c-2, GE-122d-1, GE-122d-3, GE-122e-3 -- is unaffected;
       per ADR-037's "additive-only" rule flagged by architect-review):

         outcome: str = "clean"            # one of the three module-level
                                            # constants below -- a DISTINCT
                                            # VALUE, never a bool, per this
                                            # ticket's own Implementation Notes
         unreadable_paths: list[str] = []  # the artifact(s) that could not be
                                            # read or parsed (see point 3)

       Exposed as three module-level string constants in ``_uniqueness_types``:
       ``OUTCOME_CLEAN = "clean"``, ``OUTCOME_CONTESTED = "contested"``,
       ``OUTCOME_COULD_NOT_ESTABLISH = "could_not_establish"``. ``passed``
       keeps its exact existing meaning (``True`` iff ``outcome ==
       OUTCOME_CLEAN``) so no existing consumer that only reads ``.passed``
       breaks; a NEW consumer that wants the three-way distinction reads
       ``.outcome`` instead of trying to reconstruct it from ``.passed`` +
       ``.findings`` (which is exactly what would force "parsing prose" --
       the AC's own AC-8 forbids that).

    2. A could-not-establish namespace reports ``passed=False`` (satisfies
       AC-1: "it does NOT report success") with an EMPTY ``findings`` list
       (there is no *contested number* to name -- ``Finding`` requires >= 2
       claimant paths for the SAME number, which is not this failure shape at
       all) and a NON-EMPTY ``unreadable_paths`` (satisfies AC-2: "names the
       artifact it could not read"). Because this is ``passed=False`` with
       empty ``findings``, it is already covered, with NO CHANGE REQUIRED to
       ``_commit_disposition.py``, by the EXISTING GE-122e-3/H-1 fix:
       ``unresolvable_namespaces = [ns for ns, v in ... if v.passed is False
       and not v.findings]`` already treats this shape as blocking regardless
       of the staged set. This is deliberately reused rather than duplicated:
       GE-122e-3's own fix already generalized "an empty-findings failure
       blocks unconditionally" one namespace-failure-shape wider than its own
       ticket needed, and this AC is the second, intended beneficiary of that
       generalization -- see ``TestUnreadableFileYieldsCouldNotEstablishAtCommitTime``
       and ``TestUnparsableRecordYieldsCouldNotEstablishAtCommitTime`` below,
       which assert ``disposition.blocking`` WITHOUT any change to that module.

    3. THE ABORT DECISION (the part that is not obvious, and is pinned here
       because ``test_degraded_outcome_reports_the_attempted_read_count``
       cannot pass without it): the per-artifact walk that backs
       ``scan_acceptance_criteria`` STOPS as soon as it hits an unreadable or
       unparsable artifact, rather than continuing fail-open through the rest
       of the directory (today's behaviour). Two things follow directly from
       this AC's own coverage note ("so the size of the blind spot is visible
       rather than implied") that a continue-past-the-failure design cannot
       satisfy:
         a. AC-4 requires the reported count to make "the size of the blind
            spot ... visible rather than implied". If the walk continued past
            the failure, ``inspected_count`` would equal the SAME total (N)
            whether or not any artifact failed -- there would be no visible
            difference between "read N cleanly" and "read N, one of them
            broken" for a caller who only sees the count. Aborting means the
            reported count is exactly "how far the walk got before it had to
            stop" -- the DIFFERENCE between that number and the namespace's
            true (unknowable-from-here) size IS the blind spot, made visible
            by comparison rather than asserted in prose.
         b. This is the literal, load-bearing content of this ticket's own
            Test Requirements entry for
            ``test_degraded_outcome_reports_the_attempted_read_count``: "that
            number differs from the clean-run count for the same tree". Over
            an IDENTICAL 3-file tree (only the middle file's content differs
            between the two runs), a continue-past-the-failure design reports
            inspected_count=3 in BOTH the clean and the degraded run --
            indistinguishable, which is precisely the defect this AC exists
            to close. Aborting at the first failure reports inspected_count=3
            (clean) vs inspected_count=2 (degraded, stops at the broken
            file) -- genuinely different numbers over the genuinely same
            tree, which is the only way the ticket's own phrasing can be
            literally true.
       Scope: this abort behaviour applies to ``scan_acceptance_criteria``
       (the only one of the four namespace walks that reads per-file CONTENT
       today -- ``_scan_filename_numbered``, backing ``scan_decisions`` /
       ``scan_diagrams``, only regex-matches a filename and never opens the
       file, so it has no "cannot read/parse" failure mode to abort on; that
       is flagged here, not silently generalized past what this AC's own
       fixtures exercise).

    4. ``main()``'s existing per-namespace report line
       (``"{ns}: FAILED ({count} inspected)"``) is extended, when
       ``ns_verdict.unreadable_paths`` is non-empty, to ALSO print: the
       unreadable artifact's path (AC-2), an explicit "uniqueness ... not
       established" statement (AC-3), and the read count (AC-4) -- see
       ``_assert_three_statements`` below for the exact substrings asserted;
       deliberately loose (substring, not exact-line) so python-coder retains
       wording latitude while the three REQUIRED pieces of information are
       still mechanically pinned.

WHY A SIBLING FILE, NOT AN EXTENSION OF test_ge_122e_3_root_resolution.py:
    that module's own docstring already states its scope is ROOT/CONFIG
    resolvability, explicitly distinct from "collision detection over a
    resolved root" -- this AC is a THIRD distinct concern (per-artifact
    failure inside an already-resolved root), so it gets its own file rather
    than growing either existing ~900-line module further, following the
    test_ge_122a_1_fast_path_equivalence.py / test_ge_122a_2_lifecycle_folder_paths.py
    / test_ge_122e_3_root_resolution.py precedent already established in this
    directory.

FIXTURE AUTHENTICITY: every non-corrupt fixture (AC YAML id, ADR/diagram
    markdown, ticket frontmatter, ticket_lifecycle.json) is produced via the
    real serializer (yaml.safe_dump / json.dump) and read back by the code
    under test -- never a hand-typed literal -- per this repo's Fixture
    Authenticity convention. The ONE deliberately-CORRUPT fixture (malformed
    YAML text) is the documented exception: it exists specifically to
    simulate a file a real serializer could never produce, which is exactly
    the "unparsable" half of this AC's own coverage note.

PLATFORM NOTE (unreadable-file test): mode-000 permission tests behave
    differently when the test runs as root (some CI containers still permit
    the read) -- per this ticket's own Implementation Notes, that test skips
    explicitly with a stated reason on such platforms rather than silently
    passing, mirroring the existing precedent in
    test_ge_122e_3_root_resolution.py::TestPerNamespaceRootOrConfigAbsentOrUnreadable.

DECISION HISTORY
- 2026-09-01 [GE-122d-3/test-writer]: Initial authoring of all tests pinning
  the per-artifact could-not-establish contract. Reproduced the current
  fail-open defect directly against this branch before writing a single test
  (see this module's docstring above and the test-writer sign-off comment's
  red_baseline block for the exact captured output).
"""

from __future__ import annotations

import importlib
import importlib.util as _ilu
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Canonical paths -- templates/scripts/commit_guardian/ is the source of
# truth (ADR-001: template-is-canonical, .leafcutter/ is a build output).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"

_NS_AC = "acceptance-criteria"

# THE CONTRACT DECISION's three outcome-value constants, as this module
# expects them to be exposed by _uniqueness_types.py. Read defensively via
# getattr elsewhere so an import that succeeds but has not yet added these
# names still produces a clear AttributeError rather than a NameError here.
_OUTCOME_CLEAN = "clean"
_OUTCOME_CONTESTED = "contested"
_OUTCOME_COULD_NOT_ESTABLISH = "could_not_establish"


def _load_check_identifier_uniqueness():
    """Dynamically import check_identifier_uniqueness from its canonical path.

    Returns:
        The loaded module, or None if the canonical file is missing (would be
        a regression -- the module already exists as of GE-122a-1).
    """
    if not _CANONICAL.exists():
        return None
    spec = _ilu.spec_from_file_location("check_identifier_uniqueness", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_identifier_uniqueness"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_check_identifier_uniqueness()


def _ensure_commit_guardian_on_sys_path() -> None:
    commit_guardian_dir = str(_COMMIT_GUARDIAN_DIR)
    if commit_guardian_dir not in sys.path:
        sys.path.insert(0, commit_guardian_dir)


def _load_uniqueness_types_module():
    """Import _uniqueness_types by its real top-level name.

    Returns:
        The loaded module, or None if the canonical file is missing.
    """
    types_path = _COMMIT_GUARDIAN_DIR / "_uniqueness_types.py"
    if not types_path.exists():
        return None
    _ensure_commit_guardian_on_sys_path()
    return importlib.import_module("_uniqueness_types")


_types_mod = _load_uniqueness_types_module()


def _require_mod(test_case: unittest.TestCase) -> None:
    if _mod is None:
        test_case.fail(
            f"check_identifier_uniqueness.py not found at canonical path {_CANONICAL}. "
            "It should already exist from GE-122a-1/GE-122a-2 -- this would be a "
            "regression, not the expected state for this GE-122d-3 module."
        )


def _require_types_mod(test_case: unittest.TestCase) -> None:
    if _types_mod is None:
        test_case.fail(
            f"_uniqueness_types.py not found under {_COMMIT_GUARDIAN_DIR}. It should "
            "already exist from GE-122a-1 -- this would be a regression."
        )


# ---------------------------------------------------------------------------
# Fixture writers -- real serializers only (Fixture Authenticity Rule). The
# one deliberately-corrupt writer (_write_malformed_yaml) is the documented
# exception: a real serializer cannot produce broken YAML by definition.
# ---------------------------------------------------------------------------


def _write_ac_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_malformed_yaml(path: Path) -> None:
    """Write deliberately-corrupt YAML: an unterminated flow sequence.

    Not produced by yaml.safe_dump by definition -- this is the documented
    Fixture Authenticity exception for a condition a real serializer can
    never produce (see this module's own docstring).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("id: [unterminated flow sequence\nlevel: L2\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_ticket(path: Path, *, status: str, title: str = "Fixture ticket") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump({"status": status, "title": title}, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n# {title}\n\nFixture ticket body.\n"
    path.write_text(content, encoding="utf-8")


def _write_lifecycle_config(path: Path, folders: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"folders": folders}, fh)
    return path


def _populate_other_three_namespaces_cleanly(root: Path) -> None:
    """Populate decisions/diagrams/work-items cleanly so only the
    acceptance-criteria namespace under test can fail, isolating the signal.
    """
    _write_text(root / "docs" / "architecture" / "adrs" / "ADR-9001-fixture.md", "# ADR-9001 Fixture\n\nStatus: accepted\n")
    _write_text(root / "docs" / "architecture" / "diagrams" / "c2-9001-fixture.md", "# c2-9001 Fixture\n")
    _write_lifecycle_config(root / "tickets" / "ticket_lifecycle.json", [{"path": "tickets/00_inbox"}])
    _write_ticket(root / "tickets" / "00_inbox" / "TICKET-90010101-Fixture.md", status="todo")


def _git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)},
        timeout=60,
    )


def _init_git_repo(root: Path) -> None:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "fixture@example.invalid"], root)
    _git(["config", "user.name", "Fixture Author"], root)


def _assert_three_statements(test_case: unittest.TestCase, stderr: str, *, artifact_path: str, read_count: int) -> None:
    """AC-2 + AC-3 + AC-4: assert the three required statements are present.

    Deliberately substring-based (not an exact-line match) so python-coder
    keeps wording latitude while the three REQUIRED pieces of information --
    which artifact, that uniqueness was not established, and how many were
    read -- are still mechanically pinned, per this AC's own coverage note.
    """
    test_case.assertIn(
        artifact_path,
        stderr,
        msg=f"AC-2: output must name the artifact it could not read. Got stderr={stderr!r}",
    )
    test_case.assertIn(
        "not established",
        stderr.lower(),
        msg=f"AC-3: output must state uniqueness was not established for the namespace. Got stderr={stderr!r}",
    )
    test_case.assertIn(
        str(read_count),
        stderr,
        msg=f"AC-4: output must state how many artifacts it did read ({read_count}). Got stderr={stderr!r}",
    )


# ---------------------------------------------------------------------------
# Unparsable record -> could-not-establish at commit time.
# ---------------------------------------------------------------------------


class TestUnparsableRecordYieldsCouldNotEstablishAtCommitTime(unittest.TestCase):
    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_unparsable_record_yields_could_not_establish_at_commit_time(self):
        # covers: GE-122d-3
        # angle: criterion
        """AC-1/AC-2/AC-3/AC-4/AC-5/AC-8: a genuinely malformed record on disk
        in a namespace the pass owns yields the could-not-establish outcome,
        names the artifact, states uniqueness was not established, states the
        read count, and blocks the real commit-time entry point.

        FAILS TODAY: NamespaceVerdict has no `.outcome` field at all (a plain
        bool `.passed`), and the malformed record fail-opens silently --
        `run_uniqueness_pass` reports `passed=True` over this exact fixture
        (reproduced verbatim in this module's own docstring).
        """
        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        clean_a = ac_dir / "a-clean.yaml"
        broken_b = ac_dir / "b-broken.yaml"
        clean_c = ac_dir / "c-clean.yaml"
        _write_ac_yaml(clean_a, {"id": "GE-9101", "level": "L2", "title": "Clean A"})
        _write_malformed_yaml(broken_b)
        _write_ac_yaml(clean_c, {"id": "GE-9102", "level": "L2", "title": "Clean C"})
        _populate_other_three_namespaces_cleanly(self.root)

        verdict = _mod.run_uniqueness_pass(self.root)
        ns = verdict.namespaces[_NS_AC]

        self.assertFalse(verdict.passed, msg="AC-1: the whole-collection verdict must not report success.")
        self.assertFalse(ns.passed, msg="AC-1: the acceptance-criteria namespace must not report success.")
        self.assertEqual(
            getattr(ns, "outcome", None),
            _OUTCOME_COULD_NOT_ESTABLISH,
            msg=f"AC-8: outcome must be the distinct could_not_establish value, got {getattr(ns, 'outcome', None)!r}.",
        )
        self.assertIn(
            str(broken_b),
            [str(p) for p in getattr(ns, "unreadable_paths", [])],
            msg="AC-2: the unreadable/unparsable artifact must be named in unreadable_paths.",
        )

        # Commit-time stage: real subprocess entry point, nothing staged --
        # per THE CONTRACT DECISION, this must block regardless of the
        # staged set, mirroring GE-122e-3/H-1's unresolvable_namespaces
        # precedent (which this AC's shape already satisfies with no change
        # to _commit_disposition.py).
        _init_git_repo(self.root)
        (self.root / "README.md").write_text("Fixture repo for GE-122d-3.\n", encoding="utf-8")
        _git(["add", "README.md"], self.root)

        result = subprocess.run(
            [sys.executable, str(_CANONICAL)],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(self.root)},
            timeout=60,
        )

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"AC-5: the commit must not complete. stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        _assert_three_statements(self, result.stderr, artifact_path=str(broken_b), read_count=ns.inspected_count)


# ---------------------------------------------------------------------------
# Unreadable file -> could-not-establish at commit time.
# ---------------------------------------------------------------------------


class TestUnreadableFileYieldsCouldNotEstablishAtCommitTime(unittest.TestCase):
    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    @unittest.skipIf(os.name != "posix", "permission bits are not meaningfully testable on this platform")
    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "running as root bypasses file permission checks; this test cannot simulate 'unreadable' under root",
    )
    def test_unreadable_file_yields_could_not_establish_at_commit_time(self):
        # covers: GE-122d-3
        # angle: criterion
        """AC-1/AC-2/AC-3/AC-4/AC-5: a genuinely unreadable file (mode 000)
        yields the identical could-not-establish disposition as the
        unparsable-content case. Platform assumption stated explicitly via
        the skipIf decorators above (per this ticket's own Implementation
        Notes) rather than silently passing where the condition cannot be
        created.

        FAILS TODAY: same fail-open defect as the malformed-content sibling
        test above -- an unreadable file is caught by _read_yaml_id's
        OSError branch, logs a WARNING, and still lets the namespace report
        passed=True if nothing else collides.
        """
        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        clean_a = ac_dir / "a-clean.yaml"
        unreadable_b = ac_dir / "b-unreadable.yaml"
        clean_c = ac_dir / "c-clean.yaml"
        _write_ac_yaml(clean_a, {"id": "GE-9201", "level": "L2", "title": "Clean A"})
        _write_ac_yaml(unreadable_b, {"id": "GE-9202", "level": "L2", "title": "Will be unreadable"})
        _write_ac_yaml(clean_c, {"id": "GE-9203", "level": "L2", "title": "Clean C"})
        _populate_other_three_namespaces_cleanly(self.root)

        _init_git_repo(self.root)
        (self.root / "README.md").write_text("Fixture repo for GE-122d-3.\n", encoding="utf-8")
        _git(["add", "-A"], self.root)

        original_mode = unreadable_b.stat().st_mode
        unreadable_b.chmod(0)
        try:
            verdict = _mod.run_uniqueness_pass(self.root)
            ns = verdict.namespaces[_NS_AC]

            self.assertFalse(verdict.passed, msg="AC-1: the whole-collection verdict must not report success.")
            self.assertEqual(
                getattr(ns, "outcome", None),
                _OUTCOME_COULD_NOT_ESTABLISH,
                msg=f"AC-8: outcome must be could_not_establish, got {getattr(ns, 'outcome', None)!r}.",
            )
            self.assertIn(
                str(unreadable_b),
                [str(p) for p in getattr(ns, "unreadable_paths", [])],
                msg="AC-2: the unreadable artifact must be named.",
            )

            result = subprocess.run(
                [sys.executable, str(_CANONICAL)],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(self.root)},
                timeout=60,
            )
            self.assertNotEqual(
                0,
                result.returncode,
                msg=f"AC-5: the commit must not complete. stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            _assert_three_statements(self, result.stderr, artifact_path=str(unreadable_b), read_count=ns.inspected_count)
        finally:
            unreadable_b.chmod(original_mode | stat.S_IWUSR | stat.S_IRUSR)


# ---------------------------------------------------------------------------
# Degraded read count -- the abort-on-first-failure contract decision.
# ---------------------------------------------------------------------------


class TestDegradedOutcomeReportsTheAttemptedReadCount(unittest.TestCase):
    def setUp(self) -> None:
        _require_mod(self)

    def _build_three_file_namespace(self, root: Path, *, middle_is_broken: bool) -> None:
        ac_dir = root / "docs" / "acceptance-criteria" / "fixture-component"
        _write_ac_yaml(ac_dir / "a-first.yaml", {"id": "GE-9301", "level": "L2", "title": "First"})
        if middle_is_broken:
            _write_malformed_yaml(ac_dir / "b-second.yaml")
        else:
            _write_ac_yaml(ac_dir / "b-second.yaml", {"id": "GE-9302", "level": "L2", "title": "Second"})
        _write_ac_yaml(ac_dir / "c-third.yaml", {"id": "GE-9303", "level": "L2", "title": "Third"})

    def test_degraded_outcome_reports_the_attempted_read_count(self):
        # covers: GE-122d-3
        # angle: boundary
        """AC-4: the degraded result's read count differs from the clean-run
        count over the SAME 3-file tree (only the middle file's content
        differs between the two runs) -- proving the count is tracked live
        during the walk (and the walk stops at the first could-not-establish
        artifact, per THE CONTRACT DECISION above) rather than derived
        afterward from what successfully parsed. Without the abort, both
        runs would report inspected_count=3 -- indistinguishable, which is
        the exact defect this AC exists to close.

        FAILS TODAY: `scan_acceptance_criteria` never aborts; both the clean
        and degraded runs report inspected_count=3 over this identical
        3-file tree.
        """
        with tempfile.TemporaryDirectory() as clean_dir, tempfile.TemporaryDirectory() as degraded_dir:
            clean_root = Path(clean_dir)
            degraded_root = Path(degraded_dir)
            self._build_three_file_namespace(clean_root, middle_is_broken=False)
            self._build_three_file_namespace(degraded_root, middle_is_broken=True)

            clean_verdict = _mod.run_uniqueness_pass(clean_root)
            degraded_verdict = _mod.run_uniqueness_pass(degraded_root)

            clean_ns = clean_verdict.namespaces[_NS_AC]
            degraded_ns = degraded_verdict.namespaces[_NS_AC]

            self.assertTrue(clean_ns.passed, msg="fixture sanity: the all-valid tree must pass cleanly.")
            self.assertEqual(clean_ns.inspected_count, 3, msg="fixture sanity: the clean tree has exactly 3 files.")

            self.assertFalse(degraded_ns.passed, msg="the tree with one broken file must not report success.")
            self.assertEqual(
                getattr(degraded_ns, "outcome", None),
                _OUTCOME_COULD_NOT_ESTABLISH,
                msg=f"outcome must be could_not_establish, got {getattr(degraded_ns, 'outcome', None)!r}.",
            )
            self.assertNotEqual(
                clean_ns.inspected_count,
                degraded_ns.inspected_count,
                msg=(
                    "The degraded run's read count must differ from the clean-run count over "
                    f"the SAME tree shape. Got clean={clean_ns.inspected_count}, "
                    f"degraded={degraded_ns.inspected_count} -- if these are equal, the read count "
                    "was derived from something other than a live, aborting walk, and the blind "
                    "spot this AC requires to be visible is invisible again."
                ),
            )
            self.assertLess(
                degraded_ns.inspected_count,
                clean_ns.inspected_count,
                msg="The degraded run must have read STRICTLY FEWER artifacts than the clean run (it stopped early).",
            )


# ---------------------------------------------------------------------------
# Distinguishable without parsing prose.
# ---------------------------------------------------------------------------


class TestCouldNotEstablishIsDistinguishableWithoutParsingProse(unittest.TestCase):
    def setUp(self) -> None:
        _require_types_mod(self)

    def test_could_not_establish_is_distinguishable_without_parsing_prose(self):
        # covers: GE-122d-3
        # angle: criterion
        """AC-8: a caller can tell could-not-establish apart from clean AND
        from contested by inspecting `.outcome` alone -- no string matching,
        no reliance on the exit code. Built directly from the dataclass
        constructor (no filesystem I/O) since this is a pure type-contract
        assertion, not a behavioral one.

        FAILS TODAY: `NamespaceVerdict` accepts no `outcome` keyword argument
        at all (TypeError: unexpected keyword argument 'outcome') -- there is
        no third value to distinguish anything with.
        """
        Finding = _types_mod.Finding
        NamespaceVerdict = _types_mod.NamespaceVerdict

        clean_ns = NamespaceVerdict(passed=True, inspected_count=3, findings=[], outcome=_OUTCOME_CLEAN)
        contested_ns = NamespaceVerdict(
            passed=False,
            inspected_count=2,
            findings=[Finding(number="GE-1", paths=["a.yaml", "b.yaml"])],
            outcome=_OUTCOME_CONTESTED,
        )
        could_not_establish_ns = NamespaceVerdict(
            passed=False,
            inspected_count=1,
            findings=[],
            outcome=_OUTCOME_COULD_NOT_ESTABLISH,
            unreadable_paths=["broken.yaml"],
        )

        outcomes = {clean_ns.outcome, contested_ns.outcome, could_not_establish_ns.outcome}
        self.assertEqual(
            len(outcomes),
            3,
            msg=f"All three outcomes must be pairwise distinct values, got {outcomes!r}.",
        )
        # The sharp case this AC is written for: contested and
        # could-not-establish are BOTH passed=False, and must still be
        # told apart WITHOUT reading .findings length or any prose --
        # .outcome alone must suffice.
        self.assertEqual(contested_ns.passed, could_not_establish_ns.passed)
        self.assertNotEqual(
            contested_ns.outcome,
            could_not_establish_ns.outcome,
            msg="contested and could_not_establish share passed=False; .outcome must still tell them apart.",
        )
        self.assertEqual(could_not_establish_ns.outcome, _OUTCOME_COULD_NOT_ESTABLISH)


# ---------------------------------------------------------------------------
# Reachability: the real CLI entry point, invoked as a subprocess.
# ---------------------------------------------------------------------------


class TestGe122d3ReachableFromEntryPoint(unittest.TestCase):
    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_ge_122d_3_reachable_from_entry_point(self):
        # covers: GE-122d-3
        # angle: reachability
        """REQUIRED reachability test: invokes check_identifier_uniqueness.py
        as a real subprocess (the CLI entry point a pre-commit hook actually
        invokes) against a fixture repository holding a malformed record, and
        asserts the new could-not-establish behaviour is actually observed at
        that boundary -- never by importing run_uniqueness_pass and calling
        it directly.

        FAILS TODAY: exit code 0; stderr prints only the pre-existing
        "acceptance-criteria: OK (3 inspected)" line (the malformed record
        fails open silently), never the could-not-establish disposition this
        AC requires.
        """
        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        broken = ac_dir / "broken.yaml"
        _write_ac_yaml(ac_dir / "clean.yaml", {"id": "GE-9401", "level": "L2", "title": "Clean"})
        _write_malformed_yaml(broken)
        _populate_other_three_namespaces_cleanly(self.root)

        _init_git_repo(self.root)
        (self.root / "README.md").write_text("Fixture repo for GE-122d-3 reachability.\n", encoding="utf-8")
        _git(["add", "README.md"], self.root)

        result = subprocess.run(
            [sys.executable, str(_CANONICAL)],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(self.root)},
            timeout=60,
        )

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The real CLI entry point must exit non-zero when a namespace it owns holds a "
                f"malformed record. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        self.assertIn(
            str(broken),
            result.stderr,
            msg=f"The CLI's own stderr must name the artifact it could not read. Got: {result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
