"""
MODULE: unit_tests/commit_guardian/_ge_127f_5_fixture.py
COVERS: GE-127f-5 (shared fixture module -- carries no tests of its own)

GOAL: Fixture builders for the descriptors that pin the length-refusal
    exemption: a declared location where the size standard still MEASURES and
    REPORTS a file's length but does not REFUSE the commit for it, because the
    remedy the standard prescribes (moving code into a smaller companion file)
    cannot be performed there at all.

WHY THE TWO ARMS DIFFER ONLY IN LOCATION. Every refusal arm here is built from
    the SAME content builder, the SAME extension, the SAME permitted length and
    the SAME staged change -- a 600-line file against a 400-line limit taking a
    5-for-5 replacement, which is GE-127f-2's own worked example and is refused
    today. The ONLY difference between the excused arm and the refused arm is
    the directory the file sits in. Any other difference would let an
    implementation pass the pair for a reason other than the one this record
    specifies.

WHY A SYNTHETIC LOCATION, NOT templates/workflows-js/. The behavioural
    descriptors declare their own location inside a disposable fixture repo, so
    they test the MECHANISM rather than the single entry that currently uses it
    -- an exemption hardcoded to the real path would pass a test written against
    the real path while being exactly the implementation GE-127f-5's
    it_requirements forbid. The real shipped entry is asserted separately, once,
    against the tracked artifact (see test_ge_127f_5_real_artifact.py).

REUSED, NOT REINVENTED. The git plumbing and the content builders come from
    _ge_127f_2_fixture (``function_lines``, ``replace_leading_lines``, the real
    -repo helpers); the production-module copier comes from
    _ge_127a_1_ordinary_commit_fixture. Only the config writer is new here,
    because no existing writer emits the exemption key.

DECISION HISTORY
- 2026-10-12 [GE-127f-5/test-writer]: Initial authoring.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127a_1_ordinary_commit_fixture as fx1  # noqa: E402
from _ge_127f_2_fixture import (  # noqa: E402
    commit_all,
    function_lines,
    init_repo,
    replace_leading_lines,
    stage_all,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_REAL_CONFIG = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 30

# GE-127f-2's own two pinned numbers, reused unchanged so the refused arm here
# is byte-for-byte the situation that record already refuses.
BASELINE_LENGTH = 600
PERMITTED_LENGTH = 400
ADDED_LINES = 5

# The disposable fixture's own declared location and the two paths that sit
# inside / outside it. UNSPLITTABLE_SIBLING shares the declared path as a
# string prefix but is a DIFFERENT directory -- the resemblance boundary.
DECLARED_LOCATION = "pkg/unsplittable/"
EXCUSED_PATH = "pkg/unsplittable/lane.py"
ORDINARY_PATH = "pkg/ordinary/lane.py"
RESEMBLING_PATH = "pkg/unsplittable-extra/lane.py"
DECLARED_REASON = "the engine gives this location no module loader, so the file cannot be split"


def write_config_json(
    root: Path,
    line_limit: int = PERMITTED_LENGTH,
    exemptions: list[dict[str, str]] | None = None,
) -> None:
    """Write a commit_guardian.json beside the copied gate script.

    config.py resolves its config path relative to its own ``__file__``, so
    this MUST sit beside the deployed script, never at the repo root.

    Args:
        root: The disposable fixture repo's root.
        line_limit: The permitted length for every checked kind.
        exemptions: The ``file_size.length_refusal_exemptions`` value. ``None``
            omits the key entirely (the shape a config predating this record
            has), which is deliberately distinct from an empty list.
    """
    file_size: dict[str, object] = {
        "line_limits": {".py": line_limit},
        "default_limit": line_limit,
        "checked_extensions": [".py"],
    }
    if exemptions is not None:
        file_size["length_refusal_exemptions"] = exemptions
    dest = root / "scripts" / "commit_guardian" / "commit_guardian.json"
    dest.write_text(json.dumps({"file_size": file_size}), encoding="utf-8")


def build_repo(root: Path, exemptions: list[dict[str, str]] | None = None) -> None:
    """Compose a disposable fixture repo carrying the real gate and *exemptions*."""
    fx1.copy_production_modules(root)
    write_config_json(root, exemptions=exemptions)
    init_repo(root)


def declared_entry(path: str = DECLARED_LOCATION, reason: str = DECLARED_REASON) -> dict[str, str]:
    """One ``length_refusal_exemptions`` entry, declared with a reason."""
    return {"path": path, "reason": reason}


def establish_oversized_baseline(root: Path, relpath: str) -> Path:
    """Commit *relpath* at BASELINE_LENGTH measured lines, already over the limit.

    Returns:
        The absolute path of the committed file.
    """
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(function_lines(BASELINE_LENGTH, tag="base"), encoding="utf-8")
    commit_all(root, f"establish oversized baseline at {relpath}")
    return target


def stage_addition(root: Path, relpath: str) -> None:
    """Stage a change into *relpath* that PUTS IN ADDED_LINES measured lines.

    A 5-for-5 replacement: the file's length does not move, but the change
    added five measured lines, so under GE-127f-2 the file is required to come
    back at BASELINE_LENGTH - ADDED_LINES and is refused where that rule
    applies.
    """
    target = root / relpath
    target.write_text(
        replace_leading_lines(target.read_text(encoding="utf-8"), ADDED_LINES, "new"),
        encoding="utf-8",
    )
    stage_all(root)


def run_check(root: Path) -> subprocess.CompletedProcess:
    """Invoke *root*'s own copy of the REAL check_file_size.py against staged content."""
    script = root / "scripts" / "commit_guardian" / "check_file_size.py"
    return subprocess.run(
        [_PYTHON, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def combined(result: subprocess.CompletedProcess) -> str:
    """The process's whole account of itself, both streams."""
    return f"{result.stdout}\n{result.stderr}"


# Matches an actual refusal block's banner, NOT the word "refus" wherever it
# appears -- the excused block legitimately contains "LENGTH REFUSAL EXCUSED"
# and "not refused", and a substring match on "refus" would read those as the
# very thing they announce is absent. Every refusal this module prints opens
# with "❌"; the excused block opens with a different marker by design.
_REFUSAL_MARKER_RE = re.compile(r"(?i)(❌|file too large|grew while)")


def assert_not_refused_for(testcase, result: subprocess.CompletedProcess, relpath: str) -> None:
    """Assert the run completed AND *relpath* is never named near a refusal marker.

    Exit 0 alone is not enough: a file named inside a refusal block while the
    run happens to exit 0 for unrelated reasons would satisfy a bare exit-code
    assertion and still be a refusal in the author's eyes.
    """
    testcase.assertEqual(
        0,
        result.returncode,
        msg=f"Expected the commit to complete. Got:\n{combined(result)}",
    )
    for marker in _REFUSAL_MARKER_RE.finditer(result.stdout):
        window = result.stdout[max(0, marker.start() - 200) : marker.end() + 200]
        testcase.assertNotIn(
            relpath,
            window,
            msg=f"{relpath} must not be named near a refusal marker. Got: {window!r}",
        )


def assert_refused_for(testcase, result: subprocess.CompletedProcess, relpath: str) -> None:
    """Assert the run refused, and that *relpath* is the file it named."""
    testcase.assertEqual(
        1,
        result.returncode,
        msg=f"Expected a refusal. Got:\n{combined(result)}",
    )
    testcase.assertIn(relpath, result.stdout, msg=f"The refusal must name {relpath}.")


def read_real_config() -> dict:
    """The tracked, shipped commit_guardian.json -- the published rule surface."""
    return json.loads(_REAL_CONFIG.read_text(encoding="utf-8"))
