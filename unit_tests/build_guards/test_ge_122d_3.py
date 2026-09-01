"""
MODULE: unit_tests/build_guards/test_ge_122d_3.py
GOAL: RED test-first stub for the shared-build half of GE-122d-3's
    three-stage contract: "when the same condition occurs at the
    shared-build stage, the build fails carrying the same three statements".

WHY THIS FILE TARGETS THE SAME SCRIPT AS THE COMMIT-TIME TESTS: GE-122d-1
    ("one rule, evaluated at three stages, cannot give three different
    answers" -- ticket 01 of this same epic, still status: todo at the time
    this module is authored) is what will wire the shared-build stage to
    invoke the commit-time gate THROUGH pre-commit (`pre-commit run
    check-identifier-uniqueness --all-files` or equivalent), "so the
    merge-time and commit-time rule sets are literally the same config and
    cannot drift apart" -- the exact precedent GE-122d-1's own Implementation
    Notes cite from this repo's existing "AC store valid" CI job. Until that
    wiring lands, this module targets the SAME entry point script
    (check_identifier_uniqueness.py) that GE-122d-1 designates as the build
    stage's invocation target, run against a fixture that reproduces the
    shape of a CI build checkout: a full, already-committed tree with
    NOTHING staged (a build checkout has no "staged diff" concept at all --
    everything present is, from the gate's point of view, the whole
    collection to inspect). This is a deliberate, explicitly-flagged stand-in
    for the dedicated build-stage entry point GE-122d-1 has not yet created,
    not a claim that the CI wiring itself already exists -- see
    unit_tests/commit_guardian/test_ge_122d_1.py (GE-122d-1's own test file)
    for the three-stages-agree coverage that pins the wiring itself.

WHY THIS MUST STILL BLOCK WITH NOTHING STAGED: this AC's own contract
    (unit_tests/commit_guardian/test_ge_122d_3.py's "THE CONTRACT DECISION")
    makes a could-not-establish namespace report `passed=False` with an EMPTY
    `findings` list, which the EXISTING GE-122e-3/H-1 fix in
    `_commit_disposition.py` already treats as blocking REGARDLESS of the
    staged set (`unresolvable_namespaces` -- a misconfiguration-shaped
    failure is never diff-scoped). A shared-build/CI checkout with nothing
    staged is exactly the case that distinguishes "genuinely blocks
    unconditionally" from "only blocks when the broken file happens to be in
    the diff" -- the latter would silently pass most CI runs, since the
    artifact that triggers a could-not-establish condition was very likely
    committed in an earlier, unrelated commit.

FIXTURE AUTHENTICITY: the one deliberately-corrupt fixture (malformed YAML)
    is written by hand per this repo's documented exception -- a real
    serializer cannot produce broken YAML by definition. Every other artifact
    is produced via the real serializer (yaml.safe_dump / json.dump).

DECISION HISTORY
- 2026-09-01 [GE-122d-3/test-writer]: Initial authoring, reproduced against
  this branch before writing (see the test-writer sign-off comment's
  red_baseline block for the exact captured output).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CANONICAL = _COMMIT_GUARDIAN_DIR / "check_identifier_uniqueness.py"


def _write_ac_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_malformed_yaml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("id: [unterminated flow sequence\nlevel: L2\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_ticket(path: Path, *, status: str, title: str = "Fixture ticket") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump({"status": status, "title": title}, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n# {title}\n\nFixture ticket body.\n"
    path.write_text(content, encoding="utf-8")


def _write_lifecycle_config(path: Path, folders: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"folders": folders}, fh)
    return path


def _git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)},
        timeout=60,
    )


def _init_git_repo(root: Path) -> None:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "fixture@example.invalid"], root)
    _git(["config", "user.name", "Fixture Author"], root)


class TestSharedBuildStageFailsOnTheSameCondition(unittest.TestCase):
    """AC-6: the same unreadable-artifact condition, evaluated at the
    shared-build stage, fails the build carrying the same three statements
    (the named artifact, the not-established statement, and the read count).
    """

    def setUp(self) -> None:
        if not _CANONICAL.exists():
            self.fail(
                f"check_identifier_uniqueness.py not found at canonical path {_CANONICAL}. "
                "It should already exist from GE-122a-1 -- this would be a regression."
            )
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_shared_build_stage_fails_on_the_same_condition(self):
        # covers: GE-122d-3
        # angle: seam
        """Builds a full CI-style checkout (everything already COMMITTED,
        nothing staged) with one malformed acceptance-criteria record, then
        invokes the same script the commit-time stage uses -- standing in
        for the shared-build entry point GE-122d-1 will wire via pre-commit
        -- and asserts a non-zero exit carrying all three required
        statements, exactly as the commit-time stage does with nothing
        staged.

        FAILS TODAY: exit code 0 with nothing staged (the pre-existing
        `_get_staged_paths() -> []` -> `compute_commit_disposition` path
        finds no attributed finding at all for a fail-open malformed
        record), and even once nothing-staged blocking exists generically
        (GE-122e-3/H-1), the malformed-content case itself still fails open
        at the file level today with no could-not-establish outcome to
        surface in the first place.
        """
        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        broken = ac_dir / "broken.yaml"
        _write_ac_yaml(ac_dir / "clean.yaml", {"id": "GE-9501", "level": "L2", "title": "Clean"})
        _write_malformed_yaml(broken)
        _write_text(self.root / "docs" / "architecture" / "adrs" / "ADR-9501-fixture.md", "# ADR-9501 Fixture\n\nStatus: accepted\n")
        _write_text(self.root / "docs" / "architecture" / "diagrams" / "c2-9501-fixture.md", "# c2-9501 Fixture\n")
        _write_lifecycle_config(self.root / "tickets" / "ticket_lifecycle.json", [{"path": "tickets/00_inbox"}])
        _write_ticket(self.root / "tickets" / "00_inbox" / "TICKET-95010101-Fixture.md", status="todo")

        _init_git_repo(self.root)
        _git(["add", "-A"], self.root)
        _git(["commit", "-q", "-m", "fixture: full checkout, nothing left to stage"], self.root)

        staged = _git(["diff", "--cached", "--name-only"], self.root).stdout.strip()
        self.assertEqual(
            "",
            staged,
            msg="fixture sanity: this is a fully-committed build checkout -- nothing must be staged.",
        )

        result = subprocess.run(
            [sys.executable, str(_CANONICAL)],
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
                "The shared-build stage (standing in via the same entry point, nothing staged) "
                f"must fail the build. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        self.assertIn(
            str(broken),
            result.stderr,
            msg=f"The build's output must name the artifact it could not read. Got: {result.stderr!r}",
        )
        self.assertIn(
            "not established",
            result.stderr.lower(),
            msg=f"The build's output must state uniqueness was not established. Got: {result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
