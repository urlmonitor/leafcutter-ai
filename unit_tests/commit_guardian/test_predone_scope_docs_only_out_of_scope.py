"""
MODULE: test_predone_scope_docs_only_out_of_scope
GOAL: Verify BP-1100e-1-viii — a docs-only ticket that explicitly declares source
    files out of scope is answered on that declaration, instead of having it
    discarded and being told to make the declaration it already made.

BUSINESS CONTEXT: FIELD EVIDENCE — 2026-09-23, closing BO-400e-5, the documentation
    ticket of EPIC-WorkIsOnlyEverMarkedFinishedThroughThe. The commit was refused with
    24 undeclared source files, every one of which was already listed in that ticket's
    out_of_scope. The hook's own parser read them correctly; they were thrown away one
    line later by `if is_docs_only_or_config_only_ticket(files_touched): return set()`.
    The printed remedy — "add the above files to files_touched or out_of_scope" — was
    therefore the one action that could not help, and the alternatives were to list
    source files the ticket never touched or to skip the gate. It was skipped twice,
    under protest. Filed as KI-BO-20260923-0700.

    This fires for every documentation ticket in every epic that also contains
    implementation tickets, because the changed-file set is computed over the branch
    range and a docs ticket is usually last.

ARCHITECTURE: Drives the hook's own `_get_ticket_scope` against real ticket files
    written to tmp_path, rather than asserting on source text — the defect was
    precisely that the function's behaviour diverged from the criterion its own
    comment cited, so only executing it can tell the two apart.

    The middle test is what makes this a NARROWING rather than a removal: deleting the
    docs-only branch outright would satisfy the first test and still be wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(
    0, str(_REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "hooks")
)

import check_files_touched_reconciliation as hook  # noqa: E402

_SOURCE_FILE = "templates/workflows-js/build-feature.js"
_OTHER_SOURCE = "scripts/set_ticket_status.py"


def _write_ticket(
    tmp_path: Path, *, files_touched: list[str], out_of_scope: list[str] | None
) -> str:
    """Write a done ticket with the given scope, returning its repo-relative path."""
    lines = ["---", "status: done", "files_touched:"]
    lines += [f"- {p}" for p in files_touched]
    if out_of_scope is not None:
        lines.append("out_of_scope:")
        lines += [f"- {p}" for p in out_of_scope]
    lines += ["---", "", "# A ticket", ""]
    rel = "tickets/00_inbox/TICKET-docs-only.md"
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return rel


class TestDocsOnlyTicketMayDeclareWorkOutOfScope:
    """BP-1100e-1-viii: the docs-only guard narrows the scope, it does not erase it."""

    def test_docs_only_ticket_honours_its_out_of_scope_declaration(
        self, tmp_path: Path
    ) -> None:
        # covers: BP-1100e-1-viii
        # angle: criterion
        """The case that was broken: the declaration is read, not discarded."""
        rel = _write_ticket(
            tmp_path,
            files_touched=["docs/architecture/diagrams/c3-008.md"],
            out_of_scope=[_SOURCE_FILE, _OTHER_SOURCE],
        )
        scope = hook._get_ticket_scope(rel, str(tmp_path))
        assert scope is not None, "a done ticket declaring files_touched must yield a scope"
        assert hook._normalise_path(_SOURCE_FILE) in scope, (
            "a source file the ticket explicitly declared out of scope must count as "
            "declared; discarding it makes the hook's own printed remedy impossible"
        )
        assert hook._normalise_path(_OTHER_SOURCE) in scope

    def test_docs_only_ticket_still_flags_a_file_it_declared_nowhere(
        self, tmp_path: Path
    ) -> None:
        # covers: BP-1100e-1-viii
        # angle: failure
        """The guard is narrowed, not removed.

        A fix that simply deleted the docs-only branch would pass the test above and
        still be wrong; this is the test that rules it out.
        """
        rel = _write_ticket(
            tmp_path,
            files_touched=["docs/architecture/diagrams/c3-008.md"],
            out_of_scope=[_OTHER_SOURCE],
        )
        scope = hook._get_ticket_scope(rel, str(tmp_path))
        assert scope is not None
        assert hook._normalise_path(_SOURCE_FILE) not in scope, (
            "a source file named in neither list must remain undeclared, so the "
            "reconciliation still flags it"
        )

    def test_docs_only_ticket_with_no_out_of_scope_is_unchanged(
        self, tmp_path: Path
    ) -> None:
        # covers: BP-1100e-1-viii
        # angle: boundary
        """BP-1100e-1-iii's own case must not regress.

        Declaring nothing out of scope still yields an empty declared scope, so a docs
        ticket cannot silently absorb source changes it never mentioned.
        """
        rel = _write_ticket(
            tmp_path,
            files_touched=["docs/architecture/diagrams/c3-008.md"],
            out_of_scope=None,
        )
        scope = hook._get_ticket_scope(rel, str(tmp_path))
        assert scope in (set(), None), (
            "a docs-only ticket declaring nothing out of scope must contribute no "
            f"declared source paths; got {scope}"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
