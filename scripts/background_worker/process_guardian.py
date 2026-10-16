"""Linux-only child supervisor; reap adopted descendants before confirming exit."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def cleanup_children(seconds=15):
    deadline = time.monotonic() + seconds
    children_file = Path(f"/proc/self/task/{os.getpid()}/children")
    while time.monotonic() < deadline:
        for value in children_file.read_text().split():
            # Direct children cannot be reparented away while we live. Their PID
            # remains allocated until we reap them; pidfds make signaling exact.
            try:
                descriptor = os.pidfd_open(int(value))
            except ProcessLookupError:
                continue
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                os.close(descriptor)
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return True
            if pid == 0:
                break
        time.sleep(0.02)
    return False


def main():
    destination = Path(sys.argv[1])
    stopped = False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    libc = ctypes.CDLL(None, use_errno=True)
    parent = int(sys.argv[2])
    if libc.prctl(36, 1, 0, 0, 0) or libc.prctl(1, signal.SIGTERM, 0, 0, 0):
        raise OSError(ctypes.get_errno(), "Cannot establish Linux child supervision")
    if os.getppid() != parent:
        stopped = True
    code = None
    try:
        if not stopped:
            child = subprocess.Popen(sys.argv[3:])
            while not stopped:
                code = child.poll()
                if code is not None:
                    break
                time.sleep(0.02)
    finally:
        cleaned = cleanup_children()
        destination.write_text(json.dumps({"cleaned": cleaned, "returncode": code,
                                           "cancelled": stopped}), encoding="utf-8")
    return 0 if cleaned else 125


if __name__ == "__main__":
    sys.exit(main())
