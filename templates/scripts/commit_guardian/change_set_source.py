"""
MODULE: change_set_source
GOAL: Determine, from the guardrail engine's hook manifest alone, which
    registered checks are recorded as taking their own change set (rather
    than the files the commit path hands them), and verify each one recorded
    that way genuinely consumes the shared authored-change derivation
    (``_authored_change.get_authored_change()``, GE-120e-1) rather than
    computing a private git diff of its own.

BUSINESS CONTEXT: Before this module, "which checks work out their own
    change set" was answered by remembering the two checks that were once
    observed doing it privately (``check_contract_shrinking.py`` and
    ``check_doc_frontmatter.py``) — a hand-written list that cannot notice a
    third check added tomorrow that also derives its own diff without
    routing through the shared source. GE-120e-2 replaces that with a
    per-entry ``change_set_source`` field on
    ``hooks_manifest.hooks[]`` (values ``handed_by_commit_path`` /
    ``self_derived``) and a determination that reads the manifest at run
    time, so membership is decided by a recorded, checkable fact rather than
    a name someone remembered to update. ``pass_filenames`` is explicitly
    NOT the discriminator: the large majority of registered checks carry
    ``pass_filenames: false`` while only a handful actually derive a diff at
    all, so a predicate built on that flag would misclassify almost every
    entry (see this AC's Implementation Notes).

ARCHITECTURE: A leaf module with no imports beyond the standard library,
    deployed alongside every other ``*.py`` in
    ``templates/scripts/commit_guardian/`` by ``build_commit_guardian()``'s
    whole-directory copy (no separate deploy-manifest entry required, per
    ADR-001's template/deployed parity convention). Public surface:
    ``determine_change_set_sources(manifest_path) -> DeterminationResult``,
    which loads ``hooks_manifest.hooks[]`` from the JSON at the GIVEN path
    (never a fallback to the installed manifest — an absent or unreadable
    path is a reported failure, not a silent read of some other file) and
    partitions every entry into exactly one of three buckets:
    ``.handed_its_files`` (recorded ``handed_by_commit_path``),
    ``.self_deriving`` (recorded ``self_derived`` AND whose own script text
    references the shared derivation), and ``.failures`` (missing the field,
    carrying an unrecognised value, or recorded ``self_derived`` without
    actually using the shared source — the exact misattribution this AC
    exists to catch mechanically). The self-derived compliance check is a
    STATIC text scan of the script named by the entry's last
    whitespace-delimited token (the same token-extraction idiom
    ``build_precommit.py``'s ``_check_hook_script_integrity`` already uses)
    for the substrings ``get_authored_change`` / ``_authored_change`` — never
    a subprocess execution, to stay inside the documented sub-200ms,
    no-subprocess-per-entry latency budget. A CLI entry point
    (``python3 change_set_source.py <manifest_path>``) prints each failing
    id and exits 1 when any entry failed, 0 otherwise, so a future manifest
    entry could register this determination as an ordinary commit-guardian
    check without a shape change.

    INTERIM DECISION ON GE-120c-3: this ticket's Implementation Notes ask to
    "reuse GE-120c-3's manifest-reading callable," but GE-120c-3 (a
    manifest-to-harness coverage comparison, a different facility) is itself
    still ``status: todo`` with no implementation to import — confirmed by
    reading ``19_TICKET-20260825-GE-120c-3.md`` at authoring time. This
    module therefore reads the manifest directly (``_load_manifest_hooks``)
    rather than importing a callable that does not exist yet. If GE-120c-3
    later lands a shared manifest reader, ``_load_manifest_hooks`` should be
    reconciled onto it so the two questions ("what's in the manifest") are
    never answered by two independent readers that can drift apart — the
    same rationale this AC's own Implementation Notes give for consuming one
    shared reader rather than inventing a second.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)

_HANDED_BY_COMMIT_PATH = "handed_by_commit_path"
_SELF_DERIVED = "self_derived"
_ALLOWED_SOURCE_VALUES = frozenset({_HANDED_BY_COMMIT_PATH, _SELF_DERIVED})

# Substrings whose presence in a self_derived check's own script text proves
# it genuinely consumes the shared authored-change derivation (GE-120e-1)
# rather than computing a private git diff. Checking both the function name
# and the module name catches `import _authored_change` (module-qualified
# call sites) as well as `from _authored_change import get_authored_change`.
_SHARED_SOURCE_MARKERS = ("get_authored_change", "_authored_change")


@dataclass
class DeterminationResult:
    """Partition of every manifest entry's recorded change-set source.

    Every id read from the manifest appears in EXACTLY ONE of the three
    lists below — the candidate set is complete and partitioned, never a
    subset. This mirrors GE-120e-2-i's already-committed usage of exactly
    these three attribute names.

    Attributes:
        handed_its_files: ids recorded ``change_set_source:
            "handed_by_commit_path"``.
        self_deriving: ids recorded ``change_set_source: "self_derived"``
            whose own script text references the shared authored-change
            derivation.
        failures: ids with no recorded ``change_set_source``, an
            unrecognised value, or recorded ``self_derived`` without
            actually using the shared source.
    """

    handed_its_files: list[str] = field(default_factory=list)
    self_deriving: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def _load_manifest_hooks(manifest_path: Path) -> list[dict]:
    """Load ``hooks_manifest.hooks[]`` from the JSON at ``manifest_path``.

    Reads exactly the given path — never a fallback to the installed
    manifest. Any I/O or parse failure is logged at WARNING and re-raised,
    per this repository's error-handling policy: a manifest the determination
    cannot read is a reported failure, not a silent empty result.

    Args:
        manifest_path: Path to a ``commit_guardian.json``-shaped file.

    Returns:
        The raw ``hooks_manifest.hooks`` list (may be empty).

    Raises:
        OSError: if ``manifest_path`` cannot be read (including if it does
            not exist).
        json.JSONDecodeError: if the file is not valid JSON.
        ValueError: if the file is valid JSON but ``hooks_manifest`` is
            absent or not a mapping.
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning(
            "change_set_source: cannot read manifest %s: %s", manifest_path, exc
        )
        raise

    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        _log.warning(
            "change_set_source: invalid JSON in manifest %s: %s", manifest_path, exc
        )
        raise

    hooks_manifest = cfg.get("hooks_manifest")
    if not isinstance(hooks_manifest, dict):
        message = (
            f"change_set_source: manifest {manifest_path} has no "
            "'hooks_manifest' mapping."
        )
        _log.warning(message)
        raise ValueError(message)

    hooks = hooks_manifest.get("hooks", [])
    if not isinstance(hooks, list):
        message = (
            f"change_set_source: manifest {manifest_path}'s "
            "'hooks_manifest.hooks' is not a list."
        )
        _log.warning(message)
        raise ValueError(message)
    return hooks


