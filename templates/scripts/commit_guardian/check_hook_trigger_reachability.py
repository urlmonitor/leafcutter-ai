"""
MODULE: check_hook_trigger_reachability
GOAL: Pre-commit hook — the "registry's own reachability check" required by
    BP-100k-4. For every gate registered in ``hooks_manifest.hooks`` of
    commit_guardian.json, determines whether at least one path this
    repository actually tracks can ever activate it, and whether a
    whole-tree gate (``always_run: true``, never consulting the staged
    file list) has been given a path-based ``files`` filter it never
    consults. A gate that can never fire, or whose stated activation
    mechanism contradicts its own execution shape, is reported and blocks
    the commit.
BUSINESS CONTEXT: Two gates in this registry — check-build-drift and
    check-output-drift — were registered with ``files`` triggers that could
    never match anything this repository is able to stage (one named a
    consumer-install-only location, the other named locations that are
    either gitignored or absent), so both had never fired despite guarding
    roughly 3,000 lines of drift-gate hardening. Correcting those two
    triggers alone leaves the defect CLASS intact for the next hook added
    to the registry; this check makes the class itself a reported, blocking
    condition. See
    docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-4.yaml
    and BP-100k-4-i.yaml (the paired negative case: no false alarm on a
    gate that legitimately fires, and fail-closed — never a silent pass —
    when reachability cannot be determined at all).
ARCHITECTURE: This hook itself inspects the WHOLE registry, never a staged
    file list, so it is registered in hooks_manifest.hooks with
    ``always_run: true`` and ``pass_filenames: false`` — it is itself an
    instance of the whole-tree-gate shape this AC exists to police.

    Registry resolution (mirrors the HOOK_TEST_CONFIG convention already
    established by check_build_drift.py / check_output_drift.py, and the
    two-tier fallback established by check_hook_parity.py's
    ``_load_config``):
      1. ``HOOK_TEST_CONFIG`` env var, if set: read that JSON file directly
         (must contain a top-level ``hooks_manifest`` key shaped like
         ``{"hooks": [...]}``). Used INSTEAD of the real registry — never
         falls through to it.
      2. ``<cwd>/scripts/commit_guardian/commit_guardian.json`` (the
         deployed runtime copy).
      3. ``commit_guardian.json`` colocated with this script (the template
         source tree copy).
      4. If none of the above can be read and parsed as JSON: INDETERMINATE
         (see below) — never a silent pass.

    Tracked-path acquisition: ``git ls-files`` run with this process's cwd
    as the working directory. A non-zero exit (including "not a git
    repository") or a missing ``git`` executable is INDETERMINATE.

    FAIL-CLOSED CONTRACT (BP-100k-4-i): an inability to read the registry
    or to obtain the tracked-path set is reported via an
    ``INDETERMINATE: reason=<text>`` line and a non-zero (2) exit — it must
    never be reported as a clean, zero-unreachable pass. Conversely, a
    whole-tree gate (``always_run: true``) that carries no ``files`` key is
    the legitimate shape and must never be flagged merely for lacking a
    path filter.

    Per-gate rule (an ``enabled: false`` entry is skipped — intentionally
    off, not a reachability question). This is a THREE-WAY verdict —
    reachable / declared-exempt-with-ground / unreachable — reusing the
    exemption vocabulary BP-100k-3 established for the drift gates
    (``_drift_exemptions.py``: ``EXEMPT <key> ground=<text>``, with a
    groundless entry REJECTED and falling through to the un-exempted
    verdict) rather than inventing a third one:
      - ``always_run: true`` AND a ``files`` key present -> UNREACHABLE
        (whole-tree gate carrying a filter it never consults — this shape
        is never exemptable, it is always a real authoring mistake).
      - ``always_run: true``, no ``files`` -> reachable.
      - ``files`` present (``always_run`` not true): compiled as a regex
        and ``re.search`` against every ``git ls-files`` path. One or more
        matches -> reachable. Zero matches -> check the
        ``hook_trigger_reachability_exemption_registry`` (a top-level key
        of the SAME loaded registry, entries shaped ``{"id": <gate-id>,
        "ground": <text>}``) for this gate's id. A valid (non-blank
        ``ground``) entry -> EXEMPT (reported, not counted as unreachable,
        never blocks). No entry, or a groundless one (rejected with
        ``REJECTED EXEMPTION ENTRY: <id> reason=no ground stated``) ->
        UNREACHABLE.
      - neither key present -> reachable (pre-commit's own default: an
        absent ``files`` filter matches everything).

    "Zero matches in the CURRENT repository" is not always "cannot ever
    match" — a correctly-authored trigger for a file family this specific
    checkout happens not to have (e.g. ``check-infra-docs``' docker-compose
    pattern in a repo with no Docker infrastructure) is context-dependent,
    not structurally dead, and must not be forced into ``always_run`` or a
    rewritten pattern merely to satisfy this check (that would silently
    convert a conditional gate into an unconditional one for every consumer
    install). The exemption registry is the correct instrument for that
    case, exactly as BP-100k-3 established for the drift gates.

    CONSUMER BLAST-RADIUS NOTE (BP-100k-4-i): this registry ships to every
    consumer install verbatim. A gate whose ``files`` target lives inside
    the package's own vendored subtree (e.g. ``config/paths.json``,
    ``templates/docs/architecture/``) may have zero tracked matches in a
    consumer's outer repository even though the pattern is correct for the
    self-hosted package checkout — the vendored package directory can be
    gitignored or a submodule there. Such gates are declared exempt (see
    ``check-paths-integrity`` / ``check-architecture-scaffolds`` in
    commit_guardian.json) rather than forced to ``always_run`` or having
    the check's own verdict weakened, so this gate can never become a
    universal commit-blocker across every consumer project.

    Exit status: 0 when unreachable == 0 and determinate; 1 when
    unreachable > 0; 2 when indeterminate.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_GATE_NAME = "check-hook-trigger-reachability"
_HOOK_FILE = Path(__file__).resolve()
_SUBPROCESS_TIMEOUT_SECONDS = 20


# ---------------------------------------------------------------------------
# Registry resolution
# ---------------------------------------------------------------------------


def _read_json_file(path: Path) -> dict | None:
    """Read and parse one JSON file, returning None on any I/O or parse error.

    Args:
        path: Absolute path to the candidate JSON file.

    Returns:
        The parsed JSON value, or None if the file cannot be read or is not
        valid JSON. Logs a WARNING in either failure case.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as exc:
        print(f"{_GATE_NAME}: WARNING - could not read {path}: {exc}", file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print(f"{_GATE_NAME}: WARNING - {path} is not valid JSON: {exc}", file=sys.stderr)
        return None


def _load_registry() -> dict | None:
    """Resolve and load the hooks_manifest registry per the BP-100k-4 order.

    Returns:
        The parsed registry dict (expected to contain a "hooks_manifest"
        key), or None if no candidate could be read and parsed as JSON.
        When HOOK_TEST_CONFIG is set, it is used INSTEAD of the real
        registry and no fallback candidate is tried.
    """
    test_config_path = os.environ.get("HOOK_TEST_CONFIG")
    if test_config_path:
        return _read_json_file(Path(test_config_path))

    candidates = [
        Path.cwd() / "scripts" / "commit_guardian" / "commit_guardian.json",
        _HOOK_FILE.parent / "commit_guardian.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        registry = _read_json_file(candidate)
        if registry is not None:
            return registry
    return None


# ---------------------------------------------------------------------------
# Tracked-path acquisition
# ---------------------------------------------------------------------------


def _get_tracked_paths(cwd: Path) -> list[str] | None:
    """Return the repository-tracked paths via ``git ls-files``.

    Args:
        cwd: Working directory to run ``git ls-files`` in.

    Returns:
        The tracked, forward-slash, repo-root-relative paths exactly as
        ``git ls-files`` emits them, or None if the command could not be
        run at all or exited non-zero (e.g. not a git repository).
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{_GATE_NAME}: WARNING - could not run 'git ls-files': {exc}", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(
            f"{_GATE_NAME}: WARNING - 'git ls-files' exited "
            f"{result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return None

    return [line for line in result.stdout.splitlines() if line]


# ---------------------------------------------------------------------------
# Exemption registry (BP-100k-4: reuses the BP-100k-3 vocabulary)
# ---------------------------------------------------------------------------


def _validate_exemptions(entries: object) -> dict[str, str]:
    """Split raw hook_trigger_reachability_exemption_registry entries.

    Mirrors ``_drift_exemptions.validate_exemption_registry`` (BP-100k-3):
    an entry whose ``ground`` is missing, empty, or whitespace-only is
    REJECTED rather than silently honoured, so its gate falls through to
    the un-exempted UNREACHABLE verdict.

    Args:
        entries: The raw value of the registry's
            ``hook_trigger_reachability_exemption_registry`` key (expected
            to be a list of ``{"id": <gate-id>, "ground": <text>}`` dicts;
            any other shape yields an empty exemption map).

    Returns:
        Mapping of gate id to non-blank ground text, for valid entries only.
    """
    valid: dict[str, str] = {}
    if not isinstance(entries, list):
        return valid
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        gate_id = entry.get("id")
        if not gate_id:
            continue
        ground = entry.get("ground", "")
        if isinstance(ground, str) and ground.strip():
            valid[gate_id] = ground.strip()
        else:
            print(
                f"REJECTED EXEMPTION ENTRY: {gate_id} reason=no ground stated",
                file=sys.stderr,
            )
    return valid


# ---------------------------------------------------------------------------
# Per-gate reachability rule
# ---------------------------------------------------------------------------


def _evaluate_gate(
    entry: dict, tracked_paths: list[str], exemptions: dict[str, str]
) -> tuple[str, str | None]:
    """Evaluate one hooks_manifest entry's reachability.

    Args:
        entry: One entry from ``hooks_manifest.hooks``.
        tracked_paths: The repository's tracked paths (``git ls-files``
            output).
        exemptions: Valid gate-id -> ground map from
            ``_validate_exemptions``.

    Returns:
        A ``(verdict, detail)`` pair. ``verdict`` is one of "reachable"
        (detail is None), "exempt" (detail is the ground text), or
        "unreachable" (detail is the free-text reason).
    """
    always_run = bool(entry.get("always_run"))
    files_pattern = entry.get("files")
    gate_id = entry.get("id", "<unknown>")

    if always_run and files_pattern:
        return (
            "unreachable",
            "whole-tree gate (always_run: true, never consults the staged "
            f"file list) also carries a files filter it never consults: "
            f"{files_pattern!r}",
        )
    if always_run:
        return ("reachable", None)
    if not files_pattern:
        return ("reachable", None)

    try:
        compiled = re.compile(files_pattern)
    except re.error as exc:
        return ("unreachable", f"files pattern {files_pattern!r} is not a valid regex: {exc}")

    if any(compiled.search(p) for p in tracked_paths):
        return ("reachable", None)

    ground = exemptions.get(gate_id)
    if ground:
        return ("exempt", ground)
    return (
        "unreachable",
        f"files pattern {files_pattern!r} matches none of the "
        f"{len(tracked_paths)} path(s) this repository tracks",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-commit hook.

    Returns:
        0 when every non-skipped gate is reachable (determinate run); 1
        when one or more gates are unreachable; 2 when reachability could
        not be determined at all (registry unreadable or tracked-path set
        unobtainable) — never a silent pass in that case (BP-100k-4-i).
    """
    registry = _load_registry()
    if registry is None:
        print(
            "INDETERMINATE: reason=could not load a hooks_manifest registry "
            "(HOOK_TEST_CONFIG / deployed / source commit_guardian.json were "
            "all unreadable or not valid JSON)",
            file=sys.stderr,
        )
        return 2

    hooks_manifest = registry.get("hooks_manifest")
    hooks = hooks_manifest.get("hooks") if isinstance(hooks_manifest, dict) else None
    if not isinstance(hooks, list):
        print(
            "INDETERMINATE: reason=registry is missing a valid "
            "hooks_manifest.hooks list",
            file=sys.stderr,
        )
        return 2

    tracked_paths = _get_tracked_paths(Path.cwd())
    if tracked_paths is None:
        print(
            "INDETERMINATE: reason=could not obtain the repository's "
            "tracked-path set via 'git ls-files'",
            file=sys.stderr,
        )
        return 2

    exemptions = _validate_exemptions(
        registry.get("hook_trigger_reachability_exemption_registry", [])
    )

    total = 0
    unreachable = 0
    exempt = 0
    for entry in hooks:
        if not isinstance(entry, dict):
            continue
        if entry.get("enabled") is False:
            continue
        total += 1
        gate_id = entry.get("id", "<unknown>")
        verdict, detail = _evaluate_gate(entry, tracked_paths, exemptions)
        if verdict == "unreachable":
            unreachable += 1
            print(f"UNREACHABLE: {gate_id} reason={detail}", file=sys.stderr)
        elif verdict == "exempt":
            exempt += 1
            print(f"EXEMPT: {gate_id} ground={detail}", file=sys.stderr)

    print(
        f"{_GATE_NAME}: RESULT total={total} unreachable={unreachable} exempt={exempt}",
        file=sys.stderr,
    )

    return 1 if unreachable else 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation]:
