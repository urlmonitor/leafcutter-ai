"""
MODULE: scripts/evals/designer_eval/dispatch.py
GOAL: Build the live input of a test-designer row from the same ingredients as plan-feature.js
    dispatchTestDesign: the record ids, the verbatim design_prepass.py report and ac_store_path.
BUSINESS CONTEXT: TQ-200d-3 (OQ-13). The designer must see what the real pipeline gives it, so
    the pre-pass report is the script's own stdout for the row's sandbox, never text the eval
    assembles. The input asks for the test-design group only and carries nothing the row scores
    (no wrong-version names, no recorded output), so the eval cannot hand the agent its answer.
ARCHITECTURE: ``build_dispatch_input(row, sandbox)`` is called by produced_tests_mode.live_output
    through the ``input_builder`` config key, after the sandbox is built and before the agent runs.
    A pre-pass failure raises SandboxError, which the mode scores as a failed row carrying the error.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import produced_tests_runs as runs

PREPASS = Path(__file__).resolve().parents[2] / "ac_store" / "design_prepass.py"
TIMEOUT_SECONDS = 120


def prepass_report(ids: list[str], store: Path, sandbox: Path) -> str:
    """The stripped stdout of design_prepass.py run on *sandbox*; SandboxError if it cannot run."""
    cmd = [sys.executable, str(PREPASS), "--ids", ",".join(ids), "--store-root", str(store), "--repo-root", str(sandbox)]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=TIMEOUT_SECONDS, cwd=sandbox)
    except (OSError, subprocess.SubprocessError) as exc:
        msg = f"design_prepass.py could not run for {ids}: {exc!r}"
        raise runs.SandboxError(msg) from exc
    return done.stdout.strip()


def build_dispatch_input(row: dict, sandbox: Path, expected_field: str = "expected") -> str:
    """The text the designer is asked: ids, the verbatim pre-pass report, ac_store_path, test-design group only."""
    expected = row[expected_field]
    ids = expected["records"]
    store = sandbox / expected["store"]
    return (
        f"{row['input']}\n"
        f"Design the tests of these requirement records: {', '.join(ids)}.\n"
        f"Pre-pass report (file facts, verbatim): {prepass_report(ids, store, sandbox)}\n"
        "Write the test design only: test_spec, test_design_authorship and test_design_opened_files. "
        f"Edit AC YAML files ONLY under {store.as_posix()} and touch nothing else.\n"
        f"ac_store_path: {store.as_posix()}\n"
        'Return one JSON object: { "status": "ok" | "blocked", "records": [...], "anomalies": [...] }\n'
    )
