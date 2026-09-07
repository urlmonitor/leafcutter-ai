"""
MODULE: unit_tests/portability/test_bp_900h_4_i.py
GOAL: Failing test-first stubs for AC BP-900h-4-i — "The declaring-file
    proof runs against every install layout an adopter produces, so a file
    that resolves in one layout is not accepted as proof for the rest".
AC: docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900h-4-i.yaml

CONTRACT UNDER TEST (fixed here because the production behavior does not
exist yet — the explicit target python-coder must satisfy). Builds on
BP-900h-4's single-layout CLI (scripts/ci/check_declaring_files.py
--deployed-root <path>) by adding a layout-sweep mode:

    python scripts/ci/check_declaring_files.py --layout-set <config.json>

    <config.json> is a JSON list of layout descriptors, each:
        {"layout": <str identity>, "deployed_root": <path>,
         "package_dir_name": <str>, "is_worktree": <bool>}

    For each layout, resolve BP-900h-4's declaring-file inventory strictly
    under that layout's OWN deployed_root (never another layout's, never the
    package checkout, never a parent directory, never cwd) and emit a JSON
    list on stdout — one verdict record per layout, per the AC's
    config_schema_fragment:
        {"layout": ..., "package_dir_name": ..., "is_worktree": ...,
         "deployed_root": ..., "missing": [{"declaring_file":...,
         "read_by":..., "expected_at":...}, ...]}
    Exit 0 iff every layout's "missing" list is empty; otherwise non-zero.
    Every layout is run and reported even after an earlier one fails
    (per-layout verdicts, not first-failure).

    Does NOT exist today — confirmed by `find scripts/ci -iname
    '*declaring*'` returning nothing (same absence BP-900h-4 confirms for
    its own single-layout mode).

LAYOUT CONSTRUCTION: via _bp900h4_layout_helpers.make_package_checkout,
which creates a REAL ``git clone --local`` (non-worktree layouts) or a REAL
``git worktree add`` (the worktree layout) against THIS checkout's own
object store — never a hand-copied directory (a copy would carry contents
a worktree structurally lacks, defeating the KI-BP-003 trigger this AC
turns on). Confirmed in-session: a full local clone of this repo completes
in <1s and `git worktree add` in ~1s, so building 2-4 real layouts per test
is inexpensive.

RED AT AUTHORING TIME: scripts/ci/check_declaring_files.py has no
--layout-set mode (it does not exist at all yet), so every subprocess call
below fails at argument-parsing / file-not-found rather than exercising the
sweep behavior.
"""

from __future__ import annotations

import concurrent.futures
import json
import subprocess
import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bp900h4_layout_helpers import (  # noqa: E402
    build_consumer_install,
    find_output_root,
    make_package_checkout,
    remove_package_checkout,
)

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_INSPECTOR = _WORKTREE_ROOT / "scripts" / "ci" / "check_declaring_files.py"
_CI_YAML = _WORKTREE_ROOT / ".github" / "workflows" / "ci.yml"

_KNOWN_FILE = "config/doc_types.json"
_EXPECTED_LAYOUT_SHAPES = {"prescribed-name", "different-name", "worktree", "self-hosted"}


def _run_sweep(config_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_INSPECTOR), "--layout-set", str(config_path)],
        capture_output=True, text=True, timeout=180, check=False,
    )


def _write_layout_set(tmp_path: Path, layouts: list[dict]) -> Path:
    config_path = tmp_path / "layout_set.json"
    config_path.write_text(json.dumps(layouts), encoding="utf-8")
    return config_path


class _Layout:
    """One real, built layout, with teardown for whatever it created."""

    def __init__(self, identity: str, package_dir: Path, deployed_root: Path,
                 package_dir_name: str, is_worktree: bool, was_created_as_worktree: bool) -> None:
        self.identity = identity
        self.package_dir = package_dir
        self.deployed_root = deployed_root
        self.package_dir_name = package_dir_name
        self.is_worktree = is_worktree
        self._was_created_as_worktree = was_created_as_worktree

    def as_descriptor(self) -> dict:
        return {
            "layout": self.identity,
            "deployed_root": str(self.deployed_root),
            "package_dir_name": self.package_dir_name,
            "is_worktree": self.is_worktree,
        }

    def teardown(self) -> None:
        remove_package_checkout(self.package_dir, was_worktree=self._was_created_as_worktree)


