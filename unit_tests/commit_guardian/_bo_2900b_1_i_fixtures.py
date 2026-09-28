"""
MODULE: unit_tests/commit_guardian/_bo_2900b_1_i_fixtures.py
GOAL: Shared real-artifact fixture builders for BO-2900b-1-i ("A capability
    introduced together with its caller passes; one introduced alone is
    refused with both ways forward named").

Not a test file itself (does not match test_*.py) so pytest never collects it
directly.

DESIGN NOTE (test-writer, 2026-09-25): this AC's own it_requirements.constraints
say it "adds no new refusal cause and no second code path -- it constrains
the content of the existing one and asserts the passing case", reusing
BO-2900b-1's finding record and message path verbatim. So this fixture module
mirrors _bo_2900b_1_fixtures.py's own surface/automation fixture shape
exactly (a real, on-disk, importable fixture surface module built via a
zero-arg `build_parser()` callable, and a real fixture automation script that
invokes the surface via `subprocess.run([sys.executable, _SURFACE,
"<capability>"], ...)`, the exact call shape
_reachability_invocation_collector.collected_invocations() recognises) --
only the capability name (`verify`, per this AC's own Gherkin literally)
differs from the sibling fixtures.

THE ADOPTION-TRAP SHAPE: `write_fixture_surface_with_verify` always registers
both `claim` and `verify`. Two automation fixtures exist against the SAME
surface: one invokes both (the same-change-adoption / passing case), the
other invokes only `claim` (`verify` lands with no caller -- the refusing
case). Both automation fixtures are written into a fresh temp directory per
test via `fixture_tmp_dir()`/`run_check_reachability()`, imported from the
sibling `_bo_2900b_1_fixtures` module rather than duplicated here -- there is
exactly one tmp-dir helper and one subprocess-dispatch helper for this whole
AC family.
"""
from __future__ import annotations

from pathlib import Path

_FIXTURE_SURFACE_WITH_VERIFY = '''"""Fixture command surface: registers claim and verify.

Mirrors BO-2900b-1-i's own Gherkin literally -- a surface that registers a
new capability `verify` alongside an existing `claim` capability.
"""
import argparse


def build_parser() -> argparse.ArgumentParser:
    """Return the built argparse parser -- the ONLY source of truth for what
    this surface registers (never source-scan this file's text)."""
    parser = argparse.ArgumentParser(prog="fixture-surface-verify")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("claim")
    sub.add_parser("verify")
    return parser


if __name__ == "__main__":
    build_parser().parse_args()
'''

_FIXTURE_AUTOMATION_CALLS_CLAIM_AND_VERIFY = '''"""Fixture automation script: invokes BOTH claim and verify against the
fixture surface -- the same-change adoption case, where the capability and
its automation caller land together.
"""
import subprocess
import sys
from pathlib import Path

_SURFACE = str(Path(__file__).resolve().parent / "fixture_surface_with_verify.py")


def run_build() -> None:
    """Invoke claim and verify in sequence."""
    subprocess.run([sys.executable, _SURFACE, "claim"], check=False)
    subprocess.run([sys.executable, _SURFACE, "verify"], check=False)
'''

_FIXTURE_AUTOMATION_CALLS_CLAIM_ONLY = '''"""Fixture automation script: invokes only claim against the fixture surface.
"verify" is deliberately never invoked anywhere in this file -- the
capability-introduced-alone refusal case.
"""
import subprocess
import sys
from pathlib import Path

_SURFACE = str(Path(__file__).resolve().parent / "fixture_surface_with_verify.py")


def run_build() -> None:
    """Invoke only claim."""
    subprocess.run([sys.executable, _SURFACE, "claim"], check=False)
'''


def write_fixture_surface_with_verify(src_dir: Path) -> Path:
    """Write the real, on-disk, importable fixture surface module
    (claim/verify) via a verbatim on-disk file -- never a hand-typed
    in-memory literal the test body constructs at assertion time."""
    src_dir.mkdir(parents=True, exist_ok=True)
    path = src_dir / "fixture_surface_with_verify.py"
    path.write_text(_FIXTURE_SURFACE_WITH_VERIFY, encoding="utf-8")
    return path


def write_fixture_automation_calls_claim_and_verify(automation_dir: Path) -> Path:
    """Write the fixture automation script that invokes both claim and verify
    -- the same-change adoption (passing) case."""
    automation_dir.mkdir(parents=True, exist_ok=True)
    path = automation_dir / "fixture_automation_calls_claim_and_verify.py"
    path.write_text(_FIXTURE_AUTOMATION_CALLS_CLAIM_AND_VERIFY, encoding="utf-8")
    return path


def write_fixture_automation_calls_claim_only(automation_dir: Path) -> Path:
    """Write the fixture automation script that invokes only claim -- verify
    lands with no automation caller, the refusing case."""
    automation_dir.mkdir(parents=True, exist_ok=True)
    path = automation_dir / "fixture_automation_calls_claim_only.py"
    path.write_text(_FIXTURE_AUTOMATION_CALLS_CLAIM_ONLY, encoding="utf-8")
    return path
