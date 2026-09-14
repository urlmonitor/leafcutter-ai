"""
MODULE: test_inf_400c_4_seams
GOAL: RED test stubs for AC INF-400c-4 (continued) -- cross-directory
    seam behavior, the non-absolute / directory-dependent failure branch,
    and the concurrent-writers boundary.
AC: INF-400c-4 (source_ac)

SPLIT (GE-127a-1 file-size guard): this module is the second half of the
    INF-400c-4 test suite, split out of ``test_inf_400c_4.py`` purely to
    keep each file under the check-file-size guard's line limit. Both
    modules share fixtures from ``_inf_400c_4_helpers.py``; see
    ``test_inf_400c_4.py``'s own docstring for what is already landed vs.
    genuinely RED at authoring time, and the real-artifact / reachability
    notes -- both apply identically here.
"""
# @ac-tag: INF-400c-4

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _inf_400c_4_helpers import (  # noqa: E402
    _TIMEOUT_SECONDS,
    _deploy_harvester,
    _deploy_synthetic_surfaces,
    _run_check_sink_parity,
    _run_harvester_default,
    _run_print_sink,
    _write_declaration,
)


def test_the_declaration_reads_the_same_from_an_isolated_working_directory_and_from_the_project_root(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-4
    # angle: seam
    target_dir = tmp_path / "install"
    deployed_root = target_dir / ".leafcutter"
    harvester_path = _deploy_harvester(deployed_root)
    declared_sink = str(target_dir / "debugging" / "logs" / "knowledge_emissions.jsonl")
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=declared_sink,
        operational_telemetry_stream=str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl"),
    )
    isolated_working_dir = target_dir / "isolated_working_directory"
    isolated_working_dir.mkdir(parents=True)

    from_root = _run_print_sink(harvester_path, cwd=target_dir)
    from_isolated = _run_print_sink(harvester_path, cwd=isolated_working_dir)

    assert from_root.returncode == 0 and from_isolated.returncode == 0, (
        f"both reads must succeed; root={from_root!r} isolated={from_isolated!r}"
    )
    root_value = from_root.stdout.strip()
    isolated_value = from_isolated.stdout.strip()
    assert root_value == isolated_value == declared_sink, (
        f"expected identical declared path from both directories; "
        f"root={root_value!r} isolated={isolated_value!r} declared={declared_sink!r}"
    )
    assert Path(root_value).is_absolute() and Path(isolated_value).is_absolute()
    assert not root_value.startswith(str(isolated_working_dir)), (
        "the declared path must lie outside every isolated working directory"
    )


def test_a_record_written_from_an_isolated_working_directory_is_still_there_after_it_is_removed(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-4
    # angle: real_artifact
    target_dir = tmp_path / "install"
    deployed_root = target_dir / ".leafcutter"
    harvester_path = _deploy_harvester(deployed_root)
    declared_sink = target_dir / "debugging" / "logs" / "knowledge_emissions.jsonl"
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=str(declared_sink),
        operational_telemetry_stream=str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl"),
    )
    isolated_working_dir = target_dir / "isolated_working_directory"
    isolated_working_dir.mkdir(parents=True)

    # A real subprocess, standing inside the isolated working directory,
    # obtains the declared absolute path and appends a record there.
    print_sink_result = _run_print_sink(harvester_path, cwd=isolated_working_dir)
    assert print_sink_result.returncode == 0
    resolved_path = Path(print_sink_result.stdout.strip())
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    record = json.dumps({"event": "knowledge_captured", "text": "written from an isolated working directory"})
    with open(resolved_path, "a", encoding="utf-8") as fh:
        fh.write(record + "\n")

    shutil.rmtree(isolated_working_dir)

    assert resolved_path.exists(), (
        f"the record's file {resolved_path} must survive removal of the "
        "isolated working directory that wrote it"
    )
    content_after_removal = resolved_path.read_text(encoding="utf-8")
    assert "written from an isolated working directory" in content_after_removal


