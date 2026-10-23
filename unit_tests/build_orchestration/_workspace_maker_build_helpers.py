"""
MODULE: unit_tests/build_orchestration/_workspace_maker_build_helpers.py
GOAL: Generate the stub scripts/build.py source (and its real accept/reject
    git pre-commit hook) that _workspace_maker_fixtures.make_project() writes
    into every fixture project it builds.
BUSINESS CONTEXT: BO-4300f-4's own Implementation Notes ("BUILDERS") require
    a stub build entry point that installs a real hook in well under a
    second for every fixture project the shared locator's proofs build --
    never the package's own scripts/build.py (CLAUDE.md "Tests must not
    spawn their own build.py"). The reject/accept switch lets later
    BO-4300 tickets (e.g. the discard-token family) build a fixture project
    whose hook never blocks a commit, without hand-rolling a second stub.
ARCHITECTURE: Pure string templating, no I/O of its own. Split out of
    _workspace_maker_fixtures.py to keep that module under the package's
    400-line file-size ratchet -- the build_phases.py / build_helpers.py
    split precedent this ticket's own "File-Size Limit" note points to.

NOT a test file itself (leading underscore). Nothing in here is collected
by pytest.
"""
from __future__ import annotations

import json
from pathlib import Path

# The sentinel a REJECT-mode hook refuses. Distinct from
# _bo_4300a_1_fixtures.REJECT_SENTINEL (BO-4300a-1's own fixture module) so
# a test that accidentally mixes the two fixture families gets a visibly
# different string, never a silent false pass.
REJECT_SENTINEL = "BO4300F4_REJECT_SENTINEL"

_HOOK_BODIES: dict[str, str] = {
    "reject": (
        "#!/usr/bin/env python\n"
        "import subprocess, sys\n"
        "diff = subprocess.run(\n"
        "    ['git', 'diff', '--cached'], capture_output=True, text=True,\n"
        ").stdout\n"
        f"if {REJECT_SENTINEL!r} in diff:\n"
        f"    print('PRECOMMIT_CANARY_REJECTED rejected by stub hook: {REJECT_SENTINEL}')\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n"
    ),
    "accept": (
        "#!/usr/bin/env python\n"
        "import sys\n"
        "sys.exit(0)\n"
    ),
}


_PRE_COMMIT_CONFIG = """repos:
  - repo: local
    hooks:
      - id: stub-reject
        name: stub-reject
        entry: 'true'
        language: system
        stages: [pre-commit]
"""


def write_hook_declarations(root: Path, sentinel: str = REJECT_SENTINEL) -> None:
    """Write, into a fixture project root, what the maker's readiness proof reads.

    A ``.pre-commit-config.yaml`` declaring the pre-commit stage, and the
    install's ``scripts/commit_guardian/commit_guardian.json`` ``stage_canaries``
    entry naming a known-bad file (carrying *sentinel*) that the stub rejecting
    hook refuses. Without both the maker answers HOOKS_INACTIVE.
    """
    (root / ".pre-commit-config.yaml").write_text(_PRE_COMMIT_CONFIG, encoding="utf-8")
    guardian = root / "scripts" / "commit_guardian"
    guardian.mkdir(parents=True, exist_ok=True)
    declared = {"stage_canaries": {"pre-commit": {"path": "canary_bad.txt", "content": sentinel + "\n"}}}
    (guardian / "commit_guardian.json").write_text(json.dumps(declared, indent=2) + "\n", encoding="utf-8")


def stub_build_py_source(hook_mode: str = "reject") -> str:
    """Return the source text for a fixture project's own tiny scripts/build.py.

    Never the real leafcutter scripts/build.py. Writes INSTALLED_MARKER.txt
    stamped from the project's own BUILD_STAMP.txt (proving the install ran
    "from its own contents", mirroring the established
    _bo_4300a_1_fixtures._stub_build_py_source precedent) and installs a
    real git pre-commit hook: rejecting (default) or always-accepting, per
    *hook_mode*, decided once at fixture-build time -- never re-decided at
    hook-run time.

    Args:
        hook_mode: ``"reject"`` (default) or ``"accept"``.

    Returns:
        The stub build.py module source, ready to be written to a fixture
        project's ``scripts/build.py``.

    Raises:
        ValueError: *hook_mode* is neither ``"reject"`` nor ``"accept"``.
    """
    if hook_mode not in _HOOK_BODIES:
        msg = f"stub_build_py_source: hook_mode must be 'reject' or 'accept', got {hook_mode!r}"
        raise ValueError(msg)
    hook_body = _HOOK_BODIES[hook_mode]
    return f'''"""Stub build entry point for a BO-4300f-4 shared fixture project.

Never the real leafcutter scripts/build.py -- a fixture-only stand-in per
this ticket's own Implementation Notes ("BUILDERS: ... a stub build entry
point that installs a real rejecting hook in well under a second").
"""
import argparse
import os
import stat
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--config-path", default=None)
    args = parser.parse_args()

    target = Path(args.target_dir)
    own_root = Path(__file__).resolve().parent.parent
    stamp = (own_root / "BUILD_STAMP.txt").read_text(encoding="utf-8").strip()

    (target / "INSTALLED_MARKER.txt").write_text(
        f"installed-from-stamp:{{stamp}}\\n", encoding="utf-8"
    )

    hooks_dir = target / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text(
{hook_body!r},
        encoding="utf-8",
    )
    st = os.stat(hook_path)
    os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print("stub build complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-28 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02]:
#   Created this module to hold make_project()'s stub-build/hook source
#   templating, split out of _workspace_maker_fixtures.py to keep that
#   module under the 400-line file-size ratchet. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02)
# ===========================================================================
