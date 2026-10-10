"""
MODULE: check_negative_control_liveness
GOAL: Negative-control liveness sweep. For each examined hooks_manifest entry
    that declares a `negative_control`, actually run its declared `command` as
    a real subprocess, decide whether the declared rejection was observed from
    the subprocess's own exit code, and write that observation back into
    `negative_control.currently` in the SAME manifest file, at the SAME path —
    never inferred from the declaration itself. GE-120f-1-i extends this: the
    observation must also be classified as a genuine `demonstration` through
    the entry point the protected surface invokes (`hook["entry"]`, ground
    truth) or a `reach_inside` refusal obtained some other way — a rejection
    reachable only by reaching inside the check is not evidence the check
    itself refuses anything in service.
BUSINESS CONTEXT: GE-120f-1. A check's declared known-bad input and expected
    rejection (config/verification_flow.schema.json $defs/negative_control) is
    worthless as evidence unless something actually puts that input through the
    check's real entry point and records what happened. Before this module, no
    hooks_manifest entry's negative control was ever exercised: a declaration
    could be well-formed and still describe a guard that had quietly stopped
    refusing anything (KI-CG-021's shape — templates/hooks/readme_read_guard.py
    is the worked example this AC's own doc_links cite). This sweep closes that
    gap by producing the `currently` record from OBSERVATION, never from the
    declaration: a check whose declared input was not put through it this run
    carries `unverified` — the schema's own honest placeholder — however
    complete its declaration is. GE-120f-1-i: the cheapest way to satisfy the
    parent AC is to import the check and call the part of it that decides,
    rather than invoke its entry point — that would certify as demonstrated
    precisely the guard whose deciding part is correct and whose service path
    never reaches it (readme_read_guard's own shape). `demonstration` names
    that class so it is never folded into "rejection observed".
ARCHITECTURE: A single-file CLI, deployed verbatim by build_commit_guardian()
    (it lives inside templates/scripts/commit_guardian/, so it ships with the
    rest of that tree and needs no scripts/build_phases.py deploy-map entry —
    see this ticket's own HOST AND DEPLOYMENT constraint). Two entry points:
    `--selftest` (proves the deployed module and everything it imports load in
    a cold process, touching nothing) and `--manifest PATH [--check-id ID ...]`
    (the real sweep). Named `check_negative_control_liveness.py` deliberately:
    the `check_*.py` prefix pulls it into check_hook_parity.py's
    hook_script_patterns census (BP-1600a-2), which is why it also carries a
    real `hooks_manifest` entry below in commit_guardian.json — a runner
    nothing calls is inert (KI-CG-021) — registered `always_run: true` and
    `pass_filenames: false` because it reads the whole manifest's declared
    population, never the staged-file list, mirroring `check-build-drift`'s
    own rationale in this same manifest.

DECISION HISTORY
====================================================================
- 2026-09-25 09:15 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/01,
  GE-120f-1]: Initial implementation. Reads a commit_guardian.json-shaped
  manifest, tokenizes each examined hook's declared `negative_control.command`
  with `shlex.split(command, posix=(os.name != "nt"))` (Windows-safe per
  test-writer's own CLI contract note), runs it as a real subprocess, and
  decides `passing` (rejection observed, non-zero exit) vs `failing` (rejection
  not observed, zero exit) vs `blocked` (could not be run to a verdict at all —
  no declared command, a tokenization error, or a subprocess/timeout failure).
  A hook excluded from this run via `--check-id` that has no pre-existing
  `currently` block gets `unverified`; one that already has a `currently`
  block is left byte-identical, since this run made no attempt on it. Every
  hook carrying a `negative_control` (examined or not) gets exactly one
  `NEGATIVE_CONTROL_RESULT` stdout line. Exit code is 0 iff every EXAMINED
  hook ended `passing`. (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/01)
- 2026-09-25 17:15 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02,
  GE-120f-1-i]: Added the `demonstration` classification per
  architect-review's binding design (fb_2026-09-25_7560dc1f, Q1/Q2). Ground
  truth for "the entry point the protected surface invokes" is `hook["entry"]`
  (never `hook["entry_point"]`, human prose on the real registration surface
  today). The performed invocation is the literal `tokens` list
  `_run_negative_control_command` runs — never `negative_control.command` as
  text, never a declaration echoed back. `_target_identity()` resolves both
  sides to a single space-free script-stem token, tolerant of the
  `run_hook.py <target> ...` wrapper shape (a process-hop count is explicitly
  NOT the rule — see `_classify_demonstration()`'s own docstring). `state` is
  `passing` only when `demonstration == "entry_point"` AND the subprocess
  exited non-zero; a reach-inside command that itself exits non-zero still
  records `failing`. `demonstration` lives OUTSIDE the schema-shaped
  `currently` block (config/verification_flow.schema.json's `currently` is
  `additionalProperties: false` with a fixed 4-value `state` enum) — it is an
  added key on the existing per-check record and on the
  `NEGATIVE_CONTROL_RESULT` stdout line only, inserted before `command=`. A
  hook that declares no `entry` field at all (a registration surface that
  predates this AC) has no independent ground truth to compare against, so it
  classifies as `entry_point` by default rather than silently downgrading
  every such check to `reach_inside` — this preserves GE-120f-1's own already
  -signed-off fixture surface (`_ge_120f_1_fixtures.fixture_hook()`, which
  declares only `entry_point`, never `entry`) unchanged.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02)
- 2026-09-25 18:10 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii]: Added the acceptable-input pairing per architect-review's
  binding design (fb_2026-09-25_33c1543f, AMENDED by fb_2026-09-25_83f0382e
  -- the amendment supersedes the first note's currently.state vocabulary
  answer; currently.state stays exactly the existing 4-value enum). A hook
  entry may now carry command + pass_criteria as NEW top-level keys,
  SIBLINGS of negative_control (never nested inside it, never a second
  declaration store) -- the acceptable input this AC requires. Declaration
  -level pairing is checked BEFORE either subprocess runs (never an
  outcome-level finding): a missing/empty acceptable command, or one that
  tokenizes (via the SAME _tokenize() GE-120f-1-i already established) to
  the identical argv as negative_control.command, is pair_cannot_discriminate
  -- reported as blocked, and the sweep CONTINUES to the remaining hooks,
  never aborting. Otherwise BOTH declared inputs are put through a real
  subprocess in the SAME run (the mandatory injection this AC's test 1
  exists to catch is stopping after the bad-input side alone). The three
  wordings live in a NEW sibling field, discrimination
  (discriminates | refuses_without_discriminating | pair_cannot_discriminate
  | n/a), living OUTSIDE currently next to -i's demonstration, never a new
  currently.state value. state is passing only when the pair discriminates
  (bad rejected, acceptable accepted) AND -i's own demonstration ==
  entry_point -- both conditions, same record. The declaration-level
  pairing check and the (state, discrimination) mapping live in the new
  sibling module _negative_control_pairing.py (this file was at 351/400
  counted lines before this change, per GE-120f-1-i's own headroom note
  leaving too little room for the full pairing logic in place; the split
  keeps this file under the 400-line limit without splitting any
  function's behaviour across files). RESULT line field order:
  "... entry_point=<e> demonstration=<d> discrimination=<x> command=<c>"
  -- discrimination= immediately after demonstration=, both before the
  pre-existing greedy command= group. The `import _negative_control_pairing`
  sibling import is preceded by a `sys.path` bootstrap (this file's own
  directory, inserted if absent) -- the same fix check_identifier_uniqueness.py
  already established: GE-120c-1's harness invokes this script with `-I`,
  which does NOT add the script's own directory to sys.path the way an
  ordinary invocation does, so an unguarded sibling import would raise
  ModuleNotFoundError under that harness even though the module IS deployed
  alongside it.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03)
- 2026-09-25 19:05 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii, coordinator rework]: Between the 18:10 entry above and this
  one, `_examine()` briefly carried an UNDOCUMENTED narrowing
  (fb_2026-09-25_946dd180): a hook with NO acceptable-input `command` at
  all kept its old single-sided passing/failing verdict instead of the
  18:10 entry's own stated unconditional rule, to avoid regressing
  pre-existing GE-120f-1/-i fixtures that predated this AC's two new
  sibling keys. The coordinator rejected this: THE LITERAL RULE IS
  UNCONDITIONAL, exactly as the 18:10 entry above already said -- a
  missing acceptable `command` is pair_cannot_discriminate/blocked, no
  exception for "never declared one." A guard widened to refuse
  everything must not be able to reach `passing` merely by omitting the
  acceptable-input declaration; that is the exact escape this AC exists
  to close. The regressions were fixed at the FIXTURE layer instead
  (test-writer rework fb_2026-09-25_d9d65758: every pre-existing fixture
  hook in `_ge_120f_1_fixtures.py` / `_ge_120f_1_i_fixtures.py` /
  `test_ge_120f_1_i.py` now declares a real, discriminating acceptable
  input, with zero assertion changes). `_examine()` is restored to match
  the 18:10 entry's own description; `_negative_control_pairing.pair_disposition()`
  is back to its original two-value contract with no missing-command
  carve-out (see that module's own DECISION HISTORY for the mirrored
  entry).
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03)
- 2026-09-25 19:35 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii, pr-reviewer medium finding fb_2026-09-25_bb6a7c1d]: Both
  `_examine()` call sites of `ncp.blocked_pair_currently()` updated for
  that function's narrowed `(command, output)` signature (see
  `_negative_control_pairing.py`'s own DECISION HISTORY for the full
  reasoning) -- `currently.evidence` items stay exactly schema-shaped
  (`command`/`output`/`exit_code` only), never a fourth
  `acceptable_command` key. The declaration-level cannot-discriminate case
  folds the acceptable command's text into `output`; the failed-second
  -invocation case appends a genuine second `{command, output}` evidence
  item for the acceptable-input attempt instead.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03)
- 2026-09-25 21:20 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02,
  GE-120f-1-i, pr-reviewer H-1 finding fb_2026-09-25_79587943]: WITHDRAWN
  the fail-open default this file's 17:15 entry above introduced:
  `_classify_demonstration()` used to return `DEMONSTRATION_ENTRY_POINT`
  when a hook declared no `entry` at all -- silently certifying a genuine
  entry-point demonstration with no ground truth to support that claim,
  the exact shape this AC's own error-handling policy forbids ("A failed
  invocation is `blocked`, never a silent absence and never a `passing`").
  `_examine()` now checks `entry` immediately after computing
  `stated_entry_point` and BEFORE calling `_classify_demonstration()` at
  all (before either subprocess runs): a missing `entry` routes through the
  new `_negative_control_pairing.no_entry_disposition()` instead, forcing
  `blocked`/`demonstration="n/a"` with a schema-valid single-evidence-item
  naming the missing entry point as the reason, and a `discrimination` of
  `pair_cannot_discriminate` when the pair is ALSO non-discriminating on
  its own declaration (decided from the declaration alone, no subprocess),
  else `n/a`. Added to `_negative_control_pairing.py` rather than inline
  here: this file was at 391/400 counted lines, no headroom for the fix in
  place; that module had 314 lines of headroom (see its own DECISION
  HISTORY for the mirrored entry). `_classify_demonstration()`'s own
  special case for an empty `entry` is removed entirely -- the caller now
  never calls it that way; an empty `entry` reaching it regardless (defense
  in depth only) classifies `reach_inside`, never `entry_point`.
  `unit_tests/portability/_ge_120f_1_fixtures.py::fixture_hook()` and every
  `_ge_120f_1_i_fixtures.py`/`_ge_120f_1_ii_fixtures.py` hook builder
  already declare a real `entry` (test-writer's rework, fb_2026-09-25_fa2f39dc)
  -- no fixture regressed.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02)
- 2026-09-25 21:45 [python-coder/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02,
  GE-120f-1-i, check-secrets false positive]: Renamed `_NO_IDENTITY_TOKEN`
  to `_NO_IDENTITY` (value/behaviour unchanged) -- check-secrets' GENERIC_SECRET
  heuristic flagged the `*TOKEN* = "<string literal>"` shape as a possible
  credential and blocked the family commit; no `.security-allowlist` entry
  was added since the fix is a plain rename.
  (#EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02)
- 2026-10-07 [python-coder, GE-120g-4]: `main()` called `_write_manifest`
  unconditionally on every run, and `_write_manifest`'s `json.dumps(data,
  indent=2)` left `ensure_ascii` at its default True -- a run that changed
  nothing still rewrote the manifest it was handed, and any write escaped
  every non-ASCII character in the document's prose (measured: 0 -> 110
  escaped em-dashes from a single invocation against a repaired deployed
  config, tripping the next commit's check-output-drift). Fixed both halves,
  neither alone: (1) `main()` now takes a `copy.deepcopy` snapshot of `data`
  BEFORE calling `_build_records` (which mutates `data` in place) and calls
  `_write_manifest` only when the mutated document differs from that
  snapshot -- a guard on the rendered TEXT would always be true, since this
  file's hand-authored indentation never round-trips through `json.dumps`
  byte-for-byte even with `ensure_ascii` fixed, so the guard compares the
  parsed DATA instead; (2) `_write_manifest`'s `json.dumps` call now passes
  `ensure_ascii=False`, so a genuine write preserves prose it was not asked
  to change. The verdict path (`_build_records`'s records, `_format_result_
  line`'s lines, `_exit_code_for`'s exit code) is untouched; the existing
  OSError log-and-raise on the write path is untouched.
  (#GE-120g-4)
====================================================================
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import re
import shlex
import subprocess
import sys
from datetime import date
from pathlib import Path

# `-I` (GE-120c-1's harness) does not add this script's own directory to
# sys.path -- bootstrap it first (see DECISION HISTORY; same pattern as
# check_identifier_uniqueness.py).
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import _negative_control_pairing as ncp  # noqa: E402

logger = logging.getLogger(__name__)

#: Printed by --selftest so a cold-process import/load check can prove this
#: deployed module and everything it imports loaded successfully, without
#: needing a real manifest or running any real check.
SELFTEST_MARKER = "NEGATIVE_CONTROL_LIVENESS_SELFTEST_OK"

#: Prefix for the one stdout line this sweep emits per examined-or-not hook
#: that carries a `negative_control` key.
_RESULT_LINE_PREFIX = "NEGATIVE_CONTROL_RESULT"

#: The schema's own four state values (config/verification_flow.schema.json
#: $defs/currently) — reused verbatim, never a synonym.
STATE_PASSING = "passing"
STATE_FAILING = "failing"
STATE_BLOCKED = "blocked"
STATE_UNVERIFIED = "unverified"

#: GE-120f-1-i's own field (NOT a schema `currently.state` value — see the
#: module docstring's DECISION HISTORY, architect-review Q2). Classifies the
#: invocation `_run_negative_control_command` actually performed against the
#: hook's own declared `entry` (ground truth). "n/a" is reserved for
#: `blocked`/`unverified` records — no completed invocation exists there to
#: classify.
DEMONSTRATION_ENTRY_POINT = "entry_point"
DEMONSTRATION_REACH_INSIDE = "reach_inside"
DEMONSTRATION_NA = "n/a"

#: Placeholder for the `NEGATIVE_CONTROL_RESULT` line's `entry_point=` token
#: when no invocation identity could be resolved (e.g. no command declared).
#: Never blank — the field is `\S+`-shaped in every real report line. Named
#: without "TOKEN" deliberately: check-secrets' GENERIC_SECRET heuristic
#: flags any `*TOKEN* = "<string literal>"` assignment as a possible
#: credential -- this is a display placeholder, not a secret.
_NO_IDENTITY = "(unavailable)"

#: A hook's `entry`/performed-command token names the run_hook.py dispatch
#: wrapper itself, not the real target — `_target_identity()` skips past it.
_RUN_HOOK_WRAPPER_STEM = "run_hook"

#: Matches a Python interpreter token's own basename (tolerant of a Windows
#: `.exe` suffix, already stripped by `Path.stem`): `python`, `python3`,
#: `python3.11`, etc.
_INTERPRETER_RE = re.compile(r"^python\d*(\.\d+)?$", re.IGNORECASE)

_SUBPROCESS_TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse this runner's CLI contract.

    Args:
        argv: Argument vector (excluding the program name), or None to read
            from `sys.argv[1:]` (argparse's own default).

    Returns:
        The parsed namespace with `manifest`, `check_id`, and `selftest`.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Put each declared negative_control.command through a real "
            "subprocess and write the observed result back into the manifest."
        ),
    )
    parser.add_argument("--manifest", default=None, help="Path to a commit_guardian.json-shaped manifest.")
    parser.add_argument(
        "--check-id", action="append", dest="check_id", default=None,
        help="Repeatable. Examine only these hook ids this run.",
    )
    parser.add_argument(
        "--selftest", action="store_true",
        help="Print the cold-load marker and exit 0 without touching any file.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Manifest I/O (external I/O — wrapped per the repo's error-handling policy)
# ---------------------------------------------------------------------------
def _load_manifest(manifest_path: Path) -> dict:
    """Read and parse a commit_guardian.json-shaped manifest file.

    Args:
        manifest_path: Path to the manifest to read.

    Returns:
        The parsed manifest document.

    Raises:
        OSError: The file could not be read.
        json.JSONDecodeError: The file's contents are not valid JSON.
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read manifest %s: %s", manifest_path, exc)
        raise
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse manifest %s as JSON: %s", manifest_path, exc)
        raise


