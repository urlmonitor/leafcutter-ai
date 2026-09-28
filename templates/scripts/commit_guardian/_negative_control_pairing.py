"""
MODULE: _negative_control_pairing
GOAL: Declaration-level pairing check and the (state, discrimination)
    mapping for GE-120f-1-ii's acceptable-input pairing -- split out of
    check_negative_control_liveness.py to keep that file under its
    400-counted-line limit (see that module's own DECISION HISTORY entry
    for GE-120f-1-ii, which was at 351/400 counted lines before this split
    with too little headroom left for the full pairing logic in place).
    Deployed verbatim alongside it: this file lives inside
    templates/scripts/commit_guardian/, so build_commit_guardian()'s
    directory copy carries it with no separate scripts/build_phases.py
    deploy-map entry needed -- that tree is deployed wholesale.
BUSINESS CONTEXT: GE-120f-1-ii -- a check that also refuses the work it is
    meant to accept has demonstrated nothing: refusing everything is as
    inert as refusing nothing, and must be reported under its own wording
    so a reader can tell which repair each needs (narrow the guard, or
    widen it -- opposite remedies). This module owns two pure decisions:
    (a) whether a hook's declared pair (known-bad input, acceptable input)
    can discriminate AT ALL, decided BEFORE either subprocess is invoked --
    a non-discriminating pair is a FINDING, never a malformed-input error,
    so it must be reported and the sweep must continue to the remaining
    hooks, never abort; and (b) composing the two invocations' own outcomes
    (plus GE-120f-1-i's own `demonstration` classification of the bad
    -input side) into the `discrimination` field's three distinct
    wordings, per architect-review's binding design (fb_2026-09-25_33c1543f,
    AMENDED by fb_2026-09-25_83f0382e -- the amendment supersedes the first
    note's `currently.state` vocabulary answer: `state` stays exactly the
    existing 4-value enum, and the three wordings live in this new sibling
    `discrimination` field instead).
ARCHITECTURE: Two pure functions. `pair_disposition()` is the only one that
    touches I/O-adjacent input (an untrusted `accept_command` string it
    tokenizes) -- its own `shlex.split` failure is caught internally
    because an unparsable acceptable-input declaration IS part of the
    declaration-level finding this function exists to produce, not a call
    its caller can usefully wrap. `classify_pair()` is a pure composition
    of three already-known booleans (Rule 4 -- no try/except). Neither
    function runs a subprocess: `check_negative_control_liveness.py`'s own
    `_examine()` is the only place that invokes
    `_run_negative_control_command()`, for both the bad-input and the
    acceptable-input side, in the SAME run.

DECISION HISTORY
====================================================================
- 2026-09-25 18:10 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii]: Initial split from check_negative_control_liveness.py, per
  architect-review's binding design (fb_2026-09-25_33c1543f, AMENDED by
  fb_2026-09-25_83f0382e). `pair_disposition()` implements Q2's mechanical
  "cannot discriminate" test (missing/empty acceptable command, or
  identical tokenized argv, via the SAME Windows-safe
  `shlex.split(text, posix=(os.name != "nt"))` rule
  check_negative_control_liveness.py's own `_tokenize()` already
  established). `classify_pair()` implements the amendment's mapping
  table: bad rejected + acceptable accepted + demonstration==entry_point
  -> passing/discriminates; bad rejected + acceptable also rejected ->
  failing/refuses_without_discriminating; bad not rejected ->
  failing/n/a (the existing "declared rejection not observed" wording,
  reused verbatim, unaffected by the acceptable side); bad rejected +
  acceptable accepted but demonstration==reach_inside -> failing/n/a
  (GE-120f-1-i's own reach-inside finding governs; this AC makes no claim).
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03)
- 2026-09-25 19:05 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii, coordinator rework]: WITHDRAWN a same-day narrowing
  (fb_2026-09-25_946dd180) that had exempted a hook with NO acceptable
  -input `command` at all from the `blocked`/`pair_cannot_discriminate`
  verdict, on the theory that pre-existing GE-120f-1/-i fixtures never
  declared one. The coordinator rejected this: THE LITERAL RULE IS
  UNCONDITIONAL -- a hook that declares `negative_control` but no
  acceptable `command` MUST read `state=blocked`/
  `discrimination=pair_cannot_discriminate` and fail the run, exactly like
  a declared-but-identical or unparsable pair, with NO carve-out for
  "never declared one." The narrowing was a real regression-avoidance
  shortcut, not a reading of the amendment: leaving it in place would let
  a guard widened to refuse everything read `passing` merely by never
  declaring an acceptable input -- precisely the escape this AC exists to
  close (a hook that refuses everything must be UNABLE to reach `passing`
  by omission, not just by an explicit broken declaration). The actual
  fix for the 4 regressions this narrowing had been avoiding was a
  FIXTURE gap, not a production-code exemption: test-writer's rework
  (fb_2026-09-25_d9d65758) gave every pre-existing `_ge_120f_1_fixtures.py`
  / `_ge_120f_1_i_fixtures.py` / `test_ge_120f_1_i.py` fixture hook a real,
  discriminating acceptable input, with zero assertion changes, so those
  suites now exercise `DISPOSITION_OK` rather than the missing-command
  path at all. `pair_disposition()` is back to its original two-value
  contract (`DISPOSITION_OK` / `DISPOSITION_CANNOT_DISCRIMINATE`); a
  missing/empty `accept_command` is handled by the SAME branch as an
  identical-argv or unparsable one, with no special case.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03)
- 2026-09-25 19:35 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii, pr-reviewer medium finding fb_2026-09-25_bb6a7c1d]:
  `blocked_pair_currently()` DROPPED its fourth `acceptable_command` key --
  `config/verification_flow.schema.json`'s `$defs/currently.evidence` items
  are `additionalProperties: false` with only `command`/`output`/`exit_code`
  allowed, and `currently` stays exactly schema-shaped per the binding
  design (fb_2026-09-25_83f0382e); the extra key made every declaration
  -level and failed-second-invocation `blocked` record schema-invalid.
  test-writer's `test_ge_120f_1_ii_b.py::test_ge120f1ii_every_written_currently_block_is_schema_shaped`
  was RED on exactly the 3 records this key touched (missing, identical,
  failed-second) and is now green. The signature narrowed to
  `(command, output)`; the caller now folds the acceptable command's TEXT
  into `output` for the declaration-level cannot-discriminate case (no
  subprocess ran, so there is nothing to attach a second evidence item
  to), and appends a genuine second `{command, output}` evidence item (the
  acceptable-input command IS non-empty and WAS attempted in this branch)
  for the failed-second-invocation case, rather than smuggling it through
  a non-schema key.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03)
- 2026-09-25 21:20 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02,
  GE-120f-1-i, pr-reviewer H-1 finding fb_2026-09-25_79587943]: Added
  `no_entry_disposition()`. WITHDRAWN: `check_negative_control_liveness.py`'s
  `_classify_demonstration()` used to default a hook with no declared
  `entry` to `DEMONSTRATION_ENTRY_POINT` -- a hook with no registered entry
  point was silently certified as a genuine entry-point demonstration with
  no ground truth to support that claim (the exact fail-open shape this AC
  exists to forbid). `_examine()` now checks `entry` BEFORE calling
  `_classify_demonstration()` at all (before either subprocess runs) and
  routes a missing `entry` through this new function instead: forced
  `blocked`/`demonstration=n/a`, schema-valid single-evidence-item via the
  existing `blocked_pair_currently()`. `discrimination` for this case reuses
  `DISCRIMINATION_CANNOT` when the pair is ALSO non-discriminating on its
  own declaration (still a true, more informative reading, decided from
  `pair_disposition()` alone -- no subprocess needed), else `DISCRIMINATION_NA`
  (a pair that would genuinely discriminate cannot be credited for that when
  there is nothing to demonstrate it through). Added to this module rather
  than inline in `check_negative_control_liveness.py`: that file was at
  391/400 counted lines, no headroom for the full fix in place; this module
  was at 86/400, per the same file-size-driven split rationale as the rest
  of this module's own DECISION HISTORY. `_classify_demonstration()`'s own
  fail-open special case is removed entirely (see that module's own DECISION
  HISTORY entry) -- an empty `entry` reaching that function now (defense in
  depth only; the caller never calls it that way) classifies
  `reach_inside`, never `entry_point`.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02)
====================================================================
"""

