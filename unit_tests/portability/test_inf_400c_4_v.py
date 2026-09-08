"""
MODULE: test_inf_400c_4_v
GOAL: RED test stubs for AC INF-400c-4-v — the knowledge-emission sink's
    build-time absolute-path declaration must land in the project the
    package was built into, in every install shape, and must say so when
    that stops being true (staleness, silent re-split on rebuild, silent
    relocation).
AC: INF-400c-4-v (source_ac)
DEPENDS ON: INF-400c-4 (work_status: todo, implemented_by: [] as of
    authoring) — the build-time declaration and its parity check do not
    exist yet in this worktree. None of the surfaces this file exercises
    exist today, so every test below is expected to be RED at authoring
    time via a real, informative failure (a missing declaration file, an
    "unrecognized arguments: --print-sink" argparse error, or an assertion
    that the described behaviour is absent) — never a bare collection error.

CONTRACT THIS FILE FIXES (test-writer's concrete reading of the AC's
    "single named location both sides read" and "recorded in the
    configuration that build deploys" — python-coder implements against
    this exact shape, mirroring how ``feedback_categories.yaml`` and
    ``paths.json`` already sit beside each other under the same directory):

    1. Declaration file: ``<deployed_root>/config/knowledge_sink.json``,
       where ``<deployed_root>`` is ``<target-dir>/<output_root>``
       (``.leafcutter`` by default — see ``scripts/ci/check_consumer_install.py``
       and its own ``_resolve_output_root`` helper). Content:
       ``{"knowledge_emission_sink": "<absolute-path-string>"}``.
    2. Reader entry point: the DEPLOYED copy of
       ``scripts/knowledge/harvest_learnings.py`` (i.e.
       ``<deployed_root>/scripts/knowledge/harvest_learnings.py`` — never the
       source-tree copy; the whole point of a build-time declaration is that
       it is read from the deployed configuration of a specific install).
    3. A new, side-effect-free query flag on that same script: ``--print-sink``.
       Prints the resolved absolute path (and nothing else) to stdout and
       exits 0. Reads the declaration only — never opens, creates, or stats
       the sink file itself or its parent directories.
    4. The staleness report (declared directory gone) is surfaced through
       the SAME script's ordinary (non-``--print-sink``) run, and must:
       (a) exit non-zero with one of the four PRE-EXISTING enumerated exit
       codes {1, 2, 3, 4} (INF-400c-4-iv forbids inventing a fifth), and
       (b) mention the substring "stale" (case-insensitive) together with
       the declared path, distinguishing it from the exit-0 no-work outcome
       for a sink that has simply never been written to.

REAL-ARTIFACT / REACHABILITY NOTE (BP-1100f-2 + BP-1100g-2): every test here
    drives the REAL ``scripts/ci/check_consumer_install.py`` (which shells
    out to the REAL ``scripts/build.py``) against a REAL ``tmp_path``
    scratch directory, and then invokes the REAL deployed
    ``harvest_learnings.py`` as a REAL subprocess. Nothing here imports a
    resolver function directly and calls it in-process — that would prove
    only that a helper exists, not that the declared install shape actually
    produces it, which is exactly what BP-1100g-2's reachability angle rules
    out.
"""
# @ac-tag: INF-400c-4-v

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — conftest.py in this directory already inserts the worktree
# root onto sys.path; we need the concrete worktree root ourselves to build
# --package-dir arguments and to locate check_consumer_install.py.
# ---------------------------------------------------------------------------
_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_CHECK_CONSUMER_INSTALL = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"

_BUILD_TIMEOUT_SECONDS = 180
_QUERY_TIMEOUT_SECONDS = 30

# The four pre-existing enumerated exit codes from INF-400c-4-iv's
# it_requirements. Staleness must reuse one of these — never a new one.
_EXISTING_NONZERO_EXIT_CODES = {1, 2, 3, 4}


def _run_consumer_build(
    target_dir: Path,
    package_dir: Path = _WORKTREE_ROOT,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    """Run the REAL scripts/ci/check_consumer_install.py as a REAL subprocess.

    This shells out to the REAL scripts/build.py underneath (per that
    script's own docstring) — no mocking of the build, the filesystem, or
    the declaration this AC adds.
    """
    argv = [
        sys.executable,
        str(_CHECK_CONSUMER_INSTALL),
        "--package-dir", str(package_dir),
        "--target-dir", str(target_dir),
        *extra_args,
    ]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
        check=False,
    )


