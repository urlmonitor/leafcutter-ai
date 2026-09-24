"""Process-lifetime locks released by the OS after crashes, without PID guessing."""

from contextlib import contextmanager
import os
import logging

LOGGER = logging.getLogger(__name__)


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = open(path, "a+b")
    except OSError as exc:
        LOGGER.warning("Cannot open worker lock: %s", type(exc).__name__)
        raise
    acquired = False
    try:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        yield acquired
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