def _write_manifest(manifest_path: Path, data: dict) -> None:
    """Write `data` back to `manifest_path` — the SAME file, same path.

    Args:
        manifest_path: Path the sweep loaded the manifest from.
        data: The manifest document, with `currently` blocks updated in place.

    Raises:
        OSError: The file could not be written.
    """
    try:
        manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write manifest %s: %s", manifest_path, exc)
        raise


# ---------------------------------------------------------------------------
# Tokenization and identity resolution — GROUND TRUTH is `hook["entry"]`; the
# PERFORMED invocation is the tokens list actually passed to subprocess.run,
# never `negative_control.command` as text and never a declared field echoed
# back (architect-review Q1, fb_2026-09-25_7560dc1f).
# ---------------------------------------------------------------------------
def _tokenize(text: str, *, label: str) -> list[str] | None:
    """Tokenize `text` the same Windows-safe way it will be (or was) invoked.

    Args:
        text: A `negative_control.command` value or a hook's own declared
            `entry` value.
        label: Human-readable label for the warning message on failure.

    Returns:
        The token list, or None when tokenization failed or produced an
        empty argv.
    """
    try:
        tokens = shlex.split(text, posix=(os.name != "nt"))
    except ValueError as exc:
        logger.warning("Could not tokenize %s %r: %s", label, text, exc)
        return None
    return tokens or None


