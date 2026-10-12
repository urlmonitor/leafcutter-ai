"""Async coverage must be discovered and proved by actually executing its tests.

Type: integration. Angles: regression, real_artifact, negative_control.
Uses real IsolatedAsyncioTestCase fixtures and the public done-proof oracle.
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "ac_store"))

from done_proof import collect_test_tag_records, verify_done_eligible  # noqa: E402


def fixture(root: Path, passing: bool) -> tuple[Path, Path, str]:
    """Write an AC and an async test with a genuine pass or failure outcome."""
    ac_root, test_root = root / "acs", root / "tests"
    ac_root.mkdir()
    test_root.mkdir()
    ac_id = "ZZ-ASYNC-PROOF"
    (ac_root / "proof.yaml").write_text(yaml.safe_dump({
        "id": ac_id, "status": "active", "work_status": "done", "covered_by": []}),
        encoding="utf-8")
    (test_root / "test_async_proof.py").write_text(textwrap.dedent(f'''\
        import asyncio
        import unittest

        class AsyncProof(unittest.IsolatedAsyncioTestCase):
            # covers: {ac_id}
            # angle: criterion
            async def test_async_proof(self):
                await asyncio.sleep(0)
                self.assertTrue({passing!r})
        '''), encoding="utf-8")
    return ac_root, test_root, ac_id


class TestAsyncDoneProof(unittest.TestCase):
    """A coroutine's covers tag has the same meaning as a synchronous test's tag."""

    # covers: BP-1100g-3
    def test_async_tag_records_preserve_function_and_both_axes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, tests, ac_id = fixture(Path(temporary), True)
            records = collect_test_tag_records(tests)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["function"], "test_async_proof")
        self.assertEqual(records[0]["covers"], [ac_id])
        self.assertEqual(records[0]["angles"], ["criterion"])

    # covers: BO-2500a-3
    def test_passing_async_test_proves_done(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            acs, tests, ac_id = fixture(Path(temporary), True)
            verdict = verify_done_eligible(ac_id, ac_root=acs, test_root=tests)
        self.assertTrue(verdict["eligible"], verdict)
        self.assertTrue(any("test_async_proof" in node for node in verdict["passing_tests"]))

    # covers: BO-2500a-2
    def test_failing_async_test_is_executed_and_refuses_done(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            acs, tests, ac_id = fixture(Path(temporary), False)
            verdict = verify_done_eligible(ac_id, ac_root=acs, test_root=tests)
        self.assertFalse(verdict["eligible"], verdict)
        self.assertTrue(any("test_async_proof" in node for node in verdict["failing_tests"]))
        self.assertNotIn("no linked test", verdict["reason"])
