"""
MODULE: unit_tests/portability/test_bp_900h_4.py
GOAL: Failing test-first stubs for AC BP-900h-4 — "The install under test is
    a vendoring consumer, so a guardrail's data file cannot pass by
    borrowing the package's own tree".
AC: docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900h-4.yaml

CONTRACT UNDER TEST (fixed here because the production behavior does not
exist yet — this is the explicit target python-coder must satisfy):

    python scripts/ci/check_declaring_files.py --deployed-root <path> \
        [--print-inventory] [--extra-inventory-json <path>]

    Does NOT exist today — confirmed by ``find`` of scripts/ci/*declaring*
    (only check_consumer_install.py and check_fixture_orphans.py exist).

    Without ``--print-inventory``: derive, from the guardrails found under
    ``<deployed-root>``, the per-guardrail declaring-file inventory (one
    record per (guardrail, declaring file) pair, each carrying
    declaring_file / read_by / expected_at / ownership / derivation per the
    AC's config_schema_fragment). For every ``ownership: ours_to_ship``
    entry, resolve ``expected_at`` ONLY under ``<deployed-root>`` — never the
    package checkout beneath it, a parent directory, or the invoking
    process's cwd. Exit 0 iff every such entry resolves; otherwise exit
    non-zero and print one line per missing entry:
        MISSING: <declaring_file> read_by=<read_by> expected_at=<expected_at>
    An ``external``-owned entry is never reported missing even when its
    ``expected_at`` does not exist under the deployed root.

    With ``--print-inventory``: print the derived inventory (merged with any
    ``--extra-inventory-json`` entries, provided so the ownership-exclusion
    behavior can be tested without standing up a second real guardrail) as a
    JSON list of objects, and exit 0 unconditionally — this mode performs no
    presence checks, only derivation.

The five declaring files confirmed absent from a deployed output root on
2026-08-18 (and used here as the non-vacuity floor, per the AC's own text)
are, relative to a deployed output root:
    config/doc_types.json
    config/diagram_types.json
    config/ac_store_schema.json
    config/agent_registry.json
    scripts/ac_store/_component_migration_map.py
All five are confirmed present as SOURCE files at this repo's own root
(hence usable as the "package checkout" decoy location in entry 4 without
planting anything there).

RED AT AUTHORING TIME: scripts/ci/check_declaring_files.py does not exist,
so every subprocess invocation below fails at the interpreter's own
"can't open file" stage (non-zero exit, no JSON on stdout) rather than
executing the assertions' target behavior.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bp900h4_layout_helpers import build_consumer_install, find_output_root  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_INSPECTOR = _WORKTREE_ROOT / "scripts" / "ci" / "check_declaring_files.py"
_CI_YAML = _WORKTREE_ROOT / ".github" / "workflows" / "ci.yml"

_KNOWN_ABSENT_FILES = [
    "config/doc_types.json",
    "config/diagram_types.json",
    "config/ac_store_schema.json",
    "config/agent_registry.json",
    "scripts/ac_store/_component_migration_map.py",
]


def _run_inspector(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_INSPECTOR), *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _build_scratch_install(root: Path) -> Path:
    """Build the REAL scratch consumer install (BP-900h-1 shape) into
    *root* — a directory that is NOT a descendant of this package checkout."""
    consumer_root = root / "consumer"
    result = build_consumer_install(_WORKTREE_ROOT, consumer_root)
    assert result.returncode == 0, (
        f"scripts/build.py --target-dir failed to build the scratch install.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return find_output_root(consumer_root)


@pytest.fixture(scope="module")
def scratch_deployed_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Built ONCE for the whole module and shared across every test in this
    file. build.py takes ~4-5s; building it 5 times (once per test) would
    dominate this suite's runtime for no reason none of these tests actually
    needs an independent build — they need an independent DEPLOYED ROOT
    STATE, which each mutating test restores before returning (see each
    test's own teardown). Sharing is safe under that discipline and keeps
    the whole module's real-subprocess cost near a single build."""
    root = tmp_path_factory.mktemp("bp900h4_scratch")
    return _build_scratch_install(root)