def _deployed_root(target_dir: Path) -> Path:
    """Default deployed output root for a minimal seeded skills_config.json."""
    return target_dir / ".leafcutter"


def _declared_sink_config_path(target_dir: Path) -> Path:
    return _deployed_root(target_dir) / "config" / "knowledge_sink.json"


def _deployed_harvester_path(target_dir: Path) -> Path:
    return _deployed_root(target_dir) / "scripts" / "knowledge" / "harvest_learnings.py"


def _read_declared_sink(target_dir: Path) -> str:
    """Read the build-time sink declaration this AC requires build.py to write.

    Raises a descriptive AssertionError (a valid RED state) when the
    declaration does not exist yet, which is the case for every run of this
    file until INF-400c-4 and INF-400c-4-v are both implemented.
    """
    config_path = _declared_sink_config_path(target_dir)
    assert config_path.is_file(), (
        f"Expected a build-time knowledge-sink declaration at {config_path} "
        "(AC INF-400c-4-v contract: 'the path is fixed when the package is "
        "built into a project ... and is recorded in the configuration that "
        "build deploys'). This file does not exist — the declaration has not "
        "been implemented yet."
    )
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"{config_path} exists but is not valid JSON: {exc}"
        ) from exc
    assert "knowledge_emission_sink" in data, (
        f"Expected key 'knowledge_emission_sink' in {config_path}, "
        f"found keys: {sorted(data.keys())}"
    )
    return data["knowledge_emission_sink"]


def _run_print_sink(target_dir: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the DEPLOYED harvester's side-effect-free sink query.

    Uses the deployed copy under ``target_dir``'s own ``.leafcutter`` tree,
    run with a caller-supplied ``cwd`` so callers can simulate querying from
    inside an isolated working directory vs. from the project root.
    """
    script = _deployed_harvester_path(target_dir)
    argv = [sys.executable, str(script), "--print-sink"]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=_QUERY_TIMEOUT_SECONDS,
        check=False,
        cwd=str(cwd),
    )


def _run_harvester_default(target_dir: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the DEPLOYED harvester in its ordinary (non-query) run mode.

    No ``--sink`` argument is passed, so this exercises "the reader's
    default -- the path it uses when no sink is supplied on the command
    line" (INF-400c-4's own criteria), which INF-400c-4-v requires to be the
    declared build-time value.
    """
    script = _deployed_harvester_path(target_dir)
    argv = [sys.executable, str(script)]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=_QUERY_TIMEOUT_SECONDS,
        check=False,
        cwd=str(cwd),
    )


