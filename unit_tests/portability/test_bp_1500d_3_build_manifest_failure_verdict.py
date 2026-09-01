"""
MODULE: unit_tests/portability/test_bp_1500d_3_build_manifest_failure_verdict.py
GOAL: BP-1500d-3 -- a build that cannot produce the build-manifest record for
    an out-of-package target must FAIL (non-zero process exit status), not
    print one warning line and report success. This is the enforcement floor
    for BP-1500d's whole guarantee: "(a) through (c) implemented over a build
    that still exits zero when it gives up leaves the whole family
    unenforceable, silently, exactly as today."

FAIL-OPEN SITE (named by the AC's own doc_links, confirmed still current at
    authoring time, 2026-09-01 -- ``grep -n "except Exception" scripts/
    build_helpers.py`` puts it at lines ~1046-1066, not the ~201-213 the AC
    text cites; the file has grown since the AC was written):

        scripts/build_helpers.py, write_build_manifest():
            try:
                output_mappings = _compute_output_mappings(...)
            except Exception as exc:  # noqa: BLE001
                output_mappings_error = f"{type(exc).__name__}: {exc}"
                warnings.warn(f"could not compute output_mappings: {exc}. "
                               "Direction B detection will be unavailable "
                               "until next build.", stacklevel=2)
                _warn(...)
            # falls through -- manifest is written with output_mappings={}
            # and write_build_manifest() returns normally either way.

    build.py's main() (scripts/build.py) never inspects
    write_build_manifest()'s outcome at all -- the call site is a bare
    statement whose return value (None) is discarded, and main() returns 0
    unconditionally afterwards (confirmed by reading scripts/build.py lines
    2086-2138: no branch anywhere reads output_mappings_error). The process
    exit status is therefore NEVER a function of whether the record could be
    produced, which is exactly the guarantee (d) this AC exists to close.

REPRODUCTION (empirically measured against a REAL subprocess run of THIS
    worktree's own scripts/build.py on 2026-09-01, not read from source):
    when ``package_root`` (derived from ``build.py``'s own ``__file__``) is
    NOT an ancestor of ``target_root`` (the ``--target-dir`` argument) --
    i.e. a real, plausible misuse where a developer runs a checked-out
    ``leafcutter-ai/scripts/build.py`` against some unrelated project
    directory without first placing the package under that project --
    ``_compute_output_mappings()``'s per-template
    ``template_path.relative_to(repo_root)`` (repo_root == target_root)
    raises ``ValueError: '<template path>' is not in the subpath of
    '<target_root>'``. The caught exception is downgraded to a warning,
    ``output_mappings`` is written as an empty dict (0 entries, versus ~470
    for the same package built into its own correctly-nested target), and
    the process still exits 0.

ARCHITECTURE / EXERCISE STRATEGY (BP-1500d's mandatory proof shape):
    Every test below builds a REAL, on-disk synthetic package copy (real
    ``templates/``, ``scripts/``, ``config/`` and ``docs/product-truth/``
    trees copied byte-for-byte from this worktree -- never paraphrased) into
    a ``tmp_path``-rooted scratch tree that has NOTHING to do with this
    worktree's own parent directory, and invokes the REAL
    ``scripts/build.py`` as a REAL subprocess through its actual CLI
    (``python <pkg>/scripts/build.py --target-dir <target>``) -- never by
    importing and calling ``write_build_manifest()`` directly. The verdict
    asserted on is the child process's own ``returncode``, because that is
    the only thing an automated caller (a CI step, a shell script, an
    install wizard) ever sees. This satisfies BP-1500d's mandate that every
    child AC be "provable by running a REAL build into a project directory
    located OUTSIDE the producing package's own parent folder" -- reading
    build.py's source for the presence of the try/except above would NOT
    satisfy it, which is why this file never imports build_helpers.

    ``docs/product-truth`` is copied alongside the three usual trees because
    ``build_phases.py``'s ``build_product_truth`` phase declares that source
    directory outside ``templates/``/``scripts/``/``config/``; omitting it
    makes an unrelated deploy phase raise ``DeployDeclarationError`` against
    every synthetic package this file builds, which would corrupt every
    verdict below with a failure this AC does not own. This mirrors (and, if
    the real ``build_phases.py`` ever adds a new such declared directory,
    should be re-derived the same way as)
    ``unit_tests/build_guards/test_bp_100k_2.py``'s
    ``_derive_extra_package_dirs()`` -- duplicated here in miniature (see
    ``_extra_package_dirs()`` below) rather than imported cross-test-module,
    since importing a private helper from a sibling test file is fragile.

    Neither the synthetic package copy nor the scratch target directory is a
    git repository. This is deliberate, not an oversight: ``build.py``'s own
    three preflight guards (``_check_script_reference_guard``,
    ``_check_tracked_source_guard``, ``_check_intra_package_closure_guard``)
    are read directly (2026-09-01) and confirmed to no-op gracefully outside
    a git work-tree (``_check_tracked_source_guard`` explicitly logs "is not
    a git repository -- skipping" and returns 0), so a non-git copy exercises
    exactly the output_mappings defect this AC owns without an unrelated
    guard producing a confounding non-zero exit for the wrong reason. This
    was verified empirically, not assumed: a real build into the correctly-
    nested (non-out-of-package) layout of the SAME synthetic copy was probed
    first and confirmed to exit 0 with ~470 non-empty output_mappings
    entries and an empty ``output_mappings_error`` before any assertion
    below was written, so a future "record IS producible" run failing here
    is attributable to a regression in this AC's own target, not to an
    unrelated guard tripping on the non-git fixture.

RED BASELINE (measured 2026-09-01, before any production-code change, via
    a real subprocess run of this worktree's own scripts/build.py against a
    real synthetic out-of-package copy):
    - Exit code observed: 0 (test 1 asserts != 0 -- RED).
    - stdout contained: "[WARNING] could not compute output_mappings:
      '<pkg>/templates/agents/README.md' is not in the subpath of
      '<target>'. Direction B detection will be unavailable until next
      build." -- names both output_mappings (the record) and the exact
      target directory path (the project), so test 3's message-content
      assertion is expected to PASS today; only the exit-code and
      exit-code-attribution assertions (tests 1, 2's exit-code half, and 4's
      run-1/run-3 legs) are expected RED. This is intentional and matches
      the AC's own test_rationale: "entries 1 and 3 are deliberately
      separate ... a build can satisfy either one alone."
    - ``.build_manifest.json``: ``output_mappings == {}`` (0 entries),
      ``output_mappings_error == "ValueError: '<pkg>/templates/agents/
      README.md' is not in the subpath of '<target>'"``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CONFIG_DIR = _REPO_ROOT / "config"
_CI_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

_SUBPROCESS_TIMEOUT_SECONDS = 120

# Mirrors unit_tests/build_guards/test_bp_100k_2.py's
# _derive_extra_package_dirs() in miniature: PACKAGE_ROOT / "seg1" / "seg2"
# chains declared by build_phases.py outside templates/scripts/config, kept
# only when they resolve to a real on-disk directory. Verified against this
# repo on 2026-09-01: yields exactly ["docs/product-truth"].
_PACKAGE_ROOT_CHAIN_RE = re.compile(r'PACKAGE_ROOT\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"')
_ALREADY_COPIED_TOP_LEVEL = frozenset({"templates", "scripts", "config"})


def _extra_package_dirs() -> list[str]:
    """Derive extra top-level source dirs a synthetic package copy must carry.

    Returns:
        Repo-relative "seg1/seg2" directory strings declared by the real
        build_phases.py outside templates/scripts/config, deduplicated, in
        first-seen order.
    """
    build_phases_src = _SCRIPTS_DIR / "build_phases.py"
    text = build_phases_src.read_text(encoding="utf-8")
    derived: dict[str, None] = {}
    for first, second in _PACKAGE_ROOT_CHAIN_RE.findall(text):
        if first in _ALREADY_COPIED_TOP_LEVEL:
            continue
        if not (_REPO_ROOT / first / second).is_dir():
            continue
        derived[f"{first}/{second}"] = None
    return list(derived)


def _copy_package(dest_pkg_root: Path) -> Path:
    """Copy real templates/, scripts/, config/, and declared extra dirs.

    Never paraphrases: every file is a byte-for-byte copy of this worktree's
    own real package trees (BP-1100f-2 real-artifact mandate). The resulting
    directory is deliberately NOT a git repository -- see module docstring
    for why that is required, not incidental, to this AC's reproduction.

    Args:
        dest_pkg_root: Absolute path (need not exist yet) to build the
            synthetic package copy at.

    Returns:
        dest_pkg_root, for chaining.
    """
    shutil.copytree(_TEMPLATES_DIR, dest_pkg_root / "templates", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_SCRIPTS_DIR, dest_pkg_root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_CONFIG_DIR, dest_pkg_root / "config", ignore=shutil.ignore_patterns("__pycache__"))
    for rel in _extra_package_dirs():
        shutil.copytree(_REPO_ROOT / rel, dest_pkg_root / rel, ignore=shutil.ignore_patterns("__pycache__"))
    return dest_pkg_root


def _run_build(pkg_root: Path, target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the REAL scripts/build.py of *pkg_root* as a real subprocess.

    This is the production entry point (BP-1500d-3's "reachability" angle):
    a caller of this function sees exactly what an automated CI step or a
    developer's shell sees -- a returncode and captured stdout/stderr --
    never an in-process function call into write_build_manifest().

    Args:
        pkg_root: Absolute path to a synthetic (or real) package root
            containing scripts/build.py.
        target_dir: Absolute path to pass as --target-dir. Need not be an
            ancestor of pkg_root -- that relationship is exactly what each
            test below varies.

    Returns:
        The completed subprocess result (returncode, stdout, stderr).
    """
    return subprocess.run(
        [sys.executable, str(pkg_root / "scripts" / "build.py"), "--target-dir", str(target_dir)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _read_manifest(target_dir: Path) -> dict:
    """Read and parse .build_manifest.json from *target_dir*.

    Args:
        target_dir: The --target-dir a build was run against.

    Returns:
        Parsed manifest dict.
    """
    import json

    manifest_path = target_dir / ".build_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Shared, MODULE-scoped fixtures.
#
# PERFORMANCE NOTE (binding on this file): the fast-lane red-baseline gate
# (.leafcutter/scripts/build_orchestration/fast_lane.py verify_red_baseline)
# reuses done_proof.py's _run_pytest_and_parse(), which runs every
# `# covers:`-tagged test file for an AC under a HARD, non-configurable
# 60-second subprocess timeout (scripts/ac_store/done_proof.py, line ~900).
# A single real `build.py` subprocess run against a full synthetic package
# copy costs roughly 8-30s depending on OS filesystem cache state, so naively
# giving tests 1-3 below their OWN independent build invocation (as an
# earlier draft of this file did) cost 3 full runs for what is, from the
# build's point of view, the IDENTICAL scenario (out-of-package target, same
# package content) -- and blew the 60s budget when run through the gate
# (confirmed empirically: `verify_red_baseline` timed out and reported
# `"reason": "no_red_outcome_among_new_tests"` even though every test failed
# for the correct reason when run directly). Tests 1-3 therefore share ONE
# real build invocation via the module-scoped `_fail_run` fixture below;
# only test 4 (the attribution control, which genuinely needs to observe the
# SAME out-of-package project both fail and then succeed) pays for
# additional real build invocations. This is a fixture-sharing decision
# about wall-clock cost, not a weakening of any assertion: each consuming
# test still asserts against a REAL subprocess CompletedProcess, never a
# mock.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _outside_pkg_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build ONE synthetic package copy, outside any target dir's own tree.

    Shared (read-only) across every test in this module -- never mutated
    by a consumer. Building it once instead of per-test avoids repeating a
    multi-second ``shutil.copytree`` of templates/scripts/config/docs-
    product-truth for every one of the four tests below.
    """
    root = tmp_path_factory.mktemp("bp1500d3_outside_pkg") / "leafcutter-ai"
    return _copy_package(root)


@pytest.fixture(scope="module")
def _fail_run(
    _outside_pkg_root: Path, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    """Run the REAL build.py ONCE against an out-of-package target.

    Shared across tests 1-3, which all assert different facts about this
    SAME real subprocess result (exit code, CI-consumption, and report
    content respectively) -- see the PERFORMANCE NOTE above for why sharing
    this one real run is required to fit the fast-lane gate's fixed 60s
    budget.

    Returns:
        (target_dir, CompletedProcess) -- target_dir so consumers can read
        back .build_manifest.json.
    """
    target_dir = tmp_path_factory.mktemp("bp1500d3_fail_target")
    result = _run_build(_outside_pkg_root, target_dir)
    return target_dir, result


def test_bp_1500d_3_build_exits_nonzero_when_the_record_cannot_be_produced_for_an_out_of_package_target(
    _fail_run: tuple[Path, subprocess.CompletedProcess[str]],
) -> None:
    """AC BP-1500d-3: the primary assertion, and it is on the exit code.

    Given a real build whose package is copied to a location that is NOT an
    ancestor of --target-dir (an out-of-package target, per the AC's own
    reproduction), when the build runs to completion, then the process must
    exit non-zero. THIS ENTRY IS EXPECTED RED TODAY: build.py's real exit
    status is 0 regardless of whether output_mappings could be computed --
    see module docstring RED BASELINE. Do NOT retarget this assertion onto
    the warning string or the output_mappings entry count if it is ever
    inconvenient; per the AC's own test_rationale, exit-0-on-failure IS the
    defect, and any assertion satisfied by today's broken build reintroduces
    it into the specification.
    """
    # covers: BP-1500d-3
    # angle: criterion
    target_dir, result = _fail_run

    assert result.returncode != 0, (
        "build.py exited 0 for an out-of-package target whose "
        ".build_manifest.json output_mappings record could not be "
        "produced -- this is BP-1500d-3's defect: a build that could not "
        "produce the record must fail, not warn once and report success.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # Supporting signal only (per test_rationale, never the primary
    # assertion): the manifest itself should show the whole-computation
    # failure recorded as data.
    manifest = _read_manifest(target_dir)
    assert manifest.get("output_mappings") == {}, (
        "setup sanity: expected an empty output_mappings for the "
        f"out-of-package target. Got {len(manifest.get('output_mappings', {}))} "
        "entries -- the reproduction may no longer trigger the fail-open path."
    )
    assert manifest.get("output_mappings_error"), (
        "setup sanity: expected a non-empty output_mappings_error naming "
        "the ValueError -- the reproduction may no longer trigger the "
        "fail-open path."
    )


def test_bp_1500d_3_the_verdict_is_taken_from_the_real_build_command_line_and_reaches_an_automated_caller(
    _fail_run: tuple[Path, subprocess.CompletedProcess[str]],
) -> None:
    """AC BP-1500d-3: production entry point, plus the consumption half.

    Reads returncode from the SAME real subprocess CompletedProcess the
    shared `_fail_run` fixture produced by invoking the build through the
    exact command line a consumer or a CI step runs -- never by importing
    write_build_manifest or calling an internal step. Then asserts the
    consumption half at every in-repo CI caller: parses
    .github/workflows/ci.yml as YAML (never grepped as text) and asserts
    every step invoking build.py neither carries continue-on-error: true
    nor pipes the build into a command that could mask its exit status. A
    grep for the script name is green on a step that ignores the exit code
    -- that is the defect one level up from this AC's own subject, and
    parsing the workflow as a data structure is what this repo's
    "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep" convention
    demands instead.

    The exit-code half is EXPECTED RED today for the same reason as the
    first test above (build.py always exits 0). The YAML-consumption half
    is expected to PASS today (ci.yml's three build.py steps currently carry
    no continue-on-error and pipe into nothing) -- which is exactly the
    point: today, a correctly-propagating CI step still cannot catch this
    defect, because the thing it propagates (build.py's exit status) is
    itself always 0.
    """
    # covers: BP-1500d-3
    # angle: reachability
    _target_dir, result = _fail_run

    assert result.returncode != 0, (
        "An automated caller reading only build.py's process exit status "
        "(e.g. a CI step, `$?` in a shell script) would conclude the build "
        "succeeded even though the output_mappings record could not be "
        f"produced for this out-of-package target.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert _CI_WORKFLOW_PATH.is_file(), (
        f"Expected the real CI workflow at {_CI_WORKFLOW_PATH} -- if it has "
        "moved, update _CI_WORKFLOW_PATH."
    )
    workflow = yaml.safe_load(_CI_WORKFLOW_PATH.read_text(encoding="utf-8"))

    build_steps: list[dict] = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            run_cmd = step.get("run")
            if isinstance(run_cmd, str) and "build.py" in run_cmd and "--target-dir" in run_cmd:
                build_steps.append(step)

    assert build_steps, (
        "Expected at least one CI step invoking `build.py ... --target-dir` "
        f"in {_CI_WORKFLOW_PATH} -- found none in the parsed workflow steps."
    )

    for step in build_steps:
        assert step.get("continue-on-error") is not True, (
            f"CI step {step.get('name')!r} invokes build.py with "
            "continue-on-error: true -- this masks build.py's exit status "
            "from the job's own verdict, defeating BP-1500d-3's guarantee "
            "one level up even after build.py's own exit code is fixed."
        )
        run_cmd = step["run"]
        assert "|" not in run_cmd and "||" not in run_cmd, (
            f"CI step {step.get('name')!r} pipes build.py's invocation "
            f"into another command ({run_cmd!r}), which can mask its real "
            "exit status."
        )


def test_bp_1500d_3_the_failure_report_names_the_record_and_the_project_the_build_was_aimed_at(
    _fail_run: tuple[Path, subprocess.CompletedProcess[str]],
) -> None:
    """AC BP-1500d-3: the report clause, asserted separately from the outcome clause.

    The criteria separate "the build reports failure" (the outcome, tested
    above) from "the report names the record ... and the project" (the
    message), and a build can satisfy either alone -- so this is its own
    test, not a second assertion bolted onto the first. Reads the SAME real
    subprocess CompletedProcess the shared `_fail_run` fixture produced and
    asserts its combined output names BOTH the unproducible record
    (output_mappings) AND the exact out-of-package target directory path,
    so a reader knows which install is unprotected without re-running
    anything.
    """
    # covers: BP-1500d-3
    # angle: criterion
    target_dir, result = _fail_run
    combined = result.stdout + result.stderr

    assert "output_mappings" in combined, (
        "Expected the failure report to name the record that could not be "
        f"produced (output_mappings). Combined output:\n{combined}"
    )
    assert str(target_dir) in combined, (
        "Expected the failure report to name the exact project the build "
        f"was aimed at ({target_dir}) -- a message that only says "
        "'could not compute output_mappings' tells a reader nothing about "
        f"which install is unprotected. Combined output:\n{combined}"
    )


def test_bp_1500d_3_the_identical_build_succeeds_and_leaves_the_record_in_place_once_it_can_be_produced(
    _outside_pkg_root: Path,
    tmp_path: Path,
) -> None:
    """AC BP-1500d-3: the attribution control, and the guard against a
    regression dressed as a fix.

    Three runs against the SAME out-of-package target project directory
    (the "project the build was aimed at" never changes across the three
    runs below -- only whether the package copy invoked is nested under it):

    1. Package copied OUTSIDE target_dir's own tree (the reproduction) --
       record unproducible -- expect non-zero exit. EXPECTED RED today.
    2. The SAME package content copied so it is now nested INSIDE
       target_dir (the condition resolved -- the record can now be
       produced for that same project) -- expect exit 0 AND the record
       (.build_manifest.json with a non-empty output_mappings) actually
       present on disk in target_dir. This run is load-bearing: without
       it, a "fix" that simply makes build.py refuse every out-of-package
       target would pass runs 1 and 3 perfectly while being strictly worse
       than today.
    3. The original out-of-package package copy invoked again against the
       SAME target_dir (now carrying leftover state from run 2) --
       condition reintroduced -- expect non-zero exit again, proving the
       failure verdict in run 1 was attributable to the unproducible
       record and not to some one-shot fluke. EXPECTED RED today, same
       reason as run 1.
    """
    # covers: BP-1500d-3
    # angle: failure
    target_dir = tmp_path / "myproject"
    target_dir.mkdir()
    # Reuses the module-shared, read-only _outside_pkg_root fixture (see
    # PERFORMANCE NOTE above _fail_run) instead of building a fourth
    # synthetic package copy -- this function's own target_dir is unique to
    # this test, so sharing the package copy is safe (never mutated).
    outside_pkg_root = _outside_pkg_root

    # --- Run 1: record unproducible (out-of-package) ------------------
    run1 = _run_build(outside_pkg_root, target_dir)
    assert run1.returncode != 0, (
        "Run 1 (record unproducible, out-of-package target) must fail. "
        f"stdout:\n{run1.stdout}\nstderr:\n{run1.stderr}"
    )

    # --- Run 2: condition resolved, SAME target_dir --------------------
    nested_pkg_root = _copy_package(target_dir / "leafcutter-ai")
    run2 = _run_build(nested_pkg_root, target_dir)
    assert run2.returncode == 0, (
        "Run 2 (identical build, package now correctly nested under the "
        "SAME target project so the record CAN be produced) must succeed "
        "-- a build that instead refuses every out-of-package target would "
        f"fail this run too, which is the regression this control guards "
        f"against.\nstdout:\n{run2.stdout}\nstderr:\n{run2.stderr}"
    )
    manifest = _read_manifest(target_dir)
    assert manifest.get("output_mappings"), (
        "Run 2 exited 0 but wrote no non-empty output_mappings record to "
        f"{target_dir / '.build_manifest.json'} -- a build that succeeds "
        "by silently skipping the record must not pass this control either."
    )
    assert manifest.get("output_mappings_error", "") == "", (
        "Run 2's manifest still records output_mappings_error non-empty "
        "despite exit 0 -- the report and the outcome must agree."
    )

    # --- Run 3: condition reintroduced, SAME target_dir ----------------
    run3 = _run_build(outside_pkg_root, target_dir)
    assert run3.returncode != 0, (
        "Run 3 (condition reintroduced against the SAME target project) "
        "must fail again -- if it now succeeds, run 1's failure was not "
        "attributable to the unproducible record.\n"
        f"stdout:\n{run3.stdout}\nstderr:\n{run3.stderr}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [test-writer/fast-lane/BP-1500d-3]: Initial failing test
#   stubs. Empirically probed (real subprocess build.py runs, not read from
#   source) against a synthetic non-git copy of this worktree's own
#   templates/scripts/config/docs-product-truth trees on 2026-09-01: an
#   out-of-package target (package copied outside target_dir's own tree)
#   reproduces "ValueError: '<template>' is not in the subpath of
#   '<target>'", caught and downgraded to a warning, output_mappings written
#   as {} (vs ~470 for the same package correctly nested), process exits 0.
#   The paired success run (same package content, now nested under the SAME
#   target_dir) was independently probed and confirmed to exit 0 with a
#   non-empty output_mappings and an empty output_mappings_error. No
#   dependency on BP-1500d-1's (unimplemented, work_status: todo as of this
#   writing) shared out-of-package consumer-simulation harness -- this file
#   builds its own self-contained synthetic package copy instead, per this
#   AC's own note that BP-900h-1 (the nearest existing harness precedent) is
#   "a SPEC, NOT PRIOR ART" and BP-1500d-1's harness does not yet exist in
#   this worktree.
# ====================================================================