def _looks_like_interpreter(token: str) -> bool:
    """True when `token`'s own basename names a Python interpreter."""
    return bool(_INTERPRETER_RE.fullmatch(Path(token).stem))


def _target_identity(tokens: list[str]) -> str:
    """Resolve the single space-free identity token for the script `tokens`
    actually invokes.

    Skips the interpreter token and the `run_hook.py <target> ...` wrapper
    token when present — tolerant of that real deployed wrapper shape, never
    a process-boundary rule (architect-review's own "PROCESS BOUNDARY IS A
    SMELL, NOT THE CRITERION" constraint): an extra hop through the
    recognised wrapper must not defeat identity matching against the SAME
    target script, and a single-hop command targeting a DIFFERENT script
    must not be mistaken for a match merely because it took one hop.

    Args:
        tokens: The literal argv `_run_negative_control_command` runs (or,
            for the hook's own declared `entry`, that string tokenized the
            same way).

    Returns:
        The target script's filename stem, or "" when no candidate token
        exists.
    """
    remaining = [token for token in tokens if token]
    if remaining and _looks_like_interpreter(remaining[0]):
        remaining = remaining[1:]
    if remaining and Path(remaining[0]).stem.lower() == _RUN_HOOK_WRAPPER_STEM:
        remaining = remaining[1:]
    if remaining:
        return Path(remaining[0]).stem
    return ""