def test_parity_check_blocks_a_relative_declared_value_and_a_directory_dependent_read(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-4
    # angle: failure
    # --- Variant A: both sides agree on a knowledge-only NAME, but that
    # declared value is RELATIVE, not absolute. -------------------------
    target_dir = tmp_path / "install_relative"
    deployed_root = target_dir / ".leafcutter"
    _deploy_harvester(deployed_root)
    _deploy_synthetic_surfaces(deployed_root, overrides={})
    relative_value = "debugging/logs/knowledge_emissions.jsonl"
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=relative_value,
        operational_telemetry_stream=str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl"),
    )

    variant_a_result = _run_check_sink_parity(target_dir)
    combined_a = variant_a_result.stdout + variant_a_result.stderr
    assert variant_a_result.returncode != 0, (
        "a non-absolute declared value must be rejected even though every "
        f"surface agrees with it verbatim -- got exit 0 (PASS).\n{combined_a}"
    )
    assert Path(relative_value).is_absolute() is False  # fixture sanity

    # --- Variant B: the SAME relative declared value, read as the ordinary
    # (non-print-sink) run default from two different current directories,
    # resolves to two DIFFERENT absolute files on disk. ------------------
    cwd_a = target_dir / "cwd_a"
    cwd_b = target_dir / "cwd_b"
    cwd_a.mkdir(parents=True)
    cwd_b.mkdir(parents=True)
    harvester_path = deployed_root / "scripts" / "knowledge" / "harvest_learnings.py"

    local_sink_a = cwd_a / relative_value
    local_sink_b = cwd_b / relative_value
    local_sink_a.parent.mkdir(parents=True, exist_ok=True)
    local_sink_b.parent.mkdir(parents=True, exist_ok=True)
    local_sink_a.write_text(
        json.dumps({"event": "knowledge_captured", "text": "record local to cwd_a"}) + "\n",
        encoding="utf-8",
    )
    local_sink_b.write_text(
        json.dumps({"event": "knowledge_captured", "text": "record local to cwd_b"}) + "\n",
        encoding="utf-8",
    )

    run_a = _run_harvester_default(harvester_path, cwd=cwd_a)
    run_b = _run_harvester_default(harvester_path, cwd=cwd_b)
    assert run_a.returncode == 0 and run_b.returncode == 0

    resolved_a = (cwd_a / relative_value).resolve()
    resolved_b = (cwd_b / relative_value).resolve()
    assert resolved_a != resolved_b, (
        "fixture sanity: the same relative declared value must resolve to "
        f"two different absolute files depending on cwd; got {resolved_a} "
        f"and {resolved_b} both"
    )

    # The check must catch this directory-dependent-read hazard when
    # pointed at either install -- it currently has no mechanism to do so.
    check_a = _run_check_sink_parity(cwd_a)
    combined_check_a = check_a.stdout + check_a.stderr
    assert check_a.returncode != 0, (
        "a declared value whose resolution depends on the current working "
        f"directory must be rejected by the parity check.\n{combined_check_a}"
    )


def test_two_units_of_work_emitting_at_once_lose_no_record_and_interleave_none(tmp_path: Path) -> None:
    # covers: INF-400c-4
    # angle: boundary
    target_dir = tmp_path / "install"
    deployed_root = target_dir / ".leafcutter"
    harvester_path = _deploy_harvester(deployed_root)
    declared_sink = target_dir / "debugging" / "logs" / "knowledge_emissions.jsonl"
    declared_sink.parent.mkdir(parents=True, exist_ok=True)
    declared_sink.touch()
    _write_declaration(
        deployed_root,
        knowledge_emission_sink=str(declared_sink),
        operational_telemetry_stream=str(target_dir / "debugging" / "logs" / "agent_telemetry.jsonl"),
    )
    isolated_working_dir = target_dir / "isolated_working_directory"
    isolated_working_dir.mkdir(parents=True)

    appender_script = tmp_path / "_concurrent_appender.py"
    appender_script.write_text(
        "import json, sys\n"
        "sink, agent, n = sys.argv[1], sys.argv[2], int(sys.argv[3])\n"
        "with open(sink, 'a', encoding='utf-8') as fh:\n"
        "    for i in range(n):\n"
        "        fh.write(json.dumps({'event': 'knowledge_captured', 'agent': agent, 'seq': i}) + chr(10))\n",
        encoding="utf-8",
    )

    n_records = 200
    proc_a = subprocess.Popen(
        [sys.executable, str(appender_script), str(declared_sink), "unit-a", str(n_records)],
        cwd=str(target_dir),
    )
    proc_b = subprocess.Popen(
        [sys.executable, str(appender_script), str(declared_sink), "unit-b", str(n_records)],
        cwd=str(isolated_working_dir),
    )
    proc_a.wait(timeout=_TIMEOUT_SECONDS)
    proc_b.wait(timeout=_TIMEOUT_SECONDS)
    assert proc_a.returncode == 0 and proc_b.returncode == 0

    lines = declared_sink.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 * n_records, (
        f"expected {2 * n_records} total appended lines with none lost or "
        f"merged, got {len(lines)}"
    )
    seen_by_agent: dict[str, set[int]] = {"unit-a": set(), "unit-b": set()}
    for line_no, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"line {line_no} does not parse as its own JSON object "
                f"(interleaved with another record?): {line!r} ({exc})"
            ) from exc
        assert record.get("event") == "knowledge_captured"
        agent = record["agent"]
        assert agent in seen_by_agent, f"unexpected agent {agent!r} at line {line_no}"
        seen_by_agent[agent].add(record["seq"])
    assert seen_by_agent["unit-a"] == set(range(n_records))
    assert seen_by_agent["unit-b"] == set(range(n_records))
