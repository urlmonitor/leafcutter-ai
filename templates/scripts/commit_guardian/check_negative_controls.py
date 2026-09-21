"""
MODULE: check_negative_controls
GOAL: Liveness runner for GE-120f-1 / ADR-045 — establishes whether a
    registered protective check can actually refuse its own declared
    known-bad input, by putting that input through the real entry point the
    protected surface uses and writing the check's record from what was
    OBSERVED, never from what was declared.
BUSINESS CONTEXT: A check can be registered, wired, and invoked on every
    commit while being structurally unable to refuse anything — and until
    this runner existed, nothing in this repository could tell that check
    apart from one that refuses correctly
    (docs/architecture/adrs/ADR-045-observed-refusal-establishes-protection.md;
    templates/hooks/readme_read_guard.py is the worked example). This
    runner is the first code reader of config/verification_flow.schema.json
    and closes that gap by EXECUTING, never reading, each check's own
    declared negative control.
ARCHITECTURE: Deliberately named `check_*.py` (ADR-045 §4) so it enrols in
    hook_parity's own gate census rather than hiding from it, and is itself
    a real `hooks_manifest` entry invoked through `run_hook.py` — it is not
    exempt from the regime it enforces (ADR-045 §6a). Reads
    `hooks_manifest.hooks` from the DEPLOYED `commit_guardian.json` beside
    this file (never a list held inside this module, never the source-tree
    `templates/` copy — ADR-045 §§2 and 5) on every invocation, restricted
    to entries that carry a real `entry` string. For each such hook with a
    well-formed `negative_control` ({input, command, expected_result,
    currently}), executes `negative_control["command"]` as a real
    subprocess — the SAME `run_hook.py`-wrapped entry point the check's own
    `entry` field uses, with the declared known-bad input appended — and
    derives the state PURELY from what that subprocess did, never from the
    declaration itself. A disabled hook, or one with no falsifiable control
    declared at all, is recorded `unverified`: the attempt has never been
    made, however completely the declaration is written.

    NO IMPORTS BEYOND THE STANDARD LIBRARY, no sibling imports either, by
    design: `python -I <script>` (the isolation this module's own harness,
    unit_tests/portability/_deployed_check_harness.py, exercises it under)
    does not add the script's own directory to `sys.path` on Python 3.12,
    so a sibling import here would raise `ModuleNotFoundError` in exactly
    the cold-process test this module must pass
    (test_ge120f1_deployed_runner_and_every_module_it_imports_load_in_a_cold_process).
    `run_hook.py`'s own import-with-fallback pattern for `check_outcome`
    exists for the same reason; this module sidesteps the failure class
    entirely — which is also why no `scripts/build_phases.py` deploy-map
    entry is needed for it.

    THE RUNNER'S OWN NEGATIVE CONTROL (ADR-045 §6a): its declared
    known-bad input is the `--self-check-empty-population` flag, fed
    through this SAME entry point; the rejection it demonstrates is
    refusing a registration surface with zero invokable entries — ADR-045
    §7's own failure mode — rather than mutating the real manifest, since
    the runner's failure mode is about the POPULATION it sweeps, not any
    one check's behaviour. ADR-045 §6b's INDEPENDENT guard (this runner's
    existence and reachability, pinned WITHOUT routing through its own
    regime) lives in test_ge_120f_1.py's
    test_ge120f1_runner_is_registered_and_reachable_independently_of_its_own_regime,
    deliberately not here.

DECISION HISTORY:
  - 2026-09-21 [python-coder/GE-120f-1]: Initial implementation.
  - 2026-09-21 [python-coder/GE-120f-1, pr-reviewer rework]: `_observe()`'s
    launch-failure detection was a five-substring blocklist over combined
    stdout+stderr, checked only AFTER `exit_code`. `run_hook.py` -- the SAME
    dispatch wrapper every negative-control command routes through -- already
    emits a structured, parseable report for every outcome where it never
    launches the delegated check's own process at all: `RESULT: not_run
    checker=<target> reason=<reason>` via `check_outcome.emit_not_run()`.
    Two hooks_manifest entries can legitimately share a script basename
    (`run_hook.py`'s `_is_target_disabled()` matches by basename, not id), so
    disabling one silently short-circuits the other's negative control with
    `reason=disabled` and exit 0 -- a marker list with no "disabled" entry
    read that as a clean exit with no rejection, i.e. `failing`: a check that
    never launched recorded as run-and-failed, which would block every
    future commit. Added `_parse_not_run_reason()`, which parses this
    structured line explicitly and is now the PRIMARY discriminator: any
    `reason` value routes to `blocked` (ADR-045 §3: an attempt WAS made by
    this runner -- the subprocess was launched -- but the wrapper prevented
    the delegated check's own process from ever running, which is "the
    attempt could not be run to a verdict", never "the attempt has never
    been made" -- that value stays reserved for THIS hook's own declaration
    stating no attempt was configured at all, checked earlier in `_observe()`
    before any subprocess runs). `_LAUNCH_FAILURE_MARKERS` is now the
    documented CONSERVATIVE FALLBACK for a launch failure that does not
    route through `run_hook.py`'s own protocol at all (e.g. the interpreter
    itself never reaching `run_hook.py`), not the primary mechanism.
    Also added `_looks_like_argparse_usage_error()`: a real argparse-based
    check that treats the appended known-bad input as an unrecognised
    positional argument exits Python's own hard-coded parser-error code (2)
    with a `usage: ...` / `error: unrecognized arguments` footprint written
    by `argparse.ArgumentParser.error()` BEFORE the check's own examination
    logic ever runs -- structurally the same failure class as a launch
    failure (the check's own verdict-producing logic never executed), so it
    is also `blocked`, never `passing`: a matching exit code alone is not
    evidence the check evaluated its declared input, only that its own CLI
    layer rejected the token before doing so.
  - 2026-09-21 [python-coder/GE-120f-1, pr-reviewer H-1c rework]:
    `_looks_like_argparse_usage_error()` required only the single `usage: `
    substring, which is NOT exclusive to argparse -- `change_set_source.py`
    in this same directory prints its own non-argparse `"usage:
    change_set_source.py <manifest_path>"` line on exit code 2 as its own
    convention. The function now requires the CO-MARKER this module's own
    docstring already described as argparse's real footprint: both
    `usage: ` AND `error: unrecognized arguments` must appear, matching the
    two-line shape `argparse.ArgumentParser.error()` actually writes. This
    was a record-accuracy gap only (`_sweep()`'s `any_failing` fires solely
    on `STATE_FAILING`, so a false `blocked` here could never flip a gate's
    exit code) -- no currently-declared `negative_control` was exposed to
    it, but a future check following the exit-2/`usage: ` convention would
    have been misclassified `blocked` instead of `passing` once it gained
    one.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_OUTPUT_ROOT = _THIS_DIR.parent.parent
_REPO_ROOT = _OUTPUT_ROOT.parent
_MANIFEST_PATH = _THIS_DIR / "commit_guardian.json"

# Built from separately-quoted pieces, deliberately: `build_commit_guardian` runs
# `inject_config()` over every deployed .py file (this one included), which does a
# literal text substitution of the whole token wherever it appears CONTIGUOUS in
# the raw source -- deploy time or not. A single literal spelling it out whole
# would get "resolved" by that SAME mechanism, permanently destroying this
# module's own ability to recognise (and substitute) the token in a hook entry
# written directly to disk AFTER deploy time -- exactly how this module's own
# test fixtures, and any post-deploy hook entry, are built.
_OUTPUT_ROOT_TOKEN = "{" + "{config.output_root}" + "}"
_SELF_CHECK_FLAG = "--self-check-empty-population"
_SUBPROCESS_TIMEOUT_SECONDS = 60
_MAX_EVIDENCE_OUTPUT_CHARS = 4000

# CONSERVATIVE FALLBACK ONLY (see DECISION HISTORY above) -- substrings
# meaning "this subprocess was never truly launched to a verdict" for a
# launch failure that does NOT route through run_hook.py's own structured
# not-run protocol at all (e.g. the interpreter itself failing before it
# could even reach run_hook.py). `_parse_not_run_reason()` is the PRIMARY
# discriminator; this list is only consulted when that parse finds nothing.
# ANY of these is `blocked`, never a genuine non-zero "rejection" -- a
# launch failure that exits non-zero is not a real refusal.
_LAUNCH_FAILURE_MARKERS = (
    "could_not_start",
    "no such file or directory",
    "can't open file",
    "modulenotfounderror",
    "traceback (most recent call last)",
)

# run_hook.py (check_outcome.emit_not_run()) emits exactly this line shape
# for every outcome where IT decided never to launch the delegated check's
# own process at all -- "RESULT: not_run checker=<target> reason=<reason>".
_NOT_RUN_RESULT_PREFIX = "RESULT: not_run "
_NOT_RUN_REASON_TOKEN = "reason="

# Python's argparse hard-codes exit code 2 for a parser error (ArgumentParser
# .error()), always preceded by a "usage: ..." line -- written before the
# check's own examination logic ever runs. "usage: " ALONE is not exclusive to
# argparse -- change_set_source.py in this same directory prints its own,
# non-argparse "usage: change_set_source.py <manifest_path>" line on exit 2 as
# its own convention (pr-reviewer H-1c) -- so BOTH markers are required, per
# this module's own DECISION HISTORY and the "error: unrecognized arguments"
# footprint argparse.ArgumentParser.error() writes for an unrecognised
# positional/optional token.
_ARGPARSE_USAGE_ERROR_EXIT_CODE = 2
_ARGPARSE_USAGE_MARKER = "usage: "
_ARGPARSE_UNRECOGNIZED_ARGS_MARKER = "error: unrecognized arguments"

STATE_PASSING = "passing"
STATE_FAILING = "failing"
STATE_BLOCKED = "blocked"
STATE_UNVERIFIED = "unverified"


def _warn(message: str) -> None:
    """Print a WARNING-level diagnostic to stderr.

    Mirrors ``check_secrets.py``'s own ``[check_x] WARNING: ...`` convention
    so every commit_guardian hook's stderr output is greppable the same way.

    Args:
        message: The human-readable warning text.
    """
    print(f"[check_negative_controls] WARNING: {message}", file=sys.stderr)


def _today() -> str:
    """Return today's date as ``YYYY-MM-DD``, the format ``currently.observed`` requires."""
    return datetime.date.today().isoformat()


