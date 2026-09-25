"""
MODULE: test_km_300a_1_doc_index_posix_links
GOAL: RED test-first regression tests for KM-300a-1 -- "Every link in the
    documentation map uses forward slashes, whichever OS generated it".
BUG: `_render_single_file()` and `_render_directory()` in
    scripts/generate_doc_index.py both compute `rel = <path>.relative_to(repo_root)`
    and interpolate `rel` directly into `[{rel}]({rel})`. This calls
    `str(<pathlib.Path>)`, which stringifies using the HOST's native path
    separator. On a Windows host, `rel` is a `WindowsPath` and every link text
    and link target in the generated docs/INDEX.md contains backslashes
    instead of forward slashes -- in both the directory-table sections
    (Components, ADRs, Retrospectives, ...) and the single-file sections
    (Glossary).
FIX: both rendering sites must derive the link text/target from a POSIX
    rendering of the relative path (e.g. `rel.as_posix()`), not from a bare
    `str(rel)`/f-string interpolation of the pathlib object, and the fix must
    cover BOTH call sites -- a half-fix (one site only) must still fail.
ARCHITECTURE: Unit tests exercising `generate_doc_index.generate_index()`
    directly against a synthetic docs tree built under
    `tempfile.TemporaryDirectory()`. No I/O to the real docs/ tree.

    Two of the three tests below force the module's `.relative_to()` calls to
    return a `PureWindowsPath`/`PurePosixPath` rendering instead of whatever
    the real Path.relative_to(...) call natively returns on the host running
    the suite, by patching `pathlib.Path.relative_to` for the duration of the
    `generate_index()` call. `pathlib.Path` sits before `PurePosixPath` /
    `PureWindowsPath` / `PurePath` in the MRO of both `WindowsPath` and
    `PosixPath` (see `pathlib.WindowsPath.__mro__`), so patching the
    `relative_to` attribute on `Path` intercepts the exact call sites the
    generator uses (`path.relative_to(repo_root)` at both rendering
    functions) without touching scripts/generate_doc_index.py itself. This
    seam still intercepts correctly after a correct fix that calls
    `.as_posix()` on the relative path: `.as_posix()` on a `PureWindowsPath`
    (or `PurePosixPath`) object normalizes to forward slashes regardless of
    which flavour produced it -- that IS what `.as_posix()` is for -- so a
    real fix stays green under this patch, while the current bare
    `str(rel)`/f-string interpolation stays red.

    This deliberately does NOT rely on the actual host OS to prove the
    cross-flavour identity in test 3: comparing "whatever this host produces"
    against a simulated Windows flavour would coincidentally already be equal
    (both backslash) on a real Windows host running the unfixed code, which
    would let the bug hide behind a false green on exactly the host this
    defect was discovered on. Simulating both flavours explicitly keeps the
    test's red/green status independent of which OS the suite happens to run
    on.

# covers: KM-300a-1
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest import mock

# ---------------------------------------------------------------------------
# Path setup: unit_tests/commit_guardian/ is 3 levels below the repo root
# (matches the existing sibling tests test_generate_doc_index_last_updated.py
# and test_km_dbf_014_doc_index_idempotent.py).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_doc_index as gdi  # noqa: E402


_BACKSLASH = chr(92)

# Matches every markdown [text](target) link pair in the generated content.
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Captured BEFORE any patching below, so the fake implementations can still
# call through to the real relative-path computation.
_REAL_RELATIVE_TO = Path.relative_to


def _fake_relative_to(flavour_cls):
    """Build a `Path.relative_to` replacement that renders results as
    `flavour_cls` (a `PureWindowsPath` or `PurePosixPath`) instead of
    whatever concrete class the real `.relative_to()` call would have
    returned on this host.

    This is the seam: it intercepts exactly the two call sites the generator
    uses (`path.relative_to(repo_root)` in `_render_single_file()` and
    `_render_directory()`), without modifying generate_doc_index.py.

    Args:
        flavour_cls: `PureWindowsPath` or `PurePosixPath`.

    Returns:
        A function with the same signature as `Path.relative_to`, suitable
        for `mock.patch.object(Path, "relative_to", new=...)`.
    """

    def _relative_to(self, *other, **kwargs):
        real_rel = _REAL_RELATIVE_TO(self, *other, **kwargs)
        return flavour_cls(*real_rel.parts)

    return _relative_to


def _build_fixture_repo(repo_root: Path) -> None:
    """Create the docs tree named in KM-300a-1's Given clause.

    Populates:
      - docs/architecture/adrs/ADR-001-self-hosting-boundary.md (a
        table-section entry, three folders deep)
      - docs/architecture/components/ac-driven-dev.md (a component page,
        also a table-section entry)
      - docs/retrospectives/EPIC-ACDrivenDevelopment.md (a retrospective,
        also a table-section entry)
      - docs/glossary.md (the single-file Glossary section, not a table)

    Args:
        repo_root: Root of a synthetic repo (a tempdir) to populate.
    """
    adrs_dir = repo_root / "docs" / "architecture" / "adrs"
    components_dir = repo_root / "docs" / "architecture" / "components"
    retro_dir = repo_root / "docs" / "retrospectives"
    for d in (adrs_dir, components_dir, retro_dir):
        d.mkdir(parents=True, exist_ok=True)

    (adrs_dir / "ADR-001-self-hosting-boundary.md").write_text(
        '---\ndescription: "Fixture ADR for KM-300a-1."\n---\n\n'
        "# ADR-001: Self-Hosting Boundary\n",
        encoding="utf-8",
    )
    (components_dir / "ac-driven-dev.md").write_text(
        '---\ndescription: "Fixture component page for KM-300a-1."\n---\n\n'
        "# AC-Driven Development\n",
        encoding="utf-8",
    )
    (retro_dir / "EPIC-ACDrivenDevelopment.md").write_text(
        '---\ndescription: "Fixture retrospective for KM-300a-1."\n---\n\n'
        "# EPIC-ACDrivenDevelopment Retrospective\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "glossary.md").write_text(
        '---\ndescription: "Fixture glossary for KM-300a-1."\n---\n\n'
        "# Glossary\n",
        encoding="utf-8",
    )


def _extract_links(content: str) -> list[tuple[str, str]]:
    """Extract every `[text](target)` markdown link pair from *content*."""
    return _LINK_RE.findall(content)


def _find_link_ending_with(
    links: list[tuple[str, str]], suffix_posix: str
) -> tuple[str, str] | None:
    """Find the first (text, target) pair whose forward-slash-normalized
    link TEXT ends with *suffix_posix*, tolerating a backslash-flavoured text
    on the buggy code path. Matched on text because KM-300a-2 makes the
    target relative to the map's folder while the text keeps the root path.
    """
    for text, target in links:
        normalized = text.replace(_BACKSLASH, "/")
        if normalized.endswith(suffix_posix):
            return (text, target)
    return None


class TestDocIndexPosixLinkPaths(unittest.TestCase):
    """KM-300a-1: every doc-index link uses forward slashes on any host OS."""

    def test_doc_index_links_use_forward_slashes_in_table_and_single_file_sections(
        self,
    ) -> None:
        # covers: KM-300a-1
        # angle: criterion
        """Builds the fixture docs tree and calls generate_index() with no
        patching (i.e. using whatever the real host's `.relative_to()`
        naturally returns). Asserts the ADR row's link text is exactly
        `docs/architecture/adrs/ADR-001-self-hosting-boundary.md`, the
        Glossary entry's link text is exactly `docs/glossary.md`, and no
        link text or target anywhere in the generated content contains a
        backslash.

        Fails red on the current code on a Windows host, where both
        rendering sites render `str(WindowsPath)` with backslashes.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _build_fixture_repo(repo_root)
            content = gdi.generate_index(repo_root)

        links = _extract_links(content)

        adr_pair = _find_link_ending_with(
            links, "docs/architecture/adrs/ADR-001-self-hosting-boundary.md"
        )
        self.assertIsNotNone(
            adr_pair, f"ADR link not found among extracted links: {links}"
        )
        self.assertEqual(
            adr_pair[0],
            "docs/architecture/adrs/ADR-001-self-hosting-boundary.md",
            f"ADR link text must be a forward-slash path. Got: {adr_pair[0]!r}",
        )
        self.assertEqual(
            adr_pair[1],
            "architecture/adrs/ADR-001-self-hosting-boundary.md",
            f"ADR link target must be a forward-slash path. Got: {adr_pair[1]!r}",
        )

        glossary_pair = _find_link_ending_with(links, "docs/glossary.md")
        self.assertIsNotNone(
            glossary_pair, f"Glossary link not found among extracted links: {links}"
        )
        self.assertEqual(
            glossary_pair[0],
            "docs/glossary.md",
            f"Glossary link text must be a forward-slash path. Got: {glossary_pair[0]!r}",
        )
        self.assertEqual(
            glossary_pair[1],
            "glossary.md",
            f"Glossary link target must be a forward-slash path. Got: {glossary_pair[1]!r}",
        )

        offenders = [
            pair
            for pair in links
            if _BACKSLASH in pair[0] or _BACKSLASH in pair[1]
        ]
        self.assertEqual(
            offenders,
            [],
            "No link text or link target may contain a backslash. "
            f"Offending pairs: {offenders}",
        )

    def test_doc_index_links_forward_slash_under_simulated_windows_path_flavour(
        self,
    ) -> None:
        # covers: KM-300a-1
        # angle: criterion
        """Same fixture, but patches `pathlib.Path.relative_to` (the exact
        call the generator makes at both rendering sites) so it returns a
        `PureWindowsPath` -- backslash-stringifying -- for every entry.
        Asserts one table-section entry (the ADR) and the Glossary
        single-file entry both still carry forward-slash link text and
        target, and that no backslash appears anywhere inside any `[..]` or
        `(..)`.

        Makes the defect red on a POSIX CI host too: a half-fix covering
        only one of the two rendering sites stays red, because both the
        table-section ADR entry and the single-file Glossary entry are
        checked.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _build_fixture_repo(repo_root)
            with mock.patch.object(
                Path, "relative_to", new=_fake_relative_to(PureWindowsPath)
            ):
                content = gdi.generate_index(repo_root)

        links = _extract_links(content)

        adr_pair = _find_link_ending_with(
            links, "docs/architecture/adrs/ADR-001-self-hosting-boundary.md"
        )
        self.assertIsNotNone(
            adr_pair,
            f"ADR link not found among extracted links under simulated "
            f"Windows path flavour: {links}",
        )
        self.assertEqual(
            adr_pair[0],
            "docs/architecture/adrs/ADR-001-self-hosting-boundary.md",
            "ADR link text must be forward-slash even when the underlying "
            f".relative_to() call returns a PureWindowsPath. Got: {adr_pair[0]!r}",
        )
        self.assertEqual(
            adr_pair[1],
            "architecture/adrs/ADR-001-self-hosting-boundary.md",
            "ADR link target must be forward-slash even when the underlying "
            f".relative_to() call returns a PureWindowsPath. Got: {adr_pair[1]!r}",
        )

        glossary_pair = _find_link_ending_with(links, "docs/glossary.md")
        self.assertIsNotNone(
            glossary_pair,
            f"Glossary link not found among extracted links under simulated "
            f"Windows path flavour: {links}",
        )
        self.assertEqual(
            glossary_pair[0],
            "docs/glossary.md",
            "Glossary link text must be forward-slash even when the "
            f"underlying .relative_to() call returns a PureWindowsPath. "
            f"Got: {glossary_pair[0]!r}",
        )
        self.assertEqual(
            glossary_pair[1],
            "glossary.md",
            "Glossary link target must be forward-slash even when the "
            f"underlying .relative_to() call returns a PureWindowsPath. "
            f"Got: {glossary_pair[1]!r}",
        )

        offenders = [
            pair
            for pair in links
            if _BACKSLASH in pair[0] or _BACKSLASH in pair[1]
        ]
        self.assertEqual(
            offenders,
            [],
            "No link text or link target may contain a backslash under a "
            f"simulated Windows path flavour. Offending pairs: {offenders}",
        )

    def test_doc_index_links_identical_across_path_flavours(self) -> None:
        # covers: KM-300a-1
        # angle: criterion
        """Generates the same fixture twice: once with `.relative_to()`
        forced to a `PurePosixPath` rendering (simulating a Linux/macOS
        host) and once forced to a `PureWindowsPath` rendering (simulating a
        Windows host), and asserts the extracted link text/target lists are
        equal character for character.

        Both flavours are explicitly simulated -- rather than comparing
        "whatever this host naturally produces" against a simulated Windows
        flavour -- so this test's red/green status does not depend on which
        OS happens to be running the suite. On the unfixed code, the POSIX
        flavour renders forward slashes (because `str(PurePosixPath(...))`
        already uses "/") while the Windows flavour renders backslashes
        (because `str(PureWindowsPath(...))` uses "\\\\"), so the two lists
        differ and this test is red on ANY host, including a real Windows
        host running the unfixed code. After a correct `.as_posix()` fix,
        both flavours normalize to forward slashes and the lists become
        equal.
        """
        with tempfile.TemporaryDirectory() as tmp_posix:
            repo_root_posix = Path(tmp_posix)
            _build_fixture_repo(repo_root_posix)
            with mock.patch.object(
                Path, "relative_to", new=_fake_relative_to(PurePosixPath)
            ):
                posix_flavour_content = gdi.generate_index(repo_root_posix)

        with tempfile.TemporaryDirectory() as tmp_windows:
            repo_root_windows = Path(tmp_windows)
            _build_fixture_repo(repo_root_windows)
            with mock.patch.object(
                Path, "relative_to", new=_fake_relative_to(PureWindowsPath)
            ):
                windows_flavour_content = gdi.generate_index(repo_root_windows)

        posix_links = _extract_links(posix_flavour_content)
        windows_links = _extract_links(windows_flavour_content)

        self.assertEqual(
            posix_links,
            windows_links,
            "The extracted link text/target pairs must be identical whether "
            "the documentation map is generated under a simulated POSIX "
            "path flavour or a simulated Windows path flavour. "
            f"POSIX flavour: {posix_links}\nWindows flavour: {windows_links}",
        )


if __name__ == "__main__":
    unittest.main()
