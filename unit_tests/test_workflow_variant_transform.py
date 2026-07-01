"""Unit tests for the build-time _emit_workflow_variant transform.

MODULE GOAL: Verify that _emit_workflow_variant produces the correct output
    for each supported engine target (e2, auto, e1) and that the build pipeline
    correctly reads the engine from config and preserves the SHA-256 idempotency
    guard.

BUSINESS CONTEXT: The build pipeline must emit engine-specific variants of
    canonical E2 workflow scripts at deploy time. E2 and auto targets receive a
    byte-identical copy of the source; E1 targets receive the source prepended
    with a shim that adds an engine-detection predicate, a callAgent adapter,
    and an exported run() entry point. This allows a single canonical source
    to be deployed to both engine versions without hand-maintaining two files.

ARCHITECTURE: _emit_workflow_variant is a pure function in scripts/build_phases.py.
    It is called by build_workflow_scripts inside the copy loop. The SHA-256
    idempotency guard compares emitted bytes (post-transform) against the
    existing deployed file, not the raw source bytes.

Ticket: 04_build_time_variant_transform
Covers:
  - AC-1: E2 target is byte-identity (also tests "auto")
  - AC-2: E1 target is a valid wrap (node --check + dispatch-equivalence)
  - AC-3: engine selected from config + SHA-256 idempotency short-circuits
  - AC-4: reachability (deployed workflow loads without error)
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — scripts/ must be importable.
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Also ensure unit_tests/ is importable (for the harness).
_UNIT_TESTS_DIR = pathlib.Path(__file__).parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from build_phases import _emit_workflow_variant, build_workflow_scripts  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

# ---------------------------------------------------------------------------
# Canonical workflow source fixture
# ---------------------------------------------------------------------------
_QUICK_FIX_JS = _REPO_ROOT / "templates" / "workflows-js" / "quick-fix.js"

# Minimal synthetic E2 source used for tests that don't need the real file.
_MINIMAL_E2_SRC = b"""\
// Minimal synthetic E2 workflow for testing
const result = await agent('stub prompt', { agentType: 'general-purpose' })
return result
"""


# ---------------------------------------------------------------------------
# AC-1: E2 target is byte-identity
# ---------------------------------------------------------------------------


class TestE2Identity:
    """AC-1 — E2 and auto targets produce byte-identical output."""

    def test_e2_is_identity_with_synthetic_source(self):
        """_emit_workflow_variant(src, 'e2') must return the exact same bytes."""
        src = _MINIMAL_E2_SRC
        result = _emit_workflow_variant(src, "e2")
        assert result == src, "e2 variant must be byte-identical to source"

    def test_auto_is_identity_with_synthetic_source(self):
        """_emit_workflow_variant(src, 'auto') must return the exact same bytes."""
        src = _MINIMAL_E2_SRC
        result = _emit_workflow_variant(src, "auto")
        assert result == src, "auto variant must be byte-identical to source"

    def test_e2_identity_is_same_object_or_bytes(self):
        """The identity transform may return the same object or equal bytes."""
        src = b"const x = 1\n"
        result = _emit_workflow_variant(src, "e2")
        assert result == src

    @pytest.mark.skipif(
        not _QUICK_FIX_JS.exists(),
        reason="quick-fix.js not found in templates/workflows-js/",
    )
    def test_e2_identity_with_real_quick_fix(self):
        """Identity transform on the real quick-fix.js must preserve all bytes."""
        src = _QUICK_FIX_JS.read_bytes()
        result = _emit_workflow_variant(src, "e2")
        assert result == src, "e2 variant of quick-fix.js must be byte-identical"

    @pytest.mark.skipif(
        not _QUICK_FIX_JS.exists(),
        reason="quick-fix.js not found in templates/workflows-js/",
    )
    def test_auto_identity_with_real_quick_fix(self):
        """auto variant of the real quick-fix.js must be byte-identical."""
        src = _QUICK_FIX_JS.read_bytes()
        result = _emit_workflow_variant(src, "auto")
        assert result == src, "auto variant of quick-fix.js must be byte-identical"


# ---------------------------------------------------------------------------
# AC-2: E1 target is a valid wrap
# ---------------------------------------------------------------------------


class TestE1Wrap:
    """AC-2 — E1 target prepends a valid shim (node --check + dispatch-equivalence)."""

    def test_e1_wrap_contains_shim_markers(self):
        """Emitted E1 variant must include the three shim sections."""
        src = _MINIMAL_E2_SRC
        result = _emit_workflow_variant(src, "e1")
        text = result.decode("utf-8")
        assert "IS_E2" in text, "E1 shim must define IS_E2"
        assert "callAgent" in text, "E1 shim must define callAgent adapter"
        assert "export async function run" in text, "E1 shim must export run()"

    def test_e1_wrap_includes_original_source(self):
        """Emitted E1 variant must contain the original source bytes."""
        src = _MINIMAL_E2_SRC
        result = _emit_workflow_variant(src, "e1")
        assert src in result, "Original E2 source must be preserved in E1 variant"

    def test_e1_wrap_is_longer_than_source(self):
        """E1 variant must be longer than the source (shim was prepended)."""
        src = _MINIMAL_E2_SRC
        result = _emit_workflow_variant(src, "e1")
        assert len(result) > len(src), "E1 variant must be longer than source"

    def test_e1_wrap_starts_with_shim(self):
        """E1 variant must start with the shim, not the original source."""
        src = b"// original source\n"
        result = _emit_workflow_variant(src, "e1")
        text = result.decode("utf-8")
        assert text.startswith("// ---"), (
            "E1 variant must start with the shim comment block"
        )

    @pytest.mark.skipif(
        not shutil.which("node"),
        reason="node binary not available",
    )
    @pytest.mark.skipif(
        not _QUICK_FIX_JS.exists(),
        reason="quick-fix.js not found in templates/workflows-js/",
    )
    def test_e1_wrap_parses_with_node_check(self):
        """Emitted E1 variant must pass `node --check` (syntax validation)."""
        src = _QUICK_FIX_JS.read_bytes()
        emitted = _emit_workflow_variant(src, "e1")

        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".js", prefix="e1_variant_", delete=False
        ) as tmp:
            tmp_path = pathlib.Path(tmp.name)
            try:
                tmp.write(emitted)
            except OSError as exc:
                pytest.fail(f"Could not write temp file: {exc}")

        try:
            proc = subprocess.run(
                ["node", "--check", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert proc.returncode == 0, (
                f"node --check failed for E1 variant:\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
        except subprocess.TimeoutExpired:
            pytest.fail("node --check timed out")
        except FileNotFoundError:
            pytest.skip("node binary not found")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    @pytest.mark.skipif(
        not shutil.which("node"),
        reason="node binary not available",
    )
    @pytest.mark.skipif(
        not _QUICK_FIX_JS.exists(),
        reason="quick-fix.js not found in templates/workflows-js/",
    )
    def test_e1_wrap_dispatch_equivalence_via_harness(self):
        """E1 variant executed under E2 harness must capture >= 1 agent() call."""
        src = _QUICK_FIX_JS.read_bytes()
        emitted = _emit_workflow_variant(src, "e1")

        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".js", prefix="e1_harness_", delete=False
        ) as tmp:
            tmp_path = pathlib.Path(tmp.name)
            try:
                tmp.write(emitted)
            except OSError as exc:
                pytest.fail(f"Could not write temp file: {exc}")

        try:
            result = run_workflow_under_e2(tmp_path, timeout=20)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

        assert result.dispatch_count >= 1, (
            f"E1 variant must dispatch at least one agent() call under the E2 harness."
            f"\nstdout: {result.stdout[:300]}"
            f"\nstderr: {result.stderr[:300]}"
        )


# ---------------------------------------------------------------------------
# AC-3: engine selected from config + SHA-256 idempotency short-circuits
# ---------------------------------------------------------------------------


class TestBuildWorkflowScriptsEngineFromConfig:
    """AC-3 — build_workflow_scripts reads engine from config and preserves idempotency."""

    @pytest.fixture()
    def tmp_dirs(self, tmp_path):
        """Set up a minimal build environment with a synthetic JS source."""
        # Source tree: templates/workflows-js/<minimal>.js
        src_dir = tmp_path / "templates" / "workflows-js"
        src_dir.mkdir(parents=True)
        js_file = src_dir / "stub.js"
        js_file.write_bytes(_MINIMAL_E2_SRC)

        # Output dir that build_workflow_scripts will write into.
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        return tmp_path, src_dir, js_file, output_dir

    def _call_build(self, monkeypatch, tmp_path, output_dir, engine: str, force: bool = True):
        """Invoke build_workflow_scripts with a patched TEMPLATES_DIR."""
        import build_phases
        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp_path / "templates")
        config = {"workflows": {"enabled": True, "engine": engine}}
        # Suppress version-check subprocess: inject env var.
        monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.999")
        return build_workflow_scripts(output_dir, config, dry_run=False, force=force)

    def test_e2_engine_emits_byte_identical_file(self, monkeypatch, tmp_dirs):
        """build_workflow_scripts with engine=e2 must write a byte-identical file."""
        tmp_path, src_dir, js_file, output_dir = tmp_dirs
        written = self._call_build(monkeypatch, tmp_path, output_dir, "e2")
        assert written >= 1, "At least one file must be written"

        deployed = output_dir / "workflows" / "stub.js"
        assert deployed.exists(), "Deployed file must exist"
        assert deployed.read_bytes() == _MINIMAL_E2_SRC, (
            "e2 variant must be byte-identical to source"
        )

    def test_sha256_idempotency_skips_unchanged_file(self, monkeypatch, tmp_dirs):
        """Second build_workflow_scripts call must short-circuit via SHA-256 guard."""
        import build_phases
        tmp_path, src_dir, js_file, output_dir = tmp_dirs
        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp_path / "templates")
        monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.999")
        config = {"workflows": {"enabled": True, "engine": "e2"}}

        # First run: write file.
        written_first = build_workflow_scripts(output_dir, config, dry_run=False, force=True)
        assert written_first >= 1, "First run must write at least one file"

        # Snapshot mtime before second run.
        deployed = output_dir / "workflows" / "stub.js"
        mtime_before = deployed.stat().st_mtime_ns

        # Reset uptodate counter so we can detect the skip.
        build_phases.reset_uptodate_count()

        # Second run: same bytes, must short-circuit.
        written_second = build_workflow_scripts(output_dir, config, dry_run=False, force=True)
        assert written_second == 0, (
            f"Second run with identical bytes must write 0 files (got {written_second})"
        )

        # File must not have been rewritten.
        mtime_after = deployed.stat().st_mtime_ns
        assert mtime_before == mtime_after, (
            "SHA-256 guard must prevent rewrite of byte-identical file"
        )

    def test_e1_engine_emits_wrapped_file(self, monkeypatch, tmp_dirs):
        """build_workflow_scripts with engine=e1 must prepend the E1 shim."""
        import build_phases
        tmp_path, src_dir, js_file, output_dir = tmp_dirs
        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp_path / "templates")
        monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.999")
        config = {"workflows": {"enabled": True, "engine": "e1"}}

        written = build_workflow_scripts(output_dir, config, dry_run=False, force=True)
        assert written >= 1, "At least one file must be written for e1"

        deployed = output_dir / "workflows" / "stub.js"
        assert deployed.exists(), "Deployed file must exist"
        text = deployed.read_bytes().decode("utf-8")
        assert "IS_E2" in text, "E1 variant must contain engine-detection predicate"
        assert "export async function run" in text, "E1 variant must export run()"

    def test_auto_engine_defaults_to_identity(self, monkeypatch, tmp_dirs):
        """build_workflow_scripts with engine=auto must write byte-identical file."""
        import build_phases
        tmp_path, src_dir, js_file, output_dir = tmp_dirs
        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp_path / "templates")
        monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.999")
        config = {"workflows": {"enabled": True, "engine": "auto"}}

        written = build_workflow_scripts(output_dir, config, dry_run=False, force=True)
        assert written >= 1

        deployed = output_dir / "workflows" / "stub.js"
        assert deployed.read_bytes() == _MINIMAL_E2_SRC, (
            "auto variant must be byte-identical to source"
        )


# ---------------------------------------------------------------------------
# AC-4: reachability
# ---------------------------------------------------------------------------


class TestReachability:
    """AC-4 — deployed workflow can be resolved and opened without error."""

    @pytest.mark.skipif(
        not _QUICK_FIX_JS.exists(),
        reason="quick-fix.js not found in templates/workflows-js/",
    )
    def test_deployed_workflow_is_readable(self, monkeypatch, tmp_path):
        """Deploy a workflow and verify the deployed file can be opened."""
        import build_phases
        # Set up source tree.
        src_dir = tmp_path / "templates" / "workflows-js"
        src_dir.mkdir(parents=True)
        shutil.copy(_QUICK_FIX_JS, src_dir / _QUICK_FIX_JS.name)

        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp_path / "templates")
        monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.999")
        config = {"workflows": {"enabled": True, "engine": "e2"}}

        output_dir = tmp_path / "consumer_root"
        output_dir.mkdir()

        written = build_workflow_scripts(output_dir, config, dry_run=False, force=True)
        assert written >= 1, "At least one file must be written"

        deployed = output_dir / "workflows" / _QUICK_FIX_JS.name
        assert deployed.exists(), f"Deployed file not found at {deployed}"

        # Open the deployed file without error.
        try:
            content = deployed.read_bytes()
        except OSError as exc:
            pytest.fail(f"Cannot read deployed workflow: {exc}")

        assert len(content) > 0, "Deployed file must not be empty"

    def test_synthetic_e2_workflow_is_readable_after_deploy(self, monkeypatch, tmp_path):
        """Deploy a synthetic E2 workflow and verify it can be opened."""
        import build_phases
        src_dir = tmp_path / "templates" / "workflows-js"
        src_dir.mkdir(parents=True)
        (src_dir / "synthetic.js").write_bytes(_MINIMAL_E2_SRC)

        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp_path / "templates")
        monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.999")
        config = {"workflows": {"enabled": True, "engine": "e2"}}

        output_dir = tmp_path / "consumer_root"
        output_dir.mkdir()

        build_workflow_scripts(output_dir, config, dry_run=False, force=True)

        deployed = output_dir / "workflows" / "synthetic.js"
        assert deployed.exists(), "Deployed synthetic workflow must exist"

        try:
            content = deployed.read_bytes()
        except OSError as exc:
            pytest.fail(f"Cannot open deployed synthetic workflow: {exc}")

        assert content == _MINIMAL_E2_SRC
