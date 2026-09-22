#!/usr/bin/env python3
"""
MODULE: _gtfa_cli
GOAL: Drive one ticket generation end to end: resolve the roots, find the AC,
    and either print a preview (``--dry-run`` / ``--verify``) or write the
    ticket file and its ``implemented_by`` back-reference.
BUSINESS CONTEXT: The preview path and the write path must agree on their
    INPUTS, which is why both pass the deferral arguments through. A preview
    that omitted them would report ``pull-request: needed`` for a ticket that
    would actually be written with ``not_needed`` — misstating the very field
    the deferral mechanism exists to get right, in the direction of the
    original defect, in the report a person reads when deciding whether a
    ticket is sound.
ARCHITECTURE: Only the write path resolves the phase-deferral declaration
    strictly enough to REFUSE, and it does so even when ``--phase-deferral-path``
    is omitted — that resolves to the real default declaration rather than
    skipping the check. The preview paths write no file, so they never refuse.

    Failure handling is split by consequence: a missing AC, an existing ticket,
    or an unwritable ticket path exits 1; a failed ``implemented_by`` back-write
    is non-fatal and only WARNs, because the ticket itself is already on disk
    and a hard exit there would make a successful generation look like a failed
    one.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]


def _sib(name: str):
    """Import a ``_gtfa_*`` sibling under this module's own import layout."""
    return importlib.import_module(f"{_PKG}.{name}" if _PKG else name)


_gtfa_seams = _sib("_gtfa_seams")
_gtfa_constants = _sib("_gtfa_constants")
_gtfa_agents_map = _sib("_gtfa_agents_map")
_gtfa_body = _sib("_gtfa_body")
_gtfa_cli_parser = _sib("_gtfa_cli_parser")
_gtfa_files_touched = _sib("_gtfa_files_touched")
_gtfa_frontmatter = _sib("_gtfa_frontmatter")
_gtfa_implemented_by = _sib("_gtfa_implemented_by")
_gtfa_paths = _sib("_gtfa_paths")
_gtfa_phases = _sib("_gtfa_phases")
_gtfa_report = _sib("_gtfa_report")
_gtfa_store = _sib("_gtfa_store")
_gtfa_tests_section = _sib("_gtfa_tests_section")

logger = logging.getLogger(_gtfa_seams.logger_name())

# ``AcRecord`` is bound at RUNTIME by the ``else`` branch, off the sibling
# module object resolved above through importlib under a prefix COMPUTED from
# ``__name__`` -- see the "Sibling wiring" note in generate_ticket_from_ac.py
# for why a literal relative import there would break one of the two supported
# layouts. A computed name is opaque to a type checker, so that rebind reads as
# a VARIABLE and mypy rejects every annotation using it ("Variable ... is not
# valid as a type"). The TYPE_CHECKING branch declares the alias statically and
# is never executed, so the runtime binding is unchanged.
if TYPE_CHECKING:  # pragma: no cover - a static declaration, never executed
    from ._gtfa_constants import AcRecord
else:
    AcRecord = _gtfa_constants.AcRecord

_DEFAULT_AC_ROOT = _gtfa_constants._DEFAULT_AC_ROOT
_DEFAULT_PHASE_DEFERRAL = _gtfa_constants._DEFAULT_PHASE_DEFERRAL
_DEFAULT_TICKETS_ROOT = _gtfa_constants._DEFAULT_TICKETS_ROOT


#: TKT-600b-5 refusal for an AC whose assigned_agent is null. The builder
#: raises without the AC id — it never sees one — so naming the offending
#: record is this layer's job. Both generation paths render this same string,
#: so the preview and the write path refuse on identical terms.
_UNASSIGNED_WORK_AGENT_REFUSAL = "ERROR: generation refused — AC '{ac_id}': {exc}"


def _build_agents_map_for_write_path(
    assigned_agent: str,
    *,
    change_targets: list[str] | None,
    risk_surface: str | None,
    files_touched: list[str],
    declares_side_effect: bool,
    has_authored_test_spec: bool,
    resolved_destination: str | None,
    phase_deferral_path: str | None,
    worktree: Path,
    location_kind: str | None = None,
) -> "tuple[dict[str, str] | None, str | None]":
    """Build the agents map for main()'s ticket-writing path, or a refusal.

    TKT-600b-1-i: unlike the --dry-run/--verify preview path (which never
    passes a destination or declaration and so never refuses), the path that
    actually persists a ticket always resolves the phase-deferral
    declaration — even when ``--phase-deferral-path`` is omitted, which
    resolves to the real default declaration rather than skipping the check.

    Args:
        assigned_agent: The agent name from the AC's assigned_agent field.
        change_targets: Normalised change_target list from the AC.
        risk_surface: risk_surface field from the AC.
        files_touched: Computed files_touched list.
        declares_side_effect: declares_side_effect field from the AC.
        has_authored_test_spec: Whether the AC carries an authored test_spec.
        resolved_destination: ``--resolved-destination`` CLI value, or None.
        phase_deferral_path: ``--phase-deferral-path`` CLI value, or None.
        worktree: Resolved worktree root, used to default phase_deferral_path.
        location_kind: ``--location-kind`` CLI value, or None.

    Returns:
        ``(agents_map, None)`` on success, or ``(None, error_message)`` when
        generation must refuse — *error_message* is ready to print to stderr.
    """
    resolved_phase_deferral_path = (
        Path(phase_deferral_path) if phase_deferral_path else worktree / _DEFAULT_PHASE_DEFERRAL
    )
    try:
        agents = _gtfa_agents_map._build_agents_map(
            assigned_agent,
            change_targets=change_targets,
            risk_surface=risk_surface,
            files_touched=files_touched,
            declares_side_effect=declares_side_effect,
            has_authored_test_spec=has_authored_test_spec,
            resolved_destination=resolved_destination,
            phase_deferral_path=resolved_phase_deferral_path,
            location_kind=location_kind,
        )
    except _gtfa_phases.PhaseDeferralDeclarationError as exc:
        return None, (
            f"ERROR: generation refused — phase deferral declaration could not "
            f"be loaded: {exc}"
        )
    except _gtfa_phases.UnresolvedDestinationError as exc:
        return None, f"ERROR: generation refused — {exc}"
    return agents, None