from __future__ import annotations

import logging
import os
import shlex
from datetime import date

logger = logging.getLogger(__name__)

#: The three wordings this AC's pairing logic produces, living OUTSIDE the
#: schema-shaped `currently` block, next to GE-120f-1-i's `demonstration`
#: field (architect-review's amendment, fb_2026-09-25_83f0382e) -- never a
#: new `currently.state` value. "n/a" covers every state this pairing
#: logic does not classify: the existing "declared rejection not observed"
#: `failing` case, a `blocked` reason that is not a non-discriminating
#: pair, and a genuinely-discriminating pair observed only reach-inside.
DISCRIMINATION_DISCRIMINATES = "discriminates"
DISCRIMINATION_REFUSES_WITHOUT = "refuses_without_discriminating"
DISCRIMINATION_CANNOT = "pair_cannot_discriminate"
DISCRIMINATION_NA = "n/a"

#: `pair_disposition()`'s own two-value result -- never a `currently.state`
#: or `discrimination` value itself; the caller maps
#: `DISPOSITION_CANNOT_DISCRIMINATE` onto `STATE_BLOCKED` /
#: `DISCRIMINATION_CANNOT` together, UNCONDITIONALLY -- a missing
#: acceptable `command` is exactly as much a non-discriminating pair as an
#: identical or unparsable one (coordinator ruling, superseding this
#: module's earlier three-way DISPOSITION_MISSING carve-out: see this
#: file's DECISION HISTORY).
DISPOSITION_OK = "ok"
DISPOSITION_CANNOT_DISCRIMINATE = "cannot_discriminate"

