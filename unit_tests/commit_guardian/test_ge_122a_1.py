"""
MODULE: unit_tests/commit_guardian/test_ge_122a_1.py
GOAL: RED test-first stubs for GE-122a-1 -- "A whole-collection pass reports
    every number claimed by two artifacts". The module under test,
    templates/scripts/commit_guardian/check_identifier_uniqueness.py, does
    NOT exist yet. python-coder builds it to satisfy the contract asserted
    below.
BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml
    and
    tickets/00_inbox/epics/EPIC-GE122UniquenessPassAndRepair/01_TICKET-20260818-GE-122a-1.md.
    Three whole-collection detectors already exist in this repo
    (check_adr_collision.py, check_ticket_state_integrity.py,
    check_ticket_no_branch_move.py) and are registered NOWHERE, so none has
    ever run -- the exact "built, tested green, wired into nothing" trap this
    epic's Master_Plan.md names as the most likely failure mode. Every test
    below therefore EXECUTES the pass over a real on-disk fixture collection
    (never mocks the walk or the parse) and, for the registration test, drives
    the hook through an ACTUAL git-staged commit scenario -- never a grep of
    commit_guardian.json for a string.

CONTRACT UNDER TEST (fixed here because the production module does not exist
yet; this is the explicit target python-coder must satisfy -- see the
ticket's Implementation Notes, "verdict object MUST carry, per namespace: an
outcome value, every contested number with EVERY claimant path for that
number, and the count of artifacts inspected"):

    import check_identifier_uniqueness as mod
    verdict = mod.run_uniqueness_pass(collection_root)

    verdict.passed                     -> bool, True iff every namespace passed
    verdict.namespaces                 -> dict[str, <NamespaceVerdict>], keyed
                                           by namespace name. This module fixes
                                           the three namespace names below --
                                           the fourth (work-items) belongs to
                                           the sibling AC GE-122a-2 and is out
                                           of scope here.
    namespace_verdict.passed           -> bool
    namespace_verdict.inspected_count  -> int, count of artifacts the pass
                                           walked in that namespace
    namespace_verdict.findings         -> list[<Finding>], one entry PER
                                           CONTESTED NUMBER -- never one entry
                                           per claimant file
    finding.number                     -> str, the contested identifier/number
                                           (e.g. "GE-119", "029", "c2-003")
    finding.paths                      -> list[str], EVERY claimant path for
                                           that number (>= 2 entries)

    Namespace names fixed by this module's fixtures:
        "acceptance-criteria", "decisions", "diagrams"

Any correct implementation may choose its own internal shape as long as
`run_uniqueness_pass` returns an object satisfying the attribute access above
-- these tests do not care whether it is a dataclass, a namedtuple, or a
plain object; they never introspect internals beyond the documented surface.

ARCHITECTURE / EXERCISE STRATEGY:
  - Behavioral tests (1-4) load templates/scripts/commit_guardian/
    check_identifier_uniqueness.py by FILE PATH via importlib (the module is
    not on sys.path as an installed package -- this follows the same
    dynamic-import convention already used by
    unit_tests/commit_guardian/test_check_hook_parity.py in this directory).
    Each builds a REAL on-disk fixture collection under a tempdir -- three
    namespace subtrees mirroring the real store's own directory shapes
    (docs/acceptance-criteria/<component>/<goal-folder>/*.yaml with a
    parentless sibling at the namespace root; docs/architecture/adrs/
    ADR-<NNN>-*.md; docs/architecture/diagrams/c2-<NNN>-*.md) -- and calls
    the real entry point against it. AC-format fixtures are produced with
    yaml.safe_dump (per docs/reference/fixture-policy.md's Fixture
    Authenticity Rule); a hand-typed YAML literal is explicitly rejected by
    that policy because it reproduces the author's indentation bias rather
    than the real serializer's column-0 output -- the exact defect class
    that hid the files_touched parser bug in EPIC-PhantomDoneFilesTouched.
  - test_pass_runs_from_the_deployed_layout and
    test_decision_namespace_gate_is_registered_and_executes are integration
    tests that shell out to the REAL scripts/build.py against a scratch
    target directory and then invoke the DEPLOYED copy in a subprocess --
    never the source-tree import -- because a source-tree unit test cannot
    structurally observe a ModuleNotFoundError caused by an undeployed
    dependency (CLAUDE.md, "New Hook / Gate Dependencies Must Be in the
    Build Deploy-Manifest"), nor can it observe a hook silently vanishing
    from a build-regenerated .pre-commit-config.yaml.
  - No test baselines against a git ref (origin/main, main, or a hardcoded
    SHA). Fixtures use their own `git init`-ed scratch directories, per the
    caution against exactly that mistake on PR #462.

DECISION HISTORY
- 2026-08-18 [GE-122a-1/test-writer]: Initial authoring of all six RED test
  stubs. Verified RED via `python -m unittest discover`: all six fail with
  AssertionError from `_require_mod` / explicit manifest-lookup assertions
  because templates/scripts/commit_guardian/check_identifier_uniqueness.py
  does not exist yet and the decision-namespace hook is registered nowhere
  (see the test-writer sign-off comment for the exact captured output).
- 2026-08-18 [GE-122a-1/test-writer, performance regression]: Added
  TestUniquenessPassPerformanceBudget per pr-reviewer's finding that
  run_uniqueness_pass('.') measured 10.2-11.4s over three runs against this
  repo's real collection (3092 AC yaml, 35 decisions, 24 diagrams, 289 work
  items) -- over 2x the ticket's own <5s Implementation Notes budget, and
  isolated to scan_acceptance_criteria's per-file yaml.safe_load. No prior
  test in this file asserted on wall-clock time, which is exactly why the
  regression was invisible to a fully green suite. Verified RED: see the
  test-writer sign-off comment for the measured elapsed time.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import subprocess
import sys
import tempfile
import time
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
_CANONICAL_MANIFEST = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"

_SUBPROCESS_TIMEOUT_SECONDS = 60
_CLEAN_ENV_TEMPLATE = {"PATH": "/usr/bin:/bin:/usr/local/bin"}

# Namespace names this fixture collection uses -- fixed by the contract
# documented in the module docstring.
_NS_AC = "acceptance-criteria"
_NS_DECISIONS = "decisions"
_NS_DIAGRAMS = "diagrams"
_NS_WORK_ITEMS = "work-items"

# Performance regression guard constants -- see
# TestUniquenessPassPerformanceBudget below. Sized to roughly this repo's
# own real collection as measured directly by a pr-reviewer pass (3092 AC
# yaml, 35 decisions, 24 diagrams, 289 work items), rounded to clean counts.
_PERF_AC_COUNT = 3000
_PERF_DECISION_COUNT = 35
_PERF_DIAGRAM_COUNT = 24
_PERF_WORK_ITEM_COUNT = 289
_PERF_WORK_ITEM_FOLDERS = ("00_inbox", "01_todo", "99_done")
_PERF_WALLCLOCK_CEILING_SECONDS = 8.0

# A representative Gherkin criteria block, repeated to approximate this
# repo's own real AC record size (measured average 2677 bytes/file across
# 3092 on-disk records -- a trivial 3-key flat dict does NOT reproduce the
# regression: yaml.safe_load's per-file cost scales with content size, not
# merely file count, so an unrealistically tiny fixture record would leave
# this test falsely green against the real defect).
_PERF_CRITERIA_BLOCK = (
    "Given a staged artifact that exercises a representative Gherkin scenario\n"
    "And the record body contains a realistic number of clauses similar to a\n"
    "  real on-disk acceptance-criteria record in this store\n"
    "When the whole-collection uniqueness pass reads and parses the file\n"
    "Then the per-file parse cost is comparable to a real AC record's cost\n"
    "And the fixture is not an unrealistically tiny flat dict\n"
    "And this multi-line block approximates real criteria length.\n"
) * 5


def _load_module():
    """Dynamically import check_identifier_uniqueness from its canonical path.

    Returns:
        The loaded module, or None if the canonical file does not exist yet
        (the expected RED state before python-coder implements this ticket).
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
            f"{_CANONICAL}. Ensure python-coder has implemented this ticket."
        )


