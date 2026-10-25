"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_fixture_layout
GOAL: Guard that no eval fixture under scripts/evals/sets/ is collectable by pytest.
Target: scripts/evals/sets/
"""

from __future__ import annotations

import fnmatch

import unit_tests.evals.tq200d4._helpers as h

COLLECTED = ("test_*.py", "*_test.py", "conftest.py")


def test_no_file_under_the_eval_sets_matches_pytests_collection_patterns():
    # covers: TQ-200d-4
    # angle: real_artifact
    """Anything that runs pytest over a tree containing scripts/ would collect these fixtures.

    CI shard 7 (suite_performance, TQ-600a-13) runs a child pytest in a temp root whose
    scripts/ is a symlink to the repo's scripts/; a fixture test such as
    ``.../tests/test_window_total.py`` imports a module that only resolves inside its own
    fixture project, so collection fails. Fixture tests must carry a non-collected name
    (for example the ``.py.recorded`` suffix the sets already use).
    """
    sets = h.SETS_DIR
    assert sets.is_dir(), f"{sets} does not exist"
    files = [p for p in sets.rglob("*") if p.is_file()]
    assert files, "control: the sets directory holds fixture files, so the scan sees something"
    hits = sorted(p.relative_to(h.REPO_ROOT).as_posix() for p in files if any(fnmatch.fnmatch(p.name, pat) for pat in COLLECTED))
    assert hits == [], f"pytest would collect these eval fixtures: {hits}"