def _build_layout(
    root_parent: Path, identity: str, package_dir_name: str, *, as_worktree: bool,
) -> _Layout:
    """Build one real layout: a package checkout named *package_dir_name*
    (a real clone, or a real worktree when as_worktree=True) sibling to a
    real deployed output root produced by that checkout's own build.py —
    mirroring the CI job's ``actions/checkout@v4 path: leafcutter-ai`` +
    ``--target-dir .`` shape."""
    root = root_parent / f"{identity}-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True)
    package_dir = root / package_dir_name
    make_package_checkout(package_dir, as_worktree=as_worktree)

    deployed_parent = root  # sibling of package_dir, per the CI layout shape
    # --no-shims: shim installation is orthogonal to declaring-file
    # resolution and this AC alone needs 4 independent real builds inside
    # the fast-lane gate's fixed 60s pytest budget — see
    # _bp900h4_layout_helpers.build_consumer_install's docstring.
    result = build_consumer_install(package_dir, deployed_parent, extra_args=["--no-shims"])
    assert result.returncode == 0, (
        f"build.py failed for layout {identity!r} (package_dir_name="
        f"{package_dir_name!r}, as_worktree={as_worktree}).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    deployed_root = find_output_root(deployed_parent, exclude_name=package_dir_name)
    return _Layout(
        identity=identity, package_dir=package_dir, deployed_root=deployed_root,
        package_dir_name=package_dir_name, is_worktree=as_worktree,
        was_created_as_worktree=as_worktree,
    )


def _build_self_hosted_layout(deployed_parent: Path) -> _Layout:
    """The self-hosted control layout: package_dir_name matches THIS
    checkout's own directory name, deployed root built directly from THIS
    checkout — the exact shape this repository's own development
    environment uses, and the real thing rather than a clone of it (no
    clone needed: this checkout already exists on disk, and it is NEVER
    torn down — see _all_layouts' teardown, which skips this identity).

    *deployed_parent* must already exist and must be created by the caller
    on the main thread (see _all_layouts) — pytest.TempPathFactory.mktemp is
    not thread-safe, so this worker-invoked function must never call it
    itself."""
    result = build_consumer_install(_WORKTREE_ROOT, deployed_parent, extra_args=["--no-shims"])
    assert result.returncode == 0, (
        f"build.py failed for the self-hosted control layout.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    deployed_root = find_output_root(deployed_parent)
    return _Layout(
        identity="self-hosted", package_dir=_WORKTREE_ROOT, deployed_root=deployed_root,
        package_dir_name=_WORKTREE_ROOT.name, is_worktree=True,
        was_created_as_worktree=False,
    )


@pytest.fixture(scope="module")
def _all_layouts(tmp_path_factory: pytest.TempPathFactory) -> Generator[dict, None, None]:
    """Build ALL FOUR real layouts CONCURRENTLY (ThreadPoolExecutor — each
    worker's cost is a subprocess.run call, which releases the GIL, so this
    gets real wall-clock parallelism) and share them across every test in
    this module via the four thin accessor fixtures below.

    WHY THIS EXISTS: building 4 real layouts sequentially (a real git
    clone/worktree + a real, --no-shims build.py run each) measured ~27s in
    this session — safely under the fast-lane red-baseline gate's fixed 60s
    pytest budget on its own, but combined with test_bp_900h_4.py's own
    fixture and normal timing variance it left too little margin. Building
    concurrently cuts this module's layout-construction wall time to
    roughly the single SLOWEST layout rather than the sum of all four.

    THREAD-SAFETY OF THE PYTEST FIXTURE ITSELF: pytest.TempPathFactory is
    NOT thread-safe. mktemp()'s lazy basetemp initialisation
    (_ensure_relative_to_basetemp) races when called concurrently from
    multiple worker threads, raising "... is not a normalized and relative
    path" — reproduced deterministically under CI's fresh-clone conditions.
    Every mktemp() call below therefore happens HERE, on the main thread,
    before the ThreadPoolExecutor is created; the worker functions
    (_build_layout via _build_clone, and _build_self_hosted_layout) only
    ever receive already-created Path objects and never touch
    tmp_path_factory (or any other pytest fixture object) themselves. This
    is the only pytest fixture object touched anywhere in this module from
    a worker thread — caplog, monkeypatch, and request are not used."""
    clone_specs = [
        ("prescribed-name", "leafcutter-ai", False),
        ("different-name", "vendor-package-dir", False),
        ("worktree", "leafcutter-ai", True),
    ]

    # Allocate every temp directory the workers will need UP FRONT, on the
    # main thread. Distinct clone identities are disambiguated by
    # _build_layout's own uuid-suffixed subdirectory, so all three clones
    # safely share one pre-allocated parent.
    clone_root = tmp_path_factory.mktemp("layouts")
    self_hosted_root = tmp_path_factory.mktemp("self-hosted")

    def _build_clone(spec: tuple[str, str, bool]) -> _Layout:
        identity, package_dir_name, as_worktree = spec
        return _build_layout(clone_root, identity, package_dir_name, as_worktree=as_worktree)

    layouts: dict[str, _Layout] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_build_clone, spec) for spec in clone_specs]
        futures.append(executor.submit(_build_self_hosted_layout, self_hosted_root))
        for future in concurrent.futures.as_completed(futures):
            layout = future.result()
            layouts[layout.identity] = layout

    yield layouts

    for identity, layout in layouts.items():
        if identity != "self-hosted":
            layout.teardown()