# ---------------------------------------------------------------------------
# Fixture collection builder
# ---------------------------------------------------------------------------


def _write_ac_yaml(path: Path, data: dict) -> None:
    """Write an AC YAML fixture using the REAL serializer (yaml.safe_dump).

    Per docs/reference/fixture-policy.md, a hand-typed YAML string is
    rejected as a fixture for a serialized format: it reproduces the
    author's indentation model rather than PyYAML's actual column-0 output,
    which is the exact bias that hid the files_touched parser defect in
    EPIC-PhantomDoneFilesTouched. This helper always round-trips: it writes
    with yaml.safe_dump and the caller re-reads from disk via the module
    under test, never from an in-memory literal.

    Args:
        path: Destination file path (parents created as needed).
        data: The AC record fields to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_text(path: Path, content: str) -> None:
    """Write a plain-text fixture artifact (decision record / diagram doc).

    Args:
        path: Destination file path (parents created as needed).
        content: File content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_fixture_collection(root: Path, *, contested: bool) -> None:
    """Build a real on-disk collection fixture across three namespaces.

    Mirrors the real store's own directory shapes:
      - docs/acceptance-criteria/<component>/<goal-folder>/*.yaml for a
        goal-level record owning a folder of children, plus parentless
        detail-level records sitting directly at the namespace root.
      - docs/architecture/adrs/ADR-<NNN>-<slug>.md for decision records.
      - docs/architecture/diagrams/c2-<NNN>-<slug>.md for diagrams.

    When contested=True, three collisions are planted (matching the AC's
    Gherkin verbatim): two AC records both declaring id "GE-119" (one
    goal-level owning a folder of children, one parentless detail-level at
    the namespace root), two decision records both claiming integer 029,
    and two diagrams both claiming "c2-003". When contested=False, each of
    the three collisions is resolved by renumbering ONE claimant, while
    keeping the total artifact count per namespace identical -- so a
    before/after count comparison is meaningful.

    A further batch of uncontested artifacts is added to each namespace so
    that "no artifact whose number is claimed once appears in the report"
    is a real assertion, not a vacuous one over an all-contested fixture.

    Args:
        root: Tempdir root to build the fixture collection under.
        contested: Whether to plant the three collisions or their repair.
    """
    ac_root = root / "docs" / "acceptance-criteria" / "fixture-component"
    adr_root = root / "docs" / "architecture" / "adrs"
    diagram_root = root / "docs" / "architecture" / "diagrams"

    # --- acceptance-criteria namespace ---
    _write_ac_yaml(
        ac_root / "GE-119-collision-goal" / "GE-119.yaml",
        {"id": "GE-119", "level": "L0", "title": "Goal-level record owning children"},
    )
    _write_ac_yaml(
        ac_root / "GE-119-collision-goal" / "GE-119a-1.yaml",
        {"id": "GE-119a-1", "level": "L2", "title": "Child one"},
    )
    _write_ac_yaml(
        ac_root / "GE-119-collision-goal" / "GE-119a-2.yaml",
        {"id": "GE-119a-2", "level": "L2", "title": "Child two"},
    )
    detail_id = "GE-119" if contested else "GE-500"
    _write_ac_yaml(
        ac_root / "GE-119-detail.yaml",
        {"id": detail_id, "level": "L2", "title": "Parentless detail-level record"},
    )
    for i in range(1, 21):
        _write_ac_yaml(
            ac_root / f"GE-{800 + i}-standalone.yaml",
            {"id": f"GE-{800 + i}", "level": "L2", "title": f"Uncontested AC {i}"},
        )

    # --- decisions namespace ---
    _write_text(
        adr_root / "ADR-029-fixture-alpha.md",
        "# ADR-029 Fixture Alpha\n\nStatus: accepted\n",
    )
    beta_number = "029" if contested else "090"
    _write_text(
        adr_root / f"ADR-{beta_number}-fixture-beta.md",
        f"# ADR-{beta_number} Fixture Beta\n\nStatus: proposed\n",
    )
    for i in range(1, 16):
        _write_text(
            adr_root / f"ADR-{700 + i}-standalone.md",
            f"# ADR-{700 + i}\n\nStatus: accepted\n",
        )

    # --- diagrams namespace ---
    _write_text(diagram_root / "c2-003-fixture-alpha.md", "# c2-003 Fixture Alpha\n")
    diagram_seq = "003" if contested else "099"
    _write_text(
        diagram_root / f"c2-{diagram_seq}-fixture-beta.md",
        f"# c2-{diagram_seq} Fixture Beta\n",
    )
    for i in range(1, 13):
        _write_text(
            diagram_root / f"c2-{600 + i}-standalone.md",
            f"# c2-{600 + i}\n",
        )


