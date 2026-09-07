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
    off, not a reachability question). This is a FOUR-WAY verdict —
    reachable / nothing-to-match / declared-exempt-with-ground /
    unreachable (BP-100k-4-ii added the "nothing-to-match" outcome; BP-
    100k-4 / BP-100k-4-i established reachable/exempt/unreachable, reusing
    the exemption vocabulary BP-100k-3 established for the drift gates —
    ``_drift_exemptions.py``: ``EXEMPT <key> ground=<text>``, with a
    groundless entry REJECTED and falling through to the un-exempted
    verdict):
      - ``always_run: true`` AND a ``files`` key present -> UNREACHABLE
        (whole-tree gate carrying a filter it never consults — this shape
        is never exemptable, it is always a real authoring mistake).
      - ``always_run: true``, no ``files`` -> reachable.
      - ``files`` present (``always_run`` not true): compiled as a regex
        and ``re.search`` against every ``git ls-files`` path. One or more
        matches -> reachable. Zero matches:
          - BP-100k-4-ii: if the pattern selects by file KIND rather than
            LOCATION (no regex start-of-string anchor ``^`` on any
            alternative — see ``has_location_anchor`` in
            _hook_trigger_reachability_helpers.py) -> NOTHING-TO-MATCH
            (reported by name, never blocks, never needs a stated
            exemption ground — a project that has not yet acquired a file
            of that kind is a gate with no work to do, not a gate that
            could never fire).
          - Otherwise (a location-anchored condition, unaffected by this
            AC): check the ``hook_trigger_reachability_exemption_registry``
            (a top-level key of the SAME loaded registry, entries shaped
            ``{"id": <gate-id>, "ground": <text>}``) for this gate's id. A
            valid (non-blank ``ground``) entry -> EXEMPT (reported, not
            counted as unreachable, never blocks). No entry, or a
            groundless one (rejected with ``REJECTED EXEMPTION ENTRY: <id>
            reason=no ground stated``) -> UNREACHABLE.
      - neither key present -> reachable (pre-commit's own default: an
        absent ``files`` filter matches everything).

    "Zero matches in the CURRENT repository" is not always "cannot ever
    match" — a correctly-authored trigger for a file family this specific
    checkout happens not to have is context-dependent, not structurally
    dead, and must not be forced into ``always_run`` or a rewritten pattern
    merely to satisfy this check (that would silently convert a conditional
    gate into an unconditional one for every consumer install). BP-100k-4-ii
    split this "not structurally dead" case in two, on whether the trigger
    selects by KIND or by LOCATION:
      - KIND-based (e.g. ``check-infra-docs``' docker-compose pattern,
        ``check-placeholder-defaults``' ``\\.py$``): the COULD-EVER/DOES-NOW
        distinction is drawn automatically by ``has_location_anchor`` and
        reported NOTHING-TO-MATCH — no exemption entry is needed or
        consulted.
      - LOCATION-based (e.g. ``check-mermaid-parent-link``'s
        ``docs/architecture/*.md``, a doc family a fresh scaffold has not
        created yet): the exemption registry remains the correct
        instrument, exactly as BP-100k-3 established for the drift gates —
        this AC does not touch that path.

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

    BP-100n-4 / BP-100n-4-i / BP-100n-4-ii (KI-CG-20260831-hook-scripts-
    never-invoked): everything above answers "of the REGISTERED gates,
    which can never fire" -- its input IS hooks_manifest.hooks, so a script
    nobody registered at all is invisible to it. This second census (in
    _hook_trigger_census.py) answers the prior question: which gate scripts
    EXIST at all, recursively, beneath this script's own directory
    (identified by path, never bare filename, so hooks/check_ac_limits.py
    and check_ac_limits.py are two distinct members), and which of them no
    EMITTED entry line invokes (the last ``.py``-suffixed token of the raw
    ``entry`` field, never the last whitespace token, which misreads a
    trailing flag such as check-done-proof's ``--test-root .`` as the
    invoked script). Four per-script classes, each reported by name on its
    own diagnostic line: UNREFERENCED (fails the run), SWITCHED-OFF (named
    only by an ``enabled: false`` entry -- registered and deliberately off,
    a third state distinct from invoked and from absent, never fails by
    itself), DECLARED-NON-GATE (a grounded record in the SAME
    hook_trigger_reachability_exemption_registry key, this time keyed on
    ``script`` rather than ``id`` -- BP-100n-4-i -- never fails by itself),
    and the silent fourth class of "invoked, reported nowhere." The RESULT
    line gains four counts: ``compared`` (gate scripts found on disk),
    ``registered`` (hooks_manifest entries read), ``unreferenced``, and
    ``declared_non_gate`` -- BP-100n-4-ii requires these be STATED in every
    run (never inferred from an empty output) and requires the disk listing
    and the registry read each carry their own zero-population INDETERMINATE
    floor, distinguishing "unlistable" from "empty" and "unreadable" from
    "unparseable" so neither failure can be reported as a clean pass.
    ``HOOK_TEST_GATE_DIR`` is a test-only override (mirrors
    ``HOOK_TEST_CONFIG``) that redirects the disk-side census to a directory
    other than this script's own, so BP-100n-4-ii's indeterminate-path tests
    can make a listing genuinely unlistable/empty without disturbing the
    directory the interpreter is loading this very script from.
"""

from __future__ import annotations

import sys
from pathlib import Path

# No ImportError fallback here (contrast check_build_drift.py's
# _drift_exemptions import): build_commit_guardian deploys the ENTIRE
# templates/scripts/commit_guardian/ directory verbatim (never a per-file
# allowlist), and every test fixture in this file family deploys the whole
# directory too (see _deploy_commit_guardian_dir in test_bp_100k_4.py) — so
# these sibling modules are always present alongside this one.
from _hook_trigger_census import (
    census_is_enabled,
    classify_invocation,
    list_gate_scripts_or_reason,
    load_registry_or_reason,
    report_unreferenced_and_switched_off,
    resolve_gate_dir,
    resolve_hooks_or_reason,
    validate_non_gate_records,
)
from _hook_trigger_reachability_helpers import (
    evaluate_all_gates,
    validate_exemptions,
)
from _hook_trigger_tracked_paths import resolve_tracked_paths_or_reason

_GATE_NAME = "check-hook-trigger-reachability"
_HOOK_FILE = Path(__file__).resolve()


# ---------------------------------------------------------------------------
# Registry resolution (load_registry_or_reason / resolve_hooks_or_reason) now
# lives in _hook_trigger_census.py (BP-100n-4-ii: distinguishes "unreadable"
# from "unparseable" in the returned reason); exemption registry validation,
# the per-gate reachability rule, and its registry-wide application
# (evaluate_all_gates) now live in _hook_trigger_reachability_helpers.py;
# tracked-path acquisition (resolve_tracked_paths_or_reason) now lives in
# _hook_trigger_tracked_paths.py. All three splits are purely to stay under
# the 400-line file-size limit — see each module's own docstring for its
# contract, and this file's DECISION HISTORY for the integration.
# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-commit hook.

    Returns:
        0 when no gate is UNREACHABLE and no disk-side script is
        UNREFERENCED (determinate run — NOTHING-TO-MATCH, SWITCHED-OFF and
        DECLARED-NON-GATE never count against this); 1 when one or more
        gates are unreachable or one or more disk-side scripts are
        unreferenced; 2 when reachability could not be determined at all
        (registry unreadable/unparseable, no evaluable gates, an
        unobtainable or empty tracked-path set, the gate-script directory
        unlistable/empty, or a regex evaluation exceeding its wall-clock
        bound) — never a silent pass in any of those cases (BP-100k-4-i,
        BP-100n-4-ii).
    """
    registry, load_failure_reason = load_registry_or_reason(_HOOK_FILE)
    if registry is None:
        print(f"INDETERMINATE: reason={load_failure_reason}", file=sys.stderr)
        return 2

    hooks, hooks_failure_reason = resolve_hooks_or_reason(registry)
    if hooks is None:
        print(f"INDETERMINATE: reason={hooks_failure_reason}", file=sys.stderr)
        return 2

    census_on = census_is_enabled()
    disk_scripts: list[str] = []
    if census_on:
        disk_scripts, disk_failure_reason = list_gate_scripts_or_reason(
            resolve_gate_dir(_HOOK_FILE.parent)
        )
        if disk_scripts is None:
            print(f"INDETERMINATE: reason={disk_failure_reason}", file=sys.stderr)
            return 2

    tracked_paths, tracked_failure_reason = resolve_tracked_paths_or_reason(Path.cwd())
    if tracked_paths is None:
        print(f"INDETERMINATE: reason={tracked_failure_reason}", file=sys.stderr)
        return 2

    exemptions = validate_exemptions(
        registry.get("hook_trigger_reachability_exemption_registry", [])
    )

    counts = evaluate_all_gates(hooks, tracked_paths, exemptions)
    if counts is None:
        return 2
    total, unreachable, exempt, nothing_to_match = counts

    unreferenced_scripts: list[str] = []
    declared_non_gate: dict[str, str] = {}
    if census_on:
        disk_scripts_set = set(disk_scripts)
        invoked_scripts, switched_off_scripts = classify_invocation(hooks, disk_scripts_set)
        declared_non_gate = validate_non_gate_records(
            registry.get("hook_trigger_reachability_exemption_registry", []),
            disk_scripts_set,
            invoked_scripts,
        )
        unreferenced_scripts = report_unreferenced_and_switched_off(
            disk_scripts, invoked_scripts, switched_off_scripts, declared_non_gate
        )

    print(
        f"{_GATE_NAME}: RESULT total={total} unreachable={unreachable} "
        f"exempt={exempt} nothing_to_match={nothing_to_match} "
        f"compared={len(disk_scripts)} registered={len(hooks)} "
        f"unreferenced={len(unreferenced_scripts)} "
        f"declared_non_gate={len(declared_non_gate)}",
        file=sys.stderr,
    )

    return 1 if (unreachable or unreferenced_scripts) else 0


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
# - 2026-08-26 [python-coder/EPIC-BuildPipelinePhantomRemediation, r2
#   hardening]: An adversarial logic review that EXECUTED this gate (not
#   just read it) found five defects — the charter defect ("a check that
#   cannot perform its check reporting a pass") recurring inside the check
#   written to police it:
#   (F5) an exemption entry keyed on the "<unknown>" display sentinel
#   silenced EVERY id-less gate at once, and a duplicated hooks-manifest id
#   let one exemption entry cover two distinct gates. Fixed by never
#   defaulting a missing id to the sentinel for LOOKUP purposes (only for
#   display), rejecting sentinel-keyed exemption entries outright, and
#   detecting duplicate ids up front so a duplicate can never resolve to
#   "exempt" — it is reported (`DUPLICATE-ID: ...`) and forced unreachable
#   instead.
#   (F6) a deployed registry that EXISTS but fails to parse fell through to
#   the colocated source copy and reported a clean pass against a registry
#   that was not the one pre-commit would actually run. `_load_registry` now
#   distinguishes "no candidate exists" (try the next one) from "a candidate
#   exists but is corrupt" (stop, INDETERMINATE) — mirrors the F2 finding
#   already known for the sibling drift gates.
#   (F7) an empty (or all-disabled/non-dict) `hooks_manifest.hooks` list
#   exited 0 with `total=0` — a run that inspected zero gates reported
#   clean. Added the same `verified == 0`-shaped floor BP-100k-3 uses for
#   the drift gates: zero evaluable entries is now INDETERMINATE.
#   (M) a repository with a successfully-empty tracked-path set (fresh
#   clone/submodule/shallow checkout before the first `git add`) was
#   evaluated as if the empty set were proof every files-triggered gate is
#   unreachable, rather than as "no evidence either way". Now INDETERMINATE.
#   (M) an unbounded `re.search` let a catastrophic-backtracking `files`
#   pattern hang the process forever with no verdict. Bounded with a
#   SIGALRM-based wall-clock guard (`search_any_with_timeout`, default 2s,
#   overridable via HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS for tests only);
#   exceeding the bound is INDETERMINATE, never a pass.
#   Exemption validation, the per-gate rule, and the timeout guard were
#   split into the new sibling module _hook_trigger_reachability_helpers.py
#   to stay under the 400-line file-size limit after this round's additions.
#   F8 (an empty-but-present `commands/` directory passing
#   `check_command_reachability`) is a DIFFERENT gate in
#   scripts/build_phases.py, out of this module's scope — not addressed
#   here. See /tmp/review_logic_round2.md and /tmp/review_code_round2.md.
# - 2026-09-07 [python-coder/BP-100k-4-ii] (KI-CG-20260831-0713): the
#   UNREACHABLE verdict was too strict in the opposite direction from
#   BP-100k-4-i — a kind-based `files` condition (no location anchor, e.g.
#   `\.py$`) matching zero of THIS checkout's tracked paths was reported
#   UNREACHABLE exactly like a condition naming a location no checkout
#   could ever produce, so a fresh adopter tracking no Python could not
#   make a first commit at all (two registered Python-kind gates,
#   check-placeholder-defaults / check-exception-handling, both tripped).
#   Added a fourth verdict, NOTHING-TO-MATCH (own diagnostic line, own
#   RESULT counter `nothing_to_match=<n>`, never blocking), drawn by
#   `_hook_trigger_reachability_helpers.has_location_anchor` on the
#   could-ever/does-now line: a condition with no regex start-of-string
#   anchor selects by KIND and can always eventually match SOME checkout,
#   so a zero-match today never makes it structurally unreachable — no
#   exemption ground is required or consulted. A location-anchored
#   condition is completely untouched: it still requires an exemption
#   entry or is UNREACHABLE, exactly as before this AC. `check-infra-docs`'
#   exemption entry in commit_guardian.json was removed as redundant under
#   the new automatic classification; `check-mermaid-parent-link` (a
#   location-anchored, `^docs/architecture/.*\.md$` pattern) keeps its
#   entry unchanged. `HOOK_TRIGGER_DISABLE_KIND_DISTINCTION=1` is a
#   test-only escape hatch restoring the pre-fix behavior (required by
#   test_bp_100k_4_ii.py's mutation-proof test). Deliberately narrow in
#   scope, per this AC's own constraints: does not widen which HOOKS this
#   check inspects (BP-100n-4 and siblings, "the check walks only
#   registered hooks", remain a separate, unbuilt-as-of-this-AC defect).
#   (#BP-100k-4-ii)
# - 2026-09-07 [python-coder/BP-100n-4 + BP-100n-4-i + BP-100n-4-ii]: widened
#   this guard's INPUT from "the registry" to "the registry AND the gate
#   directory on disk" (KI-CG-20260831-hook-scripts-never-invoked) — a script
#   nobody registered was invisible to the incumbent predicate, which walks
#   only hooks_manifest.hooks. Registry loading, the disk-side census, the
#   entry-line invoking-side extraction (last-.py-token, never last-
#   whitespace-token, never kebab-id), and the declared-non-gate register
#   were split into the new sibling _hook_trigger_census.py (this file and
#   _hook_trigger_reachability_helpers.py were both already near the
#   400-line cap). RESULT gains compared/registered/unreferenced/
#   declared_non_gate; day-one triage of the real registry's unreferenced
#   set is recorded in commit_guardian.json in this same change.
#   (#BP-100n-4, #BP-100n-4-i, #BP-100n-4-ii)
# - 2026-09-07 [python-coder/BP-100n-4, correction]: the day-one triage above
#   registered 19 previously-unwired scripts, taking hooks_manifest.hooks from
#   61 to 80 with unreferenced=0. Six of those 19 were withheld from this
#   corrected pass because they cannot currently be invoked the way pre-commit
#   actually invokes a `files: null`/no-`always_run` gate (positional staged
#   filenames; pass_filenames defaults true): check-ac-coverage,
#   check-debug-scripts, check-docstrings, check-documentation and
#   check-v2-ac-store-alignment each crash with `argparse: error: unrecognized
#   arguments: <path>` (exit 2) because their parsers define only optional
#   flags (--ac-dir/--test-dir, --file, --ticket/--ac-store, etc.) with no
#   positional or catch-all form; check-doc-coverage crashes earlier still,
#   with `NameError: name '_project_root' is not defined` (exit 1) at
#   argparse-setup time, before it can even reach its own advertised
#   always-exit-0 advisory behavior. Registering any one of the six as a real
#   gate would have reproduced KI-CG-20260831-0713 (a gate that blocks every
#   commit, here and in every consumer install) inside the very change meant
#   to close its sibling defect (KI-CG-20260831-hook-scripts-never-invoked).
#   The census finding that nothing invokes these six was correct; the
#   inference that they should therefore be switched on was not -- for these
#   six, nothing invokes them because nothing CAN. Each was instead recorded
#   as a script-keyed entry in hook_trigger_reachability_exemption_registry,
#   with a ground stating plainly that it is a BROKEN, TRACKED gate withheld
#   from registration (not a legitimate non-gate like check_outcome.py's
#   library-module entry), naming the exact failure, and noting that an AC is
#   being authored to fix each script's CLI and re-register it as a real gate.
#   The remaining 13 were verified individually (each invoked the same way,
#   each exits 0) and kept registered: check-complexity, check-doc-links,
#   check-file-size, check-folder-density, check-pytest-style,
#   check-root-files, check-sql-complexity, check-sql-dependencies,
#   check-test-ac-tags, check-test-fixture-bloat,
#   check-ticket-test-requirements, check-ticket-ac-limits (the
#   hooks/check_ac_limits.py filename-collision case), and
#   check-ac-done-on-merge (stages: [post-merge], verified separately).
#   RESULT after this correction: total=69 unreachable=0 exempt=0
#   nothing_to_match=1 compared=72 registered=74 unreferenced=0
#   declared_non_gate=7 (the six above plus check_outcome.py), exit 0.
#   (#BP-100n-4)
# - 2026-09-07 [python-coder/BP-100n-4, file-size split]: the BP-100n-4
#   integration above pushed this file to 424 counted lines (limit 400),
#   which the check-file-size gate correctly caught on its own registering
#   commit. Moved ``_resolve_hooks_or_reason`` to _hook_trigger_census.py
#   (renamed ``resolve_hooks_or_reason`` — it belongs beside that module's
#   ``load_registry_or_reason``, both reasoning about the same loaded
#   registry); ``_evaluate_all_gates`` / ``_apply_duplicate_id_override`` to
#   _hook_trigger_reachability_helpers.py (renamed ``evaluate_all_gates`` —
#   it is the registry-wide application of that module's own
#   ``evaluate_gate``; ``_apply_duplicate_id_override`` stayed private,
#   called only by ``evaluate_all_gates`` in its new home); and
#   ``_get_tracked_paths`` / ``_resolve_tracked_paths_or_reason`` to a NEW
#   sibling, _hook_trigger_tracked_paths.py (renamed ``get_tracked_paths`` /
#   ``resolve_tracked_paths_or_reason``) — moving them into
#   _hook_trigger_reachability_helpers.py instead (the first split target
#   tried) would have pushed that module itself to 406 counted lines, over
#   the same cap this change exists to satisfy, so tracked-path acquisition
#   (a distinct concern from both the disk-side script census and the
#   per-gate reachability rule) got its own well-named module rather than
#   being forced into either. Pure move: no behavior change, the RESULT
#   line and exit codes are unaffected. ``main()`` here now imports and
#   calls all five under their (mostly renamed) public names. File is 292
#   counted lines after the three-way split — headroom kept deliberately
#   generous so the next addition does not immediately re-trip this gate.
#   (#BP-100n-4)
# ====================================================================
