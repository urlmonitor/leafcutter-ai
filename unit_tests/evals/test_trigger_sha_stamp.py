"""
MODULE: test_trigger_sha_stamp
GOAL: Prove run_agent_eval.py stamps a `trigger_shas` field (repo-relative path
    -> sha256 hex over the agent's resolved trigger globs) into every result it
    writes, so the eval_selector freshness gate (TQ-200b-4) has the input SHAs it
    compares against. Uses --self-test (no model call) against the real
    pt-classifier config so the stamp is exercised end-to-end deterministically.

Target module: scripts/evals/run_agent_eval.py (+ shared resolver in eval_selector.py)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVALS_DIR = _REPO_ROOT / "scripts" / "evals"
_RUNNER = _EVALS_DIR / "run_agent_eval.py"
_CONFIG = _EVALS_DIR / "agent_eval_config.json"

sys.path.insert(0, str(_EVALS_DIR))
import eval_selector  # noqa: E402


def test_selftest_result_carries_trigger_shas(tmp_path: Path) -> None:
    results_file = tmp_path / "pt-classifier-selftest.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(_RUNNER),
            "--agent",
            "pt-classifier",
            "--self-test",
            "--results-file",
            str(results_file),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert results_file.exists(), "runner did not write the results file"

    payload = json.loads(results_file.read_text(encoding="utf-8"))
    # Existing fields are preserved.
    assert payload["agent"] == "pt-classifier"
    assert "aggregate" in payload
    # The stamp is present and non-empty.
    shas = payload.get("trigger_shas")
    assert isinstance(shas, dict) and shas, "trigger_shas stamp missing or empty"

    # Every stamped key is a repo-relative path with a 64-hex sha256 value.
    for rel, digest in shas.items():
        assert not Path(rel).is_absolute()
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)

    # The stamp equals what the selector resolves for the same agent's triggers,
    # so the freshness comparison is apples-to-apples.
    config = eval_selector.load_config(_CONFIG)
    triggers = eval_selector.agent_triggers(config)["pt-classifier"]
    expected = eval_selector.resolve_trigger_shas(_REPO_ROOT, triggers)
    assert shas == expected
