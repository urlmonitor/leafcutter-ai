"""
MODULE: test_ge_118e
GOAL: TDD red-baseline tests for AC GE-118e -- the document-frontmatter
    reference and the pre-commit-hooks guide teach the accepted path-entry
    shapes, with examples that are EXECUTED through the real guard.
BUSINESS CONTEXT: Example convention (fixed): a fenced block with info string
    ``yaml accepted`` or ``yaml refused`` holding a standalone frontmatter
    mapping; each ``yaml refused`` block is immediately followed by a ``text``
    block quoting the guard's actual output line(s). See _ge_118e_fixtures.py.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts"))

from frontmatter_path_resolver import (  # noqa: E402
    ACCEPTED_SHAPES,
    PathEntryRefusal,
    resolve_frontmatter_path_entry,
)

from . import _ge_118e_fixtures as fx  # noqa: E402

_DOCS = (fx.FRONTMATTER_DOC, fx.README_DOC)


def _path_entries(example: fx.Example):
    for field in fx.PATH_FIELD_NAMES:
        entries = example.mapping.get(field)
        if isinstance(entries, list):
            for entry in entries:
                yield field, entry


class TestGe118eExecutableDocumentation(unittest.TestCase):
    def test_ge_118e_every_example_entry_in_both_documents_behaves_as_the_documents_claim(self):
        # covers: GE-118e
        # angle: real_artifact
        """Both documents must carry marked examples; the guard must agree with each."""
        for doc in _DOCS:
            examples = fx.extract_examples(doc)
            kinds = [e.kind for e in examples]
            self.assertGreaterEqual(
                kinds.count("accepted"), 1,
                f"{doc.name} has no 'yaml accepted' example (found {len(examples)} marked examples)",
            )
            self.assertGreaterEqual(
                kinds.count("refused"), 1,
                f"{doc.name} has no 'yaml refused' example (found {len(examples)} marked examples)",
            )
            for example in examples:
                with self.subTest(doc=doc.name, line=example.line, kind=example.kind):
                    result = fx.run_guard(example)
                    output = result.stdout + result.stderr
                    if example.kind == "accepted":
                        self.assertEqual(
                            result.returncode, 0,
                            f"{doc.name}:{example.line} presented as accepted but the guard refused it:\n{output}",
                        )
                    else:
                        self.assertNotEqual(
                            result.returncode, 0,
                            f"{doc.name}:{example.line} presented as refused but the guard accepted it:\n{output}",
                        )
                        self.assertTrue(
                            any(line.startswith("Unsupported entry") for line in example.refusal_lines),
                            f"{doc.name}:{example.line} quoted text has no 'Unsupported entry' line",
                        )
                        for expected in example.refusal_lines:
                            self.assertIn(
                                expected, output,
                                f"{doc.name}:{example.line} quotes a message the guard does not emit",
                            )


class TestGe118eShapeSetEqualsResolverSet(unittest.TestCase):
    def test_ge_118e_the_shape_set_the_documents_enumerate_equals_the_resolvers_accepted_set(self):
        # covers: GE-118e
        # angle: seam
        """Documents enumerate exactly ACCEPTED_SHAPES, and their accepted examples exercise each."""
        for doc in _DOCS:
            text = fx.read_document(doc)
            for shape in ACCEPTED_SHAPES:
                self.assertTrue(shape in text, f"{doc.name} does not state accepted shape {shape!r} verbatim")
            accepted = [e for e in fx.extract_examples(doc) if e.kind == "accepted"]
            self.assertGreaterEqual(len(accepted), 1, f"{doc.name} has no accepted example")
            saw_bare = saw_mapping = False
            for example in accepted:
                for field, entry in _path_entries(example):
                    resolved = resolve_frontmatter_path_entry(entry, field)
                    self.assertNotIsInstance(
                        resolved, PathEntryRefusal,
                        f"{doc.name}:{example.line} accepted example holds a shape the resolver refuses: {entry!r}",
                    )
                    if isinstance(entry, str):
                        saw_bare = True
                    elif isinstance(entry, dict):
                        self.assertEqual(len(entry), 1, f"{doc.name}:{example.line} shows a multi-key mapping")
                        saw_mapping = True
            self.assertTrue(saw_bare, f"{doc.name} accepted examples show no bare string entry")
            self.assertTrue(saw_mapping, f"{doc.name} accepted examples show no single-key mapping entry")


class TestGe118eSupersededDescription(unittest.TestCase):
    def test_ge_118e_the_superseded_path_existence_only_description_is_gone_and_the_reference_link_resolves(self):
        # covers: GE-118e
        # angle: criterion
        """README row no longer says path-existence-only, and its reference link resolves."""
        rows = [
            line for line in fx.read_document(fx.README_DOC).splitlines()
            if line.startswith("| `check_doc_frontmatter.py`")
        ]
        self.assertEqual(len(rows), 1, "expected exactly one check_doc_frontmatter.py row in the README")
        row = rows[0]
        self.assertNotIn(
            "path existence of `related_docs` / `related_code`", row,
            "superseded path-existence-only description is still in the row",
        )
        targets = [t.split("#")[0] for t in re.findall(r"\]\(([^)]+)\)", row)]
        reference = [t for t in targets if t.endswith("FRONTMATTER.md")]
        self.assertTrue(reference, "row has no link to FRONTMATTER.md")
        for target in reference:
            resolved = (fx.README_DOC.parent / target).resolve()
            self.assertTrue(resolved.is_file(), f"reference link {target!r} resolves to missing {resolved}")


class TestGe118eAllThreeFields(unittest.TestCase):
    def test_ge_118e_all_three_path_fields_are_documented_with_the_same_rule(self):
        # covers: GE-118e
        # angle: boundary
        """Every field in the guard's own path_fields list appears in both documents."""
        tree = ast.parse(fx.read_document(fx.VALIDATORS))
        fields = None
        for func in ast.walk(tree):
            if isinstance(func, ast.FunctionDef) and func.name == "validate_paths":
                for node in ast.walk(func):
                    if (
                        isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "path_fields" for t in node.targets)
                        and isinstance(node.value, ast.List)
                    ):
                        fields = [ast.literal_eval(elt) for elt in node.value.elts]
        if not fields:
            fx.fail("cannot find path_fields list literal inside validate_paths()")
        for doc in _DOCS:
            text = fx.read_document(doc)
            for field in fields:
                self.assertTrue(field in text, f"{doc.name} does not mention path field {field!r}")


if __name__ == "__main__":
    unittest.main()
