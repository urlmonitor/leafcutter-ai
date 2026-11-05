"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_iii.py
COVERS: GE-127d-3-iii -- the previous length and the new length a commit quotes
    are both arrived at by the ONE rule in force (including every merge parent).

DECISION HISTORY
- 2026-10-20 [GE-127d-3-iii/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402

_LIMIT = 40


def _with_used_string(code: int, s_lines: int) -> str:
    """``code`` code lines then a USED (assigned) ``s_lines``-line string: all counted."""
    rows = [f"value_{i} = {i}" for i in range(code)]
    return "\n".join([*rows, 'BIG = """', *[f"body {i}" for i in range(s_lines - 2)], '"""']) + "\n"


def _with_hash_run(code: int, hashes: int) -> str:
    rows = [f"value_{i} = {i}" for i in range(code)]
    return "\n".join([*rows, *[f"# note {i}" for i in range(hashes)]]) + "\n"


class TestOneRuleOnBothSides(unittest.TestCase):
    def test_ge_127d_3_iii_a_file_that_measures_longer_under_the_new_rule_is_not_refused_as_crossing(self):
        # covers: GE-127d-3-iii
        # angle: discrimination
        """HEAD holds code plus an ASSIGNED triple-quoted string (counted under the new rule,
        discarded under the old). Taking 3 code lines out completes, quoting previous and new
        lengths that are both new-rule measurements, and reports the file as already over, never
        refused as crossing."""
        code, s_lines = 30, 15
        head, staged = _with_used_string(code, s_lines), _with_used_string(code - 3, s_lines)
        with tempfile.TemporaryDirectory() as tmp:
            result, output = fx.change_outcome(Path(tmp), "big.py", head, staged, limit=_LIMIT)
        numbers = fx.outcome_numbers(output)
        measured_head, measured_staged = fx.measure_texts([(".py", head), (".py", staged)])
        self.assertEqual(0, result.returncode, msg=f"must complete, not be refused as crossing. Got: {output!r}")
        self.assertEqual((code + s_lines, code - 3 + s_lines), (numbers["previous"], numbers["new"]), msg=output)
        self.assertEqual((measured_head, measured_staged), (numbers["previous"], numbers["new"]), msg=output)
        self.assertIn("already over", output.lower(), msg=f"must report it as already over. Got: {output!r}")
        self.assertNotIn("FILE TOO LARGE", output)

    def test_ge_127d_3_iii_a_file_that_measures_shorter_under_the_new_rule_uses_the_shorter_previous(self):
        # covers: GE-127d-3-iii
        # angle: criterion
        """HEAD holds code plus a run of ``#`` lines (counted by the old rule, not the new): the
        outcome's previous length equals the shared measure applied to the HEAD content now."""
        head, staged = _with_hash_run(36, 10), _with_hash_run(40, 10)
        with tempfile.TemporaryDirectory() as tmp:
            result, output = fx.change_outcome(Path(tmp), "calm.py", head, staged, limit=_LIMIT)
        numbers = fx.outcome_numbers(output)
        measured_head = fx.measure_texts([(".py", head)])[0]
        self.assertEqual(0, result.returncode, msg=f"must complete. Got: {output!r}")
        self.assertEqual(measured_head, numbers["previous"], msg=f"previous must be the new-rule length. {output!r}")
        self.assertEqual(36, numbers["previous"], msg="and independently that is the code-line count")
        self.assertEqual(40, numbers["new"], msg=output)

    def test_ge_127d_3_iii_every_merge_parent_is_measured_by_the_rule_in_force(self):
        # covers: GE-127d-3-iii
        # angle: boundary
        """A real merge in progress (MERGE_HEAD present): HEAD's version carries a large ASSIGNED
        string (counted now), the other parent's a run of ``#`` comments (not counted now). The
        quoted previous length equals the maximum of the shared measure applied to each parent's
        blob, and the verdict follows from that maximum."""
        head_text, other_text = _with_used_string(30, 15), _with_hash_run(30, 20)
        resolved = _with_used_string(27, 15)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.build_repo(root, limit=_LIMIT)
            fx.start_merge(root, "merged.py", _with_hash_run(20, 0), head_text, other_text, resolved)
            result, output = fx.run_gate(root)
        numbers = fx.outcome_numbers(output)
        want = max(fx.measure_texts([(".py", head_text), (".py", other_text)]))
        independent = max(content.independent_python_length(head_text), content.independent_python_length(other_text))
        self.assertEqual(45, independent, msg="fixture sanity: the new-rule maximum is the HEAD parent's 45")
        self.assertEqual(independent, want, msg="the shared measure must agree with the independent derivation")
        self.assertEqual(want, numbers["previous"], msg=f"previous must be the max over parents. Got: {output!r}")
        self.assertEqual(0, result.returncode, msg=f"42 against a previous of 45 completes. Got: {output!r}")


if __name__ == "__main__":
    unittest.main()
