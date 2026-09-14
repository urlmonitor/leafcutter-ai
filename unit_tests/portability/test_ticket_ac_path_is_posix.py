"""
MODULE: unit_tests/portability/test_ticket_ac_path_is_posix.py
GOAL: A ticket's ac_traceability.path is an identifier, not a filesystem path,
    and must render identically on every platform.
BUSINESS CONTEXT: generate_ticket_from_ac.py built that value with
    str(ac_path.relative_to(...)), which renders with os.sep. Every ticket
    generated on Windows recorded a path with backslashes -- all 45 of the
    EPIC-WhatYourProjectSaysAboutItselfIsTrue epic did -- and ac-fulfillment-gate,
    marked needed on each of them, resolves that field in CI on Linux where such
    a path names nothing. The identical defect shipped in
    generate_product_truth.py and made the product-truth validator unpassable on
    Windows; _canonicalise_ticket_path in generate_ticket_from_ac.py itself
    already guards against it, so the knowledge existed and simply had not
    reached this construction site.
ARCHITECTURE: Asserts on string content rather than round-tripping through
    pathlib. A round-trip normalises separators and would pass on POSIX -- the
    platform that cannot reproduce the bug -- so it would never have caught this.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GENERATOR = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
_BACKSLASH = chr(92)


class TestTicketAcPathIsPlatformIndependent(unittest.TestCase):
    def test_generator_builds_the_ac_path_with_as_posix(self) -> None:
        source = _GENERATOR.read_text(encoding="utf-8")
        self.assertIn(
            "ac_path.relative_to(ac_root.parent.parent).as_posix()",
            source,
            "the ac_traceability path must be built with as_posix(); str() "
            "renders with os.sep and writes a Windows-only path into a field "
            "that CI resolves on Linux",
        )
        self.assertNotIn(
            "str(ac_path.relative_to(ac_root.parent.parent))",
            source,
            "the str() form is the defect and must not return",
        )

    def test_no_committed_ticket_carries_a_platform_separator_ac_path(self) -> None:
        tickets_root = _REPO_ROOT / "tickets"
        if not tickets_root.is_dir():
            self.skipTest("no tickets/ tree in this checkout")
        offenders = []
        for ticket in tickets_root.rglob("*.md"):
            try:
                text = ticket.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("path:") and _BACKSLASH in stripped:
                    offenders.append(f"{ticket.relative_to(_REPO_ROOT).as_posix()}: {stripped}")
                    break
        self.assertEqual(
            offenders,
            [],
            "ticket frontmatter must not carry platform-separator paths -- "
            "ac-fulfillment-gate resolves them on Linux. Offenders:\n  "
            + "\n  ".join(offenders[:10]),
        )


if __name__ == "__main__":
    unittest.main()
