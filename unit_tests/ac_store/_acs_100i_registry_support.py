"""
MODULE: _acs_100i_registry_support
GOAL: A real-git harness for ACS-100i-8 / -8-i — the commit-time check that
    refuses a NEW package-registry entry unless a cited acceptance criterion
    carries `package_surface: true`.
BUSINESS CONTEXT: Once the structured-spec obligation is keyed off a
    declaration (ACS-100i-6), an author who registers a package surface and
    simply omits `package_surface: true` escapes the gate entirely. Nothing in
    the record contradicts them — the record is a statement of intent and intent
    is what the author controls. The signal NOT under the author's control is the
    registration itself: a package surface exists because an entry appears in a
    registry the build reads. That entry is in the diff, it is enumerable, and it
    cannot be omitted without failing to ship the feature. So the check runs
    against the registration, not against the record.

THE CONTRACT THIS HARNESS PINS
------------------------------
There is no implementation yet; these tests define it.

  script    templates/scripts/commit_guardian/check_package_surface_declaration.py
            (self-hosting boundary, ADR-001: deployed to
            scripts/commit_guardian/ in a consumer layout)
  invoked   python <script> <commit_msg_file>     with cwd = the committing repo
  staged    read from real git: `git diff --cached --name-only --diff-filter=AM`
  citations AC ids parsed out of the commit-message file, and out of any staged
            ticket body in the same commit
  records   cited ids resolved against docs/acceptance-criteria/**/<id>.yaml in
            the committing repo
  exit 0    allowed
  exit 1    refused; the refusal text names the registry file, the key of each
            entry being added, and every acceptance criterion the change cited
  nothing   when no package registry is touched: exit 0, and the output states
            that there was nothing to evaluate — it must NOT claim a pass

  registries watched (a maintained enumeration; CONCESSION 3 on ACS-100i-8):
      config/agent_registry.json
      config/skill_registry.json
      config/paths.json
      templates/scripts/commit_guardian/commit_guardian.json

  "new entry" = a key present in the staged content and absent from HEAD. For a
  list-of-objects registry (agent_registry.json's `agents`) the key is each
  object's `id`; for an object registry it is the mapping key.

ARCHITECTURE: Each test builds a throwaway git repository under pytest's
    tmp_path containing a real registry file and a real AC store, commits a
    baseline, stages the change under test with real `git add`, and runs the
    hook as a subprocess with cwd set to that repo — so the hook's
    `git rev-parse --show-toplevel` root resolution and its `git diff --cached`
    read behave exactly as they do in a real commit. Nothing is mocked and no
    source file is grepped.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: The hook this tree must produce. Absent today — that is the red state.
DECLARATION_HOOK = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_package_surface_declaration.py"
)

#: The registry the ACS-100i-8 doc_links name first, and the one these tests
#: exercise: an entry here is what makes an agent reachable in a consumer
#: project — the registration event the check watches for.
AGENT_REGISTRY_REL = "config/agent_registry.json"


@dataclass(frozen=True)
class HookRun:
    """Outcome of running the declaration check in a throwaway repo."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        return self.stdout + self.stderr

    @property
    def refused(self) -> bool:
        """True when the check blocked the commit."""
        return self.returncode != 0


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command inside ``repo`` and fail loudly on error."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, (
        f"git {' '.join(args)} failed in {repo}: {proc.stdout}{proc.stderr}"
    )
    return proc


def _agent_entry(agent_id: str) -> dict[str, Any]:
    """Return a minimal agent-registry entry shaped like the real ones."""
    return {
        "id": agent_id,
        "name": agent_id.replace("-", " ").title(),
        "tier": "utility",
        "role": "analysis",
        "portable": True,
    }


def _ac_record(ac_id: str, package_surface: bool | None) -> dict[str, Any]:
    """Return an AC record, optionally carrying the declaration.

    Args:
        ac_id: The record id, also its file stem.
        package_surface: True / False to set the field, or None to omit it.
    """
    record: dict[str, Any] = {
        "id": ac_id,
        "title": f"Fixture acceptance criterion {ac_id}",
        "component": "ac-store",
        "components": ["ac_store"],
        "status": "active",
        "readiness": "approved",
        "priority": "medium",
        "criteria": (
            f"Given fixture criterion {ac_id}\n"
            "When the commit-time declaration check runs\n"
            "Then it reconciles the registration against this record"
        ),
        "assigned_agent": "python-coder",
    }
    if package_surface is not None:
        record["package_surface"] = package_surface
    return record


