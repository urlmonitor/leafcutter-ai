"""
Unit tests for the live_surface_testing validation block in config_loader.py.

Covers:
  - test_valid_disabled_config: absent or enabled=false passes without errors
  - test_valid_enabled_config: enabled=true with valid startup_command passes
  - test_enabled_missing_startup_command: enabled=true but startup_command absent raises
  - test_port_range_inverted: port_range_start >= port_range_end raises

Framework: unittest (no DB required).
"""

from __future__ import annotations

import unittest

from scripts.config_loader import ConfigValidationError, _validate_live_surface_testing


class TestValidateLiveSurfaceTesting(unittest.TestCase):
    """Tests for _validate_live_surface_testing."""

    # ------------------------------------------------------------------
    # Happy-path tests
    # ------------------------------------------------------------------

    def test_valid_disabled_config(self) -> None:
        """Absent live_surface_testing block is valid (treated as enabled=false)."""
        config: dict = {}
        # Must not raise
        _validate_live_surface_testing(config)

    def test_valid_disabled_block_explicit(self) -> None:
        """Explicit enabled=false with no startup_command is valid."""
        config = {
            "live_surface_testing": {
                "enabled": False,
                "health_check_path": "/health",
                "startup_timeout_seconds": 30,
                "port_range_start": 8200,
                "port_range_end": 8299,
            }
        }
        _validate_live_surface_testing(config)

    def test_valid_enabled_config(self) -> None:
        """enabled=true with a non-empty startup_command is valid."""
        config = {
            "live_surface_testing": {
                "enabled": True,
                "startup_command": "python -m uvicorn app.main:app --host 0.0.0.0 --port {port}",
                "health_check_path": "/health",
                "startup_timeout_seconds": 30,
                "port_range_start": 8200,
                "port_range_end": 8299,
            }
        }
        _validate_live_surface_testing(config)

    def test_valid_port_range(self) -> None:
        """port_range_start < port_range_end is valid."""
        config = {
            "live_surface_testing": {
                "enabled": False,
                "port_range_start": 8000,
                "port_range_end": 8099,
            }
        }
        _validate_live_surface_testing(config)

    # ------------------------------------------------------------------
    # Failure tests
    # ------------------------------------------------------------------

    def test_enabled_missing_startup_command(self) -> None:
        """enabled=true with absent startup_command raises ConfigValidationError."""
        config = {
            "live_surface_testing": {
                "enabled": True,
                "health_check_path": "/health",
                "startup_timeout_seconds": 30,
                "port_range_start": 8200,
                "port_range_end": 8299,
            }
        }
        with self.assertRaises(ConfigValidationError) as ctx:
            _validate_live_surface_testing(config)
        self.assertIn("startup_command", str(ctx.exception))

    def test_enabled_empty_startup_command(self) -> None:
        """enabled=true with empty startup_command raises ConfigValidationError."""
        config = {
            "live_surface_testing": {
                "enabled": True,
                "startup_command": "   ",
            }
        }
        with self.assertRaises(ConfigValidationError) as ctx:
            _validate_live_surface_testing(config)
        self.assertIn("startup_command", str(ctx.exception))

    def test_port_range_inverted(self) -> None:
        """port_range_start >= port_range_end raises ConfigValidationError."""
        config = {
            "live_surface_testing": {
                "enabled": False,
                "port_range_start": 8300,
                "port_range_end": 8200,
            }
        }
        with self.assertRaises(ConfigValidationError) as ctx:
            _validate_live_surface_testing(config)
        self.assertIn("port_range", str(ctx.exception))

    def test_port_range_equal(self) -> None:
        """port_range_start == port_range_end raises ConfigValidationError."""
        config = {
            "live_surface_testing": {
                "enabled": False,
                "port_range_start": 8200,
                "port_range_end": 8200,
            }
        }
        with self.assertRaises(ConfigValidationError):
            _validate_live_surface_testing(config)

    def test_enabled_not_bool(self) -> None:
        """enabled value that is not a boolean raises ConfigValidationError."""
        config = {
            "live_surface_testing": {
                "enabled": "yes",
            }
        }
        with self.assertRaises(ConfigValidationError) as ctx:
            _validate_live_surface_testing(config)
        self.assertIn("boolean", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
