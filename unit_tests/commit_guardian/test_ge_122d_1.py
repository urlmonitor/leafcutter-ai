"""
MODULE: unit_tests/commit_guardian/test_ge_122d_1.py
GOAL: RED test-first stubs for GE-122d-1 -- "One rule, evaluated at three
    stages, cannot give three different answers". The shared evaluation
    module (templates/scripts/commit_guardian/check_identifier_uniqueness.py,
    built for GE-122a-1) already exists and already deploys correctly to
    ``<target>/scripts/commit_guardian/`` (the commit-time AND shared-build
    stages, per build_commit_guardian's whole-directory rglob copy). What
    does NOT exist yet is a deploy path to ``<target>/hooks/`` (the
    authoring-time stage, per build_hooks, which only copies files that live
    directly under ``templates/hooks/`` and skips underscore-prefixed
    files) -- this ticket's job, confined to scripts/build_phases.py, is to
    add that second deploy destination.
BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
    and this ticket's Implementation Notes: "THE HARD PART IS DEPLOY-PATH,
    NOT DESIGN... Getting this wrong presents as the authoring stage
    silently emitting nothing while the other two work -- a three-way
    disagreement in exactly the shape this criterion forbids, and invisible
    to source-tree unit tests." Every test below therefore invokes the
    stages as separate SUBPROCESSES against a real on-disk deployed copy --
    never a source-tree import of one canonical file pretending to be three
    stages -- because a source-tree import cannot observe a deploy-manifest
    gap (CLAUDE.md, "New Hook / Gate Dependencies Must Be in the Build
    Deploy-Manifest").

STAGE DEFINITIONS USED BY THESE TESTS (per this ticket's own Implementation
Notes, "Follow the precedent the AC store valid job records... That
collapses two of the three stages to one configuration by construction,
leaving only the authoring stage to reconcile"):
    - authoring-time stage : the deployed copy at ``<target>/hooks/
      check_identifier_uniqueness.py`` (does not exist before this ticket).
    - commit-time stage    : the deployed copy at ``<target>/scripts/
      commit_guardian/check_identifier_uniqueness.py`` (already deployed by
      the pre-existing build_commit_guardian, unaffected by this ticket).
    - shared-build stage   : the SAME commit-time deployed copy, invoked
      through pre-commit in CI rather than a second copy -- covered
      separately (and structurally, since it is a CI-wiring fact) by
      unit_tests/build_guards/test_ge_122d_1.py.

ARCHITECTURE / EXERCISE STRATEGY:
  - Tests 1-3 build a real on-disk fixture collection (AC-namespace id
    collisions, produced with yaml.safe_dump per docs/reference/
    fixture-policy.md's Fixture Authenticity Rule -- never a hand-typed
    YAML literal) under a scratch target directory that ALSO serves as the
    ``--target-dir`` for a real ``scripts/build.py`` subprocess run, then
    invoke each deployed stage script as its own subprocess with that
    directory as ``cwd`` (main() reads ``Path.cwd()``).
  - Test 4 (single-rule-change) copies the REAL canonical
    templates/scripts/commit_guardian/ tree into an isolated scratch
    templates directory (never mutates the actual repository source),
    monkeypatches a freshly-loaded copy of scripts/build_phases.py's
    ``TEMPLATES_DIR`` to point at that scratch tree, and calls the real
    ``build_hooks`` / ``build_commit_guardian`` deploy functions against it
    twice: once before and once after a single-line edit to the ONE
    existing regex constant (``_ADR_FILENAME_RE`` in ``_uniqueness_
    scanners.py``) that governs the decisions namespace's recognised number
    shape. This exercises the real production regex and the real
    build_phases.py deploy functions this ticket touches, without ever
    writing to the actual repository tree.
  - Test 5 is the mandatory reachability test: it invokes the deployed
    authoring-time script as a subprocess (never importing the function
    directly) and asserts its exit code -- the process's real contract with
    a caller -- reflects the contested fixture.
  - No test baselines against a git ref (origin/main, main, or a hardcoded
    SHA); every fixture is its own scratch directory (PR #462 caution,
    reused from test_ge_122a_1.py's own module docstring).

DECISION HISTORY
- 2026-09-01 [GE-122d-1/test-writer]: Initial authoring of all five RED test
  stubs. Verified RED via `python -m unittest discover`: see the test-writer
  sign-off comment for the exact captured failures/errors.

CONTRACT-AWARE MODE / GLOBAL AC LIST NOTE (not testable as separate units):
    The ticket body's global `## Acceptance Criteria` checklist (AC-1..AC-5)
    is an auto-split of GE-122d-1's single Gherkin block into sentence
    fragments (e.g. "AC-1: at the shared-build stage, each over that same
    collection"), not five independently testable requirements -- none of
    the five is a complete statement on its own. There is no
    `### test-writer` subsection under `## Agent Contracts` to scope this
    further. Per the AC-mapping fallback rule, each fragment is noted here
    against the test(s) in this file that exercise the FULL sentence it was
    cut from, rather than fabricated as a standalone assertion:
      - AC-1 ("...at the shared-build stage, each over that same
        collection") + AC-2 ("all three stages identify the same contested
        number and name the same set of claimant paths") together restate
        the Gherkin's first Then-clause -> covered by
        test_three_stages_agree_on_the_same_contested_collection.
      - AC-3 ("given the rule is then extended so that a number shape
        previously accepted is now [contested]") -> covered by
        test_single_rule_change_propagates_to_all_three_stages.
      - AC-4 ("all three stages report the newly contested case") -> covered
        by the same test (its second half, after the single-place edit).
      - AC-5 ("there is no collection for which one stage reports a clean
        result while another stage reports a contested one") -> covered by
        test_no_stage_reports_clean_while_another_reports_contested.
    (not testable: AC-1..AC-5 are sentence fragments of one Gherkin
    criterion, not independently checkable statements; see the mapping
    above for the tests that cover the full sentences they were split from.)
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Canonical paths -- templates/ is the source of truth (ADR-001).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CANONICAL_MODULE = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"
_CANONICAL_SCANNERS = _COMMIT_GUARDIAN_DIR / "_uniqueness_scanners.py"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"
_BUILD_PHASES_PY = _REPO_ROOT / "scripts" / "build_phases.py"

_SUBPROCESS_TIMEOUT_SECONDS = 60
_CLEAN_ENV_TEMPLATE = {"PATH": "/usr/bin:/bin:/usr/local/bin"}

_FINDING_LINE_RE = re.compile(r"^  (\S.*?) claimed by: (.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Fixture / invocation helpers
# ---------------------------------------------------------------------------


def _write_ac_yaml(path: Path, data: dict) -> None:
    """Write an AC-namespace YAML fixture using the REAL serializer.

    Per docs/reference/fixture-policy.md's Fixture Authenticity Rule, a
    hand-typed YAML string is rejected as a fixture for a serialized format.

    Args:
        path: Destination file path (parents created as needed).
        data: The record fields to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _scaffold_empty_collection(root: Path) -> None:
    """Create an otherwise-empty, resolvable four-namespace collection.

    Every namespace root must actually EXIST (an absent root reports
    passed=False per GE-122e-3's "root resolution" contract, which would be
    indistinguishable from a genuine collision in these tests) but starts
    empty, so callers can plant exactly the collision they want to assert on
    without any other namespace contributing noise.

    Args:
        root: The collection root (also the build.py --target-dir and the
            cwd every stage script is invoked from).
    """
    (root / "docs" / "acceptance-criteria").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
    (root / "tickets").mkdir(parents=True, exist_ok=True)
    with open(root / "tickets" / "ticket_lifecycle.json", "w", encoding="utf-8") as fh:
        json.dump({"folders": []}, fh)


