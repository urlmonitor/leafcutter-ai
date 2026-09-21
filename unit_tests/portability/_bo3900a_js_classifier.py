r"""
MODULE: unit_tests/portability/_bo3900a_js_classifier.py
GOAL: Extract the REAL BO-3900 path-classification helper block out of a
    workflow script's own source text and run it via a real Node.js
    subprocess, so BO-3900a's tests exercise the shipped code — never a
    Python reimplementation of the same rules, which could silently drift
    from what templates/workflows-js/*.js actually does.
BUSINESS CONTEXT: BO-3900a.yaml's test_rationale requires classification be
    "asserted on the runner CI actually has" and forbids a test that merely
    "calls an extracted path helper directly... INSTEAD of the harness run"
    for the reachability entry — but explicitly welcomes an extracted-helper
    test IN ADDITION for the criterion/seam/failure entries. This module is
    that extraction: it slices the helper block out of the real script file
    between two sentinel comments the implementation carries, and evaluates
    that exact text in Node — no reimplementation, no drift.
ARCHITECTURE: `process.platform` is forced to a caller-chosen value INSIDE
    the Node subprocess before the extracted functions run, so the "same
    result on a POSIX host and on a Windows host" property is proven by
    EXECUTION (toggling the actual value the code could have read) rather
    than by a source-text grep for "platform", which BO-3900 explicitly
    disallows as coverage.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

_START_MARKER = "// BO-3900-PATH-HELPERS-START"
_END_MARKER = "// BO-3900-PATH-HELPERS-END"


def extract_path_helpers(script_path: Path) -> str:
    """Slice the BO-3900 path-helper block out of `script_path`'s own text.

    Raises:
        AssertionError: the block's sentinel markers are absent — the
            script does not yet carry the shared cross-platform path logic
            this test family exercises (a legitimate RED-baseline state
            before BO-3900 is implemented).
    """
    text = script_path.read_text(encoding="utf-8")
    start = text.find(_START_MARKER)
    end = text.find(_END_MARKER, start if start != -1 else 0)
    if start == -1 or end == -1:
        raise AssertionError(
            f"{script_path} does not carry the BO-3900 path-helper block "
            f"(markers {_START_MARKER!r} / {_END_MARKER!r} not found) — "
            "the shared classification/resolution logic has not landed yet."
        )
    return text[start:end]


def _run_node(driver_source: str, timeout: int = 10) -> Any:
    proc = subprocess.run(
        ["node", "-e", driver_source],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"node classifier driver failed (exit {proc.returncode}): {proc.stderr}"
        )
    return json.loads(proc.stdout)


def classify_many(
    script_path: Path, inputs: list[str], forced_platform: str | None = None
) -> list[str]:
    """Call the real classifyPathForm(x) for each x in `inputs`.

    When `forced_platform` is given (e.g. "linux" or "win32"),
    `process.platform` is overridden to that value INSIDE the subprocess
    before the extracted functions run — proving the result does not depend
    on it, by actually varying it, not by inspecting source text.
    """
    helpers = extract_path_helpers(script_path)
    platform_override = (
        f"Object.defineProperty(process, 'platform', {{value: {json.dumps(forced_platform)}}});\n"
        if forced_platform
        else ""
    )
    driver = (
        "'use strict';\n"
        + platform_override
        + helpers
        + "\nconst __inputs__ = "
        + json.dumps(inputs)
        + ";\nprocess.stdout.write(JSON.stringify(__inputs__.map(x => classifyPathForm(x))));\n"
    )
    return _run_node(driver)


def resolve_many(
    script_path: Path,
    root: str,
    inputs: list[str],
    forced_platform: str | None = None,
) -> list[str | None]:
    """Call the real resolvePathOntoRoot(root, x) for each x in `inputs`."""
    helpers = extract_path_helpers(script_path)
    platform_override = (
        f"Object.defineProperty(process, 'platform', {{value: {json.dumps(forced_platform)}}});\n"
        if forced_platform
        else ""
    )
    driver = (
        "'use strict';\n"
        + platform_override
        + helpers
        + "\nconst __root__ = "
        + json.dumps(root)
        + ";\nconst __inputs__ = "
        + json.dumps(inputs)
        + ";\nprocess.stdout.write(JSON.stringify(__inputs__.map(x => {"
        + " const r = resolvePathOntoRoot(__root__, x); return r.ok ? r.path : null; })));\n"
    )
    return _run_node(driver)
