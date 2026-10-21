"""
MODULE: unit_tests/build_orchestration/test_tq500g1v_list_speed.py
GOAL: Timing test for the writer's ``list`` step on THIS repository (TQ-500g-1-v, user decisions
    2026-10-15 and 2026-10-21). It took 82 seconds for one id. The gate is machine-independent: the
    50-id run takes at most 2.0 x the 1-id run + 1.0 s, and both runs stay under 15 s.
BUSINESS CONTEXT: TQ-500g-1-ix budgets the list step at 2 seconds for up to 50 ids; that figure is a
    developer-machine target and is NOT asserted (it failed on slow CI runners). A small fixture
    cannot show scaling holds, so this runs the real CLI against the real AC store and the real
    test root. The list reads the same declared scope as the runner (one shared reader); the test
    compares the two for the same ids so a second, faster reader that disagrees cannot pass.
ARCHITECTURE: Subprocess only for the timing (wall clock around the CLI). The cross-check imports
    the runner's own reader after the timing assertions, so a slow list fails on the clock first.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import yaml

import unit_tests.build_orchestration._tq500g1ix_fixtures as ix

REPO_ROOT = ix.REPO_ROOT
AC_ROOT = REPO_ROOT / "docs" / "acceptance-criteria"
SCALE_FACTOR = 2.0  # the 50-id run may cost at most this many times the 1-id run ...
SCALE_SLACK_SECONDS = 1.0  # ... plus this slack
CEILING_SECONDS = 15.0  # absolute per-run ceiling; catches the original 82 s bug on any machine
KILL_AFTER_SECONDS = 30  # a slow list is stopped here and fails on the clock, not on a hang


def _ids_with_must_catch(limit: int) -> list[str]:
    """Ids of the first *limit* stored ACs whose test_spec names a must_catch (sorted path order)."""
    found: list[str] = []
    for path in sorted(AC_ROOT.rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "must_catch:" not in text:
            continue
        data = yaml.safe_load(text)
        if isinstance(data, dict) and any(isinstance(e, dict) and e.get("must_catch") for e in data.get("test_spec") or []):
            found.append(str(data["id"]))
        if len(found) == limit:
            break
    return found


def _timed_list(ids: list[str]) -> tuple[float, int | None, dict | None]:
    """Run ``wrong_version_writer.py list`` for *ids* here; return ``(seconds, exit code, parsed JSON)``."""
    cmd = [sys.executable, str(ix.WRITER), "list", "--ac-ids", ",".join(ids), "--ac-root", str(AC_ROOT),
           "--test-root", str(REPO_ROOT), "--base-ref", "HEAD"]
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=KILL_AFTER_SECONDS, env=ix._env())  # noqa: SLF001
    except subprocess.TimeoutExpired:
        return time.monotonic() - start, None, None
    try:
        parsed = json.loads(proc.stdout.strip())
    except ValueError:
        parsed = None
    return time.monotonic() - start, proc.returncode, parsed


def test_writer_list_meets_time_budget_on_real_repo():
    # covers: TQ-500g-1-v
    # angle: boundary
    # must_catch: list rescans the whole test root per id
    # must_catch: a second reader added for list that disagrees with the runner's
    # must_catch: list cost grows with the number of ids
    ids = _ids_with_must_catch(50)
    assert len(ids) == 50, f"the real AC store must offer 50 ids with must_catch entries, found {len(ids)}"
    results = {}
    for count in (1, 50):
        seconds, code, parsed = _timed_list(ids[:count])
        results[count] = (seconds, code, parsed)
    t1, t50 = results[1][0], results[50][0]
    times = f"t1={t1:.2f} s, t50={t50:.2f} s"
    for count, (seconds, code, parsed) in results.items():
        assert code == 0 and isinstance(parsed, dict) and set(parsed) == {"owed", "error"}, (count, code, parsed, times)
        assert parsed["error"] is None and isinstance(parsed["owed"], list), (parsed, times)
        assert seconds < CEILING_SECONDS, f"list for {count} id(s) took {seconds:.2f} s, ceiling {CEILING_SECONDS} s ({times})"
    limit = SCALE_FACTOR * t1 + SCALE_SLACK_SECONDS
    assert t50 <= limit, f"list cost grows with the number of ids: 50 ids may take {limit:.2f} s, took {t50:.2f} s ({times})"
    # Same ids: the list's names and files are what the runner's own reader derives.
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "build_orchestration"))
    import _wvr_scope as scope  # noqa: PLC0415 -- the runner's reader; imported only after the clock checks

    scoped = scope.resolve_scope(ids, REPO_ROOT, AC_ROOT)
    assert not scoped.problem, scoped.problem
    expected = {o.name: list(o.files) for o in scope.owed_names(scoped.tests, None, lambda: [])}
    listed = results[50][2]["owed"]
    assert [o["name"] for o in listed] == list(expected), "the list's names or order differ from the runner's reader"
    for item in listed:
        if item["scope"] == "declared":
            assert item["files"] == expected[item["name"]], f"files differ from the runner's reader for {item['name']!r}"
