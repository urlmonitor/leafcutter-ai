"""Process isolation, credential hygiene and inspected-check evidence for worker executors."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

LOGGER = logging.getLogger(__name__)
PROTECTED_RUNTIME_PATHS = (
    ".leafcutter/scripts", ".leafcutter/config", ".leafcutter/skills/security-scanner/scripts",
    ".leafcutter/pre-commit-config.yaml", ".pre-commit-config.yaml",
)


class ExecutorError(RuntimeError):
    """An external execution did not produce trustworthy evidence."""


def permission_overrides(*, readonly=False, workspace=None):
    """Deny host reads as well as writes; unsupported native policies fail closed."""
    access = "read" if readonly else "write"
    # The coordinator virtualenv contains check tools, not repository/user data.
    runtime = ""
    if sys.prefix != sys.base_prefix:
        runtime = ", " + json.dumps(str(Path(sys.prefix).resolve())) + '="read"'
    protected = ""
    if workspace is not None:
        for relative in PROTECTED_RUNTIME_PATHS:
            path = Path(workspace) / relative
            if path.is_symlink():
                raise ExecutorError("Protected worker runtime cannot be a symlink")
            if path.exists():
                protected += ", " + json.dumps(relative) + '="read"'
    return [
        'default_permissions="leafcutter-worker"',
        'permissions.leafcutter-worker.filesystem={ glob_scan_max_depth=32, ":root"="deny", ":minimal"="read", ":workspace_roots"={ "."="'
        + access
        + '", ".git"="read", ".codex"="read", "**/*.env"="deny"' + protected + " }" + runtime + " }",
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
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed or key.upper().startswith("LC_")
    } | {"AC_ENFORCE_STRICT": "1"}
    if sys.prefix != sys.base_prefix:
        binaries = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
        environment["PATH"] = str(binaries) + os.pathsep + environment.get("PATH", "")
        environment["VIRTUAL_ENV"] = sys.prefix
    return environment


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
    from .owned_process import start_process

    try:
        process = start_process(
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
            elif sys.platform != "linux":
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            stdout, stderr = process.communicate(timeout=20)
        except (OSError, subprocess.SubprocessError, ExecutorError) as cleanup_error:
            LOGGER.error("Could not prove executor termination: %s", cleanup_error)
            raise ExecutorError(
                "Uncertain process termination; retain the execution lease"
            ) from cleanup_error
        error = ExecutorError(
            "Execution timed out or lost its lease; process tree terminated"
        )
        error.evidence = {"termination_confirmed": True,
                          "timed_out": isinstance(exc, subprocess.TimeoutExpired),
                          "returncode": process.returncode}
        if "--json" in argv and Path(argv[0]).stem == "codex":
            from .local_outcome import event_diagnostics, parse_events

            error.evidence.update(event_diagnostics(parse_events(stdout)))
        else:
            error.evidence.update(stdout=safe_output(stdout), stderr=safe_output(stderr))
        raise error from exc
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