def _resolve_script_path(entry: str, manifest_path: Path) -> Path | None:
    """Resolve the on-disk script a manifest entry's ``entry`` field names.

    The last whitespace-delimited token of ``entry`` is the script path —
    the same idiom ``build_precommit.py``'s ``_check_hook_script_integrity``
    already uses. Two shapes are honoured: a token that is already an
    existing path (used by this AC's own fixture manifests), and the real
    manifest's templated form (e.g. ``{{config.output_root}}/scripts/
    commit_guardian/check_doc_frontmatter.py``), whose basename is resolved
    against the directory the given manifest itself lives in — the checks a
    manifest registers are always deployed alongside that manifest.

    Args:
        entry: The raw ``entry`` field of one manifest hook.
        manifest_path: Path to the manifest ``entry`` was read from.

    Returns:
        The resolved script path if it exists on disk, else None.
    """
    tokens = entry.split()
    if not tokens:
        return None

    direct = Path(tokens[-1])
    if direct.exists():
        return direct

    candidate = manifest_path.parent / direct.name
    if candidate.exists():
        return candidate

    return None


def _self_derived_uses_shared_source(entry: str, manifest_path: Path) -> bool:
    """Return True if the ``self_derived`` entry's script uses the shared source.

    A static text scan (never a subprocess execution, per this AC's latency
    budget) for ``get_authored_change`` / ``_authored_change`` in the
    resolved script's own source text. An unresolvable or unreadable script
    is treated as non-compliant (logged, not silently passed) — a
    determination that cannot verify a self_derived claim must not credit it.

    Args:
        entry: The raw ``entry`` field of the manifest hook being checked.
        manifest_path: Path to the manifest ``entry`` was read from.

    Returns:
        True if the script text references the shared derivation.
    """
    script_path = _resolve_script_path(entry, manifest_path)
    if script_path is None:
        _log.warning(
            "change_set_source: could not resolve script for entry %r "
            "(manifest %s) — treating as non-compliant.",
            entry,
            manifest_path,
        )
        return False

    try:
        text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _log.warning(
            "change_set_source: cannot read script %s: %s", script_path, exc
        )
        return False

    return any(marker in text for marker in _SHARED_SOURCE_MARKERS)


