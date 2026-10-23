"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_hook.py
COVERS: GE-127d-3 -- the real_artifact, reachability and seam descriptors, all
    driven through the check-file-size gate (directly, or via a real
    ``git commit`` with the registered hook) in temporary git repositories.

DECISION HISTORY
- 2026-10-20 [GE-127d-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import ast
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as fx2  # noqa: E402
import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402

_BUILD_FEATURE = fx.REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_PART_RE = re.compile(r"^\s*-\s*(?P<name>\w+)\S*:\s*(?P<portion>\d+)\s*lines?\s*$", re.IGNORECASE | re.MULTILINE)


class TestRestyleLeavesQuotedLengthUnchanged(unittest.TestCase):
    def test_ge_127d_3_restyling_a_real_workflow_template_leaves_its_quoted_length_unchanged(self):
        # covers: GE-127d-3
        # angle: real_artifact
        """Real templates/workflows-js/build-feature.js with every run of ``//``
        lines rewritten into one /* */ block: the hook's quoted length for the
        original (new file) and for the rewrite (staged over the original at
        HEAD) are the same number, read from the hook's own output."""
        original = _BUILD_FEATURE.read_text(encoding="utf-8")
        rewrite = content.runs_to_blocks(original)
        self.assertNotEqual(original, rewrite, msg="fixture sanity: the conversion must change the file")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx.build_repo(root, limits={".js": 1000})
            fx.commit_files(root, {"seed_bystander.py": "SEED = 1\n"})
            fx.stage(root, "build-feature.js", original)
            _result, as_new = fx.run_gate(root)
            quoted_original = fx2.parse_lines_and_limit(as_new)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, outcome = fx.change_outcome(root, "build-feature.js", original, rewrite, limits={".js": 1000})
            numbers = fx.outcome_numbers(outcome)
        self.assertIsNotNone(quoted_original, msg=f"the original must be refused and quoted. Got: {as_new!r}")
        self.assertEqual(0, result.returncode, msg=f"a restyle-only change must complete. Got: {outcome!r}")
        self.assertEqual(
            {quoted_original[0]}, {numbers["previous"], numbers["new"]},
            msg=f"previous, new and the original's quoted length must be one number. Got: {outcome!r}",
        )


class TestRestyleThroughRegisteredHook(unittest.TestCase):
    def test_ge_127d_3_the_hook_quotes_the_same_length_before_and_after_a_restyle_only_commit(self):
        # covers: GE-127d-3
        # angle: reachability
        """surface_invoked: python .leafcutter/scripts/commit_guardian/run_hook.py
        .leafcutter/scripts/commit_guardian/check_file_size.py -- mirrored by a
        single-hook pre-commit config and a REAL ordinary ``git commit``. A
        restyle-only change to an over-limit .js and an over-limit .py file
        completes and the hook output quotes equal previous and new lengths."""
        js_head, _ = content.build_text(".js", 40, 4, "line")
        js_new, _ = content.build_text(".js", 40, 4, "block")
        py_head = content.py_positioned("module", "hash", 4, extra_code=40)
        py_new = content.py_positioned("module", "string", 4, extra_code=40)
        for rel, head, staged in (("big.js", js_head, js_new), ("big.py", py_head, py_new)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                fx.build_repo(root, limit=30)
                fx.commit_files(root, {rel: head})
                fx.install_hook(root)
                fx.stage(root, rel, staged)
                result, outcome = fx.hook_commit(root)
                numbers = fx.outcome_numbers(outcome)
            self.assertEqual(0, result.returncode, msg=f"{rel}: restyle-only must complete. Got: {outcome!r}")
            self.assertIsNotNone(numbers["previous"], msg=f"{rel}: previous length must be quoted. Got: {outcome!r}")
            self.assertEqual(numbers["previous"], numbers["new"], msg=f"{rel}: restyle moved the length. {outcome!r}")


def _refused_parts_file(hash_in: str, string_in: str) -> str:
    """Back-to-back top-level functions (no blank lines, so a part's range is unambiguous)."""
    runs = {name: [] for name in ("func_a", "func_b", "func_c")}
    runs[hash_in] = [f"    # comment run {i}" for i in range(5)]
    strings = {name: [] for name in runs}
    strings[string_in] = ['    """bare standalone', "    string text", '    here"""']
    lines = ["import os"]
    for name in runs:
        lines += [f"def {name}():", *runs[name], *strings[name]]
        if name == "func_b":
            lines += ['    TEXT = """', "    used string line one", "    used string line two", '    """']
        lines += [f"    value_{i} = {i}" for i in range(8)] + ["    return os.sep"]
    return "\n".join(lines) + "\n"


class TestRefusalPartsUseTheSameMeasure(unittest.TestCase):
    def _portions(self, text: str) -> dict[str, int]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, outcome = fx.change_outcome(root, "parts.py", None, text, limit=20)
        self.assertEqual(1, result.returncode, msg=f"the over-limit file must be refused. Got: {outcome!r}")
        return {m.group("name"): int(m.group("portion")) for m in _PART_RE.finditer(outcome)}

    def test_ge_127d_3_the_refusal_part_breakdown_is_measured_by_the_same_rule(self):
        # covers: GE-127d-3
        # angle: seam
        """Each listed part's portion equals the shared measure applied at run
        time to that part's own line range; moving the comment run from one
        function to another leaves every listed portion unchanged."""
        first = _refused_parts_file("func_a", "func_a")
        second = _refused_parts_file("func_c", "func_c")
        listed_first, listed_second = self._portions(first), self._portions(second)
        tree = ast.parse(first)
        rows = first.splitlines()
        expected = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                expected[node.name] = "\n".join(rows[node.lineno - 1 : node.end_lineno]) + "\n"
        measured = fx.measure_texts([(".py", text) for text in expected.values()])
        want = dict(zip(expected, measured))
        self.assertEqual(want, {name: listed_first.get(name) for name in want},
                         msg="each part's portion must be the shared measure over its own line range")
        self.assertEqual(listed_first, listed_second, msg="moving a comment run must not move any listed portion")


if __name__ == "__main__":
    unittest.main()