def _build_volume_fixture_collection(root: Path) -> dict:
    """Build a real on-disk collection sized to roughly this repo's own.

    Mirrors the exact per-namespace scale a pr-reviewer pass measured
    directly against this repository's real collection (3092 AC yaml files,
    35 decisions, 24 diagrams, 289 work items), rounded to clean,
    easy-to-assert counts. Every AC record is written with yaml.safe_dump
    (Fixture Authenticity Rule -- never a hand-typed YAML literal); the
    work-items lifecycle manifest is written with json.dump, never a
    hand-typed JSON literal. No collisions are planted anywhere: this
    fixture exists purely to measure wall-clock time and inspected counts at
    realistic volume -- collision detection is already covered by
    TestContestedCollectionReporting / TestRepairedCollectionPasses above.

    Args:
        root: Tempdir root to build the fixture collection under.

    Returns:
        Mapping of namespace name -> the exact count of artifacts written
        for that namespace, for an independent ground-truth comparison
        against verdict.namespaces[name].inspected_count.
    """
    ac_root = root / "docs" / "acceptance-criteria" / "perf-fixture-component"
    adr_root = root / "docs" / "architecture" / "adrs"
    diagram_root = root / "docs" / "architecture" / "diagrams"
    tickets_root = root / "tickets"

    for i in range(_PERF_AC_COUNT):
        _write_ac_yaml(
            ac_root / f"GE-PERF-{i}-standalone.yaml",
            {
                "id": f"GE-PERF-{i}",
                "components": ["commit_guardian"],
                "title": f"Perf-volume fixture AC record number {i} with a realistically long title",
                "component": "guardrail-engine",
                "status": "active",
                "level": "L2",
                "readiness": "draft",
                "work_status": "done",
                "priority": "high",
                "criteria": _PERF_CRITERIA_BLOCK,
                "origin_agent": "business-analyst-v2",
                "created": "2026-08-18",
                "created_by_ticket": f"tickets/00_inbox/TICKET-perf-{i}.md",
                "covered_by": [f"unit_tests/commit_guardian/test_perf_{i}.py"],
                "implemented_by": [f"templates/scripts/commit_guardian/hooks/perf_{i}.py"],
            },
        )

    for i in range(_PERF_DECISION_COUNT):
        _write_text(
            adr_root / f"ADR-{2000 + i}-perf-volume.md",
            f"# ADR-{2000 + i}\n\nStatus: accepted\n",
        )

    for i in range(_PERF_DIAGRAM_COUNT):
        _write_text(
            diagram_root / f"c2-{2000 + i}-perf-volume.md",
            f"# c2-{2000 + i}\n",
        )

    lifecycle_manifest = {"folders": [{"path": f"tickets/{name}"} for name in _PERF_WORK_ITEM_FOLDERS]}
    tickets_root.mkdir(parents=True, exist_ok=True)
    with open(tickets_root / "ticket_lifecycle.json", "w", encoding="utf-8") as fh:
        json.dump(lifecycle_manifest, fh)

    for i in range(_PERF_WORK_ITEM_COUNT):
        folder_path = tickets_root / _PERF_WORK_ITEM_FOLDERS[i % len(_PERF_WORK_ITEM_FOLDERS)]
        _write_text(
            folder_path / f"TICKET-PERF-{i}.md",
            "---\nstatus: todo\n---\n# Perf-volume ticket\n",
        )

    return {
        _NS_AC: _PERF_AC_COUNT,
        _NS_DECISIONS: _PERF_DECISION_COUNT,
        _NS_DIAGRAMS: _PERF_DIAGRAM_COUNT,
        _NS_WORK_ITEMS: _PERF_WORK_ITEM_COUNT,
    }


