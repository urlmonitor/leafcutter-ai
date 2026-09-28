"""
MODULE: unit_tests/build_guards/test_ge_122d_3.py
GOAL: RED test-first stub fixing the shared-build half of GE-122d-3 -- "when
    the same condition occurs at the shared-build stage, the build fails
    carrying the same three statements".
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3.yaml
BUSINESS CONTEXT: GE-122d-1 already established, and
    unit_tests/build_guards/test_ge_122d_1_build_stage_parity.py already
    pins, that the shared-build stage for this whole numbering rule is NOT a
    second, independently-maintained invocation -- CI runs
    ``pre-commit run check-identifier-uniqueness``, which resolves through
    the exact same ``.pre-commit-config.yaml`` entry the commit-time stage
    uses:

        entry: python .leafcutter/scripts/commit_guardian/run_hook.py
               .leafcutter/scripts/commit_guardian/check_identifier_uniqueness.py

    Because the shared-build stage is, by GE-122d-1's own design, the SAME
    hook invoked through a different runner (``run_hook.py`` rather than
    pre-commit's git-staged-file plumbing directly), this test exercises
    THAT exact entry -- never a second, hand-rolled invocation of the
    numbering rule -- against a fixture "build checkout" containing the same
    genuinely-malformed record GE-122d-3's commit-time tests use
    (unit_tests/commit_guardian/test_ge_122d_3.py). Since GE-122d-3's own
    fix widens ``NamespaceVerdict`` (see that module's own "THE CONTRACT
    DECISION"), and ``run_hook.py`` performs no filtering of its own (it
    only resolves which Python interpreter to delegate to and forwards
    argv verbatim), a fix at the shared module level is automatically
    visible through this exact entry point with no separate build-stage
    logic to maintain -- this test is what proves that is actually true,
    rather than merely asserted.

ARCHITECTURE: Reads the REAL, tracked ``.pre-commit-config.yaml`` entry for
    ``check-identifier-uniqueness`` to derive the exact entry command
    (rather than hardcoding a guess at it, which could silently drift from
    the real config), splits it into its two script paths, and invokes it
    as a real subprocess against a from-scratch git-fixture "build checkout"
    -- never a mock of git, never a direct call to check_identifier_uniqueness's
    own main() or run_uniqueness_pass.

DOC_LINKS:
  - .pre-commit-config.yaml
  - templates/scripts/commit_guardian/run_hook.py
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - unit_tests/commit_guardian/test_ge_122d_3.py
  - unit_tests/build_guards/test_ge_122d_1_build_stage_parity.py

DECISION HISTORY:
  - 2026-09-07 [test-writer/GE-122d-3]: Created. Confirmed RED empirically:
    running the exact ``.pre-commit-config.yaml`` entry command (via
    run_hook.py, which simply resolves an interpreter and forwards argv) as
    a subprocess against a fixture git checkout with a genuinely malformed
    acceptance-criteria record exits 0 and stderr contains no mention of the
    malformed artifact's filename at all -- the same defect
    unit_tests/commit_guardian/test_ge_122d_3.py pins at the commit-time
    stage, now confirmed to reach the shared-build entry point unchanged
    (as GE-122d-1's own "one rule, one config" design predicts it must).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRECOMMIT_CONFIG = _REPO_ROOT / ".pre-commit-config.yaml"
_HOOK_ID = "check-identifier-uniqueness"

_MALFORMED_YAML_CONTENT = "id: [unterminated flow collection\n  more: stuff\n"


def _resolve_real_entry_scripts() -> tuple[Path, Path]:
    """Read the REAL, tracked pre-commit entry for check-identifier-uniqueness
    and resolve both script paths it names, relative to the repo root.

    Deliberately does not hardcode a guess at the entry command -- reading it
    from the tracked config means a future change to the entry (a different
    wrapper, a different relative path) is reflected here automatically
    rather than silently drifting out of sync with what the real shared-build
    stage actually runs.

    Returns:
        (run_hook_path, check_identifier_uniqueness_path) -- both resolved
        against _REPO_ROOT, since the entry's relative paths
        (``.leafcutter/scripts/...``) describe the DEPLOYED layout, and this
        repo's own root also carries a populated ``.leafcutter/`` deploy
        (ADR-001: templates/ is canonical, .leafcutter/ is the build output
        this repo self-hosts against).

    Raises:
        AssertionError: if the hook id is missing, or its entry does not
            name exactly the two script arguments this function expects --
            surfaced as a clear test failure rather than an opaque crash.
    """
    config = yaml.safe_load(_PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == _HOOK_ID:
                entry = hook["entry"]
                parts = entry.split()
                # entry shape: "python <run_hook.py path> <check_identifier_uniqueness.py path>"
                assert len(parts) == 3 and parts[0] == "python", (
                    f"Unexpected entry shape for {_HOOK_ID!r}: {entry!r}. "
                    "Expected 'python <run_hook.py> <check_identifier_uniqueness.py>'."
                )
                return _REPO_ROOT / parts[1], _REPO_ROOT / parts[2]
    raise AssertionError(f"{_HOOK_ID!r} not found in {_PRECOMMIT_CONFIG}.")


def _write_ac_yaml(path: Path, data: dict) -> None:
    """Write a well-formed AC YAML fixture using the REAL serializer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_malformed_yaml(path: Path) -> None:
    """Write a genuinely-unparsable YAML fixture (sanctioned Fixture
    Authenticity Rule exception -- see unit_tests/commit_guardian/test_ge_122d_3.py's
    own module docstring for the full rationale)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_MALFORMED_YAML_CONTENT, encoding="utf-8")


class TestSharedBuildStageFailsOnTheSameCondition(unittest.TestCase):
    """The shared-build stage, exercised through its REAL, tracked entry
    point -- never a second, hand-rolled invocation of the numbering rule."""

    def setUp(self) -> None:
        self.run_hook_path, self.canonical_path = _resolve_real_entry_scripts()
        for path, label in ((self.run_hook_path, "run_hook.py"), (self.canonical_path, "check_identifier_uniqueness.py")):
            if not path.exists():
                self.fail(
                    f"The real pre-commit entry for {_HOOK_ID!r} names {label} at {path}, "
                    "which does not exist on disk -- this repo's own .leafcutter/ deploy is "
                    "stale or was never built (run build.py) before this test."
                )

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _git(self, args: list, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)},
            timeout=60,
        )

    def test_shared_build_stage_fails_on_the_same_condition(self) -> None:
        # covers: GE-122d-3
        # angle: reachability
        """A fixture 'build checkout' with a genuinely malformed
        acceptance-criteria record must make the REAL shared-build entry
        (the exact .pre-commit-config.yaml ``check-identifier-uniqueness``
        command, run via ``run_hook.py`` exactly as CI's own
        ``pre-commit run check-identifier-uniqueness`` step resolves it)
        fail, carrying the same three statements the commit-time stage must
        carry: the named artifact, the not-established statement (via the
        FAILED/BLOCKING report lines), and the read count.

        FAILS TODAY: the process exits 0 and stderr never names the
        malformed artifact at all -- see this module's own DECISION HISTORY
        for the exact reproduction.
        """
        self._git(["init", "-q"], self.root)
        self._git(["config", "user.email", "fixture@example.invalid"], self.root)
        self._git(["config", "user.name", "Fixture Author"], self.root)

        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        _write_ac_yaml(ac_dir / "GE-9001-ok.yaml", {"id": "GE-9001", "level": "L2", "title": "Fixture AC"})
        _write_malformed_yaml(ac_dir / "GE-9002-malformed.yaml")
        (self.root / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
        tickets_root = self.root / "tickets"
        tickets_root.mkdir(parents=True, exist_ok=True)
        (tickets_root / "ticket_lifecycle.json").write_text('{"folders": []}', encoding="utf-8")
        (self.root / "README.md").write_text("Fixture build checkout for GE-122d-3.\n", encoding="utf-8")
        self._git(["add", "README.md"], self.root)

        result = subprocess.run(
            [sys.executable, str(self.run_hook_path), str(self.canonical_path)],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(self.root)},
            timeout=60,
        )

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The real shared-build entry must exit non-zero (the build fails) when a "
                f"namespace holds an unparsable record. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        self.assertIn(
            "GE-9002-malformed.yaml",
            result.stderr,
            msg=f"The build's stderr must name the malformed artifact. Got: {result.stderr!r}",
        )
        self.assertIn(
            "2 inspected",
            result.stderr,
            msg=f"The build's stderr must state the attempted read count. Got: {result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
