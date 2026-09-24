"""Process isolation, credential hygiene and inspected-check evidence for worker executors."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
import signal
import subprocess
import time

LOGGER = logging.getLogger(__name__)


class ExecutorError(RuntimeError):
    """An external execution did not produce trustworthy evidence."""


def permission_overrides(*, readonly=False):
    """Deny host reads as well as writes; unsupported native policies fail closed."""
    access = "read" if readonly else "write"
    return [
        'default_permissions="leafcutter-worker"',
        'permissions.leafcutter-worker.filesystem={ ":root"="deny", ":minimal"="read", ":workspace_roots"={ "."="'
        + access
        + '", ".git"="read", ".codex"="read", "**/*.env"="deny" } }',
        "permissions.leafcutter-worker.network.enabled=false",
        'approval_policy="never"',
        "features.multi_agent=false",
    ]


def local_environment():
    """Allow runtime essentials rather than trying to enumerate every secret name."""
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "LANG",
        "SHELL",
        "TERM",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
        "VIRTUAL_ENV",
        "PYTHONIOENCODING",
    }
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed or key.upper().startswith("LC_")
    } | {"AC_ENFORCE_STRICT": "1"}


def safe_output(value):
    text = str(value or "")
    for key, secret in os.environ.items():
        if len(secret) >= 6 and any(
            word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "CREDENTIAL")
        ):
            text = text.replace(secret, "[REDACTED]")
    return text[-16000:]


def check_evidence(argv, result):
    stdout, stderr = safe_output(result.stdout), safe_output(result.stderr)
    count = 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    explicit_envelope = any('"leafcutter_check"' in line for line in lines)
    if lines:
        try:
            final = json.loads(lines[-1])
        except ValueError:
            final = None
        envelope = final.get("leafcutter_check") if isinstance(final, dict) else None
        if (
            isinstance(envelope, dict)
            and envelope.get("passed") is True
            and type(envelope.get("inspected")) is int
            and envelope["inspected"] > 0
        ):
            count = envelope["inspected"]
    if not explicit_envelope and any(
        Path(arg).stem in {"pytest", "py.test"} or arg == "pytest" for arg in argv
    ):
        matches = re.findall(r"\b(\d+) passed\b", result.stdout)
        if matches:
            count = max(count, int(matches[-1]))
    if result.returncode != 0 or count <= 0 or "AC-ENFORCEMENT [MASKED FAILURE]" in result.stdout:
        error = ExecutorError(
            "Required check has no positive inspected-item evidence; emit a leafcutter_check JSON envelope or a pytest passing summary"
        )
        error.evidence = {
            "argv": argv,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        raise error
    return {"argv": argv, "passed": True, "inspected": count, "stdout": stdout, "stderr": stderr}


def run_process(argv, *, cwd, input_text="", timeout=300, env=None, heartbeat=None):
    """Run argument arrays without a shell; terminate the entire process tree on timeout."""
    if timeout <= 0:
        raise ExecutorError("Execution budget exhausted")
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            **options,
        )
    except OSError as exc:
        raise ExecutorError(f"Cannot start required executable: {argv[0]}") from exc
    deadline = time.monotonic() + timeout
    first = True
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
            try:
                stdout, stderr = process.communicate(
                    input=input_text if first else None, timeout=min(10, remaining)
                )
                break
            except subprocess.TimeoutExpired:
                first = False
                if heartbeat is not None and heartbeat() is False:
                    raise ExecutorError("Execution lease ownership lost")
                if time.monotonic() >= deadline:
                    raise
    except (subprocess.TimeoutExpired, ExecutorError) as exc:
        try:
            if os.name == "nt":
                killed = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                if killed.returncode != 0:
                    raise OSError("Windows process-tree termination did not succeed")
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            process.communicate(timeout=20)
        except (OSError, subprocess.SubprocessError) as cleanup_error:
            LOGGER.error("Could not prove executor termination: %s", cleanup_error)
            raise ExecutorError(
                "Uncertain process termination; retain the execution lease"
            ) from cleanup_error
        raise ExecutorError(
            "Execution timed out or lost its lease; process tree terminated"
        ) from exc
    if process.returncode:
        # Raw stderr may contain credentials or prompts. Keep it out of persistent status.
        error = ExecutorError(
            f"{Path(argv[0]).name} exited with code {process.returncode}; execution did not succeed"
        )
        error.evidence = {
            "returncode": process.returncode,
            "stdout": safe_output(stdout),
            "stderr": safe_output(stderr),
        }
        raise error
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
