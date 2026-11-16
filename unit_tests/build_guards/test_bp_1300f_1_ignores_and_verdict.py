"""
MODULE: unit_tests/build_guards/test_bp_1300f_1_ignores_and_verdict.py
COVERS: BP-1300f-1-v, BP-1300f-1-vi, BP-1300f-1-vii -- the type-ignore count, the
    honest verdict (summary, nothing inspected, could not check) and the CI job.
GOAL: Behavioural proof. The integration tests build a real git repository with a
    base and a head commit (see _bp1300f_ratchet_fixture.py) and run the real
    scripts/ci/mypy_ratchet.py with the real mypy. The counter table feeds source
    bytes to the real tokenizer-based counter. The CI test parses the real
    .github/workflows/ci.yml with a YAML parser; the live proof of that job is the
    pull request's own CI run.
"""

from __future__ import annotations

import importlib
import os
import re
import unittest

import yaml

from unit_tests.build_guards._bp1300f_ratchet_fixture import REPO_ROOT, RatchetRepoCase, summary

IGNORE_BASE = '# svc\ndef f() -> None:\n    y: int = "s"  # type: ignore[assignment]\n    print(y)\n'
SCOPE_DIRS = ("scripts", "tests", "unit_tests", "knowledge", "integrations", "kernel")


class TestTypeIgnoreCount(RatchetRepoCase):
    """BP-1300f-1-v."""

    def setUp(self) -> None:
        super().setUp()
        self.commit_base({"scripts/svc.py": IGNORE_BASE})

    def test_bp_1300f_1_v_added_type_ignore_fails_naming_file_and_line(self):
        # covers: BP-1300f-1-v
        head = IGNORE_BASE + '\n\ndef g() -> None:\n    a = 1\n    z: int = "t"  # type: ignore[assignment]\n'
        self.assertIn("type: ignore", head.splitlines()[8])  # line 9
        self.commit_head({"scripts/svc.py": head})
        run = self.ratchet()
        counts = self.assert_failed(run)
        self.assertEqual((counts["new"], counts["ignores"]), (0, 1))
        named = self.lines_with(run.out, "scripts/svc.py", "type-ignore")
        self.assertEqual(len(named), 1, run.out)
        self.assertRegex(named[0], r"\b1\b.*\b2\b")
        self.assertRegex(named[0], r"line \b9\b")
        self.assertTrue(self.lines_with(run.out, "remedy", "remove the ignore"), run.out)

    def test_bp_1300f_1_v_type_ignore_text_inside_a_string_is_not_counted(self):
        # covers: BP-1300f-1-v
        head = IGNORE_BASE + '\n\nS = "# type: ignore"\n\n\ndef doc() -> None:\n    """Mentions # type: ignore."""\n'
        self.commit_head({"scripts/svc.py": head})
        counts = self.assert_passed(self.ratchet())
        self.assertEqual(counts["ignores"], 0)

    def test_bp_1300f_1_v_removed_type_ignore_passes(self):
        # covers: BP-1300f-1-v
        self.commit_head({"scripts/svc.py": IGNORE_BASE.replace('"s"  # type: ignore[assignment]', "1")})
        counts = self.assert_passed(self.ratchet())
        self.assertEqual((counts["new"], counts["ignores"]), (0, 0))

    def test_bp_1300f_1_v_comment_counter_table(self):
        # covers: BP-1300f-1-v
        ratchet = importlib.import_module("scripts.ci.mypy_ratchet")
        source = (
            "a = 1  # type: ignore\n"
            "b = 2  #type:ignore\n"
            "c = 3  # type: ignore[assignment, misc]  # why\n"
            "d = 4  # type: ignored by policy\n"
            'e = "# type: ignore"\n'
            'f = f"{e} # type: ignore"\n'
            "def g() -> None:\n"
            '    """# type: ignore in a docstring"""\n'
            "    pass  # noqa: E501  # type: ignore\n"
            "h = 5  # TYPE: IGNORE\n"
        )
        found = ratchet.type_ignore_lines(source.encode("utf-8"))
        self.assertEqual([line for line, _text in found], [1, 2, 3])


