"""
MODULE: test_bp_1100b_5
GOAL: Unit tests for the (not-yet-implemented) presence-only-assertion guard,
    templates/scripts/commit_guardian/check_presence_only_assertions.py — a
    NEW staged-hunk pre-commit hook that rejects newly added tests over
    workflow/commit-guardian source whose entire "coverage" is a grep for a
    symbol's presence (a substring check or a regex-declaration check), the
    exact defect class BP-1100b-4 exists to fix in one confirmed incumbent.
BUSINESS CONTEXT: EPIC-BuildPipelinePhantomRemediation's own thesis, turned on
    the epic's own evidence base — a test can no longer prove a guard works
    by grepping for its name. This hook is the mechanical ratchet: it reads
    STAGED HUNKS ONLY (never a whole-file/whole-tree scan), so the 46
    pre-existing violations already in unit_tests/workflows/ and
    unit_tests/commit_guardian/ do not make the hook's own introducing
    commit unmergeable. Nothing new lands; the backlog is a separate sweep.
ARCHITECTURE / TEST-DESIGN NOTE (self-consistency, mandatory per this
    ticket): every test below actually EXECUTES the hook — as a subprocess,
    against a synthesized staged diff — never a test that greps
    check_presence_only_assertions.py's own source for a function name. A
    test doing the latter would be an instance of the exact defect this hook
    exists to reject.

    Test interface contract this test file specifies for python-coder
    (mirrors two conventions already established elsewhere in
    commit_guardian/, see check_contract_shrinking.py and config.py):

      HOOK_TEST_DIFF   (existing convention, check_contract_shrinking.py):
        path to a file containing the synthetic staged diff text, used
        instead of a real `git diff --cached` call.

      HOOK_TEST_CONFIG (NEW convention introduced by this ticket): path to a
        JSON file containing ONLY the `presence_only_assertion_guard` config
        section (enabled / scanned_source_globs / waiver_marker), used
        instead of loading commit_guardian.json via config.py. This lets
        tests control the scanned-source glob set and waiver marker per-case
        without mutating the real commit_guardian.json (AC: the glob set
        must be DATA read from config, never hardcoded in the hook — this
        env var is how a test proves that without monkeypatching internals).

    When neither env var is set, the hook must fall back to its production
    behaviour: `git diff --cached` and commit_guardian.json's
    `presence_only_assertion_guard` key (both per the n_location_rule '2'
    registration this ticket also requires).
TICKET: 09_bp1100b45_presence_only_assertions_stop_counting.md
AC: BP-1100b-5
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# The hook script that will be created by python-coder (does not exist yet —
# these tests are RED). Canonical template source per ADR-001 self-hosting.
HOOK_SCRIPT = (
    _REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_presence_only_assertions.py"
)
_BUILD_SCRIPT = _REPO_ROOT / "scripts" / "build.py"

_SUBPROCESS_TIMEOUT_SECONDS = 15
_BUILD_TIMEOUT_SECONDS = 60

_DEFAULT_TEST_CONFIG = {
    "enabled": True,
    "scanned_source_globs": [
        "templates/workflows-js/*.js",
        "templates/scripts/commit_guardian/*.py",
    ],
    "waiver_marker": "presence-only",
}


def _run_hook(
    diff_content: str,
    config: dict | None = _DEFAULT_TEST_CONFIG,
    cwd: Path | None = None,
    hook_script: Path | None = None,
) -> subprocess.CompletedProcess:
    """Execute the REAL hook script as a subprocess against a synthesized
    staged diff — see module docstring for the HOOK_TEST_DIFF / HOOK_TEST_CONFIG
    interface contract this test file specifies.

    Args:
        diff_content: Synthetic `git diff --cached`-shaped text.
        config: The presence_only_assertion_guard config section to inject via
            HOOK_TEST_CONFIG. Pass None to omit HOOK_TEST_CONFIG entirely
            (exercise the hook's own commit_guardian.json fallback).
        cwd: Working directory for the subprocess. Defaults to the repo root.
        hook_script: Override the hook script path (used by the
            deployed-layout test to run the post-build copy instead of the
            templates/ source).

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".diff", delete=False, encoding="utf-8"
    ) as f:
        f.write(diff_content)
        diff_path = f.name

    config_path: str | None = None
    if config is not None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(config, f)
            config_path = f.name

    env = os.environ.copy()
    env["HOOK_TEST_DIFF"] = diff_path
    if config_path is not None:
        env["HOOK_TEST_CONFIG"] = config_path

    script = hook_script if hook_script is not None else HOOK_SCRIPT

    try:
        return subprocess.run(
            [sys.executable, str(script)],
            cwd=str(cwd) if cwd is not None else str(_REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    finally:
        os.unlink(diff_path)
        if config_path is not None:
            os.unlink(config_path)


class TestSubstringFormReported(unittest.TestCase):
    """AC-6, AC-7: the substring presence-assertion form is reported, naming
    the test file, the asserted symbol, and the scanned source file.
    """

    def test_unwaived_substring_presence_assertion_is_reported_with_file_symbol_and_source(
        self,
    ):
        # covers: BP-1100b-5
        """A staged diff adding a substring presence assertion over a
        scanned-source file (mirroring the confirmed incumbent at
        test_deploy_collision_guard.py:741 — `assert 'Workflow(\"build-feature\"'
        in content`) must be reported by name of the test file, the asserted
        symbol, and the source file scanned.
        """
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/build_guards/test_new_guard_wiring_bp1100b5.py b/unit_tests/build_guards/test_new_guard_wiring_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/build_guards/test_new_guard_wiring_bp1100b5.py
            +++ b/unit_tests/build_guards/test_new_guard_wiring_bp1100b5.py
            @@ -10,6 +10,10 @@ class TestNewGuardWiring(unittest.TestCase):
                 def test_new_guard_is_wired(self):
            +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        assert 'Workflow("build-feature"' in content
            """
        )
        result = _run_hook(diff)

        self.assertEqual(
            result.returncode,
            1,
            msg=f"Hook should exit 1. stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "test_new_guard_wiring_bp1100b5.py",
            combined,
            msg=f"Report does not name the test file. Output:\n{combined}",
        )
        self.assertIn(
            "Workflow(",
            combined,
            msg=f"Report does not name the asserted symbol. Output:\n{combined}",
        )
        self.assertIn(
            "finalize-feature.js",
            combined,
            msg=f"Report does not name the source file the assertion scans. Output:\n{combined}",
        )


class TestRegexDeclarationFormAlsoReported(unittest.TestCase):
    """AC-7: the regex-declaration form (matches confirmed incumbent
    unit_tests/workflows/test_bo_1000c_1a.py) is ALSO matched, not only the
    substring form.
    """

    def test_regex_declaration_presence_assertion_is_also_reported(self):
        # covers: BP-1100b-5
        """A staged diff adding a regex-declaration presence assertion
        (`re.compile(r"function\\s+<name>\\s*\\(").search(<content>)`) over a
        scanned-source file must be reported, mirroring the confirmed
        incumbent test_ac1_journal_append_mechanism_defined_in_js.
        """
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/workflows/test_new_regex_wiring_bp1100b5.py b/unit_tests/workflows/test_new_regex_wiring_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/workflows/test_new_regex_wiring_bp1100b5.py
            +++ b/unit_tests/workflows/test_new_regex_wiring_bp1100b5.py
            @@ -10,6 +10,12 @@ class TestNewRegexWiring(unittest.TestCase):
                 def test_helper_defined(self):
            +        _HELPER_DEFINITION = re.compile(r"function\\s+someBrandNewHelper\\s*\\(")
            +        js = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        self.assertTrue(bool(_HELPER_DEFINITION.search(js)))
            """
        )
        result = _run_hook(diff)

        self.assertEqual(
            result.returncode,
            1,
            msg=f"Hook should exit 1. stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "test_new_regex_wiring_bp1100b5.py",
            combined,
            msg=f"Report does not name the test file. Output:\n{combined}",
        )
        self.assertIn(
            "someBrandNewHelper",
            combined,
            msg=f"Report does not name the asserted symbol. Output:\n{combined}",
        )
        self.assertIn(
            "finalize-feature.js",
            combined,
            msg=f"Report does not name the source file the assertion scans. Output:\n{combined}",
        )


class TestReportStatesRationaleAndWaiverRoute(unittest.TestCase):
    """AC-6: the report explains WHY presence-only assertions are rejected
    and names the waiver as the deliberate-acceptance route.
    """

    def test_report_states_the_unreachable_code_rationale_and_names_the_waiver(self):
        # covers: BP-1100b-5
        """The hook's emitted report must state that a presence-only
        assertion stays green on unreachable code (so it is not coverage),
        and must name the `# presence-only: <reason>` waiver as the route
        for deliberate acceptance.
        """
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/build_guards/test_rationale_bp1100b5.py b/unit_tests/build_guards/test_rationale_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/build_guards/test_rationale_bp1100b5.py
            +++ b/unit_tests/build_guards/test_rationale_bp1100b5.py
            @@ -10,6 +10,10 @@ class TestRationale(unittest.TestCase):
                 def test_wired(self):
            +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        assert 'Workflow("build-feature"' in content
            """
        )
        result = _run_hook(diff)

        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            "unreachable code",
            combined,
            msg=f"Report does not state the unreachable-code rationale. Output:\n{combined}",
        )
        self.assertIn(
            "not coverage",
            combined,
            msg=f"Report does not state that presence-only is not coverage. Output:\n{combined}",
        )
        self.assertIn(
            "# presence-only:",
            combined,
            msg=f"Report does not name the waiver marker syntax. Output:\n{combined}",
        )


class TestWaiverSuppressesWithNonEmptyReason(unittest.TestCase):
    """AC-8: a `# presence-only: <reason>` waiver with a non-empty reason
    suppresses the violation and is listed with its reason.
    """

    def test_waived_assertion_is_not_reported_and_its_reason_is_listed(self):
        # covers: BP-1100b-5
        """An added assertion preceded by `# presence-only: <reason>` with a
        non-empty reason is not reported as a violation, and the waiver
        together with its reason appears in the executed hook's output.
        """
        reason = "unreachable under current harness fidelity; tracked in BP-1100b-4 follow-up"
        diff = textwrap.dedent(
            f"""\
            diff --git a/unit_tests/build_guards/test_waived_bp1100b5.py b/unit_tests/build_guards/test_waived_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/build_guards/test_waived_bp1100b5.py
            +++ b/unit_tests/build_guards/test_waived_bp1100b5.py
            @@ -10,6 +10,11 @@ class TestWaived(unittest.TestCase):
                 def test_wired(self):
            +        # presence-only: {reason}
            +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        assert 'Workflow("build-feature"' in content
            """
        )
        result = _run_hook(diff)

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "A waiver with a non-empty reason must suppress the violation. "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            reason,
            combined,
            msg=f"Waiver reason is not listed in the hook's output. Output:\n{combined}",
        )


class TestWaiverWithEmptyReasonDoesNotSuppress(unittest.TestCase):
    """AC-8: a waiver marker with an empty or whitespace-only reason must NOT
    suppress the violation — the marker cannot become a silent suppression
    list.
    """

    def test_waiver_with_an_empty_reason_does_not_suppress_the_violation(self):
        # covers: BP-1100b-5
        for label, waiver_line in [
            ("empty", "        # presence-only:"),
            ("whitespace-only", "        # presence-only:    "),
        ]:
            with self.subTest(reason=label):
                diff = textwrap.dedent(
                    f"""\
                    diff --git a/unit_tests/build_guards/test_empty_waiver_bp1100b5.py b/unit_tests/build_guards/test_empty_waiver_bp1100b5.py
                    index abc..def 100644
                    --- a/unit_tests/build_guards/test_empty_waiver_bp1100b5.py
                    +++ b/unit_tests/build_guards/test_empty_waiver_bp1100b5.py
                    @@ -10,6 +10,11 @@ class TestEmptyWaiver(unittest.TestCase):
                         def test_wired(self):
                    +{waiver_line}
                    +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
                    +        assert 'Workflow("build-feature"' in content
                    """
                )
                result = _run_hook(diff)

                self.assertEqual(
                    result.returncode,
                    1,
                    msg=(
                        f"A waiver with a {label} reason must NOT suppress the "
                        f"violation. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                    ),
                )


class TestFixtureExemptPathIsNotScanned(unittest.TestCase):
    """BP-1100b-5 (self-maintenance): added lines in a file listed under
    ``fixture_exempt_paths`` are not scanned, so this guard's own test file —
    which must contain literal examples of the pattern the guard detects — does
    not block its own maintenance.

    Found live: this guard blocked the very commit that introduced it, flagging
    ten of its own synthetic diff fixtures. The ``# presence-only:`` waiver
    cannot address that case, because a waiver placed inside a fixture is
    consumed by the scanner under test and inverts what the fixture asserts.
    """

    def test_added_lines_in_an_exempt_path_produce_no_violation(self):
        # covers: BP-1100b-5
        exempt_path = "unit_tests/commit_guardian/test_bp_1100b_5.py"
        diff = textwrap.dedent(
            f"""\
            diff --git a/{exempt_path} b/{exempt_path}
            index abc..def 100644
            --- a/{exempt_path}
            +++ b/{exempt_path}
            @@ -10,6 +10,9 @@ class TestSomething(unittest.TestCase):
                 def test_fixture(self):
            +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        assert 'doSomething(' in content
            """
        )
        config = dict(_DEFAULT_TEST_CONFIG)
        config["fixture_exempt_paths"] = [exempt_path]

        result = _run_hook(diff, config=config)

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Added lines in a fixture_exempt_paths file must not be scanned. "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )

    def test_the_same_lines_still_violate_when_the_path_is_not_exempt(self):
        # covers: BP-1100b-5
        # Discrimination guard: proves the exemption is what suppresses the
        # violation above, not the fixture content being harmless.
        exempt_path = "unit_tests/commit_guardian/test_bp_1100b_5.py"
        diff = textwrap.dedent(
            f"""\
            diff --git a/{exempt_path} b/{exempt_path}
            index abc..def 100644
            --- a/{exempt_path}
            +++ b/{exempt_path}
            @@ -10,6 +10,9 @@ class TestSomething(unittest.TestCase):
                 def test_fixture(self):
            +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        assert 'doSomething(' in content
            """
        )
        config = dict(_DEFAULT_TEST_CONFIG)
        config["fixture_exempt_paths"] = []

        result = _run_hook(diff, config=config)

        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "With an empty fixture_exempt_paths the identical diff must still "
                "be reported — otherwise the exemption test above proves nothing. "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )


class TestUnscannedFileIsNotReported(unittest.TestCase):
    """AC-9 (scope): an assertion over a file matched by none of the
    configured scanned-source globs produces no violation.
    """

    def test_presence_assertion_over_an_unscanned_file_is_not_reported(self):
        # covers: BP-1100b-5
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/other_area/test_unrelated_bp1100b5.py b/unit_tests/other_area/test_unrelated_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/other_area/test_unrelated_bp1100b5.py
            +++ b/unit_tests/other_area/test_unrelated_bp1100b5.py
            @@ -10,6 +10,9 @@ class TestUnrelated(unittest.TestCase):
                 def test_wired(self):
            +        content = Path("some_other_project/unrelated_module.py").read_text()
            +        assert 'doSomething(' in content
            """
        )
        result = _run_hook(diff)

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "An assertion over a file matched by no scanned_source_globs entry "
                f"must not be reported. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )


class TestPreexistingAssertionsInUntouchedFilesAreNotReported(unittest.TestCase):
    """AC-9: staged-hunks-only scope. Run against the REAL repo (which
    already contains 46 confirmed presence-only violations in
    unit_tests/workflows/ and unit_tests/commit_guardian/), with a staged
    diff touching none of them — the hook must report nothing.
    """

    def test_preexisting_assertions_in_untouched_files_are_not_reported(self):
        # covers: BP-1100b-5
        diff = textwrap.dedent(
            """\
            diff --git a/README.md b/README.md
            index abc..def 100644
            --- a/README.md
            +++ b/README.md
            @@ -1,3 +1,4 @@
             # Leafcutter
            +Some unrelated documentation update (BP-1100b-5 calibration).
            """
        )
        # cwd=_REPO_ROOT: the REAL repo tree, which genuinely contains the 46
        # pre-existing presence-only violations this ticket's "Out of Scope"
        # section references. If the hook whole-file/whole-tree scanned
        # instead of reading only the staged diff, it would find them here.
        result = _run_hook(diff, cwd=_REPO_ROOT)

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "A diff touching only an unrelated file must produce zero violations "
                f"— even in a real tree with pre-existing offenders. "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "finalize-feature.js",
            combined,
            msg=(
                "Hook output references finalize-feature.js despite the diff never "
                f"touching it — evidence of a whole-tree scan, not staged-hunks-only. "
                f"Output:\n{combined}"
            ),
        )
        self.assertNotIn(
            "appendJournal",
            combined,
            msg=f"Hook output references a pre-existing untouched violation. Output:\n{combined}",
        )