@pytest.fixture(scope="module")
def prescribed_name_layout(_all_layouts: dict) -> _Layout:
    return _all_layouts["prescribed-name"]


@pytest.fixture(scope="module")
def different_name_layout(_all_layouts: dict) -> _Layout:
    return _all_layouts["different-name"]


@pytest.fixture(scope="module")
def worktree_layout(_all_layouts: dict) -> _Layout:
    return _all_layouts["worktree"]


@pytest.fixture(scope="module")
def self_hosted_layout(_all_layouts: dict) -> _Layout:
    return _all_layouts["self-hosted"]


def test_bp_900h_4_i_every_declaring_file_is_present_in_every_layout_and_each_layout_has_its_own_verdict(
    tmp_path: Path, prescribed_name_layout, different_name_layout, worktree_layout,
    self_hosted_layout,
) -> None:
    # covers: BP-900h-4-i
    # angle: criterion
    """NON-VACUITY HAS TWO HALVES: the layout set must be non-empty and
    contain all four shapes the criterion names, and the declaring-file
    inventory each layout is checked against must be non-empty and contain
    the document-type vocabulary confirmed unreachable on 2026-08-25. The
    report must carry one verdict record per layout, keyed by identity."""
    layouts = [prescribed_name_layout, different_name_layout, worktree_layout, self_hosted_layout]
    descriptors = [layout.as_descriptor() for layout in layouts]
    identities = {layout.identity for layout in layouts}
    assert identities == _EXPECTED_LAYOUT_SHAPES, (
        f"Constructed layout identities {identities} do not cover all four "
        f"shapes the criterion names: {_EXPECTED_LAYOUT_SHAPES}."
    )
    config_path = _write_layout_set(tmp_path, descriptors)

    result = _run_sweep(config_path)
    assert result.returncode == 0, (
        f"Sweep did not exit 0 across a fully healthy 4-layout set.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    verdicts = json.loads(result.stdout)
    assert verdicts, "The sweep produced an empty verdict list — non-vacuity violation."
    assert len(verdicts) == len(descriptors), (
        f"Expected {len(descriptors)} verdict records (one per layout), got "
        f"{len(verdicts)}: {verdicts}. An aggregate pass indistinguishable "
        "from a single-layout run is exactly the state that shipped broken."
    )
    reported_identities = {v["layout"] for v in verdicts}
    assert reported_identities == {d["layout"] for d in descriptors}, (
        f"Reported layout identities {reported_identities} do not match the "
        f"requested set {[d['layout'] for d in descriptors]}."
    )
    for v in verdicts:
        assert v["missing"] == [], (
            f"Layout {v['layout']!r} reported missing declaring files on a "
            f"healthy build: {v['missing']}"
        )


def test_bp_900h_4_i_an_install_whose_package_directory_carries_a_different_name_resolves_every_declaring_file(
    tmp_path: Path, prescribed_name_layout, different_name_layout,
) -> None:
    # covers: BP-900h-4-i
    # angle: deployed
    """THE NAME-INDEPENDENCE ENTRY. Two installs differing in exactly one
    respect (package_dir_name) must both resolve every declaring file. Then
    the anti-hardcode control: in the differently-named install, delete one
    declaring file and plant a decoy at the path the CURRENT (hardcoded,
    two-candidate) lookup would spell out for the PRESCRIBED name — the
    inspection must still report it missing rather than resolving the decoy."""
    config_path = _write_layout_set(
        tmp_path,
        [prescribed_name_layout.as_descriptor(), different_name_layout.as_descriptor()],
    )
    healthy_result = _run_sweep(config_path)
    assert healthy_result.returncode == 0, (
        f"Sweep did not exit 0 for two healthy, differently-named installs.\n"
        f"stdout:\n{healthy_result.stdout}\nstderr:\n{healthy_result.stderr}"
    )
    healthy_verdicts = {v["layout"]: v for v in json.loads(healthy_result.stdout)}
    assert healthy_verdicts["prescribed-name"]["missing"] == []
    assert healthy_verdicts["different-name"]["missing"] == []

    # Anti-hardcode control.
    target_path = different_name_layout.deployed_root / _KNOWN_FILE
    was_present = target_path.is_file()
    original_bytes = (
        target_path.read_bytes() if was_present
        else (_WORKTREE_ROOT / _KNOWN_FILE).read_bytes()
    )
    if was_present:
        target_path.unlink()
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)

    hardcoded_candidate = (
        different_name_layout.package_dir.parent / "leafcutter-ai" / _KNOWN_FILE
    )
    try:
        hardcoded_candidate.parent.mkdir(parents=True, exist_ok=True)
        hardcoded_candidate.write_bytes(original_bytes)

        sabotaged_result = _run_sweep(config_path)
        assert sabotaged_result.returncode != 0, (
            "Sweep went green after deleting a declaring file from the "
            "differently-named install's deployed root, with a decoy planted "
            "at the prescribed-name candidate path.\n"
            f"stdout:\n{sabotaged_result.stdout}\nstderr:\n{sabotaged_result.stderr}"
        )
        sabotaged_verdicts = {v["layout"]: v for v in json.loads(sabotaged_result.stdout)}
        different_name_missing = sabotaged_verdicts["different-name"]["missing"]
        assert different_name_missing, (
            "different-name layout reported no missing files even though "
            f"{_KNOWN_FILE} was deleted from its deployed root."
        )
        combined = json.dumps(different_name_missing)
        assert str(hardcoded_candidate) not in combined, (
            f"Sweep resolved (or named) the hardcoded-candidate decoy path "
            f"{hardcoded_candidate} instead of reporting the file missing under "
            f"the differently-named install's own deployed root:\n{combined}"
        )
    finally:
        if was_present:
            target_path.write_bytes(original_bytes)


