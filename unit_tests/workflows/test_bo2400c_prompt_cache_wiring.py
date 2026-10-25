"""
MODULE: test_bo2400c_prompt_cache_wiring
GOAL: RED behavioral tests for the reachability + consumption half of the
    fast-lane prompt-caching layer — the half BO-2400c-1's amendment says has
    never run once, even though ``assemble_context_bundle`` in
    ``scripts/injection_builders.py`` has been pure, correct, and unit-tested
    since 2026-07-21.

    File split (file-size ratchet): this file holds the BO-2400c-1-ii
    reachability tests (the ``assemble-bundle`` command). The BO-2400c-1-iii /
    -iv consumption tests live in the sibling
    test_bo2400c_prompt_cache_consumption.py.

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

=== BO-2400c-1-vi call-site audit (2026-08-26) ===
BO-2400c-1-vi removes the `conventions` and `acs` layers from
assemble_context_bundle() and the `assemble-bundle` CLI subcommand entirely
(not defaulted to None — removed, so no caller can reintroduce the largest
duplicate in the payload). This file is a declared call site
(BO-2400c-1-vi.yaml's it_requirements constraint list) for THREE distinct
reasons, all fixed in this same change:
  (a) the CLI-layer helpers below (_write_layer_files, _cli_args) built a
      five-flag invocation including --conventions/--acs;
  (b) test_ac2ii_stdout_matches_the_pure_function_output_byte_for_byte calls
      assemble_context_bundle() directly with conventions=/acs=;
  (c) the MODULE-SCOPE `_KNOWN_BUNDLE` fixture (now in the sibling
      test_bo2400c_prompt_cache_consumption.py) calls
      assemble_context_bundle() with conventions=/acs= — a call at
      IMPORT time, so an unfixed module-scope call would fail this whole
      file at pytest COLLECTION rather than at assertion, per that AC's own
      note.
Classification (Source-of-Truth Discipline Rule 1): TEST DRIFT — production
has not changed yet, so every rewritten call below now omits arguments the
CURRENT (unmodified) assemble_context_bundle() still requires as
keyword-only parameters with no default, and the CLI still requires
--conventions/--acs. The resulting TypeError / non-zero exit is the
intended, correctly-red state until BO-2400c-1-vi lands.
(classification: test_drift)

=== Assumed implementation contracts (for python-coder) ===
Neither the CLI subcommand nor the bundle-obtaining dispatch in
fast-lane-ship.js exists yet, so these tests necessarily assume specific,
minimal, documented names for the seams they exercise — the concrete
contract these tests constrain python-coder to implement. If the real
implementation differs in naming but still satisfies the AC criteria, adjust
these tests alongside it (Source-of-Truth Discipline Rule 1: a failing test
is a question, not an answer) — the underlying BEHAVIOR asserted is what the
ACs actually require, independent of naming.

  1. BO-2400c-1-ii, as narrowed by BO-2400c-1-vi — scripts/injection_builders.py
     gains a subcommand named ``assemble-bundle`` invoked as:
       python3 injection_builders.py assemble-bundle \
         --architecture <path> --high-level <path> --prior-tests <path> \
         [--prior-outputs <path>] [--working-diff <path>] \
         [--breakpoint-marker <str>]
     ``--conventions`` and ``--acs`` are REMOVED (BO-2400c-1-vi) — not made
     optional, not defaulted — because the receiving agent already has the
     project conventions (the harness injects them) and can already open
     the run's own AC store, so carrying either duplicated content the
     agent already had (129,178 of 148,891 bytes, 87%, on the run that
     failed). Each remaining required/optional layer flag (except
     --breakpoint-marker, which is a literal string) takes a FILE PATH, not
     inline text — mirroring the existing fast_lane.py CLI convention
     (every argument is a path or an id, never large inline text) and
     matching the it_requirements note that "an argument names content the
     layer cannot obtain" is a failure mode, which only makes sense if
     arguments are references to content rather than the content itself.
     The command reads each required file as UTF-8, calls
     assemble_context_bundle() with the contents, and prints the result to
     stdout with nothing else. Missing required flag or unreadable path:
     non-zero exit, nothing on stdout, the missing/unreadable layer named on
     stderr.

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

# The fast-lane harness plumbing moved to the consumption file; sibling suites
# (1-iii, 1-vi, blank-lines) still reach it through this module as _sibling.
from test_bo2400c_prompt_cache_consumption import (  # noqa: E402, F401
    _BUNDLE_LABEL, _GREEN_LABELS, _call, _labels_ship, _run_ship,
)

_INJECTION_BUILDERS_PY = _SCRIPTS_DIR / "injection_builders.py"


# ===========================================================================
# BO-2400c-1-ii — reachability: a real command that runs
# ===========================================================================

_ARCH_TEXT = "## Architecture\nSTABLE_ARCHITECTURE_MARKER_BO2400C1II — layered repository pattern."
_HL_TEXT = "## L1 AC\nSTABLE_HIGHLEVEL_MARKER_BO2400C1II — the big picture."
_PRIOR_TESTS_TEXT = "## Prior Tests\nVOLATILE_PRIOR_TESTS_MARKER_BO2400C1II."
_DEFAULT_MARKER = "<!-- CACHE_BREAKPOINT -->"

# _CONV_TEXT and _ACS_TEXT are gone (BO-2400c-1-vi): the conventions and acs
# layers no longer exist as CLI flags or as bundle content.


def _write_layer_files(tmp_path: Path) -> dict[str, Path]:
    """Write each required layer's content to a real temp file and return paths.

    BO-2400c-1-vi note: only architecture, high_level and prior_tests remain
    required — conventions and acs are removed.
    """
    layers = {
        "architecture": _ARCH_TEXT,
        "high_level": _HL_TEXT,
        "prior_tests": _PRIOR_TESTS_TEXT,
    }
    paths: dict[str, Path] = {}
    for name, text in layers.items():
        p = tmp_path / f"{name}.md"
        p.write_text(text, encoding="utf-8")
        paths[name] = p
    return paths


def _cli_args(script: Path, paths: dict[str, Path]) -> list[str]:
    """Build the assumed `assemble-bundle` CLI invocation (see module docstring).

    BO-2400c-1-vi note: --conventions and --acs are removed.
    """
    return [
        sys.executable,
        str(script),
        "assemble-bundle",
        "--architecture", str(paths["architecture"]),
        "--high-level", str(paths["high_level"]),
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
        capture_output=True, text=True, encoding="utf-8", timeout=15,
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
    for stable_text in (_ARCH_TEXT, _HL_TEXT):
        assert stable_text in stdout[:marker_idx], (
            f"Stable layer content missing before the breakpoint marker: "
            f"{stable_text!r}. stdout={stdout!r}"
        )
    assert _PRIOR_TESTS_TEXT in stdout[marker_idx:], (
        f"Volatile layer content missing after the breakpoint marker: "
        f"{_PRIOR_TESTS_TEXT!r}. stdout={stdout!r}"
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
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert proc.returncode == 0, f"Expected exit 0. Got {proc.returncode}. stderr={proc.stderr!r}"

    expected = assemble_context_bundle(
        architecture=_ARCH_TEXT,
        high_level=_HL_TEXT,
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
        args_missing_prior_tests, capture_output=True, text=True, encoding="utf-8", timeout=15,
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

    BO-2400c-1-vi note: targets --prior-tests rather than the now-removed
    --acs flag, since acs is no longer part of the layer set this CLI
    accepts.

    RED today: the module ignores all arguments, so it exits 0 with empty
    stdout regardless of whether the named path exists.
    """
    paths = _write_layer_files(tmp_path)
    args = _cli_args(_INJECTION_BUILDERS_PY, paths)
    layer_flag_idx = args.index("--prior-tests") + 1
    args[layer_flag_idx] = str(tmp_path / "does_not_exist.md")

    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=15)
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
        _cli_args(deployed_script, paths), capture_output=True, text=True, encoding="utf-8", timeout=15,
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
