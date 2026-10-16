"""Reject executable content filters before trusted coordinator staging."""

from .execution_boundary import ExecutorError, run_process


def assert_no_executable_filters(workspace, *, invoke=run_process):
    prefix = ["git", "-c", "core.fsmonitor=false", "--no-optional-locks"]
    files = invoke(
        [*prefix, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=workspace,
        timeout=30,
    ).stdout
    if not files:
        return
    result = invoke(
        [*prefix, "check-attr", "--stdin", "-z", "filter"],
        cwd=workspace,
        input_text=files,
        timeout=30,
    ).stdout.split("\0")
    drivers = {result[index + 2] for index in range(0, len(result) - 2, 3)} - {
        "unspecified",
        "unset",
        "set",
    }
    for driver in sorted(drivers):
        for operation in ("clean", "process"):
            command = invoke(
                [*prefix, "config", "--get", "--default", "", f"filter.{driver}.{operation}"],
                cwd=workspace,
                timeout=20,
            ).stdout.strip()
            if command:
                raise ExecutorError(
                    f"Active Git filter {driver}.{operation} requires an executable-filter sandbox "
                    "before coordinator staging; the required filter will not be bypassed"
                )
