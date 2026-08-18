"""
MODULE: test_bo2400c_prompt_cache_wiring
GOAL: RED behavioral tests for the reachability + consumption half of the
    fast-lane prompt-caching layer — the half BO-2400c-1's amendment says has
    never run once, even though ``assemble_context_bundle`` in
    ``scripts/injection_builders.py`` has been pure, correct, and unit-tested
    since 2026-07-21.

ACs covered (see BO-2400c-1.yaml's amended_by entry for the full narrative):
  - BO-2400c-1-ii  — the prompt-caching layer must be reachable as a COMMAND,
    because the fast-lane workflow body has no filesystem access (ADR-024)
    and reaches Python only by dispatching an agent that runs one Bash
    command. KI-BO-005: the module defines no argparse and no __main__, so
    the only production call site (an orphaned runner) is a silent no-op.
  - BO-2400c-1-iii — the prompt a dispatched test-writer/coder agent receives
    IS the assembled bundle, verbatim. KI-BO-006: the live lane
    (templates/workflows-js/fast-lane-ship.js) never mentions the layer at
    all today.
  - BO-2400c-1-iv  — across one run's successive context-carrying dispatches,
    the cacheable prefix (everything up to and including the breakpoint
    marker) is byte-identical, and the volatile suffix genuinely differs.

Deliberately NOT covered here: BO-2400c-1-v (deleting the orphaned runner) —
sequenced after this work lands, per the dispatching instructions.

=== Verify Behaviorally, Not by Grep (root CLAUDE.md) ===
Every BO-2400c-1-ii test below EXECUTES scripts/injection_builders.py as a
real subprocess (subprocess.run with a list of args) and asserts on its
actual exit code and actual stdout/stderr — never on source text. Every
BO-2400c-1-iii/-iv test EXECUTES the real, on-disk fast-lane-ship.js under
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() and asserts
on the RECORDED, EXECUTED agent_calls' prompts and the executed call order —
never on fast-lane-ship.js source text. This lane has already shipped the
grep-passes-on-dead-code failure mode twice (fast_lane.py's missing CLI;
the unit_tests/workflows/test_bo2400a_runner_wiring.py:401 grep test that
asserted a layer's NAME appeared in an orphaned file) — no test in this file
repeats it.

=== Source-of-Truth Discipline Rule 3 (cross-layer seam) ===
BO-2400c-1-iii/-iv tests are exactly the mandated cross-layer seam tests: the
producer is the prompt-caching layer (reached via the BO-2400c-1-ii command),
the consumer is fast-lane-ship.js's phase-agent dispatches. A unit test of
the pure assemble_context_bundle() function plus a unit test of the CLI in
isolation would NOT satisfy this — nothing would prove the lane's dispatched
prompts actually carry the bundle text, which is the entire content of
BO-2400c-1-iii's criterion ("the criterion is satisfied only by what the
dispatched agent receives").

=== Assumed implementation contracts (for python-coder) ===
Neither the CLI subcommand nor the bundle-obtaining dispatch in
fast-lane-ship.js exists yet, so these tests necessarily assume specific,
minimal, documented names for the seams they exercise — the concrete
contract these tests constrain python-coder to implement. If the real
implementation differs in naming but still satisfies the AC criteria, adjust
these tests alongside it (Source-of-Truth Discipline Rule 1: a failing test
is a question, not an answer) — the underlying BEHAVIOR asserted is what the
ACs actually require, independent of naming.

  1. BO-2400c-1-ii — scripts/injection_builders.py gains a subcommand named
     ``assemble-bundle`` invoked as:
       python3 injection_builders.py assemble-bundle \
         --architecture <path> --conventions <path> --high-level <path> \
         --acs <path> --prior-tests <path> \
         [--prior-outputs <path>] [--working-diff <path>] \
         [--breakpoint-marker <str>]
     Each required/optional layer flag (except --breakpoint-marker, which is
     a literal string) takes a FILE PATH, not inline text — mirroring the
     existing fast_lane.py CLI convention (every argument is a path or an
     id, never large inline text) and matching the it_requirements note that
     "an argument names content the layer cannot obtain" is a failure mode,
     which only makes sense if arguments are references to content rather
     than the content itself. The command reads each required file as UTF-8,
     calls assemble_context_bundle() with the contents, and prints the
     result to stdout with nothing else. Missing required flag or unreadable
     path: non-zero exit, nothing on stdout, the missing/unreadable layer
     named on stderr.

  2. BO-2400c-1-iii/-iv — fast-lane-ship.js gains ONE new agent() dispatch,
     between Resolve/claim and Test Writer, with opts.label ==
     "fastlane-context-bundle". Its returned payload conforms to
     BO-2400c-1-iii's own config_schema_fragment (fast_lane_context_bundle):
       { bundle: str, obtained: bool, message: str }
     obtained must be read with the same plain-falsy check already used for
     testWriterResult.gate_passed (BO-2400c-1-iii's own constraint). The
     returned bundle text is threaded verbatim into the Test Writer and
     Coder dispatch prompts. This dispatch must be obtained exactly ONCE per
     run and its stable region reused unchanged by both dispatches — not
     re-assembled per phase (BO-2400c-1-iv's own note that re-assembly is
     "precisely how a mid-run edit ... would bust the anchor without anyone
     noticing").

=== Real-Artifact Behavioral Test Mandate ===
The BO-2400c-1-ii deployed-copy test performs a genuine real-effect
round-trip: it runs the REAL scripts/build.py into a fresh tmp_path (a real
filesystem write, not mocked), then executes the DEPLOYED copy of
injection_builders.py from that real output directory and reads its real
stdout back — mirroring the established pattern in
unit_tests/test_bp_900g_6_paths.py. The BO-2400c-1-iii/-iv harness tests have
no durable artifact to round-trip: fast-lane-ship.js is an E2 workflow script
with no direct filesystem access (ADR-024) — every side effect is an LLM
agent dispatch the harness mocks — which mirrors the identical scoping note
already documented in test_bo2400f_review_and_delivery_guarantee.py for the
sibling fast-lane feature.

=== Fixture-authenticity mandate (BO-2500c) ===
No hand-typed copy of fast-lane-ship.js or injection_builders.py content is
embedded as a fixture standing in for the real files. BO-2400c-1-ii tests
write REAL temp files to disk and execute the REAL on-disk
injection_builders.py as a subprocess. BO-2400c-1-iii/-iv tests execute the
REAL on-disk fast-lane-ship.js via run_workflow_under_e2. The only
hand-authored strings are the INPUT content for the layers (architecture
text, etc.) and the assumed label/schema names documented above, which is
the same posture test_bo2400f_review_and_delivery_guarantee.py already
established for this same file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ and unit_tests/ importable regardless of cwd.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import build as _build  # noqa: E402 — after sys.path setup
from injection_builders import assemble_context_bundle  # noqa: E402
from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_INJECTION_BUILDERS_PY = _SCRIPTS_DIR / "injection_builders.py"
_FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"


# ===========================================================================
# BO-2400c-1-ii — reachability: a real command that runs
# ===========================================================================

_ARCH_TEXT = "## Architecture\nSTABLE_ARCHITECTURE_MARKER_BO2400C1II — layered repository pattern."
_CONV_TEXT = "## Conventions\nSTABLE_CONVENTIONS_MARKER_BO2400C1II — docstrings required."
_HL_TEXT = "## L1 AC\nSTABLE_HIGHLEVEL_MARKER_BO2400C1II — the big picture."
_ACS_TEXT = "## L2 ACs\nVOLATILE_ACS_MARKER_BO2400C1II — BO-2400c-1-ii."
_PRIOR_TESTS_TEXT = "## Prior Tests\nVOLATILE_PRIOR_TESTS_MARKER_BO2400C1II."
_DEFAULT_MARKER = "<!-- CACHE_BREAKPOINT -->"


def _write_layer_files(tmp_path: Path) -> dict[str, Path]:
    """Write each required layer's content to a real temp file and return paths."""
    layers = {
        "architecture": _ARCH_TEXT,
        "conventions": _CONV_TEXT,
        "high_level": _HL_TEXT,
        "acs": _ACS_TEXT,
        "prior_tests": _PRIOR_TESTS_TEXT,
    }
    paths: dict[str, Path] = {}
    for name, text in layers.items():
        p = tmp_path / f"{name}.md"
        p.write_text(text, encoding="utf-8")
        paths[name] = p
    return paths