def test_a_nested_install_declares_the_sink_at_the_consumers_root_not_the_package_subdirectory(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-v: nested consumer install — sink lands at the CONSUMER's
    root, never inside the package subdirectory.

    Fixture: a consumer repository (its own ``git init``) containing a
    package subdirectory that is ITSELF a repository with its own repository
    data — satisfied here by symlinking the real worktree root (which is
    itself a git worktree with its own ``.git``) in as a nested
    ``vendor/leafcutter-ai`` subdirectory, rather than duplicating the whole
    checkout. This is the fixture the criterion names as the ONLY one that
    can distinguish a build-time-declared implementation from one that
    resolves by looking at its surroundings (e.g. nearest ``.git``): in a
    flat fixture every candidate implementation gives the same answer.
    """
    # covers: INF-400c-4-v
    # angle: real_artifact
    consumer_root = tmp_path / "consumer_repo"
    vendor_dir = consumer_root / "vendor"
    vendor_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(consumer_root)], check=True, timeout=30)
    package_subdir = vendor_dir / "leafcutter-ai"
    package_subdir.symlink_to(_WORKTREE_ROOT, target_is_directory=True)

    build_result = _run_consumer_build(consumer_root, package_subdir)
    assert build_result.returncode == 0, (
        "Fixture setup failed: the real build did not succeed against the "
        f"nested consumer fixture.\nstdout:\n{build_result.stdout}\n"
        f"stderr:\n{build_result.stderr}"
    )

    declared_sink = _read_declared_sink(consumer_root)

    assert declared_sink.startswith(str(consumer_root) + "/") or declared_sink == str(consumer_root), (
        f"Declared sink {declared_sink!r} does not live under the consumer's "
        f"own root {consumer_root} — AC INF-400c-4-v requires the sink to be "
        "reviewable, diffable and mergeable by the people who own the "
        "consumer project."
    )
    assert not declared_sink.startswith(str(package_subdir)), (
        f"Declared sink {declared_sink!r} lives inside the PACKAGE "
        f"subdirectory ({package_subdir}) rather than the consumer's root — "
        "this is exactly the failure mode the criterion's nested fixture "
        "exists to catch: a consumer's learnings filed inside the package "
        "clone, where the consumer's review never sees them."
    )


def test_the_declared_sink_sits_beside_the_rest_of_the_installs_deployed_content(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-v: workspace-shaped install — sink lands under the same
    root the rest of the deployed content (agents/, scripts/) was written to.
    """
    # covers: INF-400c-4-v
    # angle: criterion
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    build_result = _run_consumer_build(workspace_root)
    assert build_result.returncode == 0, (
        "Fixture setup failed: the real build did not succeed against the "
        f"workspace fixture.\nstdout:\n{build_result.stdout}\n"
        f"stderr:\n{build_result.stderr}"
    )

    deployed_root = _deployed_root(workspace_root)
    assert deployed_root.is_dir(), f"Expected deployed root at {deployed_root}"

    declared_sink = _read_declared_sink(workspace_root)

    assert declared_sink.startswith(str(workspace_root)), (
        f"Declared sink {declared_sink!r} is not under the workspace root "
        f"{workspace_root} the build was pointed at — the deployed "
        "configuration, agents and scripts all sit under that root, and the "
        "sink must sit beside them rather than beside the package sources "
        f"({_WORKTREE_ROOT})."
    )
    assert not declared_sink.startswith(str(_WORKTREE_ROOT)), (
        f"Declared sink {declared_sink!r} points into the PACKAGE SOURCES "
        f"({_WORKTREE_ROOT}) rather than the install the build produced."
    )


def test_a_declaration_whose_directory_is_gone_is_reported_stale_and_not_as_an_empty_sink(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-v: moving an installed project by hand must be reported
    as a STALE declaration, distinctly from a sink that has simply never
    been written to, without conjuring the missing directory back into
    existence and without inventing a new exit status.
    """
    # covers: INF-400c-4-v
    # angle: failure
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    build_result = _run_consumer_build(project_dir)
    assert build_result.returncode == 0, (
        f"Fixture setup failed.\nstdout:\n{build_result.stdout}\n"
        f"stderr:\n{build_result.stderr}"
    )

    declared_sink = _read_declared_sink(project_dir)
    declared_sink_path = Path(declared_sink)

    # Baseline: run the never-written-to (empty / absent sink) case for
    # comparison, BEFORE moving anything, so the two outcomes can be
    # distinguished from each other rather than each asserted in isolation.
    never_written_result = _run_harvester_default(project_dir, cwd=project_dir)

    # Now relocate the whole project by hand — nothing rebuilds the
    # declaration, so it now names a directory that is no longer there. The
    # entire original tree (including the declared sink's own directory, if
    # any existed) is moved away by this rename, so the OLD absolute path
    # cannot exist afterwards unless something recreates it.
    moved_project_dir = tmp_path / "project_moved"
    project_dir.rename(moved_project_dir)

    stale_result = _run_harvester_default(moved_project_dir, cwd=moved_project_dir)

    assert stale_result.returncode != 0, (
        "A declaration whose directory is gone must be reported as an error "
        f"(one of the existing nonzero exit codes), got exit 0.\n"
        f"stdout:\n{stale_result.stdout}\nstderr:\n{stale_result.stderr}"
    )
    assert stale_result.returncode in _EXISTING_NONZERO_EXIT_CODES, (
        f"Staleness must reuse one of the pre-existing exit codes "
        f"{_EXISTING_NONZERO_EXIT_CODES} (INF-400c-4-iv forbids a new exit "
        f"status), got {stale_result.returncode}."
    )

    combined_stale_output = (stale_result.stdout + stale_result.stderr).lower()
    assert "stale" in combined_stale_output, (
        "Expected the staleness report to say the declaration has gone "
        f"stale.\nstdout:\n{stale_result.stdout}\nstderr:\n{stale_result.stderr}"
    )
    assert declared_sink in (stale_result.stdout + stale_result.stderr), (
        "Expected the staleness report to name the declared path it could "
        f"not reach ({declared_sink}).\nstdout:\n{stale_result.stdout}\n"
        f"stderr:\n{stale_result.stderr}"
    )

    combined_never_written_output = (never_written_result.stdout + never_written_result.stderr).lower()
    assert "stale" not in combined_never_written_output, (
        "The never-written-to (no-work) case must NOT say 'stale' — the two "
        "conditions must be distinguishable, not collapsed into one message."
    )
    assert stale_result.stdout + stale_result.stderr != never_written_result.stdout + never_written_result.stderr, (
        "The stale-directory report and the never-written-to report must be "
        "distinguishable outputs, not byte-identical."
    )

    # Nothing was written into nowhere: the moved-away declared directory
    # must not have been recreated by the mere act of asking about it. The
    # entire original project_dir tree was moved away above, so the OLD
    # absolute declared_sink_path can only exist now if something recreated it.
    assert not declared_sink_path.exists(), (
        f"Resolving/reporting a stale declaration must not conjure the "
        f"missing sink file {declared_sink_path} back into existence."
    )
    assert not declared_sink_path.parent.exists(), (
        f"Resolving/reporting a stale declaration must not conjure the "
        f"missing directory {declared_sink_path.parent} back into existence."
    )


def test_a_build_pointed_at_an_isolated_working_directory_does_not_silently_split_the_sink(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-v: rebuilding into an isolated working directory of an
    already-installed project must not silently give that working directory
    its own, separate sink. Either the same sink is reached, or the second
    build explicitly states it is creating a second one and names the
    project it is dividing.
    """
    # covers: INF-400c-4-v
    # angle: seam
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    first_build = _run_consumer_build(project_dir)
    assert first_build.returncode == 0, (
        f"Fixture setup failed.\nstdout:\n{first_build.stdout}\n"
        f"stderr:\n{first_build.stderr}"
    )
    original_sink = _read_declared_sink(project_dir)

    # An "isolated working directory" of the same project -- e.g. a git
    # worktree checked out elsewhere -- represented here as a second,
    # separate scratch directory that a bare rebuild is pointed at.
    working_dir = tmp_path / "isolated_working_directory"
    working_dir.mkdir()
    second_build = _run_consumer_build(working_dir)
    assert second_build.returncode == 0, (
        f"Fixture setup failed on second build.\nstdout:\n{second_build.stdout}\n"
        f"stderr:\n{second_build.stderr}"
    )
    second_sink = _read_declared_sink(working_dir)

    same_sink = second_sink == original_sink
    combined_second_build_output = (second_build.stdout + second_build.stderr).lower()
    stated_divergence = "sink" in combined_second_build_output and any(
        keyword in combined_second_build_output
        for keyword in ("second", "divid", "separate", "split")
    )

    assert same_sink or stated_divergence, (
        "A rebuild pointed at an isolated working directory of an "
        "already-installed project produced a DIFFERENT declared sink "
        f"({second_sink!r} vs {original_sink!r}) with no statement that a "
        "second sink was being created and which project it divides — this "
        "is the silent third outcome AC INF-400c-4-v forbids.\n"
        f"second build stdout:\n{second_build.stdout}\n"
        f"second build stderr:\n{second_build.stderr}"
    )

    if same_sink:
        # Durability check: a record emitted while the working directory
        # exists must survive that working directory's removal.
        sink_path = Path(original_sink)
        sink_path.parent.mkdir(parents=True, exist_ok=True)
        with sink_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"event": "knowledge_captured", "text": "emitted from isolated working dir"}
                )
                + "\n"
            )

        shutil.rmtree(working_dir)

        assert sink_path.exists(), (
            f"Expected the shared sink {sink_path} to still exist after the "
            "isolated working directory that emitted into it was removed."
        )
        assert "emitted from isolated working dir" in sink_path.read_text(encoding="utf-8"), (
            "A record emitted from inside the isolated working directory "
            "was lost when that working directory was removed."
        )


