"""
MODULE: build_phases_local_change
GOAL: Own the ACD-2100d-2-i local-change-before-overwrite announcement --
    detecting when an installed generated file was edited after the last
    install (a "local change", per KI-ACD-004) and announcing the loss in
    the run's own output, by name, right before the install overwrites it.
BUSINESS CONTEXT: On 2026-08-18 a hand-applied repair was patched directly
    into a DEPLOYED copy. The next ``build.py`` run silently discarded it --
    the workaround did not fail loudly, it disappeared, and the operator who
    applied it had every reason to believe it was still in effect. This
    module closes that gap: the same loss is now visible in the installer's
    own output at the moment it happens. The install always wins -- nothing
    here refuses, preserves, or merges the local edit; it only announces it
    before it is replaced.
ARCHITECTURE: One module-level baseline (``set_local_change_baseline``, plus
    the ``_previous_output_mappings`` / ``_local_change_target_root`` /
    ``_local_change_output_root`` state it populates) and one public check
    (``announce_if_local_change_replaced``), extracted out of
    ``build_phases.py`` to keep that module under the 400-counted-line
    check-file-size limit (the same GE-127b-1 split ``build_phases_ac_store``,
    ``build_phases_workflows``, and their siblings already went through).
    Re-exported from ``build_phases.py`` so every existing caller (notably
    ``build.py``, which imports ``set_local_change_baseline`` and
    ``announce_if_local_change_replaced`` directly) keeps working unchanged.

    The divergence verdict is deliberately NOT authored here. It reuses
    ACD-2100d-2's own installer-derived mapping and per-file determination --
    the SAME ``output_mappings`` / ``expected_output_hash`` computation
    ``build_helpers._compute_output_mappings`` writes into
    ``.build_manifest.json`` and ``check_output_drift.py`` reads back at
    commit time -- so the delivery check and this install-time announcement
    can never disagree about which files diverged (see this ticket's own
    Implementation Notes: "CONSUME ACD-2100d-2's DETERMINATION, DO NOT AUTHOR
    ONE"). Concretely: before any phase writes a single file, build.py's
    main() calls ``set_local_change_baseline`` to record the PREVIOUS run's
    ``output_mappings`` (read from the ``.build_manifest.json`` already on
    disk, before this run's own manifest overwrites it). Each of
    ``build_phases.py``'s compare-before-write branches (``_write``,
    ``_files_content_identical``) and ``build_phases_workflows.py``'s
    ``build_workflow_scripts`` own inline SHA-256 compare then call
    ``announce_if_local_change_replaced`` right before overwriting an
    EXISTING file, while that file's pre-install content is still readable.
    ``write_file`` in build.py -- the fourth named branch -- imports
    ``announce_if_local_change_replaced`` from ``build_phases`` (which
    re-exports it from here) rather than duplicating the check.

    Canonicalisation reuses ``build_helpers._canonicalize_output_path`` --
    the exact function ``_compute_output_mappings`` itself calls to
    translate a pre-shim, ``output_root``-relative write target (e.g.
    ``<output_root>/workflows/build-epic.js``) into the canonical,
    ``target_root``-relative key ``output_mappings`` actually uses (e.g.
    ``.claude/workflows/build-epic.js``) -- never a second, independently
    maintained path translation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from build_helpers import _canonicalize_output_path

_log = logging.getLogger(__name__)

_previous_output_mappings: dict[str, Any] = {}
_local_change_target_root: Path | None = None
_local_change_output_root: Path | None = None


def set_local_change_baseline(target_root: Path, output_root: Path) -> None:
    """Record the previous install's output_mappings as this run's baseline.

    Must be called once, by build.py's main(), before any build phase writes
    a file, so the baseline reflects what the LAST install produced — never
    this run's own (not-yet-written) manifest. A missing or unreadable
    previous manifest degrades to an empty baseline (first install, or a
    manifest this check cannot vouch for): every announcement check below
    then no-ops rather than raising, since there is nothing to compare
    against.

    Args:
        target_root: Absolute path to the target project root. The previous
            manifest, if any, is read from
            ``target_root / ".build_manifest.json"`` — the exact path
            ``write_build_manifest()`` writes to (``repo_root == target_root``
            there by construction).
        output_root: Absolute path to the consolidated output directory
            (``target_root / config["output_root"]``), needed to translate a
            pre-shim write target into its canonical output_mappings key via
            ``build_helpers._canonicalize_output_path``.
    """
    global _previous_output_mappings, _local_change_target_root, _local_change_output_root  # noqa: PLW0603
    _local_change_target_root = target_root
    _local_change_output_root = output_root
    _previous_output_mappings = {}

    manifest_path = target_root / ".build_manifest.json"
    if not manifest_path.exists():
        return  # First install: no prior baseline, nothing can have diverged.
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning(
            "could not read the previous build manifest at %s to establish "
            "the local-change baseline; local-change announcements are "
            "disabled for this run: %s",
            manifest_path,
            exc,
        )
        return

    previous_mappings = manifest.get("output_mappings")
    if isinstance(previous_mappings, dict):
        _previous_output_mappings = previous_mappings


def _hash_for_local_change_check(path: Path) -> str | None:
    """Hash pre-write file content identically to check_output_drift.py.

    Normalises CRLF -> LF before hashing, matching
    ``check_output_drift._sha256_of_file`` exactly, so a Windows checkout's
    line-ending translation can never manufacture a false "local change"
    announcement that the delivery check itself would not also report.

    Args:
        path: Absolute path to the on-disk file to hash.

    Returns:
        Lowercase hex SHA-256 digest, or None if the file could not be read.
        The caller must not treat None as "clean" — per the repository
        error-handling policy, a read failure must not silently suppress the
        announcement.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _log.warning(
            "could not read %s to check whether a local change is about to "
            "be replaced: %s",
            path,
            exc,
        )
        return None
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _local_change_output_key(target: Path) -> str | None:
    """Resolve ``target`` to the output_mappings key its determination uses.

    Args:
        target: Absolute path a compare-before-write branch is about to
            overwrite.

    Returns:
        The forward-slash, ``target_root``-relative output_mappings key, or
        None when no baseline is set or ``target`` cannot be resolved to one
        (e.g. it lies outside both ``output_root`` and ``target_root``).
    """
    if _local_change_target_root is None:
        return None
    target_root = _local_change_target_root.resolve()
    resolved = target.resolve()

    if _local_change_output_root is not None:
        canonical = _canonicalize_output_path(
            resolved, _local_change_output_root.resolve(), target_root
        )
        if canonical is not None:
            try:
                return canonical.relative_to(target_root).as_posix()
            except ValueError:
                return None

    try:
        return resolved.relative_to(target_root).as_posix()
    except ValueError:
        return None