#: The schema's own three `currently.state` literals this module produces
#: -- reused verbatim (mirrors check_negative_control_liveness.py's own
#: STATE_PASSING/STATE_FAILING/STATE_BLOCKED; duplicated here only because
#: this module must not import that one, to avoid a circular import --
#: these are fixed schema literals, not a second vocabulary that could
#: drift from them).
_STATE_PASSING = "passing"
_STATE_FAILING = "failing"
_STATE_BLOCKED = "blocked"


def pair_disposition(bad_tokens: list[str], accept_command: str) -> tuple[str, list[str] | None]:
    """Declaration-level pairing check, run BEFORE either subprocess.

    Args:
        bad_tokens: The already-tokenized `negative_control.command` argv.
        accept_command: The hook's declared acceptable-input `command`
            (may be missing or empty -- a hook that never declares one is
            exactly as non-discriminating as one that declares a broken
            pair; see this module's DECISION HISTORY for why a hook with
            no acceptable-input `command` at all is NOT exempted).

    Returns:
        `(DISPOSITION_OK, accept_tokens)` when the pair is safe to run, or
        `(DISPOSITION_CANNOT_DISCRIMINATE, None)` when `accept_command` is
        missing/empty, fails to tokenize, or tokenizes to the SAME argv as
        the declared bad input -- "differ in no way the check can act on"
        read mechanically, since the check's only channel onto the
        declared input is the argv it receives. This is a FINDING, never a
        malformed-input error: the caller must still report this hook and
        continue examining the remaining hooks, never abort the sweep.
    """
    if not accept_command:
        return DISPOSITION_CANNOT_DISCRIMINATE, None
    try:
        accept_tokens = shlex.split(accept_command, posix=(os.name != "nt"))
    except ValueError as exc:
        logger.warning("Could not tokenize acceptable-input command %r: %s", accept_command, exc)
        return DISPOSITION_CANNOT_DISCRIMINATE, None
    if not accept_tokens or accept_tokens == bad_tokens:
        return DISPOSITION_CANNOT_DISCRIMINATE, None
    return DISPOSITION_OK, accept_tokens