def _ac_inputs(ac: AcRecord) -> tuple[list[str], str, "list[str] | None", "str | None", bool]:
    """Extract the five AC-derived inputs both generation paths need.

    Args:
        ac: Parsed AC record.

    Returns:
        ``(files_touched, assigned_agent, change_targets, risk_surface,
        declares_side_effect)``.
    """
    return (
        _gtfa_files_touched._build_files_touched(ac),
        ac.get("assigned_agent", "python-coder"),
        _gtfa_frontmatter._normalize_change_target(ac),
        ac.get("risk_surface") or None,
        bool(ac.get("declares_side_effect", False)),
    )


def _run_preview(
    args: argparse.Namespace,
    ac: AcRecord,
    ac_id: str,
    ac_root: Path,
    tickets_root: Path,
    ac_store_path: str,
) -> int:
    """Build the ticket in memory, print it, and for --verify append a report.

    Neither path writes a file. The deferral inputs are passed through exactly
    as the write path does: a preview that omits them reports
    ``pull-request: needed`` for a ticket that would be written with
    ``not_needed`` — a preview that misstates the very field this mechanism
    exists to get right, and misstates it in the direction of the original
    defect. --verify's readiness report is read by people deciding whether a
    ticket is sound, so the two paths must agree on their inputs.

    Args:
        args: Parsed CLI arguments.
        ac: Parsed AC record.
        ac_id: The AC id.
        ac_root: Root directory of the AC store.
        tickets_root: Root directory for written tickets.
        ac_store_path: Repo-root-relative path to the source AC YAML.

    Returns:
        Exit code: 0, or 2 when --verify recorded a FAIL.
    """
    (
        files_touched,
        assigned_agent,
        change_targets,
        risk_surface,
        declares_side_effect,
    ) = _ac_inputs(ac)

    try:
        agents = _gtfa_agents_map._build_agents_map(
            assigned_agent,
            change_targets=change_targets,
            risk_surface=risk_surface,
            files_touched=files_touched,
            declares_side_effect=declares_side_effect,
            has_authored_test_spec=_gtfa_tests_section._has_authored_test_spec(ac),
            resolved_destination=args.resolved_destination,
            phase_deferral_path=args.phase_deferral_path,
            location_kind=args.location_kind,
        )
    except _gtfa_agents_map.UnassignedWorkAgentError as exc:
        # The preview refuses on exactly the terms the write path refuses on.
        print(_UNASSIGNED_WORK_AGENT_REFUSAL.format(ac_id=ac_id, exc=exc), file=sys.stderr)
        return 1
    frontmatter = _gtfa_frontmatter._build_frontmatter(
        ac, ac_id, files_touched, agents, ac_store_path, tickets_root=tickets_root
    )
    body = _gtfa_body._build_ticket_body(ac, ac_id, agents_map=agents, ac_root=ac_root)
    print(frontmatter)
    print()
    print(body)
    if args.verify:
        report, has_fail = _gtfa_report._build_verification_report(
            ac, ac_id, agents, body, files_touched
        )
        print()
        print(report)
        return 2 if has_fail else 0
    return 0


