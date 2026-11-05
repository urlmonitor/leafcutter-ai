"""
MODULE: test_tq100a_2_ii
AC: TQ-100a-2-ii -- the worktree-scoped identity write is refused as a remediation
    because it aborts on a fresh checkout (no worktreeConfig extension); the
    environment-supplied identity is the accepted form.
GOAL: Reproduce the extension-less condition for real, and require the written
    remediation to stop offering the aborting form.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tq100a_2_support as S  # noqa: E402

_KI_DIR = S.REPO_ROOT / "docs" / "known-issues"
_REFUSAL = re.compile(
    r"(not\s+(available|legal|usable|possible|an option)|abort|fatal|refus|do\s+not|never|"
    r"fails?\b|unavailable|illegal)",
    re.IGNORECASE,
)


def _remediation_items(text: str) -> list[str]:
    """Numbered items inside each 'Remediation' passage of a write-up."""
    items: list[str] = []
    for m in re.finditer(r"^(?:\*\*|#+\s*)Remediation.*$", text, re.MULTILINE):
        rest = text[m.end():]
        end = re.search(r"^(?:\*\*|#+\s)", rest, re.MULTILINE)
        passage = rest[: end.start()] if end else rest
        items.extend(re.split(r"\n(?=\d+\.\s)", passage))
    return items


class TestTq100a2Ii(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.env = S.scrubbed_env(self.root / "home")

    def _extensionless_multi_worktree(self):
        host = S.make_host(self.root, self.env)
        self.assertIsNone(S.read_key(host, "extensions.worktreeConfig", self.env))
        return host, S.add_worktree(host, self.root, self.env)

    def test_tq100a_2_ii_worktree_scoped_write_aborts_on_a_checkout_without_the_extension(self):
        # covers: TQ-100a-2-ii
        # angle: boundary
        _host, wt = self._extensionless_multi_worktree()
        res = S.git(["config", "--worktree", "user.email", "x@example.invalid"], wt, self.env)
        self.assertEqual(res.returncode, 128, res.stderr)
        self.assertIn("worktreeConfig", res.stderr)

    def test_tq100a_2_ii_the_environment_supplied_identity_succeeds_on_that_same_checkout(self):
        # covers: TQ-100a-2-ii
        # angle: criterion
        _host, wt = self._extensionless_multi_worktree()
        res = S.sandbox_commit(wt, self.env)
        self.assertEqual(res.returncode, 0, res.stderr)
        want = f"{S.FIXTURE_NAME} <{S.FIXTURE_EMAIL}>"
        got = S.must_git(["log", "-1", "--format=%an <%ae>|%cn <%ce>"], wt, self.env).strip()
        self.assertEqual(got, f"{want}|{want}")

    def test_tq100a_2_ii_the_portability_suite_passes_on_an_extension_less_checkout(self):
        # covers: TQ-100a-2-ii
        # angle: deployed
        clone = self.root / "clone"
        # core.longpaths for the clone too: the scrubbed env cannot reach the global config,
        # and Windows aborts the checkout on the long changelog filenames without it.
        S.must_git(["-c", "core.longpaths=true", "clone", "-q", "--no-hardlinks",
                    str(S.REPO_ROOT), str(clone)], self.root, self.env)
        self.assertIsNone(S.read_key(clone, "extensions.worktreeConfig", self.env))
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
             "unit_tests/portability/test_ge_120e_1_i.py::"
             "TestCleanAutomergeWithNoAuthoredContentIsNotBlocked::"
             "test_ge120e1i_clean_automerge_with_no_authored_content_is_not_blocked"],
            cwd=str(clone),
            # core.longpaths is normally supplied by the machine's global config,
            # which this run deliberately cannot reach (no identity anywhere).
            env=dict(self.env, PYTHONPATH=str(clone), GIT_CONFIG_COUNT="1",
                     GIT_CONFIG_KEY_0="core.longpaths", GIT_CONFIG_VALUE_0="true"),
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=550,
        )
        self.assertEqual(res.returncode, 0, (res.stdout + res.stderr)[-3000:])

    def test_tq100a_2_ii_the_register_no_longer_offers_the_aborting_form_as_a_remediation(self):
        # covers: TQ-100a-2-ii
        # angle: real_artifact
        files = sorted(_KI_DIR.glob("testing-quality/**/*ki-tq-012*.md"))
        files.append(_KI_DIR / "testing-quality.md")
        self.assertGreaterEqual(len(files), 3, files)
        offenders = []
        examined = 0
        for f in files:
            for item in _remediation_items(f.read_text(encoding="utf-8")):
                examined += 1
                if "--worktree" in item and not _REFUSAL.search(item):
                    offenders.append((f.name, item.strip()[:120]))
        self.assertGreaterEqual(examined, 2, "remediation passages not found")
        self.assertEqual(offenders, [], "remediation still offers `git config --worktree`")


if __name__ == "__main__":
    unittest.main()
