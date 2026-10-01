"""
MODULE: tests.kernel.config.test_input_files
GOAL: Prove a non-UTF-8 config or registry file, and a missing explicit env file, are reported
    as `config_invalid` / `registry_invalid` (exit 5 with one JSON document), never a traceback.
BUSINESS CONTEXT: The client parses stdout blindly and branches on the exit code; an uncaught
    UnicodeDecodeError gives exit 1 and empty stdout, and a silently ignored env file sends a
    run out with the wrong credentials (Rev 3 section 11.2).
ARCHITECTURE: Real files in a temp directory written as bytes a broken editor would produce;
    the CLI cases run the shipped `python -m kernel` in a child process.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kernel.config import ConfigError, load_kernel_config
from kernel.registry import RegistryError, load_component_ids
from kernel.secrets import ENV_FILE_VAR, load_secrets
from tests.kernel.adapters.cli_support import child_env, real_cli, spawn

BAD_BYTES = b'{"limits": {"max_depth": 2}} \xff\xfe\x80'
STATUS = ["status", "--run-id", "run-0123456789abcdef", "--json"]


class TestUndecodableFiles(unittest.TestCase):
    """Decode errors map to the typed errors the CLI already handles."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.bad = self.dir / "bad.json"
        self.bad.write_bytes(BAD_BYTES)

    def test_config_with_invalid_utf8_raises_config_error(self) -> None:
        with self.assertRaises(ConfigError):
            load_kernel_config(self.bad)

    def test_registry_file_with_invalid_utf8_raises_registry_error(self) -> None:
        with self.assertRaises(RegistryError):
            load_component_ids(self.bad)

    def test_cli_reports_a_bad_config_as_exit_5_config_invalid(self) -> None:
        result = real_cli(STATUS, config=self.bad)
        self.assertEqual(result.code, 5, result.stderr)
        self.assertEqual(result.document()["error"]["code"], "config_invalid")


class TestExplicitEnvFile(unittest.TestCase):
    """A named env file that cannot be read is an error; the implicit walk-up is unchanged."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        (self.dir / ".env").write_text("JEV_API_KEY=" + "walkup" + "-value-1\n", encoding="utf-8")
        self.missing = self.dir / "gone.env"

    def test_missing_explicit_file_raises_instead_of_falling_back(self) -> None:
        with self.assertRaises(ConfigError) as caught:
            load_secrets(self.missing, env={}, start_dir=self.dir)
        self.assertIn("gone.env", str(caught.exception))

    def test_missing_file_named_by_the_environment_variable_raises(self) -> None:
        with self.assertRaises(ConfigError):
            load_secrets(env={ENV_FILE_VAR: str(self.missing)}, start_dir=self.dir)

    def test_implicit_walk_up_without_an_explicit_file_still_works(self) -> None:
        self.assertTrue(load_secrets(env={}, start_dir=self.dir).has_jev())

    def test_cli_reports_a_missing_env_file_as_exit_5_config_invalid(self) -> None:
        result = real_cli([*STATUS, "--env-file", str(self.missing)])
        self.assertEqual(result.code, 5, result.stderr)
        self.assertEqual(result.document()["error"]["code"], "config_invalid")

    def test_cli_reports_a_missing_env_var_file_as_exit_5(self) -> None:
        env = child_env({ENV_FILE_VAR: str(self.missing)})
        result = spawn("kernel", STATUS, env=env)
        self.assertEqual((result.code, result.document()["error"]["code"]), (5, "config_invalid"))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:40 [python-coder]: The bytes are written raw, as a mis-encoded editor would
#   save them, instead of being produced by json.dumps. (#KernelBootstrapV0/FIXC)
# ====================================================================
