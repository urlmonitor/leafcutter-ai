"""Linux-owned descendants cannot outlive a completed worker invocation."""
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.background_worker.execution_boundary import ExecutorError, run_process

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux child supervision")


def child_script(detached, parent_wait):
    return f"""
import os,sys,time
from pathlib import Path
pid=os.fork()
if pid == 0:
    if {detached!r}: os.setsid()
    for fd in (0,1,2):
        null=os.open('/dev/null',os.O_RDWR)
        os.dup2(null,fd)
        if null > 2: os.close(null)
    time.sleep(120)
else:
    Path('child.pid').write_text(str(pid))
    print('root complete',flush=True)
    if {parent_wait!r}: time.sleep(120)
"""


@pytest.mark.parametrize("detached", [False, True])
def test_parent_success_reaps_survivor_without_touching_unrelated_process(tmp_path, detached):
    # covers: ACD-1300g-2 ACD-1300c-1-i
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
    try:
        result = run_process([sys.executable, "-c", child_script(detached, False)], cwd=tmp_path, timeout=10)
        assert result.returncode == 0 and "root complete" in result.stdout
        child = int((tmp_path / "child.pid").read_text())
        assert not Path(f"/proc/{child}").exists()
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_timeout_reaps_detached_descendant_before_confirming_termination(tmp_path):
    # covers: ACD-1300c-1 ACD-1300c-1-i
    with pytest.raises(ExecutorError, match="process tree terminated") as caught:
        run_process([sys.executable, "-c", child_script(True, True)], cwd=tmp_path, timeout=1)
    assert caught.value.evidence["termination_confirmed"] is True
    assert not Path(f"/proc/{int((tmp_path / 'child.pid').read_text())}").exists()


@pytest.mark.parametrize("receipt", [
    '{"cleaned":false,"returncode":0}', '[]',
    '{"cleaned":true,"returncode":null,"cancelled":false}',
    '{"cleaned":"true","returncode":0,"cancelled":false}',
])
def test_supervisor_failure_cannot_report_success(tmp_path, receipt):
    # covers: ACD-1300c-1-i
    from scripts.background_worker.owned_process import LinuxOwnedProcess

    process = LinuxOwnedProcess([sys.executable, "-c", "pass"], cwd=tmp_path,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True)
    process.process.wait(timeout=5)
    process.receipt.write_text(receipt)
    with pytest.raises(ExecutorError, match="Uncertain process termination"):
        process.communicate(timeout=5)


def test_cancelled_receipt_cannot_be_success(tmp_path):
    # covers: ACD-1300c-1-i
    from scripts.background_worker.owned_process import LinuxOwnedProcess

    process = LinuxOwnedProcess([sys.executable, "-c", "pass"], cwd=tmp_path,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True)
    process.process.wait(timeout=5)
    process.receipt.write_text('{"cleaned":true,"returncode":0,"cancelled":true}')
    process.communicate(timeout=5)
    assert process.returncode != 0


def test_supervision_preserves_input_output_and_nonzero_status(tmp_path):
    # covers: ACD-1300g-2
    result = run_process([sys.executable, "-c", "import sys; print(sys.stdin.read()); print('diagnostic', file=sys.stderr)"],
                         cwd=tmp_path, input_text="input body", timeout=5)
    assert result.stdout.strip() == "input body" and result.stderr.strip() == "diagnostic"
    with pytest.raises(ExecutorError) as caught:
        run_process([sys.executable, "-c", "raise SystemExit(7)"], cwd=tmp_path, timeout=5)
    assert caught.value.evidence["returncode"] == 7


def test_failed_supervisor_launch_removes_private_receipt_directory(tmp_path, monkeypatch):
    # covers: ACD-1300c-1-i
    from scripts.background_worker import owned_process

    original_directory = owned_process.tempfile.TemporaryDirectory
    created = []
    def directory(**kwargs):
        result = original_directory(dir=tmp_path, **kwargs)
        created.append(Path(result.name))
        return result
    failure = OSError("controlled launch failure")
    def launch(*args, **kwargs):
        raise failure
    monkeypatch.setattr(owned_process.tempfile, "TemporaryDirectory", directory)
    monkeypatch.setattr(owned_process.subprocess, "Popen", launch)
    with pytest.raises(OSError) as caught:
        owned_process.LinuxOwnedProcess(["not-started"])
    assert caught.value is failure
    assert len(created) == 1 and not created[0].exists()