def make_repo(tmp_path: Path, ac_records: dict[str, bool | None]) -> Path:
    """Create a committed throwaway repo with a registry and an AC store.

    Args:
        tmp_path: pytest tmp_path.
        ac_records: Mapping of AC id -> declaration value (True / False / None
            for "field omitted").

    Returns:
        Path to the repo root.
    """
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "docs" / "acceptance-criteria" / "ac-store").mkdir(parents=True)

    registry = {
        "$schema": "./agent_registry.schema.json",
        "agent_categories": ["analysis"],
        "agents": [_agent_entry("research-agent")],
    }
    (repo / AGENT_REGISTRY_REL).write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )

    for ac_id, declaration in ac_records.items():
        (repo / "docs" / "acceptance-criteria" / "ac-store" / f"{ac_id}.yaml").write_text(
            yaml.safe_dump(_ac_record(ac_id, declaration), sort_keys=False),
            encoding="utf-8",
        )

    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "ACS-100i test harness")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def stage_new_agent(repo: Path, agent_id: str) -> None:
    """Add a NEW entry to the agent registry and stage it."""
    path = repo / AGENT_REGISTRY_REL
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry["agents"].append(_agent_entry(agent_id))
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", AGENT_REGISTRY_REL)


def stage_edited_agent(repo: Path, agent_id: str, **changes: Any) -> None:
    """Change the value of an entry ALREADY present in the registry, and stage it."""
    path = repo / AGENT_REGISTRY_REL
    registry = json.loads(path.read_text(encoding="utf-8"))
    matches = [e for e in registry["agents"] if e["id"] == agent_id]
    assert matches, f"{agent_id} is not already present in the registry"
    matches[0].update(changes)
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", AGENT_REGISTRY_REL)


def stage_removed_agent(repo: Path, agent_id: str) -> None:
    """Remove an entry from the registry and stage the removal."""
    path = repo / AGENT_REGISTRY_REL
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry["agents"] = [e for e in registry["agents"] if e["id"] != agent_id]
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", AGENT_REGISTRY_REL)


def stage_unrelated_edit(repo: Path) -> None:
    """Stage a change that touches no package registry at all."""
    path = repo / "docs" / "notes.md"
    path.write_text("An edit that registers nothing.\n", encoding="utf-8")
    _git(repo, "add", "docs/notes.md")


def current_branch(repo: Path) -> str:
    """Return the name of the branch ``repo``'s HEAD currently points at."""
    return _git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()