def test_bp_900h_4_every_declaring_file_of_every_deployed_guardrail_is_present_under_the_scratch_deployed_root(
    scratch_deployed_root: Path,
) -> None:
    # covers: BP-900h-4
    # angle: criterion
    """Non-vacuity is mandatory (a for-each over an empty inventory is green
    on a broken install): the derived inventory must be non-empty and must
    contain the five files confirmed absent on 2026-08-18. Then the real
    presence check must exit 0 against a complete scratch install."""
    deployed_root = scratch_deployed_root

    inv_result = _run_inspector("--deployed-root", str(deployed_root), "--print-inventory")
    assert inv_result.returncode == 0, (
        f"--print-inventory did not exit 0.\nstdout:\n{inv_result.stdout}\n"
        f"stderr:\n{inv_result.stderr}"
    )
    inventory = json.loads(inv_result.stdout)
    assert inventory, (
        "The derived declaring-file inventory is empty. An empty inventory "
        "produces a passing for-each loop over nothing — the exact "
        "success-shaped-but-checked-nothing failure mode this AC exists "
        "against."
    )
    declaring_files = {entry["declaring_file"] for entry in inventory}
    missing_from_inventory = [f for f in _KNOWN_ABSENT_FILES if f not in declaring_files]
    assert not missing_from_inventory, (
        f"The derived inventory does not contain: {missing_from_inventory}. "
        f"Full inventory declaring_file set: {sorted(declaring_files)}. These "
        "five files were confirmed unreachable from a genuine consumer "
        "install on 2026-08-18 and must be part of the inventory this "
        "inspection walks."
    )

    presence_result = _run_inspector("--deployed-root", str(deployed_root))
    assert presence_result.returncode == 0, (
        "The declaring-file inspection did not exit 0 against a complete "
        f"scratch install.\nstdout:\n{presence_result.stdout}\n"
        f"stderr:\n{presence_result.stderr}"
    )


