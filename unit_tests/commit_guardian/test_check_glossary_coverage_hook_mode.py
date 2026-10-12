"""Hook-mode behaviour of check_glossary_coverage (no dispatch_fn => no stub decisions).

Ticket TICKET-20261002-GlossaryHookStubBlacklistsNewTerms. In hook mode the hook
must write nothing to docs/glossary.md / docs/glossary_blacklist.md, report the
novel terms, and exit 0. An injected dispatch_fn still applies its decisions.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO / "templates" / "scripts"
for _p in (_SCRIPTS / "commit_guardian", _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import check_glossary_coverage as cgc  # noqa: E402
from glossary_detector import detect_candidates  # noqa: E402

TERM = "backfill_complete"
GLOSSARY = "# Glossary\n\n### existing_term\n\nAn existing entry.\n"
BLACKLIST = "# Glossary Blacklist\n\n| term | reason | date |\n| --- | --- | --- |\n"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=True
    ).stdout


class _HookRepo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "t")
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "glossary.md").write_text(GLOSSARY, encoding="utf-8", newline="")
        (docs / "glossary_blacklist.md").write_text(BLACKLIST, encoding="utf-8", newline="")
        _git(self.root, "add", "docs")
        _git(self.root, "commit", "-q", "-m", "base")
        (self.root / "notes.md").write_text(
            f"The {TERM} flag marks a finished backfill run.\n", encoding="utf-8"
        )
        _git(self.root, "add", "notes.md")
        self.staged_before = _git(self.root, "diff", "--cached", "--name-only")
        self.g_before = (docs / "glossary.md").read_bytes()
        self.b_before = (docs / "glossary_blacklist.md").read_bytes()

    def _detector_patch(self):
        return mock.patch.object(cgc, "_load_detector", return_value=detect_candidates)

    def _run_main(self):
        out, err = io.StringIO(), io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with self._detector_patch(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cgc.main()
        finally:
            os.chdir(cwd)
        return rc, out.getvalue() + err.getvalue()


class TestHookMode(_HookRepo):
    def test_hook_mode_writes_no_stub_decisions(self):
        # covers: TICKET-20261002-GlossaryHookStubBlacklistsNewTerms
        # angle: discrimination
        """Hook mode (main(), no dispatch_fn) must leave glossary files untouched."""
        rc, _ = self._run_main()
        self.assertEqual(rc, 0)
        self.assertEqual((self.root / "docs/glossary.md").read_bytes(), self.g_before)
        self.assertEqual((self.root / "docs/glossary_blacklist.md").read_bytes(), self.b_before)
        self.assertEqual(_git(self.root, "diff", "--cached", "--name-only"), self.staged_before)

    def test_hook_mode_reports_novel_terms(self):
        # covers: TICKET-20261002-GlossaryHookStubBlacklistsNewTerms
        # angle: reachability
        """Hook output must name the novel term and point at the triage flow."""
        rc, output = self._run_main()
        self.assertEqual(rc, 0)
        self.assertIn(TERM, output)
        self.assertIn("glossary-triage", output)
        self.assertIn("glossary_bootstrap.py --apply-decisions", output)


class TestInjectedDispatch(_HookRepo):
    def test_injected_dispatch_still_applies_decisions(self):
        # covers: TICKET-20261002-GlossaryHookStubBlacklistsNewTerms
        # angle: criterion
        """An injected dispatch_fn returning add_to_glossary still writes glossary.md."""

        def fake_dispatch(term, occurrences, glossary_terms, blacklist_terms):
            return {
                "action": "add_to_glossary",
                "reason": "real triage",
                "draft_entry": f"### {term}\n\nA finished backfill marker.\n",
                "canonical_link": "",
            }

        with self._detector_patch():
            rc = cgc.check_glossary_coverage(self.root, dispatch_fn=fake_dispatch)
        self.assertEqual(rc, 0)
        text = (self.root / "docs/glossary.md").read_text(encoding="utf-8")
        self.assertIn(f"### {TERM}", text)


if __name__ == "__main__":
    unittest.main()
