"""
Shared helpers + constants for the TQ-600a-1 test files:
``test_tq_600a_1.py`` (tests 1, 2, 5, 6, 7) and
``test_tq_600a_1_multiworker.py`` (tests 3, 4 — the ``-n 2`` cross-worker
pair). Extracted purely to keep each test file under the repo's
GE-127a-1 file-size limit (400 lines) after the original single file
(``check-file-size`` measured 449 counted lines against the class alone)
tripped the pre-commit hook. No test behavior, assertion, name, or
``# covers:``/``# angle:`` tag changed by this extraction — see
``test_tq_600a_1.py``'s module docstring for the full "ASSUMED PRODUCTION
CONTRACT" this whole test suite is pinned to; that content was NOT
duplicated here, only relocated helpers and constants that both files need.
"""
from __future__ import annotations

import json
import shutil
import sys
import textwrap
from pathlib import Path

# unit_tests/suite_performance/_test_helpers.py -> parents[2] == worktree root
_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
if str(_WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKTREE_ROOT))

_SUITE_PERF_DIR = Path(__file__).resolve().parent

# Env var the assumed production contract uses to emit one JSONL line per
# REAL `python scripts/build.py --target-dir <path>` subprocess execution.
_EXECUTION_LOG_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG"

# Generous timeout for subprocess pytest sessions that perform a real
# ~60s package deploy (see scripts/build.py measured deploy cost in
# TQ-600.yaml). These tests are integration tests over the real deploy
# subprocess and are correctly slow until the shared-layout caching this
# AC specifies exists; they are suffixed _MANUAL per the test-writer
# performance convention (testing_context.manual_test_suffix) because they
# cannot complete within max_test_duration_seconds.
_REAL_DEPLOY_SUBPROCESS_TIMEOUT_S = 240


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _write_consumer_test(
    directory: Path,
    filename: str,
    body: str,
) -> Path:
    """Write a tiny real pytest test file that consumes shared_reference_layout.

    `body` is the source of the test function(s) — dedented and written
    verbatim so callers can shape exactly what each simulated consumer does.
    """
    directory.mkdir(parents=True, exist_ok=True)
    init_file = directory / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")
    target = directory / filename
    target.write_text(textwrap.dedent(body), encoding="utf-8")
    return target


def _rmtree_if_exists(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
