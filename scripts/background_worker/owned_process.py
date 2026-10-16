"""Keep a Linux supervisor alive until every owned descendant is reaped."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


class LinuxOwnedProcess:
    def __init__(self, argv, **options):
        if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
            raise OSError("Linux pidfd support is required for owned execution")
        self.directory = tempfile.TemporaryDirectory(prefix="leafcutter-process-")
        self.receipt = Path(self.directory.name) / "result.json"
        self.returncode = None
        self.descriptor = None
        helper = Path(__file__).with_name("process_guardian.py")
        try:
            self.process = subprocess.Popen([sys.executable, str(helper), str(self.receipt), str(os.getpid()), *argv], **options)
        except OSError:
            self.directory.cleanup()
            raise
        self.pid = self.process.pid
        try:
            self.descriptor = os.pidfd_open(self.pid)
        except OSError:
            # A very short invocation may have exited; its receipt is still
            # required. Resource/permission failures also leave cleanup uncertain
            # on cancellation. Never fall back to an unpinned numeric PID.
            pass

    def communicate(self, **options):
        stdout, stderr = self.process.communicate(**options)
        try:
            receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
            if (not isinstance(receipt, dict) or receipt.get("cleaned") is not True
                    or type(receipt.get("cancelled")) is not bool
                    or not (type(receipt.get("returncode")) is int
                            or (receipt.get("returncode") is None and receipt["cancelled"]))
                    or self.process.returncode != 0):
                raise ValueError("Owned descendant cleanup incomplete")
            self.returncode = receipt["returncode"]
            if receipt["cancelled"] or self.returncode is None:
                self.returncode = -signal.SIGTERM
        except (OSError, ValueError, KeyError) as exc:
            from .execution_boundary import ExecutorError

            raise ExecutorError("Uncertain process termination; retain the execution lease") from exc
        finally:
            if self.descriptor is not None:
                os.close(self.descriptor)
                self.descriptor = None
            self.directory.cleanup()
        return stdout, stderr

    def kill(self):
        if self.descriptor is not None:
            try:
                signal.pidfd_send_signal(self.descriptor, signal.SIGTERM)
            except ProcessLookupError:
                pass


def start_process(argv, **options):
    if sys.platform == "linux":
        return LinuxOwnedProcess(argv, **options)
    try:
        return subprocess.Popen(argv, **options)
    except OSError:
        raise
