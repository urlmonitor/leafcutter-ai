"""
MODULE: unit_tests/commit_guardian/test_ge_127d_5.py
COVERS: GE-127d-5 -- the refusal advice and every published place state the one
    measurement rule in force, and the parity gate carries it as a fourth fact.

PINNED VOCABULARY (test-writer design decisions, not AC-pinned): the measurement-rule
    passage on a published surface is located by the fixed marker ``MEASUREMENT RULE``
    and runs to the end of its sentence/table cell; the parity gate names a
    disagreeing surface on a ``DISAGREEMENT: <surface> ...`` line (GE-127d-1's token).

DECISION HISTORY
- 2026-10-20 [GE-127d-5/test-writer]: Initial authoring.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_1_fixture as fx1  # noqa: E402
import _ge_127d_2_fixture as fx2  # noqa: E402
import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402

MARKER = "MEASUREMENT RULE"
OLD_SENTENCE = (
    "a quoted length discards content inside triple-quoted strings, in either Python quote style, and content "
    "inside C-style block comments; every remaining line -- including blank lines and hash comment lines -- is counted."
)
_REMOVED_ADVICE = ("WILL reduce", "'#' comments count", fx2.FORBIDDEN_OLD_SENTENCE, fx2.HELPS_MARKER, fx2.NO_HELP_MARKER)


def _outputs(ext: str) -> dict[str, str]:
    """The refusal output through both paths (crossing, growth) for *ext*."""
    style = "line" if ext == ".py" else "block"
    base, _ = content.build_text(ext, 50, 6, style)
    more = base + "".join(f"{content.code_line(ext, 100 + i)}\n" for i in range(5))
    result = {}
    with tempfile.TemporaryDirectory() as tmp:
        result["crossing"] = fx.change_outcome(Path(tmp), f"big{ext}", None, base, limit=30)[1]
    with tempfile.TemporaryDirectory() as tmp:
        result["growth"] = fx.change_outcome(Path(tmp), f"big{ext}", base, more, limit=30)[1]
    return result


class TestAdviceStatesTheRuleInForce(unittest.TestCase):
    def test_ge_127d_5_the_refusal_advice_states_the_rule_and_names_no_free_comment_style(self):
        # covers: GE-127d-5
        # angle: criterion
        """Over-limit .py and .js through crossing and growth: the advice states that every comment
        style, standalone strings and blank lines do not count, that used strings do, that
        rewriting/deleting/joining are not remedies, and states no style as counted. Behaviour check:
        deleting every comment and standalone string leaves the quoted length unchanged."""
        for ext in (".py", ".js"):
            for path, output in _outputs(ext).items():
                lowered = output.lower()
                where = f"{ext}/{path}: {output!r}"
                self.assertRegex(lowered, r"(?:do|does) not count|not counted|uncounted", msg=where)
                for word in ("standalone", "docstring", "used string", "blank lines", "rewriting", "deleting", "joining"):
                    self.assertIn(word, lowered, msg=f"missing {word!r}: {where}")
                # BrainCandy 2026-10-21: blank lines are NOT counted anywhere. A mention of blank
                # lines must sit inside a "does not count ..." clause, never a "counts ..." one.
                self.assertRegex(
                    lowered, r"not count[^;.\n]*blank lines|blank lines[^;.\n]*(?:not counted|uncounted)",
                    msg=f"the advice must say blank lines are not counted: {where}",
                )
                counted_clauses = re.findall(r"(?<!not )counts? [^;.\n]*", lowered)
                self.assertFalse(
                    [c for c in counted_clauses if "blank line" in c],
                    msg=f"no clause may say blank lines count: {where}",
                )
                for removed in _REMOVED_ADVICE:
                    self.assertNotIn(removed, output, msg=f"the incumbent advice must be replaced: {where}")
                measures = (fx2.extract_measures_line(output) or "").lower()
                self.assertIn("standalone", measures, msg=f"the Measures line states the same rule: {where}")
        py_with = content.build_text(".py", 50, 6, "line")[0] + '"""\ntrailing standalone\n"""\n'
        py_without = content.build_text(".py", 50, 0, "line")[0]
        js_with, js_without = content.build_text(".js", 50, 6, "block")[0], content.build_text(".js", 50, 0, "line")[0]
        py_blanks = py_with.replace("\n", "\n\n")
        js_blanks = js_with.replace("\n", "\n\n")
        for rel, with_text, without_text, spaced in (
            ("a.py", py_with, py_without, py_blanks),
            ("a.js", js_with, js_without, js_blanks),
        ):
            quoted = []
            for text in (with_text, without_text, spaced, spaced.replace("\n\n", "\n")):
                with tempfile.TemporaryDirectory() as tmp:
                    _result, output = fx.change_outcome(Path(tmp), rel, None, text, limit=30)
                parsed = fx2.parse_lines_and_limit(output)
                self.assertIsNotNone(parsed, msg=f"{rel}: must quote a length. Got: {output!r}")
                quoted.append(parsed[0])
            self.assertEqual(
                1, len(set(quoted)), msg=f"{rel}: deleting comments, standalone strings or blank lines must not move it: {quoted}"
            )


def _real_surface_tree(root: Path) -> Path:
    """A fixture tree holding the gate and the REAL README.md / commit_guardian.json."""
    dest = fx.build_repo(root, limit=40)
    shutil.copy2(fx.GUARDIAN_SRC / "README.md", dest / "README.md")
    shutil.copy2(fx.GUARDIAN_SRC / "commit_guardian.json", dest / "commit_guardian.json")
    return dest


def _passage_span(text: str) -> tuple[int, int]:
    start = text.find(MARKER)
    if start < 0:
        message = f"the published surface carries no {MARKER} passage"
        raise AssertionError(message)
    ends = [i for i in (text.find(" | ", start), text.find("\n", start)) if i >= 0]
    return start, min(ends) if ends else len(text)


def _run_parity(root: Path):
    result = fx2.run([fx.PYTHON, str(root / "scripts" / "commit_guardian" / fx1.SCRIPT_NAME)], root)
    return result, fx2.combined_output(result)


class TestParityGate(unittest.TestCase):
    @pytest.mark.shared_layout_reader
    @pytest.mark.usefixtures("shared_reference_layout")
    def test_ge_127d_5_the_real_published_surfaces_agree_with_the_rule_in_force(self):
        # covers: GE-127d-5
        # angle: deployed
        """On the shared deployed layout, the published-versus-enforced comparison over the real
        surfaces and configuration reports zero disagreements, a surfaces-compared count above
        zero and exit 0, and every real surface carries the rule in force (standalone strings)."""
        deployed = fx.deployed_guardian_dir()
        config = json.loads((deployed / "commit_guardian.json").read_text(encoding="utf-8"))
        for surface in config["file_size"]["published_rule_surfaces"]:
            text = (deployed / surface).read_text(encoding="utf-8")
            start, end = _passage_span(text)
            self.assertIn("standalone", text[start:end].lower(), msg=f"{surface} must state the rule in force")
        layout_root = deployed.parents[2] if deployed.parent.parent.name == ".leafcutter" else deployed.parents[1]
        result = fx2.run([fx.PYTHON, str(deployed / fx1.SCRIPT_NAME)], layout_root)
        output = fx2.combined_output(result)
        self.assertNotIn("ModuleNotFoundError", output, msg=output)
        self.assertEqual(0, result.returncode, msg=f"zero disagreements over the real surfaces. Got: {output!r}")
        self.assertNotIn(fx1.DISAGREEMENT_TOKEN, output)
        self.assertGreater(fx1.parse_compared_count(output) or 0, 0, msg=f"surfaces compared. Got: {output!r}")

    def test_ge_127d_5_a_surface_left_stating_the_old_measurement_rule_refuses_the_commit(self):
        # covers: GE-127d-5
        # angle: seam
        """Real surfaces in a fixture tree: the old MEASUREMENT RULE paragraph restored to
        README.md alone, the old sentence ADDED beside the new one, and the passage DELETED are
        each a disagreement naming README.md that stops a real commit; reverting returns to clean."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = _real_surface_tree(root)
            readme = dest / "README.md"
            original = readme.read_text(encoding="utf-8")
            start, end = _passage_span(original)
            clean, clean_output = _run_parity(root)
            self.assertEqual(0, clean.returncode, msg=f"the real surfaces must agree to begin with. {clean_output!r}")
            variants = {
                "old_only": original[:start] + f"{MARKER}: {OLD_SENTENCE}" + original[end:],
                "old_beside_new": original[:start] + original[start:end] + " " + OLD_SENTENCE + original[end:],
                "deleted": original[:start] + original[end:],
            }
            fx1.write_precommit_config(root)
            fx1.install_precommit(root)
            for name, mutated in variants.items():
                readme.write_text(mutated, encoding="utf-8")
                fx2.git(["add", "scripts/commit_guardian/README.md"], root)
                result = fx1.commit(root, f"attempt {name}")
                output = fx2.combined_output(result)
                lines = fx1.disagreement_lines(output)
                self.assertNotEqual(0, result.returncode, msg=f"{name}: the commit must not complete. Got: {output!r}")
                self.assertTrue(any("README.md" in ln for ln in lines), msg=f"{name}: must name README.md. {output!r}")
                self.assertFalse(any("commit_guardian.json" in ln for ln in lines), msg=f"{name}: only README.md")
                readme.write_text(original, encoding="utf-8")
                fx2.git(["add", "scripts/commit_guardian/README.md"], root)
                reverted, reverted_output = _run_parity(root)
                self.assertEqual(0, reverted.returncode, msg=f"{name}: reverting returns to clean. {reverted_output!r}")

    def test_ge_127d_5_changing_the_measure_alone_changes_the_generated_rule_and_the_gate_reports_it(self):
        # covers: GE-127d-5
        # angle: discrimination
        """In a fixture copy make the in-force measure count SQL ``--`` comments again, touching no
        surface: the comparison reports a disagreement on EVERY surface. The registered
        check-file-size-rule-parity ``files`` trigger (re.search on the staged path) selects
        _file_size_ratchet.py and each module under _file_size_measure/ in both trees."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = _real_surface_tree(root)
            clean, clean_output = _run_parity(root)
            self.assertEqual(0, clean.returncode, msg=f"baseline must agree. Got: {clean_output!r}")
            ratchet = dest / "_file_size_ratchet.py"
            ratchet.write_text(
                ratchet.read_text(encoding="utf-8")
                + "\n\n_ORIG_COUNT_DASHES = count_content_lines\n\n\n"
                "def count_content_lines(content, *args, **kwargs):  # noqa: F811 -- test-injected mutation\n"
                "    extension = kwargs.get('extension') or (args[0] if args else None)\n"
                "    total = _ORIG_COUNT_DASHES(content, *args, **kwargs)\n"
                "    return total + (sum(1 for ln in content.splitlines() if ln.strip().startswith('--'))"
                " if extension == '.sql' else 0)\n"
                "\n\n_ORIG_MEASURE_DASHES = measure_current_length\n\n\n"
                "def measure_current_length(filepath, *args, **kwargs):  # noqa: F811 -- test-injected mutation\n"
                "    total = _ORIG_MEASURE_DASHES(filepath, *args, **kwargs)\n"
                "    if str(filepath).endswith('.sql'):\n"
                "        total += sum(1 for ln in open(filepath, encoding='utf-8') if ln.strip().startswith('--'))\n"
                "    return total\n",
                encoding="utf-8",
            )
            mutated, mutated_output = _run_parity(root)
            lines = fx1.disagreement_lines(mutated_output)
            self.assertNotEqual(0, mutated.returncode, msg=f"a measure-only change must be caught. {mutated_output!r}")
            for surface in ("README.md", "commit_guardian.json"):
                self.assertTrue(any(surface in ln for ln in lines), msg=f"{surface} must be named. {mutated_output!r}")
        # BrainCandy 2026-10-21: the blank-line probe must read as uncounted, so a measure that
        # counts blank lines again must change the generated statement and be reported too.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = _real_surface_tree(root)
            ratchet = dest / "_file_size_ratchet.py"
            ratchet.write_text(
                ratchet.read_text(encoding="utf-8")
                + "\n\n_ORIG_COUNT_BLANKS = count_content_lines\n\n\n"
                "def count_content_lines(content, *args, **kwargs):  # noqa: F811 -- test-injected mutation\n"
                "    total = _ORIG_COUNT_BLANKS(content, *args, **kwargs)\n"
                "    return total + sum(1 for ln in content.splitlines() if not ln.strip())\n",
                encoding="utf-8",
            )
            mutated, mutated_output = _run_parity(root)
            lines = fx1.disagreement_lines(mutated_output)
            self.assertNotEqual(0, mutated.returncode, msg=f"a blank-counting measure must be caught. {mutated_output!r}")
            for surface in ("README.md", "commit_guardian.json"):
                self.assertTrue(any(surface in ln for ln in lines), msg=f"{surface} must be named. {mutated_output!r}")
        config = json.loads((fx.GUARDIAN_SRC / "commit_guardian.json").read_text(encoding="utf-8"))
        entries =[d for d in _walk(config) if d.get("id") == "check-file-size-rule-parity"]
        trigger = next(d["files"] for d in entries if "files" in d)
        ground = next(d["ground"] for d in entries if "ground" in d)
        measure_dir = fx.GUARDIAN_SRC / "_file_size_measure"
        modules = {"__init__.py", "python_lines.py", "c_family_lines.py", "sql_lines.py", "shell_lines.py"}
        modules |= {p.name for p in measure_dir.glob("*.py")} if measure_dir.is_dir() else set()
        for tree in ("templates/scripts/commit_guardian/", "scripts/commit_guardian/"):
            for rel in ("_file_size_ratchet.py", *[f"_file_size_measure/{m}" for m in sorted(modules)]):
                self.assertIsNotNone(re.search(trigger, tree + rel), msg=f"the trigger must select {tree + rel}")
        self.assertIn("_file_size_measure", ground, msg="the consumer-layout ground entry names the same set")
        self.assertIn("_file_size_ratchet.py", ground)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


if __name__ == "__main__":
    unittest.main()