def _classify_demonstration(entry: str, performed_tokens: list[str]) -> str:
    """Classify `performed_tokens` against the hook's own declared `entry`.

    Args:
        entry: The hook's declared `entry` field — the real production way
            in the protected surface invokes (never `entry_point`, human
            prose on today's real registration surface). The caller
            (`_examine()`) never calls this with an empty `entry` — a hook
            declaring no `entry` at all has no independent ground truth and
            is forced `blocked`/`n/a` before this function is ever reached
            (pr-reviewer H-1, fb_2026-09-25_79587943; see the module
            docstring's DECISION HISTORY for the withdrawn fail-open
            default this replaced).
        performed_tokens: The literal argv actually passed to
            `subprocess.run` for this check's `negative_control.command`.

    Returns:
        `DEMONSTRATION_ENTRY_POINT` when the performed invocation's target
        script identity matches the entry's, `DEMONSTRATION_REACH_INSIDE`
        otherwise (including an empty `entry`, as defense in depth) — the
        observable is WHICH script was actually invoked, never how many
        process hops it took to get there.
    """
    entry_identity = _target_identity(_tokenize(entry, label="hook entry") or [])
    performed_identity = _target_identity(performed_tokens)
    if entry_identity and entry_identity == performed_identity:
        return DEMONSTRATION_ENTRY_POINT
    return DEMONSTRATION_REACH_INSIDE


