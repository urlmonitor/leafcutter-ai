"""
MODULE: unit_tests/scripts/test_bo4500b_2_deployed_layout.py
GOAL: BO-4500b-2 - the identity check run on the REAL deployed layout with the REAL build config
    (the shared reference build, never a build.py of its own: TQ-600a).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo4500b2_support as T  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]  # the package source the shared layout was built from
REQUIRED_CONSUMERS = (
    "build-feature.js", "build-ticket.js", "quick-fix.js",
    "plan-feature.js", "fast-lane-ship.js", "finalize-feature.js",
)


def _real_config(package_root: Path, layout: Path) -> dict:
    """The config the real build used: load_config plus the two values build.py injects."""
    import build

    config = build.load_config(None, layout)
    build._inject_file_size_limits(config, package_root)
    build._inject_changelogs_dir(config, package_root)
    return config


@pytest.mark.shared_layout_reader
def test_every_deployed_copy_of_every_shared_block_matches_its_source(shared_reference_layout):
    # covers: BO-4500b-2
    # covers: BO-4500b
    # angle: deployed
    """Wrong version caught: a check that passes by inspecting nothing, or a deployed consumer
    of WORKSPACE-ANSWER that is skipped. Also the parent promise (BO-4500b): one source, every
    deployed route carrying it identical."""
    from shared_block_identity import check_identity

    layout = Path(shared_reference_layout)
    result = check_identity(layout / ".leafcutter", REPO_ROOT, _real_config(REPO_ROOT, layout))
    assert result["passed"] is True, result["message"]
    assert result["inspected_total"] > 0
    matched = {m["block"]: m for m in result["matched"]}
    assert "WORKSPACE-ANSWER" in matched
    carriers = {r.rsplit("/", 1)[-1] for r in matched["WORKSPACE-ANSWER"]["routes"]}
    assert set(REQUIRED_CONSUMERS) <= carriers, carriers
    assert matched["WORKSPACE-ANSWER"]["inspected"] >= len(REQUIRED_CONSUMERS)
    assert T.CONFIG  # support module imported for the shared contract