def test_adopting_the_declaration_does_not_silently_orphan_records_already_accumulating(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-v: when the newly declared sink location differs from
    where records were already accumulating, the run must name BOTH
    locations once -- never present the new, empty location as if it were
    the whole history.

    Mirrors the concrete instance this AC's notes record: in a development
    workspace the build target is the workspace root (no records directory
    of its own), while the operational history sits one level down under a
    nested subdirectory that predates the build-time declaration.
    """
    # covers: INF-400c-4-v
    # angle: boundary
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    # Records already accumulating "one level down", before the declaration
    # is adopted -- the pre-existing corpus this criterion must not orphan.
    legacy_dir = workspace_root / "leafcutter-ai" / "debugging" / "logs"
    legacy_dir.mkdir(parents=True)
    legacy_sink = legacy_dir / "knowledge_emissions.jsonl"
    legacy_lines = [
        json.dumps({"event": "knowledge_captured", "text": f"pre-existing learning {i}"})
        for i in range(3)
    ]
    legacy_sink.write_text("\n".join(legacy_lines) + "\n", encoding="utf-8")

    build_result = _run_consumer_build(workspace_root)
    assert build_result.returncode == 0, (
        f"Fixture setup failed.\nstdout:\n{build_result.stdout}\n"
        f"stderr:\n{build_result.stderr}"
    )
    declared_sink = _read_declared_sink(workspace_root)

    assert declared_sink != str(legacy_sink), (
        "Fixture assumption violated: the newly declared sink happens to "
        "equal the legacy accumulation location, so this test cannot "
        "exercise the divergence it is meant to prove. Adjust the fixture."
    )

    adopt_result = _run_harvester_default(workspace_root, cwd=workspace_root)
    combined_output = adopt_result.stdout + adopt_result.stderr

    assert declared_sink in combined_output, (
        "Expected the run adopting the declaration to name the newly "
        f"declared location ({declared_sink}).\nstdout:\n{adopt_result.stdout}\n"
        f"stderr:\n{adopt_result.stderr}"
    )
    assert str(legacy_sink) in combined_output, (
        "Expected the run to also name the pre-existing accumulation "
        f"location ({legacy_sink}) it is diverging from, rather than "
        "silently presenting the new, empty location as the whole history.\n"
        f"stdout:\n{adopt_result.stdout}\nstderr:\n{adopt_result.stderr}"
    )


def test_the_declared_location_is_obtainable_without_emitting_or_harvesting(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-v: the sink's location must be answerable without
    emitting a record or running a harvest -- and asking must create
    neither the sink file, nor the directory that would hold it, nor any
    record.
    """
    # covers: INF-400c-4-v
    # angle: reachability
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    build_result = _run_consumer_build(project_dir)
    assert build_result.returncode == 0, (
        f"Fixture setup failed.\nstdout:\n{build_result.stdout}\n"
        f"stderr:\n{build_result.stderr}"
    )
    declared_sink = _read_declared_sink(project_dir)
    sink_path = Path(declared_sink)

    assert not sink_path.exists(), (
        f"Fixture assumption violated: the declared sink {sink_path} already "
        "exists immediately after a fresh build, before anything was asked "
        "or emitted."
    )

    query_result = _run_print_sink(project_dir, cwd=project_dir)

    assert query_result.returncode == 0, (
        "Querying the declared sink location must succeed with no prior "
        f"emission or harvest.\nstdout:\n{query_result.stdout}\n"
        f"stderr:\n{query_result.stderr}"
    )
    printed = query_result.stdout.strip()
    assert printed == declared_sink, (
        f"Expected the side-effect-free query to print the declared "
        f"absolute path {declared_sink!r}, got {printed!r}."
    )
    assert Path(printed).is_absolute(), (
        f"The location obtained via the side-effect-free query must be "
        f"absolute, got {printed!r}."
    )

    assert not sink_path.exists(), (
        f"Asking for the declared location must not create the sink file "
        f"{sink_path} as a side effect."
    )
    assert not sink_path.parent.exists(), (
        f"Asking for the declared location must not create the directory "
        f"holding it ({sink_path.parent}) as a side effect."
    )
