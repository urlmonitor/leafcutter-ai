"""
MODULE: unit_tests/ac_store/test_ge_120a_4.py
GOAL: GE-120a-4 — An inspection that resolved none of the targets it was given
    does not report success.

BUSINESS CONTEXT: scripts/ac_store/validate_ac_schema.py is the agent-side AC
    schema validator invoked ad hoc (and per CLAUDE.md's "AC-store hygiene"
    pre-flight) before a finalization drive. KI-ACS-001 already closed the
    headline defect — a directory argument that resolves to zero files now
    exits non-zero instead of printing "No YAML files to validate" and
    exiting 0 (see test_validate_ac_schema_no_op.py). What GE-120a-4 adds on
    top is the boundary the KI-ACS-001 fix must NOT break: a run given no
    targets AT ALL — an empty scope, e.g. a commit-time invocation where no
    matching file was staged — must still report an ordinary pass, because
    the rule fires on targets that were NAMED but not resolved, never on an
    empty scope. Today `main([])` prints a usage message and returns exit
    code 2, not 0 — that is the one genuine gap this AC still has open
    (confirmed in architect-review comment on this ticket).

    Both boundary invocations are exercised here per the AC's own coverage
    note: targets-named-but-unresolved (must fail), and no-targets-empty-scope
    (must pass).

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120a-4.yaml
  - unit_tests/ac_store/test_validate_ac_schema_no_op.py
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
_VALIDATOR_DIR = _REPO_ROOT / "scripts" / "ac_store"

# Import the module directly (in addition to subprocess invocation) so
# test_ge120a4_no_targets_empty_scope_still_passes can assert against
# main([]) as a unit-level check. sys.path[0] mirrors how the script itself
# resolves its sibling `_ac_components` import when invoked directly.
if str(_VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VALIDATOR_DIR))

import validate_ac_schema as _vas  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the validator as a real subprocess — the way every caller reaches it."""
    return subprocess.run(
        [sys.executable, str(_VALIDATOR), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )


_VALID_AC = """\
id: {ac_id}
title: "A placeholder criterion used only to exercise the validator"
component: ac-store
components:
  - ac_store
level: L2
status: active
req_status: draft
work_status: todo
readiness: draft
priority: medium
roadmap_phase: phase_1
criteria: |
  Given a fixture record,
  When the validator reads it,
  Then it is accepted.
depends_on: []
doc_links: []
assigned_agent: python-coder
estimated_complexity: S
origin_agent: BrainCandy
created: 2026-08-25
amended_by: []
superseded_by: null
covered_by: []
implemented_by: []
change_target: docs
test_required: false
test_rationale: "Fixture record; not real work."
notes: "Fixture."
"""

_INVALID_READINESS_AC = _VALID_AC.replace("readiness: draft", "readiness: not-a-real-value")


class TestGe120a4DirectoryArgumentAgainstPopulatedDir(unittest.TestCase):
    """AC-1, AC-2: a directory that genuinely contains AC YAML files must have
    its contents actually inspected — including a genuinely invalid record —
    rather than silently reporting the old "No YAML files to validate" +
    success no-op. Before KI-ACS-001, a directory argument resolved to ZERO
    files regardless of what it contained, so even a directory full of
    invalid records reported success having checked nothing.
    """

    def setUp(self) -> None:
        self.tmpdir = self._make_tmp_dir()
        self.store = self.tmpdir / "guardrail-engine"
        self.store.mkdir(parents=True)
        # Five genuinely valid records (ids must match the AC id regex in
        # config/ac_store_schema.json, hence GE-99N rather than a
        # descriptive-but-invalid placeholder)...
        for i in range(5):
            (self.store / f"GE-99{i}.yaml").write_text(
                _VALID_AC.format(ac_id=f"GE-99{i}"), encoding="utf-8"
            )
        # ...and one genuinely invalid record, so the directory "genuinely
        # contains AC YAML files" (per the AC's Given clause) and one of them
        # is broken.
        (self.store / "GE-9999.yaml").write_text(
            _INVALID_READINESS_AC.format(ac_id="GE-9999"), encoding="utf-8"
        )

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @staticmethod
    def _make_tmp_dir() -> Path:
        import tempfile

        return Path(tempfile.mkdtemp(prefix="ge120a4_"))

    def test_ge120a4_directory_argument_against_populated_dir_reports_failure(self) -> None:
        # covers: GE-120a-4
        result = _run(str(self.store))

        self.assertNotEqual(
            result.returncode,
            0,
            "a directory containing a genuinely invalid AC record must fail — "
            f"reporting success here is the old no-op bug in a new costume. "
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertNotIn(
            "No YAML files to validate",
            result.stdout,
            "the directory was silently treated as zero files instead of "
            f"being walked and validated. stdout: {result.stdout}",
        )
        self.assertIn(
            "GE-9999",
            result.stderr,
            f"the failure must name the offending record. stderr: {result.stderr}",
        )


class TestGe120a4FailureNamesUnresolvedArgument(unittest.TestCase):
    """AC-1: an argument that is NAMED but resolves to zero files states that
    nothing was inspected and names the argument it could not resolve.
    """

    def setUp(self) -> None:
        import tempfile

        self.tmpdir = Path(tempfile.mkdtemp(prefix="ge120a4_"))
        self.empty_dir = self.tmpdir / "empty-scope"
        self.empty_dir.mkdir()

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ge120a4_failure_names_the_unresolved_argument(self) -> None:
        # covers: GE-120a-4
        result = _run(str(self.empty_dir))

        self.assertNotEqual(
            result.returncode,
            0,
            f"a named-but-unresolved argument must fail. stdout: {result.stdout}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "no",
            combined.lower(),
            f"expected a 'nothing was inspected' style message. output: {combined}",
        )
        self.assertIn(
            str(self.empty_dir),
            combined,
            "the failure message must name the argument that could not be "
            f"resolved into files. output: {combined}",
        )


class TestGe120a4ResolvingFileArgumentsUnaffected(unittest.TestCase):
    """AC-3: an invocation whose named targets DO resolve to files is
    unaffected and reports exactly as before.
    """

    def setUp(self) -> None:
        import tempfile

        self.tmpdir = Path(tempfile.mkdtemp(prefix="ge120a4_"))
        self.ac_file = self.tmpdir / "GE-9990.yaml"
        self.ac_file.write_text(_VALID_AC.format(ac_id="GE-9990"), encoding="utf-8")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ge120a4_resolving_file_arguments_unaffected(self) -> None:
        # covers: GE-120a-4
        result = _run(str(self.ac_file))

        self.assertEqual(
            result.returncode,
            0,
            f"an explicit file path that resolves must pass unaffected. "
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn("OK", result.stdout)


class TestGe120a4NoTargetsEmptyScopeStillPasses(unittest.TestCase):
    """AC-4: an invocation given NO targets at all, in a context where
    nothing is in scope, must still report an ordinary pass — the rule fires
    on targets that were named but not resolved, never on an empty scope.

    RED today: main([]) prints a usage message and returns exit code 2, not
    the ordinary pass (0) this AC requires. This is the one genuine
    implementation gap this ticket leaves open (see architect-review comment
    on this ticket, which traced AC-1/AC-2/AC-3/AC-5 to an already-landed fix
    but flagged this exact boundary as unresolved).
    """

    def test_ge120a4_no_targets_empty_scope_still_passes(self) -> None:
        # covers: GE-120a-4
        exit_code = _vas.main([])

        self.assertEqual(
            exit_code,
            0,
            "an invocation with no targets named at all (empty scope) must "
            f"report an ordinary pass (0), not a usage/error code. got: {exit_code}. "
            "The rule must fire on targets NAMED but unresolved, never on an "
            "empty scope — this is the AC-4 boundary this ticket must implement.",
        )


class TestGe120a4UnresolvableArgumentFormStillFailsAfterExpansion(unittest.TestCase):
    """AC-5: even after directory-expansion convenience handling exists, an
    argument form the validator still cannot resolve into files must produce
    the reported failure — the criterion is not satisfied by teaching the
    validator to expand directory arguments alone.
    """

    def setUp(self) -> None:
        import tempfile

        self.tmpdir = Path(tempfile.mkdtemp(prefix="ge120a4_"))
        # A named path that plainly cannot resolve to any AC YAML, even with
        # directory-expansion in place: a file that does not exist.
        self.nonexistent = self.tmpdir / "does-not-exist.yaml"
        # A named, existing, non-YAML file — also unresolvable into AC records.
        self.stray = self.tmpdir / "notes.md"
        self.stray.write_text("not an AC\n", encoding="utf-8")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ge120a4_unresolvable_argument_form_still_fails_after_expansion(self) -> None:
        # covers: GE-120a-4
        missing_result = _run(str(self.nonexistent))
        self.assertNotEqual(
            missing_result.returncode,
            0,
            "a nonexistent path must still fail even with directory-expansion "
            f"in place. stdout: {missing_result.stdout}\nstderr: {missing_result.stderr}",
        )

        stray_result = _run(str(self.stray))
        self.assertNotEqual(
            stray_result.returncode,
            0,
            "a named, existing, non-YAML file resolves to nothing and must "
            f"still fail. stdout: {stray_result.stdout}\nstderr: {stray_result.stderr}",
        )


class TestGe120a4ReachableFromEntryPoint(unittest.TestCase):
    """Reachability floor: exercise the REAL CLI entry point (subprocess,
    __main__ -> sys.exit(main())) with a bare invocation and no arguments —
    not `main([])` imported directly — and assert the AC-4 behaviour actually
    occurs end-to-end. Importing the function is not sufficient: this proves
    the fix is wired all the way through argv -> main() -> process exit code,
    which is what every real caller (a human at a shell, or a future
    commit-time wrapper) actually observes.
    """

    def test_ge_120a_4_reachable_from_entry_point(self) -> None:
        # covers: GE-120a-4
        result = _run()  # zero argv — the real subprocess entry point, no args at all

        self.assertEqual(
            result.returncode,
            0,
            "invoking the real CLI entry point with no arguments at all must "
            f"exit 0 (ordinary pass), not a usage/error code. "
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
