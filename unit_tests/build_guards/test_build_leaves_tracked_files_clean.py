"""Bootstrap's build.py must be idempotent and keep generated text LF-only.

Ticket TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty. The build is run
exactly as ``setup_ticket_worktree._bootstrap`` runs it, in a throwaway clone.
Implementation needed: build.py writes generated text with newline="\n" and
committed generated files match current build output.

TQ-600a-9-ii: ``test_a_second_build_on_a_clean_checkout_changes_nothing`` used
to clone and build its own throwaway checkout (2 real ``build.py`` spawns),
structurally identical to ``_built_clone()``'s own clone-and-build (a 3rd
spawn when ``test_generated_text_outputs_keep_lf_line_endings`` also runs).
It now reuses ``_built_clone()``'s cached, already-built clone as its "first"
snapshot and runs exactly one more build on top of it for the "second" --
2 real builds total for the whole file where there were 3. See
``unit_tests/suite_performance/_test_helpers_tq_600a_9.py``'s module
docstring for the full TQ-600a-9 production contract this file's
``emit_execution_signal`` call participates in.
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_coordination import (
    emit_execution_signal,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE: dict = {}
_BASETEMP_ROOT: dict[str, Path] = {}


@pytest.fixture(scope="session", autouse=True)
def _capture_basetemp_root(tmp_path_factory):
    """Capture pytest's own basetemp root so `_built_clone()`'s clone lands
    somewhere an EXTERNAL caller can find via `--basetemp` (TQ-600a-9-ii's
    hardlink-safety test inspects the clone this file produces via
    `basetemp.rglob(".git")`, which can only see paths pytest itself placed
    under that root -- a plain `tempfile.TemporaryDirectory()`, this file's
    previous approach, is invisible to it). Autouse so it runs even though
    this file's tests are unittest.TestCase methods, which cannot request a
    fixture directly; session-scoped so every test in this module shares the
    one captured root.
    """
    _BASETEMP_ROOT["root"] = tmp_path_factory.getbasetemp()


def _clone_parent_dir() -> Path:
    """Return the directory `_built_clone()` should create its clone under.

    Prefers the captured pytest basetemp root (see `_capture_basetemp_root`)
    so the clone is discoverable via `--basetemp` from an external process.
    Falls back to an ordinary OS temp dir for a direct `python -m unittest`
    invocation, where no pytest session (and so no basetemp fixture) ran.
    """
    root = _BASETEMP_ROOT.get("root")
    if root is not None:
        return root
    return Path(tempfile.mkdtemp(prefix="tq600a9ii_no_basetemp_"))


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True).stdout


def _clone_head(clone: Path) -> None:
    subprocess.run(["git", "clone", "--no-local", "-q", str(REPO_ROOT), str(clone)],
                   check=True, capture_output=True)


def _run_build(clone: Path) -> None:
    subprocess.run([sys.executable, str(clone / "scripts" / "build.py"),
                    "--target-dir", str(clone)],
                   cwd=str(clone), check=True, capture_output=True)
    # TQ-600a-9-ii: the one real deploy subprocess this file's tests funnel
    # through. A no-op unless a test has pointed
    # LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG at a scratch file.
    emit_execution_signal(clone)


def _built_clone() -> Path:
    if "clone" not in _STATE:
        clone = _clone_parent_dir() / f"tq600a9ii_clone_{uuid.uuid4().hex}"
        _clone_head(clone)
        _run_build(clone)
        _STATE["clone"] = clone
    return _STATE["clone"]


def _snapshot_tracked(clone: Path) -> dict:
    """Map each tracked path to the sha256 of its bytes (None when missing)."""
    names = _git(clone, "ls-files", "-z").split("\0")
    snap = {}
    for rel in filter(None, names):
        path = clone / rel
        snap[rel] = (hashlib.sha256(path.read_bytes()).hexdigest()
                     if path.is_file() else None)
    return snap


def tearDownModule():
    """Leave `_built_clone()`'s clone in place when it was placed under
    pytest's own basetemp (TQ-600a-9-ii's hardlink-safety and self-
    targeting tests inspect it via `--basetemp` from an EXTERNAL process,
    AFTER this module's own test run has already finished -- eagerly
    deleting it here would make it invisible to that later inspection).
    Only the FALLBACK (no pytest basetemp available, e.g. a direct
    `python -m unittest` invocation) location -- which no external
    inspection can ever reach -- is cleaned up here.
    """
    clone = _STATE.pop("clone", None)
    if clone is not None and _BASETEMP_ROOT.get("root") is None:
        shutil.rmtree(clone, ignore_errors=True)


class TestBuildLeavesTrackedFilesClean(unittest.TestCase):
    def test_a_second_build_on_a_clean_checkout_changes_nothing(self):
        # covers: TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty
        # angle: criterion
        """A repeat build must leave every tracked file byte-identical.

        Pins byte stability (no CRLF flip-flop) and machine independence (a
        deployed copy cannot change links between runs). Freshness of the
        committed generated files is out of scope for this test.

        TQ-600a-9-ii: reuses `_built_clone()`'s already-built clone as the
        FIRST snapshot instead of cloning and building one of its own -- the
        clone it would have produced is structurally identical to
        `_built_clone()`'s own clone-and-build, so sharing it removes one of
        this file's three real `build.py` subprocess spawns without changing
        what this test proves: idempotency does not depend on how many PRIOR
        builds the inspected tree has already undergone.
        """
        clone = _built_clone()
        first = _snapshot_tracked(clone)
        _run_build(clone)
        second = _snapshot_tracked(clone)
        changed = sorted(k for k in first.keys() | second.keys()
                         if first.get(k) != second.get(k))
        self.assertEqual(
            changed, [],
            "a second build.py run changed tracked files:" + chr(10) + chr(10).join(changed),
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
