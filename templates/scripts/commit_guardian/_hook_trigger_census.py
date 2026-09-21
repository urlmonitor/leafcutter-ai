"""
MODULE: _hook_trigger_census
GOAL: The disk-side gate-script census, the entry-line invoking-side
    extraction, and the declared-non-gate register validation required by
    BP-100n-4 / BP-100n-4-i / BP-100n-4-ii. Split out of
    check_hook_trigger_reachability.py and _hook_trigger_reachability_helpers.py
    (both already close to the 400-line file-size cap) into a fresh sibling
    module, per those files' own DECISION HISTORY guidance: "if the guard
    still exceeds the cap, split a further sibling INSIDE
    templates/scripts/commit_guardian/ -- never outside it."
BUSINESS CONTEXT: KI-CG-20260831-hook-scripts-never-invoked. BP-100k-4's
    reachability guard walks only hooks_manifest.hooks -- its input IS the
    registry, so a script nobody registered at all is invisible to it. This
    module supplies the missing disk side: every check_*.py-shaped file
    actually present beneath the gate-script directory, recursively, and the
    generated commit-time configuration's own entry lines (never a kebab-cased
    id comparison, never the last whitespace token, which misreads a trailing
    flag such as check-done-proof's "--test-root .").
ARCHITECTURE: Registry loading distinguishes "no candidate exists" from "a
    candidate exists but is corrupt" (mirrors the sibling drift gates' F2/F6
    finding) and, for BP-100n-4-ii, further distinguishes "unreadable" from
    "unparseable" in the returned reason text so the two conditions are never
    reported identically. The disk listing distinguishes "the directory could
    not be listed" from "the directory listed successfully but is empty" for
    the same reason -- both are floors that return (None, reason) rather than
    silently completing on no evidence, mirroring
    check_hook_trigger_reachability.py's own
    _resolve_hooks_or_reason/_resolve_tracked_paths_or_reason pattern.

    BP-100n-4 (file-size split): ``resolve_hooks_or_reason`` moved here from
    check_hook_trigger_reachability.py, which was over the 400-line cap. It
    extracts and floor-checks ``hooks_manifest.hooks`` from the SAME loaded
    registry this module's ``load_registry_or_reason`` already resolves, so
    it belongs beside that function rather than in a differently-scoped
    sibling.

    Invoking-script resolution (``resolve_invoked_script``) matches an
    entry's LAST ``.py``-suffixed token against the disk census by path
    SUFFIX, preferring the longest match. This works uniformly whether the
    entry carries the full templated path
    ("{{config.output_root}}/scripts/commit_guardian/hooks/check_x.py") or a
    bare filename (as in a synthetic HOOK_TEST_CONFIG fixture), and is what
    keeps ``hooks/check_ac_limits.py`` and ``check_ac_limits.py`` — two
    distinct population members sharing a bare filename — from being
    conflated: a token ending in ".../check_ac_limits.py" matches the
    top-level entry only, never the longer "hooks/check_ac_limits.py" suffix.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_GATE_NAME = "check-hook-trigger-reachability"
HOOK_TEST_GATE_DIR_ENV_VAR = "HOOK_TEST_GATE_DIR"
_GATE_SCRIPT_PREFIX = "check_"


def census_is_enabled() -> bool:
    """Whether the BP-100n-4 disk-side census should run this invocation.

    Test-only compatibility shim. A synthetic HOOK_TEST_CONFIG registry
    fixture PREDATING this census (BP-100k-4 / -i / -ii) exercises the
    registered-gate reachability predicate against a deliberately small,
    hand-built registry while leaving the real gate-script directory on
    disk untouched. Under an unconditional census, every real script that
    tiny fixture registry does not mention would be reported UNREFERENCED,
    failing a run those pre-existing tests never intended to fail. The
    census is disabled ONLY when ``HOOK_TEST_CONFIG`` is set without an
    accompanying ``HOOK_TEST_GATE_DIR`` override -- the latter is this AC's
    own explicit signal that a test wants the disk side exercised (BP-
    100n-4-ii's synthetic clean-run test sets both together). Production
    code sets neither variable, so this branch is unreachable outside the
    test suite.

    Returns:
        False only when ``HOOK_TEST_CONFIG`` is set and
        ``HOOK_TEST_GATE_DIR`` is not; True otherwise.
    """
    return not os.environ.get("HOOK_TEST_CONFIG") or bool(
        os.environ.get(HOOK_TEST_GATE_DIR_ENV_VAR)
    )


def resolve_gate_dir(default_dir: Path) -> Path:
    """Resolve the directory the disk-side census walks.

    Args:
        default_dir: The directory holding the running hook script itself,
            used unless overridden.

    Returns:
        ``HOOK_TEST_GATE_DIR`` as a ``Path`` when set (test-only override so
        BP-100n-4-ii's indeterminate-path tests can make a listing genuinely
        unlistable/empty without disturbing the script's own directory);
        otherwise ``default_dir``. Production code never sets this variable.
    """
    override = os.environ.get(HOOK_TEST_GATE_DIR_ENV_VAR)
    return Path(override) if override else default_dir


def _raise_walk_error(exc: OSError) -> None:
    """``os.walk`` onerror callback: re-raise so listing failures propagate.

    ``os.walk`` silently swallows a scandir failure by default (calling no
    callback at all), which would make an unlistable directory look
    identical to an empty one -- exactly the fail-open shape this AC exists
    to forbid. Supplying this callback turns that failure back into a raised
    exception the caller can catch.
    """
    raise exc


def list_gate_scripts_or_reason(gate_dir: Path) -> tuple[list[str] | None, str | None]:
    """Recursively enumerate gate scripts beneath *gate_dir*.

    A gate script is any ``check_*.py`` file, at any depth, identified by
    its path relative to *gate_dir* (never its bare filename) so that e.g.
    ``hooks/check_ac_limits.py`` and ``check_ac_limits.py`` are two distinct
    population members.

    Args:
        gate_dir: Directory to walk (the real gate-script directory, or a
            ``HOOK_TEST_GATE_DIR`` override).

    Returns:
        A ``(paths, reason)`` pair. On success, ``paths`` is a sorted list of
        forward-slash relative paths and ``reason`` is None. On failure,
        ``paths`` is None and ``reason`` names ONE of two distinct
        situations: the directory could not be listed at all ("unlistable"),
        or it listed successfully but holds no gate scripts ("empty") --
        BP-100n-4-ii requires these be distinguishable, never folded together.
    """
    if not gate_dir.exists():
        return None, (
            f"the gate-script directory {gate_dir} does not exist (unlistable) "
            "-- which gate scripts exist could not be established"
        )

    found: list[str] = []
    try:
        for root, dirs, files in os.walk(gate_dir, onerror=_raise_walk_error):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if name.startswith(_GATE_SCRIPT_PREFIX) and name.endswith(".py"):
                    rel = Path(root, name).relative_to(gate_dir)
                    found.append(str(rel).replace(os.sep, "/"))
    except OSError as exc:
        return None, (
            f"the gate-script directory {gate_dir} is unlistable: {exc} -- "
            "which gate scripts exist could not be established"
        )

    if not found:
        return None, (
            f"the gate-script directory {gate_dir} listed successfully but "
            "holds no gate scripts (empty) -- reachability cannot be "
            "established from no evidence"
        )
    return sorted(found), None


def _read_json_file(path: Path) -> dict | None:
    """Read and parse one JSON file, returning None on any I/O or parse error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as exc:
        print(f"{_GATE_NAME}: WARNING - could not read {path}: {exc}", file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print(f"{_GATE_NAME}: WARNING - {path} is not valid JSON: {exc}", file=sys.stderr)
        return None


def load_registry_or_reason(hook_file: Path) -> tuple[dict | None, str | None]:
    """Resolve and load the hooks_manifest registry.

    BP-100n-4-ii: an absent candidate ("unreadable") and a present-but-corrupt
    one ("unparseable") are different facts about the world and must be named
    with different reason text -- never the same message for both.

    Args:
        hook_file: Absolute path of the running hook script, used to locate
            the colocated source-tree registry copy as the final fallback.

    Returns:
        A ``(registry, reason)`` pair: ``(dict, None)`` on success, or
        ``(None, reason)`` naming which of the two situations applies.
    """
    test_config_path = os.environ.get("HOOK_TEST_CONFIG")
    if test_config_path:
        candidate = Path(test_config_path)
        if not candidate.exists():
            return None, f"HOOK_TEST_CONFIG={candidate} does not exist (registry unreadable)"
        registry = _read_json_file(candidate)
        if registry is None:
            return None, (
                f"HOOK_TEST_CONFIG={candidate} exists but is not valid JSON "
                "(registry unparseable)"
            )
        return registry, None

    candidates = [
        Path.cwd() / "scripts" / "commit_guardian" / "commit_guardian.json",
        hook_file.parent / "commit_guardian.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        registry = _read_json_file(candidate)
        if registry is None:
            return None, (
                f"{candidate} exists but could not be parsed as JSON (registry "
                "unparseable) -- this is the registry pre-commit would actually "
                "run, so the check is not falling through to try a different copy"
            )
        return registry, None
    return None, (
        "no hooks_manifest registry candidate exists (HOOK_TEST_CONFIG unset; "
        "deployed and source commit_guardian.json are both absent) -- registry unreadable"
    )


def resolve_hooks_or_reason(registry: dict) -> tuple[list[dict] | None, str | None]:
    """Extract and floor-check ``hooks_manifest.hooks`` from a loaded registry.

    BP-100k-4 round-2 hardening (F7): a run that inspected zero gates has
    established nothing — mirrors the ``verified == 0`` floor the sibling
    drift gates already enforce. An absent/wrong-typed list, an empty list,
    or a list whose every entry is disabled/non-dict are all INDETERMINATE,
    never a clean pass.

    Args:
        registry: The loaded registry dict.

    Returns:
        A ``(hooks, reason)`` pair: ``(hooks_list, None)`` on success, or
        ``(None, reason)`` with a diagnostic suitable for the
        ``INDETERMINATE: reason=<...>`` line.
    """
    hooks_manifest = registry.get("hooks_manifest")
    hooks = hooks_manifest.get("hooks") if isinstance(hooks_manifest, dict) else None
    if not isinstance(hooks, list):
        return None, "registry is missing a valid hooks_manifest.hooks list"

    eligible_entries = [
        entry
        for entry in hooks
        if isinstance(entry, dict) and entry.get("enabled") is not False
    ]
    if not eligible_entries:
        return None, (
            "hooks_manifest.hooks contains no evaluable entries (empty "
            "list, or every entry is disabled/non-dict) — a run that "
            "inspected zero gates has established nothing"
        )
    return hooks, None


def resolve_invoked_script(entry_text: str, disk_scripts: set[str]) -> str | None:
    """Resolve which disk-census member (if any) an entry line invokes.

    Takes the LAST whitespace-delimited token that ends in ``.py`` (never the
    last whitespace token overall, which misreads a trailing flag such as
    check-done-proof's ``--test-root .`` as the invoked script) and matches it
    against the disk census by path suffix, preferring the longest match so a
    path held in a subdirectory is never shadowed by a same-named top-level
    script.

    Args:
        entry_text: The raw ``entry`` field of one hooks_manifest.hooks item.
        disk_scripts: The disk-side census (paths relative to the gate dir).

    Returns:
        The matching disk-census member, or None if no ``.py`` token exists
        or none matches (e.g. the script lives outside the gate directory
        entirely, such as docs/product-truth/scripts/*.py).
    """
    py_tokens = [t for t in entry_text.split() if t.endswith(".py")]
    if not py_tokens:
        return None
    last = py_tokens[-1].replace("\\", "/")
    best: str | None = None
    for candidate in disk_scripts:
        if last == candidate or last.endswith("/" + candidate):
            if best is None or len(candidate) > len(best):
                best = candidate
    return best


def classify_invocation(
    hooks: list[dict], disk_scripts: set[str]
) -> tuple[set[str], set[str]]:
    """Split the disk census into invoked and switched-off members.

    Args:
        hooks: The full (raw) ``hooks_manifest.hooks`` list.
        disk_scripts: The disk-side census.

    Returns:
        A ``(invoked, switched_off)`` pair. ``invoked`` is every disk-census
        member named on an EMITTED (not ``enabled: false``) entry line.
        ``switched_off`` is every member named ONLY by a disabled entry --
        registered-and-off is a third state, distinct from invoked and from
        absent, per BP-100n-4's own criteria.
    """
    invoked: set[str] = set()
    switched_off: set[str] = set()
    for entry in hooks:
        if not isinstance(entry, dict):
            continue
        script = resolve_invoked_script(entry.get("entry", ""), disk_scripts)
        if script is None:
            continue
        if entry.get("enabled") is False:
            switched_off.add(script)
        else:
            invoked.add(script)
    switched_off -= invoked
    return invoked, switched_off


def validate_non_gate_records(
    entries: object, disk_scripts: set[str], invoked_scripts: set[str]
) -> dict[str, str]:
    """Validate the script-keyed declared-non-gate register (BP-100n-4-i).

    Reports (as a side effect, on stderr) every record that is redundant (its
    script is invoked), stale (its script is absent from disk), or refused
    (its ground is blank/whitespace-only) -- in that priority order, so a
    record that is both invoked and groundless is reported redundant, never
    doubly reported.

    Args:
        entries: The raw ``hook_trigger_reachability_exemption_registry``
            value. Only dict entries carrying a ``script`` key are
            considered here; ``id``-keyed entries belong to the pre-existing
            registered-gate exemption path and are ignored.
        disk_scripts: The disk-side census.
        invoked_scripts: Scripts invoked by an emitted entry line.

    Returns:
        Mapping of script -> non-blank ground text, for records that are
        honoured as a declared non-gate.
    """
    declared: dict[str, str] = {}
    if not isinstance(entries, list):
        return declared
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        script = entry.get("script")
        if not script:
            continue
        if script in invoked_scripts:
            print(
                f"REDUNDANT NON-GATE RECORD: {script} reason=script is "
                "invoked by an emitted entry line; this non-gate record no "
                "longer applies",
                file=sys.stderr,
            )
            continue
        if script not in disk_scripts:
            print(
                f"STALE NON-GATE RECORD: {script} reason=no such script "
                "exists on disk",
                file=sys.stderr,
            )
            continue
        ground = entry.get("ground", "")
        if isinstance(ground, str) and ground.strip():
            declared[script] = ground.strip()
        else:
            print(
                f"REJECTED NON-GATE RECORD: {script} reason=no ground stated",
                file=sys.stderr,
            )
    return declared


def report_unreferenced_and_switched_off(
    disk_scripts: list[str],
    invoked_scripts: set[str],
    switched_off_scripts: set[str],
    declared_non_gate: dict[str, str],
) -> list[str]:
    """Print the per-script census verdicts and return the unreferenced set.

    A script on an emitted entry line is reported in NEITHER class -- "not
    reported at all" is the correct, silent outcome for it (BP-100n-4).

    Args:
        disk_scripts: The disk-side census, in any deterministic order.
        invoked_scripts: Scripts invoked by an emitted entry line.
        switched_off_scripts: Scripts named only by a disabled entry.
        declared_non_gate: Scripts covered by a grounded non-gate record.

    Returns:
        The scripts that are on disk, not invoked, not switched off, and not
        declared a non-gate -- the population the run fails on.
    """
    unreferenced: list[str] = []
    for script in disk_scripts:
        if script in invoked_scripts:
            continue
        if script in declared_non_gate:
            print(
                f"DECLARED-NON-GATE: {script} ground={declared_non_gate[script]}",
                file=sys.stderr,
            )
            continue
        if script in switched_off_scripts:
            print(
                f"SWITCHED-OFF: {script} reason=named only by a registry "
                "entry with enabled: false -- registered and switched off, "
                "distinct from invoked and from absent",
                file=sys.stderr,
            )
            continue
        print(
            f"UNREFERENCED: {script} reason=no emitted registry entry line "
            "invokes this script",
            file=sys.stderr,
        )
        unreferenced.append(script)
    return unreferenced


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-07 [python-coder/BP-100n-4 + BP-100n-4-i + BP-100n-4-ii]: created
#   module. Split out of check_hook_trigger_reachability.py and
#   _hook_trigger_reachability_helpers.py (both near the 400-line cap) to
#   hold the new disk-side census, entry-line invoking-side extraction, the
#   declared-non-gate register, and the registry-load unreadable/unparseable
#   distinction. See check_hook_trigger_reachability.py's own DECISION
#   HISTORY for the integration and docs/known-issues/commit-guardian.md
#   (KI-CG-20260831-hook-scripts-never-invoked) for the source finding.
# - 2026-09-07 [python-coder/BP-100n-4, file-size split]:
#   check_hook_trigger_reachability.py exceeded the 400-line file-size cap
#   (424 counted lines) once the disk-side census above was wired in. Moved
#   ``resolve_hooks_or_reason`` here — it extracts hooks_manifest.hooks from
#   the same loaded registry ``load_registry_or_reason`` already resolves,
#   so it belongs beside that function. Pure move, no behavior change:
#   `main()` in check_hook_trigger_reachability.py now imports and calls it
#   under its unchanged shape (only the leading underscore was dropped,
#   since it is now a public export of this module). See that module's own
#   DECISION HISTORY. (#BP-100n-4)
# ====================================================================