def announce_if_local_change_replaced(target: Path) -> None:
    """Print a notice when ``target`` diverged from the previous install.

    Fires only when ALL of the following hold, so a legitimate template
    change (every file is replaced on every install) is never mistaken for a
    local edit (per this ticket's own Implementation Notes: "a message for
    each [generated file] is noise ... which is the same as no message"):

    1. A previous-install baseline exists (``set_local_change_baseline`` was
       called and found a readable prior manifest).
    2. ``target`` already exists on disk (nothing has been lost on a first
       install).
    3. ``target``'s output_mappings key was recorded by the PREVIOUS install.
    4. ``target``'s CURRENT on-disk content hash does not match the
       previously recorded ``expected_output_hash`` for that key — i.e.
       something changed the file after the last install, the exact
       KI-ACD-004 shape.

    Never refuses, preserves, or delays the overwrite that follows this
    call — the install still wins; this only announces the loss before it
    happens. Callers must invoke this BEFORE overwriting ``target``, while
    its pre-install content is still readable.

    Args:
        target: Absolute path about to be overwritten.
    """
    if _local_change_target_root is None or not _previous_output_mappings:
        return
    if not target.exists():
        return

    output_key = _local_change_output_key(target)
    if output_key is None:
        return

    entry = _previous_output_mappings.get(output_key)
    previous_hash = entry.get("expected_output_hash") if isinstance(entry, dict) else None
    if not previous_hash:
        return  # Not recorded by the previous install — no baseline to diverge from.

    current_hash = _hash_for_local_change_check(target)
    if current_hash is not None and current_hash == previous_hash:
        return  # Unchanged since the last install: nothing is being lost.

    # current_hash is None (unreadable) OR it differs from the previous
    # install's own output — announce either way rather than silently
    # suppressing a read failure (repository error-handling policy).
    print(f"[build] NOTICE: a local change is being replaced: {output_key}")


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-01 [BrainCandy/ACD-2100d-2-i]: Added the local-change-before-
#   overwrite announcement. An installed generated file edited after the
#   last install was silently discarded on the next build.py run with no
#   trace in the output (KI-ACD-004, 2026-08-18). The install still always
#   wins; this only announces the loss before it happens, reusing
#   ACD-2100d-2's own output_mappings / expected_output_hash determination
#   rather than authoring a second one. (#ACD-2100d-2-i)
# - 2026-09-21 [python-coder/EPIC-StartingNewWorkTheProperWayAlways]:
#   Extracted this whole feature out of build_phases.py into its own module.
#   It was ported forward on a merge from origin/main's GE-127b-1 file-size-
#   ratchet split, which took build_phases.py's shape from a branch state
#   that predated ACD-2100d-2-i, so the feature was absent after the split
#   landed. Keeping it inline in build_phases.py would have pushed that file
#   back over the 400-counted-line limit the split exists to enforce, so it
#   follows the same sibling-module pattern build_phases_ac_store.py,
#   build_phases_workflows.py and the rest already use. No behaviour change
#   from the pre-split implementation. (#refactor/build-phases-size-limit)
# ===========================================================================