def _is_examinable(hook: object) -> bool:
    """Return True when ``hook`` is a registration-surface entry an entry line invokes.

    Per ADR-045 §2: the population is every ``hooks_manifest.hooks`` entry
    that carries both a real ``id`` and a real ``entry`` string — read at
    run time, never a hard-coded list.

    Args:
        hook: One raw element of ``hooks_manifest.hooks``.

    Returns:
        bool: True when ``hook`` is examinable.
    """
    return isinstance(hook, dict) and bool(hook.get("id")) and bool(hook.get("entry"))


def _derive_entry_point(entry: str) -> str:
    """Resolve a manifest ``entry`` string into its human-readable entry point.

    Substitutes the config output-root placeholder token with the real
    deployed output root's own directory name. A no-op when the entry was
    already resolved at deploy time — true of every REAL ``hooks_manifest``
    entry, since ``build_commit_guardian`` runs the same ``inject_config``
    substitution when it copies ``templates/scripts/commit_guardian/``
    verbatim — and load-bearing only for a hook injected directly into the
    deployed manifest after deploy time, which is how this module's own
    test fixtures are built.

    Args:
        entry: A hook's raw ``entry`` command string.

    Returns:
        str: The resolved entry point string.
    """
    return entry.replace(_OUTPUT_ROOT_TOKEN, _OUTPUT_ROOT.name)