def _expected_claimant_paths(root: Path) -> dict:
    """Return the expected two-claimant path pairs for each contested number.

    Args:
        root: The fixture collection root built by _build_fixture_collection
            with contested=True.

    Returns:
        Mapping of namespace name -> (contested_number, [claimant_a, claimant_b]).
    """
    ac_root = root / "docs" / "acceptance-criteria" / "fixture-component"
    adr_root = root / "docs" / "architecture" / "adrs"
    diagram_root = root / "docs" / "architecture" / "diagrams"
    return {
        _NS_AC: (
            "GE-119",
            [
                ac_root / "GE-119-collision-goal" / "GE-119.yaml",
                ac_root / "GE-119-detail.yaml",
            ],
        ),
        _NS_DECISIONS: (
            "029",
            [
                adr_root / "ADR-029-fixture-alpha.md",
                adr_root / "ADR-029-fixture-beta.md",
            ],
        ),
        _NS_DIAGRAMS: (
            "c2-003",
            [
                diagram_root / "c2-003-fixture-alpha.md",
                diagram_root / "c2-003-fixture-beta.md",
            ],
        ),
    }


def _resolved_path_set(raw_paths, collection_root: Path) -> set:
    """Normalize a finding's claimant path strings to resolved absolute Paths.

    Args:
        raw_paths: Iterable of path strings/Path objects from a Finding.
        collection_root: The fixture root, used to resolve relative paths.

    Returns:
        Set of resolved absolute Path objects.
    """
    resolved = set()
    for raw in raw_paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = collection_root / candidate
        resolved.add(candidate.resolve())
    return resolved


def _all_findings(verdict):
    """Flatten every (namespace_name, finding) pair out of a verdict object.

    Args:
        verdict: The object returned by run_uniqueness_pass.

    Returns:
        List of (namespace_name, finding) tuples.
    """
    flattened = []
    for ns_name, ns_verdict in verdict.namespaces.items():
        for finding in ns_verdict.findings:
            flattened.append((ns_name, finding))
    return flattened


def _number_matches(finding_number, expected: str) -> bool:
    """Compare a finding's contested number against the expected value.

    Decision numbers may reasonably be represented zero-padded ("029") or as
    a bare int (29) depending on the coder's chosen internal type -- this
    does not over-constrain that choice while still requiring the SAME
    underlying number.

    Args:
        finding_number: The `number` attribute off a Finding.
        expected: The zero-padded expected string (e.g. "029", "GE-119").

    Returns:
        True if the numbers denote the same contested value.
    """
    candidate = str(finding_number)
    if candidate == expected:
        return True
    return candidate.lstrip("0") == expected.lstrip("0") and expected.lstrip("0") != ""


# ---------------------------------------------------------------------------
# Behavioral tests 1-4: execute the real pass over a real fixture collection
# ---------------------------------------------------------------------------


