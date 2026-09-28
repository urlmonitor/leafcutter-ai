"""
MODULE: unit_tests/hooks/test_ge_122d_3.py
GOAL: RED test-first stub fixing the authoring-time half of GE-122d-3 --
    "when the same condition occurs at the authoring-time stage, the author
    is told the same three statements in-session, and the write they just
    made is not reverted".
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3.yaml
BUSINESS CONTEXT: this AC's own notes are explicit that the three stages are
    NOT uniform: commit-time BLOCKS, shared-build FAILS, but authoring-time
    only ANNOUNCES and must NOT revert the write the author just made
    ("Reverting an author's work over an unreadable file elsewhere in the
    collection punishes the wrong person, and the two later stages still
    hold the line."). GE-122d-1 already established, and
    unit_tests/commit_guardian/test_ge_122d_1_authoring_reachability.py
    already pins, that this stage's real, reachable entry point is
    ``templates/hooks/check_identifier_uniqueness_authoring.py``'s own
    ``main()`` -- a PostToolUse Edit|Write hook that reads a JSON payload on
    stdin (never argv) and delegates entirely to the SAME
    ``check_identifier_uniqueness.run_uniqueness_pass`` the commit-time and
    shared-build stages call, per that module's own ARCHITECTURE note ("This
    module therefore contains NO scanning logic of its own"). This test
    exercises that exact entry point -- real subprocess, real stdin payload,
    real files on disk -- never a direct call to
    ``evaluate_identifier_uniqueness`` and never a mock of the shared module.

THE SEAM UNDER TEST (Source-of-Truth Discipline Rule 3): the REAL producer
    (``check_identifier_uniqueness.run_uniqueness_pass``, loaded by the
    authoring hook itself via its own ``_load_shared_uniqueness_module``) is
    piped into the REAL consumer (the authoring hook's own PostToolUse
    ``main()``), and this test asserts the CONSUMER's observable behaviour --
    its exit code, its stderr message, and the on-disk state of the file the
    author just wrote -- not merely that the two modules can be imported
    together. GE-122d-3's own fix widens ``NamespaceVerdict`` at the
    producer; this is the test that proves the widening is actually visible
    all the way through the consumer's real session-facing behaviour, rather
    than merely asserted to be.

DOC_LINKS:
  - templates/hooks/check_identifier_uniqueness_authoring.py
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/settings.json
  - unit_tests/commit_guardian/test_ge_122d_1_authoring_reachability.py
  - unit_tests/commit_guardian/test_ge_122d_3.py

DECISION HISTORY:
  - 2026-09-07 [test-writer/GE-122d-3]: Created. Confirmed RED empirically:
    invoking templates/hooks/check_identifier_uniqueness_authoring.py as a
    real subprocess, fed the same PostToolUse stdin payload shape the real
    hook reads, against a fixture project root holding a genuinely malformed
    acceptance-criteria record, exits 0 (should block, exit 2) and its
    stderr contains no mention of the malformed artifact's filename, no
    "not established" statement, and no read count at all -- the
    authoring-time stage's own ``_build_block_message`` only ever lists
    ``contested_numbers`` and generic ``unresolvable_namespaces`` names
    today, neither of which this AC's could-not-establish shape populates
    yet (see unit_tests/commit_guardian/test_ge_122d_3.py's own "THE
    CONTRACT DECISION" for the NamespaceVerdict widening this depends on).
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
_AUTHORING_SRC = _REPO_ROOT / "templates" / "hooks" / "check_identifier_uniqueness_authoring.py"

_MALFORMED_YAML_CONTENT = "id: [unterminated flow collection\n  more: stuff\n"
_AUTHORED_FILE_CONTENT = "id: GE-9007\nlevel: L2\ntitle: The author's own new record\n"


def _write_ac_yaml(path: Path, data: dict) -> None:
    """Write a well-formed AC YAML fixture using the REAL serializer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def _write_malformed_yaml(path: Path) -> None:
    """Write a genuinely-unparsable YAML fixture (sanctioned Fixture
    Authenticity Rule exception)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_MALFORMED_YAML_CONTENT, encoding="utf-8")


class TestAuthoringStageAnnouncesWithoutRevertingTheWrite(unittest.TestCase):
    """Real subprocess invocation of the real authoring-time PostToolUse
    entry point, fed a real stdin payload, against a real fixture project
    root -- never a direct call to evaluate_identifier_uniqueness()."""

    def setUp(self) -> None:
        if not _AUTHORING_SRC.exists():
            self.fail(f"{_AUTHORING_SRC} not found -- should already exist from GE-122d-1.")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        # A project-root marker so _find_project_root's ancestor walk
        # terminates at self.root (mirrors ticket_frontmatter_guard.py's own
        # marker list, which check_identifier_uniqueness_authoring.py reuses).
        (self.root / "CLAUDE.md").write_text("Fixture project marker.\n", encoding="utf-8")

    def test_authoring_stage_announces_without_reverting_the_write(self) -> None:
        # covers: GE-122d-3
        # angle: seam
        """The author just wrote a NEW, well-formed AC record
        (``authored_path``) via a real Edit/Write tool call. Elsewhere in
        the SAME collection, an UNRELATED record is genuinely malformed
        (pre-existing, not touched by this Edit/Write). The real PostToolUse
        hook, invoked exactly as templates/settings.json wires it (stdin
        JSON naming the edited file's own path, no argv), must:

          1. Exit 2 (block, per this directory's PostToolUse "exit 2 = block
             with content" convention) -- announcing the problem in-session.
          2. Print, to stderr, the malformed artifact's filename, a
             not-established statement, and the namespace's read count --
             the same three statements the commit-time and shared-build
             stages must carry.
          3. NEVER revert or alter the author's own just-written file: it
             must still exist on disk with EXACTLY the content the author
             wrote, since GE-122d-3's own notes are explicit that punishing
             the author for an unrelated pre-existing defect elsewhere in
             the collection is the wrong disposition for this stage alone.

        FAILS TODAY: the process exits 0 (does not block at all), and even
        setting that aside, its block-message builder
        (``_build_block_message``) has no code path that would ever print
        the malformed filename, a not-established statement, or a read
        count -- see this module's own DECISION HISTORY for the exact
        reproduction.
        """
        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        _write_ac_yaml(ac_dir / "GE-9001-ok.yaml", {"id": "GE-9001", "level": "L2", "title": "Pre-existing fixture AC"})
        _write_malformed_yaml(ac_dir / "GE-9002-malformed.yaml")
        (self.root / "docs" / "architecture" / "adrs").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "architecture" / "diagrams").mkdir(parents=True, exist_ok=True)
        tickets_root = self.root / "tickets"
        tickets_root.mkdir(parents=True, exist_ok=True)
        (tickets_root / "ticket_lifecycle.json").write_text('{"folders": []}', encoding="utf-8")

        # The author's OWN new write -- this is the file the PostToolUse
        # event names, and the one that must survive on disk untouched.
        authored_path = ac_dir / "GE-9007-authored.yaml"
        authored_path.write_text(_AUTHORED_FILE_CONTENT, encoding="utf-8")

        payload = json.dumps({"tool_input": {"file_path": str(authored_path)}})

        result = subprocess.run(
            [sys.executable, str(_AUTHORING_SRC)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(
            2,
            result.returncode,
            msg=(
                "The authoring-time hook must exit 2 (block/announce) when the collection "
                f"holds a malformed record. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        self.assertIn(
            "GE-9002-malformed.yaml",
            result.stderr,
            msg=f"The in-session message must name the malformed artifact. Got: {result.stderr!r}",
        )
        self.assertIn(
            "2 inspected",
            result.stderr,
            msg=f"The in-session message must state the namespace's read count. Got: {result.stderr!r}",
        )

        self.assertTrue(authored_path.exists(), msg="The author's own just-written file must NOT be reverted (must still exist).")
        self.assertEqual(
            authored_path.read_text(encoding="utf-8"),
            _AUTHORED_FILE_CONTENT,
            msg="The author's own just-written file must NOT be altered -- exact original content must survive.",
        )


if __name__ == "__main__":
    unittest.main()
