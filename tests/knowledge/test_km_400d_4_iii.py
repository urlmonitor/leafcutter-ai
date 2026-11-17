"""KM-400d-4-iii: a retrieval result reports name-lookup, connect and query time and names the step
a deadline miss happened in.

Every test runs ``python -m knowledge retrieve`` (real argv, real ``main``, real service and
``Neo4jBackend._transaction`` worker thread) in a fresh subprocess; only the resolver and the driver
are doubles (see ``_km_400d_4_support``). Implementation target: additive ``stats.resolve_ms``,
``stats.connect_ms``, ``stats.query_ms``, ``stats.resolve_from_memory`` and ``stats.deadline_step``
(``"name lookup"`` | ``"connect"`` | ``"query"`` | null), measured on the retrieval clock.
"""

from tests.knowledge import _km_400d_4_support as support
from tests.knowledge._km_400d_4_support import BLOCK, fake, run_requests, run_retrieve

TIMED = dict(v4_delay=0.2, any_delay=0.2, connect_delay=0.3, query_script=[0.5])


def _ints(stats, *names):
    for name in names:
        assert name in stats, f"stats carries no {name}: {sorted(stats)}"
        assert isinstance(stats[name], int) and not isinstance(stats[name], bool), (
            f"stats.{name} must be an integer, got {stats[name]!r}"
        )


def test_km_400d_4_iii_successful_retrieve_has_status_ok_with_step_timings_present(tmp_path):
    # covers: KM-400d-4-iii
    # angle: criterion
    """A healthy retrieval stays ok and carries the three step timings as integers."""
    run = run_retrieve(tmp_path, fake(**TIMED))
    assert run.returncode == 0
    assert run.answer["status"] == "ok"
    _ints(run.stats, "resolve_ms", "connect_ms", "query_ms")


def test_km_400d_4_iii_step_timings_match_the_injected_delays_within_100_ms(tmp_path):
    # covers: KM-400d-4-iii
    # angle: boundary
    """0.2 s lookup, 0.3 s connect and 0.5 s of queries give 200, 300 and 500 ms (each +/- 100)."""
    stats = run_retrieve(tmp_path, fake(**TIMED)).stats
    _ints(stats, "resolve_ms", "connect_ms", "query_ms")
    assert abs(stats["resolve_ms"] - 200) <= 100, stats
    assert abs(stats["connect_ms"] - 300) <= 100, stats
    assert abs(stats["query_ms"] - 500) <= 100, stats


def test_km_400d_4_iii_no_step_time_is_folded_into_another(tmp_path):
    # covers: KM-400d-4-iii
    # angle: discrimination
    """Raising only the lookup delay by 0.8 s raises only resolve_ms; the steps do not overlap."""
    (tmp_path / "base").mkdir()
    (tmp_path / "slow").mkdir()
    base = run_retrieve(tmp_path / "base", fake(**TIMED)).stats
    slow = run_retrieve(tmp_path / "slow", fake(**{**TIMED, "v4_delay": 1.0, "any_delay": 1.0})).stats
    for stats in (base, slow):
        _ints(stats, "resolve_ms", "connect_ms", "query_ms")
        total = stats["resolve_ms"] + stats["connect_ms"] + stats["query_ms"]
        assert total <= stats["duration_ms"] + 5, f"the steps overlap: {stats}"
    assert abs((slow["resolve_ms"] - base["resolve_ms"]) - 800) <= 150, (base, slow)
    # Control: the two untouched steps do not move (lookup time is not inside connect or query).
    assert abs(slow["connect_ms"] - base["connect_ms"]) <= 100, (base, slow)
    assert abs(slow["query_ms"] - base["query_ms"]) <= 100, (base, slow)


def test_km_400d_4_iii_deadline_miss_during_lookup_is_unavailable(tmp_path):
    # covers: KM-400d-4-iii
    # angle: criterion
    """A lookup blocked past the deadline is unavailable, and the warning text is unchanged."""
    run = run_retrieve(tmp_path, fake(v4_delay=BLOCK, any_delay=BLOCK), deadline_ms=2000)
    assert run.answer["status"] == "unavailable"
    assert "retrieval deadline reached" in run.answer["warnings"]


def test_km_400d_4_iii_lookup_miss_names_name_lookup_step_and_time_spent(tmp_path):
    # covers: KM-400d-4-iii
    # angle: discrimination
    """The miss is attributed to the name lookup with about 2000 ms spent in it."""
    run = run_retrieve(tmp_path, fake(v4_delay=BLOCK, any_delay=BLOCK), deadline_ms=2000)
    stats = run.stats
    assert stats.get("deadline_step") == "name lookup", stats
    _ints(stats, "resolve_ms")
    assert abs(stats["resolve_ms"] - 2000) <= 300, stats


