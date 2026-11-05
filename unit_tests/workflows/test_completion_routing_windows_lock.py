"""INF-700a-5-iv: completion_routing must load and lock without POSIX fcntl.

Each test loads scripts/knowledge/completion_routing.py fresh in a simulated
platform (sys.modules entry of None makes ``import X`` raise ImportError).
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "knowledge" / "completion_routing.py"


def _load_fresh(name: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _msvcrt_stub(calls: list):
    stub = types.ModuleType("msvcrt")
    stub.LK_LOCK = 1
    stub.LK_UNLCK = 0
    stub.LK_NBLCK = 2
    stub.locking = lambda fd, mode, nbytes: calls.append(("locking", mode, nbytes))
    return stub


def _fcntl_stub(calls: list):
    stub = types.ModuleType("fcntl")
    stub.LOCK_EX = 2
    stub.LOCK_UN = 8
    stub.flock = lambda fd, op: calls.append(("flock", op))
    return stub


def test_completion_routing_imports_when_fcntl_is_unavailable(monkeypatch):
    # covers: INF-700a-5-iv
    # angle: failure
    """Windows host: fcntl missing, msvcrt present -> module must import."""
    monkeypatch.setitem(sys.modules, "fcntl", None)
    monkeypatch.setitem(sys.modules, "msvcrt", _msvcrt_stub([]))
    module = _load_fresh("_cr_win_import")
    assert callable(module.claim_and_confirm_routed)


def test_claim_lock_uses_msvcrt_locking_on_windows(monkeypatch, tmp_path):
    # covers: INF-700a-5-iv
    # angle: criterion
    """msvcrt.locking locks then unlocks, and the claim lands in the store."""
    calls: list = []
    monkeypatch.setitem(sys.modules, "fcntl", None)
    monkeypatch.setitem(sys.modules, "msvcrt", _msvcrt_stub(calls))
    module = _load_fresh("_cr_win_lock")
    state = tmp_path / "routed.json"
    claimed = module.claim_and_confirm_routed(state_path=state, record_ids=["rec-1"])
    assert claimed == ["rec-1"]
    modes = [c[1] for c in calls if c[0] == "locking"]
    assert modes == [1, 0]
    again = module.claim_and_confirm_routed(state_path=state, record_ids=["rec-1"])
    assert again == []


def test_claim_lock_uses_fcntl_flock_on_posix(monkeypatch, tmp_path):
    # covers: INF-700a-5-iv
    # angle: criterion
    """POSIX: flock LOCK_EX then LOCK_UN; msvcrt absent."""
    calls: list = []
    monkeypatch.setitem(sys.modules, "fcntl", _fcntl_stub(calls))
    monkeypatch.setitem(sys.modules, "msvcrt", None)
    module = _load_fresh("_cr_posix_lock")
    claimed = module.claim_and_confirm_routed(
        state_path=tmp_path / "routed.json", record_ids=["rec-1"]
    )
    assert claimed == ["rec-1"]
    assert calls == [("flock", 2), ("flock", 8)]


def test_claim_lock_raises_when_no_lock_primitive_exists(monkeypatch, tmp_path):
    # covers: INF-700a-5-iv
    # angle: boundary
    """Neither primitive: must raise, never merge a claim unlocked."""
    monkeypatch.setitem(sys.modules, "fcntl", None)
    monkeypatch.setitem(sys.modules, "msvcrt", None)
    state = tmp_path / "routed.json"
    with pytest.raises(Exception) as excinfo:  # noqa: PT011
        module = _load_fresh("_cr_no_lock")
        module.claim_and_confirm_routed(state_path=state, record_ids=["rec-1"])
    assert not isinstance(excinfo.value, ModuleNotFoundError) or "fcntl" not in str(excinfo.value)
    assert not state.exists()