class TestNewViolationReportedRegardlessOfSourceCoModification(unittest.TestCase):
    """AC-9 (ratchet correctness): a new violation is reported whether or not
    the same staged diff also modifies the scanned source file.
    """

    def test_new_violation_reported_regardless_of_author_or_source_co_modification(
        self,
    ):
        # covers: BP-1100b-5
        diff = textwrap.dedent(
            """\
            diff --git a/templates/workflows-js/finalize-feature.js b/templates/workflows-js/finalize-feature.js
            index abc..def 100644
            --- a/templates/workflows-js/finalize-feature.js
            +++ b/templates/workflows-js/finalize-feature.js
            @@ -10,6 +10,7 @@ function narrate(progressText, description) {
               const line = progressText + ': ' + description;
               log(line);
            +  // unrelated comment, co-modifying the scanned source itself
             }
            diff --git a/unit_tests/build_guards/test_comodified_bp1100b5.py b/unit_tests/build_guards/test_comodified_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/build_guards/test_comodified_bp1100b5.py
            +++ b/unit_tests/build_guards/test_comodified_bp1100b5.py
            @@ -10,6 +10,10 @@ class TestComodified(unittest.TestCase):
                 def test_wired(self):
            +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        assert 'Workflow("build-feature"' in content
            """
        )
        result = _run_hook(diff)

        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "A new presence-only assertion must be reported even when the same "
                f"diff also modifies the scanned source file. stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )


class TestDocumentationMarkerIsNotOverMatched(unittest.TestCase):
    """AC-10: calibration against the named non-target — a literal AC-id
    documentation marker (unit_tests/workflows/test_bo_1000a_2_i.py ~L166)
    is NOT a presence-only behavioural claim and must not be flagged.
    """

    def test_documentation_marker_assertion_is_not_over_matched(self):
        # covers: BP-1100b-5
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/workflows/test_doc_marker_bp1100b5.py b/unit_tests/workflows/test_doc_marker_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/workflows/test_doc_marker_bp1100b5.py
            +++ b/unit_tests/workflows/test_doc_marker_bp1100b5.py
            @@ -10,6 +10,14 @@ class TestDocMarker(unittest.TestCase):
                 def test_ac_referenced(self):
            +        js = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        self.assertIn(
            +            "BP-1100b-5-CALIBRATION-MARKER",
            +            js,
            +        )
            +
                 def test_real_behavioural_claim(self):
            +        js2 = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        self.assertIn('someRealHelperFunction(', js2)
            """
        )
        result = _run_hook(diff)

        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "The real behavioural-claim assertion in the same diff must still be "
                f"reported. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "BP-1100b-5-CALIBRATION-MARKER",
            combined,
            msg=(
                "The documentation-marker (literal AC-id) assertion was over-matched "
                f"and reported as a violation. Output:\n{combined}"
            ),
        )
        self.assertIn(
            "someRealHelperFunction",
            combined,
            msg=f"The real behavioural-claim assertion was not reported. Output:\n{combined}",
        )


class TestScannedSourceGlobsAreReadFromConfig(unittest.TestCase):
    """AC (implementation note): scanned_source_globs is DATA read from the
    guardian config, never hardcoded in the hook.
    """

    def test_scanned_source_globs_are_read_from_the_guardian_config(self):
        # covers: BP-1100b-5
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/build_guards/test_glob_config_bp1100b5.py b/unit_tests/build_guards/test_glob_config_bp1100b5.py
            index abc..def 100644
            --- a/unit_tests/build_guards/test_glob_config_bp1100b5.py
            +++ b/unit_tests/build_guards/test_glob_config_bp1100b5.py
            @@ -10,6 +10,14 @@ class TestGlobConfig(unittest.TestCase):
                 def test_wired_a(self):
            +        content_a = Path("templates/workflows-js/finalize-feature.js").read_text()
            +        assert 'Workflow("build-feature"' in content_a
            +
                 def test_wired_b(self):
            +        content_b = Path("templates/scripts/commit_guardian/check_ac_schema.py").read_text()
            +        assert 'def validate_schema(' in content_b
            """
        )

        only_js_config = {
            "enabled": True,
            "scanned_source_globs": ["templates/workflows-js/*.js"],
            "waiver_marker": "presence-only",
        }
        only_py_config = {
            "enabled": True,
            "scanned_source_globs": ["templates/scripts/commit_guardian/*.py"],
            "waiver_marker": "presence-only",
        }

        result_js_only = _run_hook(diff, config=only_js_config)
        result_py_only = _run_hook(diff, config=only_py_config)

        combined_js_only = result_js_only.stdout + result_js_only.stderr
        combined_py_only = result_py_only.stdout + result_py_only.stderr

        self.assertIn(
            "finalize-feature.js",
            combined_js_only,
            msg=f"With only the .js glob configured, the .js violation must be reported. Output:\n{combined_js_only}",
        )
        self.assertNotIn(
            "check_ac_schema.py",
            combined_js_only,
            msg=f"With only the .js glob configured, the .py file must not be reported. Output:\n{combined_js_only}",
        )

        self.assertIn(
            "check_ac_schema.py",
            combined_py_only,
            msg=f"With only the .py glob configured, the .py violation must be reported. Output:\n{combined_py_only}",
        )
        self.assertNotIn(
            "finalize-feature.js",
            combined_py_only,
            msg=f"With only the .py glob configured, the .js file must not be reported. Output:\n{combined_py_only}",
        )


