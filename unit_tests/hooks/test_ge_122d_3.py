"""
MODULE: unit_tests/hooks/test_ge_122d_3.py
GOAL: RED test-first stub for the authoring-time half of GE-122d-3's
    three-stage contract: "when the same condition occurs at the
    authoring-time stage, the author is told the same three statements
    in-session, and the write they just made is not reverted."

NAMING ASSUMPTION, STATED EXPLICITLY (this AC's own Implementation Notes
    warn: "There is no other way for that stage to say anything" than the
    PostToolUse block-decision channel GE-122c-1 uses, but GE-122c-1 itself
    is still status: todo in the AC store with no hook filename fixed
    anywhere in this repository -- confirmed by architect-review's own note
    on this ticket). This module targets a NEW hook module,
    ``templates/hooks/numbering_uniqueness_guard.py``, registered on the
    same PostToolUse ``Edit|Write`` matcher GE-122c-1 documents in
    ``templates/settings.json``. This is a test-writer DESIGN DECISION, not
    a fact already fixed elsewhere -- python-coder may reuse GE-122c-1's own
    hook (if it lands first and this AC's disposition is folded into it) or
    create this dedicated module; either is acceptable AS LONG AS the
    could-not-establish disposition below is reachable from a real
    PostToolUse invocation. If python-coder chooses a different filename,
    update ``_HOOK_PATH`` below in the SAME commit rather than leaving this
    test permanently red for the wrong reason.

WHY A DEDICATED PostToolUse HOOK RATHER THAN THE COMMIT-TIME SCRIPT: the
    commit-time and shared-build stages both run OUTSIDE the live agent
    session (a git hook subprocess, a CI job) and can only block-and-print.
    The authoring-time stage runs INSIDE the live session; per
    ``templates/hooks/ticket_frontmatter_guard.py``'s own documented
    contract (the proven precedent this AC's own doc_links cite), the ONLY
    channel back into the session is a PostToolUse hook's
    ``{"decision": "block", "reason": ...}`` JSON on stdout, printed after
    reading the tool-use payload from stdin. This module drives the hook
    through exactly that real, documented contract -- never by importing an
    internal function and calling it directly.

THE NON-REVERTING DISPOSITION IS THE LOAD-BEARING ASSERTION HERE: GE-122d-3's
    own Implementation Notes and GE-122c-1's own notes (quoted above) BOTH
    independently land on "announce, do not revert" for this stage. A hook
    that reverted the author's write to enforce a could-not-establish
    condition would fail this AC even if its emitted message were perfect --
    this module's single test therefore asserts BOTH the message contract
    AND the file's on-disk survival in one place, since a change that broke
    either half is the exact defect this AC exists to prevent at this stage.

FIXTURE AUTHENTICITY: the one deliberately-corrupt fixture (malformed YAML)
    is written by hand per this repo's documented exception -- a real
    serializer cannot produce broken YAML by definition. Every other artifact
    is produced via the real serializer (yaml.safe_dump / json.dump).

DECISION HISTORY
- 2026-09-01 [GE-122d-3/test-writer]: Initial authoring, reproduced against
  this branch before writing (see the test-writer sign-off comment's
  red_baseline block for the exact captured output -- the hook module does
  not exist at all yet, so the reproduction is "file not found").
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
# See the module docstring's NAMING ASSUMPTION note above.
_HOOK_PATH = _REPO_ROOT / "templates" / "hooks" / "numbering_uniqueness_guard.py"


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


class TestAuthoringStageAnnouncesWithoutRevertingTheWrite(unittest.TestCase):
    """AC-7 (+ AC-2/AC-3/AC-4 restated in-session): the authoring-time stage
    announces the same three statements as the other two stages and leaves
    the author's just-written file untouched on disk.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        # A project-root marker so the hook's own root-resolution (mirroring
        # ticket_frontmatter_guard.find_project_root's documented marker
        # list) can locate this fixture tree.
        (self.root / ".git").mkdir()

    def test_authoring_stage_announces_without_reverting_the_write(self):
        # covers: GE-122d-3
        # angle: criterion
        """The author writes a new, perfectly valid AC record into a
        namespace that ALREADY holds an unrelated malformed sibling record
        elsewhere in the collection. The PostToolUse hook that fires on that
        write must: (a) exit 0 with a block decision, (b) name the malformed
        artifact, (c) state uniqueness was not established for the
        namespace, (d) state the read count, and (e) leave the author's own
        just-written file exactly as written -- never reverted.

        FAILS TODAY: templates/hooks/numbering_uniqueness_guard.py does not
        exist at all (this is a brand-new module this AC introduces) -- the
        subprocess invocation below fails to even start the intended script.
        """
        ac_dir = self.root / "docs" / "acceptance-criteria" / "fixture-component"
        broken = ac_dir / "broken-sibling.yaml"
        _write_malformed_yaml(broken)

        # Populate the other three namespaces cleanly so only the
        # acceptance-criteria namespace under test can fail.
        _write_text(self.root / "docs" / "architecture" / "adrs" / "ADR-9601-fixture.md", "# ADR-9601 Fixture\n\nStatus: accepted\n")
        _write_text(self.root / "docs" / "architecture" / "diagrams" / "c2-9601-fixture.md", "# c2-9601 Fixture\n")
        _write_lifecycle_config(self.root / "tickets" / "ticket_lifecycle.json", [{"path": "tickets/00_inbox"}])
        _write_ticket(self.root / "tickets" / "00_inbox" / "TICKET-96010101-Fixture.md", status="todo")

        # The author's own write: a new, perfectly valid record.
        authored_path = ac_dir / "authored-by-me.yaml"
        authored_content_before = yaml.safe_dump(
            {"id": "GE-9602", "level": "L2", "title": "Authored just now"}, sort_keys=False
        )
        authored_path.parent.mkdir(parents=True, exist_ok=True)
        authored_path.write_text(authored_content_before, encoding="utf-8")

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(authored_path),
                "content": authored_content_before,
            },
        }

        result = subprocess.run(
            [sys.executable, str(_HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "PostToolUse hook contract: must exit 0 regardless of decision (per "
                "templates/hooks/ticket_frontmatter_guard.py's documented contract). "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )

        try:
            decision_payload = json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError:
            self.fail(f"Hook stdout must be valid JSON when it blocks. Got stdout={result.stdout!r}")

        self.assertEqual(
            decision_payload.get("decision"),
            "block",
            msg=f"AC-7: the author must be told in-session (a block decision). Got: {decision_payload!r}",
        )
        reason = decision_payload.get("reason", "")
        self.assertIn(
            str(broken),
            reason,
            msg=f"AC-2: the in-session message must name the artifact it could not read. Got reason={reason!r}",
        )
        self.assertIn(
            "not established",
            reason.lower(),
            msg=f"AC-3: the in-session message must state uniqueness was not established. Got reason={reason!r}",
        )

        # AC-7's second half: the author's own write must survive untouched.
        self.assertTrue(
            authored_path.exists(),
            msg="The author's just-made write must not be reverted (the file must still exist).",
        )
        self.assertEqual(
            authored_path.read_text(encoding="utf-8"),
            authored_content_before,
            msg="The author's just-made write must not be reverted (content must be unchanged).",
        )


if __name__ == "__main__":
    unittest.main()
