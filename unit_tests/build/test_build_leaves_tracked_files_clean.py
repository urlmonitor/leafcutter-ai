"""Bootstrap's build.py run must leave tracked files byte-identical to HEAD.

Ticket TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty. The build is run
exactly as ``setup_ticket_worktree._bootstrap`` runs it, in a throwaway clone.
Implementation needed: build.py writes generated text with newline="\n" and
committed generated files match current build output.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE: dict = {}


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True).stdout


def _built_clone() -> Path:
    if "clone" not in _STATE:
        tmp = tempfile.TemporaryDirectory()
        _STATE["tmp"] = tmp
        clone = Path(tmp.name) / "clone"
        subprocess.run(["git", "clone", "--no-local", "-q", str(REPO_ROOT), str(clone)],
                       check=True, capture_output=True)
        subprocess.run([sys.executable, str(clone / "scripts" / "build.py"),
                        "--target-dir", str(clone)],
                       cwd=str(clone), check=True, capture_output=True)
        _STATE["clone"] = clone
    return _STATE["clone"]


def tearDownModule():
    tmp = _STATE.pop("tmp", None)
    if tmp is not None:
        tmp.cleanup()


class TestBuildLeavesTrackedFilesClean(unittest.TestCase):
    def test_build_on_a_clean_checkout_leaves_tracked_files_unchanged(self):
        # covers: TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty
        # angle: criterion
        """Build in a fresh clone must leave `git status` clean."""
        clone = _built_clone()
        out = _git(clone, "status", "--porcelain", "--untracked-files=no").strip()
        self.assertEqual(
            out, "",
            "build.py modified tracked files:\n" + out,
        )

    def test_generated_text_outputs_keep_lf_line_endings(self):
        # covers: TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty
        # angle: real_artifact
        """Generated tracked text files gain no CRLF the HEAD version lacks."""
        clone = _built_clone()
        targets = ["LEAFCUTTER_VERSION", "docs/INDEX.md"]
        targets += sorted(
            p.relative_to(clone).as_posix()
            for p in (clone / "docs" / "agents" / "cards").glob("*.card.md")
        )
        offenders = []
        for rel in targets:
            path = clone / rel
            if not path.exists():
                continue
            head = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=str(clone),
                                  capture_output=True).stdout
            if b"\r\n" in path.read_bytes() and b"\r\n" not in head:
                offenders.append(rel)
        self.assertEqual(offenders, [], "CRLF introduced by build in: " + ", ".join(offenders))


def _resolver_repo(extra_tracked=()):
    """Temp git repo: tracked templates copy, gitignored deployed copy."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text(".claude/\n.leafcutter/\n", encoding="utf-8", newline="\n")
    tracked = ["templates/skills/signoff/SKILL.md", *extra_tracked]
    for rel in tracked + [".claude/skills/signoff/SKILL.md"]:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x\n", encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", ".gitignore", "templates"], cwd=str(root),
                   check=True, capture_output=True)
    return tmp, root


def _resolver():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import generate_agent_cards
    finally:
        sys.path.pop(0)
    return generate_agent_cards._resolve_source_to_path


class TestResolverIgnoresUntrackedCopies(unittest.TestCase):
    def test_resolver_ignores_gitignored_deployed_copy(self):
        # covers: TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty
        # angle: discrimination
        """Strategy 2 must return the tracked templates path, not .claude/."""
        tmp, root = _resolver_repo()
        self.addCleanup(tmp.cleanup)
        got = _resolver()("signoff SKILL.md", root)
        self.assertEqual(
            got, root / "templates" / "skills" / "signoff" / "SKILL.md")

    def test_resolver_deployed_copy_does_not_make_tracked_match_ambiguous(self):
        # covers: TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty
        # angle: boundary
        """Strategy 3: unique tracked file plus ignored duplicate still resolves."""
        tmp, root = _resolver_repo()
        self.addCleanup(tmp.cleanup)
        got = _resolver()("SKILL.md", root)
        self.assertEqual(
            got, root / "templates" / "skills" / "signoff" / "SKILL.md")


if __name__ == "__main__":
    unittest.main()