# ---------------------------------------------------------------------------
# Subprocess execution (external I/O — wrapped)
# ---------------------------------------------------------------------------
def _run_negative_control_command(tokens: list[str]) -> tuple[str, int | None]:
    """Run `tokens` as a real subprocess.

    Never reads or parses the declared command as text to infer a verdict —
    the verdict comes only from the subprocess's own exit code, decided by
    the caller. `tokens` IS the performed invocation: the same list is also
    the ground truth for this check's stated entry point and `demonstration`
    classification (architect-review Q1) — never re-derived elsewhere.

    Args:
        tokens: The already-tokenized argv to run.

    Returns:
        A `(combined_output, exit_code)` pair. `exit_code` is None when the
        command could not be run to a verdict at all (timeout, or the
        interpreter could not be launched) — the caller reads that as
        `blocked`.
    """
    try:
        proc = subprocess.run(
            tokens, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("negative_control command %r could not be run to a verdict: %s", tokens, exc)
        return f"could not run to a verdict: {exc}", None
    return (proc.stdout or "") + (proc.stderr or ""), proc.returncode


# ---------------------------------------------------------------------------
# `currently` record construction — OBSERVATION ONLY, never the declaration.
# `_blocked()`/`_unverified()` return `(currently, demonstration,
# stated_entry_point)`; `_examine()` returns that SAME triple plus a
# `discrimination` (GE-120f-1-ii) as a fourth element. `currently` is the
# schema-shaped block; `demonstration` and `discrimination` are NOT part of
# the schema (architect-review Q2, amended by fb_2026-09-25_83f0382e) — the
# caller folds them into the per-check record only, never into
# `negative_control.currently`.
# ---------------------------------------------------------------------------
def _blocked(command: str, output: str) -> tuple[dict, str, str]:
    """Build a `blocked` `currently` block — no completed invocation exists
    to classify, so `demonstration` is `n/a` by definition (architect-review
    Q2)."""
    return (
        {
            "state": STATE_BLOCKED,
            "observed": date.today().isoformat(),
            "evidence": [{"command": command, "output": output}],
        },
        DEMONSTRATION_NA,
        "",
    )


def _examine(negative_control: dict, entry: str, accept_command: str) -> tuple[dict, str, str, str]:
    """Put BOTH declared inputs through a real subprocess, in the SAME run,
    and build the `currently` block plus this AC's `discrimination` from
    what was observed (architect-review's binding design,
    fb_2026-09-25_33c1543f AMENDED by fb_2026-09-25_83f0382e).

    Args:
        negative_control: The hook's `negative_control` declaration (never
            mutated here — the caller assigns the returned block onto it).
        entry: The hook's own declared `entry` field — ground truth for
            `_classify_demonstration()` (never `entry_point`).
        accept_command: The hook's own top-level `command` — the
            acceptable-input side of the pair (never a second declaration
            store; may be missing or empty).

    Returns:
        `(currently, demonstration, stated_entry_point, discrimination)`.
        `currently.state` stays within the existing 4-value enum. A hook
        declaring no `entry` at all is detected BEFORE `_classify_demonstration()`
        is ever called (and before either subprocess runs) and UNCONDITIONALLY
        forces `blocked`/`demonstration="n/a"` — no ground truth means no
        demonstration, never a default to `entry_point` (pr-reviewer H-1,
        fb_2026-09-25_79587943). A non-discriminating pair — `accept_command`
        missing/empty, or a declared `command` that tokenizes to the
        identical argv as the bad input or fails to tokenize at all — is
        likewise detected BEFORE either subprocess runs and UNCONDITIONALLY
        forces `blocked` (a hook that never declares an acceptable input is
        exactly as non-discriminating as one that declares a broken pair;
        see the module docstring's DECISION HISTORY). Neither case aborts
        the sweep — the caller continues to the remaining hooks
        unconditionally.
    """
    command = negative_control.get("command", "")
    if not command:
        currently, demonstration, stated_entry_point = _blocked(
            "(none declared)", "negative_control has no `command` to run",
        )
        return currently, demonstration, stated_entry_point, ncp.DISCRIMINATION_NA

    bad_tokens = _tokenize(command, label="negative_control command")
    if bad_tokens is None:
        currently, demonstration, stated_entry_point = _blocked(command, "could not tokenize command")
        return currently, demonstration, stated_entry_point, ncp.DISCRIMINATION_NA

    stated_entry_point = _target_identity(bad_tokens)

    if not entry:
        # pr-reviewer H-1 (fb_2026-09-25_79587943): no registered entry
        # point means no ground truth to demonstrate through -- decided
        # before either subprocess runs, never defaulted to entry_point.
        currently, discrimination = ncp.no_entry_disposition(bad_tokens, accept_command, command)
        return currently, DEMONSTRATION_NA, stated_entry_point, discrimination

    demonstration = _classify_demonstration(entry, bad_tokens)

    disposition, accept_tokens = ncp.pair_disposition(bad_tokens, accept_command)
    if disposition == ncp.DISPOSITION_CANNOT_DISCRIMINATE:
        currently = ncp.blocked_pair_currently(
            command,
            "the declared acceptable input does not discriminate from the "
            f"declared bad input (acceptable command: {accept_command or '(none declared)'}) "
            "-- no subprocess run for either side this examination",
        )
        return currently, DEMONSTRATION_NA, stated_entry_point, ncp.DISCRIMINATION_CANNOT

    bad_output, bad_exit = _run_negative_control_command(bad_tokens)
    if bad_exit is None:
        currently, _, _ = _blocked(command, bad_output)
        return currently, DEMONSTRATION_NA, stated_entry_point, ncp.DISCRIMINATION_NA

    accept_output, accept_exit = _run_negative_control_command(accept_tokens)
    if accept_exit is None:
        currently = ncp.blocked_pair_currently(command, bad_output)
        currently["evidence"][0]["exit_code"] = bad_exit
        currently["evidence"].append({"command": accept_command, "output": accept_output})
        return currently, demonstration, stated_entry_point, ncp.DISCRIMINATION_NA

    state, discrimination = ncp.classify_pair(
        bad_rejected=bad_exit != 0,
        accept_accepted=accept_exit == 0,
        demonstration_is_entry_point=demonstration == DEMONSTRATION_ENTRY_POINT,
    )
    currently = {
        "state": state,
        "observed": date.today().isoformat(),
        "evidence": [
            {"command": command, "output": bad_output, "exit_code": bad_exit},
            {"command": accept_command, "output": accept_output, "exit_code": accept_exit},
        ],
    }
    return currently, demonstration, stated_entry_point, discrimination


def _unverified(command: str) -> tuple[dict, str, str]:
    """Build the honest `currently` placeholder for an attempt never made.

    Args:
        command: The declared (but not run) `negative_control.command`, for
            evidence purposes only — never executed here.

    Returns:
        `(currently, demonstration, stated_entry_point)` with
        `state: "unverified"` and `demonstration: "n/a"` — no invocation was
        performed this run to classify.
    """
    currently = {
        "state": STATE_UNVERIFIED,
        "observed": date.today().isoformat(),
        "evidence": [
            {
                "command": command or "(no command declared)",
                "output": "not examined this run -- the attempt has never been made",
            },
        ],
    }
    return currently, DEMONSTRATION_NA, ""


def _fallback_identity(entry: str) -> str:
    """Best-effort identity for a record no invocation was performed for
    this run (excluded via `--check-id` with a pre-existing `currently`) —
    informational only: `demonstration` is `"n/a"` for these records and
    makes no claim about a performed invocation."""
    return _target_identity(_tokenize(entry, label="hook entry") or [])


# ---------------------------------------------------------------------------
# Sweep over a manifest's hooks_manifest.hooks[]
# ---------------------------------------------------------------------------
def _hook_id(hook: dict) -> str | None:
    """Return `hook["id"]` when it is a usable, non-blank string, else None."""
    raw_id = hook.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        return raw_id
    return None


def _build_records(hooks: list[dict], check_ids: list[str] | None) -> list[dict]:
    """Sweep every hook carrying a falsifiable `negative_control`, mutating
    each one's `currently` block in place, and return one record per hook.

    Args:
        hooks: `hooks_manifest.hooks` from the loaded manifest (mutated).
        check_ids: `--check-id` values, or None to examine every hook that
            carries a `negative_control`.

    Returns:
        One record per hook carrying a falsifiable `negative_control`:
        `{check_id, state, entry_point, demonstration, discrimination,
        command, examined}`. `entry_point` is the identity of the
        invocation ACTUALLY PERFORMED this run, never the hook's declared
        `entry_point`/`entry` field. `discrimination` (GE-120f-1-ii) is
        `"n/a"` for every record this AC's pairing logic does not classify.
    """
    examine_only = set(check_ids) if check_ids else None
    records: list[dict] = []
    for hook in hooks:
        negative_control = hook.get("negative_control")
        if not isinstance(negative_control, dict) or negative_control.get("not_applicable"):
            continue
        hook_id = _hook_id(hook)
        if hook_id is None:
            continue

        entry = hook.get("entry", "")
        accept_command = hook.get("command", "")
        examined = examine_only is None or hook_id in examine_only
        if examined:
            currently, demonstration, stated_entry_point, discrimination = _examine(
                negative_control, entry, accept_command,
            )
            negative_control["currently"] = currently
        elif "currently" not in negative_control:
            currently, demonstration, stated_entry_point = _unverified(negative_control.get("command", ""))
            negative_control["currently"] = currently
            discrimination = ncp.DISCRIMINATION_NA
        else:
            # Excluded this run AND already has a record -- left untouched,
            # no invocation performed.
            demonstration = DEMONSTRATION_NA
            stated_entry_point = _fallback_identity(entry)
            discrimination = ncp.DISCRIMINATION_NA

        records.append({
            "check_id": hook_id,
            "state": negative_control["currently"]["state"],
            "entry_point": stated_entry_point,
            "demonstration": demonstration,
            "discrimination": discrimination,
            "command": negative_control.get("command", ""),
            "examined": examined,
        })
    return records


def _format_result_line(record: dict) -> str:
    """Render one record as its `NEGATIVE_CONTROL_RESULT` stdout line.

    `entry_point=` states the invocation actually performed (never a
    declaration); `demonstration=` (GE-120f-1-i) and `discrimination=`
    (GE-120f-1-ii) are inserted, in that order, before `command=` per
    architect-review Q3 / fb_2026-09-25_83f0382e (never corrupting the
    pre-existing greedy `command` group). No token may be blank —
    `_NO_IDENTITY` covers a record with no resolvable invocation
    identity.
    """
    entry_point = record["entry_point"] or _NO_IDENTITY
    return (
        f"{_RESULT_LINE_PREFIX} check_id={record['check_id']} state={record['state']} "
        f"entry_point={entry_point} demonstration={record['demonstration']} "
        f"discrimination={record['discrimination']} command={record['command']}"
    )


def _exit_code_for(records: list[dict]) -> int:
    """0 iff every EXAMINED record ended `passing`; unexamined never blocks."""
    for record in records:
        if record["examined"] and record["state"] != STATE_PASSING:
            return 1
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """Run the negative-control liveness sweep (or `--selftest`).

    Args:
        argv: Argument vector (excluding the program name), or None to read
            `sys.argv[1:]`.

    Returns:
        0 iff every hook examined this run ended `passing` (or `--selftest`
        succeeded); non-zero otherwise.
    """
    args = _parse_args(argv)

    if args.selftest:
        print(SELFTEST_MARKER)
        return 0

    if not args.manifest:
        print("check-negative-control-liveness: --manifest is required unless --selftest", file=sys.stderr)
        return 2

    manifest_path = Path(args.manifest)
    try:
        data = _load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError):
        return 2

    hooks = data.get("hooks_manifest", {}).get("hooks")
    if not isinstance(hooks, list):
        print(
            f"check-negative-control-liveness: {manifest_path} has no hooks_manifest.hooks list",
            file=sys.stderr,
        )
        return 2

    # Snapshot the parsed document BEFORE `_build_records` mutates it in
    # place (its own docstring: "with `currently` blocks updated in place").
    # A shallow copy would not isolate this snapshot -- `hooks` is a nested
    # list of dicts that `_build_records` mutates by reference. Only a run
    # that actually changed something may write: the rendered JSON never
    # reproduces this file's own hand-authored indentation byte-for-byte
    # (see the module docstring's GE-120g-4 DECISION HISTORY entry), so a
    # guard comparing rendered text against current text would always be
    # true and write on every run. Comparing the parsed DATA instead of the
    # rendered text is the only guard that is ever false.
    before_sweep = copy.deepcopy(data)
    records = _build_records(hooks, args.check_id)

    if data != before_sweep:
        try:
            _write_manifest(manifest_path, data)
        except OSError:
            return 2

    for record in records:
        print(_format_result_line(record))

    return _exit_code_for(records)


if __name__ == "__main__":
    sys.exit(main())