class TestDeployedHookRunsAndReportsAfterBuild(unittest.TestCase):
    """AC (deployed-layout verification): after build.py deploys, the hook
    copy under scripts/commit_guardian/ runs and reports — proving the
    hooks_manifest entry and deploy manifest are wired, not just the
    templates/ source.
    """

    def test_deployed_hook_runs_and_reports_after_build(self):
        # covers: BP-1100b-5
        with tempfile.TemporaryDirectory() as tmp:
            build_result = subprocess.run(
                [sys.executable, str(_BUILD_SCRIPT), "--target-dir", tmp],
                capture_output=True,
                text=True,
                timeout=_BUILD_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                build_result.returncode,
                0,
                msg=(
                    f"build.py failed to deploy to a fresh target dir. "
                    f"stdout:\n{build_result.stdout}\nstderr:\n{build_result.stderr}"
                ),
            )

            deployed_hook = (
                Path(tmp)
                / "scripts"
                / "commit_guardian"
                / "check_presence_only_assertions.py"
            )
            self.assertTrue(
                deployed_hook.exists(),
                msg=(
                    f"check_presence_only_assertions.py was not deployed to {deployed_hook}. "
                    "Add it to the build deploy manifest for scripts/commit_guardian/."
                ),
            )

            diff = textwrap.dedent(
                """\
                diff --git a/unit_tests/build_guards/test_deployed_bp1100b5.py b/unit_tests/build_guards/test_deployed_bp1100b5.py
                index abc..def 100644
                --- a/unit_tests/build_guards/test_deployed_bp1100b5.py
                +++ b/unit_tests/build_guards/test_deployed_bp1100b5.py
                @@ -10,6 +10,10 @@ class TestDeployed(unittest.TestCase):
                     def test_wired(self):
                +        content = Path("templates/workflows-js/finalize-feature.js").read_text()
                +        assert 'Workflow("build-feature"' in content
                """
            )
            result = _run_hook(diff, cwd=Path(tmp), hook_script=deployed_hook)

            self.assertNotIn(
                "ModuleNotFoundError",
                result.stderr,
                msg=(
                    "Deployed hook crashed importing a dependency not present in the "
                    f"deploy manifest. stderr:\n{result.stderr}"
                ),
            )
            self.assertEqual(
                result.returncode,
                1,
                msg=(
                    "Deployed hook did not report the violation. "
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