class UniquenessPassFixtureTestCase(unittest.TestCase):
    """Shared tempdir fixture scaffolding for the four behavioral tests."""

    def setUp(self) -> None:
        _require_mod(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


class TestContestedCollectionReporting(UniquenessPassFixtureTestCase):
    """AC-2, AC-3, AC-4, AC-5: the contested-fixture half of the Gherkin."""

    def test_uniqueness_pass_reports_one_finding_per_contested_number(self):
        # covers: GE-122a-1
        """Over a fixture holding a duplicated AC id, a duplicated decision
        integer, and a duplicated diagram level-and-sequence -- plus 48
        further uncontested artifacts across the same three namespaces --
        the pass must return a FAILING outcome and EXACTLY THREE findings
        total across the whole verdict: one per contested number, never one
        per claimant file (which would produce six).

        FAILS TODAY: check_identifier_uniqueness.py does not exist, so
        _require_mod fails this test in setUp with a clear AssertionError.
        """
        _build_fixture_collection(self.root, contested=True)

        verdict = _mod.run_uniqueness_pass(self.root)

        self.assertFalse(
            verdict.passed,
            msg="A collection with three planted collisions must fail the pass.",
        )
        findings = _all_findings(verdict)
        self.assertEqual(
            len(findings),
            3,
            msg=(
                "Expected exactly 3 findings (one per contested number across "
                f"3 namespaces), got {len(findings)}: {findings}. A per-claimant-"
                "file report (6 findings) is the specific off-by-design error "
                "this AC calls out."
            ),
        )

    def test_uncontested_artifacts_absent_from_report(self):
        # covers: GE-122a-1
        """No artifact whose number is claimed exactly once may appear
        anywhere in the report -- neither as a contested `number` nor inside
        any finding's `paths` -- even though the fixture carries 48
        uncontested artifacts (20 AC + 15 decision + 13 diagram) alongside
        the three collisions.

        FAILS TODAY: module does not exist yet.
        """
        _build_fixture_collection(self.root, contested=True)

        verdict = _mod.run_uniqueness_pass(self.root)

        findings = _all_findings(verdict)
        reported_numbers = {finding.number for _ns, finding in findings}
        reported_paths = set()
        for _ns, finding in findings:
            reported_paths |= _resolved_path_set(finding.paths, self.root)

        uncontested_ac_ids = {f"GE-{800 + i}" for i in range(1, 21)}
        uncontested_decision_numbers = {f"{700 + i}" for i in range(1, 16)}
        uncontested_diagram_numbers = {f"c2-{600 + i}" for i in range(1, 13)}

        for number in uncontested_ac_ids | uncontested_decision_numbers | uncontested_diagram_numbers:
            self.assertFalse(
                any(_number_matches(n, number) for n in reported_numbers),
                msg=f"Uncontested number {number!r} leaked into the report's contested numbers.",
            )

        ac_root = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        adr_root = self.root / "docs" / "architecture" / "adrs"
        diagram_root = self.root / "docs" / "architecture" / "diagrams"
        uncontested_paths = (
            [(ac_root / f"GE-{800 + i}-standalone.yaml").resolve() for i in range(1, 21)]
            + [(adr_root / f"ADR-{700 + i}-standalone.md").resolve() for i in range(1, 16)]
            + [(diagram_root / f"c2-{600 + i}-standalone.md").resolve() for i in range(1, 13)]
        )
        for path in uncontested_paths:
            self.assertNotIn(
                path,
                reported_paths,
                msg=f"Uncontested artifact {path} must not appear in any finding's paths.",
            )

    def test_each_finding_names_every_claimant_path(self):
        # covers: GE-122a-1
        """Each of the three findings must carry the contested number AND
        the on-disk path of BOTH claimants -- asserted against the actual
        paths written to disk by the fixture builder, not against any
        internal helper's return value.

        FAILS TODAY: module does not exist yet.
        """
        _build_fixture_collection(self.root, contested=True)
        expected = _expected_claimant_paths(self.root)

        verdict = _mod.run_uniqueness_pass(self.root)

        for ns_name, (expected_number, expected_paths) in expected.items():
            self.assertIn(
                ns_name,
                verdict.namespaces,
                msg=f"Verdict is missing the {ns_name!r} namespace entirely.",
            )
            ns_verdict = verdict.namespaces[ns_name]
            matching = [f for f in ns_verdict.findings if _number_matches(f.number, expected_number)]
            self.assertEqual(
                len(matching),
                1,
                msg=(
                    f"Expected exactly one finding for {expected_number!r} in "
                    f"namespace {ns_name!r}, found {len(matching)}: "
                    f"{ns_verdict.findings}"
                ),
            )
            finding = matching[0]
            actual_paths = _resolved_path_set(finding.paths, self.root)
            expected_resolved = {p.resolve() for p in expected_paths}
            self.assertEqual(
                actual_paths,
                expected_resolved,
                msg=(
                    f"Namespace {ns_name!r} finding for {expected_number!r} must "
                    f"name exactly both claimants. Expected {expected_resolved}, "
                    f"got {actual_paths}."
                ),
            )


class TestRepairedCollectionPasses(UniquenessPassFixtureTestCase):
    """AC-6, AC-7, AC-8: the repaired-fixture half of the Gherkin."""

    def test_repaired_collection_passes_with_per_namespace_counts(self):
        # covers: GE-122a-1
        """With the three collisions resolved (one claimant per pair
        renumbered, same TOTAL artifact count per namespace), the pass must
        return a PASSING outcome AND report, per namespace, an
        inspected_count EQUAL to an independently-computed on-disk count --
        not merely non-zero. A pass that inspected zero files and a pass
        that inspected the whole collection both currently look identical
        (`passed=True`) unless the count is checked against ground truth.

        FAILS TODAY: module does not exist yet.
        """
        _build_fixture_collection(self.root, contested=False)

        verdict = _mod.run_uniqueness_pass(self.root)

        self.assertTrue(
            verdict.passed,
            msg="A collection with every collision resolved must pass the pass.",
        )

        ac_dir = self.root / "docs" / "acceptance-criteria"
        adr_dir = self.root / "docs" / "architecture" / "adrs"
        diagram_dir = self.root / "docs" / "architecture" / "diagrams"

        expected_counts = {
            _NS_AC: len(list(ac_dir.rglob("*.yaml"))),
            _NS_DECISIONS: len(list(adr_dir.glob("*.md"))),
            _NS_DIAGRAMS: len(list(diagram_dir.glob("*.md"))),
        }

        for ns_name, expected_count in expected_counts.items():
            self.assertGreater(
                expected_count,
                0,
                msg=f"Fixture sanity check failed: namespace {ns_name!r} has 0 on-disk artifacts.",
            )
            self.assertIn(ns_name, verdict.namespaces)
            ns_verdict = verdict.namespaces[ns_name]
            self.assertTrue(ns_verdict.passed, msg=f"Namespace {ns_name!r} must pass once repaired.")
            self.assertEqual(
                ns_verdict.inspected_count,
                expected_count,
                msg=(
                    f"Namespace {ns_name!r} inspected_count must equal the "
                    f"independently-computed on-disk count ({expected_count}), "
                    f"got {ns_verdict.inspected_count}. A count that is merely "
                    "non-zero cannot distinguish a real pass from a pass over "
                    "a partial walk."
                ),
            )


# ---------------------------------------------------------------------------
# Integration test 5: the pass must run from the DEPLOYED layout
# ---------------------------------------------------------------------------


class TestDeployedLayoutInvocation(unittest.TestCase):
    """test_pass_runs_from_the_deployed_layout."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

    def test_pass_runs_from_the_deployed_layout(self):
        # covers: GE-122a-1
        """After running the REAL scripts/build.py against a scratch target
        directory, check_identifier_uniqueness.py (and every module it
        imports, e.g. a shared store-loader extracted per this ticket's
        Implementation Notes) must be present in the DEPLOYED
        scripts/commit_guardian/ copy and runnable as a subprocess without
        ModuleNotFoundError. A source-tree unit test that imports the module
        directly (as tests 1-4 do) cannot make this specific check: it would
        stay green even if a dependency were never added to the build
        deploy-manifest, exactly as happened historically with
        done_proof.py (CLAUDE.md, "New Hook / Gate Dependencies Must Be in
        the Build Deploy-Manifest").

        FAILS TODAY: templates/scripts/commit_guardian/
        check_identifier_uniqueness.py does not exist, so build.py deploys
        nothing by that name and the existence assertion below fails with a
        plain AssertionError (not a crash, not a syntax error).
        """
        build_result = subprocess.run(
            [sys.executable, str(_BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            0,
            build_result.returncode,
            msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
        )

        deployed_script = self.target / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"
        self.assertTrue(
            deployed_script.exists(),
            msg=(
                f"{deployed_script} was not deployed by build.py. Ensure "
                "check_identifier_uniqueness.py exists under "
                "templates/scripts/commit_guardian/ (ADR-001: template is "
                "canonical, build.py deploys the whole directory)."
            ),
        )

        # Give the deployed script a real, if empty, docs/ tree to walk so a
        # genuine execution is exercised, not merely a file-existence check.
        (self.target / "docs" / "acceptance-criteria").mkdir(parents=True, exist_ok=True)
        (self.target / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
        (self.target / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)

        run_result = subprocess.run(
            [sys.executable, str(deployed_script)],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            env={**_CLEAN_ENV_TEMPLATE, "HOME": str(self.target)},
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertNotIn(
            "ModuleNotFoundError",
            run_result.stderr,
            msg=(
                "check_identifier_uniqueness.py crashed importing a dependency "
                f"from the deployed layout. stderr:\n{run_result.stderr}"
            ),
        )
        self.assertIn(
            run_result.returncode,
            (0, 1),
            msg=(
                "Deployed script must exit 0 (pass) or 1 (findings/failure), "
                f"never crash. returncode={run_result.returncode} "
                f"stderr:\n{run_result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# Integration test 6: decision-namespace gate registration + survival + bite
# ---------------------------------------------------------------------------


class TestDecisionNamespaceGateRegistration(unittest.TestCase):
    """test_decision_namespace_gate_is_registered_and_executes."""

    def test_decision_namespace_gate_is_registered_and_executes(self):
        # covers: GE-122a-1
        """Three escalating checks, each necessary and none sufficient alone:

        1. A decision-number uniqueness hook is registered in
           hooks_manifest.hooks of the CANONICAL commit_guardian.json (not
           merely: check_adr_collision.py exists as a file -- verified
           2026-08-17 to be registered in NEITHER .pre-commit-config.yaml,
           NOR either commit_guardian.json manifest, NOR ci.yml, so it has
           never executed).
        2. That registration SURVIVES a real build.py regeneration of
           .pre-commit-config.yaml -- build_precommit.py strips every
           `@package-managed` block and re-renders it from
           hooks_manifest.hooks on every run, so a hook added only by hand
           to .pre-commit-config.yaml vanishes on the next build.
        3. The deployed hook ACTUALLY BLOCKS (non-zero exit) when invoked
           against a real git-staged commit adding two decision records
           that both claim number 029. Manifest presence alone is
           explicitly insufficient coverage per this ticket's Test
           Requirements.

        FAILS TODAY at step 1: no hook in hooks_manifest.hooks references
        check_adr_collision.py, check_identifier_uniqueness.py, or an
        id/name mentioning "adr"/"decision" -- confirmed by direct read of
        templates/scripts/commit_guardian/commit_guardian.json.
        """
        self.assertTrue(
            _CANONICAL_MANIFEST.exists(),
            msg=f"Canonical manifest not found at {_CANONICAL_MANIFEST}.",
        )
        manifest = json.loads(_CANONICAL_MANIFEST.read_text(encoding="utf-8"))
        hooks = manifest.get("hooks_manifest", {}).get("hooks", [])

        def _is_decision_hook(hook: dict) -> bool:
            # Matches on the SCRIPT the hook actually runs, or an id naming
            # the collision/uniqueness behavior specifically -- NOT a loose
            # "adr" substring, which would false-positive on the pre-existing
            # (and unrelated) check-adr-coverage / check-adr-cross-reference
            # hooks that already run today and do not detect number
            # collisions at all.
            hook_id = hook.get("id", "").lower()
            entry = hook.get("entry", "")
            return (
                "check_adr_collision.py" in entry
                or "check_identifier_uniqueness.py" in entry
                or "collision" in hook_id
                or "uniqueness" in hook_id
            )

        decision_hook = next((h for h in hooks if _is_decision_hook(h)), None)
        self.assertIsNotNone(
            decision_hook,
            msg=(
                "No decision-number uniqueness hook found in hooks_manifest.hooks "
                f"of {_CANONICAL_MANIFEST}. check_adr_collision.py exists but is "
                "registered nowhere (verified 2026-08-17) -- this is the "
                "registration gap this AC's decision namespace must close."
            ),
        )
        hook_id = decision_hook["id"]
        entry_template = decision_hook.get("entry", "")
        entry_tokens = entry_template.split()
        self.assertTrue(
            entry_tokens,
            msg=f"Hook {hook_id!r} has an empty 'entry' field in the manifest.",
        )
        entry_script_name = Path(entry_tokens[-1]).name

        with tempfile.TemporaryDirectory() as td:
            target = Path(td)

            build_result = subprocess.run(
                [sys.executable, str(_BUILD_PY), "--target-dir", str(target)],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                0,
                build_result.returncode,
                msg=f"build.py failed: stdout={build_result.stdout} stderr={build_result.stderr}",
            )

            precommit_config = target / ".pre-commit-config.yaml"
            self.assertTrue(
                precommit_config.exists(),
                msg="build.py did not generate .pre-commit-config.yaml.",
            )
            config_text = precommit_config.read_text(encoding="utf-8")
            self.assertIn(
                hook_id,
                config_text,
                msg=(
                    f"Hook {hook_id!r} is present in hooks_manifest.hooks but "
                    "absent from the REGENERATED .pre-commit-config.yaml -- a "
                    "hook only added by hand to .pre-commit-config.yaml is "
                    "stripped on the next build.py run."
                ),
            )

            subprocess.run(
                ["git", "init", "-q", str(target)],
                check=True,
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )
            adr_dir = target / "docs" / "architecture" / "adrs"
            adr_dir.mkdir(parents=True, exist_ok=True)
            (adr_dir / "ADR-029-alpha.md").write_text("# ADR-029 Alpha\n", encoding="utf-8")
            (adr_dir / "ADR-029-beta.md").write_text("# ADR-029 Beta\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(target), "add", "."],
                check=True,
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )

            entry_script = target / "scripts" / "commit_guardian" / entry_script_name
            self.assertTrue(
                entry_script.exists(),
                msg=f"Deployed hook entry script {entry_script} does not exist after build.py.",
            )

            hook_result = subprocess.run(
                [sys.executable, str(entry_script)],
                cwd=str(target),
                capture_output=True,
                text=True,
                env={**_CLEAN_ENV_TEMPLATE, "HOME": str(target)},
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )
            self.assertNotEqual(
                0,
                hook_result.returncode,
                msg=(
                    f"Hook {hook_id!r} is registered and survives build.py but did "
                    "NOT block a commit staging two decision records both claiming "
                    f"number 029. stdout={hook_result.stdout} "
                    f"stderr={hook_result.stderr}"
                ),
            )


# ---------------------------------------------------------------------------
# Performance regression guard -- wall-clock upper bound
# ---------------------------------------------------------------------------


class TestUniquenessPassPerformanceBudget(UniquenessPassFixtureTestCase):
    """test_uniqueness_pass_completes_within_generous_wallclock_ceiling.

    Regression guard for the performance defect a pr-reviewer pass measured
    directly against this repository's own real collection:
    run_uniqueness_pass('.') took 10.2-11.4s over three runs (3092 AC yaml
    files, 35 decisions, 24 diagrams, 289 work items); an independent
    re-measurement on the same collection was worse still, at 13.6/14.9/16.0s.
    Either way it is multiples of this
    ticket's own Implementation Notes budget of "under 5 seconds at commit
    time... a commit-time gate slower than that gets bypassed." pr-reviewer
    isolated the cost to scan_acceptance_criteria alone (10.9s for 3092
    files): every *.yaml is opened and run through yaml.safe_load purely to
    read the top-level `id` field. NO EXISTING TEST elsewhere in this file
    asserts on wall-clock time -- that is exactly why the regression was
    invisible to a fully green suite.
    """

    def test_uniqueness_pass_completes_within_generous_wallclock_ceiling_at_realistic_scale(self):
        # covers: GE-122a-1
        """Assert an 8-second upper bound -- a GENEROUS ceiling, NOT the
        ticket's 5-second target.

        The 3-second margin above the 5s commit-time target absorbs
        ordinary machine variance (CI runner contention, cold filesystem
        cache, a slower dev laptop) so this test is not flaky for reasons
        unrelated to the code under test. The point of an 8s ceiling is to
        catch an ORDER-OF-MAGNITUDE regression like the one pr-reviewer
        actually measured (10.2-11.4s, over 2x budget) -- not to
        micro-benchmark down to the ticket's literal number, which would
        make this test a source of noise rather than a real regression
        guard.

        Fixture CONSTRUCTION (writing ~3348 files to disk across all four
        namespaces) is deliberately EXCLUDED from the timed region -- only
        the run_uniqueness_pass call itself is timed. A pass that inspected
        nothing (or only a fraction of the fixture) would otherwise be
        trivially fast and falsely green against this wall-clock assertion,
        so every namespace's inspected_count is checked against the EXACT
        count of artifacts this fixture actually wrote -- never a bare
        "> 0" check, which cannot distinguish a real full pass from a
        partial or empty one.

        FAILS TODAY: run_uniqueness_pass takes 10+ seconds against a
        collection sized like this one, because scan_acceptance_criteria
        opens and yaml.safe_load's every one of the 3000 AC fixture files
        purely to read their top-level `id` field. This assertion is
        expected to be RED until python-coder fixes the AC namespace scan
        (e.g. a cheap id-only fast path before falling back to full
        yaml.safe_load, or parallelizing the per-file reads).
        """
        expected_counts = _build_volume_fixture_collection(self.root)

        start = time.perf_counter()
        verdict = _mod.run_uniqueness_pass(self.root)
        elapsed = time.perf_counter() - start

        self.assertLess(
            elapsed,
            _PERF_WALLCLOCK_CEILING_SECONDS,
            msg=(
                f"run_uniqueness_pass took {elapsed:.2f}s against a fixture sized to "
                f"roughly this repo's real collection ({sum(expected_counts.values())} "
                f"total artifacts across {sorted(expected_counts)}) -- over the "
                f"{_PERF_WALLCLOCK_CEILING_SECONDS}s generous ceiling. The ticket's own "
                "Implementation Notes budget is under 5s at commit time ('a commit-time "
                "gate slower than that gets bypassed'); this 8s ceiling only catches an "
                "order-of-magnitude regression, so overshooting it is a real defect, not "
                "machine noise."
            ),
        )

        self.assertTrue(
            verdict.passed,
            msg=(
                "This fixture plants no collisions in any namespace; a non-passing "
                "verdict indicates a bug in the fixture builder, not a genuine finding."
            ),
        )
        for ns_name, expected_count in expected_counts.items():
            self.assertIn(
                ns_name,
                verdict.namespaces,
                msg=f"Verdict is missing the {ns_name!r} namespace entirely.",
            )
            actual_count = verdict.namespaces[ns_name].inspected_count
            self.assertEqual(
                actual_count,
                expected_count,
                msg=(
                    f"Namespace {ns_name!r} inspected_count must equal the exact count "
                    f"of artifacts this fixture wrote ({expected_count}), got "
                    f"{actual_count}. A pass that inspected zero (or only a partial "
                    "fixture) would otherwise look trivially fast and falsely satisfy "
                    "the wall-clock ceiling above."
                ),
            )


if __name__ == "__main__":
    unittest.main()