def test_bp_900h_4_i_a_git_worktree_of_a_consumer_install_resolves_every_declaring_file_and_goes_red_when_one_is_removed_from_it_alone(
    tmp_path: Path, prescribed_name_layout, worktree_layout,
) -> None:
    # covers: BP-900h-4-i
    # angle: failure
    """THE REPORTED TRIGGER plus the negative control, against a REAL git
    worktree. (1) both layouts healthy -> exit 0, no missing entries.
    (2) remove one declaring file from the WORKTREE layout's deployed root
    only -> non-zero, naming the layout/file/guardrail/expected location,
    with the OTHER layout still reported passing. (3) restore -> exit 0."""
    config_path = _write_layout_set(
        tmp_path,
        [prescribed_name_layout.as_descriptor(), worktree_layout.as_descriptor()],
    )

    run1 = _run_sweep(config_path)
    assert run1.returncode == 0, (
        f"Run 1 (both layouts healthy) did not exit 0.\n"
        f"stdout:\n{run1.stdout}\nstderr:\n{run1.stderr}"
    )
    verdicts1 = {v["layout"]: v for v in json.loads(run1.stdout)}
    assert verdicts1["prescribed-name"]["missing"] == []
    assert verdicts1["worktree"]["missing"] == []

    target_path = worktree_layout.deployed_root / _KNOWN_FILE
    was_present = target_path.is_file()
    original_bytes = (
        target_path.read_bytes() if was_present
        else (_WORKTREE_ROOT / _KNOWN_FILE).read_bytes()
    )
    if was_present:
        target_path.unlink()
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        run2 = _run_sweep(config_path)
        assert run2.returncode != 0, (
            "Sweep stayed green after removing a declaring file from the "
            f"worktree layout's deployed root alone.\nstdout:\n{run2.stdout}\n"
            f"stderr:\n{run2.stderr}"
        )
        verdicts2 = {v["layout"]: v for v in json.loads(run2.stdout)}
        assert verdicts2["prescribed-name"]["missing"] == [], (
            "The prescribed-name (main checkout) layout was reported as failing "
            "when only the worktree layout's file was removed — the run does "
            "not attribute the failure to the correct layout.\n"
            f"{verdicts2['prescribed-name']}"
        )
        worktree_missing = verdicts2["worktree"]["missing"]
        assert worktree_missing, "worktree layout reported no missing files after deletion."
        combined = json.dumps(worktree_missing)
        assert _KNOWN_FILE in combined, f"Missing-entry report does not name {_KNOWN_FILE}:\n{combined}"
    finally:
        if was_present:
            target_path.write_bytes(original_bytes)

    run3 = _run_sweep(config_path)
    assert run3.returncode == 0, (
        "Restoring the deleted file did not bring the sweep back to green.\n"
        f"stdout:\n{run3.stdout}\nstderr:\n{run3.stderr}"
    )


