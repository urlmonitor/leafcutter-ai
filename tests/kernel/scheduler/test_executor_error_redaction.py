"""
MODULE: tests.kernel.scheduler.test_executor_error_redaction
GOAL: Prove an exception raised inside a capability executor is masked by the Redactor before
    its text enters the run outcome (and so the envelope, run.json and events).
BUSINESS CONTEXT: Executors call providers whose exceptions often echo credentials or request
    bodies; `ErrorInfo.message` is client-visible and persisted (Rev 3 section 13.3).
ARCHITECTURE: Drives the real compiled graph through the scheduler Rig with an executor that
    raises; the runtime redactor is injected the way bootstrap does. Secret values are built at
    runtime.
"""

from __future__ import annotations

import base64
import hashlib
import unittest
from dataclasses import replace

from kernel.contracts import RunStatus
from kernel.observability.redaction import Redactor
from tests.kernel.scheduler.support import Rig, descriptor

SECRET = "tk-" + hashlib.sha1(b"fixc-secret").hexdigest()[:14]
ENTROPY = base64.b64encode(hashlib.sha256(b"fixc-executor").digest()).decode()


class TestExecutorExceptionIsMasked(unittest.IsolatedAsyncioTestCase):
    """The failed result carries masked exception text."""

    async def _failed_message(self, redactor: Redactor | None) -> str:
        def explode(inv):
            raise RuntimeError(f"upstream rejected {SECRET} / {ENTROPY}")

        rig = Rig([descriptor("decide.root")])
        rig.bind("decide.root", factory=explode)
        if redactor is not None:
            plain = rig.runtime
            rig.runtime = lambda: replace(plain(), redactor=redactor)
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].status, RunStatus.FAILED)
        error = state["outcome"].errors[0]
        self.assertEqual(error.code, "executor_exception")
        return error.message

    async def test_exact_secret_value_is_masked_with_the_runtime_redactor(self) -> None:
        rig = Rig([])
        redactor = Redactor({"jev_api_key": SECRET}, rig.config.data_policy, [])
        message = await self._failed_message(redactor)
        self.assertNotIn(SECRET, message)
        self.assertIn("RuntimeError", message)
        self.assertIn("upstream rejected", message)

    async def test_entropy_token_is_masked_even_without_a_runtime_redactor(self) -> None:
        message = await self._failed_message(None)
        self.assertNotIn(ENTROPY, message)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:20 [python-coder]: The no-redactor case is covered because the scheduler tests
#   (and any caller that omits it) fall back to a pattern-only redactor. (#KernelBootstrapV0/FIXC)
# ====================================================================
