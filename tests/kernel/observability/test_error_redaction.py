"""
MODULE: tests.kernel.observability.test_error_redaction
GOAL: Prove exception text reaches the Langfuse span status and the telemetry spool only after
    the Redactor has masked it (exact secret values and entropy-like tokens).
BUSINESS CONTEXT: The SDK `mask` hook covers input, output and metadata but NOT `status_message`,
    so an exception message that echoes a credential would leave the process unmasked (Rev 3
    section 13.3).
ARCHITECTURE: Real Langfuse 4.x SDK with an in-memory OpenTelemetry exporter (the harness of
    test_langfuse_tracer); secrets and the entropy token are built at runtime.
"""

from __future__ import annotations

import base64
import hashlib
import unittest

from tests.kernel.observability import test_langfuse_tracer as base

ENTROPY = base64.b64encode(hashlib.sha256(b"fixc-error-sample").digest()).decode()


class _LeakyError(RuntimeError):
    """An error whose message echoes whatever it was built with."""


class TestSpanErrorRedaction(base._Harness):
    """status_message and every other exported attribute are masked."""

    def _failing_span(self) -> dict:
        tracer = self.make()
        tracer.open_segment(base.RUN, base.TASK, "start")
        message = f"auth failed for {self.secret} and {ENTROPY}"
        with self.assertRaises(_LeakyError), tracer.span("kernel.leak", "chain", self.corr):
            raise _LeakyError(message)
        tracer.close_segment()
        span = self.spans()["kernel.leak"][0]
        return {"attrs": self.attrs(span), "description": span.status.description}

    def test_status_message_does_not_carry_secret_or_entropy_token(self) -> None:
        seen = self._failing_span()
        message = seen["attrs"]["langfuse.observation.status_message"]
        self.assertNotIn(self.secret, message)
        self.assertNotIn(ENTROPY, message)
        self.assertIn("auth failed", message)

    def test_nothing_in_the_exported_span_carries_the_secret(self) -> None:
        seen = self._failing_span()
        everything = repr(seen["attrs"]) + repr(seen["description"])
        self.assertNotIn(self.secret, everything)
        self.assertNotIn(ENTROPY, everything)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:00 [python-coder]: Checked against langfuse 4.16: `_mask_attribute` is applied
#   to input, output and metadata only, never to `status_message`. (#KernelBootstrapV0/FIXC)
# ====================================================================
