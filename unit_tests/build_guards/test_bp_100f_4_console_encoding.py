"""
MODULE: unit_tests/build_guards/test_bp_100f_4_console_encoding.py
GOAL: BP-100f-4 — every scripts/build_colors.py print helper (success, warn,
    error, info, dry_run, heading) must never raise UnicodeEncodeError when
    the console's stdout encoding cannot represent a character it writes
    (e.g. a Windows cp1252 console and the '✓' glyph success() prints right
    after the manifest write); on a UTF-8 capable console the original
    characters must still be printed unchanged.
BUSINESS CONTEXT: build.py crashes with
    "UnicodeEncodeError: 'charmap' codec can't encode character '\\u2713'"
    on a real Windows cp1252 console, because every helper in
    scripts/build_colors.py calls bare ``print()``. Python's default
    ``print()`` uses ``sys.stdout``'s configured encoding with
    ``errors="strict"``; when that encoding cannot represent a character
    (cp1252 has no code point for '✓'), the write raises instead of
    degrading. This crashes the whole build immediately after the manifest
    is written, so the build never reaches completion on affected consoles.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100f-4.yaml.
ARCHITECTURE / EXERCISE STRATEGY:
    Loads scripts/build_colors.py via
    ``importlib.util.spec_from_file_location`` (per-test unique module name)
    so this test never depends on package installation or sys.path state.
    Monkeypatches ``sys.stdout`` to a real ``io.TextIOWrapper`` wrapping an
    ``io.BytesIO()``, with ``encoding="cp1252"`` and ``errors="strict"`` —
    the exact combination that reproduces the crash on a real Windows
    console. Each helper is called against this stream; the wrapper is
    flushed and the underlying BytesIO is read back and decoded to assert
    on the actual bytes written (not on a mocked call).

    The colour ANSI constants (RESET, GREEN, etc.) are resolved once at
    import time from ``sys.stdout.isatty()`` / NO_COLOR / TERM, so this test
    does not assert on their exact value — assertions use substring
    containment (`in`) against the message text, which is stable regardless
    of whether colour codes are present.

RED BASELINE (expected on the current, unmodified build_colors.py): every
    helper calls bare ``print()``, so writing a message containing the '✓'
    glyph (or any other character absent from cp1252) through the
    cp1252/strict TextIOWrapper raises UnicodeEncodeError instead of
    degrading. test_success_does_not_crash_on_cp1252_stdout and
    test_all_helpers_survive_unencodable_message_on_cp1252_stdout are
    expected to FAIL with UnicodeEncodeError until the helpers are made to
    degrade gracefully (e.g. via errors="replace" or an encode/decode
    round-trip before printing).
"""

from __future__ import annotations

import importlib.util
import io
import sys
import unittest
import unittest.mock
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILD_COLORS_SRC = _REPO_ROOT / "scripts" / "build_colors.py"

_UNIQUE_COUNTER = [0]


def _load_build_colors():
    """Load scripts/build_colors.py fresh, under a unique module name.

    Returns:
        The freshly executed build_colors module object.
    """
    _UNIQUE_COUNTER[0] += 1
    unique_name = f"_bp100f4_build_colors_{_UNIQUE_COUNTER[0]}"
    spec = importlib.util.spec_from_file_location(unique_name, _BUILD_COLORS_SRC)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _make_wrapped_stream(encoding: str) -> io.TextIOWrapper:
    """Build a real TextIOWrapper over a BytesIO with strict error handling.

    Args:
        encoding: The codec name to bind the wrapper to (e.g. "cp1252").

    Returns:
        A TextIOWrapper ready to be used as a sys.stdout replacement.
    """
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors="strict")


def _read_decoded(stream: io.TextIOWrapper) -> str:
    """Flush a TextIOWrapper and decode its underlying BytesIO back to text.

    Args:
        stream: The TextIOWrapper to flush and read from.

    Returns:
        The decoded text content written to the stream so far.
    """
    stream.flush()
    buffer = stream.buffer
    assert isinstance(buffer, io.BytesIO)
    return buffer.getvalue().decode(stream.encoding)


class TestSuccessDoesNotCrashOnCp1252Stdout(unittest.TestCase):
    """AC BP-100f-4: success() must not raise on a cp1252 console."""

    def setUp(self) -> None:
        self.build_colors = _load_build_colors()

    def test_success_does_not_crash_on_cp1252_stdout(self) -> None:
        # covers: BP-100f-4
        # angle: reachability
        stream = _make_wrapped_stream("cp1252")
        with unittest.mock.patch.object(sys, "stdout", stream):
            try:
                self.build_colors.success("manifest written")
            except UnicodeEncodeError as exc:
                self.fail(
                    "build_colors.success() raised UnicodeEncodeError on a "
                    "cp1252 stdout stream instead of degrading gracefully — "
                    f"this is the exact BP-100f-4 crash symptom: {exc!r}"
                )

        decoded = _read_decoded(stream)
        self.assertIn(
            "manifest written",
            decoded,
            msg=f"success() output does not contain the expected message text. Got: {decoded!r}",
        )


class TestAllHelpersSurviveUnencodableMessageOnCp1252Stdout(unittest.TestCase):
    """AC BP-100f-4: every print helper must survive an unrepresentable char."""

    def setUp(self) -> None:
        self.build_colors = _load_build_colors()

    def test_all_helpers_survive_unencodable_message_on_cp1252_stdout(self) -> None:
        # covers: BP-100f-4
        # angle: boundary
        message = "✓ → ü"
        helper_names = ["success", "warn", "error", "info", "dry_run", "heading"]

        for helper_name in helper_names:
            with self.subTest(helper=helper_name):
                stream = _make_wrapped_stream("cp1252")
                helper = getattr(self.build_colors, helper_name)
                with unittest.mock.patch.object(sys, "stdout", stream):
                    try:
                        helper(message)
                    except UnicodeEncodeError as exc:
                        self.fail(
                            f"build_colors.{helper_name}() raised "
                            "UnicodeEncodeError on a cp1252 stdout stream "
                            f"for a message containing unencodable "
                            f"characters (BP-100f-4): {exc!r}"
                        )


class TestSuccessPrintsUnchangedGlyphOnUtf8Stdout(unittest.TestCase):
    """AC BP-100f-4: on a UTF-8 console the original glyph is unchanged."""

    def setUp(self) -> None:
        self.build_colors = _load_build_colors()

    def test_success_prints_unicode_glyph_unchanged_on_utf8_stdout(self) -> None:
        # covers: BP-100f-4
        # angle: criterion
        stream = _make_wrapped_stream("utf-8")
        with unittest.mock.patch.object(sys, "stdout", stream):
            self.build_colors.success("manifest written")

        decoded = _read_decoded(stream)
        self.assertIn(
            "✓",
            decoded,
            msg=(
                "success() must print the literal '✓' glyph unchanged on a "
                f"UTF-8 capable console. Got: {decoded!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
