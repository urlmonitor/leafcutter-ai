"""
MODULE: build_retired_outputs
GOAL: Remove an installed slash-command / workflow file once the package no
    longer ships the template that produced it -- but only a copy the build can
    prove is its own, unmodified output. Every other copy is kept and named.
BUSINESS CONTEXT: Renaming templates/workflows/leafcutter.md to
    leafcutter-help.md (TICKET-20260930-RenameLeafcutterHubCommand) left the old
    leafcutter.md in .leafcutter/commands/, .claude/commands/ and
    .gemini/workflows/ of every existing install, under a plain build and under
    --clean alike. The old command stayed reachable by name and
    check-output-drift refused every commit (GAP) until someone deleted the
    files by hand; rerunning build.py could not help because the template was
    gone. Nothing removed it: _cleanup_stale_paths handles only whole
    pre-consolidation containers, and clean_stale_artifacts neither covers
    commands/ nor knows the .md command templates.
    TICKET-20260930-RetireRenamedCommandOutputs.
ARCHITECTURE: Decides ownership per ADR-041 -- recomputed attribution, item
    granularity, non-attribution means keep, kept items are reported:
      1. Candidates come from the PREVIOUS install's own record: the
         output_mappings baseline build_phases_local_change snapshots before any
         phase writes. A recorded path is a candidate only when its recorded
         template is a templates/commands/*.md or templates/workflows/*.md
         template AND this run's source-derived phase mappings
         (build_phases._compute_phase_mappings, canonicalised through
         shim_map) no longer produce it, inside a directory those mappings
         still write into -- so a record in any other key spelling can never
         make a still-shipped file look retired. Deriving "still produced"
         from sources, not from this run's existence-gated manifest, keeps
         --dry-run exact. Other families -- notably .claude/workflows/*.js,
         which the phase mappings do not enumerate -- are never candidates.
      2. Each physical copy (the canonical path and its output-root source,
         deduplicated through a symlink shim) gets its own verdict. It is
         removed only when its CRLF-normalised SHA-256 still equals the
         recorded expected_output_hash (package_produced) -- the same hash rule
         check_output_drift.py and the local-change announcement use. A changed
         copy (adopter_owned), or one that is a symlink, not a regular file, or
         unreadable (unattributable), is kept and named.
      3. A file the build never recorded is not a candidate at all: it is
         neither touched nor named (BP-1500b-4's negative side).
    Called from build_main_helpers._run_shim_and_hook_install BEFORE shim
    install, so a copy-strategy shim cannot merge a retired file back into the
    canonical directory, and before the --no-shims early return.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from build_colors import (
    dry_run as _dry_run_msg,
    heading as _heading,
    info as _info,
    success as _success,
    warn as _warn,
)
from build_helpers import _canonicalize_output_path, shim_map
from build_phases_local_change import _hash_for_local_change_check, get_previous_output_mappings

_log = logging.getLogger(__name__)

#: Template directories whose installed outputs this step may retire -- the
#: prose slash-command templates, whose current output set
#: build_phases._compute_phase_mappings() recomputes from source.
RETIRABLE_TEMPLATE_DIRS: tuple[str, ...] = ("commands", "workflows")

PACKAGE_PRODUCED = "package_produced"
ADOPTER_OWNED = "adopter_owned"
UNATTRIBUTABLE = "unattributable"
ABSENT = "absent"


@dataclass
class RetirementReport:
    """What one run of the step removed and what it kept.

    Attributes:
        removed: Target-relative paths removed (or, under dry-run, that would be).
        kept: ``(path, verdict, reason)`` for every existing copy of a retired
            output that was not provably the package's own unmodified file.
    """

    removed: list[str] = field(default_factory=list)
    kept: list[tuple[str, str, str]] = field(default_factory=list)


def _recorded_template_is_retirable(template: object) -> bool:
    """Whether a recorded ``template`` names a templates/commands|workflows/*.md file.

    Accepts every recorded spelling (``<package>/templates/...``, a bare
    ``templates/...`` for the self-host layout, or backslash separators).
    """
    if not isinstance(template, str):
        return False
    parts = PurePosixPath(template.replace("\\", "/")).parts
    if len(parts) < 3 or not parts[-1].endswith(".md"):
        return False
    return parts[-3] == "templates" and parts[-2] in RETIRABLE_TEMPLATE_DIRS


def _is_safe_relative_key(key: str) -> bool:
    """Reject a malformed record key that could point outside the target tree."""
    path = PurePosixPath(key.replace("\\", "/"))
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and ":" not in key


def find_retired_outputs(
    previous_mappings: dict[str, Any], current_keys: set[str]
) -> list[tuple[str, str]]:
    """Return ``(key, expected_hash)`` for every recorded command output no longer produced.

    Args:
        previous_mappings: The previous install's ``output_mappings`` record.
        current_keys: Canonical keys this run's current sources still produce.

    Returns:
        Sorted candidates: recorded, from a retirable template family, carrying
        a recorded hash, absent from ``current_keys``, and inside a directory
        ``current_keys`` still writes into. The last condition means a record
        written in some other key spelling (an older manifest format, a
        pre-shim path, backslash separators) can never make a still-shipped
        file look retired: it simply is not a candidate.
    """
    current_dirs = {PurePosixPath(key).parent.as_posix() for key in current_keys}
    retired: list[tuple[str, str]] = []
    for key in sorted(previous_mappings):
        entry = previous_mappings[key]
        if key in current_keys or not isinstance(entry, dict):
            continue
        expected = entry.get("expected_output_hash")
        if not expected or not _is_safe_relative_key(key):
            continue
        if PurePosixPath(key).parent.as_posix() not in current_dirs:
            continue
        if _recorded_template_is_retirable(entry.get("template")):
            retired.append((key, expected))
    return retired


def classify_installed_copy(path: Path, expected_hash: str) -> tuple[str, str]:
    """ADR-041 verdict for one installed copy of a retired output.

    Args:
        path: The installed copy to judge.
        expected_hash: The hash the previous install recorded for it.

    Returns:
        ``(verdict, reason)``; ``reason`` is empty for ``package_produced``
        and ``absent``.
    """
    if path.is_symlink():
        return UNATTRIBUTABLE, "it is a symlink, and the build never installs a single command file as one"
    if not path.exists():
        return ABSENT, ""
    if not path.is_file():
        return UNATTRIBUTABLE, "it is not a regular file"
    current = _hash_for_local_change_check(path)
    if current is None:
        return UNATTRIBUTABLE, "it could not be read"
    if current != expected_hash:
        return ADOPTER_OWNED, "its content changed after the package installed it"
    return PACKAGE_PRODUCED, ""


def _output_root_copy(key: str, output_root: Path) -> Path | None:
    """Map a canonical key back to its output-root source via ``shim_map``.

    The inverse of ``build_helpers._canonicalize_output_path``: the longest
    canonical prefix wins, e.g. ``.gemini/workflows/x.md`` ->
    ``<output_root>/gemini/workflows/x.md``.
    """
    parts = PurePosixPath(key).parts
    canonical_to_output = dict(shim_map)
    for length in range(len(parts) - 1, 0, -1):
        output_rel = canonical_to_output.get("/".join(parts[:length]))
        if output_rel is not None:
            return output_root / output_rel / Path(*parts[length:])
    return None


def _installed_copies(key: str, target_root: Path, output_root: Path) -> list[Path]:
    """Every distinct physical copy of one output: canonical first, then its source."""
    candidates = [target_root / Path(*PurePosixPath(key).parts)]
    source = _output_root_copy(key, output_root)
    if source is not None:
        candidates.append(source)
    copies: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        identity = path.resolve()
        if identity not in seen:
            seen.add(identity)
            copies.append(path)
    return copies


def _shown(path: Path, target_root: Path) -> str:
    try:
        return path.relative_to(target_root).as_posix()
    except ValueError:
        return str(path)


def retire_outputs(
    target_root: Path,
    output_root: Path,
    previous_mappings: dict[str, Any],
    current_keys: set[str],
    dry_run: bool,
) -> RetirementReport:
    """Remove every provably package-produced copy of a retired command output.

    Args:
        target_root: The adopter's project root.
        output_root: The consolidated output root (``.leafcutter/``).
        previous_mappings: The previous install's ``output_mappings`` record.
        current_keys: Canonical keys this run's current sources still produce.
        dry_run: When True, report what would be removed and remove nothing.

    Returns:
        The removed and kept copies.

    Raises:
        OSError: When a copy judged removable cannot be removed. It is logged
            and re-raised rather than reported as removed.
    """
    report = RetirementReport()
    for key, expected in find_retired_outputs(previous_mappings, current_keys):
        for path in _installed_copies(key, target_root, output_root):
            verdict, reason = classify_installed_copy(path, expected)
            if verdict == ABSENT:
                continue
            if verdict != PACKAGE_PRODUCED:
                report.kept.append((_shown(path, target_root), verdict, reason))
                continue
            if not dry_run:
                try:
                    path.unlink()
                except OSError as exc:
                    _log.error("could not remove retired output %s: %s", path, exc)
                    raise
            report.removed.append(_shown(path, target_root))
    return report


def current_command_output_keys(target_root: Path, output_root: Path, config: dict) -> set[str]:
    """Canonical keys the current sources produce for the command/workflow family.

    Recomputed from the templates via ``build_phases._compute_phase_mappings``
    (the same enumeration the deploy-collision guard uses), never from the
    existence-gated manifest, so the answer does not depend on whether this run
    has written anything yet.
    """
    import build_phases as _bp

    keys: set[str] = set()
    for _source, target in _bp._compute_phase_mappings(output_root, config):
        canonical = _canonicalize_output_path(target, output_root, target_root)
        if canonical is not None:
            keys.add(canonical.relative_to(target_root).as_posix())
    return keys


def run_retired_output_sweep(
    target_root: Path,
    output_root: Path,
    config: dict,
    dry_run: bool,
    previous_mappings: dict[str, Any] | None = None,
) -> RetirementReport:
    """The build step: retire, then report every removal and every kept copy.

    Args:
        target_root: The adopter's project root.
        output_root: The consolidated output root.
        config: The merged build config (selects the active platforms).
        dry_run: When True, name what would be removed and remove nothing.
        previous_mappings: The previous install's record; defaults to the
            baseline ``set_local_change_baseline`` captured for this run.

    Returns:
        The step's report.
    """
    if previous_mappings is None:
        previous_mappings = get_previous_output_mappings()
    current_keys = current_command_output_keys(target_root, output_root, config)
    report = retire_outputs(target_root, output_root, previous_mappings, current_keys, dry_run)

    print()
    _heading("Retired command outputs")
    if not previous_mappings:
        _info("(no previous install record to compare against -- nothing examined)")
    elif not report.removed and not report.kept:
        _info("(no command or workflow template retired since the last install)")
    for shown in report.removed:
        if dry_run:
            _dry_run_msg(f"would remove retired: {shown}")
        else:
            _success(f"removed retired: {shown}")
    for shown, verdict, reason in report.kept:
        _warn(
            f"kept retired {shown} ({verdict}): {reason}. The package no longer "
            "ships it; delete it yourself if you no longer need it."
        )
    return report


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-30 [BrainCandy/TICKET-20260930-RetireRenamedCommandOutputs]:
#   Created. Retires installed slash-command/workflow files whose template
#   was renamed or deleted, attributing each copy from the previous install's
#   own output_mappings record plus a content-hash match (ADR-041), and
#   keeping and naming anything it cannot attribute. Scoped to the
#   templates/commands|workflows family on purpose: the approved BP-1500b
#   orphan-sweep family covers every family and is not claimed here.
#   (#TICKET-20260930-RetireRenamedCommandOutputs)
# ===========================================================================
