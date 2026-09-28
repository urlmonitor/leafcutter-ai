"""
MODULE: unit_tests/commit_guardian/test_ge_122d_3.py
GOAL: RED test-first stubs fixing the commit-time half of GE-122d-3 — "A pass
    that could not see the whole collection never reports success". Today,
    an individual artifact within an otherwise-resolvable namespace that
    cannot be READ (permission denied) or cannot be PARSED (malformed YAML)
    is silently fail-open at the per-file level: it counts toward
    inspected_count but contributes no claim, and the namespace (and the
    whole collection) reports a clean PASS. This module pins the required
    behaviour change: such a namespace must report a distinguishable
    could-not-establish outcome, name the artifact it could not read, and
    block the commit.

THE DEFECT (reproduced directly against this branch before writing a single
    test below, via a throwaway probe script run against
    templates/scripts/commit_guardian/check_identifier_uniqueness.py):

        tree: docs/acceptance-criteria/fixture-component/{GE-9001-ok.yaml,
              GE-9002-malformed.yaml (genuinely unparsable YAML)}

        run_uniqueness_pass(root)
          overall passed = True
          acceptance-criteria  passed=True  inspected=2  findings=[]

    Same result (passed=True) when GE-9002 is chmod'd to 0o000 (unreadable)
    instead of malformed. Both conditions are silently swallowed by
    ``_read_yaml_id``'s existing per-file fail-open branch
    (``_uniqueness_scanners.py``): the file counts toward inspected_count but
    the whole namespace still reports clean, because ``_build_namespace_verdict``
    only ever looks at ``findings`` (contested numbers), never at whether
    every attempted read actually succeeded.

THE CONTRACT DECISION (this module's central design question, answered
    explicitly rather than picked implicitly -- the coder implements to these
    tests, matching the precedent already set by
    test_ge_122e_3_root_resolution.py's own "THE CONTRACT DECISION" for the
    sibling root-resolvability defect):

    GE-122e-3/H-1 already established that a namespace which could not be
    resolved AT ALL (missing root/config) reports
    ``NamespaceVerdict(passed=False, findings=[])`` -- and that shape ALREADY
    blocks unconditionally in ``_commit_disposition.compute_commit_disposition``
    (see its own "unresolvable_namespaces" contract) and is already reported
    by ``main()``'s ``_print_unresolvable_namespaces_summary``. This AC
    extends the SAME "the namespace could not be resolved" concept one level
    down: from "the root/config itself is unreadable" to "an artifact INSIDE
    an otherwise-resolved root is unreadable or unparsable" -- the walk did
    happen, but it did not see everything it was responsible for.

    Reusing ``passed=False, findings=[]`` alone is NOT sufficient here,
    though, because that shape carries no way to name WHICH artifact could
    not be read (AC-2) -- the existing unresolvable-root case has nothing to
    name (the root itself is the finding), but this AC's failure mode always
    has a specific artifact. This module therefore fixes a MINIMAL, ADDITIVE
    widening of ``NamespaceVerdict`` (Source-of-Truth Discipline Rule 5 --
    prefer the smaller, additive change; six downstream consumers read
    ``.passed`` / ``.inspected_count`` / ``.findings`` today and none of
    those three fields change meaning):

        NamespaceVerdict(
            passed: bool,                 # UNCHANGED meaning: False whenever
                                           # outcome != "clean".
            inspected_count: int,         # UNCHANGED meaning: every artifact
                                           # whose read was ATTEMPTED, tracked
                                           # during the walk, regardless of
                                           # whether that read succeeded.
            findings: list[Finding],      # UNCHANGED meaning: unchanged for
                                           # a "could_not_establish" outcome
                                           # (stays empty -- there is no
                                           # collision to name, only an
                                           # unreadable artifact).
            outcome: str = "clean",       # NEW, additive field. One of the
                                           # three sanctioned literal values
                                           # this module fixes below. This is
                                           # the "distinct VALUE in the
                                           # pass's return type" the ticket's
                                           # own it_requirements demand --
                                           # explicitly NOT a boolean, and
                                           # explicitly not derivable by
                                           # string-matching printed prose
                                           # (test 4 below pins this).
            unreadable_paths: list[str] = [],  # NEW, additive field. The
                                           # specific artifact path(s) this
                                           # namespace could not read or
                                           # parse -- non-empty iff
                                           # outcome == "could_not_establish".
                                           # This is what AC-2 ("names the
                                           # artifact") needs that the
                                           # existing unresolvable-root
                                           # shape cannot provide.
        )

    Sanctioned literal ``outcome`` values (fixed here, not re-derived by
    python-coder):
        "clean"               -- every artifact in the namespace was read
                                  successfully and no number is claimed
                                  twice.
        "contested"           -- every artifact was read successfully but at
                                  least one number is claimed by two or more
                                  of them (``findings`` non-empty).
        "could_not_establish" -- at least one artifact could not be read or
                                  parsed at all; uniqueness for this
                                  namespace was therefore never established,
                                  regardless of whether the artifacts that
                                  WERE read collided with each other.

    ``compute_commit_disposition`` must treat a ``could_not_establish``
    namespace exactly as it already treats an unresolvable-root namespace:
    BLOCKING regardless of the staged set, since an unread artifact is a
    property of the collection's own inspectability, not of the current
    diff (mirrors GE-122e-3/H-1's own reasoning verbatim).

WHY A SIBLING FILE, NOT test_ge_122e_3.py / test_ge_122e_3_root_resolution.py:
    those modules fix the ROOT/CONFIG-level resolvability contract (an entire
    namespace root or config file missing or unreadable). This module fixes
    a narrower, ARTIFACT-level contract (one file inside an otherwise-real,
    walkable root). The two are related (both widen what "the namespace
    could not be resolved" means) but are deliberately kept in separate
    files, matching this directory's own established precedent for
    per-bug-fix / per-AC test modules.

FIXTURE AUTHENTICITY: every well-formed fixture artifact (the "ok" AC YAML
    records) is produced via the REAL serializer (``yaml.safe_dump``) and
    read back by the code under test. The two deliberately-CORRUPT fixtures
    (a hand-typed unterminated YAML flow collection; a chmod 0o000 file) are
    the sanctioned exception to the Fixture Authenticity Rule: they exist
    specifically to simulate an artifact a real serializer could never
    produce, which is exactly the "unreadable/unparsable" condition under
    test, per this AC's own coverage note ("covered only by a test that
    creates the genuine unreadable or unparsable condition on disk").

PLATFORM CAVEAT (per this AC's own it_requirements): a mode-000 fixture
    behaves differently when tests run as root (some CI containers still
    permit the read) -- ``TestUnreadableFileYieldsCouldNotEstablishAtCommitTime``
    explicitly skips on non-POSIX platforms and when running as uid 0, rather
    than silently passing on a permission condition it never actually created.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3.yaml
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/scripts/commit_guardian/_uniqueness_scanners.py
  - templates/scripts/commit_guardian/_commit_disposition.py
  - unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py

DECISION HISTORY:
  - 2026-09-07 [test-writer/GE-122d-3]: Created. Confirmed RED empirically
    against this branch's real, unmodified
    templates/scripts/commit_guardian/check_identifier_uniqueness.py: a
    two-file acceptance-criteria namespace (one well-formed, one genuinely
    malformed) reports ``verdict.passed == True`` and
    ``namespaces["acceptance-criteria"].passed == True`` with
    ``inspected_count == 2`` -- the malformed record is silently fail-open.
    Identical result reproduced with a chmod 0o000 unreadable file in place
    of the malformed one.
"""

