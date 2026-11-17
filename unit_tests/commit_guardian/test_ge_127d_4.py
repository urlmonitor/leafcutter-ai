"""
MODULE: unit_tests/commit_guardian/test_ge_127d_4.py
COVERS: GE-127d-4 -- the backstop: an already-over file whose measured length
    FELL while its total physical line count ROSE is refused (a canary for any
    gap in the measure), and honest shapes are not.

NUMBERS: every number a test compares against is computed at run time -- the
    measured lengths by the independent ast/tokenize oracle, the totals by a
    plain physical-line count the measure cannot influence.

DECISION HISTORY
- 2026-10-20 [GE-127d-4/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as fx2  # noqa: E402
import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402

_LIMIT = 40
_BUILD_FEATURE = fx.REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"


def py_file(code: int, comments: int, *, skip_code: int = 0, fresh: int = 0) -> str:
    """``code`` code lines (the first ``skip_code`` removed, ``fresh`` new ones added) + ``#`` lines."""
    rows = [f"value_{i} = {i}" for i in range(skip_code, code)] + [f"fresh_{i} = {i}" for i in range(fresh)]
    return "\n".join([*rows, *[f"# comment {i}" for i in range(comments)]]) + "\n"


def numbers_for(prev: str, new: str) -> tuple[int, int, int, int]:
    """(measured prev, measured new, total prev, total new) from oracles the measure cannot influence."""
    return (
        content.independent_python_length(prev), content.independent_python_length(new),
        fx.plain_line_count(prev), fx.plain_line_count(new),
    )


