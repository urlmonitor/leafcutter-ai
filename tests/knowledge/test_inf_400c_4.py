"""
MODULE: test_inf_400c_4
GOAL: RED test stubs for AC INF-400c-4 -- emitters and the harvester must
    read one knowledge-emission sink per install, declared exactly once, as
    an ABSOLUTE path fixed at build time, from one declared location; and a
    parity check must exist with three independently-exercisable failure
    branches: (1) the emitting and reading sides resolve to different paths,
    (2) the declared value IS the operational telemetry stream, (3) the
    declared value is not absolute, or resolves differently depending on the
    current directory a process was started from.
AC: INF-400c-4 (source_ac)

SPLIT (GE-127a-1 file-size guard): this AC's test suite is split across two
    files that share fixtures from ``_inf_400c_4_helpers.py`` -- this file
    covers the parity-agreement and disagreement branches plus the
    no-side-effect resolution criterion; ``test_inf_400c_4_seams.py`` covers
    the cross-directory seam, the non-absolute/directory-dependent failure
    branch, and the concurrent-writers boundary. See that module's own
    docstring for what is already landed vs. genuinely RED at authoring
    time, and the real-artifact / reachability notes -- both apply
    identically here.
"""
# @ac-tag: INF-400c-4

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _inf_400c_4_helpers import (  # noqa: E402
    _REAL_SURFACES,
    _SYNTHETIC_LITERAL_SURFACE,
    _deploy_harvester,
    _deploy_real_surfaces,
    _deploy_synthetic_surfaces,
    _run_check_sink_parity,
    _run_print_sink,
    _write_declaration,
)


def test_emitting_and_reading_sides_resolve_the_same_absolute_path(tmp_path: Path) -> None:
    # covers: INF-400c-4
    # angle: seam
    target_dir = tmp_path / "install"
    deployed_root = target_dir / ".leafcutter"
    harvester_path = _deploy_harvester(deployed_root)
    _deploy_real_surfaces(deployed_root)
    declared_sink = str(target_dir / "debugging" / "logs" / "knowledge_emissions.jsonl")
    operational_stream = str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl")
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=declared_sink,
        operational_telemetry_stream=operational_stream,
    )

    reading_side = _run_print_sink(harvester_path, cwd=target_dir)
    assert reading_side.returncode == 0, (
        f"reading side (--print-sink) must succeed; stdout={reading_side.stdout!r} "
        f"stderr={reading_side.stderr!r}"
    )
    assert reading_side.stdout.strip() == declared_sink

    check_result = _run_check_sink_parity(target_dir)
    combined = check_result.stdout + check_result.stderr
    assert check_result.returncode == 0, (
        "the four REAL shipped emit surfaces and the reader must all resolve "
        f"to the same declared sink; check output:\n{combined}"
    )
    assert "Inspected 4 surfaces" in combined, (
        "the check must report having inspected all four emitting surfaces "
        "-- a run that resolved none must never report agreement "
        f"(INF-400c-4 test_rationale); got:\n{combined}"
    )
    for surface_id, _src, _parts in _REAL_SURFACES:
        assert surface_id in combined, f"expected {surface_id!r} named in check output:\n{combined}"


def test_parity_check_blocks_when_the_two_sides_resolve_to_different_paths(tmp_path: Path) -> None:
    # covers: INF-400c-4
    # angle: reachability
    target_dir = tmp_path / "install"
    deployed_root = target_dir / ".leafcutter"
    _deploy_harvester(deployed_root)
    declared_sink = str(target_dir / "debugging" / "logs" / "knowledge_emissions.jsonl")
    operational_stream = str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl")
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=declared_sink,
        operational_telemetry_stream=operational_stream,
    )
    # Three surfaces resolve via the real --print-sink invocation (agreeing
    # with the declared sink); one ("it-po") names a different, self-carried
    # literal destination instead -- the emitting/reading disagreement
    # branch 1 exists to catch.
    _deploy_synthetic_surfaces(deployed_root, overrides={"it-po": _SYNTHETIC_LITERAL_SURFACE})

    result = _run_check_sink_parity(target_dir)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        f"a surface disagreeing with the declared sink must block the check; "
        f"got exit 0.\n{combined}"
    )
    assert "it-po" in combined, f"the failing surface must be named:\n{combined}"
    # The AC requires the failure to name BOTH resolved values and which
    # side produced each -- not only the literal the failing surface
    # carries. This is the gap: check_sink_parity's current message for a
    # self-carried literal never prints the declared sink it disagrees with.
    assert declared_sink in combined, (
        "expected the check to also name the OTHER side's resolved value "
        f"(the declared sink {declared_sink!r}) so a reader can see both "
        f"paths and which side produced each; got:\n{combined}"
    )


def test_parity_check_blocks_when_the_declared_value_is_the_operational_telemetry_stream(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-4
    # angle: failure
    target_dir = tmp_path / "install"
    deployed_root = target_dir / ".leafcutter"
    _deploy_harvester(deployed_root)
    _deploy_synthetic_surfaces(deployed_root, overrides={})
    # Both sides agree -- and the agreed value IS the operational telemetry
    # stream. This is the settlement discriminator: an implementation that
    # "ends the disagreement" by repointing everything at the shared
    # operational file must still be rejected.
    shared_stream = str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl")
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=shared_stream,
        operational_telemetry_stream=shared_stream,
    )

    result = _run_check_sink_parity(target_dir)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "declaring the operational telemetry stream itself as the "
        "knowledge-emission sink must be rejected even though every surface "
        f"agrees with it -- got exit 0 (PASS).\n{combined}"
    )


def test_resolving_the_sink_path_creates_neither_the_file_nor_its_directory(tmp_path: Path) -> None:
    # covers: INF-400c-4
    # angle: criterion
    target_dir = tmp_path / "install"
    deployed_root = target_dir / ".leafcutter"
    harvester_path = _deploy_harvester(deployed_root)
    declared_sink = target_dir / "debugging" / "logs" / "knowledge_emissions.jsonl"
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=str(declared_sink),
        operational_telemetry_stream=str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl"),
    )
    assert not declared_sink.parent.exists(), "fixture must start with no debugging/ directory at all"

    result = _run_print_sink(harvester_path, cwd=target_dir)

    assert result.returncode == 0, f"resolving the declared sink must succeed; {result.stdout!r} {result.stderr!r}"
    assert result.stdout.strip() == str(declared_sink)
    assert not declared_sink.exists(), "resolving the path must never create the sink file"
    assert not declared_sink.parent.exists(), "resolving the path must never create the sink's parent directory"
