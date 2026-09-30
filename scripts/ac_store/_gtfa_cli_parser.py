#!/usr/bin/env python3
"""
MODULE: _gtfa_cli_parser
GOAL: Define the ticket generator's command-line surface.
BUSINESS CONTEXT: Two of these flags exist to stop a specific silent failure
    rather than to add convenience. ``--resolved-destination`` and
    ``--location-kind`` both answer "where will this ticket finally live?",
    which decides whether the drive defers a phase for it; ``--tickets-root``
    is NEVER accepted as a substitute, because it may be a staging root a later
    step moves the file out of. Neither flag has a default: defaulting to
    ``standalone`` on silence would classify every epic member as standalone
    and silently restore the ``pull-request: needed`` defect the mechanism
    removes.
ARCHITECTURE: Parser construction only — no side effects, no I/O — so the
    argparse surface can be introspected by a test without running anything.
    Help text carries the reasoning, because the refusal a caller hits when it
    omits a location is otherwise hard to act on.
"""

from __future__ import annotations

import argparse
import importlib

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)

_DEFAULT_AC_ROOT = _gtfa_constants._DEFAULT_AC_ROOT
_DEFAULT_PHASE_DEFERRAL = _gtfa_constants._DEFAULT_PHASE_DEFERRAL
_DEFAULT_TICKETS_ROOT = _gtfa_constants._DEFAULT_TICKETS_ROOT


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Generate a ticket file from an AC YAML record.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ac",
        required=True,
        dest="ac_id",
        help="AC id to generate a ticket for.",
    )
    parser.add_argument(
        "--ac-root",
        dest="ac_root",
        default=None,
        help=f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--tickets-root",
        dest="tickets_root",
        default=None,
        help=f"Root directory for written tickets (default: {_DEFAULT_TICKETS_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print the ticket body to stdout without writing.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        dest="verify",
        help=(
            "Print the ticket that WOULD be generated plus a readiness report "
            "checking whether the AC provides enough for a coder to build and a "
            "test-writer to test. Implies --dry-run. Exits non-zero on any FAIL."
        ),
    )
    parser.add_argument(
        "--resolved-destination",
        dest="resolved_destination",
        default=None,
        help=(
            "The ticket's FINAL repo-relative location (e.g. "
            "tickets/00_inbox/epics/EPIC-Foo/01_bar.md), distinct from "
            "--tickets-root which may be a staging root a later step moves "
            "the file out of. Required whenever the phase-deferral "
            "declaration (config/phase_deferral.yaml) is location-dependent "
            "(TKT-600b-1-i); --tickets-root is never accepted as a "
            "substitute. Not required for --dry-run / --verify previews, "
            "which write no file."
        ),
    )
    parser.add_argument(
        "--location-kind",
        dest="location_kind",
        default=None,
        choices=["standalone", "epic_member"],
        help=(
            "DECLARE which kind of location this ticket is being built for, "
            "when you know the kind but not yet the path — /build-ac "
            "generating a loose ticket knows it is 'standalone' without "
            "knowing a folder. Satisfies the same requirement as "
            "--resolved-destination without inventing a path. This is a "
            "declaration, never a default: if neither this nor "
            "--resolved-destination is given and the declaration is "
            "location-dependent, generation still REFUSES (TKT-600b-1-i). "
            "Defaulting to 'standalone' on silence would classify every epic "
            "member as standalone and silently restore the "
            "'pull-request: needed' defect this mechanism removes. Supplying "
            "both is allowed only when they agree; a contradiction refuses."
        ),
    )
    parser.add_argument(
        "--phase-deferral-path",
        dest="phase_deferral_path",
        default=None,
        help=(
            "Path to the location-keyed phase-deferral declaration "
            f"(default: {_DEFAULT_PHASE_DEFERRAL} relative to worktree)."
        ),
    )
    return parser
