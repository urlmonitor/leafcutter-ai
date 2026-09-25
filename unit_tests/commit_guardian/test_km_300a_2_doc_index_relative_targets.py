"""
MODULE: test_km_300a_2_doc_index_relative_targets
GOAL: Regression tests for KM-300a-2 -- "Each link in the documentation map
    points at its page relative to where the map itself lives".
BUG: scripts/generate_doc_index.py used the project-root path
    (docs/architecture/...) as both link text AND link target. The map is
    written to docs/INDEX.md, and a relative Markdown link resolves against
    the file's own folder, so every target opened docs/docs/... -- a 404 on
    the code host and a dead link locally.
FIX: link targets are the path from the folder the map is written to; link
    text keeps the project-root path. write_index and the transform-doc-index
    pre-commit hook must emit byte-identical content.
ARCHITECTURE: direct-import unit tests over a temp docs tree, mirroring
    test_km_300a_1_doc_index_posix_links. The resolution test writes the map
    to disk and resolves every target from the map's folder, case-exactly, so
    the verdict is host-independent and cannot pass on zero links.

# covers: KM-300a-2
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import generate_doc_index as gdi  # noqa: E402

_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "transform_doc_index.py"
)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_ADR = "architecture/adrs/ADR-001-self-hosting-boundary.md"


def _make_docs_tree(root: Path) -> None:
    """Create a small docs tree covering a table section and a single-file section.

    Args:
        root: Temp repository root to populate.
    """
    files = {
        f"docs/{_ADR}": "ADR-001",
        "docs/architecture/components/ac-driven-dev.md": "Component",
        "docs/retrospectives/EPIC-ACDrivenDevelopment.md": "Retro",
        "docs/glossary.md": "Glossary",
    }
    for rel, title in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\ntitle: {title}\ndescription: {title} page.\n---\n\n# {title}\n",
            encoding="utf-8",
        )


def _links(content: str) -> list[tuple[str, str]]:
    """Return every (text, target) Markdown link pair in the map content."""
    return _LINK_RE.findall(content)


class TestDocIndexRelativeTargets(unittest.TestCase):
    """KM-300a-2: link targets resolve from the map's own folder."""

    def test_doc_index_link_targets_are_relative_to_map_folder(self):
        # covers: KM-300a-2
        # angle: criterion
        """The ADR and Glossary targets are relative to docs/, while their
        link text keeps the project-root path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_docs_tree(root)
            pairs = dict(_links(gdi.generate_index(root)))

            self.assertEqual(pairs.get(f"docs/{_ADR}"), _ADR)
            self.assertEqual(pairs.get("docs/glossary.md"), "glossary.md")
            self.assertFalse(
                [t for t in pairs.values() if t.startswith("docs/")],
                f"No target may start with docs/ inside docs/INDEX.md: {pairs}",
            )

    def test_every_doc_index_link_target_resolves_from_map_folder(self):
        # covers: KM-300a-2
        # angle: real_artifact
        """Every target in the written map names an existing file, case-exactly,
        when joined with the folder the map was written to."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_docs_tree(root)
            written = gdi.write_index(root)
            map_dir = written.parent
            pairs = _links(written.read_text(encoding="utf-8"))

            self.assertGreaterEqual(len(pairs), 4, "The check must inspect real links.")
            for text, target in pairs:
                resolved = (map_dir / target).resolve()
                self.assertTrue(resolved.is_file(), f"{text} -> {target} opens nothing")
                self.assertIn(
                    resolved.name,
                    [p.name for p in resolved.parent.iterdir()],
                    f"{target} differs in case from the file on disk",
                )

    def test_transform_hook_and_generator_emit_same_relative_targets(self):
        # covers: KM-300a-2
        # angle: seam
        """The transform-doc-index hook writes byte-identical content to write_index."""
        spec = importlib.util.spec_from_file_location("transform_doc_index", _HOOK_PATH)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            gen_root, hook_root = Path(a), Path(b)
            _make_docs_tree(gen_root)
            _make_docs_tree(hook_root)
            expected = gdi.write_index(gen_root).read_text(encoding="utf-8")

            with mock.patch.object(
                hook, "_get_staged_docs_files", return_value=["docs/glossary.md"]
            ), mock.patch.object(
                hook, "_find_generator_module", return_value=gdi
            ), mock.patch.object(hook, "_restage_index"):
                hook.main(repo_root=hook_root)

            actual = (hook_root / "docs" / "INDEX.md").read_text(encoding="utf-8")
            self.assertEqual(actual, expected)
            self.assertIn(f"]({_ADR})", actual)


if __name__ == "__main__":
    unittest.main()