from __future__ import annotations

import importlib
import importlib.util as _ilu
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
# truth (ADR-001: template-is-canonical, .leafcutter/ is a build output),
# matching test_ge_122e_3_root_resolution.py's own convention exactly.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"

_NS_AC = "acceptance-criteria"

_OUTCOME_CLEAN = "clean"
_OUTCOME_CONTESTED = "contested"
_OUTCOME_COULD_NOT_ESTABLISH = "could_not_establish"

_MALFORMED_YAML_CONTENT = "id: [unterminated flow collection\n  more: stuff\n"


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
    """Insert templates/scripts/commit_guardian/ onto sys.path, once."""
    commit_guardian_dir = str(_COMMIT_GUARDIAN_DIR)
    if commit_guardian_dir not in sys.path:
        sys.path.insert(0, commit_guardian_dir)


def _load_scanners_module():
    """Import _uniqueness_scanners by its real top-level name.

    Returns:
        The loaded module, or None if the canonical file is missing.
    """
    scanners_path = _COMMIT_GUARDIAN_DIR / "_uniqueness_scanners.py"
    if not scanners_path.exists():
        return None
    _ensure_commit_guardian_on_sys_path()
    return importlib.import_module("_uniqueness_scanners")


_scanners = _load_scanners_module()


def _require_mod(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if check_identifier_uniqueness could not be loaded."""
    if _mod is None:
        test_case.fail(
            f"check_identifier_uniqueness.py not found at canonical path {_CANONICAL}. "
            "It should already exist from GE-122a-1 -- this would be a regression, not "
            "the expected state for this GE-122d-3 bug-fix module."
        )


def _require_scanners(test_case: unittest.TestCase) -> None:
    """Fail with a clear message if _uniqueness_scanners could not be loaded."""
    if _scanners is None:
        test_case.fail(f"_uniqueness_scanners.py not found under {_COMMIT_GUARDIAN_DIR}.")


# ---------------------------------------------------------------------------
# Fixture writers -- real serializer for well-formed records; the two
# deliberately-corrupt shapes are the Fixture Authenticity Rule's own
# sanctioned exception (see module docstring).
# ---------------------------------------------------------------------------


def _write_ac_yaml(path: Path, data: dict) -> None:
    """Write a well-formed AC YAML fixture using the REAL serializer.

    Args:
        path: Destination file path (parents created as needed).
        data: The AC record fields to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_malformed_yaml(path: Path) -> None:
    """Write a genuinely-unparsable YAML fixture (sanctioned corrupt exception).

    Args:
        path: Destination file path (parents created as needed).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_MALFORMED_YAML_CONTENT, encoding="utf-8")


def _build_minimal_resolvable_collection(root: Path) -> None:
    """Populate the three non-acceptance-criteria namespaces cleanly and
    resolvably, so a test isolating the acceptance-criteria namespace's
    could-not-establish behaviour is not confounded by an UNRELATED
    unresolvable namespace (decisions/diagrams/work-items) also failing.

    Args:
        root: Fixture collection root.
    """
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
    tickets_root = root / "tickets"
    tickets_root.mkdir(parents=True, exist_ok=True)
    (tickets_root / "ticket_lifecycle.json").write_text('{"folders": []}', encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests 1-2: the two ways an artifact can be "cannot read or cannot parse"
# per the AC's own Gherkin Given-clause -- malformed content, and a file the
# process is not permitted to open.
# ---------------------------------------------------------------------------


class TestUnparsableRecordYieldsCouldNotEstablishAtCommitTime(unittest.TestCase):
    """AC-1..AC-5: a genuinely malformed record on disk must yield the
    could-not-establish outcome, name the artifact, and block the commit --
    never a silent clean pass."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        self.ok_path = self.ac_dir / "GE-9001-ok.yaml"
        self.malformed_path = self.ac_dir / "GE-9002-malformed.yaml"
        _write_ac_yaml(self.ok_path, {"id": "GE-9001", "level": "L2", "title": "Fixture AC"})
        _write_malformed_yaml(self.malformed_path)
        _build_minimal_resolvable_collection(self.root)

    def test_unparsable_record_yields_could_not_establish_at_commit_time(self) -> None:
        # covers: GE-122d-3
        # angle: failure
        """A namespace holding one well-formed and one genuinely-malformed
        record must NOT report success (AC-1), must name the malformed
        artifact (AC-2), must report the could-not-establish outcome value
        distinct from clean (AC-3/AC-8), must report the number of artifacts
        it actually attempted to read (AC-4), and must block the commit
        regardless of what is staged (AC-5).

        FAILS TODAY: verdict.passed is True; the acceptance-criteria
        namespace reports passed=True with no way to name the malformed
        artifact at all.
        """
        verdict = _mod.run_uniqueness_pass(self.root)
        ns = verdict.namespaces[_NS_AC]

        self.assertFalse(
            verdict.passed,
            msg="A malformed record anywhere in the collection must not yield an overall passing verdict (AC-1).",
        )
        self.assertFalse(
            ns.passed,
            msg=f"The {_NS_AC!r} namespace must not report passed=True over a genuinely malformed record (AC-1).",
        )
        self.assertEqual(
            getattr(ns, "outcome", "<MISSING outcome ATTRIBUTE>"),
            _OUTCOME_COULD_NOT_ESTABLISH,
            msg=(
                "NamespaceVerdict must carry a new 'outcome' field distinguishing this "
                f"case from an ordinary clean pass (AC-3/AC-8); expected "
                f"{_OUTCOME_COULD_NOT_ESTABLISH!r}."
            ),
        )
        self.assertIn(
            str(self.malformed_path),
            list(getattr(ns, "unreadable_paths", [])),
            msg=(
                "NamespaceVerdict must carry a new 'unreadable_paths' field naming the "
                f"artifact that could not be read (AC-2): expected {self.malformed_path} "
                f"in the list, got {getattr(ns, 'unreadable_paths', '<MISSING>')!r}."
            ),
        )
        self.assertEqual(
            ns.inspected_count,
            2,
            msg=(
                "inspected_count must reflect BOTH attempted reads (the ok record and the "
                f"malformed one), got {ns.inspected_count} (AC-4)."
            ),
        )
        self.assertEqual(
            ns.findings,
            [],
            msg="A could-not-establish outcome from a single unparsable record is not a collision; findings must stay empty.",
        )

        disposition_nothing_staged = _mod.compute_commit_disposition(verdict, staged_paths=[])
        self.assertTrue(
            disposition_nothing_staged.blocking,
            msg=(
                "A could-not-establish namespace must block the commit REGARDLESS of the "
                f"staged set (AC-5), mirroring GE-122e-3/H-1's own unresolvable-root "
                f"contract. Got blocking={disposition_nothing_staged.blocking}."
            ),
        )
        disposition_unrelated_staged = _mod.compute_commit_disposition(
            verdict, staged_paths=[str(self.root / "README.md")]
        )
        self.assertTrue(
            disposition_unrelated_staged.blocking,
            msg="A could-not-establish namespace must block even when the staged set is entirely unrelated to it (AC-5).",
        )


class TestUnreadableFileYieldsCouldNotEstablishAtCommitTime(unittest.TestCase):
    """AC-1..AC-5, same disposition, for a genuinely unreadable (mode 0o000)
    file rather than a malformed one -- the second half of the AC's own
    Given-clause ('a record whose content is not well-formed, OR a file the
    process is not permitted to open')."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        self.ok_path = self.ac_dir / "GE-9001-ok.yaml"
        self.unreadable_path = self.ac_dir / "GE-9002-unreadable.yaml"
        _write_ac_yaml(self.ok_path, {"id": "GE-9001", "level": "L2", "title": "Fixture AC"})
        _write_ac_yaml(self.unreadable_path, {"id": "GE-9002", "level": "L2", "title": "Soon-unreadable"})
        _build_minimal_resolvable_collection(self.root)
        self._original_mode = self.unreadable_path.stat().st_mode
        self.unreadable_path.chmod(0)
        self.addCleanup(lambda: self.unreadable_path.chmod(self._original_mode | stat.S_IWUSR | stat.S_IRUSR))

    @unittest.skipIf(os.name != "posix", "permission bits are not meaningfully testable on this platform")
    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "running as root bypasses file permission checks; this test cannot simulate 'unreadable' under root "
        "and must not silently pass a permission condition it never actually created",
    )
    def test_unreadable_file_yields_could_not_establish_at_commit_time(self) -> None:
        # covers: GE-122d-3
        # angle: failure
        """A namespace holding one well-formed and one genuinely permission-
        denied record must not report success, must name the unreadable
        artifact, must report the could-not-establish outcome, must report
        the attempted-read count, and must block the commit.

        FAILS TODAY: verdict.passed is True; the unreadable file is silently
        fail-open with no way to name it.
        """
        verdict = _mod.run_uniqueness_pass(self.root)
        ns = verdict.namespaces[_NS_AC]

        self.assertFalse(verdict.passed, msg="A permission-denied record anywhere must not yield an overall pass.")
        self.assertFalse(ns.passed, msg=f"The {_NS_AC!r} namespace must not pass over an unreadable record.")
        self.assertEqual(
            getattr(ns, "outcome", "<MISSING outcome ATTRIBUTE>"),
            _OUTCOME_COULD_NOT_ESTABLISH,
            msg="An unreadable (permission-denied) record must yield the could_not_establish outcome.",
        )
        self.assertIn(
            str(self.unreadable_path),
            list(getattr(ns, "unreadable_paths", [])),
            msg=f"unreadable_paths must name {self.unreadable_path}, got {getattr(ns, 'unreadable_paths', '<MISSING>')!r}.",
        )
        self.assertEqual(ns.inspected_count, 2, msg="Both the ok and the unreadable record must count as attempted reads.")

        disposition = _mod.compute_commit_disposition(verdict, staged_paths=[])
        self.assertTrue(disposition.blocking, msg="An unreadable-file could-not-establish namespace must block the commit.")


# ---------------------------------------------------------------------------
# Test 3: the read count must be tracked during the walk, not derived from
# the successes -- the assertion is that the reported count DIFFERS from
# what a successes-only implementation would report, per this AC's own
# test_rationale ("written to fail on the most likely wrong implementation").
# ---------------------------------------------------------------------------


class TestDegradedOutcomeReportsTheAttemptedReadCount(unittest.TestCase):
    def setUp(self) -> None:
        _require_scanners(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_degraded_outcome_reports_the_attempted_read_count(self) -> None:
        # covers: GE-122d-3
        # angle: boundary
        """Three artifacts, two well-formed and one genuinely malformed: the
        reported inspected_count must equal 3 (every attempted read),
        which must DIFFER from 2 (the count of artifacts that actually
        parsed successfully) -- proving the count is tracked during the walk
        itself rather than derived afterwards from what parsed. An
        implementation that computes the count from successful parses would
        wrongly report 2 here, identical to what a genuinely clean two-file
        namespace reports, hiding the blind spot entirely.

        FAILS TODAY: this specific assertion (inspected_count != successful
        parse count) may coincidentally hold today only because
        inspected_count is ALREADY tracked during the walk for THIS
        dimension -- but the namespace's own outcome/pass signal still
        cannot express that a read failed at all (see the sibling tests
        above), which is what this AC as a whole is red for. This test locks
        the count dimension specifically so a future refactor cannot
        regress it while fixing the outcome dimension.
        """
        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        _write_ac_yaml(ac_dir / "GE-9001-ok.yaml", {"id": "GE-9001", "level": "L2", "title": "Fixture AC one"})
        _write_ac_yaml(ac_dir / "GE-9003-ok.yaml", {"id": "GE-9003", "level": "L2", "title": "Fixture AC two"})
        _write_malformed_yaml(ac_dir / "GE-9002-malformed.yaml")

        ns = _scanners.scan_acceptance_criteria(ac_dir)

        successful_parse_count = 2
        self.assertFalse(
            ns.passed,
            msg=(
                "A namespace whose read count and pass/fail disposition genuinely disagree "
                "must not still report passed=True just because the count dimension already "
                f"works -- got passed={ns.passed} with inspected_count={ns.inspected_count} "
                "over a tree holding one genuinely malformed record."
            ),
        )
        self.assertEqual(
            getattr(ns, "outcome", "<MISSING outcome ATTRIBUTE>"),
            _OUTCOME_COULD_NOT_ESTABLISH,
            msg="The same degraded tree used to pin the read count must also report the could_not_establish outcome.",
        )
        self.assertEqual(
            ns.inspected_count,
            3,
            msg=(
                f"inspected_count must count every ATTEMPTED read (3: two ok, one malformed), "
                f"got {ns.inspected_count}."
            ),
        )
        self.assertNotEqual(
            ns.inspected_count,
            successful_parse_count,
            msg=(
                "inspected_count must NOT equal the count of artifacts that successfully "
                "parsed (2) -- a count derived from successes alone is identical to what a "
                "genuinely clean two-file namespace would report, which is exactly the blind "
                "spot this AC's coverage note forbids."
            ),
        )


# ---------------------------------------------------------------------------
# Test 4: three-way machine-distinguishability of the outcome value alone,
# with no string matching and no reliance on the exit code (AC-8 / GE-119a-1).
# ---------------------------------------------------------------------------


class TestCouldNotEstablishIsDistinguishableWithoutParsingProse(unittest.TestCase):
    def setUp(self) -> None:
        _require_scanners(self)

    def _clean_namespace(self) -> tuple:
        with tempfile.TemporaryDirectory() as tmp:
            ac_dir = Path(tmp) / "docs" / "acceptance-criteria" / "fixture-component"
            _write_ac_yaml(ac_dir / "GE-9001-ok.yaml", {"id": "GE-9001", "level": "L2", "title": "Clean"})
            return _scanners.scan_acceptance_criteria(ac_dir)

    def _contested_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            ac_dir = Path(tmp) / "docs" / "acceptance-criteria" / "fixture-component"
            _write_ac_yaml(ac_dir / "GE-9004-a.yaml", {"id": "GE-9004", "level": "L2", "title": "Claimant A"})
            _write_ac_yaml(ac_dir / "GE-9004-b.yaml", {"id": "GE-9004", "level": "L2", "title": "Claimant B"})
            return _scanners.scan_acceptance_criteria(ac_dir)

    def _could_not_establish_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            ac_dir = Path(tmp) / "docs" / "acceptance-criteria" / "fixture-component"
            _write_ac_yaml(ac_dir / "GE-9005-ok.yaml", {"id": "GE-9005", "level": "L2", "title": "Fine"})
            _write_malformed_yaml(ac_dir / "GE-9006-malformed.yaml")
            return _scanners.scan_acceptance_criteria(ac_dir)

    def test_could_not_establish_is_distinguishable_without_parsing_prose(self) -> None:
        # covers: GE-122d-3
        # angle: criterion
        """A caller inspecting ONLY the 'outcome' field (no string matching
        against any printed message, no reliance on an exit code) must be
        able to tell clean, contested, and could-not-establish apart, and
        each must equal the exact sanctioned literal this module's contract
        fixes.

        FAILS TODAY: NamespaceVerdict has no 'outcome' field at all --
        getattr(..., 'outcome', '<MISSING outcome ATTRIBUTE>') returns the
        sentinel for all three fixtures, so none of the three equality
        assertions below can pass.
        """
        clean_ns = self._clean_namespace()
        contested_ns = self._contested_namespace()
        broken_ns = self._could_not_establish_namespace()

        clean_outcome = getattr(clean_ns, "outcome", "<MISSING outcome ATTRIBUTE>")
        contested_outcome = getattr(contested_ns, "outcome", "<MISSING outcome ATTRIBUTE>")
        broken_outcome = getattr(broken_ns, "outcome", "<MISSING outcome ATTRIBUTE>")

        self.assertEqual(clean_outcome, _OUTCOME_CLEAN, msg=f"A genuinely clean namespace must report outcome={_OUTCOME_CLEAN!r}.")
        self.assertEqual(
            contested_outcome, _OUTCOME_CONTESTED, msg=f"A genuine collision must report outcome={_OUTCOME_CONTESTED!r}."
        )
        self.assertEqual(
            broken_outcome,
            _OUTCOME_COULD_NOT_ESTABLISH,
            msg=f"An unparsable record must report outcome={_OUTCOME_COULD_NOT_ESTABLISH!r}.",
        )
        self.assertEqual(
            len({clean_outcome, contested_outcome, broken_outcome}),
            3,
            msg=(
                "All three outcomes must be pairwise distinct values a caller can switch on "
                f"directly: got {clean_outcome!r}, {contested_outcome!r}, {broken_outcome!r}."
            ),
        )


# ---------------------------------------------------------------------------
# Test 5 (reachability floor, BP-1100g-2): the AC's own test_spec authored no
# reachability descriptor. Resolved per the Reachability Entry-Point
# Resolution procedure -- Step 1, category 1 (CLI script): the unit under
# proof is check_identifier_uniqueness.py's own `main()`, guarded by
# `if __name__ == "__main__":`, invoked exactly as the commit-time
# pre-commit hook invokes it. Recorded verbatim in this ticket's sign-off
# completion_manifest.reachability_entry_point_answer.
# ---------------------------------------------------------------------------


class TestGe122d3ReachableFromEntryPoint(unittest.TestCase):
    """Invokes the REAL CLI entry point as a subprocess against a REAL git
    repository -- never a mock of git, never a direct call to main() -- and
    asserts the process both blocks (non-zero exit) and prints all three
    required statements to stderr."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _git(self, args: list, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)},
            timeout=60,
        )

    def test_ge_122d_3_reachable_from_entry_point(self) -> None:
        # covers: GE-122d-3
        # angle: reachability
        """REQUIRED reachability floor: run the real
        check_identifier_uniqueness.py CLI as a subprocess (never import
        the module and call a function directly) against a real git
        repository holding a genuinely malformed AC record, and assert the
        process both fails (non-zero exit -- AC-5) and names the malformed
        artifact and the read count in its stderr output (AC-2/AC-4).

        FAILS TODAY: the subprocess exits 0 and stderr contains no mention
        of the malformed artifact's filename at all.
        """
        self._git(["init", "-q"], self.root)
        self._git(["config", "user.email", "fixture@example.invalid"], self.root)
        self._git(["config", "user.name", "Fixture Author"], self.root)

        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        _write_ac_yaml(ac_dir / "GE-9001-ok.yaml", {"id": "GE-9001", "level": "L2", "title": "Fixture AC"})
        _write_malformed_yaml(ac_dir / "GE-9002-malformed.yaml")
        _build_minimal_resolvable_collection(self.root)
        (self.root / "README.md").write_text("Fixture repo for GE-122d-3 reachability.\n", encoding="utf-8")
        self._git(["add", "README.md"], self.root)

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
                "The real CLI must exit non-zero when a namespace holds an unparsable record "
                f"(AC-5). stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        self.assertIn(
            "GE-9002-malformed.yaml",
            result.stderr,
            msg=f"stderr must name the malformed artifact (AC-2). Got: {result.stderr!r}",
        )
        self.assertIn(
            "2 inspected",
            result.stderr,
            msg=f"stderr must state how many artifacts in the namespace were actually read (AC-4). Got: {result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
