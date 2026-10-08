"""
MODULE: tests.kernel.adapters.test_cli_error_redaction
GOAL: Prove the exit-5 `internal` error of the CLI is masked by the environment's Redactor.
BUSINESS CONTEXT: The catch-all prints `{type}: {message}` of an unexpected exception on stdout
    for the client; a provider or library error may echo a credential (Rev 3 section 13.3).
ARCHITECTURE: Runs the real `main` in-process over a rig environment whose run store raises an
    unexpected error carrying a runtime-built secret and an entropy-like token.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from kernel.adapters.cli import main
from kernel.observability.redaction import Redactor
from tests.kernel.adapters.support import rig_environment
from tests.kernel.interaction.support import host_rig
from tests.kernel.scheduler.support import Rig

SECRET = "tk-" + hashlib.sha1(b"fixc-cli-secret").hexdigest()[:14]
ENTROPY = base64.b64encode(hashlib.sha256(b"fixc-cli").digest()).decode()
RUN_ID = "run-0123456789abcdef"


class _Leaky(RuntimeError):
    """Carries a secret and an entropy token in its message."""


def _environment(root: Path, rig: Rig):
    env = rig_environment(root, rig)

    def explode(run_id: str):
        raise _Leaky(f"store failed with {SECRET} and {ENTROPY}")

    cast(Any, env.run_store).get_run = explode
    env.redactor = Redactor({"jev_api_key": SECRET}, rig.config.data_policy, [])
    return env


class TestInternalErrorIsMasked(unittest.TestCase):
    """The exit-5 document never carries the secret."""

    def test_internal_error_message_is_redacted(self) -> None:
        rig = host_rig()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = main(["status", "--run-id", RUN_ID, "--json"],
                            environment=lambda **_: _environment(Path(tmp), rig))
        self.assertEqual(code, 5)
        document = json.loads(out.getvalue())
        message = document["error"]["message"]
        self.assertEqual(document["error"]["code"], "internal")
        self.assertIn("_Leaky", message)
        self.assertNotIn(SECRET, out.getvalue())
        self.assertNotIn(ENTROPY, out.getvalue())


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:20 [python-coder]: In-process (not a child process) so the injected store
#   failure and redactor are the ones under test. (#KernelBootstrapV0/FIXC)
# ====================================================================
