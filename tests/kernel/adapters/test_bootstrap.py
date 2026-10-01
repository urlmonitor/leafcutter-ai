"""
MODULE: tests.kernel.adapters.test_bootstrap
GOAL: Test the composition root: the verified registry snapshot, the trusted binding table with
    native executors and host placeholders, the run root from config, the redactor over loaded
    secrets, and the live-Jev wiring (one shared tracer, created and closed inside the loop).
BUSINESS CONTEXT: Exactly one place maps binding keys to classes and decides where runs live; a
    wrong binding or a second tracer instance would silently break routing or split a trace.
ARCHITECTURE: Builds the real environment offline: no credentials are loaded (an empty
    SecretSettings is injected), so nothing touches the network. The Jev adapter is constructed
    with a dummy key and closed without any call.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from pydantic import SecretStr

from kernel.bootstrap import (
    NATIVE_VERSION,
    EnvironmentOverrides,
    HostBindingExecuted,
    HostMarkerExecutor,
    build_bindings,
    build_environment,
    load_snapshot,
    resolve_run_root,
)
from kernel.config import load_kernel_config, repo_root
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability.langfuse_tracer import LangfuseTracer
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.secrets import SecretSettings

HOST_KEYS = ("host.formulate_question", "host.generate_options", "host.research",
             "host.synthesize")
DUMMY_KEY = "dummy-jev-credential-for-tests"


class BootstrapCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.override = self.tmp / "override.json"
        self.override.write_text(json.dumps({"paths": {"run_root": str(self.tmp / "runs_here")},
                                             "langfuse": {"enabled": False}}), encoding="utf-8")

    def build(self, secrets: SecretSettings | None = None, *, langfuse: bool = False):
        """Build the real environment with injected secrets (no .env lookup, no network)."""
        if langfuse:
            self.override.write_text(json.dumps({"paths": {"run_root": str(self.tmp / "r")}}),
                                     encoding="utf-8")
        return build_environment(config_path=self.override,
                                 overrides=EnvironmentOverrides(secrets=secrets or SecretSettings()))


class TestBindings(BootstrapCase):
    def test_every_enabled_registry_capability_has_a_binding_at_its_version(self) -> None:
        env = self.build()
        for descriptor in env.snapshot.descriptors:
            self.assertTrue(env.bindings.has(descriptor.binding, descriptor.version),
                            descriptor.id)

    def test_native_executors_and_host_placeholders_are_bound_at_1_0_0(self) -> None:
        env = self.build()
        for key in ("decision", "research", "retrieve.repository", *HOST_KEYS):
            self.assertTrue(env.bindings.has(key, NATIVE_VERSION), key)

    def test_host_bindings_are_placeholders_that_refuse_to_execute(self) -> None:
        table = build_bindings(self.build().snapshot)
        executor = table.resolve("host.research", NATIVE_VERSION)
        self.assertIsInstance(executor, HostMarkerExecutor)
        with self.assertRaises(HostBindingExecuted):
            asyncio.run(executor.ainvoke(cast(Any, None), cast(Any, None)))


class TestEnvironment(BootstrapCase):
    def test_run_root_comes_from_config_and_relative_paths_resolve_to_the_repo(self) -> None:
        self.assertEqual(self.build().run_root, self.tmp / "runs_here")
        default = load_kernel_config()
        self.assertEqual(resolve_run_root(default, Path("/repo")).name, "kernel")
        self.assertTrue(resolve_run_root(default, repo_root()).is_absolute())

    def test_the_snapshot_is_the_verified_registry(self) -> None:
        env = self.build()
        again = load_snapshot(env.config, env.repo_root)
        self.assertEqual(env.snapshot.content_hash, again.content_hash)
        self.assertTrue(env.snapshot.descriptors)

    def test_without_a_jev_key_there_is_no_factory_and_the_tracer_is_langfuse(self) -> None:
        env = self.build()
        self.assertIsNone(env.jev_factory)
        self.assertIsInstance(env.tracer, LangfuseTracer)

    def test_a_disabled_tracer_opens_and_closes_without_raising(self) -> None:
        env = self.build()
        env.tracer.open_segment("run-1", "task-1", "start")
        self.assertEqual(env.tracer.close_segment(), ObservabilityStatus.OK)
        env.shutdown()

    def test_enabled_tracing_without_credentials_degrades_instead_of_failing(self) -> None:
        env = self.build(langfuse=True)
        state = env.tracer.open_segment("run-1", "task-1", "start")
        self.assertEqual(len(state.trace_id), 32)
        self.assertEqual(env.tracer.close_segment(), ObservabilityStatus.DEGRADED)
        self.assertEqual(env.tracer.degraded_reason, "missing_credentials")
        env.shutdown()

    def test_the_redactor_masks_loaded_secret_values(self) -> None:
        env = self.build(SecretSettings(jev_api_key=SecretStr(DUMMY_KEY)))
        masked = env.redactor.mask({"text": f"key is {DUMMY_KEY} here"})
        self.assertNotIn(DUMMY_KEY, json.dumps(masked))
        self.assertIn("REDACTED", json.dumps(masked))

    async def test_the_jev_adapter_shares_the_runtime_tracer_and_closes_cleanly(self) -> None:
        env = self.build(SecretSettings(jev_api_key=SecretStr(DUMMY_KEY)))
        self.assertIsNotNone(env.jev_factory)
        adapter = env.jev_factory()
        try:
            self.assertIsInstance(adapter, TypeSafeJevAdapter)
            self.assertIs(adapter._tracer, env.tracer)  # one tracer: generations nest in one trace
        finally:
            await adapter.aclose()


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:40 [python-coder]: The dummy credential is a readable placeholder string, not a
#   key-shaped literal, so the secret scanner has nothing to flag. (#KernelBootstrapV0/P7)
# ====================================================================