def _plant_single_ac_collision(root: Path, number: str) -> None:
    """Plant exactly one contested acceptance-criteria id, plus one solo id.

    Mirrors the AC's own Gherkin: "a collection containing exactly one
    contested number".

    Args:
        root: The collection root (must already be scaffolded).
        number: The contested identifier to plant twice.
    """
    ac_dir = root / "docs" / "acceptance-criteria" / "guardrail-engine"
    _write_ac_yaml(ac_dir / "dup-a.yaml", {"id": number, "title": "Dup A"})
    _write_ac_yaml(ac_dir / "dup-b.yaml", {"id": number, "title": "Dup B"})
    _write_ac_yaml(ac_dir / "solo.yaml", {"id": f"{number}-SOLO", "title": "Solo"})


def _run_build(target: Path) -> subprocess.CompletedProcess:
    """Run the REAL scripts/build.py against ``target`` and return the result."""
    return subprocess.run(
        [sys.executable, str(_BUILD_PY), "--target-dir", str(target)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _run_stage(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed stage script as its own subprocess.

    Args:
        script: Absolute path to the deployed script.
        cwd: Directory to run it from (main() reads Path.cwd()).

    Returns:
        The completed subprocess result. Never raises on a missing script:
        the interpreter itself reports "can't open file" via a non-zero
        return code, which callers assert on explicitly.
    """
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**_CLEAN_ENV_TEMPLATE, "HOME": str(cwd)},
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _parse_findings(stderr: str) -> dict:
    """Parse "<number> claimed by: <paths>" lines out of stage stderr.

    Args:
        stderr: Captured stderr text from a stage invocation.

    Returns:
        Mapping of contested number -> set of claimant path strings.
    """
    findings: dict[str, set[str]] = {}
    for match in _FINDING_LINE_RE.finditer(stderr):
        number = match.group(1)
        paths_part = match.group(2).split(" (declared states:")[0]
        findings[number] = {p.strip() for p in paths_part.split(",")}
    return findings


class _DeployedCollectionTestCase(unittest.TestCase):
    """Shared setUp: one scratch dir used as both build target and cwd."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

    def _deploy(self) -> None:
        result = _run_build(self.target)
        self.assertEqual(
            0,
            result.returncode,
            msg=f"build.py itself failed: stdout={result.stdout} stderr={result.stderr}",
        )


# ---------------------------------------------------------------------------
# Test 1: three stages agree on one contested collection
# ---------------------------------------------------------------------------


class TestThreeStagesAgree(_DeployedCollectionTestCase):
    def test_three_stages_agree_on_the_same_contested_collection(self):
        # covers: GE-122d-1
        # angle: criterion
        """A collection with exactly one contested number must be reported
        identically -- same contested number, same set of claimant paths --
        by the authoring-time deployed copy (<target>/hooks/
        check_identifier_uniqueness.py) and the commit-time deployed copy
        (<target>/scripts/commit_guardian/check_identifier_uniqueness.py).

        FAILS TODAY: <target>/hooks/check_identifier_uniqueness.py is never
        written by build.py (build_hooks only copies files that live
        directly under templates/hooks/, and no such file exists there yet)
        -- the interpreter reports "can't open file" (return code 2), not
        the expected disposition (1, contested).
        """
        self._deploy()
        _scaffold_empty_collection(self.target)
        _plant_single_ac_collision(self.target, "GE-900")

        authoring_script = self.target / "hooks" / "check_identifier_uniqueness.py"
        commit_script = self.target / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"

        authoring = _run_stage(authoring_script, self.target)
        commit = _run_stage(commit_script, self.target)

        self.assertEqual(
            1,
            authoring.returncode,
            msg=(
                "authoring-time stage did not report the contested collection "
                f"(script={authoring_script}). stdout={authoring.stdout} "
                f"stderr={authoring.stderr}"
            ),
        )
        self.assertEqual(
            1,
            commit.returncode,
            msg=f"commit-time stage did not report the contested collection. stderr={commit.stderr}",
        )

        authoring_findings = _parse_findings(authoring.stderr)
        commit_findings = _parse_findings(commit.stderr)
        self.assertIn(
            "GE-900",
            authoring_findings,
            msg=f"authoring stage did not name the contested number. stderr={authoring.stderr}",
        )
        self.assertEqual(
            commit_findings,
            authoring_findings,
            msg=(
                "The two stages named different contested numbers and/or "
                f"different claimant paths for the same collection. "
                f"authoring={authoring_findings} commit={commit_findings}"
            ),
        )


# ---------------------------------------------------------------------------
# Test 2: a single-place rule extension propagates to both deploy destinations
# ---------------------------------------------------------------------------


class TestSingleRuleChangePropagation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        scratch_root = Path(self._tmp.name)
        self.scratch_templates = scratch_root / "templates"
        self.scratch_cg = self.scratch_templates / "scripts" / "commit_guardian"
        shutil.copytree(_COMMIT_GUARDIAN_DIR, self.scratch_cg)
        self.target = scratch_root / "deployed"

        # build_phases.py does `from template_compiler import (...)` at
        # module scope, resolved via sys.path rather than its own __file__
        # directory (unlike check_identifier_uniqueness.py's explicit
        # bootstrap) -- loading it by file path via importlib requires its
        # sibling scripts/ directory on sys.path first, same as running it
        # as `python scripts/build.py` would get for free.
        scripts_dir = str(_BUILD_PHASES_PY.parent)
        self._sys_path_inserted = scripts_dir not in sys.path
        if self._sys_path_inserted:
            sys.path.insert(0, scripts_dir)
            self.addCleanup(lambda: sys.path.remove(scripts_dir) if scripts_dir in sys.path else None)

    def _deploy_scratch(self) -> None:
        """Call the REAL build_phases deploy functions against the scratch
        templates tree (never the real repository templates/).

        Loaded fresh (not via sys.modules cache) so re-invoking after the
        single-line edit below re-reads the module docstring constants,
        not a stale cached copy.
        """
        spec = _ilu.spec_from_file_location("build_phases_ge122d1_scratch", _BUILD_PHASES_PY)
        bp = _ilu.module_from_spec(spec)
        spec.loader.exec_module(bp)
        bp.TEMPLATES_DIR = self.scratch_templates
        config = {
            "platforms": {
                "claude": True,
                "antigravity": False,
                "cursor": False,
                "copilot": False,
                "cline": False,
            }
        }
        bp.build_hooks(self.target, config, dry_run=False, force=True)
        bp.build_commit_guardian(self.target, config, dry_run=False, force=True)

    def test_single_rule_change_propagates_to_all_three_stages(self):
        # covers: GE-122d-1
        # angle: criterion
        """Extending the rule's recognised number shape in exactly ONE
        place -- the single existing ``_ADR_FILENAME_RE`` regex constant in
        ``_uniqueness_scanners.py`` -- so that a bare "ADR-029.md" (no slug)
        newly claims decision number "029" alongside the pre-existing
        "ADR-029-old.md", must be observed identically by BOTH the
        authoring-time and commit-time deployed copies, with no second edit
        made anywhere else.

        FAILS TODAY at the first `assertTrue`: build_commit_guardian (the
        only deploy function this ticket's Implementation Notes direct the
        fix into, per architect-review: "keep the shared module's deploy
        entry next to the existing commit_guardian file list") does not yet
        also write to <target>/hooks/, so the authoring-time deployed copy
        never comes into existence at all.
        """
        self._deploy_scratch()
        deployed_hook = self.target / "hooks" / "check_identifier_uniqueness.py"
        deployed_commit = self.target / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"

        self.assertTrue(
            deployed_hook.exists(),
            msg=(
                f"{deployed_hook} does not exist. The shared GE-122a-1 evaluation "
                "module (and its sibling _uniqueness_* modules) must be added to "
                "the hooks/ deploy destination in scripts/build_phases.py."
            ),
        )
        self.assertTrue(deployed_commit.exists(), msg=f"{deployed_commit} does not exist.")

        fixture = self.target
        _scaffold_empty_collection(fixture)
        adr_dir = fixture / "docs" / "architecture" / "adrs"
        (adr_dir / "ADR-029-old.md").write_text("# ADR-029 old\n", encoding="utf-8")
        (adr_dir / "ADR-029.md").write_text("# ADR-029 bare\n", encoding="utf-8")

        before_hook = _run_stage(deployed_hook, fixture)
        before_commit = _run_stage(deployed_commit, fixture)
        self.assertEqual(
            0,
            before_hook.returncode,
            msg=(
                "baseline (unwidened regex) unexpectedly already treats "
                f"ADR-029.md as claiming '029'. stderr={before_hook.stderr}"
            ),
        )
        self.assertEqual(0, before_commit.returncode, msg=f"baseline commit stage: {before_commit.stderr}")

        scanners_path = self.scratch_cg / "_uniqueness_scanners.py"
        original = scanners_path.read_text(encoding="utf-8")
        old_line = '_ADR_FILENAME_RE = re.compile(r"^ADR-(\\d+)-.*\\.md$", re.IGNORECASE)'
        new_line = '_ADR_FILENAME_RE = re.compile(r"^ADR-(\\d+)(-.*)?\\.md$", re.IGNORECASE)'
        self.assertIn(
            old_line,
            original,
            msg=(
                "Expected the current single-line _ADR_FILENAME_RE definition in "
                f"{scanners_path}. Update this test if that regex literal changed."
            ),
        )
        scanners_path.write_text(original.replace(old_line, new_line), encoding="utf-8")

        # Re-deploy with NO second edit anywhere else -- the extension was
        # made in exactly one place (this one file, one line).
        self._deploy_scratch()

        after_hook = _run_stage(deployed_hook, fixture)
        after_commit = _run_stage(deployed_commit, fixture)
        self.assertEqual(
            1,
            after_hook.returncode,
            msg=(
                "authoring-time stage did not observe the single-place rule "
                f"extension. stderr={after_hook.stderr}"
            ),
        )
        self.assertEqual(
            1,
            after_commit.returncode,
            msg=(
                "commit-time stage did not observe the single-place rule "
                f"extension. stderr={after_commit.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# Test 3: no collection produces disagreeing verdicts across stages
# ---------------------------------------------------------------------------


class TestNoStageDisagreement(_DeployedCollectionTestCase):
    def test_no_stage_reports_clean_while_another_reports_contested(self):
        # covers: GE-122d-1
        # angle: criterion
        """Across a clean collection, an acceptance-criteria-namespace
        collision, and a decisions-namespace collision, the authoring-time
        and commit-time deployed copies must always agree on pass/fail --
        never one clean while the other is contested.

        FAILS TODAY: the authoring-time deployed copy does not exist, so
        every sub-case's authoring invocation reports the interpreter's
        "can't open file" exit code (2) while the commit-time invocation
        reports the real disposition (0 or 1) -- an observed disagreement
        for every single sub-case.
        """
        self._deploy()
        authoring_script = self.target / "hooks" / "check_identifier_uniqueness.py"
        commit_script = self.target / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"

        cases = {}

        clean_dir = self.target / "clean"
        _scaffold_empty_collection(clean_dir)
        cases["clean"] = clean_dir

        ac_contested_dir = self.target / "ac_contested"
        _scaffold_empty_collection(ac_contested_dir)
        _plant_single_ac_collision(ac_contested_dir, "GE-901")
        cases["ac_contested"] = ac_contested_dir

        decision_contested_dir = self.target / "decision_contested"
        _scaffold_empty_collection(decision_contested_dir)
        adr_dir = decision_contested_dir / "docs" / "architecture" / "adrs"
        (adr_dir / "ADR-030-alpha.md").write_text("# alpha\n", encoding="utf-8")
        (adr_dir / "ADR-030-beta.md").write_text("# beta\n", encoding="utf-8")
        cases["decision_contested"] = decision_contested_dir

        for label, collection_root in cases.items():
            authoring = _run_stage(authoring_script, collection_root)
            commit = _run_stage(commit_script, collection_root)
            authoring_clean = authoring.returncode == 0
            commit_clean = commit.returncode == 0
            self.assertEqual(
                commit_clean,
                authoring_clean,
                msg=(
                    f"case={label!r}: commit-time stage reported "
                    f"{'clean' if commit_clean else 'contested'} (exit {commit.returncode}) "
                    f"while authoring-time stage reported "
                    f"{'clean' if authoring_clean else 'contested'} (exit {authoring.returncode}). "
                    f"authoring stderr={authoring.stderr} commit stderr={commit.stderr}"
                ),
            )


# ---------------------------------------------------------------------------
# Test 4: the shared module imports successfully from both deployed layouts
# ---------------------------------------------------------------------------


class TestSharedModuleImportsFromBothLayouts(_DeployedCollectionTestCase):
    def test_shared_module_imports_from_both_deployed_layouts(self):
        # covers: GE-122d-1
        # angle: deployed
        """After build.py, check_identifier_uniqueness.py (and every module
        it imports) must be present and importable/runnable -- without
        ModuleNotFoundError -- from BOTH <target>/hooks/ (authoring-time)
        and <target>/scripts/commit_guardian/ (commit-time). A source-tree
        unit test that imports one canonical file cannot make this specific
        check: it stays green even when a dependency is never added to the
        hooks/ deploy destination, exactly as happened historically with
        done_proof.py (CLAUDE.md, "New Hook / Gate Dependencies Must Be in
        the Build Deploy-Manifest").

        FAILS TODAY: <target>/hooks/check_identifier_uniqueness.py does not
        exist at all.
        """
        self._deploy()
        _scaffold_empty_collection(self.target)

        hooks_script = self.target / "hooks" / "check_identifier_uniqueness.py"
        commit_script = self.target / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"

        self.assertTrue(
            hooks_script.exists(),
            msg=f"{hooks_script} was not deployed by build.py to the authoring-time hooks/ layout.",
        )
        self.assertTrue(
            commit_script.exists(),
            msg=f"{commit_script} was not deployed by build.py to the commit-time layout.",
        )

        hooks_result = _run_stage(hooks_script, self.target)
        commit_result = _run_stage(commit_script, self.target)

        self.assertNotIn(
            "ModuleNotFoundError",
            hooks_result.stderr,
            msg=(
                "check_identifier_uniqueness.py crashed importing a sibling "
                f"module from the hooks/ deployed layout. stderr:\n{hooks_result.stderr}"
            ),
        )
        self.assertNotIn(
            "ModuleNotFoundError",
            commit_result.stderr,
            msg=f"crashed importing a dependency from the commit_guardian/ deployed layout. stderr:\n{commit_result.stderr}",
        )
        self.assertIn(hooks_result.returncode, (0, 1), msg=f"hooks/ copy crashed: {hooks_result.stderr}")
        self.assertIn(commit_result.returncode, (0, 1), msg=f"commit_guardian/ copy crashed: {commit_result.stderr}")


# ---------------------------------------------------------------------------
# Test 5: reachability -- the production entry point is actually invoked
# ---------------------------------------------------------------------------


class TestReachableFromEntryPoint(_DeployedCollectionTestCase):
    def test_ge_122d_1_reachable_from_entry_point(self):
        # covers: GE-122d-1
        # angle: reachability
        """REQUIRED reachability test (the AC's own test_spec carried no
        dedicated reachability-angle entry, so this one is authored per the
        mandatory floor). Invokes the deployed authoring-time script as a
        real subprocess -- never importing run_uniqueness_pass directly --
        against a fixture with exactly one contested acceptance-criteria id,
        and asserts the process's exit code (its real contract with a
        pre-commit-style caller) reflects that contested result, and that
        the contested number is actually present in what it printed.

        FAILS TODAY: <target>/hooks/check_identifier_uniqueness.py does not
        exist, so the interpreter reports "can't open file" (return code 2)
        rather than the expected 1.
        """
        self._deploy()
        _scaffold_empty_collection(self.target)
        _plant_single_ac_collision(self.target, "GE-902")

        script = self.target / "hooks" / "check_identifier_uniqueness.py"
        result = _run_stage(script, self.target)

        self.assertEqual(
            1,
            result.returncode,
            msg=(
                f"invoking {script} as a subprocess against a contested collection "
                f"did not exit 1. stdout={result.stdout} stderr={result.stderr}"
            ),
        )
        self.assertIn(
            "GE-902",
            result.stderr,
            msg=f"the contested number was not present in the process's own output. stderr={result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