def run_change(rel: str, head: str | None, staged: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        result, output = fx.change_outcome(Path(tmp), rel, head, staged, limit=_LIMIT)
    return result.returncode, output


class TestBackstop(unittest.TestCase):
    def test_ge_127d_4_measured_fell_while_total_rose_is_refused_and_named(self):
        # covers: GE-127d-4
        # angle: criterion
        """Previous version over its limit; the staged version removes C code lines and adds K
        comment lines (K > C). Refused at exit 1, naming the file and both pairs of numbers
        (computed at run time), stating the separate-commits remedy and a heading distinct from
        crossing/growth; the two commits made separately each pass."""
        for cut, added_comments in ((3, 8), (5, 9)):
            head, staged = py_file(60, 5), py_file(60, 5 + added_comments, skip_code=cut)
            m0, m1, t0, t1 = numbers_for(head, staged)
            self.assertTrue(m0 > _LIMIT and m1 < m0 and t1 > t0, msg="fixture sanity: the backstop shape")
            code, output = run_change("big.py", head, staged)
            match = fx.BACKSTOP_RE.search(output)
            self.assertEqual(1, code, msg=f"C={cut}: must be refused. Got: {output!r}")
            self.assertIn("big.py", output)
            self.assertIsNotNone(match, msg=f"C={cut}: must state the fall and the rise. Got: {output!r}")
            self.assertEqual((m0, m1, t0, t1), tuple(int(g) for g in match.groups()), msg=output)
            self.assertIsNotNone(fx.SEPARATE_COMMITS_RE.search(output), msg=f"C={cut}: the remedy. Got: {output!r}")
            self.assertNotIn("FILE TOO LARGE", output, msg="distinguishable from a crossing refusal")
            self.assertNotIn("FILE GREW", output, msg="distinguishable from a growth refusal")
        head = py_file(60, 5)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.build_repo(root, limit=_LIMIT)
            fx.commit_files(root, {"big.py": head})
            fx.install_hook(root)
            fx.stage(root, "big.py", py_file(60, 5, skip_code=3))
            first, first_output = fx.hook_commit(root, "cut code only")
            fx.stage(root, "big.py", py_file(60, 13, skip_code=3))
            second, second_output = fx.hook_commit(root, "then add comments")
        self.assertEqual(0, first.returncode, msg=f"the code cut alone must pass. Got: {first_output!r}")
        self.assertEqual(0, second.returncode, msg=f"the comments alone must pass. Got: {second_output!r}")

    def test_ge_127d_4_an_under_limit_file_with_a_code_cut_and_more_comments_passes(self):
        # covers: GE-127d-4
        # angle: boundary
        """The same cut-plus-more-comments change on a file whose previous version stands under
        its limit, exactly at it, or over only under the OLD rule: no backstop refusal."""
        scenarios = {
            "under": (py_file(30, 5), py_file(30, 15, skip_code=3)),
            "at_limit": (py_file(_LIMIT, 5), py_file(_LIMIT, 15, skip_code=3)),
            "old_rule_over": (py_file(25, 20), py_file(25, 30, skip_code=3)),
        }
        for name, (head, staged) in scenarios.items():
            m0, _m1, t0, t1 = numbers_for(head, staged)
            self.assertLessEqual(m0, _LIMIT, msg=f"{name}: fixture sanity (previous not over under the new rule)")
            self.assertGreater(t1, t0, msg=f"{name}: fixture sanity (total rose)")
            code, output = run_change("calm.py", head, staged)
            self.assertIsNone(fx.BACKSTOP_RE.search(output), msg=f"{name}: no backstop refusal. Got: {output!r}")
            self.assertEqual(0, code, msg=f"{name}: must complete. Got: {output!r}")

    def test_ge_127d_4_the_backstop_catches_a_measure_gap(self):
        # covers: GE-127d-4
        # angle: discrimination
        """The shared measure deliberately replaced IN-PROCESS by the pre-2026-10-16 rule, the
        2026-10-13 restyle of build-feature.js (``//`` runs rewritten as /* */ blocks) is replayed
        through the hook's verdict: refused by the backstop, naming the situation, even though the
        degraded measure reports the file shorter."""
        original = _BUILD_FEATURE.read_text(encoding="utf-8")
        rewrite = content.runs_to_blocks(original)
        namespace: dict = {}
        exec(content.OLD_RULE_SOURCE, namespace)  # noqa: S102 -- fixed test-owned source, the old counting rule
        old_count = namespace["old_count"]
        m0, m1 = old_count(original), old_count(rewrite)
        t0, t1 = fx.plain_line_count(original), fx.plain_line_count(rewrite)
        self.assertTrue(1000 < m1 < m0 and t1 > t0, msg="fixture sanity: over 1000 and the backstop shape")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = fx.build_repo(root, limits={".js": 1000})
            fx.commit_files(root, {"build-feature.js": original})
            fx.stage(root, "build-feature.js", rewrite)
            wrapper = fx.degraded_gate_script(dest, content.OLD_RULE_SOURCE)
            result = fx2.run([fx.PYTHON, str(wrapper)], root)
            output = fx2.combined_output(result)
        match = fx.BACKSTOP_RE.search(output)
        self.assertEqual(1, result.returncode, msg=f"the backstop must refuse. Got: {output!r}")
        self.assertIsNotNone(match, msg=f"the backstop must name the situation. Got: {output!r}")
        self.assertEqual((m0, m1, t0, t1), tuple(int(g) for g in match.groups()), msg=output)

    def test_ge_127d_4_honest_shapes_are_not_refused_by_the_backstop(self):
        # covers: GE-127d-4
        # angle: boundary
        """On an already-over file: measured and total both falling, and measured unchanged with
        total rising, each pass without this refusal; so does a newly added file."""
        head = py_file(60, 5)
        scenarios = {
            "both_falling": (head, py_file(55, 5)),
            "comments_only": (head, py_file(60, 13)),
            "new_file": (None, py_file(20, 30)),
        }
        for name, (prior, staged) in scenarios.items():
            code, output = run_change("honest.py", prior, staged)
            self.assertIsNone(fx.BACKSTOP_RE.search(output), msg=f"{name}: no backstop refusal. Got: {output!r}")
            self.assertEqual(0, code, msg=f"{name}: must complete. Got: {output!r}")

    def test_ge_127d_4_a_merge_adopting_a_vetted_parent_is_not_refused_by_the_backstop(self):
        # covers: GE-127d-4
        # angle: boundary
        """A real merge in progress: the staged version equals the MERGE_HEAD parent's, which
        against HEAD shows the measured-fell / total-rose shape: no backstop refusal. The same
        staged content as an ordinary commit on HEAD is refused."""
        head_text, other_text = py_file(60, 5), py_file(60, 13, skip_code=3)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.build_repo(root, limit=_LIMIT)
            fx.start_merge(root, "merged.py", py_file(10, 0), head_text, other_text, other_text)
            _merge_result, merge_output = fx.run_gate(root)
        code, ordinary_output = run_change("merged.py", head_text, other_text)
        self.assertIsNone(fx.BACKSTOP_RE.search(merge_output), msg=f"adopting a vetted parent. Got: {merge_output!r}")
        self.assertEqual(1, code, msg=f"the same content as an ordinary commit is refused. Got: {ordinary_output!r}")
        self.assertIsNotNone(fx.BACKSTOP_RE.search(ordinary_output), msg=ordinary_output)

    def test_ge_127d_4_a_file_failing_both_checks_reports_both_refusals(self):
        # covers: GE-127d-4
        # angle: boundary
        """An over-limit file that both fails the two-for-one requirement (8 new code lines in,
        10 out) and shows the measured-fell / total-rose shape: exit 1 with both refusal blocks,
        each under its own heading."""
        head = py_file(60, 5)
        staged = py_file(60, 15, skip_code=10, fresh=8)
        m0, m1, t0, t1 = numbers_for(head, staged)
        self.assertTrue(m1 < m0 and t1 > t0, msg="fixture sanity: the backstop shape")
        code, output = run_change("both.py", head, staged)
        match = fx.BACKSTOP_RE.search(output)
        self.assertEqual(1, code, msg=output)
        self.assertIn("FILE GREW WHILE ALREADY OVER ITS LIMIT", output)
        self.assertIsNotNone(match, msg=f"the backstop block must be present too. Got: {output!r}")
        headings = [(output.index(line), line) for line in output.splitlines() if line.startswith("❌")]
        owner = [line for position, line in headings if position < match.start()][-1:]
        self.assertTrue(owner and "FILE GREW" not in owner[0] and "FILE TOO LARGE" not in owner[0],
                        msg=f"the backstop sentence must sit under its own heading. Headings: {headings!r}")

    def test_ge_127d_4_the_backstop_refusal_reaches_the_registered_hook_output(self):
        # covers: GE-127d-4
        # angle: reachability
        """surface_invoked: python .leafcutter/scripts/commit_guardian/run_hook.py
        .leafcutter/scripts/commit_guardian/check_file_size.py -- a REAL ``git commit`` through the
        registered hook shows the backstop refusal and its four numbers, exit 1, no commit created."""
        head, staged = py_file(60, 5), py_file(60, 13, skip_code=3)
        m0, m1, t0, t1 = numbers_for(head, staged)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.build_repo(root, limit=_LIMIT)
            fx.commit_files(root, {"hooked.py": head})
            fx.install_hook(root)
            before = fx2.git(["rev-list", "--count", "HEAD"], root).stdout.strip()
            fx.stage(root, "hooked.py", staged)
            result, output = fx.hook_commit(root)
            after = fx2.git(["rev-list", "--count", "HEAD"], root).stdout.strip()
        match = fx.BACKSTOP_RE.search(output)
        self.assertEqual(1, result.returncode, msg=f"the commit must be refused with status 1. Got: {output!r}")
        self.assertEqual(before, after, msg="a refused commit creates no commit object")
        self.assertIsNotNone(match, msg=f"the hook's own output must carry the refusal. Got: {output!r}")
        self.assertEqual((m0, m1, t0, t1), tuple(int(g) for g in match.groups()), msg=output)


if __name__ == "__main__":
    unittest.main()
