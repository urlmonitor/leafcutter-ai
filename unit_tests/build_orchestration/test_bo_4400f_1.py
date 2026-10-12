"""
MODULE: test_bo_4400f_1
GOAL: Red-first behavioural tests for BO-4400f-1 -- every piece of scratch
    lands in the one scratch location, labelled with owner and creation time,
    and the expiry rule is exactly: owner ended AND old, or owner unknown AND
    old; an active owner never expires.
PROOF SHAPE: the DEPLOYED scratch module (shared reference build, read-only)
    is driven in separate processes with HOME / XDG_CACHE_HOME redirected and
    TMPDIR pointed at a watched folder. See _bo4400f1_helpers.py for the
    assumed production contract.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from . import _bo4400f1_routes as routes
from ._bo4400f1_helpers import make_sandbox, read_label, snapshot


def _deployed_scripts(layout) -> Path:
    """The deployed scripts dir; the module's presence is asserted on first use
    (inside the test body, so a missing module is a FAILURE, not a setup ERROR)."""
    return Path(layout) / ".leafcutter" / "scripts"


@pytest.fixture
def sandbox(shared_reference_layout):
    box, holder = make_sandbox(_deployed_scripts(shared_reference_layout))
    yield box
    holder.cleanup()


@pytest.mark.shared_layout_reader
def test_route_throwaway_files_land_only_in_scratch_location(sandbox):
    # covers: BO-4400f-1
    # angle: criterion
    # must_catch: quick fix still writes qf-*-tmp into the project root
    # must_catch: subprocess temp writes go to the system temp folder
    watched = [sandbox.temp_standin, sandbox.project]
    before = snapshot(*watched)
    locations = sandbox.call("locations", {})
    root = Path(locations["root"])
    assert root.is_absolute()
    assert str(root).startswith(str(sandbox.home / ".cache")), root
    created = []
    for route in ("build-ticket", "quick-fix", "fast-lane"):
        item = Path(sandbox.call("new_item", {"owner": f"run-{route}", "route": route})["item"])
        env = {**sandbox.env, "TMPDIR": str(item), "TEMP": str(item), "TMP": str(item)}
        child = subprocess.run(  # noqa: S603
            [sys.executable, "-c",
             "import tempfile,sys;"
             "fd,p=tempfile.mkstemp(prefix='throwaway_');print(p);"
             "d=tempfile.mkdtemp(prefix='throwdir_');print(d)"],
            cwd=sandbox.project, env=env, capture_output=True, text=True, timeout=60, check=True,
        )
        created += child.stdout.split()
        assert item.is_dir() and root in item.parents, (root, item)
    assert len(created) == 6
    for path in created:
        assert root in Path(path).parents, f"{path} escaped the scratch root"
    assert snapshot(*watched) == before, "temp stand-in or project root gained an entry"
    declared = " ".join(locations["durable"])
    assert "test-logs" in declared and "debugging" in declared, declared


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("script", sorted(routes.ROUTES))
def test_route_workflow_obtains_its_scratch_item_and_exports_temp_vars(
    script, sandbox, shared_reference_layout
):
    # covers: BO-4400f-1
    # angle: reachability
    # must_catch: quick fix still writes qf-*-tmp into the project root
    # must_catch: subprocess temp writes go to the system temp folder
    layout = Path(shared_reference_layout)
    workflow = layout / ".leafcutter" / "workflows" / script
    route, process_labels = routes.ROUTES[script]
    item = sandbox.call("new_item", {"owner": "seed", "route": "probe"})["item"]
    result = routes.run_route(workflow, item, sandbox.project)
    assert result.error == "", result.error
    labels = [c.label for c in result.agent_calls]
    asks = [c for c in result.agent_calls if c.label == routes.SCRATCH_LABEL]
    assert len(asks) == 1, f"{script} must obtain exactly one scratch item: {labels}"
    first = labels.index(routes.SCRATCH_LABEL)
    for label in process_labels:
        assert label in labels[first + 1:], f"{label} not dispatched after the scratch item: {labels}"
        prompt = routes.prompt_of(result.agent_calls[labels.index(label, first + 1)])
        for var in ("TMPDIR", "TEMP", "TMP"):
            assert var in prompt, f"{script}/{label} does not set {var}"
        assert f'"{item}"' in prompt, f"{script}/{label} does not point the temp vars at the item"
    every_prompt = " ".join(routes.prompt_of(c) for c in result.agent_calls)
    assert "/tmp/quick" not in every_prompt, f"{script} still writes scratch into the system temp folder"

    # The command the step hands its executor really creates a labelled item in
    # the scratch root, owned by the long-lived process that ran it ($PPID).
    command = routes.scratch_command(routes.prompt_of(asks[0]))
    assert command and f"{route}" in command, routes.prompt_of(asks[0])
    made = subprocess.run(  # noqa: S603
        ["bash", "-c", command], cwd=layout, env=sandbox.env,
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert made.returncode == 0, made.stderr[-1500:]
    created = json.loads(made.stdout.strip().splitlines()[-1])["item"]
    root = Path(sandbox.call("locations", {})["root"])
    assert root in Path(created).parents, (root, created)
    label = read_label(created)
    assert label["route"] == route and label["pid"] == os.getpid(), label
    now = datetime.now(timezone.utc) + timedelta(hours=48)
    verdict = sandbox.call("classify", {"item": created, "now": now.isoformat(), "age_limit_hours": 24})
    assert verdict == {"expired": False, "reason": "owner_active"}, verdict

    # Fail-open: no item means no scratch note and an otherwise identical run.
    bare = routes.run_route(workflow, None, sandbox.project)
    assert [c.label for c in bare.agent_calls] == labels
    assert routes.NOTE_MARKER not in " ".join(routes.prompt_of(c) for c in bare.agent_calls)


@pytest.mark.shared_layout_reader
def test_every_scratch_item_carries_owner_and_creation_time(sandbox):
    # covers: BO-4400f-1
    # angle: seam
    owner, item = sandbox.start_holding_owner("run-42-xyz", "quick-fix")
    try:
        label = read_label(item)
        assert label["owner_run_id"] == "run-42-xyz"
        assert label["route"] == "quick-fix"
        assert label["pid"] == owner.pid
        assert label["host"]
        created = datetime.fromisoformat(label["created_at"])
        assert created.utcoffset() == timedelta(0), "created_at must be UTC"
        assert abs((datetime.now(timezone.utc) - created).total_seconds()) < 120
    finally:
        owner.communicate("\n", timeout=30)


def _classify(sandbox, item: str, hours_after_creation: float, label_gone: bool) -> dict:
    created = datetime.fromtimestamp(os.stat(item).st_mtime, tz=timezone.utc)
    if not label_gone:
        created = datetime.fromisoformat(read_label(item)["created_at"])
    now = created + timedelta(hours=hours_after_creation)
    return sandbox.call("classify", {"item": item, "now": now.isoformat(), "age_limit_hours": 24})


@pytest.mark.shared_layout_reader
def test_expiry_rule_truth_table(sandbox):
    # covers: BO-4400f-1
    # angle: discrimination
    # must_catch: age-only expiry
    # must_catch: unknown owner never expires
    young, old = 1, 48
    cases = []  # (name, item, expected_expired, expected_reason_old, expected_reason_young)
    holder, active_item = sandbox.start_holding_owner("run-active", "build-ticket")
    try:
        cases.append(("active", active_item, False, "owner_active", "owner_active"))
        ended_item = sandbox.call("new_item", {"owner": "run-ended", "route": "fast-lane"})["item"]
        cases.append(("ended", ended_item, True, "owner_ended_and_old", "within_age"))
        missing = sandbox.call("new_item", {"owner": "run-nolabel", "route": "x"})["item"]
        (Path(missing) / "label.json").unlink()
        cases.append(("unknown-missing", missing, True, "owner_unknown_and_old", "within_age"))
        corrupt = sandbox.call("new_item", {"owner": "run-corrupt", "route": "x"})["item"]
        (Path(corrupt) / "label.json").write_text("{not json", encoding="utf-8")
        cases.append(("unknown-corrupt", corrupt, True, "owner_unknown_and_old", "within_age"))

        expired_total = 0
        for name, item, expires_when_old, reason_old, reason_young in cases:
            gone = name.startswith("unknown")
            old_verdict = _classify(sandbox, item, old, gone)
            young_verdict = _classify(sandbox, item, young, gone)
            assert old_verdict == {"expired": expires_when_old, "reason": reason_old}, (name, old_verdict)
            assert young_verdict == {"expired": False, "reason": reason_young}, (name, young_verdict)
            expired_total += old_verdict["expired"] + young_verdict["expired"]
        assert expired_total == 3, "exactly ended-old and the two unknown-old items expire"
    finally:
        holder.communicate("\n", timeout=30)
