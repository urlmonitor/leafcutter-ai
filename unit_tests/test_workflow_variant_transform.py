"""Unit tests for the build-time _emit_workflow_variant transform.

MODULE GOAL: Verify that _emit_workflow_variant produces the correct output
    for each supported engine target (e2, auto) and raises an explicit
    ValueError when the unsupported "e1" engine is requested. Also verifies
    that the build pipeline correctly reads the engine from config and preserves
    the SHA-256 idempotency guard.

BUSINESS CONTEXT: The build pipeline must emit E2-only workflow scripts at
    deploy time. E2 and auto targets receive a byte-identical copy of the
    source. The "e1" engine is unsupported — it produces an unloadable module
    (top-level `return` inside `export async function run`) — and must raise a
    clear, explicit ValueError rather than silently emitting a corrupt module.

ARCHITECTURE: _emit_workflow_variant is a pure function in scripts/build_phases.py.
    It is called by build_workflow_scripts inside the copy loop. The SHA-256
    idempotency guard compares emitted bytes (post-transform) against the
    existing deployed file, not the raw source bytes.

Ticket: 09_e2_only_transform
Covers:
  - AC-1: E2 target is byte-identity (also tests "auto")
  - AC-2: E1 target raises an explicit unsupported error (no corrupt module)
  - AC-3: engine selected from config + SHA-256 idempotency short-circuits
  - AC-4: reachability (deployed workflow loads without error)
"""

from __future__ import annotations

import pathlib
import shutil
import sys

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — scripts/ must be importable.
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import _emit_workflow_variant, build_workflow_scripts  # noqa: E402

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
# AC-2: E1 target raises an explicit unsupported error (no corrupt module)
# ---------------------------------------------------------------------------


class TestE1Unsupported:
    """AC-2 — 'e1' engine raises an explicit ValueError (no shim emitted).

    Implementation requirement: _emit_workflow_variant(raw, "e1") must raise
    ValueError naming E1 as unsupported instead of prepending the broken shim.
    The shim produces an UNLOADABLE module (top-level `return` inside
    `export async function run`) — removing it is the safe default.
    """

    def test_e1_raises_unsupported_error(self):
        # covers: UNKNOWN
        """_emit_workflow_variant(src, 'e1') must raise ValueError.

        Must be made green by: removing the E1 shim branch in _emit_workflow_variant
        and replacing it with `raise ValueError("E1 workflow engine is not supported")`.
        """
        src = _MINIMAL_E2_SRC
        with pytest.raises(ValueError):
            _emit_workflow_variant(src, "e1")

    def test_e1_error_message_names_e1_as_unsupported(self):
        # covers: UNKNOWN
        """ValueError raised for 'e1' must contain a message naming E1 as unsupported.

        The error message must reference "E1" (or "e1") and indicate it is not
        supported, so build operators receive a clear, actionable error.
        """
        src = b"const x = 1\n"
        with pytest.raises(ValueError) as exc_info:
            _emit_workflow_variant(src, "e1")
        msg = str(exc_info.value).lower()
        assert "e1" in msg or "unsupport" in msg or "not support" in msg, (
            f"ValueError message must name E1 as unsupported; got: {exc_info.value!r}"
        )

    def test_e1_raises_for_any_source(self):
        # covers: UNKNOWN
        """ValueError must be raised regardless of the source content."""
        for src in [b"", b"// minimal\n", _MINIMAL_E2_SRC, b"\x00\x01\x02"]:
            with pytest.raises(ValueError, match="(?i)e1|unsupport|not support"):
                _emit_workflow_variant(src, "e1")

    def test_e1_no_shim_content_emitted(self):
        # covers: UNKNOWN
        """After the fix, E1 shim markers must never appear in the function's output.

        If ValueError is raised (correct), no output is produced — test passes.
        If ValueError is NOT raised (current broken state), the function returns
        shim bytes that contain "export async function run" — the assertion
        fails, making this test RED today.
        """
        src = _MINIMAL_E2_SRC
        try:
            result = _emit_workflow_variant(src, "e1")
        except ValueError:
            # Correct behavior: ValueError raised, no shim bytes produced.
            return
        # If we reach this point, no exception was raised — inspect the result.
        # Currently the shim IS returned, so this assertion fails → RED.
        text = result.decode("utf-8", errors="replace")
        assert "export async function run" not in text, (
            "E1 shim must not be emitted. Expected ValueError to be raised, "
            "but _emit_workflow_variant returned bytes containing the corrupt shim."
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

    def test_e1_engine_raises_value_error(self, monkeypatch, tmp_dirs):
        # covers: UNKNOWN
        """build_workflow_scripts with engine=e1 must propagate ValueError — no shim written.

        After the fix, _emit_workflow_variant raises ValueError for 'e1'. Since
        build_workflow_scripts only catches UnicodeDecodeError, the ValueError
        propagates to the caller. This test is RED today (no exception raised;
        shim bytes are written instead). It becomes GREEN when python-coder removes
        the E1 shim branch.
        """
        import build_phases
        tmp_path, src_dir, js_file, output_dir = tmp_dirs
        monkeypatch.setattr(build_phases, "TEMPLATES_DIR", tmp_path / "templates")
        monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.999")
        config = {"workflows": {"enabled": True, "engine": "e1"}}

        with pytest.raises(ValueError):
            build_workflow_scripts(output_dir, config, dry_run=False, force=True)

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
