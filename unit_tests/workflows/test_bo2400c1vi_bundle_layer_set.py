"""
MODULE: test_bo2400c1vi_bundle_layer_set
GOAL: RED tests for BO-2400c-1-vi — "The bundle carries only what the
    receiving agent does not already have." Drops the `conventions` and
    `acs` layers from scripts/injection_builders.py's assemble_context_bundle()
    and its `assemble-bundle` CLI subcommand entirely (removed, not defaulted
    to None), pins the architecture-layer source to one verified-existing
    workspace path with no fallback, and adds the "read each build-set id's
    YAML from the run's own acStoreRoot" instruction to the coder dispatch in
    templates/workflows-js/fast-lane-ship.js (the test-writer dispatch already
    carries it).

NEITHER scripts/injection_builders.py NOR templates/workflows-js/fast-lane-ship.js
is touched by this file — python-coder implements the change; this file only
constrains it.

=== Two distinct claims, two distinct executable shapes (per test_rationale) ===

  1. COMPOSITION claim (tests 1-6, 12, 13): which layers the assemble-bundle
     CLI accepts and what its stdout contains. Proved by running
     `python3 scripts/injection_builders.py assemble-bundle ...` as a REAL
     SUBPROCESS over real on-disk layer files and asserting on the actual
     exit code / stdout / stderr. Never asserted via an argument list or a
     grep over source.

  2. INSTRUCTION + NAMED-SOURCE claim (tests 7-11): what a dispatched agent's
     prompt actually says. Proved by EXECUTING the real, on-disk
     templates/workflows-js/fast-lane-ship.js under
     unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() (via
     the plumbing already established in the sibling file
     test_bo2400c_prompt_cache_wiring.py) and asserting on the RECORDED
     dispatch prompts. Never asserted via a grep over fast-lane-ship.js's
     source text.

=== Why the sibling import is deferred, not top-level (load-bearing) ===
Tests 7-11 reuse test_bo2400c_prompt_cache_wiring.py's harness plumbing
(_run_ship, _call, _labels_ship, _BUNDLE_LABEL, _GREEN_LABELS) rather than
duplicating its ~80-key green-baseline label_responses fixture inline
(Fixture Extraction Rule, §2h) — exactly the pattern
test_bo2400c1iii_reference_and_incomplete_states.py already established for
the same file.

That sibling file's own module-scope `_KNOWN_BUNDLE` fixture is, in this same
change, updated (call-site audit, see below) to call
assemble_context_bundle() WITHOUT `conventions=`/`acs=` — matching this AC's
future contract. Against TODAY's unmodified production code (which still
requires both as keyword-only arguments with no default), that call raises
TypeError at MODULE IMPORT time. A top-level `import
test_bo2400c_prompt_cache_wiring as _sibling` in THIS file would therefore
turn that one shared failure into a single collection error for this whole
file, masking which of tests 1-6/12/13 (which need no such import) are
independently red for their own reasons. The import is deferred into a
`_get_sibling()` helper called from inside each of tests 7-11 instead, so:
  - tests 1-6, 12, 13 collect and run normally (pure subprocess + stdlib);
  - tests 7-11 each fail as an ordinary per-test failure (not a collection
    error) with the same TypeError, until python-coder's change lands.

=== Call-site audit (CLAUDE.md "Function Signature Extension — Call-Site
    Audit Required", applied in its REMOVAL direction) ===
Two existing test files call assemble_context_bundle() with conventions=/acs=
and are updated in THIS SAME change to the post-change three-layer
signature, per BO-2400c-1-vi.yaml's it_requirements constraint list:
  - unit_tests/workflows/test_bo2400c_context_bundle.py — every direct call
    rewritten to drop conventions=/acs=; tests whose entire point was the
    removed layer (e.g. "conventions sits in the stable prefix", "acs
    precedes prior_tests") are rewritten against the surviving three-layer
    set rather than deleted, per BO-2400c-1-vi.yaml's own instruction.
  - unit_tests/workflows/test_bo2400c_prompt_cache_wiring.py — the CLI-layer
    helpers (_write_layer_files, _cli_args), the call at
    test_ac2ii_stdout_matches_the_pure_function_output_byte_for_byte, and the
    MODULE-SCOPE `_KNOWN_BUNDLE` call, all updated to the three-layer
    signature; the docstring's spelled-out CLI invocation updated to match.
Both edits are EXPECTED to make their own files red against today's
unmodified production code — that is the point of a call-site audit executed
ahead of the production change: the call sites already assume the contract
this AC establishes, so they go green the moment python-coder removes the
two parameters, and stay red (a real signal, not noise) until then.

Deliberately NOT touched, per BO-2400c-1-vi.yaml's own doc_link: `
templates/workflows-js/fast-lane-build.js` (BO-2400c-1-v's orphaned-runner
removal, unrelated to this criterion — a grep test at
unit_tests/workflows/test_bo2400a_runner_wiring.py:401 pins its current dead
`assemble_context_bundle` reference), and `
unit_tests/workflows/test_bo2400c1iii_reference_and_incomplete_states.py` —
not named in this AC's call-site inventory, but it also imports
test_bo2400c_prompt_cache_wiring.py as `_sibling` and additionally builds its
own module-scope bundles by calling assemble_context_bundle() directly with
conventions=/acs=. Once this file's sibling-module edit lands, that file will
ALSO collection-error until it is updated — a real, out-of-scope
consequence of the shared module's contract change, left for whoever's
surface that file belongs to (it is not part of BO-2400c-1-vi's declared
files_touched).

=== No hand-typed fixture standing in for a real artifact ===
Test 4 writes the worktree's REAL, on-disk CLAUDE.md content (read verbatim,
never paraphrased) to a file that is never referenced by any CLI flag,
because there is no --conventions flag left for it to be passed to. Test 5
does the same with this AC's own real, on-disk YAML record
(docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400c-1-vi.yaml)
standing in for "a real build-set AC record."
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make unit_tests/workflows/ and scripts/ importable regardless
# of cwd, mirroring the sibling files' own convention. No import of
# injection_builders or test_bo2400c_prompt_cache_wiring at module scope —
# see the module docstring's "deferred import" section.
# ---------------------------------------------------------------------------
_WORKFLOWS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _WORKFLOWS_DIR.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_WORKFLOWS_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKFLOWS_DIR))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_INJECTION_BUILDERS_PY = _SCRIPTS_DIR / "injection_builders.py"

_MARKER = "<!-- CACHE_BREAKPOINT -->"

# ---------------------------------------------------------------------------
# Layer content fixtures — plain sentinel strings for the CLI-subprocess
# tests (1-3, 12, 13). Realistic-size fixtures for test 6 are built
# separately below via _repeat_to_size().
# ---------------------------------------------------------------------------
_ARCH_TEXT = "## Architecture\nARCH_SENTINEL_BO2400C1VI"
_HL_TEXT = "## L1 AC\nHL_SENTINEL_BO2400C1VI"
_PRIOR_TESTS_TEXT = "## Prior Tests\nPRIOR_TESTS_SENTINEL_BO2400C1VI"

# Filler content for the two originally-required, now-to-be-removed layers.
# Only used by the OLD (pre-change) five-flag invocation in tests 1 and 2,
# whose whole point is that supplying these flags at all must be rejected.
_CONV_FILLER = "## Conventions\nCONV_FILLER_BO2400C1VI"
_ACS_FILLER = "## L2 ACs\nACS_FILLER_BO2400C1VI"

# The AC record standing in for "a real build-set AC record" (test 5) — this
# very criterion's own on-disk YAML file.
_AC_RECORD_PATH = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "build-orchestration"
    / "BO-2400-fast-lane-build"
    / "BO-2400c-1-vi.yaml"
)
_DISTINCTIVE_AC_RECORD_LINE = (
    'title: "The bundle carries only what the receiving agent does not already have"'
)

# The worktree's own real CLAUDE.md standing in for "the project conventions"
# (test 4) — the harness already injects this file's content into every
# agent dispatched into the worktree (see BO-2400c-1-vi.yaml's own
# duplication-verification note).
_DISTINCTIVE_CLAUDE_LINE = "## Commit Delegation — MANDATORY"


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _old_cli_args(tmp_path: Path) -> list[str]:
    """Build a fully-valid invocation under TODAY's (pre-change) CLI — all
    five originally-required layers supplied.

    Used only by tests 1 and 2 to prove a specific flag is REJECTED once
    removed: every OTHER originally-required flag is present so today's
    still-required flags cannot cause failure for the wrong reason.
    """
    paths = {
        "architecture": _write_text(tmp_path / "architecture.md", _ARCH_TEXT),
        "conventions": _write_text(tmp_path / "conventions.md", _CONV_FILLER),
        "high_level": _write_text(tmp_path / "high_level.md", _HL_TEXT),
        "acs": _write_text(tmp_path / "acs.md", _ACS_FILLER),
        "prior_tests": _write_text(tmp_path / "prior_tests.md", _PRIOR_TESTS_TEXT),
    }
    return [
        sys.executable, str(_INJECTION_BUILDERS_PY), "assemble-bundle",
        "--architecture", str(paths["architecture"]),
        "--conventions", str(paths["conventions"]),
        "--high-level", str(paths["high_level"]),
        "--acs", str(paths["acs"]),
        "--prior-tests", str(paths["prior_tests"]),
    ]


def _write_new_layer_files(tmp_path: Path, **overrides: str) -> dict[str, Path]:
    """Write the POST-CHANGE required layer set (architecture, high_level,
    prior_tests only) to real temp files, honouring any content overrides.
    """
    layers = {
        "architecture": _ARCH_TEXT,
        "high_level": _HL_TEXT,
        "prior_tests": _PRIOR_TESTS_TEXT,
    }
    layers.update(overrides)
    return {
        name: _write_text(tmp_path / f"{name}.md", text)
        for name, text in layers.items()
    }


def _new_cli_args(paths: dict[str, Path]) -> list[str]:
    """Build the POST-CHANGE (three-required-flag) `assemble-bundle` invocation."""
    return [
        sys.executable, str(_INJECTION_BUILDERS_PY), "assemble-bundle",
        "--architecture", str(paths["architecture"]),
        "--high-level", str(paths["high_level"]),
        "--prior-tests", str(paths["prior_tests"]),
    ]


def _repeat_to_size(paragraph: str, target_bytes: int) -> str:
    """Repeat a realistic paragraph until it reaches roughly *target_bytes*."""
    unit = paragraph + "\n\n"
    unit_len = len(unit.encode("utf-8"))
    reps = max(1, target_bytes // unit_len + 1)
    text = unit * reps
    return text[:target_bytes]


_REALISTIC_ARCH_PARAGRAPH = (
    "This component follows a layered repository pattern: the workflow body "
    "dispatches phase agents that read and write only through a single, "
    "explicitly injected context boundary, never through ambient filesystem "
    "access, so every side effect is attributable to a named dispatch."
)
_REALISTIC_HL_PARAGRAPH = (
    "L1: As a build operator, I need the fast lane to assemble only the "
    "context a receiving agent does not already have, so that large batch "
    "runs stay within the agent-return-value transport limit instead of "
    "silently failing to cross the agent boundary intact."
)
_REALISTIC_PRIOR_TESTS_PARAGRAPH = (
    "test_prior_component_behavior_is_covered_by_existing_suite — asserts "
    "that behavior already shipped for this area of the codebase remains "
    "green under the new, smaller context-bundle layer set."
)


# ===========================================================================
# 1-2. The CLI must REJECT the two removed flags outright (not merely stop
#      passing them) — a partial registration (dropping one, not both) fails
#      this criterion.
# ===========================================================================


def test_assemble_bundle_cli_rejects_the_conventions_flag(tmp_path):
    # covers: BO-2400c-1-vi
    """Supplying --conventions (with every other originally-required flag
    present) must be rejected once the parameter is removed from the CLI.

    RED today: --conventions is still a required, accepted argument, so this
    fully-valid old-style invocation exits 0.
    """
    args = _old_cli_args(tmp_path)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc.returncode != 0, (
        "Once --conventions is removed from assemble-bundle's argparse "
        "registration, supplying it must be rejected even though every "
        "other originally-required flag is present. Got exit 0 — the flag "
        f"is still accepted today. stdout={proc.stdout!r}"
    )
    assert "--conventions" in proc.stderr, (
        f"stderr must name the rejected flag. Got stderr={proc.stderr!r}"
    )


def test_assemble_bundle_cli_rejects_the_acs_flag(tmp_path):
    # covers: BO-2400c-1-vi
    """Same as the --conventions test, for --acs. A change that drops one
    flag but not the other is a partial registration and must still fail
    this pair of tests.

    RED today: --acs is still a required, accepted argument, so this
    fully-valid old-style invocation exits 0.
    """
    args = _old_cli_args(tmp_path)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc.returncode != 0, (
        "Once --acs is removed from assemble-bundle's argparse registration, "
        "supplying it must be rejected even though every other "
        "originally-required flag is present. Got exit 0 — the flag is "
        f"still accepted today. stdout={proc.stdout!r}"
    )
    assert "--acs" in proc.stderr, (
        f"stderr must name the rejected flag. Got stderr={proc.stderr!r}"
    )


# ===========================================================================
# 3. The reduced three-flag invocation must succeed on its own.
# ===========================================================================


def test_assemble_bundle_cli_succeeds_with_only_architecture_high_level_and_prior_tests(
    tmp_path,
):
    # covers: BO-2400c-1-vi
    """A real subprocess invocation naming only --architecture, --high-level
    and --prior-tests exits 0 and its stdout carries all three layers plus
    exactly one breakpoint marker.

    RED today: --conventions and --acs are still required, so omitting them
    exits non-zero (missing required arguments) rather than assembling a
    bundle.
    """
    paths = _write_new_layer_files(tmp_path)
    args = _new_cli_args(paths)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc.returncode == 0, (
        "Once --conventions and --acs are removed, an invocation naming only "
        "--architecture, --high-level and --prior-tests must succeed on its "
        f"own. Got exit {proc.returncode} (today's CLI still requires "
        f"--conventions and --acs). stderr={proc.stderr!r}"
    )
    stdout = proc.stdout
    assert stdout.count(_MARKER) == 1, (
        f"Expected exactly one breakpoint marker in stdout. "
        f"Found {stdout.count(_MARKER)}. stdout={stdout!r}"
    )
    marker_idx = stdout.index(_MARKER)
    for stable_text in (_ARCH_TEXT, _HL_TEXT):
        assert stable_text in stdout[:marker_idx], (
            f"Stable layer content missing before the breakpoint marker: "
            f"{stable_text!r}. stdout={stdout!r}"
        )
    assert _PRIOR_TESTS_TEXT in stdout[marker_idx:], (
        f"Volatile layer content missing after the breakpoint marker: "
        f"{_PRIOR_TESTS_TEXT!r}. stdout={stdout!r}"
    )


# ===========================================================================
# 4-5. The bundle must omit the two largest duplicates: project conventions
#      and the build set's own AC YAML text.
# ===========================================================================


def test_bundle_stdout_omits_the_project_conventions_text(tmp_path):
    # covers: BO-2400c-1-vi
    """The worktree's real, on-disk CLAUDE.md content is written to a file
    that no CLI flag ever references (there is no --conventions flag left to
    pass it to), and a distinctive line from it is absent from the actual
    stdout of a real subprocess run.

    RED today: this assertion chain first requires the reduced three-flag
    invocation to succeed at all — it does not, because --conventions and
    --acs are still required (same underlying cause as test 3). Once fixed,
    the assertion also proves CLAUDE.md's content — which the harness
    already injects into every dispatched agent — is not duplicated into the
    bundle a second time.
    """
    claude_md_text = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert _DISTINCTIVE_CLAUDE_LINE in claude_md_text, (
        "Fixture guard: the distinctive CLAUDE.md line moved or was edited — "
        "update _DISTINCTIVE_CLAUDE_LINE to a line that still exists."
    )
    # Written to disk but never referenced by any CLI argument below.
    _write_text(tmp_path / "conventions_unused.md", claude_md_text)

    paths = _write_new_layer_files(tmp_path)
    args = _new_cli_args(paths)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc.returncode == 0, (
        f"Expected the reduced 3-layer invocation to succeed. Got "
        f"{proc.returncode}. stderr={proc.stderr!r}"
    )
    assert _DISTINCTIVE_CLAUDE_LINE not in proc.stdout, (
        "The project conventions text (CLAUDE.md) — the single largest "
        "duplicate the harness already injects into every dispatched agent "
        f"— must never appear in the assembled bundle. stdout={proc.stdout!r}"
    )


def test_bundle_stdout_omits_the_build_sets_own_ac_yaml_text(tmp_path):
    # covers: BO-2400c-1-vi
    """This AC's own real, on-disk YAML record (standing in for "a real
    build-set AC record") is written to a file no CLI flag ever references,
    and a distinctive line from it is absent from the actual stdout.

    RED today: same underlying cause as test 3/4 — the reduced invocation
    does not yet succeed because --conventions and --acs are still required.
    """
    ac_record_text = _AC_RECORD_PATH.read_text(encoding="utf-8")
    assert _DISTINCTIVE_AC_RECORD_LINE in ac_record_text, (
        "Fixture guard: the distinctive AC-record line moved or was edited — "
        "update _DISTINCTIVE_AC_RECORD_LINE to a line that still exists."
    )
    _write_text(tmp_path / "acs_unused.yaml", ac_record_text)

    paths = _write_new_layer_files(tmp_path)
    args = _new_cli_args(paths)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc.returncode == 0, (
        f"Expected the reduced 3-layer invocation to succeed. Got "
        f"{proc.returncode}. stderr={proc.stderr!r}"
    )
    assert _DISTINCTIVE_AC_RECORD_LINE not in proc.stdout, (
        "The build set's own AC YAML text must never appear in the "
        "assembled bundle — each context-carrying dispatch instead tells "
        "its agent to open each id's record directly in the run's own "
        f"store. stdout={proc.stdout!r}"
    )


# ===========================================================================
# 6. Smallness is compositional, not a cap.
# ===========================================================================


def test_realistic_inputs_produce_a_bundle_on_the_order_of_twenty_kilobytes(tmp_path):
    # covers: BO-2400c-1-vi
    """Over realistic-sized layer content (sized to the byte breakdown
    measured on the run that failed: architecture 7,617 + high_level 7,105 +
    prior_tests 4,955 bytes), the assembled bundle's stdout lands on the
    order of twenty kilobytes — an order of magnitude, not an exact count,
    and never enforced by any cap or truncation step in the code.

    RED today: same underlying cause as test 3 — the reduced invocation does
    not yet succeed.
    """
    arch_text = _repeat_to_size(_REALISTIC_ARCH_PARAGRAPH, 7_600)
    hl_text = _repeat_to_size(_REALISTIC_HL_PARAGRAPH, 7_100)
    prior_tests_text = _repeat_to_size(_REALISTIC_PRIOR_TESTS_PARAGRAPH, 4_950)

    paths = _write_new_layer_files(
        tmp_path,
        architecture=arch_text,
        high_level=hl_text,
        prior_tests=prior_tests_text,
    )
    args = _new_cli_args(paths)
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc.returncode == 0, (
        f"Expected the reduced 3-layer invocation to succeed. Got "
        f"{proc.returncode}. stderr={proc.stderr!r}"
    )
    size = len(proc.stdout.encode("utf-8"))
    assert 5_000 < size < 40_000, (
        "For realistic layer content, the assembled bundle must land on the "
        "order of twenty kilobytes (conventions 38,291 + acs 90,887 bytes "
        f"REMOVED), nowhere near the prior ~150 KB scale. Got {size} bytes. "
        "This must be a CONSEQUENCE of the layer set, never a cap, "
        "truncation, or summarisation step added to hit this number."
    )


# ===========================================================================
# 12. A named source that cannot be opened ends the assembly naming it — no
#     partial bundle, no substitution.
# ===========================================================================


def test_unreadable_architecture_layer_ends_the_assembly_naming_that_path(tmp_path):
    # covers: BO-2400c-1-vi
    """Pointing --architecture at a path that does not exist exits non-zero,
    names both the layer and the path on stderr, and prints nothing to
    stdout.

    RED today: with --conventions and --acs omitted (the future contract),
    today's CLI reports THOSE as the missing required arguments before ever
    reaching the architecture file-read step, so stderr does not (yet)
    reliably name 'architecture' and the missing path together.
    """
    missing_path = tmp_path / "does_not_exist_architecture.md"
    paths = _write_new_layer_files(tmp_path)
    args = _new_cli_args(paths)
    arch_flag_idx = args.index("--architecture") + 1
    args[arch_flag_idx] = str(missing_path)

    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc.returncode != 0, (
        f"An unreadable --architecture path must exit non-zero. Got exit 0. "
        f"stdout={proc.stdout!r}"
    )
    assert not proc.stdout.strip(), (
        f"Must never print a partial bundle to stdout when a layer is "
        f"unreadable. Got stdout={proc.stdout!r}"
    )
    stderr_lower = proc.stderr.lower()
    assert "architecture" in stderr_lower, (
        f"stderr must name the failing layer ('architecture'). "
        f"Got stderr={proc.stderr!r}"
    )
    assert str(missing_path) in proc.stderr, (
        f"stderr must name the unreadable path itself. Got stderr={proc.stderr!r}"
    )


# ===========================================================================
# 13. BO-2400c-1-iv survives the cut: the stable prefix (now architecture +
#     high_level + marker) is byte-identical across two runs.
# ===========================================================================


def test_same_inputs_produce_a_byte_identical_stable_prefix_across_two_runs(tmp_path):
    # covers: BO-2400c-1-vi
    """Two real subprocess invocations over identical inputs yield a
    byte-identical prefix up to and including the breakpoint marker.

    RED today: with --conventions and --acs omitted (the future contract),
    neither run exits 0 today, so the exit-code assertions fail before any
    prefix is even compared.
    """
    paths = _write_new_layer_files(tmp_path)
    args = _new_cli_args(paths)

    proc1 = subprocess.run(args, capture_output=True, text=True, timeout=15)
    proc2 = subprocess.run(args, capture_output=True, text=True, timeout=15)

    assert proc1.returncode == 0, (
        f"Run 1: expected exit 0. Got {proc1.returncode}. stderr={proc1.stderr!r}"
    )
    assert proc2.returncode == 0, (
        f"Run 2: expected exit 0. Got {proc2.returncode}. stderr={proc2.stderr!r}"
    )
    assert proc1.stdout.count(_MARKER) == 1, (
        f"Run 1 must contain exactly one breakpoint marker. stdout={proc1.stdout!r}"
    )
    assert proc2.stdout.count(_MARKER) == 1, (
        f"Run 2 must contain exactly one breakpoint marker. stdout={proc2.stdout!r}"
    )

    prefix1 = proc1.stdout[: proc1.stdout.index(_MARKER) + len(_MARKER)]
    prefix2 = proc2.stdout[: proc2.stdout.index(_MARKER) + len(_MARKER)]
    assert prefix1 == prefix2, (
        "The stable prefix (architecture + high_level + marker) must be "
        "byte-identical across two invocations over identical inputs — "
        "BO-2400c-1-iv's property must survive the loss of the conventions "
        f"layer.\nRun 1 prefix: {prefix1!r}\nRun 2 prefix: {prefix2!r}"
    )


# ===========================================================================
# 7-11. Instruction + named-source claims — proved by EXECUTING the real,
#       on-disk fast-lane-ship.js under the E2 harness, never by grepping it.
# ===========================================================================


def _get_sibling():
    """Lazily import test_bo2400c_prompt_cache_wiring's harness plumbing.

    Deferred (not top-level) so that its module-scope `_KNOWN_BUNDLE`
    fixture — itself updated in this same change to the post-change
    three-layer signature — failing against today's unmodified production
    code raises inside EACH calling test individually, rather than
    collection-erroring this entire file. See the module docstring's
    "deferred import" section.
    """
    workflows_dir = Path(__file__).resolve().parent
    if str(workflows_dir) not in sys.path:
        sys.path.insert(0, str(workflows_dir))
    import test_bo2400c_prompt_cache_wiring as sibling  # noqa: PLC0415

    return sibling


def test_coder_dispatch_prompt_tells_the_agent_to_read_each_record_from_the_store():
    # covers: BO-2400c-1-vi
    """Executed under the E2 harness, the recorded coder dispatch's prompt
    instructs the agent to open each build-set id's YAML record in the run's
    own acStoreRoot — the instruction the test-writer dispatch already
    carries.

    RED today: fast-lane-ship.js's coder dispatch prompt carries no such
    instruction at all — only the test-writer dispatch does.
    """
    sibling = _get_sibling()
    result = sibling._run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    coder_call = sibling._call(result, "coder-connected")
    assert coder_call is not None, (
        f"Expected the coder dispatch to execute. "
        f"Labels: {sibling._labels_ship(result)}"
    )
    prompt = coder_call.prompt
    assert isinstance(prompt, str), f"coder prompt must be a string. Got: {type(prompt)}"

    store_root = (
        f"{sibling._GREEN_LABELS['fastlane-worktree']['worktree_path']}"
        f"/docs/acceptance-criteria"
    )
    assert "read its YAML from" in prompt, (
        "The coder dispatch prompt must instruct the agent to open each "
        "build-set id's own YAML record in the run's acStoreRoot — the "
        "instruction the test-writer dispatch already carries. "
        f"Prompt (first 800 chars): {prompt[:800]!r}"
    )
    assert store_root in prompt, (
        f"The instruction must name the run's own AC store root "
        f"({store_root!r}). Prompt (first 800 chars): {prompt[:800]!r}"
    )


def test_test_writer_dispatch_prompt_still_carries_the_read_from_store_instruction():
    # covers: BO-2400c-1-vi
    """The instruction the test-writer dispatch already carries survives the
    change. Asserting only the coder side (test 7) would let a refactor MOVE
    the instruction rather than ADD it.

    Allowed to pass today: the test-writer prompt already carries this
    instruction (fast-lane-ship.js line ~949). This test's job is to catch a
    regression that removes or relocates it while fixing test 7.
    """
    sibling = _get_sibling()
    result = sibling._run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    tw_call = sibling._call(result, "test-writer-connected")
    assert tw_call is not None, (
        f"Expected the test-writer dispatch to execute. "
        f"Labels: {sibling._labels_ship(result)}"
    )
    prompt = tw_call.prompt
    assert isinstance(prompt, str), (
        f"test-writer prompt must be a string. Got: {type(prompt)}"
    )

    store_root = (
        f"{sibling._GREEN_LABELS['fastlane-worktree']['worktree_path']}"
        f"/docs/acceptance-criteria"
    )
    assert "read its YAML from" in prompt, (
        "The test-writer dispatch must keep telling the agent to open each "
        "build-set id's own YAML record in the run's acStoreRoot — this "
        "instruction must SURVIVE the change, not merely relocate to the "
        f"coder dispatch. Prompt (first 800 chars): {prompt[:800]!r}"
    )
    assert store_root in prompt, (
        f"The instruction must name the run's own AC store root "
        f"({store_root!r}). Prompt (first 800 chars): {prompt[:800]!r}"
    )


def test_bundle_dispatch_prompt_asks_for_no_conventions_and_no_acs_layer():
    # covers: BO-2400c-1-vi
    """The RECORDED bundle-assembling dispatch prompt no longer asks for a
    'conventions' or 'acs' layer, and its Step 2 command line no longer
    passes --conventions or --acs.

    RED today: the prompt's Step 1 layer list still asks for both, and its
    Step 2 command still passes both flags.
    """
    sibling = _get_sibling()
    result = sibling._run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    bundle_call = sibling._call(result, sibling._BUNDLE_LABEL)
    assert bundle_call is not None, (
        f"Expected the bundle-assembling dispatch to execute. "
        f"Labels: {sibling._labels_ship(result)}"
    )
    prompt = bundle_call.prompt
    assert isinstance(prompt, str), (
        f"Bundle dispatch prompt must be a string. Got: {type(prompt)}"
    )

    assert "--conventions" not in prompt, (
        "The bundle-assembling dispatch's Step 2 command must no longer "
        f"pass --conventions. Prompt (first 1200 chars): {prompt[:1200]!r}"
    )
    assert "--acs" not in prompt, (
        "The bundle-assembling dispatch's Step 2 command must no longer "
        f"pass --acs. Prompt (first 1200 chars): {prompt[:1200]!r}"
    )
    assert re.search(r"-\s*conventions\s*:", prompt) is None, (
        "The Step 1 layer list must no longer ask for a 'conventions' "
        f"layer. Prompt (first 1200 chars): {prompt[:1200]!r}"
    )
    assert re.search(r"-\s*acs\s*:", prompt) is None, (
        "The Step 1 layer list must no longer ask for an 'acs' layer. "
        f"Prompt (first 1200 chars): {prompt[:1200]!r}"
    )


_REAL_WORKTREE_LABEL = {
    "worktree_path": str(_REPO_ROOT),
    "branch": "fast-lane/bo2400c1vi-real-worktree-probe",
    "ac_store_path": str(_REPO_ROOT / "docs" / "acceptance-criteria"),
    "created": True,
}


def _extract_architecture_path(prompt: str, worktree_path: str) -> str:
    """Pull the literal architecture-layer path out of *prompt*, rooted at
    *worktree_path*/docs/architecture/.
    """
    pattern = re.escape(worktree_path) + r"/docs/architecture/[^\s,]+"
    match = re.search(pattern, prompt)
    assert match is not None, (
        f"Could not find an architecture path rooted at "
        f"{worktree_path}/docs/architecture/ in the bundle dispatch prompt. "
        f"Prompt (first 1200 chars): {prompt[:1200]!r}"
    )
    return match.group(0)


def test_named_architecture_path_resolves_in_the_workspace():
    # covers: BO-2400c-1-vi
    """With the harness's worktree stub pointed at this REAL, on-disk
    worktree (so a resolvable path is even possible), the architecture path
    named in the recorded bundle dispatch prompt must actually exist.

    RED today: the prompt names ${worktreePath}/docs/architecture/README.md,
    which does not exist here — docs/architecture/ holds adrs/, components/,
    diagrams/ and four loose documents, no README.md.
    """
    sibling = _get_sibling()
    result = sibling._run_ship(
        extra_labels={"fastlane-worktree": _REAL_WORKTREE_LABEL}
    )
    assert result.error == "", f"Harness error: {result.error}"

    bundle_call = sibling._call(result, sibling._BUNDLE_LABEL)
    assert bundle_call is not None, (
        f"Expected the bundle-assembling dispatch to execute. "
        f"Labels: {sibling._labels_ship(result)}"
    )
    prompt = bundle_call.prompt
    assert isinstance(prompt, str), (
        f"Bundle dispatch prompt must be a string. Got: {type(prompt)}"
    )

    architecture_path = _extract_architecture_path(prompt, str(_REPO_ROOT))
    assert os.path.exists(architecture_path), (
        f"The prompt names {architecture_path!r}, which does not exist in "
        f"the real worktree ({_REPO_ROOT}). The named architecture path "
        "must resolve, exactly, with no fallback to a nearest equivalent."
    )


def test_bundle_dispatch_prompt_offers_no_fallback_for_a_missing_architecture_path():
    # covers: BO-2400c-1-vi
    """The recorded bundle dispatch prompt carries no nearest-equivalent,
    if-absent, or substitute instruction for any layer source. A layer
    chosen by judgement makes two runs at the same target incomparable.

    RED today: the prompt's architecture bullet explicitly says "or the
    nearest architecture index if that exact path does not exist".
    """
    sibling = _get_sibling()
    result = sibling._run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    bundle_call = sibling._call(result, sibling._BUNDLE_LABEL)
    assert bundle_call is not None, (
        f"Expected the bundle-assembling dispatch to execute. "
        f"Labels: {sibling._labels_ship(result)}"
    )
    prompt = bundle_call.prompt
    assert isinstance(prompt, str), (
        f"Bundle dispatch prompt must be a string. Got: {type(prompt)}"
    )

    lower = prompt.lower()
    forbidden_phrases = (
        "nearest architecture index",
        "nearest equivalent",
        "if that exact path does not exist",
        "if absent",
        "substitute",
    )
    hits = [phrase for phrase in forbidden_phrases if phrase in lower]
    assert not hits, (
        f"The prompt still offers a fallback/substitute instruction for a "
        f"layer source ({hits}). A layer chosen by judgement differs "
        "between two runs aimed at the same target, so the same target "
        "stops producing the same bundle and no comparison across runs "
        f"means anything. Prompt (first 1200 chars): {prompt[:1200]!r}"
    )
