"""Shared helpers for the TQ-600a-13-xiv tests (the no-fresh-verdict states of the hold). Not a test: underscore-named."""

from __future__ import annotations

import os
import re
from unittest import mock

from ._hold_harness import HoldTestCase

NOT_THE_PR = re.compile(r"not caused by (this|the) pull request", re.IGNORECASE)
RESTORE = re.compile(r"to restore a verdict", re.IGNORECASE)
RESTORE_HOW = {
    "red": r"fix main|declare the fix|Fixes #",
    "did_not_complete": r"re-?run",
    "stale": r"dispatch",
    "disabled": r"re-?enable",
    "never_run": r"first run|dispatch",
    "could_not_read": r"re-?run",
}
URL = re.compile(r"https?://\S+")


def headline(reason):
    """The headline of a check output: its text before the first ``:``, ``(``, ``.`` or ``;`` (cause and detail follow)."""
    return re.split(r"\s*[:(.;]", URL.sub("", reason), maxsplit=1)[0].strip().lower()


class XivTestCase(HoldTestCase):
    """``HoldTestCase`` plus one-call serving of a workflow state and a run history, with no retry delay."""

    def verdict(self, runs=(), *, workflow_state="active", jobs=None, failing=()):
        """Reset the fake, serve the given state and runs, evaluate once through the real REST client, injected clock."""
        self.svc.reset()
        self.svc.workflow_state = workflow_state
        self.svc.failing = list(failing)
        self.serve(runs, jobs)
        self.svc.requests.clear()
        with mock.patch.dict(os.environ, {"POST_MERGE_HOLD_RETRY_DELAY_SECONDS": "0"}):
            return self.evaluate()