def _cli_args(script: Path, paths: dict[str, Path]) -> list[str]:
    """Build the assumed `assemble-bundle` CLI invocation (see module docstring)."""
    return [
        sys.executable,
        str(script),
        "assemble-bundle",
        "--architecture", str(paths["architecture"]),
        "--conventions", str(paths["conventions"]),
        "--high-level", str(paths["high_level"]),
        "--acs", str(paths["acs"]),
        "--prior-tests", str(paths["prior_tests"]),
    ]


def test_ac2ii_valid_invocation_exits_zero_and_emits_assembled_bundle(tmp_path):
    # covers: BO-2400c-1-ii
    """A real subprocess invocation with all required layers supplied exits
    zero and its stdout contains the stable layers, exactly one breakpoint
    marker, and the volatile layers — in that order.

    RED today (KI-BO-005): the module defines no argparse and no __main__, so
    running it as a script does nothing regardless of arguments — it exits 0
    with EMPTY stdout, which this test's non-empty-stdout assertion catches.
    """
    paths = _write_layer_files(tmp_path)
    proc = subprocess.run(
        _cli_args(_INJECTION_BUILDERS_PY, paths),
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, (
        f"Expected exit 0 for a fully-supplied invocation. "
        f"Got {proc.returncode}. stderr={proc.stderr!r}"
    )
    stdout = proc.stdout
    assert stdout.strip(), (
        "The command exited 0 but produced no output on stdout — a silent "
        "no-op that resolves, runs, and exits zero without producing the "
        "bundle is explicitly called out by BO-2400c-1-ii as NOT satisfying "
        "the criterion (it is the defect being fixed, not evidence of a fix)."
    )
    assert stdout.count(_DEFAULT_MARKER) == 1, (
        f"Expected exactly one breakpoint marker in stdout. "
        f"Found {stdout.count(_DEFAULT_MARKER)}. stdout={stdout!r}"
    )
    marker_idx = stdout.index(_DEFAULT_MARKER)
    for stable_text in (_ARCH_TEXT, _CONV_TEXT, _HL_TEXT):
        assert stable_text in stdout[:marker_idx], (
            f"Stable layer content missing before the breakpoint marker: "
            f"{stable_text!r}. stdout={stdout!r}"
        )
    for volatile_text in (_ACS_TEXT, _PRIOR_TESTS_TEXT):
        assert volatile_text in stdout[marker_idx:], (
            f"Volatile layer content missing after the breakpoint marker: "
            f"{volatile_text!r}. stdout={stdout!r}"
        )


def test_ac2ii_stdout_matches_the_pure_function_output_byte_for_byte(tmp_path):
    # covers: BO-2400c-1-ii
    """The subprocess stdout equals the string the imported pure function
    returns for the same inputs — no banner, log line, or trailing decoration.

    RED today: stdout is empty (KI-BO-005), so it cannot equal the non-empty
    pure-function output.
    """
    paths = _write_layer_files(tmp_path)
    proc = subprocess.run(
        _cli_args(_INJECTION_BUILDERS_PY, paths),
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"Expected exit 0. Got {proc.returncode}. stderr={proc.stderr!r}"

    expected = assemble_context_bundle(
        architecture=_ARCH_TEXT,
        conventions=_CONV_TEXT,
        high_level=_HL_TEXT,
        acs=_ACS_TEXT,
        prior_tests=_PRIOR_TESTS_TEXT,
    )
    # At most one trailing newline is tolerated (print() appends one) — any
    # OTHER difference (a banner, a log line mixed into stdout) is a defect,
    # because any extra byte on the stable side of the breakpoint destroys
    # the byte-identity BO-2400c-1-iv rests on.
    assert proc.stdout in (expected, expected + "\n"), (
        "stdout must equal the pure function's return value exactly (at most "
        "a single trailing newline). "
        f"Got stdout={proc.stdout!r}\nExpected={expected!r}"
    )


def test_ac2ii_missing_required_layer_exits_non_zero_and_names_it(tmp_path):
    # covers: BO-2400c-1-ii
    """Invoked without a required layer, the command exits non-zero, names
    the missing layer on stderr, and writes no bundle to stdout.

    RED today: the module has no argparse/__main__ at all, so it exits 0 with
    empty stdout regardless of which arguments are present or absent —
    exactly the "invocation is unusable but nothing tells you" defect this
    criterion exists to close.
    """
    paths = _write_layer_files(tmp_path)
    args = _cli_args(_INJECTION_BUILDERS_PY, paths)
    # Drop the trailing `--prior-tests <path>` pair.
    args_missing_prior_tests = args[:-2]

    proc = subprocess.run(
        args_missing_prior_tests, capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode != 0, (
        "A missing required layer (--prior-tests) must exit non-zero. "
        f"Got exit 0 with stdout={proc.stdout!r}"
    )
    assert not proc.stdout.strip(), (
        "A failed invocation must never write a partial bundle to stdout. "
        f"Got stdout={proc.stdout!r}"
    )
    stderr_lower = proc.stderr.lower()
    assert "prior_tests" in stderr_lower or "prior-tests" in stderr_lower, (
        f"stderr must name the missing layer ('prior_tests'). "
        f"Got stderr={proc.stderr!r}"
    )


def test_ac2ii_unreadable_layer_input_exits_non_zero_never_partial_bundle(tmp_path):
    # covers: BO-2400c-1-ii
    """An argument that names content the layer cannot obtain (a path that
    does not exist) must exit non-zero and never emit a partial bundle.

    RED today: the module ignores all arguments, so it exits 0 with empty
    stdout regardless of whether the named path exists.
    """
    paths = _write_layer_files(tmp_path)
    args = _cli_args(_INJECTION_BUILDERS_PY, paths)
    acs_flag_idx = args.index("--acs") + 1
    args[acs_flag_idx] = str(tmp_path / "does_not_exist.md")

    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
    assert proc.returncode != 0, (
        "An unreadable layer input must exit non-zero — never a zero exit "
        f"that silently produces nothing. Got exit 0, stdout={proc.stdout!r}"
    )
    assert not proc.stdout.strip(), (
        "Must never exit with a partial/empty bundle silently printed to "
        f"stdout when a layer is unreadable. Got stdout={proc.stdout!r}"
    )


def _find_deployed_output_root(target_dir: Path) -> Path:
    """Return the deployed output root inside *target_dir* — the directory
    holding scripts/ — discovered dynamically (never hardcoded to
    ``.leafcutter``), mirroring test_bp_900g_6_paths.py's helper.
    """
    candidates = sorted(
        p for p in target_dir.iterdir() if p.is_dir() and (p / "scripts").is_dir()
    )
    assert len(candidates) == 1, (
        f"Expected exactly one deployed output root under {target_dir} "
        f"(a directory containing a 'scripts/' subdirectory); "
        f"found {[p.name for p in candidates]}."
    )
    return candidates[0]


def test_ac2ii_deployed_copy_of_the_command_runs(tmp_path):
    # covers: BO-2400c-1-ii
    """The command executes successfully from the DEPLOYED scripts layout the
    lane actually invokes (``<output_root>/scripts/injection_builders.py``),
    not only from the package source tree.

    Real-effect round-trip: runs the REAL scripts/build.py into a fresh
    tmp_path (a genuine filesystem write), then executes the DEPLOYED copy
    and reads its real stdout back — resolving against the package source
    tree cannot catch a deploy-manifest gap or a CLI that only "works" when
    run from inside the package checkout.

    RED today: injection_builders.py is already in AGENT_SUPPORT_SCRIPT_FILES
    (deployed correctly), but the deployed copy has the same KI-BO-005 defect
    as the source copy — no argparse/__main__ — so it exits 0 with empty
    stdout.
    """
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()
    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"build.py --target-dir exited {exit_code!r}; expected 0."

    output_root = _find_deployed_output_root(target_dir)
    deployed_script = output_root / "scripts" / "injection_builders.py"
    assert deployed_script.is_file(), (
        f"injection_builders.py was not deployed to {deployed_script} — it is "
        "listed in AGENT_SUPPORT_SCRIPT_FILES, so this would itself be a "
        "deploy-manifest regression, not the KI-BO-005 defect this test targets."
    )

    layer_dir = tmp_path / "layers"
    layer_dir.mkdir()
    paths = _write_layer_files(layer_dir)
    proc = subprocess.run(
        _cli_args(deployed_script, paths), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, (
        f"The DEPLOYED copy at {deployed_script} must run successfully. "
        f"Got exit {proc.returncode}. stderr={proc.stderr!r}"
    )
    assert proc.stdout.strip(), (
        "The DEPLOYED copy exited 0 but produced no output — the command "
        "must work from the deployed layout, not only from the package "
        f"source tree. Deployed script: {deployed_script}"
    )


# ===========================================================================
# BO-2400c-1-iii / BO-2400c-1-iv — consumption: the dispatched prompt IS the
# bundle, and the cacheable prefix is byte-identical across dispatches
# ===========================================================================

_TIMEOUT = 30  # seconds; Node subprocess spawn per harness run

# ASSUMED label for the not-yet-existing bundle-assembling dispatch in
# fast-lane-ship.js (see "Assumed implementation contracts" in the module
# docstring).
_BUNDLE_LABEL = "fastlane-context-bundle"

_STABLE_ARCH = "STABLE_ARCH_TEXT_FOR_BO2400C_III_IV"
_STABLE_CONV = "STABLE_CONV_TEXT_FOR_BO2400C_III_IV"
_STABLE_HL = "STABLE_HL_TEXT_FOR_BO2400C_III_IV"
_VOLATILE_ACS = "VOLATILE_ACS_TEXT_FOR_BO2400C_III_IV"
_VOLATILE_PRIOR_TESTS = "VOLATILE_PRIOR_TESTS_TEXT_FOR_BO2400C_III_IV"

# A real bundle produced the same way assemble_context_bundle() would produce
# it (fixture-authenticity: constructed via the actual pure function, not a
# hand-typed re-implementation of its ordering rule).
_KNOWN_BUNDLE = assemble_context_bundle(
    architecture=f"## Architecture\n{_STABLE_ARCH}",
    conventions=f"## Conventions\n{_STABLE_CONV}",
    high_level=f"## L1 AC\n{_STABLE_HL}",
    acs=f"## L2 ACs\n{_VOLATILE_ACS}",
    prior_tests=f"## Prior Tests\n{_VOLATILE_PRIOR_TESTS}",
)

_BUNDLE_OK_RESPONSE = {
    "bundle": _KNOWN_BUNDLE,
    "obtained": True,
    "message": "bundle assembled",
}

# Green baseline label_responses — enough to drive fast-lane-ship.js's
# CURRENT (already-landed BO-2400f) phase order all the way to the Pull
# Request phase. Every key matches a label already present in
# fast-lane-ship.js's existing agent() dispatches.
_GREEN_LABELS: dict = {
    "fastlane-worktree": {
        "worktree_path": "/tmp/fastlane-wt-bo2400c",
        "branch": "fast-lane/bo-stub-1",
        "ac_store_path": "/tmp/fastlane-wt-bo2400c/docs/acceptance-criteria",
        "created": True,
    },
    "resolve-connected": {
        "ac_ids": ["BO-STUB-1"],
        "message": "1 to build",
    },
    "claim-connected": {
        "claimed": ["BO-STUB-1"],
        "excluded_claimed": [],
        "target_refused": False,
    },
    "test-writer-connected": {
        "status": "ok",
        "tests_written": ["unit_tests/test_stub.py"],
        "gate_passed": True,
        "reason": None,
        "green_at_baseline": [],
        "message": "red baseline ok",
    },
    "coder-connected": {
        "status": "ok",
        "files_modified": ["scripts/stub_impl.py"],
        "green": True,
        "coverage_ok": True,
        "uncovered_ac_ids": [],
        "message": "implementation green",
    },
    "fastlane-review": {
        "verdict_obtained": True,
        "high_findings": [],
        "medium_findings": [],
        "low_suppressed_count": 0,
        "message": "clean review",
    },
    "fastlane-changelog": {
        "status": "ok",
        "entry_added": True,
        "entry_path": "changelogs/2026-08-18-0000-stub-entry.md",
        "message": "entry emitted",
    },
    "fastlane-commit": {
        "status": "ok",
        "branch": "fast-lane/bo-stub-1",
        "message": "committed",
    },
    "fastlane-pr": {
        "status": "ok",
        "pr_url": "https://github.com/example/repo/pull/1",
        "message": "PR opened",
    },
}


def _run_ship(bundle_response=_BUNDLE_OK_RESPONSE, extra_labels: dict | None = None,
              args: dict | None = None) -> HarnessResult:
    """Run the REAL fast-lane-ship.js under the E2 harness with the green
    baseline plus a stubbed bundle-assembling dispatch response.
    """
    labels = dict(_GREEN_LABELS)
    if extra_labels:
        labels.update(extra_labels)
    labels[_BUNDLE_LABEL] = bundle_response
    return run_workflow_under_e2(
        _FAST_LANE_SHIP_JS,
        timeout=_TIMEOUT,
        label_responses=labels,
        args=args or {"ac": "BO-STUB-1"},
    )


def _labels_ship(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


def _call(result: HarnessResult, label: str):
    return next((c for c in result.agent_calls if c.label == label), None)


# --- BO-2400c-1-iii ---------------------------------------------------------


def test_ac3iii_dispatched_agent_prompt_is_the_assembled_bundle():
    # covers: BO-2400c-1-iii
    """With the bundle-assembling dispatch stubbed to return a known bundle,
    the recorded test-writer and coder calls carry that bundle text in their
    prompts.

    RED today (KI-BO-006): fast-lane-ship.js never mentions the layer at
    all — the test-writer and coder prompts are custom prose that does not
    contain the bundle string.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    tw_call = _call(result, "test-writer-connected")
    coder_call = _call(result, "coder-connected")
    assert tw_call is not None, (
        f"Expected the test-writer dispatch to execute. Labels: {_labels_ship(result)}"
    )
    assert coder_call is not None, (
        f"Expected the coder dispatch to execute. Labels: {_labels_ship(result)}"
    )

    for call, name in ((tw_call, "test-writer"), (coder_call, "coder")):
        prompt = call.prompt
        assert isinstance(prompt, str), f"{name} prompt must be a string. Got: {type(prompt)}"
        assert _KNOWN_BUNDLE in prompt, (
            f"The assembled bundle must reach the {name} dispatch verbatim as "
            f"prompt context. Bundle not found in prompt. "
            f"Prompt (first 400 chars): {prompt[:400]!r}"
        )


def test_ac3iii_bundle_reaches_the_agent_verbatim_no_rewrap():
    # covers: BO-2400c-1-iii
    """The stubbed bundle text appears in the recorded prompt unaltered —
    same bytes, same order, no re-wrapping, appearing exactly once (not
    duplicated or fragmented).

    RED today: the bundle string does not appear in the coder prompt at all.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    coder_call = _call(result, "coder-connected")
    assert coder_call is not None, f"Expected coder dispatch. Labels: {_labels_ship(result)}"
    prompt = coder_call.prompt
    assert isinstance(prompt, str), f"coder prompt must be a string. Got: {type(prompt)}"

    assert prompt.count(_KNOWN_BUNDLE) == 1, (
        "The bundle must appear exactly once, as one contiguous, unaltered "
        f"substring — no re-wrapping, no interpolation inside it, no "
        f"duplication. Found {prompt.count(_KNOWN_BUNDLE)} occurrence(s). "
        f"Prompt (first 400 chars): {prompt[:400]!r}"
    )
    start = prompt.index(_KNOWN_BUNDLE)
    assert prompt[start:start + len(_KNOWN_BUNDLE)] == _KNOWN_BUNDLE, (
        "The bundle substring must be byte-for-byte identical to what the "
        "assembling command returned — no trimming, no re-wrapping."
    )


def test_ac3iii_bundle_assembly_dispatch_precedes_context_carrying_dispatches():
    # covers: BO-2400c-1-iii
    """In a fully green harness run, the bundle-assembling dispatch is
    EXECUTED before the test-writer and coder dispatches — asserted on
    executed call order, not source text.

    RED today: the bundle-assembling dispatch (label
    'fastlane-context-bundle') never executes at all, because
    fast-lane-ship.js never mentions the prompt-caching layer.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    labels = _labels_ship(result)
    assert _BUNDLE_LABEL in labels, (
        f"Expected the bundle-assembling dispatch (label={_BUNDLE_LABEL!r}) "
        f"to actually execute. Got labels: {labels}"
    )
    assert "test-writer-connected" in labels and "coder-connected" in labels, (
        f"Expected both context-carrying dispatches to execute. Got: {labels}"
    )

    bundle_idx = labels.index(_BUNDLE_LABEL)
    tw_idx = labels.index("test-writer-connected")
    coder_idx = labels.index("coder-connected")
    assert bundle_idx < tw_idx, (
        f"Bundle dispatch must precede test-writer dispatch. Order: {labels}"
    )
    assert bundle_idx < coder_idx, (
        f"Bundle dispatch must precede coder dispatch. Order: {labels}"
    )


def test_ac3iii_unobtainable_bundle_halts_instead_of_dispatching_unbundled_prompts():
    # covers: BO-2400c-1-iii
    """With the assembling dispatch stubbed to return a failure, an empty
    payload, or nothing readable, the run records no test-writer or coder
    dispatch, and its terminal payload names the context bundle as the
    reason.

    RED today: fast-lane-ship.js never consults any bundle-assembling
    dispatch, so it sails straight through to test-writer/coder regardless
    of what this stub returns.
    """
    unusable_variants = [
        {"bundle": "", "obtained": False, "message": "assembling command failed"},
        {},
        None,
    ]
    for variant in unusable_variants:
        result = _run_ship(bundle_response=variant)
        assert result.error == "", f"Harness error for variant {variant!r}: {result.error}"

        labels = _labels_ship(result)
        assert "test-writer-connected" not in labels, (
            f"An unobtainable bundle ({variant!r}) must not permit an "
            f"unbundled test-writer dispatch. Labels: {labels}"
        )
        assert "coder-connected" not in labels, (
            f"An unobtainable bundle ({variant!r}) must not permit an "
            f"unbundled coder dispatch. Labels: {labels}"
        )

        payload = result.result
        assert payload is not None, (
            f"Missing terminal payload for variant {variant!r}. Labels: {labels}"
        )
        message_blob = json.dumps(payload).lower()
        assert "bundle" in message_blob, (
            f"The terminal payload must name the context bundle as the "
            f"reason the run halted before dispatching context-carrying "
            f"agents. Got: {payload}"
        )
        assert payload.get("status") not in ("ok",), (
            f"An unobtainable bundle must never be reported as a successful "
            f"run. Got: {payload}"
        )


def test_ac3iii_breakpoint_marker_present_exactly_once_in_dispatched_prompt():
    # covers: BO-2400c-1-iii
    """Each recorded context-carrying prompt contains exactly one cache
    breakpoint marker, with the stable layers before it and this run's
    volatile content after it.

    RED today: the marker never appears in either prompt at all.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    for label in ("test-writer-connected", "coder-connected"):
        call = _call(result, label)
        assert call is not None, f"Expected {label} dispatch. Labels: {_labels_ship(result)}"
        prompt = call.prompt
        assert isinstance(prompt, str), f"{label} prompt must be a string."

        count = prompt.count(_DEFAULT_MARKER)
        assert count == 1, (
            f"{label} prompt must contain the cache breakpoint marker "
            f"exactly once. Found {count}. Prompt (first 400 chars): {prompt[:400]!r}"
        )
        marker_idx = prompt.index(_DEFAULT_MARKER)
        assert _STABLE_ARCH in prompt[:marker_idx], (
            f"{label}: stable layer content must appear before the "
            f"breakpoint marker."
        )
        assert _VOLATILE_ACS in prompt[marker_idx:], (
            f"{label}: volatile layer content must appear after the "
            f"breakpoint marker."
        )


# --- BO-2400c-1-iv -----------------------------------------------------------


def _stable_prefix(prompt: str, marker: str) -> str:
    """Return the portion of *prompt* up to and including *marker*.

    If the marker is absent, the entire prompt counts as "prefix" — there is
    no partition into stable/volatile yet, so any run-varying content in the
    prompt correctly counts as a violation of "nothing run-varying appears
    before the breakpoint."
    """
    idx = prompt.find(marker)
    if idx == -1:
        return prompt
    return prompt[: idx + len(marker)]


def _volatile_suffix(prompt: str, marker: str) -> str:
    """Return the portion of *prompt* strictly after *marker* (empty if absent)."""
    idx = prompt.find(marker)
    if idx == -1:
        return ""
    return prompt[idx + len(marker):]


def test_ac4iv_stable_prefix_identical_across_successive_dispatches():
    # covers: BO-2400c-1-iv
    """In an executed harness run, the region up to and including the
    breakpoint marker is byte-equal across every recorded context-carrying
    prompt.

    RED today: fast-lane-ship.js never inserts the assembled bundle into
    either prompt, so the two phase-specific prompt bodies differ entirely
    and their "prefixes" (the whole prompt, absent any marker) are unequal.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    tw_call = _call(result, "test-writer-connected")
    coder_call = _call(result, "coder-connected")
    assert tw_call is not None and coder_call is not None, (
        f"Expected both dispatches to execute. Labels: {_labels_ship(result)}"
    )

    prefix_tw = _stable_prefix(tw_call.prompt, _DEFAULT_MARKER)
    prefix_coder = _stable_prefix(coder_call.prompt, _DEFAULT_MARKER)
    assert prefix_tw == prefix_coder, (
        "The portion of each dispatched prompt up to and including the cache "
        "breakpoint must be byte-identical across the test-writer and coder "
        "dispatches.\n"
        f"test-writer prefix (first 200 chars): {prefix_tw[:200]!r}\n"
        f"coder prefix (first 200 chars): {prefix_coder[:200]!r}"
    )


def test_ac4iv_volatile_suffix_differs_across_successive_dispatches():
    # covers: BO-2400c-1-iv
    """The regions after the breakpoint marker are not all equal, so the
    prefix equality cannot be satisfied by sending every agent the same
    prompt.

    RED today: since the breakpoint marker is absent from both prompts, the
    helper treats both suffixes as empty strings — which are (wrongly) equal,
    so this assertion correctly fails.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    tw_call = _call(result, "test-writer-connected")
    coder_call = _call(result, "coder-connected")
    assert tw_call is not None and coder_call is not None, (
        f"Expected both dispatches to execute. Labels: {_labels_ship(result)}"
    )

    suffix_tw = _volatile_suffix(tw_call.prompt, _DEFAULT_MARKER)
    suffix_coder = _volatile_suffix(coder_call.prompt, _DEFAULT_MARKER)
    assert suffix_tw != suffix_coder, (
        "The per-phase content after the breakpoint must genuinely differ "
        "between dispatches — otherwise the prefix-equality guarantee could "
        "be satisfied trivially by sending every agent an identical prompt, "
        "which would destroy the per-phase context the lane depends on.\n"
        f"test-writer suffix: {suffix_tw!r}\ncoder suffix: {suffix_coder!r}"
    )


def test_ac4iv_run_varying_values_do_not_appear_before_the_breakpoint():
    # covers: BO-2400c-1-iv
    """The worktree path, branch name, and target AC id supplied to the
    executed run appear only after the breakpoint marker in the recorded
    prompts, never in the prefix.

    RED today: there is no breakpoint marker in the dispatched prompt at
    all, so the entire prompt — which DOES contain the worktree path and
    branch — counts as the prefix.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    worktree_path = _GREEN_LABELS["fastlane-worktree"]["worktree_path"]
    branch = _GREEN_LABELS["fastlane-worktree"]["branch"]
    target_ac = "BO-STUB-1"

    for label in ("test-writer-connected", "coder-connected"):
        call = _call(result, label)
        assert call is not None, f"Expected {label} dispatch. Labels: {_labels_ship(result)}"
        prefix = _stable_prefix(call.prompt, _DEFAULT_MARKER)

        for run_varying, name in (
            (worktree_path, "worktree_path"),
            (branch, "branch"),
            (target_ac, "target_ac"),
        ):
            assert run_varying not in prefix, (
                f"{label}: run-varying value {name}={run_varying!r} must "
                f"never appear in the stable prefix (everything up to and "
                f"including the breakpoint) — a prefix carrying it would "
                f"yield a cold cache on every single run.\n"
                f"prefix (first 400 chars): {prefix[:400]!r}"
            )


def test_ac4iv_prefix_drift_between_dispatches_is_surfaced():
    # covers: BO-2400c-1-iv
    """Drift is reported rather than tolerated: the bundle-assembling
    dispatch must be obtained exactly ONCE per run and its stable region
    reused verbatim by every later context-carrying dispatch. Re-obtaining
    or re-assembling it per phase is precisely how prefix drift enters (a
    stable source re-read and re-rendered mid-run, BO-2400c-1-iv's own named
    cause) — enforcing single-dispatch is what prevents it from ever being
    observable in the first place.

    RED today: the bundle-assembling dispatch does not exist at all, so it
    is dispatched zero times, not exactly once.
    """
    result = _run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    labels = _labels_ship(result)
    bundle_dispatch_count = labels.count(_BUNDLE_LABEL)
    assert bundle_dispatch_count == 1, (
        "The bundle-assembling dispatch must be obtained exactly ONCE per "
        f"run. Got {bundle_dispatch_count} dispatch(es) with label "
        f"{_BUNDLE_LABEL!r}. Full label order: {labels}"
    )