def stage_merge_carrying_new_agent(repo: Path, agent_id: str) -> None:
    """Leave ``repo`` mid-merge, carrying an entry the OTHER parent already has.

    Reproduces KI-BP-20260901-0812: a real, diverged two-parent merge where the
    only "new relative to HEAD" registry entry was registered by an earlier,
    already-landed commit on the branch being merged in (``MERGE_HEAD``) — not
    by this merge. Uses ``git merge --no-commit`` so the merge is left staged
    with ``MERGE_HEAD`` present and uncommitted, exactly the state a
    ``commit-msg`` hook observes for a real merge commit before it is written.

    Args:
        repo: Repo produced by :func:`make_repo`, on its base branch.
        agent_id: Id of the agent entry to register on the base branch and then
            merge in.
    """
    base_branch = current_branch(repo)

    _git(repo, "checkout", "-b", "feature-branch")
    notes = repo / "docs" / "feature-notes.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("Unrelated feature-branch work.\n", encoding="utf-8")
    _git(repo, "add", "docs/feature-notes.md")
    _git(repo, "commit", "-q", "-m", "chore: unrelated feature-branch change")

    _git(repo, "checkout", base_branch)
    stage_new_agent(repo, agent_id)
    _git(repo, "commit", "-q", "-m", f"feat(agents): add {agent_id} directly to base")

    _git(repo, "checkout", "feature-branch")
    merge = subprocess.run(
        ["git", "-C", str(repo), "merge", "--no-commit", "--no-ff", base_branch],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert merge.returncode == 0, (
        f"expected a clean, conflict-free merge; got {merge.returncode}: "
        f"{merge.stdout}{merge.stderr}"
    )


def stage_merge_with_genuinely_new_agent(
    repo: Path, carried_agent_id: str, new_agent_id: str
) -> None:
    """Leave ``repo`` mid-merge, carrying one entry AND introducing a fresh one.

    Builds on :func:`stage_merge_carrying_new_agent` (``carried_agent_id`` is
    already on the base branch being merged in, so it must NOT need a
    citation), then additionally stages ``new_agent_id`` — an entry absent from
    BOTH parents, added only while the merge is in progress. This is the
    negative control: the merge-scoping fix must still refuse on
    ``new_agent_id``, because nothing carried it in from either side.

    Args:
        repo: Repo produced by :func:`make_repo`, on its base branch.
        carried_agent_id: Id already registered on the base branch (must be
            waved through with no citation).
        new_agent_id: Id that exists in neither parent (must still be refused
            without a declaring citation).
    """
    stage_merge_carrying_new_agent(repo, carried_agent_id)
    stage_new_agent(repo, new_agent_id)


def stage_merge_with_edited_agent(repo: Path, agent_id: str, **changes: Any) -> None:
    """Leave ``repo`` mid-merge, editing an entry already present on both parents.

    Unlike :func:`stage_edited_agent` alone (a plain single-parent edit, no
    ``MERGE_HEAD``), this builds a real diverged two-branch merge (``git merge
    --no-commit --no-ff``) so ``MERGE_HEAD`` is genuinely present while
    ``agent_id`` — already registered by :func:`make_repo` on both branches —
    is edited on the branch being merged INTO. The registry KEY is unchanged
    on both sides; only a field value differs. This is what "editing during a
    merge" must actually mean for the test to earn its name: a real merge in
    progress, not a bare single-parent edit relabelled with a merge-flavoured
    docstring.

    Args:
        repo: Repo produced by :func:`make_repo`, on its base branch. Must
            already carry ``agent_id`` (``make_repo`` seeds ``research-agent``).
        agent_id: Id of the already-registered entry to edit.
        **changes: Field values to change on ``agent_id``'s entry.
    """
    base_branch = current_branch(repo)

    _git(repo, "checkout", "-b", "feature-branch")
    stage_edited_agent(repo, agent_id, **changes)
    _git(repo, "commit", "-q", "-m", f"chore: retier {agent_id} on feature-branch")

    _git(repo, "checkout", base_branch)
    notes = repo / "docs" / "base-branch-notes.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("Unrelated base-branch work.\n", encoding="utf-8")
    _git(repo, "add", "docs/base-branch-notes.md")
    _git(repo, "commit", "-q", "-m", "chore: unrelated base-branch change")

    _git(repo, "checkout", "feature-branch")
    merge = subprocess.run(
        ["git", "-C", str(repo), "merge", "--no-commit", "--no-ff", base_branch],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert merge.returncode == 0, (
        f"expected a clean, conflict-free merge; got {merge.returncode}: "
        f"{merge.stdout}{merge.stderr}"
    )


def merge_head_line_count(repo: Path) -> int:
    """Return the number of non-blank lines in ``.git/MERGE_HEAD``.

    Used by octopus-merge tests to prove the fixture actually built a merge
    with 3+ parents rather than silently collapsing to a fast-forward or a
    two-parent merge — the reproduction is worthless if it does not exercise
    the third-and-later line the probe under test is accused of dropping.
    """
    path = repo / ".git" / "MERGE_HEAD"
    if not path.is_file():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def stage_octopus_merge_carrying_third_parent_only(repo: Path, agent_id: str) -> None:
    """Leave ``repo`` mid-octopus-merge, carrying an entry on the THIRD parent ONLY.

    Builds a real three-way octopus merge — ``git merge --no-commit --no-ff
    branch-a branch-b branch-c`` run from the base branch — where ``agent_id``
    was registered on ``branch-c``'s tip and nowhere else: not on the base
    branch, not on ``branch-a``, not on ``branch-b``. ``MERGE_HEAD`` ends up
    with three lines (one per named branch); the base branch's own tip is the
    first parent (``HEAD``) and is not among them.

    This reproduces the finding that ``git rev-parse -q --verify MERGE_HEAD``
    resolves only the FIRST line of ``MERGE_HEAD``: that probe names only
    ``branch-a`` and never consults ``branch-b`` or ``branch-c``, so a gate
    still using it would refuse ``agent_id`` even though a real parent of the
    merge already carries it — exactly the octopus scope ACS-100i-8-ii
    requires and the pre-fix probe silently dropped.

    Args:
        repo: Repo produced by :func:`make_repo`, on its base branch.
        agent_id: Id of the agent entry registered on ``branch-c``'s tip ONLY.
    """
    base_branch = current_branch(repo)

    for branch_name in ("branch-a", "branch-b"):
        _git(repo, "checkout", base_branch)
        _git(repo, "checkout", "-b", branch_name)
        notes = repo / "docs" / f"{branch_name}-notes.md"
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.write_text(f"Unrelated {branch_name} work.\n", encoding="utf-8")
        _git(repo, "add", f"docs/{branch_name}-notes.md")
        _git(repo, "commit", "-q", "-m", f"chore: unrelated {branch_name} change")

    _git(repo, "checkout", base_branch)
    _git(repo, "checkout", "-b", "branch-c")
    stage_new_agent(repo, agent_id)
    _git(repo, "commit", "-q", "-m", f"feat(agents): add {agent_id} on branch-c only")

    _git(repo, "checkout", base_branch)
    merge = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge",
            "--no-commit",
            "--no-ff",
            "branch-a",
            "branch-b",
            "branch-c",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert merge.returncode == 0, (
        f"expected a clean, conflict-free octopus merge; got {merge.returncode}: "
        f"{merge.stdout}{merge.stderr}"
    )


def stage_octopus_merge_with_genuinely_new_agent(
    repo: Path, carried_agent_id: str, new_agent_id: str
) -> None:
    """Leave ``repo`` mid-octopus-merge, carrying a third-parent entry AND a fresh one.

    Builds on :func:`stage_octopus_merge_carrying_third_parent_only`
    (``carried_agent_id`` is on ``branch-c`` only, so it must NOT need a
    citation), then additionally stages ``new_agent_id`` — an entry absent
    from ALL THREE parents, added only while the octopus merge is in
    progress. This is the negative control for the octopus case: the
    merge-scoping fix must still refuse on ``new_agent_id`` on an octopus
    merge, exactly as it does on a two-parent one.

    Args:
        repo: Repo produced by :func:`make_repo`, on its base branch.
        carried_agent_id: Id already registered on ``branch-c`` only (must be
            waved through with no citation).
        new_agent_id: Id absent from every parent (must still be refused
            without a declaring citation).
    """
    stage_octopus_merge_carrying_third_parent_only(repo, carried_agent_id)
    stage_new_agent(repo, new_agent_id)


def run_check(repo: Path, commit_message: str) -> HookRun:
    """Run the declaration check against ``repo``'s staged state.

    Args:
        repo: The throwaway repo whose index holds the change under test.
        commit_message: The commit message; the check parses its AC citations.

    Returns:
        A :class:`HookRun`.
    """
    # Explicit, not incidental: without this guard a missing hook would make
    # python itself exit 2 ("can't open file"), which every "must refuse"
    # assertion below would happily read as a refusal — a false green on an
    # unimplemented gate.
    assert DECLARATION_HOOK.is_file(), (
        "the commit-time package-surface declaration check does not exist yet. "
        f"ACS-100i-8 requires it at {DECLARATION_HOOK.relative_to(REPO_ROOT)}, "
        "invoked as `python <script> <commit_msg_file>` with cwd set to the "
        "committing repo (see this module's docstring for the full contract)."
    )

    msg_file = repo / ".git" / "COMMIT_EDITMSG"
    msg_file.write_text(commit_message, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(DECLARATION_HOOK), str(msg_file)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(repo),
        check=False,
    )
    return HookRun(proc.returncode, proc.stdout, proc.stderr)