def test_km_400d_4_iii_steps_not_reached_are_null_not_zero_after_lookup_miss(tmp_path):
    # covers: KM-400d-4-iii
    # angle: discrimination
    """After a lookup miss connect_ms and query_ms are present and null; never 0, never omitted."""
    stats = run_retrieve(tmp_path, fake(v4_delay=BLOCK, any_delay=BLOCK), deadline_ms=2000).stats
    for name in ("connect_ms", "query_ms"):
        assert name in stats, f"{name} omitted from stats: {sorted(stats)}"
        assert stats[name] is None, f"{name} must be null for a step never reached, got {stats[name]!r}"


def test_km_400d_4_iii_connect_miss_names_connect_step(tmp_path):
    # covers: KM-400d-4-iii
    # angle: discrimination
    """A stuck connect after a 0.05 s lookup is named "connect", not "name lookup"."""
    config = fake(v4_delay=0.05, any_delay=0.05, connect_delay=BLOCK)
    stats = run_retrieve(tmp_path, config, deadline_ms=2000).stats
    assert stats.get("deadline_step") == "connect", stats


def test_km_400d_4_iii_connect_miss_keeps_lookup_time_and_nulls_query_time(tmp_path):
    # covers: KM-400d-4-iii
    # angle: boundary
    """The finished lookup keeps its time (~50 ms); the query that never started is null."""
    config = fake(v4_delay=0.05, any_delay=0.05, connect_delay=BLOCK)
    stats = run_retrieve(tmp_path, config, deadline_ms=2000).stats
    _ints(stats, "resolve_ms")
    assert abs(stats["resolve_ms"] - 50) <= 100, stats
    assert "query_ms" in stats and stats["query_ms"] is None, stats


def test_km_400d_4_iii_query_miss_names_query_step(tmp_path):
    # covers: KM-400d-4-iii
    # angle: discrimination
    """A stuck query is named "query", not the earlier connect."""
    config = fake(v4_delay=0.05, any_delay=0.05, connect_delay=0.05, query_script=[BLOCK])
    stats = run_retrieve(tmp_path, config, deadline_ms=2000).stats
    assert stats.get("deadline_step") == "query", stats


def test_km_400d_4_iii_query_miss_keeps_lookup_and_connect_times(tmp_path):
    # covers: KM-400d-4-iii
    # angle: boundary
    """Lookup and connect times measured before the query started survive a query-step miss."""
    config = fake(v4_delay=0.1, any_delay=0.1, connect_delay=0.1, query_script=[BLOCK])
    stats = run_retrieve(tmp_path, config, deadline_ms=2000).stats
    _ints(stats, "resolve_ms", "connect_ms")
    assert abs(stats["resolve_ms"] - 100) <= 100, stats
    assert abs(stats["connect_ms"] - 100) <= 100, stats


def test_km_400d_4_iii_remembered_lookup_in_a_later_request_reports_zero_with_memory_flag(tmp_path):
    # covers: KM-400d-4-iii
    # angle: boundary
    """Request 1 measures its lookup; request 2 reuses the remembered address: 0 and the flag, not null."""
    results, _ = run_requests(tmp_path, 2, fake(**TIMED))
    first, second = results[0]["stats"], results[1]["stats"]
    assert first.get("resolve_from_memory") is False, first
    _ints(first, "resolve_ms")
    assert first["resolve_ms"] >= 100, first
    assert second.get("resolve_ms") == 0, second
    assert second.get("resolve_from_memory") is True, second


def test_km_400d_4_iii_step_fields_are_reachable_through_the_retrieve_cli(tmp_path):
    # covers: KM-400d-4-iii
    # angle: reachability
    """The real CLI prints the step fields and the printed JSON parses back as a result."""
    from knowledge.contracts import KnowledgeRetrievalResult

    run = run_retrieve(tmp_path, fake(**TIMED))
    assert run.returncode == 0
    assert run.answer["status"] == "ok"
    _ints(run.stats, "resolve_ms", "connect_ms", "query_ms")
    parsed = KnowledgeRetrievalResult.model_validate_json(run.stdout)
    assert parsed.stats["resolve_ms"] == run.stats["resolve_ms"]
    assert support.server_lookups(run), "the request never reached the adapter's lookup"
