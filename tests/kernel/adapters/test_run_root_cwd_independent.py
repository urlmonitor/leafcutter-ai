"""
MODULE: tests.kernel.adapters.test_run_root_cwd_independent
GOAL: Prove the kernel run store resolves the same way from any current directory, and that an
    explicit LEAFCUTTER_KERNEL_RUN_ROOT env value wins over config and the default.
BUSINESS CONTEXT: A host must resume a run from wherever its shell is (live repro 2026-10-02:
    resume failed run_not_found from another git worktree).
ARCHITECTURE: Real build_environment / resolve_run_root, offline (empty secrets injected).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kernel.bootstrap import EnvironmentOverrides, build_environment, resolve_run_root
from kernel.config import load_kernel_config, repo_root
from kernel.secrets import SecretSettings

ENV_VAR = "LEAFCUTTER_KERNEL_RUN_ROOT"


class RunRootCwdIndependence(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.cwd0 = Path.cwd()
        self.addCleanup(os.chdir, self.cwd0)
        self.override = self.tmp / "o.json"
        self.override.write_text(json.dumps({"langfuse": {"enabled": False}}), encoding="utf-8")

    def _run_root(self, cwd: Path, env: dict[str, str] | None = None) -> Path:
        os.chdir(cwd)
        clean = {k: v for k, v in os.environ.items() if k != ENV_VAR}
        clean.update(env or {})
        with mock.patch.dict(os.environ, clean, clear=True):
            built = build_environment(
                config_path=self.override,
                overrides=EnvironmentOverrides(secrets=SecretSettings()))
        return built.run_root

    def test_ac1_default_run_root_same_from_unrelated_git_dir(self) -> None:
        """Default run root is identical from directory A and from an unrelated git repo B."""
        # covers: UNKNOWN
        # angle: criterion
        other = self.tmp / "other_repo"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        a = self._run_root(self.cwd0)
        b = self._run_root(other)
        self.assertEqual(a, b)
        self.assertTrue(str(a).startswith(str(repo_root())))

    def test_ac2_env_var_overrides_default_and_config(self) -> None:
        """LEAFCUTTER_KERNEL_RUN_ROOT wins over the config run_root and the default."""
        # covers: UNKNOWN
        # angle: discrimination
        explicit = self.tmp / "explicit_runs"
        self.override.write_text(json.dumps({"paths": {"run_root": str(self.tmp / "cfg")},
                                             "langfuse": {"enabled": False}}), encoding="utf-8")
        got = self._run_root(self.cwd0, {ENV_VAR: str(explicit)})
        self.assertEqual(got, explicit)

    def test_ac3_env_var_resolves_same_from_any_cwd(self) -> None:
        """With the env value set, two different cwds yield the same run root."""
        # covers: UNKNOWN
        # angle: boundary
        explicit = self.tmp / "shared_runs"
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        a = self._run_root(self.cwd0, {ENV_VAR: str(explicit)})
        b = self._run_root(elsewhere, {ENV_VAR: str(explicit)})
        self.assertEqual(a, b)
        self.assertEqual(a, explicit)

    def test_ac4_resolve_run_root_honours_env_var(self) -> None:
        """resolve_run_root consults the env override before the config value."""
        # covers: UNKNOWN
        # angle: criterion
        config = load_kernel_config(self.override)
        explicit = self.tmp / "viaenv"
        with mock.patch.dict(os.environ, {ENV_VAR: str(explicit)}):
            self.assertEqual(resolve_run_root(config, repo_root()), explicit)

    def test_ac5_cli_status_from_other_cwd_uses_env_run_root(self) -> None:
        """Reachability: `python -m kernel status` from an unrelated cwd reads the env run root."""
        # covers: UNKNOWN
        # angle: reachability
        explicit = self.tmp / "cli_runs"
        elsewhere = self.tmp / "cli_cwd"
        elsewhere.mkdir()
        env = {**os.environ, ENV_VAR: str(explicit),
               "PYTHONPATH": str(repo_root()), "LEAFCUTTER_KERNEL_CONFIG": str(self.override)}
        proc = subprocess.run([sys.executable, "-m", "kernel", "gaps"], cwd=elsewhere, env=env,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(explicit.exists(), "run store must be created at the env run root")


if __name__ == "__main__":
    unittest.main()