def test_bp_900h_4_i_the_layout_sweep_runs_through_its_real_ci_entry_point_and_the_self_hosted_checkout_still_passes(
    tmp_path: Path, prescribed_name_layout,
) -> None:
    # covers: BP-900h-4-i
    # angle: reachability
    """PRODUCTION ENTRY POINT with must_block. Invoke the sweep as a
    subprocess through its real CLI, assert exit 0 across a healthy set
    (a control layout standing in for the self-hosted checkout — deployed
    root is a sibling of the package dir, exactly this repo's own
    development shape), then non-zero with one layout sabotaged. Assert the
    consumption half by parsing ci.yml as YAML — never by grepping text."""
    config_path = _write_layout_set(tmp_path, [prescribed_name_layout.as_descriptor()])

    healthy = _run_sweep(config_path)
    assert healthy.returncode == 0, (
        f"Sweep did not exit 0 for a single healthy layout (self-hosted-"
        f"shape control).\nstdout:\n{healthy.stdout}\nstderr:\n{healthy.stderr}"
    )

    target_path = prescribed_name_layout.deployed_root / _KNOWN_FILE
    was_present = target_path.is_file()
    original_bytes = (
        target_path.read_bytes() if was_present
        else (_WORKTREE_ROOT / _KNOWN_FILE).read_bytes()
    )
    if was_present:
        target_path.unlink()
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sabotaged = _run_sweep(config_path)
    finally:
        if was_present:
            target_path.write_bytes(original_bytes)  # restore before any assertion can fail loudly

    assert sabotaged.returncode != 0, (
        "Sweep stayed green with a sabotaged layout in the set.\n"
        f"stdout:\n{sabotaged.stdout}\nstderr:\n{sabotaged.stderr}"
    )

    workflow = yaml.safe_load(_CI_YAML.read_text(encoding="utf-8"))
    jobs = workflow.get("jobs", {})
    consumer_job = jobs.get("consumer-install-sim", {})
    steps = consumer_job.get("steps", [])
    matching_steps = [
        step for step in steps
        if "check_declaring_files.py" in step.get("run", "") and "--layout-set" in step.get("run", "")
    ]
    assert matching_steps, (
        "No step in the 'consumer-install-sim' job invokes "
        "check_declaring_files.py with --layout-set. The multi-layout sweep "
        "must be wired into CI, not just the single-layout mode (AC "
        "BP-900h-4-i)."
    )
    for step in matching_steps:
        assert step.get("continue-on-error") is not True, (
            f"Step {step.get('name')!r} invoking the layout sweep carries "
            "continue-on-error: true — its non-zero exit is swallowed."
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [test-writer/fast-lane BP-900h-4 build set]: Initial RED
#   stubs. scripts/ci/check_declaring_files.py has no --layout-set mode
#   (the script does not exist at all — confirmed by `find`), so every
#   sweep invocation below fails before reaching the assertions. Layout
#   construction uses REAL git clone/worktree operations against this
#   checkout's own object store (confirmed <1s each in-session) rather than
#   copied directories, per BP-900h-4-i's own "must be a real git worktree"
#   constraint. The self-hosted layout descriptor in entry 1 is passed as a
#   plain dict (not a _Layout, since it must not be torn down) pointing at
#   this workspace's own parent/.leafcutter — a control per the AC's own
#   "its local result is not evidence" constraint, included only for the
#   non-vacuity/shape-count assertion, not as a missing-file check.
# ====================================================================
