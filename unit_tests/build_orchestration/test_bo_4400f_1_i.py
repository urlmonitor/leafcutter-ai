"""
MODULE: test_bo_4400f_1_i
GOAL: Red-first behavioural tests for BO-4400f-1-i -- scratch owned by a run
    that is still going is never expired, however old it is; once that run
    ends, the next application of the rule finds it expired.
PROOF SHAPE: a real long-lived child process owns the item; the item's label
    and mtimes are set 29 hours into the past; the DEPLOYED scratch module
    (shared reference build, read-only) classifies it and the DEPLOYED sweep
    runs over it, each as a separate process; then the owner is ended and the
    rule is applied again. See _bo4400f1_helpers.py for the contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ._bo4400f1_helpers import backdate_item, make_sandbox, tree_digest

AGE_LIMIT_HOURS = 24
ITEM_AGE_HOURS = 29


@pytest.fixture
def sandbox(shared_reference_layout):
    box, holder = make_sandbox(Path(shared_reference_layout) / ".leafcutter" / "scripts")
    yield box
    holder.cleanup()


def _classify_now(sandbox, item: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return sandbox.call("classify", {"item": item, "now": now, "age_limit_hours": AGE_LIMIT_HOURS})


def _old_item_held_by_live_owner(sandbox, owner: str):
    holder, item = sandbox.start_holding_owner(owner, "build-feature")
    (Path(item) / "work.txt").write_text("half-built artefact\n", encoding="utf-8")
    backdate_item(item, ITEM_AGE_HOURS)
    return holder, item


@pytest.mark.shared_layout_reader
def test_old_scratch_of_active_run_is_not_expired_or_swept(sandbox):
    # covers: BO-4400f-1-i
    # angle: discrimination
    # must_catch: age-only expiry deletes an active drive's scratch
    holder, active = _old_item_held_by_live_owner(sandbox, "run-long-epic-drive")
    try:
        # Negative control: an equally old item whose owner has ended IS swept,
        # so a sweep that removes nothing at all cannot pass this test.
        ended = sandbox.call("new_item", {"owner": "run-finished", "route": "build-feature"})["item"]
        backdate_item(ended, ITEM_AGE_HOURS)
        before = tree_digest(Path(active))

        assert _classify_now(sandbox, active) == {"expired": False, "reason": "owner_active"}
        report = sandbox.sweep()

        assert Path(active).is_dir(), "the sweep deleted a running drive's scratch"
        assert tree_digest(Path(active)) == before, "the active item is not byte-identical"
        assert active not in report["removed_paths"], report
        assert not Path(ended).exists(), "the ended owner's old item was not swept"
        assert report["removed"]["scratch"] == 1, report
    finally:
        holder.communicate("\n", timeout=30)


@pytest.mark.shared_layout_reader
def test_scratch_expires_once_owner_ends(sandbox):
    # covers: BO-4400f-1-i
    # angle: boundary
    holder, item = _old_item_held_by_live_owner(sandbox, "run-ending-soon")
    try:
        assert _classify_now(sandbox, item) == {"expired": False, "reason": "owner_active"}
    finally:
        holder.communicate("\n", timeout=30)
    assert holder.returncode is not None

    assert _classify_now(sandbox, item) == {"expired": True, "reason": "owner_ended_and_old"}
    report = sandbox.sweep()
    assert item in report["removed_paths"], report
    assert report["removed"]["scratch"] == 1, report
    assert not Path(item).exists()
