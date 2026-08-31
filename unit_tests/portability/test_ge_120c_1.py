"""
MODULE: test_ge_120c_1
AC: GE-120c-1 — "A harness executes the deployed checks out of process from a
    real separate working copy"
GOAL: Behavioral tests for `_deployed_check_harness.DeployedCheckHarness`,
    proving the harness itself satisfies GE-120c-1's Gherkin clauses on real
    artifacts: a real second working copy (independent git index + a real
    `scripts/build.py` deploy), real subprocess invocation in both entry
    shapes the commit path uses, a real subprocess environment with the
    source tree scrubbed off the import path, a genuine self-demonstration
    that the harness can FAIL on a check that resolves prerequisites only
    via the source tree, and a report carrying both copies' status/output
    per check.

WHY test-writer BUILT THE HARNESS ITSELF (not python-coder): this AC's own
    YAML (`docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/
    GE-120c-1.yaml`) sets `assigned_agent: test-writer` and this ticket's
    frontmatter carries no coder agent in its dispatch chain — by design, per
    the IT-PO's own note: "the deliverable is verification apparatus, and the
    failure mode being guarded against is an implementer building a harness
    shaped to pass against their own fix." There is therefore no follow-on
    coder phase to hand a red baseline to; the harness is implemented here,
    directly, and these tests are the evidence it works.

REAL-ARTIFACT NOTE: every test below builds or uses a REAL deployed working
    copy (a real `git init` + a real `scripts/build.py --target-dir` run —
    never a hand-built directory tree) and invokes REAL subprocesses. No
    check module, commit_guardian helper, or `_resolve_root.py` is ever
    imported by the harness or by these tests.

RUNTIME NOTE: `setUpClass` builds two real ephemeral working copies via the
    real `scripts/build.py` (a few seconds each). This deliberately exceeds
    the project's default 5s-per-test guideline — per this AC's own
    it_requirements ("RUNTIME BUDGET... mark the sweep slow rather than
    letting it quietly narrow its subject list to stay fast"), a harness that
    only exercises real subprocesses against real deployed copies cannot be
    made instant without ceasing to test the real thing.
"""
# @ac-tag: GE-120c-1

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root

sys.path.insert(0, str(_THIS_DIR))