def test_bp_900h_4_ci_inspection_runs_through_its_real_entry_point_and_its_nonzero_verdict_is_not_swallowed(
    scratch_deployed_root: Path,
) -> None:
    # covers: BP-900h-4
    # angle: reachability
    """PRODUCTION ENTRY POINT. Invoke the inspection as a subprocess through
    the CLI, then verify the CI job's step invoking it does not carry
    continue-on-error: true, by parsing .github/workflows/ci.yml as YAML —
    never by grepping the file's text."""
    deployed_root = scratch_deployed_root

    result = _run_inspector("--deployed-root", str(deployed_root))
    assert result.returncode == 0, (
        f"CLI invocation did not exit 0 for a complete install.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    workflow = yaml.safe_load(_CI_YAML.read_text(encoding="utf-8"))
    jobs = workflow.get("jobs", {})
    consumer_job = jobs.get("consumer-install-sim", {})
    steps = consumer_job.get("steps", [])
    matching_steps = [
        step for step in steps
        if "check_declaring_files.py" in step.get("run", "")
    ]
    assert matching_steps, (
        "No step in the 'consumer-install-sim' job of .github/workflows/ci.yml "
        "invokes check_declaring_files.py. The inspection must be wired into "
        "the CI job so a non-zero verdict is actually surfaced (AC BP-900h-4)."
    )
    for step in matching_steps:
        assert step.get("continue-on-error") is not True, (
            f"Step {step.get('name')!r} invoking check_declaring_files.py "
            "carries continue-on-error: true — its non-zero exit is swallowed "
            "and the job passes regardless of the verdict (TQ-100 L-4 shape)."
        )


def test_bp_900h_4_inspection_goes_red_when_one_declaring_file_is_deleted_from_the_deployed_root_after_a_green_build(
    scratch_deployed_root: Path,
) -> None:
    # covers: BP-900h-4
    # angle: failure
    """THE NEGATIVE CONTROL THE CRITERION DEMANDS. Three runs of the same
    subprocess entry point: (1) green build -> exit 0; (2) delete one
    declaring file -> non-zero, naming the file/guardrail/expected location;
    (3) restore -> exit 0 again, attributing the red in (2) to the deletion
    rather than to an already-broken fixture. Restoration happens in a
    finally so this shared fixture is left clean for the next test in this
    module even if an assertion above fails."""
    deployed_root = scratch_deployed_root

    run1 = _run_inspector("--deployed-root", str(deployed_root))
    assert run1.returncode == 0, (
        f"Run 1 (green build) did not exit 0.\nstdout:\n{run1.stdout}\n"
        f"stderr:\n{run1.stderr}"
    )

    target_rel = _KNOWN_ABSENT_FILES[0]  # config/doc_types.json
    target_path = deployed_root / target_rel
    assert target_path.is_file(), f"expected {target_path} to exist after a green build"
    original_bytes = target_path.read_bytes()
    target_path.unlink()

    try:
        run2 = _run_inspector("--deployed-root", str(deployed_root))
        assert run2.returncode != 0, (
            "The inspection stayed green after deleting a declaring file from "
            "the deployed output root. An inspection that stays green on a "
            "deliberately incomplete install proves nothing (AC BP-900h-4)."
        )
        combined = run2.stdout + run2.stderr
        assert target_rel in combined, (
            f"Run 2's output does not name the deleted file {target_rel!r}.\n"
            f"stdout:\n{run2.stdout}\nstderr:\n{run2.stderr}"
        )
        assert str(deployed_root) in combined or target_rel in combined, (
            "Run 2's output does not name the deployed location the file was "
            f"expected at.\nstdout:\n{run2.stdout}\nstderr:\n{run2.stderr}"
        )
    finally:
        target_path.write_bytes(original_bytes)

    run3 = _run_inspector("--deployed-root", str(deployed_root))
    assert run3.returncode == 0, (
        "Restoring the deleted file did not bring the inspection back to "
        f"green.\nstdout:\n{run3.stdout}\nstderr:\n{run3.stderr}"
    )


def test_bp_900h_4_a_declaring_file_present_only_outside_the_deployed_root_is_still_reported_missing(
    tmp_path: Path, scratch_deployed_root: Path,
) -> None:
    # covers: BP-900h-4
    # angle: deployed
    """THE RESOLUTION RULE. With one declaring file absent from the scratch
    deployed root, plant a readable decoy at each of the three places that
    made the original defect invisible — the parent directory of the
    scratch install, the package checkout (already real and present at
    _WORKTREE_ROOT for these five files), and the subprocess's own cwd —
    and assert the inspection still reports the file missing and names the
    expected location under the deployed root, never a decoy path. Restores
    the file in a finally so this shared fixture is left clean."""
    deployed_root = scratch_deployed_root
    target_rel = _KNOWN_ABSENT_FILES[0]  # config/doc_types.json
    target_path = deployed_root / target_rel

    package_checkout_copy = _WORKTREE_ROOT / target_rel
    assert package_checkout_copy.is_file(), (
        f"Precondition failed: expected {package_checkout_copy} to exist as "
        "a real source-tree copy (used as the package-checkout decoy)."
    )
    decoy_bytes = package_checkout_copy.read_bytes()
    was_present = target_path.is_file()
    if was_present:
        target_path.unlink()
    else:
        # Pre-implementation this file is not even deployed yet (confirmed
        # in-session: a fresh build ships only 2 of the 5 known declaring
        # files today) — this branch just documents that the "absent"
        # precondition already holds, per this AC's own "necessary but not
        # sufficient" deploy-fix constraint.
        target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Decoy 1: parent directory of the scratch install.
        parent_decoy = deployed_root.parent.parent / target_rel
        parent_decoy.parent.mkdir(parents=True, exist_ok=True)
        parent_decoy.write_bytes(decoy_bytes)

        # Decoy 2: the package checkout — already real, asserted above.

        # Decoy 3: the subprocess's own working directory.
        cwd_decoy_dir = tmp_path / "launch_cwd"
        cwd_decoy_dir.mkdir(parents=True, exist_ok=True)
        cwd_decoy = cwd_decoy_dir / target_rel
        cwd_decoy.parent.mkdir(parents=True, exist_ok=True)
        cwd_decoy.write_bytes(decoy_bytes)

        result = _run_inspector("--deployed-root", str(deployed_root), cwd=cwd_decoy_dir)

        assert result.returncode != 0, (
            "The inspection went green with a decoy present in the parent "
            "directory, the package checkout, and the launch cwd — resolution "
            "must be anchored to the deployed output root alone.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert target_rel in combined, (
            f"Output does not name the missing file {target_rel!r}.\n{combined}"
        )
        assert str(parent_decoy) not in combined, (
            f"Output names the parent-directory decoy path {parent_decoy}, "
            "instead of (or in addition to) the deployed-root expected "
            f"location.\n{combined}"
        )
        assert str(cwd_decoy) not in combined, (
            f"Output names the launch-cwd decoy path {cwd_decoy}.\n{combined}"
        )
        assert str(package_checkout_copy) not in combined, (
            f"Output names the package-checkout decoy path {package_checkout_copy}.\n{combined}"
        )
        assert str(deployed_root) in combined, (
            "Output does not name the deployed-root expected location — an "
            "inspection that fails for the right reason and one that fails "
            f"while pointing at a decoy are indistinguishable otherwise.\n{combined}"
        )
    finally:
        if was_present:
            target_path.write_bytes(decoy_bytes)


def test_bp_900h_4_a_file_owned_by_the_operating_system_or_an_external_tool_is_not_reported_as_missing(
    tmp_path: Path, scratch_deployed_root: Path,
) -> None:
    # covers: BP-900h-4
    # angle: criterion
    """The does-not-manufacture-failures half. An externally-owned entry
    (an absolute OS path, and a path owned by an external tool the package
    does not ship) must never be reported missing, paired with a control
    entry (ours_to_ship, absent) that MUST be reported missing — otherwise
    the exclusion could be satisfied by excluding everything."""
    deployed_root = scratch_deployed_root

    os_path = sys.executable  # a real absolute OS path, never under deployed_root
    assert not str(Path(os_path)).startswith(str(deployed_root))

    external_tool_path = str(Path(yaml.__file__).resolve())
    assert not external_tool_path.startswith(str(deployed_root))

    extra_entries = [
        {
            "declaring_file": os_path,
            "read_by": "synthetic-test-guardrail",
            "expected_at": os_path,
            "ownership": "external",
            "derivation": "test-injected",
        },
        {
            "declaring_file": external_tool_path,
            "read_by": "synthetic-test-guardrail",
            "expected_at": external_tool_path,
            "ownership": "external",
            "derivation": "test-injected",
        },
        {
            "declaring_file": "config/totally-fake-package-owned.json",
            "read_by": "synthetic-test-guardrail",
            "expected_at": "config/totally-fake-package-owned.json",
            "ownership": "ours_to_ship",
            "derivation": "test-injected",
        },
    ]
    extra_json_path = tmp_path / "extra_inventory.json"
    extra_json_path.write_text(json.dumps(extra_entries), encoding="utf-8")

    result = _run_inspector(
        "--deployed-root", str(deployed_root),
        "--extra-inventory-json", str(extra_json_path),
    )

    assert result.returncode != 0, (
        "Expected non-zero because the injected ours_to_ship control entry "
        "is absent from the deployed root — a run that stays green here "
        "cannot distinguish 'excludes correctly' from 'excludes everything'."
        f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "config/totally-fake-package-owned.json" in combined, (
        f"The ours_to_ship control entry was not reported missing.\n{combined}"
    )
    assert os_path not in combined, (
        f"The externally-owned OS path {os_path!r} was reported missing.\n{combined}"
    )
    assert external_tool_path not in combined, (
        f"The externally-owned tool path {external_tool_path!r} was reported "
        f"missing.\n{combined}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [test-writer/fast-lane BP-900h-4 build set]: Initial RED
#   stubs. scripts/ci/check_declaring_files.py does not exist (confirmed by
#   `find scripts/ci -iname '*declaring*'` returning nothing), so every
#   subprocess call below fails at Python's own "can't open file" stage.
#   Fixed the five-file inventory floor and the CLI contract
#   (--print-inventory, --extra-inventory-json) as the explicit target for
#   python-coder, mirroring test_bp_900h6.py's per-file "CONTRACT UNDER
#   TEST" convention. Reused git-clone/build timing probes from this
#   session (build.py ~4s, well within the 60-120s subprocess timeouts used
#   here) to size the timeouts.
# ====================================================================
