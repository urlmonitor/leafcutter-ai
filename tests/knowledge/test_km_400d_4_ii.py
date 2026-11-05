"""KM-400d-4-ii: a retrieval stuck in a blocked call still prints its answer and exits within the
deadline plus one second, counted on the retrieval clock.

Every test runs ``python -m knowledge retrieve`` in a fresh subprocess whose resolver/driver block in
``time.sleep`` (not cancellable) inside the transaction worker thread. A process that waits for the
blocked thread does not exit inside the subprocess timeout, which fails the test.
"""

import json

from tests.knowledge import _km_400d_4_support as support
from tests.knowledge._km_400d_4_support import BLOCK, fake, run_retrieve

BLOCKED_LOOKUP = dict(v4_delay=BLOCK, any_delay=BLOCK)
EXIT_BOUND_S = 3.0  # deadline_ms 2000 plus 1000 ms


def _after_start(run):
    assert run.retrieval_start is not None, "the retrieval never started"
    return run.returned_at - run.retrieval_start


def test_km_400d_4_ii_blocked_lookup_prints_unavailable_with_deadline_warning(tmp_path):
    # covers: KM-400d-4-ii
    # angle: discrimination
    """The answer is printed while the blocked lookup still runs: unavailable plus the warning."""
    run = run_retrieve(tmp_path, fake(**BLOCKED_LOOKUP), deadline_ms=2000)
    assert run.answer["status"] == "unavailable"
    assert "retrieval deadline reached" in run.answer["warnings"]
    assert _after_start(run) < BLOCK - 5, "the answer arrived only after the blocked call ended"


def test_km_400d_4_ii_blocked_lookup_exits_with_the_unavailable_exit_code(tmp_path):
    # covers: KM-400d-4-ii
    # angle: criterion
    """The process exits 2, the code main returns for an unavailable status."""
    run = run_retrieve(tmp_path, fake(**BLOCKED_LOOKUP), deadline_ms=2000)
    assert run.returncode == 2


def test_km_400d_4_ii_exit_is_within_deadline_plus_one_second_of_retrieval_start(tmp_path):
    # covers: KM-400d-4-ii
    # angle: discrimination
    """deadline_ms 2000 exits within 3.0 s; deadline_ms 4000 within 5.0 s (no hard-coded constant)."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    short = run_retrieve(tmp_path / "a", fake(**BLOCKED_LOOKUP), deadline_ms=2000)
    longer = run_retrieve(tmp_path / "b", fake(**BLOCKED_LOOKUP), deadline_ms=4000)
    assert _after_start(short) <= EXIT_BOUND_S, _after_start(short)
    assert _after_start(longer) <= 5.0, _after_start(longer)
    assert _after_start(longer) >= 3.5, "the bound is not driven by the request's own deadline"


def test_km_400d_4_ii_the_bound_is_counted_on_the_retrieval_clock_not_process_start(tmp_path):
    # covers: KM-400d-4-ii
    # angle: boundary
    """With a 2 s slow start-up the exit is >3 s after process start but <=3 s after retrieval start."""
    config = fake(start_sleep=2.0, **BLOCKED_LOOKUP)
    run = run_retrieve(tmp_path, config, deadline_ms=2000)
    assert run.answer["status"] == "unavailable"
    assert _after_start(run) <= EXIT_BOUND_S
    process_start = run.retrieval_start - 2.0
    assert run.returned_at - process_start > EXIT_BOUND_S, "start-up was not actually slow"
    assert abs(run.stats["duration_ms"] / 1000 - _after_start(run)) <= 1.5


def test_km_400d_4_ii_blocked_close_does_not_delay_the_printed_answer_or_exit(tmp_path):
    # covers: KM-400d-4-ii
    # angle: discrimination
    """A driver close() that blocks 20 s does not delay the answer or the exit."""
    config = fake(close_delay=BLOCK, driver_close_delay=BLOCK, **BLOCKED_LOOKUP)
    run = run_retrieve(tmp_path, config, deadline_ms=2000)
    assert run.answer["status"] == "unavailable"
    assert _after_start(run) <= EXIT_BOUND_S


def test_km_400d_4_ii_blocked_close_answer_is_complete_valid_json(tmp_path):
    # covers: KM-400d-4-ii
    # angle: failure
    """The whole stdout is one JSON object ending in a newline: the early exit did not cut it."""
    config = fake(close_delay=BLOCK, driver_close_delay=BLOCK, **BLOCKED_LOOKUP)
    run = run_retrieve(tmp_path, config, deadline_ms=2000)
    assert run.stdout.endswith("\n")
    assert isinstance(json.loads(run.stdout), dict)


def test_km_400d_4_ii_a_blocked_connect_after_a_fast_lookup_does_not_delay_exit(tmp_path):
    # covers: KM-400d-4-ii
    # angle: boundary
    """A stuck connect (fast lookup) is bounded too, not only the name-lookup stall."""
    config = fake(v4_delay=0.05, any_delay=0.05, connect_delay=BLOCK)
    run = run_retrieve(tmp_path, config, deadline_ms=2000)
    assert run.answer["status"] == "unavailable"
    assert _after_start(run) <= EXIT_BOUND_S


def test_km_400d_4_ii_evidence_before_the_deadline_is_reported_when_follow_up_blocks(tmp_path):
    # covers: KM-400d-4-ii
    # angle: failure
    """Evidence gathered in 0.5 s is kept (status partial) when the follow-up query blocks."""
    config = fake(query_script=[0.5, 0, 0], query_default=BLOCK)
    run = run_retrieve(tmp_path, config, deadline_ms=2000, request_extra={"disclosure_level": 1})
    answer = run.answer
    assert answer["status"] == "partial", answer["status"]
    assert len(answer["evidence"]) == 1, "the item gathered before the deadline was dropped"
    assert "retrieval deadline reached" in answer["warnings"]


def test_km_400d_4_ii_partial_evidence_case_exits_within_the_bound(tmp_path):
    # covers: KM-400d-4-ii
    # angle: boundary
    """While partial evidence is reported the process still exits within 3.0 s of retrieval start."""
    config = fake(query_script=[0.5, 0, 0], query_default=BLOCK)
    run = run_retrieve(tmp_path, config, deadline_ms=2000, request_extra={"disclosure_level": 1})
    assert run.answer["status"] == "partial"
    assert _after_start(run) <= EXIT_BOUND_S


def test_km_400d_4_ii_deadline_bound_is_reachable_through_the_retrieve_cli(tmp_path):
    # covers: KM-400d-4-ii
    # angle: reachability
    """Through the real CLI a 20 s blocked lookup ends with the unavailable answer and exit 2 well before 20 s."""
    run = run_retrieve(tmp_path, fake(**BLOCKED_LOOKUP), deadline_ms=2000)
    assert run.returncode == 2
    assert run.answer["status"] == "unavailable"
    assert "retrieval deadline reached" in run.answer["warnings"]
    assert support.server_lookups(run), "the blocked lookup was never reached through the CLI"
    assert _after_start(run) < 10
