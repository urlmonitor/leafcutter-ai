"""
MODULE: check_presence_only_assertions
GOAL: Pre-commit hook that rejects newly added tests over workflow / commit-
    guardian source whose entire "coverage" is a grep for a symbol's presence
    (a substring check or a regular-expression declaration check) — the exact
    defect class BP-1100b-4 confirmed and fixed in one incumbent test.
BUSINESS CONTEXT: EPIC-BuildPipelinePhantomRemediation's own thesis, applied to
    the test suite that let earlier phantom-done guards report a pass they had
    not earned. A presence-only assertion stays green on unreachable code — it
    proves a symbol's TEXT exists in a source file, never that the code runs —
    so it is not coverage. This hook is a ratchet: it reads STAGED HUNKS ONLY
    (never a whole-file/whole-tree scan), so the 46 pre-existing violations
    already in unit_tests/workflows/ and unit_tests/commit_guardian/ do not
    make this hook's own introducing commit unmergeable. Nothing new lands;
    the backlog is cleaned by a separate sweep (see the ticket's "Out of
    Scope" section). A `# presence-only: <reason>` comment (non-empty reason)
    directly above the assertion is the deliberate-acceptance route.
ARCHITECTURE: Reads the staged diff via `git diff --cached` (or HOOK_TEST_DIFF
    for testing); during a merge / revert / cherry-pick it instead judges the
    authored change from the shared `_authored_change.get_authored_change()`
    (GE-120e-1), so content carried in from the other side is not judged
    again. A derivation that cannot be computed reports could-not-check and
    never widens to the unscoped diff and the `presence_only_assertion_guard` config section of
    commit_guardian.json (or HOOK_TEST_CONFIG for testing — see
    unit_tests/commit_guardian/test_bp_1100b_5.py's module docstring for the
    full test-interface contract). Diff parsing and pattern detection live in
    the private `_presence_only_scanner` module (split out to respect the
    400-line file-size limit); this module owns config/diff acquisition,
    reporting, and the entry point. scanned_source_globs is DATA read from
    commit_guardian.json — never hardcoded here or in the scanner module.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SCANNER_DIR = Path(__file__).resolve().parent
if str(_SCANNER_DIR) not in sys.path:
    sys.path.insert(0, str(_SCANNER_DIR))

try:
    from check_outcome import OUTCOME_COULD_NOT_CHECK, emit_result
except ImportError:
    # check_outcome.py is deployed alongside this file in every real layout;
    # this fallback serves a working copy exposing this script in isolation.
    # The values MUST stay in sync with check_outcome.py.
    OUTCOME_COULD_NOT_CHECK = "could_not_check"

    def emit_result(outcome: str) -> None:
        """Fallback RESULT-line emitter used when check_outcome is absent."""
        print(f"RESULT: {outcome}", file=sys.stdout)

try:
    from _authored_change import get_authored_change  # type: ignore[import]
except ImportError:
    # Deployed alongside this file in every real layout; fallback only for a
    # working copy that exposes this script in isolation.
    get_authored_change = None  # type: ignore[assignment]

from _presence_only_scanner import (  # noqa: E402
    Violation,
    Waiver,
    is_test_file_path,
    scan_file_block,
    split_diff_into_file_blocks,
)

_HOOK_NAME = "presence-only-assertion guard"
_CONFIG_SECTION = "presence_only_assertion_guard"
_DEFAULT_WAIVER_MARKER = "presence-only"


# ---------------------------------------------------------------------------
# Config + diff acquisition (testable via HOOK_TEST_CONFIG / HOOK_TEST_DIFF)
# ---------------------------------------------------------------------------


def _load_guard_config() -> dict:
    """Load the presence_only_assertion_guard config section.

    Uses HOOK_TEST_CONFIG (a path to a JSON file containing ONLY the guard's
    own config section) when set, for testing. Otherwise reads
    commit_guardian.json (next to this script) and returns its
    `presence_only_assertion_guard` key.

    Returns:
        The config dict, defaulting to a disabled, empty-globs config if the
        key is absent or unreadable.
    """
    test_config_path = os.environ.get("HOOK_TEST_CONFIG")
    if test_config_path:
        try:
            with open(test_config_path, encoding="utf-8") as f:
                return json.load(f)
        except OSError as exc:
            print(f"[{_HOOK_NAME}] ERROR: could not read HOOK_TEST_CONFIG: {exc}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as exc:
            print(f"[{_HOOK_NAME}] ERROR: HOOK_TEST_CONFIG is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    guardian_config_path = Path(__file__).resolve().parent / "commit_guardian.json"
    disabled = {"enabled": False, "scanned_source_globs": [], "waiver_marker": _DEFAULT_WAIVER_MARKER}
    try:
        with open(guardian_config_path, encoding="utf-8") as f:
            guardian_config = json.load(f)
    except OSError as exc:
        print(f"[{_HOOK_NAME}] WARNING: could not read commit_guardian.json ({exc}); skipping.", file=sys.stderr)
        return disabled
    except json.JSONDecodeError as exc:
        print(f"[{_HOOK_NAME}] WARNING: commit_guardian.json is not valid JSON ({exc}); skipping.", file=sys.stderr)
        return disabled

    return guardian_config.get(_CONFIG_SECTION, {})


def _get_staged_diff() -> str:
    """Return the staged diff, from HOOK_TEST_DIFF (testing) or `git diff --cached`."""
    test_diff_path = os.environ.get("HOOK_TEST_DIFF")
    if test_diff_path:
        try:
            return Path(test_diff_path).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[{_HOOK_NAME}] ERROR: could not read HOOK_TEST_DIFF: {exc}", file=sys.stderr)
            sys.exit(1)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        print(f"[{_HOOK_NAME}] ERROR: git diff --cached failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"[{_HOOK_NAME}] ERROR: could not invoke git: {exc}", file=sys.stderr)
        sys.exit(1)


def _get_scan_diff() -> str | None:
    """Return the diff to scan: the authored change during a merge, else the staged diff.

    Outside a merge (and under the HOOK_TEST_DIFF seam, or when the shared
    module is unavailable) this is exactly :func:`_get_staged_diff`. During a
    merge / revert / cherry-pick it is the shared GE-120e-1 authored change,
    so content carried in from the other side is not judged again.

    Returns:
        The diff text, or ``None`` when the authored change could not be
        derived (could-not-check; the caller MUST NOT widen to the unscoped
        diff).
    """
    if os.environ.get("HOOK_TEST_DIFF") or get_authored_change is None:
        return _get_staged_diff()
    try:
        authored = get_authored_change()
    except Exception as exc:  # noqa: BLE001 - shared dependency may raise unpredictably; must degrade to could-not-check, never crash or widen (GE-120e-1 AC-5).
        print(f"[{_HOOK_NAME}] WARNING: shared change-set derivation raised: {exc}", file=sys.stderr)
        return None
    if authored.could_not_check:
        return None
    if len(authored.states) <= 1:
        return _get_staged_diff()  # not a merge: unchanged behaviour
    return authored.diff_text  # merge-scoped; "" when nothing authored


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _report(violations: list[Violation], waivers: list[Waiver]) -> None:
    """Print the hook's human-readable report to stdout."""
    lines: list[str] = ["", f"[{_HOOK_NAME}]"]

    if violations:
        lines.append("BLOCKED — presence-only assertion(s) added over scanned source:")
        lines.append(
            "A presence-only assertion checks only that a symbol's text appears "
            "in a source file — it stays green even against unreachable code, "
            "so by itself it is not coverage."
        )
        for v in violations:
            lines.append(
                f"  - {v.test_file}: presence-only assertion ({v.kind}) for "
                f"'{v.symbol}' against {v.source_file}"
            )
        lines.append(
            "Accept deliberately with a `# presence-only: <reason>` comment "
            "directly above the assertion — the reason must be non-empty."
        )

    if waivers:
        lines.append("Waived presence-only assertion(s) (accepted deliberately):")
        for w in waivers:
            lines.append(
                f"  - {w.test_file}: '{w.symbol}' against {w.source_file} "
                f"— reason: {w.reason}"
            )

    lines.append("")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the presence-only-assertion guard.

    Returns:
        0 if the commit is allowed, 1 if an unwaived violation is found.
    """
    config = _load_guard_config()
    if not config.get("enabled", False):
        return 0

    globs: list[str] = config.get("scanned_source_globs", []) or []
    waiver_marker: str = config.get("waiver_marker", _DEFAULT_WAIVER_MARKER)
    marker_re = re.compile(rf"^\s*#\s*{re.escape(waiver_marker)}:\s*(.*)$")

    # NOTE: there is deliberately no path-exemption list here.
    #
    # One was added — `fixture_exempt_paths` — so this guard would not block
    # its own test file, on the reasoning that a `# presence-only:` waiver
    # placed inside a synthetic diff fixture would be consumed by the scanner
    # under test and invert what the test asserts. That reasoning describes a
    # placement nobody needs. The scanner receives only the `diff` STRING; a
    # waiver comment written in the test module's own Python source, outside
    # the fixture literal, is invisible to it and waives normally.
    #
    # The exemption was also strictly weaker than the waiver it replaced: it
    # `continue`d before scan_file_block, so an exempt path produced no output
    # whatsoever — no violation, no waiver line, no reason. The waiver design
    # exists so every accepted exception is listed in the check's output and
    # readable in one place; a silent path list is the "silent suppression
    # list" the criteria explicitly rule out. And because it matched with
    # fnmatch over whole paths, a single entry like "unit_tests/*" would have
    # disabled the guard repo-wide.
    #
    # If this guard's own fixtures trip it, waive them in the test source with
    # a stated reason, like every other caller has to.

    diff = _get_scan_diff()
    if diff is None:
        print(
            f"[{_HOOK_NAME}] WARNING: could not derive the authored (merge-scoped) "
            "change set for this commit - skipping the scan rather than falling "
            "back to the whole staged diff.",
            file=sys.stderr,
        )
        emit_result(OUTCOME_COULD_NOT_CHECK)
        return 0
    if not diff.strip() or not globs:
        return 0

    all_violations: list[Violation] = []
    all_waivers: list[Waiver] = []

    for new_path, added_lines, hunk_starts in split_diff_into_file_blocks(diff):
        if not is_test_file_path(new_path) or not added_lines:
            continue
        violations, waivers = scan_file_block(
            new_path, added_lines, globs, marker_re, hunk_starts
        )
        all_violations.extend(violations)
        all_waivers.extend(waivers)

    if all_violations or all_waivers:
        _report(all_violations, all_waivers)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-08-18 [EPIC-BuildPipelinePhantomRemediation/09]: Created. New
#   staged-hunk-only pre-commit hook rejecting newly added presence-only
#   assertions (substring form + regex-declaration form) over
#   commit_guardian.json-configured scanned_source_globs, with a
#   `# presence-only: <reason>` (non-empty reason) waiver escape hatch.
#   Detection logic lives in the companion _presence_only_scanner.py module
#   to respect the 400-line file-size limit. See BP-1100b-5 and ticket
#   09_bp1100b45_presence_only_assertions_stop_counting.md.
# - 2026-10-17 [python-coder/TICKET-20261017-PresenceOnlyMergeAware]: During a
#   merge / revert / cherry-pick the scan now reads the shared
#   _authored_change.get_authored_change() (GE-120e-1) instead of a bare
#   `git diff --cached`, which attributed every line the merged-in branch
#   brought to the merge author. A plain commit is unchanged; a derivation
#   that cannot be computed emits could-not-check and never widens to the
#   unscoped diff. Same fix as check-folder-density / check-file-size.
# ===========================================================================
