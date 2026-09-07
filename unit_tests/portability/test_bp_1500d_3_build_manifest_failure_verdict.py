"""
MODULE: unit_tests/portability/test_bp_1500d_3_build_manifest_failure_verdict.py
GOAL: BP-1500d-3 -- a build that cannot produce the build-manifest record for
    a target must FAIL (non-zero process exit status) and its report must
    name the record and the project, distinguishably from a report of a
    build that DID produce the record. This is the enforcement floor for
    BP-1500d's whole guarantee: "(a) through (c) implemented over a build
    that still exits zero when it gives up leaves the whole family
    unenforceable, silently, exactly as today."

TRIGGER REBASED 2026-09-07 (test-writer pass) -- READ THIS FIRST. This file's
    prior trigger was "the package sits outside --target-dir". BP-1500d-1 has
    since landed and turned that layout into a SUCCESS case (measured: 472
    output mappings, an empty ``output_mappings_error``, exit 0) -- it is
    retained below only as the VENUE every child of BP-1500d must be proved
    in (ADR-001), no longer as a failing condition in its own right. The
    verdict this file proves (exit non-zero, report names both the record
    and the project, distinguishably from a success report) is unchanged;
    only the condition that makes the record unproducible has moved.

    THE NEW TRIGGER, measured against a REAL subprocess run of this
    worktree's own scripts/build.py on 2026-09-07, not read from source: a
    managed file's configured destination is an ABSOLUTE path outside
    --target-dir. Concretely, ``<target>/.claude/skills_config.json`` sets
    ``precommit_autofix_config_path`` to an absolute path outside the target
    project (``changelog_categories_path`` behaves identically -- this file
    pins one). Reproduction, in order:
      1. build.py's ``build_config_scaffolds`` phase writes the scaffold
         file to that absolute path (write-if-absent, so it lands wherever
         the config says, including outside the project entirely).
      2. ``write_build_manifest()`` -> ``_compute_output_mappings()`` ->
         ``_register_scaffold_if_unmodified()`` -> ``_add()`` then computes
         ``out_key = output_path.relative_to(repo_root)`` where
         ``repo_root == target_root``. Because ``output_path`` is that same
         absolute, out-of-target path, this raises
         ``ValueError: '<path>' is not in the subpath of '<target>'``.
      3. The ValueError propagates out of ``_compute_output_mappings()`` and
         is caught by ``write_build_manifest()``'s own broad
         ``except Exception`` (build_helpers.py, ~line 1219): every mapping
         already computed is discarded, ``output_mappings`` is written as
         ``{}``, ``output_mappings_error`` is set to the exception text, and
         the pre-existing fail-open warning is printed verbatim.
      4. ``write_build_manifest()`` RETURNS that non-empty error string.
         build.py's ``main()`` (scripts/build.py, ~line 2282) now consumes
         that return value: it prints
         ``[ERROR] Build manifest record (output_mappings) could not be
         produced for target project <target>: <error>. This install has no
         verifiable output_mappings record, so the build has failed rather
         than reporting success with a missing record.`` and returns 1.
    Measured 2026-09-07 on this branch: exit 1, with that exact [ERROR] line
    naming both "output_mappings" and the target directory, printed
    IMMEDIATELY AFTER a success-shaped tick line for the very same manifest
    (``build manifest (175 template + 0 output_mappings entries) -> ...``).
    Measured on origin/main: the identical state exits 0 -- the red baseline
    this file's assertions need is intact there, even though it is NOT what
    test-writer observes on THIS branch (see "NO RED BASELINE" below).

    CONFIG-DISCOVERY TRAP -- LOAD-BEARING, NOT A FOOTNOTE. The config is read
    from ``<target>/.claude/skills_config.json`` -- confirmed by reading
    ``config_loader.load_config()`` directly on 2026-09-07, which
    auto-detects across ``[".claude", ".gemini", ".cursor", ".github",
    ".cline"]`` in that order and stops at the first hit -- NOT
    ``<target>/skills_config.json``. A fixture that writes the latter
    configures NOTHING: the build succeeds with a full ~472-entry record and
    the test's red condition evaporates while looking exactly like a
    legitimate pass. Every test below that stands up this fixture therefore
    asserts a fixture-unique consequence of the config having actually been
    read (the exact escaped absolute path appearing in the failure text, or
    a non-default in-target path appearing in the written record) rather
    than trusting that writing the file was enough.

    OUT OF SCOPE, MEASURED AND DELIBERATELY NOT USED: the SAME escape
    written RELATIVELY (``"../elsewhere/<file>"``) does NOT fail -- pathlib
    does not normalise ``".."``, so the relativization silently succeeds and
    writes a record key pointing outside the project it claims to describe
    (a produced-but-untruthful record, a different and separately-filed
    defect). This file uses only the absolute form, which is the verified
    unproducible case.

FAIL-OPEN SITE (unchanged by the rebase -- only the condition that reaches
    it moved): scripts/build_helpers.py, write_build_manifest(), the
    ``except Exception`` around ``_compute_output_mappings(...)`` at
    approximately line 1219 (confirmed by direct read 2026-09-07 against
    THIS branch's HEAD, not assumed from the AC's own citation, which the
    AC's it-po flags as roughly a thousand lines stale).

ARCHITECTURE / EXERCISE STRATEGY (BP-1500d's mandatory proof shape,
    UNCHANGED by the rebase): every test below builds a REAL, on-disk
    synthetic package copy (real ``templates/``, ``scripts/``, ``config/``
    and ``docs/product-truth/`` trees copied byte-for-byte from this
    worktree -- never paraphrased) into a ``tmp_path``-rooted scratch tree
    that has NOTHING to do with this worktree's own parent directory, and
    invokes the REAL ``scripts/build.py`` as a REAL subprocess through its
    actual CLI (``python <pkg>/scripts/build.py --target-dir <target>``) --
    never by importing and calling ``write_build_manifest()`` directly. The
    verdict asserted on is the child process's own ``returncode``, because
    that is the only thing an automated caller (a CI step, a shell script,
    an install wizard) ever sees.

    LAYOUT -- THE SIBLING FORM, ASSERTED AS A FIXTURE PRECONDITION, NOT
    ASSUMED. Every out-of-package fixture below places the synthetic package
    copy and the receiving project as SIBLING directories under one common
    scratch root (``<scratch>/leafcutter-ai/`` and ``<scratch>/project/``),
    invoked as ``--target-dir <scratch>/project``. This is deliberately NOT
    ``--target-dir <scratch>`` (which would make the target EQUAL TO
    ``package_root.parent`` -- the self-host layout ADR-001 names as the one
    that hides this whole defect family, since ``package_root == repo_root``
    there and the ``relative_to`` computations this AC is about never have
    the chance to disagree). ``_assert_out_of_package_layout()`` below makes
    that distinction a load-bearing assertion rather than an assumption
    about directory naming: it fails loudly if a future edit collapses the
    target back onto ``package_root.parent``.

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
    are confirmed to no-op gracefully outside a git work-tree, so a non-git
    copy exercises exactly the output_mappings defect this AC owns without
    an unrelated guard producing a confounding non-zero exit for the wrong
    reason.

PERFORMANCE NOTE, CARRIED FORWARD FROM THE PRIOR PASS AND STILL BINDING: the
    fast-lane red-baseline gate (``.leafcutter/scripts/build_orchestration/
    fast_lane.py`` ``verify_red_baseline``) runs every ``# covers:``-tagged
    test file for an AC under a HARD, non-configurable 60-second subprocess
    timeout, and a single real ``build.py`` subprocess run against a full
    synthetic package copy costs roughly 8-30s. Tests 1 and 2 therefore
    share ONE real build invocation via the module-scoped ``_fail_run``
    fixture below, exactly as before. Test 3's new differential requirement
    (BA/IT-PO pass, 2026-09-07) necessarily adds one more real build of its
    own -- read-only against the SHARED ``_fail_run`` fixture's already-
    captured text for the failing half (no new build), plus one fresh build
    into an INDEPENDENT scratch target for the paired-success half (one new
    build). It deliberately does NOT reuse ``_fail_run``'s own target
    directory for that second build: mutating a module-scoped fixture's
    target out from under sibling tests would make test 1/2's manifest
    assertions dependent on test execution order, which is exactly the kind
    of fragility this file's own fixture-sharing note above warns against.
    Test 4 (the attribution control) still pays for its own three real
    build invocations, unchanged in structure from the prior pass. Total
    real build invocations in this file: 2 (shared, tests 1-2) + 1 (test 3's
    own paired-success half) + 3 (test 4) = 6.

NO RED BASELINE -- STATED PLAINLY, NOT A PASS. The implementation this file
    asserts against already handles the rebased trigger on THIS branch (that
    is how the trigger and every assertion below were verified in the first
    place -- see the REPRODUCTION section above, all measured against this
    branch's actual HEAD). Every test in this file is therefore expected to
    be GREEN on arrival, which is a TDD-order violation per this repo's own
    convention ("TDD Order -- test-writer Must Precede python-coder"), not a
    passing result to bank. The mutation-proof procedure that substitutes
    for a red baseline here is recorded in the sign-off comment for this
    change, not in this file: each test was confirmed to fail under a
    targeted one-line mutation of the production code path it covers, then
    confirmed green again after the mutation was reverted.
"""