def _read_manifest() -> dict | None:
    """Read and parse the DEPLOYED ``commit_guardian.json`` beside this file.

    Returns:
        dict | None: The parsed manifest, or None when it could not be read
        or parsed — logged at WARNING, never raised, so the caller can
        convert this into a ``blocked``/non-zero outcome rather than an
        uncaught traceback.
    """
    try:
        raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        _warn(f"could not read {_MANIFEST_PATH}: {exc}")
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        _warn(f"could not parse {_MANIFEST_PATH} as JSON: {exc}")
        return None


def _write_manifest(data: dict) -> bool:
    """Write ``data`` back to the DEPLOYED ``commit_guardian.json`` beside this file.

    Args:
        data: The full manifest dict, with per-hook records already updated
            in place.

    Returns:
        bool: True on success; False (logged at WARNING) on failure.
    """
    try:
        _MANIFEST_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        _warn(f"could not write {_MANIFEST_PATH}: {exc}")
        return False
    return True


def _run_command(resolved_command: str) -> tuple[int | None, str]:
    """Execute one already-token-resolved command as a real subprocess.

    Args:
        resolved_command: A whitespace-tokenizable command string with the
            config output-root placeholder token already resolved.

    Returns:
        tuple[int | None, str]: ``(exit_code, combined stdout+stderr)``.
        ``exit_code`` is None when the process could not be launched at all
        (logged at WARNING).
    """
    tokens = resolved_command.split()
    if not tokens:
        return None, "empty command"
    if tokens[0] == "python":
        tokens[0] = sys.executable
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            tokens,
            cwd=str(_REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _warn(f"negative-control command {resolved_command!r} could not be launched: {exc}")
        return None, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _parse_not_run_reason(output: str) -> str | None:
    """Extract the ``reason=`` value from run_hook.py's own not-run report.

    ``run_hook.py`` -- the SAME dispatch wrapper every negative-control
    command routes through -- emits ``RESULT: not_run checker=<target>
    reason=<reason>`` (via ``check_outcome.emit_not_run()``) for every
    outcome where it decided never to launch the delegated check's own
    process at all: the target's manifest entry is disabled, a
    same-basename sibling entry is disabled (``_is_target_disabled()``
    matches by script basename, not hook id, so either can short-circuit
    the other), or the target script is missing from disk. This is parsed
    explicitly and treated as the PRIMARY discriminator (see this module's
    DECISION HISTORY) rather than inferred from a substring blocklist, so a
    ``reason=disabled`` short-circuit -- exit 0, no traceback, nothing that
    would match ``_LAUNCH_FAILURE_MARKERS`` -- is never misread as a clean
    exit with the rejection absent.

    Args:
        output: Combined stdout+stderr from the negative-control subprocess.

    Returns:
        str | None: The reason value (e.g. ``"disabled"``,
        ``"could_not_start"``), or None when no not-run report line is
        present in ``output``.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith(_NOT_RUN_RESULT_PREFIX):
            continue
        for token in stripped.split():
            if token.startswith(_NOT_RUN_REASON_TOKEN):
                return token[len(_NOT_RUN_REASON_TOKEN) :]
    return None


def _looks_like_argparse_usage_error(exit_code: int | None, output: str) -> bool:
    """Detect Python argparse's own structural parser-error footprint.

    An argparse-based check that receives the appended known-bad input as
    an unrecognised or malformed CLI token never reaches its own
    examination logic: ``ArgumentParser.error()`` prints a ``usage: ...``
    line and exits with argparse's hard-coded parser-error code, 2, before
    the check's ``main()`` body runs at all. A matching exit code alone is
    not evidence the check evaluated its declared input -- only that its
    own CLI layer rejected the token first -- so this must never be read as
    a genuine ``passing`` rejection (ADR-045 §5's "a clean exit from a check
    that saw nothing" hazard, mirrored on the non-zero side).

    Requires BOTH the ``usage: `` line AND the ``error: unrecognized
    arguments`` line (pr-reviewer H-1c): ``usage: `` alone is not exclusive
    to argparse -- ``change_set_source.py`` in this same directory prints
    its own non-argparse ``"usage: change_set_source.py <manifest_path>"``
    line on exit code 2 as its own convention, and a future check following
    that convention must not be misclassified ``blocked`` once it gets a
    declared ``negative_control``. The co-marker is the exact footprint this
    module's own DECISION HISTORY already describes as argparse's real
    signature.

    Args:
        exit_code: The subprocess's exit code, or None if unlaunchable.
        output: Combined stdout+stderr from the subprocess.

    Returns:
        bool: True when the output matches argparse's own usage-error shape
        at its own hard-coded exit code.
    """
    lowered = output.lower()
    return (
        exit_code == _ARGPARSE_USAGE_ERROR_EXIT_CODE
        and _ARGPARSE_USAGE_MARKER in lowered
        and _ARGPARSE_UNRECOGNIZED_ARGS_MARKER in lowered
    )


def _observe(hook: dict) -> tuple[str, dict]:
    """Observe ONE hook's declared negative control by executing it for real.

    Implements ADR-045 §§1, 3 and 5's discriminator: the state MUST come
    from execution alone. A disabled hook, or one with no falsifiable
    ``negative_control`` declared — including a ``negative_control`` block
    that carries only a previously-written ``currently`` record and no
    ``input`` of its own, which is what THIS RUNNER'S OWN prior sweep
    leaves behind on a hook that had no declaration to begin with, and
    which must never be misread as a declaration on the next sweep —
    records ``unverified``: the attempt has never been made, WITHOUT
    inspecting the declaration's content any further (a well-formed
    declaration is never read back as its own answer). A declared command
    that does not contain the declared input verbatim is recorded
    ``blocked``: several commit-guardian hooks ignore argv entirely, so
    this run must establish the check actually saw the input before
    trusting its exit code (ADR-045 §5).

    Once launched, the state is derived PRIMARILY from
    ``_parse_not_run_reason()`` -- run_hook.py's own structured
    ``RESULT: not_run checker=... reason=...`` protocol, which fires
    whenever run_hook.py itself decided never to launch the delegated
    check's own process (disabled, a same-basename sibling disabled, or
    missing from disk). Any such reason is ``blocked``: the attempt was
    made by this runner but could not be run to a verdict, never
    ``failing`` -- a check that never launched must never be recorded as
    having run and failed to reject its input. ``_LAUNCH_FAILURE_MARKERS``
    and ``_looks_like_argparse_usage_error()`` are the conservative
    fallback for a launch failure that does not route through that
    protocol at all.

    Args:
        hook: One examinable ``hooks_manifest.hooks`` entry.

    Returns:
        tuple[str, dict]: ``(state, evidence)`` where evidence is a single
        ``{command, output, exit_code?}`` dict ready for
        ``currently.evidence``.
    """
    if hook.get("enabled") is False:
        return STATE_UNVERIFIED, {
            "command": "n/a",
            "output": "hook is disabled -- the attempt has never been made",
        }

    nc = hook.get("negative_control")
    declared_input = str(nc.get("input") or "") if isinstance(nc, dict) else ""
    if not isinstance(nc, dict) or nc.get("not_applicable") or not declared_input:
        reason = nc.get("reason") if isinstance(nc, dict) else "no negative_control declared"
        return STATE_UNVERIFIED, {
            "command": "n/a",
            "output": f"no falsifiable control to run: {reason}",
        }

    command = nc.get("command") or f"{hook.get('entry', '')} {declared_input}".strip()
    resolved = command.replace(_OUTPUT_ROOT_TOKEN, _OUTPUT_ROOT.name)

    if declared_input not in resolved:
        return STATE_BLOCKED, {
            "command": resolved,
            "output": (
                "declared command does not contain the declared known-bad "
                "input -- cannot establish the check actually saw it"
            ),
        }

    exit_code, output = _run_command(resolved)
    evidence: dict = {"command": resolved, "output": output[:_MAX_EVIDENCE_OUTPUT_CHARS]}
    if exit_code is not None:
        evidence["exit_code"] = exit_code

    not_run_reason = _parse_not_run_reason(output)
    if not_run_reason is not None:
        evidence["not_run_reason"] = not_run_reason
        return STATE_BLOCKED, evidence

    lowered_output = output.lower()
    if exit_code is None or any(marker in lowered_output for marker in _LAUNCH_FAILURE_MARKERS):
        return STATE_BLOCKED, evidence
    if _looks_like_argparse_usage_error(exit_code, output):
        return STATE_BLOCKED, evidence
    if exit_code != 0:
        return STATE_PASSING, evidence
    return STATE_FAILING, evidence


def _sweep(hooks: list) -> bool:
    """Examine every examinable hook, writing each one's record in place.

    Args:
        hooks: The full raw ``hooks_manifest.hooks`` list (mutated in
            place; non-examinable entries are left untouched).

    Returns:
        bool: True when at least one EXAMINED hook (one whose control was
        launched to a verdict this run) recorded ``failing`` (ADR-045 §8).
    """
    any_failing = False
    for hook in hooks:
        if not _is_examinable(hook):
            continue
        state, evidence = _observe(hook)
        entry_point = _derive_entry_point(hook.get("entry", ""))
        hook["entry_point"] = entry_point
        nc_block = hook.get("negative_control")
        if not isinstance(nc_block, dict):
            nc_block = {}
            hook["negative_control"] = nc_block
        nc_block["currently"] = {
            "state": state,
            "observed": _today(),
            "evidence": [evidence],
        }
        print(f"NEGATIVE_CONTROL: id={hook.get('id')} state={state} entry_point={entry_point}")
        if state == STATE_FAILING:
            any_failing = True
    return any_failing


def _run_self_check_empty_population() -> int:
    """The runner's OWN negative control (ADR-045 §6a).

    The declared known-bad input is the ``--self-check-empty-population``
    flag; the observable rejection is refusing to exit 0 over a
    registration surface with zero invokable entries — ADR-045 §7's own
    failure mode.

    Returns:
        int: Always 1 — a clean (0) exit here would BE the §7 failure this
        control exists to catch.
    """
    print(
        "NEGATIVE_CONTROL_SELF_CHECK: population=0 -- refusing to report a "
        "clean sweep over zero examined checks (ADR-045 section 7)."
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    """Sweep every examinable check on the real registration surface.

    Args:
        argv: Forwarded CLI arguments (defaults to ``sys.argv[1:]``).

    Returns:
        int: 0 when every examined check recorded ``passing``; 1 when at
        least one recorded ``failing``, or when the sweep could not proceed
        at all (unreadable/unwritable manifest, or a registration surface
        naming zero examinable checks — ADR-045 §7: a sweep must never
        silently degrade into examining nothing and calling that clean).
    """
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if _SELF_CHECK_FLAG in args:
        return _run_self_check_empty_population()

    data = _read_manifest()
    if data is None:
        return 1

    hooks = data.get("hooks_manifest", {}).get("hooks")
    if not isinstance(hooks, list) or not any(_is_examinable(h) for h in hooks):
        _warn(
            "the registration surface named ZERO checks with a real entry "
            "line -- refusing to report a clean sweep over nothing "
            "(ADR-045 section 7)"
        )
        return 1

    any_failing = _sweep(hooks)

    if not _write_manifest(data):
        return 1

    return 1 if any_failing else 0


if __name__ == "__main__":
    sys.exit(main())
