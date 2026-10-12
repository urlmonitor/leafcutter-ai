"""
MODULE: tests.kernel.persistence.cas_child
GOAL: Child process for the cross-process compare_and_update test: race one revision bump.
BUSINESS CONTEXT: Cancel and resume run in separate processes (design part 3); a lost cancel must
    be impossible, which only a test with real processes can show.
ARCHITECTURE: `python -m tests.kernel.persistence.cas_child <run_root> <run_id> <label> <start>`.
    It widens the check-to-write window of the real FileRunStore (a slow atomic write) so an
    unguarded compare-and-update loses reliably, waits for a shared start time and prints
    `<label> True|False`.
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from kernel.persistence import CancelInfo
from kernel.persistence import run_store as run_store_module
from kernel.persistence.run_store import FileRunStore

_real_write = run_store_module.atomic_write_bytes


def _slow_write(path: Path, data: bytes) -> None:
    """Write like the real helper after a pause, as a loaded disk would."""
    time.sleep(0.3)
    _real_write(path, data)


def main(argv: list[str]) -> int:
    """Race one compare_and_update at revision 0 and print whether this process won."""
    root, run_id, label, start = Path(argv[0]), argv[1], argv[2], float(argv[3])
    run_store_module.atomic_write_bytes = _slow_write
    store = FileRunStore(root)
    current = store.get_run(run_id)
    cancel = CancelInfo(by=label, at=datetime.now(UTC))
    time.sleep(max(0.0, start - time.time()))
    won = store.compare_and_update(
        current.model_copy(update={"state_revision": 1, "cancel": cancel}), 0)
    print(f"{label} {won}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