from __future__ import annotations

import json
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

# The exact [ERROR] sentence scripts/build.py's main() prints when
# write_build_manifest() returns a non-empty output_mappings_error (BP-1500d-3's
# load-bearing exit path -- see scripts/build.py, ~line 2282). Scoped
# narrowly enough that it can ONLY match the failure branch: the success
# tick line ("build manifest (N template + M output_mappings entries) ->
# <path>") never contains the phrase "could not be produced", so this
# predicate cannot be satisfied by donation from a success line elsewhere
# in the same capture (BP-1500d-3's anti-vacuity requirement).
_FAILURE_REPORT_RE = re.compile(
    r"Build manifest record \(output_mappings\) could not be produced for target project (?P<target>.+?): "
)

# The manifest-write success tick that precedes the failure line on a
# failing run (measured 2026-09-07: "build manifest (175 template + 0
# output_mappings entries) -> <path>"). Used only to prove the tick is NOT
# the report's verdict -- the failure sentence above must still be reachable
# after it, not merely present somewhere in the capture.
_MANIFEST_TICK_RE = re.compile(r"build manifest \(\d+ template \+ \d+ output_mappings entries\)")


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
    manifest_path = target_dir / ".build_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _write_skills_config(target_dir: Path, config: dict) -> Path:
    """Write <target_dir>/.claude/skills_config.json -- and ONLY that path.

    This is the exact path config_loader.load_config() auto-detects first
    (confirmed by reading config_loader.py directly on 2026-09-07: it walks
    [".claude", ".gemini", ".cursor", ".github", ".cline"] in that order and
    stops at the first hit). A fixture that instead writes
    ``<target_dir>/skills_config.json`` (no ``.claude/``) configures NOTHING
    -- the build silently succeeds with a full record, a false green
    indistinguishable from a real pass. This is the exact trap the AC's
    test_rationale names as "the dominant false-green risk in this
    contract."

    Args:
        target_dir: The --target-dir a build will be run against.
        config: The skills_config.json content to write (merged over
            package defaults by load_config() -- only the keys under test
            need to be present).

    Returns:
        The absolute path written to, for diagnostics.
    """
    config_dir = target_dir / ".claude"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "skills_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def _assert_out_of_package_layout(package_root: Path, target_dir: Path) -> None:
    """Fixture precondition: assert the SIBLING (not self-host) layout.

    LOAD-BEARING, NOT DEFENSIVE (BP-1500d-1 expects_from, corrected
    2026-09-07): the prior draft of this family paired a package copy at
    ``<scratch>/leafcutter-ai/`` with ``--target-dir <scratch>`` -- which
    makes ``target_dir`` EQUAL TO ``package_root.parent``, the self-host
    layout ADR-001 names as the one that hides this whole defect family
    (``package_root == repo_root`` there, so the ``relative_to`` computation
    this AC is about never has the chance to disagree). A fixture built to
    that layout proves the wrong thing while looking correct. This function
    fails loudly if a future edit collapses the two back together, rather
    than silently proving nothing.

    Args:
        package_root: Absolute path to the synthetic package copy.
        target_dir: Absolute path to be passed as --target-dir.
    """
    pkg_parent = package_root.resolve().parent
    tgt = target_dir.resolve()
    assert tgt != pkg_parent, (
        f"self-host layout detected: target_dir {tgt} equals package_root.parent "
        f"{pkg_parent}. This is the layout ADR-001 says hides this whole "
        "defect family (package_root == repo_root there) -- use a "
        "<scratch>/leafcutter-ai/ + <scratch>/project/ SIBLING layout "
        "instead, per BP-1500d-1's corrected expects_from."
    )