def classify_pair(
    *, bad_rejected: bool, accept_accepted: bool, demonstration_is_entry_point: bool,
) -> tuple[str, str]:
    """Compose both invocations' own outcomes into (state, discrimination).

    Pure composition of three already-known booleans -- no I/O, no
    try/except (Rule 4). Mapping per architect-review's amendment table
    (fb_2026-09-25_83f0382e).

    Args:
        bad_rejected: Whether the bad-input subprocess exited non-zero.
        accept_accepted: Whether the acceptable-input subprocess exited
            zero -- the schema's only documented `pass_criteria` reading
            today ("zero exit"), the direct symmetric counterpart of the
            negative side's own hardcoded "non-zero exit" reading.
        demonstration_is_entry_point: Whether GE-120f-1-i's own
            `demonstration` classified the bad-input invocation as
            `entry_point` (never `reach_inside`).

    Returns:
        A `(state, discrimination)` pair. `state` is one of the existing
        4-value enum's `"passing"`/`"failing"` literals only -- this
        function never produces `"blocked"`/`"unverified"`; those are the
        caller's own transport-failure / declaration-level outcomes.
    """
    if not bad_rejected:
        # The declared rejection was not observed at all -- the existing
        # wording, unaffected by the acceptable side's own outcome (AC-5).
        return _STATE_FAILING, DISCRIMINATION_NA
    if not accept_accepted:
        # Both declared inputs were rejected -- refuses without
        # discriminating: a refusal that never stops firing (AC-3).
        return _STATE_FAILING, DISCRIMINATION_REFUSES_WITHOUT
    if not demonstration_is_entry_point:
        # Genuinely discriminates, but the bad-input rejection was not
        # observed through the real entry point -- GE-120f-1-i's own
        # reach-inside finding governs; this AC makes no claim.
        return _STATE_FAILING, DISCRIMINATION_NA
    return _STATE_PASSING, DISCRIMINATION_DISCRIMINATES


def blocked_pair_currently(command: str, output: str) -> dict:
    """Build a `blocked` `currently` block with exactly ONE schema-valid
    evidence item, `{command, output}` -- never a fourth key.
    `config/verification_flow.schema.json`'s own `$defs/currently.evidence`
    items are `additionalProperties: false` with only
    `command`/`output`/`exit_code` allowed; `currently` stays exactly
    schema-shaped per the binding design (fb_2026-09-25_83f0382e). The
    caller appends a second evidence item (or an `exit_code` onto this
    one) when it has one to add -- this helper never invents a fourth key
    to smuggle extra context through."""
    return {
        "state": _STATE_BLOCKED,
        "observed": date.today().isoformat(),
        "evidence": [{"command": command, "output": output}],
    }


def no_entry_disposition(bad_tokens: list[str], accept_command: str, command: str) -> tuple[dict, str]:
    """Build the `blocked` `currently` block and `discrimination` for a hook
    that declares a `negative_control` but no registered `entry` at all --
    pr-reviewer H-1 (fb_2026-09-25_79587943, GE-120f-1-i). No independent
    ground truth exists to compare the performed invocation against, so
    this hook can never be classified a demonstration. Decided from the
    declaration alone, before either subprocess runs.

    Args:
        bad_tokens: The already-tokenized `negative_control.command` argv --
            used only to evaluate the pair's OWN declaration-level
            disposition via `pair_disposition()`; no subprocess is run here.
        accept_command: The hook's declared acceptable-input `command`.
        command: The raw `negative_control.command` string, for evidence.

    Returns:
        `(currently, discrimination)`. `currently` is a schema-valid
        `blocked` block naming the missing entry point as the reason.
        `discrimination` is `DISCRIMINATION_CANNOT` when the pair is ALSO
        non-discriminating on its own declaration (still true regardless of
        the missing `entry`), else `DISCRIMINATION_NA` -- a pair that would
        genuinely discriminate cannot be credited for that when there is
        nothing to demonstrate it through.
    """
    disposition, _ = pair_disposition(bad_tokens, accept_command)
    discrimination = DISCRIMINATION_CANNOT if disposition == DISPOSITION_CANNOT_DISCRIMINATE else DISCRIMINATION_NA
    currently = blocked_pair_currently(
        command, "no registered entry point to demonstrate through -- hook declares no `entry`",
    )
    return currently, discrimination
