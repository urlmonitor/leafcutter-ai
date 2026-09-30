"""
MODULE: test_predone_scope_docs_only_out_of_scope
GOAL: Unit tests for BP-1100e-1-iii as amended — a docs-only ticket's
    out_of_scope declarations survive the docs-only guard, so a documentation
    ticket on a multi-ticket branch can be marked done.
BUSINESS CONTEXT: FIELD EVIDENCE — BO-400e-5, 2026-09-23. Committing the
    status: done flip for a documentation-only ticket failed with 24 undeclared
    source files, every one of which was ALREADY listed in that ticket's
    out_of_scope. The hook's own parser read them correctly; the docs-only
    branch returned a bare empty set before they were unioned in, so the
    declared scope was empty and the whole branch's accumulated source diff was
    reported undeclared.

    The remedy the hook printed was the one thing that could not work. The files
    were already in out_of_scope; adding them to files_touched would have made
    the ticket claim source it never touched — a false record of exactly the
    kind this component exists to prevent — and would also have flipped the
    ticket out of docs-only classification, itself a lie about the change. The
    hook was skipped twice on that ticket. See KI-BO-20260923-0700.
ARCHITECTURE: These call _get_ticket_scope against real on-disk ticket files
    written with column-0 YAML block lists, which is how the ticket store
    actually serialises these fields (BP-1100e-1-v). An indented literal would
    reproduce the authoring bias that once made the whole hook a no-op on every
    real ticket — see the EPIC-PhantomDoneFilesTouched retrospective.

    The middle test is load-bearing. The fix must be a NARROWING, not a removal:
    a "fix" that simply deleted the docs-only branch would satisfy the first
    test and still be wrong, because a docs-only ticket declaring nothing out of
    scope would then absorb source changes it never mentioned. Only the pair
    distinguishes the two.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "hooks"
    / "check_files_touched_reconciliation.py"
)


def _load_hook() -> Any:
    """Load the hook module from its template path.

    Typed ``Any`` because the returned object's attribute surface is defined by
    the source file it executes, which mypy cannot know statically.

    Returns:
        Loaded module object.

    Raises:
        ImportError: When the hook script does not exist.
    """
    if not HOOK_PATH.exists():
        msg = f"Hook not found at {HOOK_PATH}."
        raise ImportError(msg)
    spec = importlib.util.spec_from_file_location(
        "check_files_touched_reconciliation_docsonly", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _write_ticket(root: Path, name: str, files_touched: str, out_of_scope: str) -> str:
    """Write a done ticket whose list fields use column-0 block serialization.

    Column 0 is deliberate: it is how the ticket store's own writer emits these
    lists, and an indented fixture would not exercise the real parser path.

    Args:
        root: Directory to write the ticket into.
        name: Ticket filename.
        files_touched: Pre-rendered YAML for the files_touched value.
        out_of_scope: Pre-rendered YAML for the out_of_scope value.

    Returns:
        The ticket's path relative to *root*.
    """
    # Assembled by join rather than textwrap.dedent: dedent runs AFTER the
    # substitution, and a multi-line value whose continuation lines start at
    # column 0 collapses the common prefix to "", leaving the --- markers
    # indented and the frontmatter unparseable. The failure looks like the
    # hook rejecting the ticket.
    body = "\n".join(
        [
            "---",
            "status: done",
            "files_touched:",
            files_touched,
            "out_of_scope:",
            out_of_scope,
            "---",
            "",
            "# Ticket body",
            "",
        ]
    )
    (root / name).write_text(body, encoding="utf-8")
    return name


class TestDocsOnlyTicketKeepsOutOfScope(unittest.TestCase):
    """BP-1100e-1-iii (amended): out_of_scope survives the docs-only guard."""

    def setUp(self) -> None:
        self.hook = _load_hook()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_docs_only_ticket_declares_its_out_of_scope_source_files(self) -> None:
        # covers: BP-1100e-1-iii
        """The broken case: a docs-only ticket that DID declare out_of_scope.

        Its declared scope must contain those entries, so the branch-range
        source diff they name is recognised as declared rather than reported
        undeclared.
        """
        name = _write_ticket(
            self.root,
            "01_TICKET-docs-only.md",
            files_touched="- docs/architecture/diagrams/c3-012-example.md\n"
            "- docs/architecture/components/build-orchestration.md",
            out_of_scope="- scripts/set_ticket_status.py\n"
            "- templates/workflows-js/build-feature.js",
        )

        scope = self.hook._get_ticket_scope(name, str(self.root))

        self.assertIsNotNone(scope, "A done ticket with declared lists must yield a scope.")
        self.assertIn(
            self.hook._normalise_path("scripts/set_ticket_status.py"),
            scope,
            "An out_of_scope entry on a docs-only ticket must reach the declared "
            "scope; discarding it is what made the hook's printed remedy "
            f"impossible to follow. Got: {scope}",
        )
        self.assertIn(
            self.hook._normalise_path("templates/workflows-js/build-feature.js"),
            scope,
            f"Every out_of_scope entry must survive, not just the first. Got: {scope}",
        )

    def test_docs_only_ticket_declaring_nothing_out_of_scope_stays_empty(self) -> None:
        # covers: BP-1100e-1-iii
        """The guard that must stay strict — this is the load-bearing case.

        A docs-only ticket that declares NOTHING out of scope must still yield
        an empty declared scope, so it cannot silently absorb source changes it
        never mentioned. A fix that deleted the docs-only branch outright would
        pass the test above and fail here.
        """
        name = _write_ticket(
            self.root,
            "02_TICKET-docs-only-bare.md",
            files_touched="- docs/architecture/components/build-orchestration.md",
            out_of_scope="[]",
        )

        scope = self.hook._get_ticket_scope(name, str(self.root))

        self.assertIn(
            scope,
            (None, set()),
            "A docs-only ticket declaring nothing out of scope must contribute "
            "no declared paths, so undeclared source changes are still caught. "
            f"Got: {scope}",
        )

    def test_a_source_ticket_still_unions_both_lists(self) -> None:
        # covers: BP-1100e-1-iii
        """BP-1100e-1-iii's own original case: non-docs tickets are unchanged.

        A ticket whose files_touched contains real source does not take the
        docs-only branch at all, and must still declare the union of both
        lists exactly as before this amendment.
        """
        name = _write_ticket(
            self.root,
            "03_TICKET-source.md",
            files_touched="- scripts/build.py",
            out_of_scope="- scripts/unrelated_helper.py",
        )

        scope = self.hook._get_ticket_scope(name, str(self.root))

        self.assertIsNotNone(scope)
        self.assertIn(self.hook._normalise_path("scripts/build.py"), scope)
        self.assertIn(
            self.hook._normalise_path("scripts/unrelated_helper.py"),
            scope,
            f"The union behaviour for source tickets must be untouched. Got: {scope}",
        )


if __name__ == "__main__":
    unittest.main()