# ---------------------------------------------------------------------------
# Shared, MODULE-scoped fixtures. See the PERFORMANCE NOTE in the module
# docstring for the cost accounting these exist to control.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _scratch_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One scratch root shared by the package copy and the shared target,
    so their SIBLING relationship (package at <scratch>/leafcutter-ai/,
    target at <scratch>/project/) is a fact about the fixture, not merely
    an accident of two independent tmp_path_factory.mktemp() calls landing
    under a common pytest session directory.
    """
    return tmp_path_factory.mktemp("bp1500d3_scratch")


@pytest.fixture(scope="module")
def _outside_pkg_root(_scratch_root: Path) -> Path:
    """Build ONE synthetic package copy at <scratch>/leafcutter-ai/.

    Shared (read-only) across every test in this module -- never mutated by
    a consumer. Building it once instead of per-test avoids repeating a
    multi-second ``shutil.copytree`` of templates/scripts/config/docs-
    product-truth for every test below.
    """
    return _copy_package(_scratch_root / "leafcutter-ai")


@pytest.fixture(scope="module")
def _escaped_config_target(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An ABSOLUTE path outside every --target-dir this module builds
    against -- the escaped precommit_autofix_config_path value that
    triggers BP-1500d-3's condition. Lives in its own scratch tree,
    deliberately never inside _scratch_root or any target_dir, so it is
    genuinely unreachable from inside the receiving project (a real build
    will actually write a scaffold file here -- see build_config_scaffolds.py
    -- so this must be a location this test run owns).
    """
    return tmp_path_factory.mktemp("bp1500d3_escaped") / "escaped-precommit-autofix.json"