class TestVerdictIsHonest(RatchetRepoCase):
    """BP-1300f-1-vi."""

    def test_bp_1300f_1_vi_pass_summary_names_files_new_existing_and_ignores(self):
        # covers: BP-1300f-1-vi
        two = '# v1\ndef f() -> str:\n    return 1\n\n\ndef g() -> None:\n    y: int = "s"\n'
        self.commit_base({"scripts/svc.py": two})
        self.commit_head({"scripts/svc.py": two.replace("# v1", "# v2")})
        run = self.ratchet()
        self.assertEqual(run.code, 0, run.out)
        expected = "mypy ratchet: 1 file, 0 new errors (2 existing errors untouched, 0 removed), 0 new type-ignores"
        self.assertEqual([line for line in run.out.splitlines() if line.startswith("mypy ratchet")], [expected])

    def test_bp_1300f_1_vi_nothing_in_scope_says_nothing_was_inspected(self):
        # covers: BP-1300f-1-vi
        self.commit_base({"scripts/keep.py": "KEEP = 1\n"})
        self.commit_head({"docs/notes.md": "# notes\n", "tools/x.py": "def f() -> str:\n    return 1\n"})
        run = self.ratchet()
        self.assertEqual(run.code, 0, run.out)
        self.assertIn("NOTHING INSPECTED", run.out)
        self.assertIn("no type check ran", run.out)
        self.assertIsNone(summary(run.out), run.out)
        self.assertNotRegex(run.out, r"\b0 new errors\b")

    def test_bp_1300f_1_vi_mypy_that_cannot_finish_is_could_not_check(self):
        # covers: BP-1300f-1-vi
        self.commit_base({"scripts/svc.py": "def f() -> str:\n    return 'ok'\n"})
        self.commit_head({"scripts/svc.py": "def f() -> str:\n    return ('ok'\n"})
        run = self.ratchet()
        self.assertEqual(run.code, 2, run.out)
        self.assertIn("COULD NOT CHECK", run.out)
        self.assertTrue(self.lines_with(run.out, "scripts/svc.py", "[syntax]"), run.out)
        self.assertIsNone(summary(run.out), run.out)

    def test_bp_1300f_1_vi_missing_or_silent_mypy_is_could_not_check(self):
        # covers: BP-1300f-1-vi
        self.commit_base({"scripts/svc.py": "X = 1\n"})
        self.commit_head({"scripts/svc.py": "X = 2\n"})
        silent = ('import sys\nif sys.argv[1:] == ["--version"]:\n'
                  '    print("mypy 0.0.0 (stub)")\n    sys.exit(0)\nsys.exit(1)\n')
        missing = 'import sys\nsys.stderr.write("No module named mypy\\n")\nsys.exit(1)\n'
        for label, body, named in (("silent", silent, "status 1"), ("missing", missing, "--version")):
            stub = self.cache.parent / "stubs" / label / "mypy"
            stub.mkdir(parents=True)
            (stub / "__init__.py").write_text("", encoding="utf-8")
            (stub / "__main__.py").write_text(body, encoding="utf-8")
            run = self.ratchet(env={**os.environ, "PYTHONPATH": str(stub.parent)})
            self.assertEqual(run.code, 2, f"{label}:\n{run.out}")
            self.assertIn("COULD NOT CHECK", run.out)
            self.assertIn(named, run.out)
            self.assertIsNone(summary(run.out), run.out)

    def test_bp_1300f_1_vi_unresolvable_base_is_could_not_check(self):
        # covers: BP-1300f-1-vi
        self.commit_base({"scripts/keep.py": "KEEP = 1\n"})
        self.commit_head({"scripts/keep.py": "KEEP = 2\n"})
        run = self.ratchet(base="no-such-ref")
        self.assertEqual(run.code, 2, run.out)
        self.assertTrue(self.lines_with(run.out, "COULD NOT CHECK", "no-such-ref"), run.out)
        self.assertIsNone(summary(run.out), run.out)


class TestCiJob(unittest.TestCase):
    """BP-1300f-1-vii."""

    def test_bp_1300f_1_vii_ci_job_runs_the_ratchet_and_can_fail(self):
        # covers: BP-1300f-1-vii
        with (REPO_ROOT / ".github" / "workflows" / "ci.yml").open(encoding="utf-8") as handle:
            workflow = yaml.safe_load(handle)
        job = workflow["jobs"]["typecheck"]
        self.assertEqual(job["name"], "mypy ratchet (new errors only)")
        self.assertNotIn("continue-on-error", job)
        checkout = [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
        self.assertEqual(len(checkout), 1)
        self.assertEqual(checkout[0].get("with", {}).get("fetch-depth"), 0)
        pr_steps = [s for s in job["steps"] if "mypy_ratchet.py" in s.get("run", "")]
        self.assertEqual(len(pr_steps), 1, "exactly one step must run the ratchet")
        step = pr_steps[0]
        self.assertEqual(step.get("if"), "github.event_name == 'pull_request'")
        self.assertNotIn("continue-on-error", step)
        run = step["run"]
        self.assertIn('git fetch --no-tags origin "${{ github.base_ref }}"', run)
        # The call, with its backslash-newline continuation lines.
        call = re.search(r"python scripts/ci/mypy_ratchet\.py(?:[^\n\\]|\\\n)*", run)
        self.assertIsNotNone(call, run)
        assert call is not None
        self.assertIn('--base "origin/${{ github.base_ref }}"', call.group(0))
        for scope in SCOPE_DIRS:
            self.assertIn(f"'{scope}/*.py'", call.group(0))
            self.assertIn(f"'{scope}/**/*.py'", call.group(0))
        self.assertIsNone(re.search(r"^\s*mypy\s", run, re.MULTILINE), "plain whole-file mypy must be gone")


if __name__ == "__main__":
    unittest.main()
