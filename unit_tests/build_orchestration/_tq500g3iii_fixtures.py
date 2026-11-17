"""
MODULE: unit_tests/build_orchestration/_tq500g3iii_fixtures.py
GOAL: Shared REAL scratch git repos and CLI drivers for the TQ-500g-3-iii tests (the static assertion
    comparison inside consumer_sweep.py check, reached through wrong_version_gate.py finish).
BUSINESS CONTEXT: "Asserts less / compares looser / tolerates more than before the work" is decided from
    the code of each test at the base ref and in the working tree, so every fixture is a real git repo
    whose base commit holds real passing tests and whose working tree holds the work's edits. Lists
    go through the real record step as strengthened (so TQ-500g-3-i passes) and every test passes at
    the base and now (so TQ-500g-3-ii passes): only the loosened outcome decides.
ARCHITECTURE: Not a test file. Builds on _tq500g3i_fixtures / _tq500g3i_review_fixtures. Every
    scenario is read back through the real check CLI, so a red run is an assertion on the printed
    ``loosened`` list (``[]`` today), never an import or fixture error.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3i_review_fixtures as rfx

SCEN = "tests/test_retry.py"
HEADER = (
    "import pytest\nimport unittest\nfrom unittest import mock\n\nTOL = 0.01\nTOL2 = 0.1\n\n\n"
    "def compute_delay(n):\n    if n < 0:\n        raise ValueError('negative')\n    return n\n\n\n"
)
# The eleven tests of the criteria (F, G, H, K, I, L, J, then M, N, P, Q): name -> (source at the base, source after the work).
RETRY = {
    "test_backoff_caps_at_five": (
        "def test_backoff_caps_at_five():\n    delay, attempts, log = 5, 3, mock.Mock()\n    log('x')\n"
        "    assert delay == 5\n    assert attempts == 3\n    assert log.called\n",
        "def test_backoff_caps_at_five():\n    delay, attempts, log = 5, 3, mock.Mock()\n    log('x')\n"
        "    assert delay == 5\n    assert attempts == 3\n"),
    "test_first_delay": (
        "def test_first_delay():\n    delay = 1\n    assert delay == 1\n",
        "def test_first_delay():\n    delay = 1\n    assert delay >= 1\n"),
    "test_no_result": (
        "def test_no_result():\n    result = None\n    assert result is None\n",
        "def test_no_result():\n    result = None\n    assert result in (None, '')\n"),
    "test_ok_status": (
        "def test_ok_status():\n    response = mock.Mock(status=200)\n    assert response.status == 200\n",
        "def test_ok_status():\n    response = mock.Mock(status=200)\n    assert response.status\n"),
    "test_jitter_bounds": (
        "def test_jitter_bounds():\n    jitter = 0.5\n    assert jitter == pytest.approx(0.5, rel=0.01)\n",
        "def test_jitter_bounds():\n    jitter = 0.5\n    assert jitter == pytest.approx(0.5, rel=0.1)\n"),
    "test_rejects_negative_delay": (
        "def test_rejects_negative_delay():\n    with pytest.raises(ValueError):\n        compute_delay(-1)\n",
        "def test_rejects_negative_delay():\n    compute_delay(1)\n"),
    "test_retry_header": (
        "def test_retry_header():\n    header = 'Retry-After: 5'\n    assert header == 'Retry-After: 5'\n",
        "def test_retry_header():\n    header = 'Retry-After: 5'\n    assert header == 'Retry-After: 5'\n"
        "    assert '5' in header\n"),
    "test_retry_after_header": (
        "def test_retry_after_header():\n    header = 'Retry-After: 5'\n    assert header == 'Retry-After: 5'\n",
        "def test_retry_after_header():\n    header = 'Retry-After: 5'\n    if header:\n"
        "        assert header == 'Retry-After: 5'\n"),
    "test_backoff_resets": (
        "def test_backoff_resets():\n    retried, delay, attempts = True, 1, 0\n    assert delay == 1\n"
        "    assert attempts == 0\n",
        "def test_backoff_resets():\n    retried, delay, attempts = True, 1, 0\n    if not retried:\n"
        "        return\n    assert delay == 1\n    assert attempts == 0\n"),
    "test_parse_header": (
        "def test_parse_header():\n    raw, parsed = '5', '5'\n    if raw:\n        assert parsed == '5'\n",
        "def test_parse_header():\n    raw, parsed = 'Retry-After: 5', '5'\n    if raw:\n"
        "        assert parsed == '5'\n"),
    "test_retry_count": (
        "def test_retry_count():\n    attempts, log = 3, mock.Mock()\n    log('x')\n    assert attempts == 3\n",
        "def test_retry_count():\n    attempts, log = 3, mock.Mock()\n    log('x')\n    assert attempts == 3\n"
        "    if log.called:\n        assert log.call_count == 1\n"),
}
ALL_ELEVEN = tuple(RETRY)
# The eight items the criteria name (J, P, Q absent), in file order: file, then the test's line, then what.
EXPECTED_EIGHT = [
    (ALL_ELEVEN[0], "fewer assertions", "3 to 2"),
    (ALL_ELEVEN[1], "comparison loosened", "== became >="),
    (ALL_ELEVEN[2], "comparison loosened", "is became in"),
    (ALL_ELEVEN[3], "comparison loosened", "== removed"),
    (ALL_ELEVEN[4], "tolerance widened", "rel 0.01 to 0.1"),
    (ALL_ELEVEN[5], "fewer assertions", "1 to 0"),
    (ALL_ELEVEN[7], "assertion now conditional", "under if"),
    (ALL_ELEVEN[8], "assertion after an early return", "return"),
]


def body(sources: dict[str, tuple[str, str]], names: tuple[str, ...], side: int) -> str:
    """The test sources of *names* on one side (0 = base, 1 = after the work), blank-line separated."""
    return "\n\n".join(sources[n][side] for n in names)


def scenario(tmp: Path, base_body: str, now_body: str, listed: tuple[str, ...], *, rel: str = SCEN,
             header: str = HEADER, record: bool = True, others: dict[str, tuple[str, str]] | None = None) -> fx.Repo:
    """A repo with *base_body* committed in *rel* and *now_body* in the working tree; *listed* recorded as strengthened.

    *others* maps further paths to ``(base text, now text)``; entries for them are the caller's to record.
    """
    repo = fx.build(tmp, edits=(), add_new_file=False)
    fx.write(repo.path(rel), header + base_body)
    for path, (old, _new) in (others or {}).items():
        fx.write(repo.path(path), old)
    fx.gitfx.commit_all(repo.root, "base with the existing passing tests")
    fx.write(repo.path(rel), header + now_body)
    for path, (_old, new) in (others or {}).items():
        fx.write(repo.path(path), new)
    if record:
        fx.recorded(repo, [fx.entry(rel, t) for t in listed])
    return repo


def retry_repo(tmp: Path, listed: tuple[str, ...] = ALL_ELEVEN) -> fx.Repo:
    """The F-to-Q repo of the criteria: all eleven tests changed, *listed* recorded as strengthened."""
    names = ALL_ELEVEN
    return scenario(tmp, body(RETRY, names, 0), body(RETRY, names, 1), listed)


def run_check(repo: fx.Repo, env_extra: dict | None = None):
    """``consumer_sweep.py check`` with extra environment; return ``(proc, JSON)``."""
    return rfx.run_cli(repo, rfx.check_args(repo), env_extra=env_extra)


def loosened_of(repo: fx.Repo) -> list[dict]:
    """The loosened items of a check whose edit and run steps found nothing else to report."""
    proc, out = run_check(repo)
    fx.assert_check_shape(proc, out)
    assert out["unlisted"] == [] and out["weakened"] == [], ("not isolated to -iii", out)
    return out["loosened"]


def brief(items: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """``{test: [(what, detail), ...]}`` of loosened items, each carrying the pinned keys and this file."""
    out: dict[str, list[tuple[str, str]]] = {}
    for item in items:
        assert {"file", "test", "what", "detail"} <= set(item), item
        out.setdefault(item["test"], []).append((item["what"], item["detail"]))
    return out


def expected_eight_brief() -> dict[str, list[tuple[str, str]]]:
    return {t: [(w, d)] for t, w, d in EXPECTED_EIGHT}
