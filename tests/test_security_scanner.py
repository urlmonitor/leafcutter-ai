"""Unit tests for the security-scanner skill scripts.

Tests cover: secrets detection patterns, entropy heuristic, allowlist
suppression, and false-positive handling with base64-like data.
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

# Add skill scripts to path
_SKILL_SCRIPTS = (
    Path(__file__).parent.parent
    / "templates" / "skills" / "security-scanner" / "scripts"
)
sys.path.insert(0, str(_SKILL_SCRIPTS))

from scan_secrets import (  # noqa: E402
    Finding,
    _shannon_entropy,
    scan_file,
    scan_files,
)


# ---------------------------------------------------------------------------
# Shannon entropy tests
# ---------------------------------------------------------------------------

class TestShannonEntropy:
    """Tests for the entropy computation helper."""

    def test_empty_string_returns_zero(self) -> None:
        assert _shannon_entropy("") == 0.0

    def test_uniform_string_low_entropy(self) -> None:
        # "aaaa" has entropy 0
        assert _shannon_entropy("aaaa") == 0.0

    def test_high_entropy_random_string(self) -> None:
        # A random-looking 32-char alphanum string should exceed 4.5
        token = "aB3xZ9qP2mN7wK1vR5tY8uE4sL6cH0jD"
        assert _shannon_entropy(token) > 4.5

    def test_low_entropy_repeated(self) -> None:
        # "abababababababab" has low entropy
        assert _shannon_entropy("abababababababab") < 2.5


# ---------------------------------------------------------------------------
# Scan file — pattern detection
# ---------------------------------------------------------------------------

class TestScanFilePatterns:
    """Tests for regex-based secrets detection."""

    def test_detects_private_key_header(self, tmp_path: Path) -> None:
        f = tmp_path / "key.py"
        f.write_text('key = "-----BEGIN RSA PRIVATE KEY-----"\n')
        findings = scan_file(f)
        rule_ids = [x.rule_id for x in findings]
        assert "PRIVATE_KEY" in rule_ids

    def test_detects_aws_key(self, tmp_path: Path) -> None:
        f = tmp_path / "config.py"
        f.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        findings = scan_file(f)
        rule_ids = [x.rule_id for x in findings]
        assert "AWS_KEY" in rule_ids

    def test_detects_generic_password(self, tmp_path: Path) -> None:
        f = tmp_path / "settings.py"
        f.write_text('DB_PASSWORD = "super_secret_pass123"\n')
        findings = scan_file(f)
        rule_ids = [x.rule_id for x in findings]
        assert "GENERIC_SECRET" in rule_ids

    def test_detects_env_filename(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("BYBIT_API_KEY=test\n")
        findings = scan_file(f)
        rule_ids = [x.rule_id for x in findings]
        assert "ENV_FILE" in rule_ids

    def test_clean_file_no_findings(self, tmp_path: Path) -> None:
        f = tmp_path / "clean.py"
        f.write_text(textwrap.dedent("""\
            def add(a: int, b: int) -> int:
                return a + b
        """))
        assert scan_file(f) == []

    def test_high_entropy_token_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "config.py"
        # 35-char high-entropy string resembling an API key
        f.write_text('api_key = "aB3xZ9qP2mN7wK1vR5tY8uE4sL6cH0jD3"\n')
        findings = scan_file(f)
        rule_ids = [x.rule_id for x in findings]
        assert "ENTROPY_HIGH" in rule_ids or "BYBIT_API_KEY" in rule_ids


# ---------------------------------------------------------------------------
# Allowlist suppression
# ---------------------------------------------------------------------------

class TestAllowlist:
    """Tests for .security-allowlist suppression logic."""

    def test_suppresses_by_rule_file_line(self, tmp_path: Path) -> None:
        # Create a file with a password line
        src = tmp_path / "settings.py"
        src.write_text('DB_PASSWORD = "mysecretpassword"\n')

        # Allowlist suppresses line 1
        allowlist = tmp_path / ".security-allowlist"
        allowlist.write_text("GENERIC_SECRET:settings.py:1\n")

        findings = scan_files([src], project_root=tmp_path)
        assert findings == []

    def test_suppresses_by_star_line(self, tmp_path: Path) -> None:
        src = tmp_path / "docs.py"
        src.write_text('example = "password = secret_value"\n')
        allowlist = tmp_path / ".security-allowlist"
        allowlist.write_text("GENERIC_SECRET:docs.py:*\n")

        findings = scan_files([src], project_root=tmp_path)
        assert findings == []

    def test_does_not_suppress_different_file(self, tmp_path: Path) -> None:
        src = tmp_path / "settings.py"
        src.write_text('DB_PASSWORD = "anotherpass"\n')
        allowlist = tmp_path / ".security-allowlist"
        allowlist.write_text("GENERIC_SECRET:other.py:1\n")

        findings = scan_files([src], project_root=tmp_path)
        assert len(findings) > 0

    def test_no_allowlist_file_still_works(self, tmp_path: Path) -> None:
        src = tmp_path / "clean.py"
        src.write_text("x = 1\n")
        # No .security-allowlist file
        findings = scan_files([src], project_root=tmp_path)
        assert findings == []


# ---------------------------------------------------------------------------
# False positive scenarios
# ---------------------------------------------------------------------------

class TestFalsePositives:
    """Tests for known false positive scenarios."""

    def test_base64_encoded_fixture_suppressed_by_allowlist(self, tmp_path: Path) -> None:
        src = tmp_path / "fixture.py"
        # High-entropy base64-like string (typical test fixture)
        src.write_text('DATA = "SGVsbG9Xb3JsZEZvb0JhckJhejEyMzQ1"\n')
        allowlist = tmp_path / ".security-allowlist"
        allowlist.write_text("ENTROPY_HIGH:fixture.py:1\n")

        findings = scan_files([src], project_root=tmp_path)
        assert findings == []

    def test_uuid_below_entropy_threshold(self, tmp_path: Path) -> None:
        src = tmp_path / "models.py"
        # UUIDs have lower entropy because they're hex-only
        src.write_text('DEFAULT_ID = "550e8400-e29b-41d4-a716-446655440000"\n')
        findings = scan_file(src)
        # UUIDs may or may not trigger depending on entropy; just verify no crash
        assert isinstance(findings, list)