def _write_ticket(
    args: argparse.Namespace,
    ac: AcRecord,
    ac_path: Path,
    ac_id: str,
    ac_root: Path,
    tickets_root: Path,
    ac_store_path: str,
    worktree: Path,
) -> int:
    """Write the generated ticket and its implemented_by back-reference.

    Args:
        args: Parsed CLI arguments.
        ac: Parsed AC record.
        ac_path: Path to the source AC YAML.
        ac_id: The AC id.
        ac_root: Root directory of the AC store.
        tickets_root: Root directory for written tickets.
        ac_store_path: Repo-root-relative path to the source AC YAML.
        worktree: Resolved worktree root.

    Returns:
        Exit code: 0 on success, 1 on refusal or write failure.
    """
    (
        files_touched,
        assigned_agent,
        change_targets,
        risk_surface,
        declares_side_effect,
    ) = _ac_inputs(ac)

    try:
        built_agents, refusal = _build_agents_map_for_write_path(
            assigned_agent,
            change_targets=change_targets,
            risk_surface=risk_surface,
            files_touched=files_touched,
            declares_side_effect=declares_side_effect,
            has_authored_test_spec=_gtfa_tests_section._has_authored_test_spec(ac),
            resolved_destination=args.resolved_destination,
            phase_deferral_path=args.phase_deferral_path,
            location_kind=args.location_kind,
            worktree=worktree,
        )
    except _gtfa_agents_map.UnassignedWorkAgentError as exc:
        # Refuse BEFORE any file is written: no ticket, and no implemented_by
        # back-reference into the AC that provoked the refusal.
        print(_UNASSIGNED_WORK_AGENT_REFUSAL.format(ac_id=ac_id, exc=exc), file=sys.stderr)
        return 1
    if refusal is not None:
        print(refusal, file=sys.stderr)
        return 1
    if built_agents is None:
        # The contract is (map, None) or (None, refusal); (None, None) is a bug
        # in the builder, not a caller error. Naming it here costs one branch and
        # turns an obscure TypeError several frames downstream into a stated
        # cause.
        print(
            "ERROR: internal: the agents-map builder returned neither a map nor "
            "a refusal. This is a defect in _build_agents_map_for_write_path.",
            file=sys.stderr,
        )
        return 1
    # Bound to a distinct name above, then narrowed here: the dry-run branch
    # earlier in this function already binds `agents` to a plain dict, so
    # assigning an Optional straight onto that name is a type error even though
    # the two branches never both run.
    agents = built_agents
    frontmatter = _gtfa_frontmatter._build_frontmatter(
        ac, ac_id, files_touched, agents, ac_store_path, tickets_root=tickets_root
    )
    body = _gtfa_body._build_ticket_body(ac, ac_id, agents_map=agents, ac_root=ac_root)
    ticket_content = frontmatter + "\n\n" + body

    # Write ticket file
    filename = _gtfa_paths._ticket_filename(ac_id)
    ticket_path = tickets_root / filename
    try:
        ticket_path.write_text(ticket_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: could not write ticket {ticket_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Written: {ticket_path}")

    # Write implemented_by back-reference into source AC
    relative_ticket_path = str(ticket_path.relative_to(worktree)) if ticket_path.is_relative_to(worktree) else str(ticket_path)
    try:
        _gtfa_implemented_by._write_implemented_by(
            ac_path, relative_ticket_path, ac_id, worktree=worktree
        )
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"WARNING: ticket written but could not update implemented_by in {ac_path}: {exc}",
            file=sys.stderr,
        )
        # Non-fatal: ticket is written; only the back-reference failed.

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for generate_ticket_from_ac.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = _gtfa_cli_parser._build_parser()
    args = parser.parse_args(argv)
    ac_id: str = args.ac_id

    # Resolve roots
    try:
        worktree = _gtfa_seams.find_worktree_root(Path(__file__))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ac_root = Path(args.ac_root) if args.ac_root else worktree / _DEFAULT_AC_ROOT
    tickets_root = Path(args.tickets_root) if args.tickets_root else worktree / _DEFAULT_TICKETS_ROOT

    if not ac_root.exists():
        print(f"ERROR: AC root not found: {ac_root}", file=sys.stderr)
        return 1

    # Find the AC
    result = _gtfa_store._find_ac_by_id(ac_root, ac_id)
    if result is None:
        print(f"ERROR: AC id '{ac_id}' not found under {ac_root}", file=sys.stderr)
        return 1
    ac_path, ac = result

    # Compute repo-root-relative path to the AC file for ac_traceability.
    # ac_path is guaranteed to be under ac_root (found by _find_ac_by_id),
    # so relative_to(ac_root.parent.parent) always succeeds.
    #
    # as_posix(), not str(): this value is an identifier written into ticket
    # frontmatter and read back by ac-fulfillment-gate, which runs in CI on
    # Linux. str() renders with os.sep, so a ticket generated on Windows records
    # a path with backslashes that resolves nowhere on the machine that has to
    # read it. The same defect shipped in generate_product_truth.py and made the
    # product-truth validator unpassable on Windows; _canonicalise_ticket_path
    # in this very file already guards against it with .replace(chr(92), "/").
    ac_store_path = ac_path.relative_to(ac_root.parent.parent).as_posix()

    # Dry-run / verify: build the ticket in memory, print it, and (for --verify)
    # append a readiness report. Neither path writes a file.
    if args.dry_run or args.verify:
        return _run_preview(args, ac, ac_id, ac_root, tickets_root, ac_store_path)

    # Idempotency guard: check for existing ticket
    tickets_root.mkdir(parents=True, exist_ok=True)
    existing = _gtfa_store._find_existing_ticket(tickets_root, ac_id)
    if existing is not None:
        print(
            f"ERROR: ticket for AC '{ac_id}' already exists: {existing}",
            file=sys.stderr,
        )
        return 1

    return _write_ticket(
        args, ac, ac_path, ac_id, ac_root, tickets_root, ac_store_path, worktree
    )
