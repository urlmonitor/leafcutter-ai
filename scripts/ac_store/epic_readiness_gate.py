"""
epic_readiness_gate.py — The interactive / TTY-aware readiness gate.

MODULE: epic_readiness_gate
GOAL: Decide which subset of the leaf ACs an epic is built from when not all of
      them are approved — via a three-choice prompt when a controlling TTY is
      present, and via the --yes / --approved-only flags when it is not.
BUSINESS CONTEXT: Implements ACD-1200b-2 and ACD-1200b-4. The gate exists so an
      epic is never assembled from requirements nobody has signed off, while
      still being drivable from a non-interactive agent run. Split out of
      epic_readiness so both halves clear the 400-line check_file_size limit;
      the seam is read-only classification (there) versus stdin/stdout
      interaction and subprocess dispatch (here).
ARCHITECTURE: Owns every prompt, every gate-related print, and the one
      subprocess dispatch to run_it_po_v3.py, which it resolves relative to its
      own directory — always ``ac_store/`` in both the source and deployed
      layouts. Imports epic_readiness (to re-read after a review-all dispatch).
      Deployed flat beside goal_to_epic.py (see AC_STORE_DEPLOY_MAP in
      scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200b-2: readiness_gate_prompt() presents the three-choice prompt and
                 routes yes / review-all / cancel correctly, re-reading
                 readiness from disk after an IT PO v3 dispatch rather than
                 trusting an in-memory cache.
    ACD-1200b-4: a non-interactive run clears the gate with --yes or
                 --approved-only, and without either exits non-zero naming both
                 flags — never calling input() on a closed stdin.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from epic_readiness import classify_readiness, print_fast_path_message

# This module always lives in ``ac_store/`` under both layouts (see
# epic_tickets.py for the full explanation), so its siblings are
# unconditionally alongside it.
_sibling_dir = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# IT PO v3 dispatch (the "review-all" path)
# ---------------------------------------------------------------------------


def dispatch_it_po_v3(unapproved_ids: list[str], store_root: Path) -> None:
    """Dispatch IT PO v3 to review and enrich the given unapproved AC IDs.

    This is the integration point for the "review-all" path (ACD-1200b-2).
    In production, this function invokes the IT PO v3 agent via subprocess
    or Agent tool. The agent enriches and promotes unapproved ACs on disk.

    After this function returns, the caller MUST re-read the AC YAML files
    from disk to detect any promotions (ACD-1200b-2 it_requirement #4).

    Args:
        unapproved_ids: List of AC IDs to send to IT PO v3 for review.
        store_root: Root directory of the AC YAML store (so IT PO v3 knows
                    where to write promoted readiness values).

    Raises:
        subprocess.CalledProcessError: If the IT PO v3 invocation fails.
        RuntimeError: If the IT PO v3 agent is not available.
    """
    script_path = _sibling_dir / "run_it_po_v3.py"
    if not script_path.exists():
        raise RuntimeError(  # noqa: TRY003
            f"IT PO v3 runner not found at {script_path}. "
            "Deploy run_it_po_v3.py before using the review-all path."
        )
    try:
        subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--ac-ids",
                ",".join(unapproved_ids),
                "--store-root",
                str(store_root),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise subprocess.CalledProcessError(  # noqa: TRY003
            exc.returncode,
            exc.cmd,
        ) from exc


# ---------------------------------------------------------------------------
# Report + prompt primitives
# ---------------------------------------------------------------------------


def _print_readiness_report(
    approved: list[str],
    unapproved: list[dict],
    total: int,
) -> None:
    """Print the human-readable readiness report before the gate prompt.

    Args:
        approved: List of approved AC IDs.
        unapproved: List of unapproved dicts (each has id + readiness).
        total: Total number of leaf ACs.
    """
    m = len(approved)
    x = len(unapproved)
    print(f"{m} of {total} leaf ACs are approved. {x} ACs need approval:")
    for entry in unapproved:
        print(f"  - {entry['id']} (readiness: {entry['readiness']})")


def _prompt_choice(m: int) -> str:
    """Display the three-choice prompt and return the user's normalised answer.

    Args:
        m: Number of currently approved ACs (shown in the prompt).

    Returns:
        One of "yes", "review-all", or "cancel" (lowercased; default "cancel"
        on unrecognised input).
    """
    answer = input(
        f"Proceed with {m} approved ACs only? (yes / review-all / cancel): "
    ).strip().lower()
    if answer not in {"yes", "review-all", "cancel"}:
        answer = "cancel"
    return answer


# ---------------------------------------------------------------------------
# Routing (ACD-1200b-2)
# ---------------------------------------------------------------------------


def _review_all_and_reclassify(
    approved: list[str],
    unapproved: list[dict],
    store_root: Path,
) -> dict:
    """Dispatch IT PO v3 for the unapproved ACs, then re-read readiness from disk.

    A dispatch failure is reported on stderr and deliberately does not abort:
    the re-read still runs, and simply finds that nothing was promoted
    (ACD-1200b-2 it_requirement #4 — never trust an in-memory cache here).

    Args:
        approved: Currently approved AC IDs.
        unapproved: Currently unapproved entries (each has id + readiness).
        store_root: Root directory of the AC YAML store.

    Returns:
        dict: A fresh :func:`classify_readiness` result covering all the ids.
    """
    all_ids = list(approved) + [entry["id"] for entry in unapproved]
    unapproved_ids = [entry["id"] for entry in unapproved]

    try:
        dispatch_it_po_v3(unapproved_ids, store_root)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"WARNING: IT PO v3 dispatch failed: {exc}", file=sys.stderr)
        # Fall through to re-read; nothing may have changed.

    # Re-read readiness from disk (ACD-1200b-2 it_requirement #4)
    return classify_readiness(all_ids, store_root)


def _route_answer(
    answer: str,
    approved: list[str],
    unapproved: list[dict],
    store_root: Path,
    is_retry: bool,
) -> list[str] | None:
    """Route the gate answer to the appropriate action.

    Args:
        answer: Normalised user answer ("yes" | "review-all" | "cancel").
        approved: Currently approved AC IDs.
        unapproved: Currently unapproved entries.
        store_root: AC store root (needed for IT PO v3 dispatch + re-read).
        is_retry: True if this is the second presentation after a review-all
                  that did not promote all ACs. Prevents infinite loops.

    Returns:
        list[str] of approved IDs on "yes", or None on "cancel".
    """
    if answer == "cancel":
        return None

    if answer == "yes":
        return list(approved)

    # review-all path
    updated = _review_all_and_reclassify(approved, unapproved, store_root)
    updated_approved = updated["approved"]
    updated_unapproved = updated["unapproved"]

    if not updated_unapproved:
        # All promoted — fast-path
        print_fast_path_message(len(updated_approved))
        return list(updated_approved)

    # Re-present with the updated counts. Both the first pass and the retry did
    # exactly this before prompting again, so it is hoisted above the is_retry
    # branch rather than duplicated inside each arm.
    total = len(updated_approved) + len(updated_unapproved)
    _print_readiness_report(updated_approved, updated_unapproved, total)
    next_answer = _prompt_choice(len(updated_approved))

    if is_retry:
        # Already re-presented once — this was the final question.
        if next_answer == "yes":
            return list(updated_approved)
        return None  # cancel or unrecognised

    # First review-all: recurse once with the updated counts.
    return _route_answer(
        next_answer, updated_approved, updated_unapproved, store_root, is_retry=True
    )


def readiness_gate_prompt(
    readiness_dict: dict,
    store_root: Path,
) -> list[str] | None:
    """Present the three-choice readiness gate prompt and route the user's answer.

    The prompt reads: "Proceed with M approved ACs only? (yes / review-all / cancel)"

    Routing (ACD-1200b-2):
    - "yes"        → return only the approved IDs (caller proceeds with subset).
    - "review-all" → dispatch IT PO v3 for unapproved ACs; re-read readiness from
                     disk; re-evaluate the gate. If some ACs remain unapproved,
                     re-present the updated readiness report once and prompt again.
    - "cancel"     → return None. No epic is generated; no files are modified.

    Args:
        readiness_dict: Output of :func:`classify_readiness` —
            ``{"approved": list[str], "unapproved": list[dict]}``.
        store_root: Root directory of the AC YAML store (for re-reading after
                    IT PO v3 dispatch).

    Returns:
        list[str] — the final set of approved AC IDs to pass to ticket generation, OR
        None      — if the user chose "cancel".
    """
    approved = readiness_dict["approved"]
    unapproved = readiness_dict["unapproved"]
    m = len(approved)
    total = m + len(unapproved)

    # Print the readiness report
    _print_readiness_report(approved, unapproved, total)

    answer = _prompt_choice(m)
    return _route_answer(answer, approved, unapproved, store_root, is_retry=False)


# ---------------------------------------------------------------------------
# TTY-aware gate entry point (ACD-1200b-4)
# ---------------------------------------------------------------------------


def _gate_select_approved_ids(
    readiness: dict,
    store_root: Path,
    yes: bool,
    approved_only: bool,
) -> list[str] | None:
    """Select the approved AC IDs to proceed with at the readiness gate.

    Implements TTY-aware gate routing (ACD-1200b-4). Called only when
    ``readiness["unapproved"]`` is non-empty; the all-approved fast-path
    bypasses this function entirely.

    Routing:
    - No controlling TTY on stdin AND neither *yes* nor *approved_only* is set:
      prints a user-readable error naming the flags and calls ``sys.exit(1)``
      (never calls ``input()``, which would hang on a closed stdin).
    - *yes* or *approved_only* is set (regardless of TTY state): returns only
      the already-approved IDs from *readiness["approved"]*, mirroring the
      "yes" choice at the interactive prompt.
    - TTY present AND neither flag set: delegates to
      :func:`readiness_gate_prompt` for the original three-choice interactive
      behaviour (unchanged from pre-ACD-1200b-4).

    Args:
        readiness: Output of :func:`classify_readiness` containing ``approved``
            and ``unapproved`` keys.
        store_root: Root directory of the AC YAML store (forwarded to
            :func:`readiness_gate_prompt` for IT PO v3 dispatch on "review-all").
        yes: True when the ``--yes`` CLI flag was passed.
        approved_only: True when the ``--approved-only`` CLI flag was passed.

    Returns:
        list[str] of approved AC IDs to proceed with, or ``None`` when the
        interactive prompt received a "cancel" choice.

    Raises:
        SystemExit: Code 1 — no TTY and no approval flag present.
        SystemExit: Code 0 — *yes* or *approved_only* set but no approved ACs.
    """
    if not sys.stdin.isatty() and not yes and not approved_only:
        # Non-interactive run with no approval flag: fail clearly (ACD-1200b-4).
        # Never call input() here — it would hang indefinitely on a closed stdin.
        print(
            "ERROR: Unapproved ACs detected but no controlling TTY is available. "
            "Pass --yes to proceed with the already-approved ACs, or pass "
            "--approved-only to proceed with only already-approved leaf ACs.",
            file=sys.stderr,
        )
        sys.exit(1)
    if yes or approved_only:
        # Non-interactive approval: proceed with only the already-approved subset.
        # This mirrors choosing "yes" at the interactive prompt (ACD-1200b-4).
        if not readiness["approved"]:
            print("No approved ACs found. Nothing to generate.")
            sys.exit(0)
        return list(readiness["approved"])
    # TTY present, no flags: existing interactive behaviour (unchanged).
    return readiness_gate_prompt(readiness, store_root=store_root)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [EPIC-GoalToEpic/02]: Readiness gate implementation.
  Implements ACD-1200b-1: classify_readiness() reads the readiness field
  from each leaf AC YAML (read-only), classifies into approved/unapproved,
  completes in <500ms for <=100 leaves. Implements ACD-1200b-1-i:
  all-approved fast-path via print_fast_path_message(). Implements
  ACD-1200b-2: readiness_gate_prompt() with three-choice routing (yes /
  review-all / cancel), IT PO v3 dispatch via dispatch_it_po_v3(), and
  re-read from disk after dispatch to prevent stale cache bugs. Gate
  integrated into run() before ticket generation begins.
- 2026-07-20 [ACD-1200b-4]: Non-interactive readiness gate.
  Implements ACD-1200b-4: added --yes and --approved-only argparse flags to
  _build_parser(). Extended run() with matching yes/approved_only bool parameters
  (default False, backward-compatible). At the readiness gate in run(), TTY state
  is detected via sys.stdin.isatty(). When stdin has no controlling TTY and neither
  flag is set, the gate prints a clear error message naming --yes and --approved-only,
  then calls sys.exit(1) — never calls input(). When --yes or --approved-only is set,
  the gate proceeds with only the already-approved leaf ACs (same routing as choosing
  "yes" at the interactive prompt). Interactive (TTY present, no flags) behaviour is
  unchanged. main() passes args.yes and args.approved_only through to run().
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  dispatch_it_po_v3, _print_readiness_report, _prompt_choice,
  readiness_gate_prompt and _gate_select_approved_ids moved verbatim — every
  prompt string, every printed line and both sys.exit codes unchanged.
  Two edits, both behaviour-preserving:
  (1) _sibling_dir is Path(__file__).resolve().parent with no if/else guard,
      because this module is in ac_store/ under BOTH layouts;
  (2) _route_answer (cyclomatic 9) had the dispatch-and-re-read inline and then
      duplicated the report/prompt pair across its is_retry and first-pass
      arms. The dispatch is now _review_all_and_reclassify() and the
      report/prompt pair is hoisted above the is_retry check, which both arms
      performed identically before branching. Printed output order, prompts and
      the single-level recursion are unchanged; cyclomatic drops to 6.

  Split out of epic_readiness.py, which came to 455 lines with classification
  and the gate together. The seam is read-only classification (there) versus
  stdin/stdout interaction and subprocess dispatch (here), so the dependency
  runs one way: this module imports epic_readiness, never the reverse.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