#   BP-100k-4 / BP-100k-4-i: created module. Registry-wide reachability
#   verdict for every hooks_manifest entry: a files-triggered gate whose
#   pattern matches no tracked path, or a whole-tree (always_run) gate that
#   also carries a files filter, is reported UNREACHABLE and the run exits
#   1. An unreadable registry or an unobtainable tracked-path set is
#   INDETERMINATE (exit 2) — never a silent pass. Paired with fixing
#   check-build-drift's and check-output-drift's dead files triggers to
#   always_run: true in commit_guardian.json.
# - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation, r2]:
#   Coordinator review found two defects in r1. (1) check-infra-docs' files
#   trigger was CORRECT (docker-compose/Dockerfile patterns) but matched
#   zero tracked paths only because this package repo has no Docker
#   infrastructure — "no match today" != "cannot ever match", and deleting
#   the filter would make the gate unconditional in every consumer install
#   that DOES have such files. Restored the filter and added the
#   three-way reachable/exempt/unreachable vocabulary (reusing BP-100k-3's
#   EXEMPT-with-ground / REJECTED-groundless shape from
#   _drift_exemptions.py) via a new
#   hook_trigger_reachability_exemption_registry key; check-infra-docs is
#   now declared exempt with a stated ground instead of unconditional.
#   (2) Consumer blast-radius check: check-paths-integrity and
#   check-architecture-scaffolds target the package's OWN internal files
#   (config/paths.json, templates/docs/architecture/); in a consumer
#   install where the vendored package directory is untracked/gitignored/
#   a submodule, these have zero tracked matches and would otherwise block
#   EVERY consumer commit forever. Verified via a synthetic consumer-layout
#   fixture (untracked package subtree) against the deployed hook. Also
#   corrected the consumer-layout alternation from the wrong `leafcutter/`
#   prefix to the documented `leafcutter-ai/` (CLAUDE.md "Repository
#   Structure"), and declared both gates exempt with a stated ground for
#   the same reason as check-infra-docs, so a correct-but-context-
#   dependent trigger can never become a universal commit-blocker.
# ====================================================================