@pytest.fixture(scope="module")
def _fail_run(
    _outside_pkg_root: Path,
    _scratch_root: Path,
    _escaped_config_target: Path,
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    """Run the REAL build.py ONCE against the sibling out-of-package target,
    configured so one managed file (precommit_autofix_config_path) is
    escaped to an absolute path outside --target-dir.

    Shared across tests 1 and 2, which assert different facts about this
    SAME real subprocess result (exit code + setup sanity, and exit code +
    CI-consumption, respectively). Test 3 reads this fixture's already-
    captured TEXT read-only for its failing-capture half and does NOT
    trigger a second build against this same target -- see the PERFORMANCE
    NOTE in the module docstring for why a second build here would be an
    order-dependence hazard, not just a cost saving.

    Returns:
        (target_dir, CompletedProcess) -- target_dir so consumers can read
        back .build_manifest.json.
    """
    target_dir = _scratch_root / "project"
    target_dir.mkdir()
    _assert_out_of_package_layout(_outside_pkg_root, target_dir)
    _write_skills_config(
        target_dir, {"precommit_autofix_config_path": str(_escaped_config_target)}
    )
    result = _run_build(_outside_pkg_root, target_dir)
    return target_dir, result


def test_bp_1500d_3_build_exits_nonzero_when_the_record_cannot_be_produced_for_an_out_of_package_target(
    _fail_run: tuple[Path, subprocess.CompletedProcess[str]],
    _escaped_config_target: Path,
) -> None:
    """AC BP-1500d-3: the primary assertion, and it is on the exit code.

    Given a real build against a sibling out-of-package target, configured
    so precommit_autofix_config_path escapes to an absolute path outside
    --target-dir (the rebased trigger -- see module docstring), when the
    build runs to completion, then the process must exit non-zero. NOT RED
    on this branch (see module docstring's "NO RED BASELINE" section) --
    the implementation already returns 1 here; confirmed red under a
    targeted mutation instead (see sign-off comment). Do NOT retarget this
    assertion onto the warning string or the mapping count if it is ever
    inconvenient -- per the AC's own test_rationale, exit-0-on-failure IS
    the defect, and any assertion satisfied by a build that only warns
    reintroduces it into the specification.
    """
    # covers: BP-1500d-3
    # angle: criterion
    target_dir, result = _fail_run
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "build.py exited 0 for a target with a managed file (precommit_autofix_"
        "config_path) configured to an absolute location outside --target-dir, "
        "whose .build_manifest.json output_mappings record could not therefore "
        "be produced -- this is BP-1500d-3's defect: a build that could not "
        "produce the record must fail, not warn once and report success.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # Config-was-read proof (mandatory per test_spec entry 1, 2026-09-07
    # it-po pass): a fixture that wrote <target>/skills_config.json instead
    # of <target>/.claude/skills_config.json would configure nothing and
    # this assertion would fail even though the exit-code assertion above
    # happened to still pass by coincidence of an unrelated defect -- so
    # this is load-bearing, not decorative.
    assert str(_escaped_config_target) in combined, (
        "expected the build's own output to name the exact escaped absolute "
        f"path ({_escaped_config_target}) written into "
        "<target>/.claude/skills_config.json -- its absence means the config "
        "was never consumed (see module docstring's CONFIG-DISCOVERY TRAP), "
        f"which would make this a false green.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # Supporting signal only (per test_rationale, never the primary
    # assertion): the manifest itself should show the whole-computation
    # failure recorded as data. Valid again under the rebased trigger -- the
    # record genuinely is emptied here, unlike the dead pre-BP-1500d-1
    # trigger these two assertions were briefly inverted against.
    manifest = _read_manifest(target_dir)
    assert manifest.get("output_mappings") == {}, (
        "setup sanity: expected an empty output_mappings for a target whose "
        "precommit_autofix_config_path escapes outside it. Got "
        f"{len(manifest.get('output_mappings', {}))} entries -- the "
        "reproduction may no longer trigger the fail-open path."
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
    nor pipes the build into a command that could mask its exit status.

    TRIGGER-INDEPENDENT HALF, UNTOUCHED BY THE REBASE (per test_spec entry
    2's description, 2026-09-07): the YAML-consumption assertions below did
    not change at all across the rebase -- only the fixture producing the
    exit code above did. A grep for the script name would be green on a
    step that ignores the exit code, which is the defect one level up from
    this AC's own subject; parsing the workflow as a data structure is what
    this repo's "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep"
    convention demands instead.
    """
    # covers: BP-1500d-3
    # angle: reachability
    _target_dir, result = _fail_run

    assert result.returncode != 0, (
        "An automated caller reading only build.py's process exit status "
        "(e.g. a CI step, `$?` in a shell script) would conclude the build "
        "succeeded even though the output_mappings record could not be "
        "produced for this target.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
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
    _outside_pkg_root: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """AC BP-1500d-3: the report clause -- rebuilt structurally, not just re-pointed.

    Measured 2026-09-07, BEFORE this rewrite: this test passed VACUOUSLY.
    Both strings the old version searched for (the record's name and the
    target path) appeared in the SUCCESS line of a healthy build too, so a
    substring search over the whole capture could not distinguish the
    report this entry exists to check from that report's exact opposite.
    Re-pointing the old fixture alone would have left a green test that
    still could not fail. THREE CHANGES, ALL REQUIRED (per the 2026-09-07
    it-po pass):

    (1) RE-POINT onto the rebased trigger -- reads the SAME real subprocess
        capture `_fail_run` produced (no second build for this half).

    (2) SCOPE THE NAMING ASSERTIONS TO THE FAILURE REPORT ITSELF, not the
        whole capture: `_FAILURE_REPORT_RE` matches ONLY the literal
        sentence build.py's exit path prints ("Build manifest record
        (output_mappings) could not be produced for target project ...") --
        a phrase that never appears in the success tick line, so neither
        match can be donated by an unrelated success line elsewhere in the
        output.

    (3) MAKE IT DIFFERENTIAL: captures a SEPARATE, fresh paired-success run
        (same package, a brand-new out-of-package target with no escape
        configured -- i.e. every managed file lands inside the project) and
        asserts the SAME `_FAILURE_REPORT_RE` predicate is ABSENT there. A
        predicate that matched both captures would prove nothing and MUST
        fail this test; that inversion is the anti-vacuity guard and may
        not be dropped. This paired-success build is deliberately a NEW
        target directory rather than a second build into `_fail_run`'s own
        shared target -- see the PERFORMANCE NOTE in the module docstring
        for why mutating that shared fixture's target here would make
        tests 1/2 order-dependent.

    Also asserts the measured ordering fact from the AC's it_requirements:
    the manifest success tick ("build manifest (175 template + 0
    output_mappings entries)") appears BEFORE the failure sentence in the
    failing capture, and the failure sentence is still reachable after it --
    i.e. the report does not present that tick as its verdict for a record
    it could not produce.
    """
    # covers: BP-1500d-3
    # angle: criterion
    target_dir, result = _fail_run
    failing_combined = result.stdout + result.stderr

    failure_match = _FAILURE_REPORT_RE.search(failing_combined)
    assert failure_match, (
        "Expected the failing run's output to contain the scoped failure "
        "sentence 'Build manifest record (output_mappings) could not be "
        f"produced for target project ...'. Combined output:\n{failing_combined}"
    )
    assert failure_match.group("target") == str(target_dir), (
        "Expected the failure report to name the exact project the build "
        f"was aimed at ({target_dir}), scoped to the failure sentence "
        f"itself -- got {failure_match.group('target')!r}. A message that "
        "only says 'could not compute output_mappings' tells a reader "
        "nothing about which install is unprotected."
    )

    # The manifest success tick must not itself stand as the report's
    # verdict for a record it could not produce: it is present (a reader
    # really does see a success-shaped line first), but the scoped failure
    # sentence above must be reachable AFTER it, not merely present
    # somewhere disconnected from it.
    tick_match = _MANIFEST_TICK_RE.search(failing_combined)
    assert tick_match, (
        "Expected the measured manifest success tick ('build manifest (N "
        "template + M output_mappings entries)') to appear in the failing "
        f"run's output. Combined output:\n{failing_combined}"
    )
    assert tick_match.start() < failure_match.start(), (
        "Expected the failure sentence to appear AFTER the manifest success "
        "tick, matching the measured shape (the report does not omit the "
        "tick -- it must not let the tick stand as the verdict). Tick at "
        f"offset {tick_match.start()}, failure at {failure_match.start()}."
    )

    # --- DIFFERENTIAL half: a fresh, independent paired-success capture ---
    success_target = tmp_path_factory.mktemp("bp1500d3_test3_paired_success")
    success_target.mkdir(exist_ok=True)
    _assert_out_of_package_layout(_outside_pkg_root, success_target)
    # No escape configured -- every managed file (including
    # precommit_autofix_config_path, left at its in-target default) lands
    # inside the project, so the record IS producible.
    success_result = _run_build(_outside_pkg_root, success_target)
    assert success_result.returncode == 0, (
        "the paired-success capture must itself succeed, or it cannot serve "
        f"as the 'opposite report' this test differentiates against.\n"
        f"stdout:\n{success_result.stdout}\nstderr:\n{success_result.stderr}"
    )
    success_combined = success_result.stdout + success_result.stderr

    assert _MANIFEST_TICK_RE.search(success_combined), (
        "expected the paired-success run to also print a manifest tick "
        "(it is a shape both reports share) -- its absence means this "
        "capture is not the healthy-build baseline it is meant to be.\n"
        f"{success_combined}"
    )
    donated_match = _FAILURE_REPORT_RE.search(success_combined)
    assert donated_match is None, (
        "ANTI-VACUITY GUARD: the scoped failure sentence matched BOTH the "
        "failing capture AND the paired-success capture -- this predicate "
        "distinguishes nothing and the test that relies on it cannot fail. "
        f"Unexpected match in the success capture: {donated_match!r}\n"
        f"success capture:\n{success_combined}"
    )


def test_bp_1500d_3_the_identical_build_succeeds_and_leaves_the_record_in_place_once_it_can_be_produced(
    _outside_pkg_root: Path,
    tmp_path: Path,
) -> None:
    """AC BP-1500d-3: the attribution control, and the guard against a
    regression dressed as a fix.

    Three runs of the SAME build command line (SAME out-of-package package
    copy throughout) against the SAME target project directory.
    MECHANISM REBASED 2026-09-07: run 2 no longer resolves the condition by
    re-nesting the package inside the target (that layout now succeeds on
    its own since BP-1500d-1 landed, making it a no-op) -- it resolves the
    condition by moving the escaped managed file back INSIDE the project via
    config, per the rebased trigger.

    1. Escape configured (precommit_autofix_config_path absolute, outside
       target_dir) -- record unproducible -- expect non-zero exit.
    2. The SAME target_dir, escape resolved by pointing
       precommit_autofix_config_path at a NON-DEFAULT path INSIDE the
       target -- expect exit 0 AND the record (.build_manifest.json with a
       non-empty output_mappings) present on disk, AND (the config-was-read
       proof for this whole entry) a mapping entry for that exact
       non-default path. Without this run, a "fix" that simply makes
       build.py refuse every out-of-package target would pass runs 1 and 3
       perfectly while being strictly worse than today -- this is not
       hypothetical, it is what shipped when this AC was built ahead of
       BP-1500d-1 and regressed 18 outcomes across 6 files.
    3. The escape reintroduced (SAME absolute out-of-target path as run 1),
       SAME target_dir -- expect non-zero exit again, proving the failure
       verdict in run 1 was attributable to the unproducible record and not
       to some one-shot fluke.
    """
    # covers: BP-1500d-3
    # angle: failure
    target_dir = tmp_path / "myproject"
    target_dir.mkdir()
    # Reuses the module-shared, read-only _outside_pkg_root fixture (see
    # PERFORMANCE NOTE in the module docstring) instead of building a
    # second synthetic package copy -- this function's own target_dir is
    # unique to this test, so sharing the package copy is safe (never
    # mutated).
    outside_pkg_root = _outside_pkg_root
    _assert_out_of_package_layout(outside_pkg_root, target_dir)

    escaped_path = tmp_path / "bp1500d3_test4_escaped" / "escaped-precommit-autofix.json"
    recovered_rel_path = "bp1500d3-recovered/precommit-autofix.json"

    # --- Run 1: record unproducible (escaped managed file) -------------
    _write_skills_config(target_dir, {"precommit_autofix_config_path": str(escaped_path)})
    run1 = _run_build(outside_pkg_root, target_dir)
    assert run1.returncode != 0, (
        "Run 1 (record unproducible -- precommit_autofix_config_path "
        "escaped outside target_dir) must fail. "
        f"stdout:\n{run1.stdout}\nstderr:\n{run1.stderr}"
    )

    # --- Run 2: condition resolved by moving the file back INSIDE the
    # project, SAME target_dir. Uses a NON-DEFAULT in-target path so this
    # run doubles as the config-was-read proof for the whole entry.
    _write_skills_config(
        target_dir, {"precommit_autofix_config_path": recovered_rel_path}
    )
    run2 = _run_build(outside_pkg_root, target_dir)
    assert run2.returncode == 0, (
        "Run 2 (identical build, the escaped file now placed back INSIDE "
        "the SAME target project so the record CAN be produced) must "
        "succeed -- a build that instead refuses every out-of-package "
        "target would fail this run too, which is the regression this "
        f"control guards against.\nstdout:\n{run2.stdout}\nstderr:\n{run2.stderr}"
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
    assert recovered_rel_path in manifest.get("output_mappings", {}), (
        "CONFIG-WAS-READ PROOF: run 2 pointed precommit_autofix_config_path "
        f"at a NON-DEFAULT in-target path ({recovered_rel_path!r}) and the "
        "written record carries no mapping entry for it -- the fixture's "
        "config was never consumed, so runs 1 and 3 prove nothing while "
        "looking green. This is the exact false green a probe hit by "
        "writing <target>/skills_config.json instead of "
        "<target>/.claude/skills_config.json."
    )

    # --- Run 3: escape reintroduced, SAME target_dir --------------------
    _write_skills_config(target_dir, {"precommit_autofix_config_path": str(escaped_path)})
    run3 = _run_build(outside_pkg_root, target_dir)
    assert run3.returncode != 0, (
        "Run 3 (escape reintroduced against the SAME target project) must "
        "fail again -- if it now succeeds, run 1's failure was not "
        "attributable to the unproducible record.\n"
        f"stdout:\n{run3.stdout}\nstderr:\n{run3.stderr}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [test-writer/fast-lane/BP-1500d-3]: Initial failing test
#   stubs against the pre-BP-1500d-1 trigger ("the package sits outside
#   --target-dir"). See git history for the original text; superseded
#   entirely by the entry below once BP-1500d-1 landed and made that
#   layout a success case.
# - 2026-09-07 [test-writer/fast-lane/BP-1500d-3]: REBASED onto the new
#   trigger per the BA/IT-PO's 2026-09-07 amendments to
#   BP-1500d-3.yaml: precommit_autofix_config_path set to an ABSOLUTE path
#   outside --target-dir via <target>/.claude/skills_config.json. Verified
#   empirically (three real subprocess build.py runs against this
#   worktree's own HEAD, not read from source) on 2026-09-07:
#     - Escaped absolute path -> exit 1, output_mappings == {}, non-empty
#       output_mappings_error, and build.py's own [ERROR] line names both
#       "output_mappings" and the exact target directory, printed
#       immediately after a success-shaped manifest tick for the same file.
#     - The SAME target, escape resolved via a non-default in-target
#       relative path -> exit 0, 472 output_mappings entries including one
#       keyed exactly to that non-default path, empty output_mappings_error.
#     - The SAME target, escape reintroduced -> exit 1 again.
#   Test 3 was additionally rebuilt structurally (not just re-pointed): its
#   prior version passed vacuously (both strings it searched for appeared in
#   a healthy build's success line too). It now scopes its naming assertion
#   to a regex matching ONLY build.py's own failure sentence, and adds a
#   differential paired-success capture in the same test, asserting the
#   failure predicate is present in the failing capture and absent from the
#   success one -- confirmed both ways against real captures on 2026-09-07.
#   All four tests are green on arrival on this branch (the implementation
#   already handles the rebased trigger, which is how it was verified) --
#   this is a stated TDD-order violation per this repo's own convention, not
#   a pass; see the sign-off comment for this change for the mutation-proof
#   substitute.
# ====================================================================
