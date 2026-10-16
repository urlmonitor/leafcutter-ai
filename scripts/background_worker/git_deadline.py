"""Bound every coordinator subprocess to the remaining AC commit budget."""
from contextlib import contextmanager
import time

from .executors import ExecutorError


@contextmanager
def commit_deadline(git, timeout):
    original = git.invoke
    deadline = time.monotonic() + min(float(timeout), 660)

    def invoke(argv, **options):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ExecutorError("AC time budget exhausted during commit preparation")
        options["timeout"] = min(options.get("timeout", 120), remaining)
        return original(argv, **options)

    git.invoke = invoke
    try:
        yield
    finally:
        git.invoke = original