def _classify_hook(
    hook: dict, manifest_path: Path, result: DeterminationResult
) -> None:
    """Classify a single manifest hook into exactly one bucket of ``result``.

    Args:
        hook: One raw entry from ``hooks_manifest.hooks``.
        manifest_path: Path to the manifest ``hook`` was read from (needed
            to resolve a ``self_derived`` entry's own script for the
            shared-source compliance check).
        result: The accumulator mutated in place.
    """
    hook_id = hook.get("id")
    if not isinstance(hook_id, str) or not hook_id:
        # A structurally malformed entry (no usable id) cannot be named in
        # any of the three lists — nothing to report it as. Skipped rather
        # than crashing the whole determination on one bad entry.
        return

    source = hook.get("change_set_source")
    if source not in _ALLOWED_SOURCE_VALUES:
        result.failures.append(hook_id)
        return

    if source == _HANDED_BY_COMMIT_PATH:
        result.handed_its_files.append(hook_id)
        return

    # source == _SELF_DERIVED: membership additionally requires that the
    # entry's own script genuinely uses the shared authored-change source —
    # a declared value alone is not enough (AC-5's last clause).
    if _self_derived_uses_shared_source(hook.get("entry", ""), manifest_path):
        result.self_deriving.append(hook_id)
    else:
        result.failures.append(hook_id)


def determine_change_set_sources(manifest_path: Path) -> DeterminationResult:
    """Determine every manifest entry's recorded change-set source.

    The candidate set is every entry in ``manifest_path``'s
    ``hooks_manifest.hooks[]``, read at the time of this call — never a
    hand-written list of previously-observed offenders and never influenced
    by ``pass_filenames``. Membership in ``.self_deriving`` additionally
    requires that the entry's own script genuinely references the shared
    authored-change source; a ``self_derived`` entry that does not is named
    in ``.failures`` instead.

    Args:
        manifest_path: Path to a ``commit_guardian.json``-shaped manifest.
            Honoured exactly as given — never a fallback to the installed
            manifest.

    Returns:
        A ``DeterminationResult`` partitioning every manifest entry into
        exactly one of ``.handed_its_files`` / ``.self_deriving`` /
        ``.failures``.

    Raises:
        OSError: if ``manifest_path`` cannot be read.
        json.JSONDecodeError: if it is not valid JSON.
        ValueError: if it is valid JSON but not manifest-shaped.
    """
    manifest_path = Path(manifest_path)
    hooks = _load_manifest_hooks(manifest_path)

    result = DeterminationResult()
    for hook in hooks:
        if isinstance(hook, dict):
            _classify_hook(hook, manifest_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: report every failing check by name, exit non-zero on failure.

    Usage: ``python3 change_set_source.py <manifest_path>``. Reads the given
    manifest, runs the determination, prints each failing id to stderr, and
    returns 1 when any failure exists, 0 otherwise — mirroring every other
    ``check_*.py`` script in this directory so a future manifest entry could
    register this determination as an ordinary commit-guardian check without
    a shape change.

    Args:
        argv: Argument list (excluding the program name); defaults to
            ``sys.argv[1:]``.

    Returns:
        0 if every manifest entry's recorded change-set source is valid and
        (for self_derived entries) verified; 1 if any entry failed; 2 on a
        usage error (no manifest path given) or an unreadable/malformed
        manifest.
    """
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(
            "usage: change_set_source.py <manifest_path>",
            file=sys.stderr,
        )
        return 2

    manifest_path = Path(argv[0])
    try:
        result = determine_change_set_sources(manifest_path)
    # JSONDecodeError is a ValueError subclass, so it MUST be caught first —
    # ordered the other way round the generic clause shadows it and the
    # malformed-manifest message can never print (GE-120e-2 pr-reviewer H-1).
    except json.JSONDecodeError as exc:
        print(
            f"[change-set-source] FAILURE — manifest {manifest_path} is not "
            f"valid JSON: {exc}",
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as exc:
        print(
            f"[change-set-source] FAILURE — cannot determine change-set "
            f"sources from {manifest_path}: {exc}",
            file=sys.stderr,
        )
        return 2

    if result.failures:
        print(
            "[change-set-source] BLOCKED — the following checks have a "
            "missing, unrecognised, or unverified change_set_source:",
            file=sys.stderr,
        )
        for hook_id in result.failures:
            print(f"  - {hook_id}", file=sys.stderr)
        return 1

    print(
        f"[change-set-source] OK — {len(result.handed_its_files)} "
        f"handed-its-files, {len(result.self_deriving)} verified "
        "self-deriving, 0 failures."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 22:00 [EPIC-TrustThatAGreenCheckActuallyChecked/30, GE-120e-2,
#   python-coder]: Created module. determine_change_set_sources(manifest_path)
#   reads hooks_manifest.hooks[] from the given path (never a fallback to the
#   installed manifest) and partitions every entry into handed_its_files /
#   self_deriving / failures based on the recorded change_set_source field —
#   never pass_filenames. A self_derived entry is only counted compliant if
#   its own script's text references the shared _authored_change source
#   (GE-120e-1); otherwise it is named in .failures, generalising the two
#   originally-observed misattributing checks into a mechanical, per-entry
#   check. GE-120c-3 (the suggested shared manifest-reading callable) is
#   still status: todo, so this module reads the manifest directly for now —
#   see the ARCHITECTURE docstring's interim-decision note for the intended
#   reconciliation once GE-120c-3 lands.
# ====================================================================