import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture check scripts. Real production entry shapes (run_hook.py-wrapped
# and direct-script) are exercised against these deterministic, fast fixture
# CHECKS rather than a real commit_guardian check, so runtime and behaviour
# do not depend on a real check's repo-scan cost or staged-file requirements.
# The invocation machinery under test (build_argv/invoke_check/run_sweep) is
# 100% real production code from _deployed_check_harness.py.
# ---------------------------------------------------------------------------
_WRAPPED_PROBE_SCRIPT = (
    '"""Deterministic fixture check for GE-120c-1\'s own test suite: exercises '
    'the run_hook.py-wrapped invocation shape."""\n'
    'print("GE120C1_WRAPPED_PROBE_OK")\n'
)

_CWD_PROBE_SCRIPT = (
    '"""Deterministic fixture check that makes the invoked subprocess\'s cwd '
    'and PYTHONPATH observable, for GE-120c-1\'s own test suite."""\n'
    "import os\n"
    'print(f"CWD:{os.getcwd()}")\n'
    'print(f"PYTHONPATH_ENV:{os.environ.get(\'PYTHONPATH\', \'\')}")\n'
)

# A check that can ONLY resolve its prerequisite via the SOURCE TREE: it
# walks up from its own file location to find a `.git` directory, then
# requires `<repo_root>/scripts/build_phases.py` to exist. That file is part
# of the real source checkout and is never produced by a
# `scripts/build.py --target-dir` deploy (confirmed empirically: a real
# build into an empty target dir produces no top-level build_phases.py — see
# this ticket's Implementation Notes), so this import succeeds only when the
# process is genuinely running against the source tree and fails against a
# deployed-only second copy. This IS the defect class GE-120c-1 exists to
# detect — one of the "19 un-migrated files" the AC's self-demonstration
# clause names, reproduced here as a minimal, controlled fixture so the test
# is deterministic rather than depending on which real checks have or have
# not migrated yet.
_SOURCE_TREE_ONLY_CHECK_SCRIPT = (
    '"""Fixture check that can only resolve its prerequisite via the SOURCE '
    'TREE (GE-120c-1 self-demonstration fixture). Mirrors the real shape of '
    'the "19 un-migrated" checks named in this AC\'s it_requirements: walk up '
    'to find the repo root, sys.path.insert the source scripts/ dir, then '
    "import a module that lives ONLY in the source checkout. Against a "
    "deployed-only second copy this raises a real ModuleNotFoundError, "
    'exactly the failure shape those checks hit today."""\n'
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "here = Path(__file__).resolve()\n"
    "root = here\n"
    'while not (root / ".git").exists() and root != root.parent:\n'
    "    root = root.parent\n"
    "\n"
    'sys.path.insert(0, str(root / "scripts"))\n'
    "import build_phases  # noqa: F401 -- only importable from the source tree\n"
    "\n"
    'print("SOURCE_TREE_PREREQUISITE_FOUND")\n'
)

_WRAPPED_PROBE_HOOK = {
    "id": "ge120c1-wrapped-probe",
    "entry": (
        "python {{config.output_root}}/scripts/commit_guardian/run_hook.py "
        "{{config.output_root}}/scripts/commit_guardian/_ge120c1_wrapped_probe.py"
    ),
    "pass_filenames": False,
}
_CWD_PROBE_HOOK = {
    "id": "ge120c1-cwd-probe",
    "entry": (
        "python {{config.output_root}}/scripts/commit_guardian/run_hook.py "
        "{{config.output_root}}/scripts/commit_guardian/_ge120c1_cwd_probe.py"
    ),
    "pass_filenames": False,
}
_SOURCE_TREE_ONLY_HOOK = {
    "id": "ge120c1-source-tree-only-check",
    "entry": (
        "python {{config.output_root}}/scripts/commit_guardian/run_hook.py "
        "{{config.output_root}}/scripts/commit_guardian/_ge120c1_source_tree_only_check.py"
    ),
    "pass_filenames": False,
}


def _write_probe_scripts(copy_dir: Path) -> None:
    """Write GE-120c-1's own fixture checks into a deployed copy's REAL
    .leafcutter/scripts/commit_guardian/ directory."""
    deployed_cg = copy_dir / ".leafcutter" / "scripts" / "commit_guardian"
    (deployed_cg / "_ge120c1_wrapped_probe.py").write_text(_WRAPPED_PROBE_SCRIPT, encoding="utf-8")
    (deployed_cg / "_ge120c1_cwd_probe.py").write_text(_CWD_PROBE_SCRIPT, encoding="utf-8")
    (deployed_cg / "_ge120c1_source_tree_only_check.py").write_text(
        _SOURCE_TREE_ONLY_CHECK_SCRIPT, encoding="utf-8",
    )


class TestDeployedCheckHarnessGE120c1(unittest.TestCase):
    """Shared, expensive fixture: build TWO real ephemeral deployed-only
    working copies via the real scripts/build.py ONCE for the whole class.
    Per this AC's own RUNTIME BUDGET requirement ("Build each copy ONCE per
    sweep, never per check"), extended here to "once per test class"."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(cls._tmp.name)
        cls.copy_a = tmp_root / "copy_a"
        cls.copy_b = tmp_root / "copy_b"
        cls.harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        cls.harness.create_second_copy(cls.copy_a)
        cls.harness.create_second_copy(cls.copy_b)
        _write_probe_scripts(cls.copy_a)
        _write_probe_scripts(cls.copy_b)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # ------------------------------------------------------------------
    def test_ge120c1_harness_creates_real_second_copy_and_stages_files(self) -> None:
        """AC-1: it creates a real second working copy of the repository
        and stages real files in it, with a real git index rather than a
        simulated one."""
        # covers: GE-120c-1
        # angle: real_artifact
        self.assertTrue(
            self.harness.deployed_layout_present(self.copy_b),
            "create_second_copy() must produce a real "
            ".leafcutter/scripts/commit_guardian/ layout via an actual "
            "scripts/build.py run, not a simulated/hand-built one.",
        )

        staged = self.harness.stage_files(
            self.copy_b,
            {"docs/ge120c1_probe.md": "# GE-120c-1 staging probe\n"},
        )
        self.assertEqual(staged, ["docs/ge120c1_probe.md"])

        # Assert against the REAL git index (git diff --cached), not a
        # Python-side simulation of "is this file staged".
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(self.copy_b), "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "docs/ge120c1_probe.md",
            result.stdout.splitlines(),
            "The staged file must appear in the real git index (git diff "
            f"--cached), not merely written to disk. git output:\n{result.stdout}",
        )

    # ------------------------------------------------------------------
    def test_ge120c1_check_invoked_as_separate_process_in_commit_path_form(self) -> None:
        """AC-1/AC-2: the check is invoked as a separate process using the
        entry shape .pre-commit-config.yaml declares (run_hook.py wrapper —
        read from the REAL deployed manifest, not hand-typed), and also the
        direct-script form used by precommit-canary."""
        # covers: GE-120c-1
        # angle: reachability
        manifest_hooks = self.harness._manifest_hooks(self.copy_b)  # noqa: SLF001
        canary_hooks = [h for h in manifest_hooks if h.get("id") == "precommit-canary"]
        self.assertTrue(
            canary_hooks,
            "precommit-canary must be present in the real deployed manifest "
            f"at {self.copy_b}.",
        )
        canary_entry = canary_hooks[0]["entry"]
        self.assertNotIn(
            "run_hook.py", canary_entry,
            "precommit-canary's real manifest entry must be the DIRECT-SCRIPT "
            f"form (no run_hook.py wrapper) — got: {canary_entry!r}",
        )

        direct_outcome = self.harness.invoke_check(self.copy_b, canary_entry, [])
        self.assertEqual(
            direct_outcome.exit_code, 0,
            f"Direct-script invocation of precommit-canary failed: {direct_outcome.output}",
        )
        self.assertIn(
            "PRECOMMIT_CANARY_OK",
            direct_outcome.output,
            "The direct-script form must produce the real canary's own "
            f"observable output. Got: {direct_outcome.output}",
        )

        wrapped_outcome = self.harness.invoke_check(self.copy_b, _WRAPPED_PROBE_HOOK["entry"], [])
        self.assertEqual(
            wrapped_outcome.exit_code, 0,
            f"run_hook.py-wrapped invocation failed: {wrapped_outcome.output}",
        )
        self.assertIn(
            "GE120C1_WRAPPED_PROBE_OK",
            wrapped_outcome.output,
            f"The run_hook.py-wrapped form must produce the check's real "
            f"observable output. Got: {wrapped_outcome.output}",
        )

    # ------------------------------------------------------------------
    def test_ge120c1_source_tree_absent_from_import_path_of_process_under_test(self) -> None:
        """AC-3: the subprocess cannot import from the source tree —
        PYTHONPATH is scrubbed, the interpreter runs isolated, and cwd is
        not the source tree — asserted by inspecting the REAL subprocess
        environment/behaviour, never by reading harness source."""
        # covers: GE-120c-1
        # angle: criterion
        argv = self.harness.build_argv(_CWD_PROBE_HOOK["entry"], [])
        self.assertIn(
            "-I", argv,
            f"The interpreter must be invoked isolated (-I) for every check "
            f"invocation. Built argv: {argv}",
        )

        # Deliberately set PYTHONPATH to the REAL source scripts/ dir on this
        # (parent) test process, so the assertion below proves the harness
        # actually STRIPS it for the child — not merely that it happens to
        # already be clean in this environment.
        os.environ["PYTHONPATH"] = str(_REPO_ROOT / "scripts")
        try:
            cwd_outcome = self.harness.invoke_check(self.copy_b, _CWD_PROBE_HOOK["entry"], [])
        finally:
            del os.environ["PYTHONPATH"]

        self.assertEqual(cwd_outcome.exit_code, 0, cwd_outcome.output)
        self.assertIn(
            f"CWD:{self.copy_b.resolve()}",
            cwd_outcome.output,
            f"cwd of the invoked process must be the working copy, never "
            f"this harness's own source tree. Output: {cwd_outcome.output}",
        )
        for line in cwd_outcome.output.splitlines():
            if line.startswith("PYTHONPATH_ENV:"):
                self.assertEqual(
                    line, "PYTHONPATH_ENV:",
                    f"PYTHONPATH must be scrubbed from the child's real "
                    f"environment even though the PARENT process had it set "
                    f"to the source scripts/ dir. Got: {line!r}",
                )
                break
        else:
            self.fail(f"Expected a PYTHONPATH_ENV: line in output: {cwd_outcome.output}")

        # Direct behavioural proof: a check that can ONLY resolve its
        # prerequisite via the source tree must fail to do so here.
        source_tree_dependent_outcome = self.harness.invoke_check(
            self.copy_b, _SOURCE_TREE_ONLY_HOOK["entry"], [],
        )
        self.assertNotEqual(
            source_tree_dependent_outcome.exit_code, 0,
            "A check whose only prerequisite lives in the source tree must "
            "fail to resolve it when the source tree is off the import "
            f"path. Output: {source_tree_dependent_outcome.output}",
        )
        self.assertIn(
            "ModuleNotFoundError",
            source_tree_dependent_outcome.output,
        )

    # ------------------------------------------------------------------
    def test_ge120c1_source_tree_only_check_fails_the_harness(self) -> None:
        """Coverage note / AC-3 self-demonstration: pointed at a check that
        resolves its prerequisites only via the source tree, the harness
        FAILS. This is the deliverable that distinguishes this harness from
        the source-tree-import-based tests that already exist — a harness
        that cannot be made to fail is not evidence."""
        # covers: GE-120c-1
        # angle: failure
        with tempfile.TemporaryDirectory(dir=str(_REPO_ROOT)) as probe_dir_str:
            probe_dir = Path(probe_dir_str)
            script_path = probe_dir / "_ge120c1_source_tree_only_check.py"
            script_path.write_text(_SOURCE_TREE_ONLY_CHECK_SCRIPT, encoding="utf-8")

            # Run the SAME fixture check FROM inside a real source-tree
            # location (this repository) — the control condition.
            source_tree_outcome = self.harness.invoke_check(
                probe_dir, f"python {script_path}", [],
            )

        self.assertEqual(
            source_tree_outcome.exit_code, 0,
            "Precondition failed: running the fixture check FROM inside a "
            f"real source-tree checkout must succeed. Output: "
            f"{source_tree_outcome.output}",
        )
        self.assertIn("SOURCE_TREE_PREREQUISITE_FOUND", source_tree_outcome.output)

        # Run the SAME check against the deployed-only second copy.
        deployed_only_outcome = self.harness.invoke_check(
            self.copy_b, _SOURCE_TREE_ONLY_HOOK["entry"], [],
        )
        self.assertNotEqual(
            deployed_only_outcome.exit_code, 0,
            "THE SELF-DEMONSTRATION: pointed at a check that resolves its "
            "prerequisite only via the source tree, the harness must FAIL "
            "when run against a deployed-only second copy. Output: "
            f"{deployed_only_outcome.output}",
        )
        self.assertEqual(deployed_only_outcome.status, "could_not_check")

        # The defining assertion: the two copies must DISAGREE for a check
        # that resolves prerequisites only via the source tree — this IS
        # "the harness fails" the AC's coverage note demands.
        self.assertNotEqual(
            source_tree_outcome.status,
            deployed_only_outcome.status,
            "The two working copies must disagree for a check that resolves "
            "its prerequisites only via the source tree — agreement here "
            "would mean the harness cannot see the defect class at all.",
        )

    # ------------------------------------------------------------------
    def test_ge120c1_reports_status_and_output_from_both_copies_per_check(self) -> None:
        """AC-4: per check exercised, the harness reports result status and
        output text from each of the two working copies, side by side, so a
        disagreement is readable directly rather than inferred from a
        failed assertion."""
        # covers: GE-120c-1
        # angle: criterion
        result = self.harness.run_sweep(
            self.copy_b,
            first_copy_dir=self.copy_a,
            extra_hooks=[_WRAPPED_PROBE_HOOK],
            check_ids=["precommit-canary", _WRAPPED_PROBE_HOOK["id"]],
        )

        self.assertEqual(result.checks_exercised, 2)
        self.assertTrue(result.success, result.message)

        for check_id in ("precommit-canary", _WRAPPED_PROBE_HOOK["id"]):
            with self.subTest(check_id=check_id):
                entry = result.checks[check_id]
                self.assertIsNotNone(
                    entry.first, f"Missing first-copy outcome for {check_id}",
                )
                self.assertIsNotNone(
                    entry.second, f"Missing second-copy outcome for {check_id}",
                )
                self.assertEqual(entry.first.status, "clean")
                self.assertEqual(entry.second.status, "clean")
                # Side-by-side readability: the check id must be visible in
                # the printed/returned message, not just in structured fields
                # nobody reads.
                self.assertIn(check_id, result.message)

        self.assertIn(
            "first_copy=", result.message,
            "The message must show each copy's status labelled, so a reader "
            f"can tell which is which. Message:\n{result.message}",
        )
        self.assertIn("second_copy=", result.message)


class TestGrepOnlyCaseRejectedByHarnessOwnRule(unittest.TestCase):
    """AC-5 / coverage note: "a harness case that only searches a check's
    source text for a string is not accepted as coverage for any criterion
    in this tree." Encoded as a rule the harness enforces on its OWN case
    definitions — a review convention will not survive the fourth author."""

    def test_ge120c1_grep_only_case_flagged_by_harness_self_check(self) -> None:
        """A test that only greps a check's source text (no subprocess or
        harness invocation anywhere in its body) must be flagged."""
        # covers: GE-120c-1
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmp:
            offending_file = Path(tmp) / "test_offender.py"
            offending_file.write_text(
                "from pathlib import Path\n"
                "def test_bad():\n"
                '    src = Path("some_check.py").read_text()\n'
                '    assert "expected_string" in src\n',
                encoding="utf-8",
            )
            offenders = dch.enforce_no_grep_only_test_cases(offending_file)
        self.assertIn(
            "test_bad", offenders,
            "A test that only greps a check's source text (no subprocess or "
            "harness invocation) must be flagged as unacceptable coverage.",
        )

    def test_ge120c1_own_test_file_has_no_grep_only_cases(self) -> None:
        """The rule must survive self-application: this very test file must
        contain zero grep-only cases."""
        # covers: GE-120c-1
        # angle: criterion
        offenders = dch.enforce_no_grep_only_test_cases(Path(__file__))
        self.assertEqual(
            offenders, [],
            f"This test file itself must contain zero grep-only cases per "
            f"its own AC-5 — the rule must survive self-application. "
            f"Offenders found: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/EPIC-TrustThatAGreenCheckActuallyChecked/12,
#   GE-120c-1]: Initial implementation AND its tests. Per this AC's own
#   assigned_agent: test-writer (no coder agent in this ticket's dispatch
#   chain — see module docstring), the real _deployed_check_harness.py
#   module was authored alongside this test file rather than left as a red
#   stub for python-coder. All 7 tests pass against the real harness,
#   verified with `python -m unittest` against this file directly.
# ====================================================================
