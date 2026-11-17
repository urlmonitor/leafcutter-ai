"""
MODULE: unit_tests/build_orchestration/_bo400e3_support.py
GOAL: Shared REAL-git scratch fixtures for the BO-400e-3-ii .. -ix / BO-4500a-5-iv family
      (finalize step 3.5: which records a finishing branch may close, and how).

NOT a test file (leading underscore). Nothing here is collected.

CONTRACT PINNED FOR THE CODER (nothing below exists yet; the tests pin it):

  scripts/build_orchestration/finalize_closable_set.py  -- two subcommands, one JSON object on stdout:

    derive --worktree <abs> --branch <name> --base-ref <ref>
        -> {outcome: closable|nothing_to_close|undeterminable, reason_code, branch, branch_kind,
            base_ref, merge_base, built_for_ticket, records:[{kind,id,path,status}], already_done,
            changed_not_closable, set_digest, set_file, listing_text}
        Persists the set (records + set_digest) to set_file, under the worktree's git dir.

    close --worktree <abs> --set-file <abs> [--scripts-root <dir>]
        -> {set_digest, results:[{kind,id,path,before,after,result,reason}], outside_set_changes:
            [{path,id,before,after}], commit_paths:[...], out_of_set_paths:[...]}
        Reads ONLY the persisted set file. `--scripts-root` names the directory holding
        set_ticket_status.py and ac_store/mark_ac_done.py (default: the worktree's deployed
        output root); the tests point it at the source `scripts/` directory, or at a wrapper
        directory that injects a leak.

  The record the built-for ticket is read from is the git config key
  branch.<branch>.leafcutterTicket (BO-400e-3-ix), nothing else.

Fixtures are serialised with yaml.safe_dump (the real producer), never typed as literals.
Every command runs the REAL script as a subprocess against a REAL scratch repository, with
cwd OUTSIDE the repository so no implementation can lean on the working directory.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
MODULE = SCRIPTS / "build_orchestration" / "finalize_closable_set.py"
COMMIT_STEP = REPO_ROOT / "templates" / "scripts" / "commit_changes.py"
RECORD_KEY = "leafcutterTicket"

INBOX = "tickets/00_inbox"
EPICS = "tickets/00_inbox/epics"
AC_ROOT = "docs/acceptance-criteria/build-orchestration"
SIGNED = {"python-coder": "signed_off"}
NEEDED = {"python-coder": "needed"}
PR_NEEDED = {"python-coder": "signed_off", "pull-request": "needed"}


def clean_env(scratch: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for key in ("TMPDIR", "TEMP", "TMP"):
        env[key] = str(scratch)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def as_json(case: unittest.TestCase, proc: subprocess.CompletedProcess) -> dict:
    """stdout as exactly one JSON object; an absent or crashing CLI is an assertion-shaped red."""
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        case.fail(
            f"stdout was not one JSON object: rc={proc.returncode} stdout={proc.stdout[:300]!r} "
            f"stderr={proc.stderr[-400:]!r}"
        )
    case.assertIsInstance(data, dict)
    return data


def ac_rel(ac_id: str) -> str:
    return f"{AC_ROOT}/{ac_id.split('a-')[0]}/{ac_id}.yaml"


_WRAPPER = """\
import json, subprocess, sys
from pathlib import Path
REAL = {real!r}
code = subprocess.run([sys.executable, REAL, *sys.argv[1:]]).returncode
if code == 0:
    for leak in json.loads((Path(__file__).resolve().parent / "leak.json").read_text(encoding="utf-8")):
        if leak["after"] != {kind!r}:
            continue
        path = Path(leak["target"])
        text = path.read_text(encoding="utf-8")
        if leak["mode"] == "append":
            path.write_text(text + "\\n# touched during the close\\n", encoding="utf-8")
            continue
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith(leak["key"] + ":"):
                lines[i] = leak["key"] + ": " + leak["to"] + "\\n"
                break
        path.write_text("".join(lines), encoding="utf-8")
sys.exit(code)
"""


class Store:
    """A scratch origin + clone on branch main, with helpers to build real tickets and ACs."""

    def __init__(self, case: unittest.TestCase) -> None:
        self.case = case
        self.scratch = Path(tempfile.mkdtemp(prefix="bo400e3_"))
        case.addCleanup(shutil.rmtree, str(self.scratch), True)
        self.env = clean_env(self.scratch)
        self.origin = self.scratch / "origin.git"
        self.repo = self.scratch / "repo"
        self.repo.mkdir()
        self._git("init", "-q", "--bare", "-b", "main", str(self.origin), cwd=self.scratch)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("remote", "add", "origin", str(self.origin))

    # -- git plumbing ---------------------------------------------------
    def _git(self, *args: str, cwd: Path, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, env=self.env, capture_output=True, text=True, check=False
        )
        if check and proc.returncode != 0:
            self.case.fail(f"fixture git {args} failed: {proc.stderr}")
        return proc.stdout

    def git(self, *args: str, check: bool = True) -> str:
        return self._git(*args, cwd=self.repo, check=check)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def head_files(self) -> list[str]:
        out = self.git("show", "--name-only", "--format=", "HEAD")
        return sorted(line for line in out.splitlines() if line)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def push_main(self) -> None:
        self.git("push", "-q", "origin", "main")

    def new_branch(self, name: str) -> None:
        self.git("checkout", "-q", "-b", name)

    def record_built_for(self, branch: str, ticket_rel: str) -> None:
        self.git("config", f"branch.{branch}.{RECORD_KEY}", ticket_rel)

    def advance_main_elsewhere(self, files: dict[str, str], message: str) -> None:
        """A second clone commits to main and pushes: origin/main moves, local main does not."""
        other = self.scratch / "other"
        if not other.exists():
            self._git("clone", "-q", str(self.origin), str(other), cwd=self.scratch)
            self._git("config", "user.email", "other@example.invalid", cwd=other)
            self._git("config", "user.name", "Other", cwd=other)
            self._git("config", "commit.gpgsign", "false", cwd=other)
        for rel, text in files.items():
            path = other / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self._git("add", "-A", cwd=other)
        self._git("commit", "-q", "-m", message, cwd=other)
        self._git("push", "-q", "origin", "main", cwd=other)
        self.git("fetch", "-q", "origin")

    def merge_origin_main(self) -> None:
        self.git("merge", "-q", "--no-edit", "origin/main")

    # -- real records ---------------------------------------------------
    def write(self, rel: str, text: str) -> Path:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read(self, rel: str) -> bytes:
        return (self.repo / rel).read_bytes()

    @staticmethod
    def ticket_text(title: str, status: str, phases: dict, source_ac: str | None, body: str) -> str:
        front: dict = {"title": title, "status": status, "agents": dict(phases)}
        if source_ac:
            front["source_ac"] = source_ac
        dumped = yaml.safe_dump(front, sort_keys=False, default_flow_style=False)
        return f"---\n{dumped}---\n\n# {title}\n\n{body}\n"

    def write_ticket(
        self, rel: str, *, status: str = "todo", phases: dict | None = None,
        source_ac: str | None = None, body: str = "original wording",
    ) -> str:
        phases = SIGNED if phases is None else phases
        self.write(rel, self.ticket_text(Path(rel).stem, status, phases, source_ac, body))
        return rel

    def write_ac(self, ac_id: str, *, work_status: str = "todo", covered_by=None, note: str = "") -> str:
        data: dict = {
            "id": ac_id, "title": f"fixture {ac_id}", "status": "active", "level": "L3",
            "work_status": work_status,
        }
        if covered_by:
            data["covered_by"] = list(covered_by)
        if note:
            data["notes"] = note
        rel = ac_rel(ac_id)
        self.write(rel, yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
        return rel

    def ticket_status(self, rel: str) -> str:
        text = (self.repo / rel).read_text(encoding="utf-8")
        return str(yaml.safe_load(text.split("---", 2)[1]).get("status"))

    def ac_status(self, ac_id: str) -> str:
        return str(yaml.safe_load((self.repo / ac_rel(ac_id)).read_text(encoding="utf-8")).get("work_status"))

    def snapshot(self) -> dict[str, str]:
        """rel path -> status for every ticket and every AC record in the working tree."""
        out: dict[str, str] = {}
        for path in sorted((self.repo / "tickets").rglob("*.md")):
            rel = path.relative_to(self.repo).as_posix()
            out[rel] = self.ticket_status(rel)
        for path in sorted((self.repo / "docs" / "acceptance-criteria").rglob("*.yaml")):
            rel = path.relative_to(self.repo).as_posix()
            out[rel] = str(yaml.safe_load(path.read_text(encoding="utf-8")).get("work_status"))
        return out

    # -- the module under test ------------------------------------------
    def _run(self, argv: list[str], env_extra: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(MODULE), *argv],
            cwd=self.scratch, env={**self.env, **(env_extra or {})},
            capture_output=True, text=True, timeout=180, check=False,
        )

    def derive_proc(self, *, branch: str, base_ref: str = "origin/main", worktree: Path | None = None):
        return self._run([
            "derive", "--worktree", str(worktree or self.repo), "--branch", branch,
            "--base-ref", base_ref,
        ])

    def derive(self, **kw) -> dict:
        return as_json(self.case, self.derive_proc(**kw))

    def close_proc(
        self, set_file: str, *, scripts_root: Path | None = None, extra_argv: list[str] | None = None,
        env_extra: dict | None = None,
    ):
        return self._run([
            "close", "--worktree", str(self.repo), "--set-file", set_file,
            "--scripts-root", str(scripts_root or SCRIPTS), *(extra_argv or []),
        ], env_extra=env_extra)

    def close(self, set_file: str, **kw) -> dict:
        return as_json(self.case, self.close_proc(set_file, **kw))

    def leaky_scripts(self, leaks: list[dict]) -> Path:
        """A scripts root whose closers delegate to the real ones, then also write `leaks`."""
        root = self.scratch / "leaky_scripts"
        (root / "ac_store").mkdir(parents=True, exist_ok=True)
        pairs = (
            (root / "set_ticket_status.py", SCRIPTS / "set_ticket_status.py", "ticket"),
            (root / "ac_store" / "mark_ac_done.py", SCRIPTS / "ac_store" / "mark_ac_done.py", "ac"),
        )
        for wrapper, real, kind in pairs:
            wrapper.write_text(_WRAPPER.format(real=str(real), kind=kind), encoding="utf-8")
            (wrapper.parent / "leak.json").write_text(json.dumps(leaks), encoding="utf-8")
        return root

    # -- the shared commit step ------------------------------------------
    def commit_via_step(self, paths: list[str], run: str = "finalize-epic-alpha-20261015") -> dict:
        message = self.scratch / "closure-message.txt"
        message.write_text("chore(tickets): close tickets and source ACs\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(COMMIT_STEP), "--message-file", str(message), "--supervised",
             "--run", run, *paths],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=120, check=False,
        )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.case.fail(f"commit step stdout was not JSON: {proc.stdout!r} {proc.stderr[-300:]!r}")


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

X = f"{INBOX}/TICKET-X.md"
Y = f"{INBOX}/TICKET-Y.md"
Z = f"{INBOX}/TICKET-Z.md"
Q = f"{INBOX}/TICKET-Q.md"


def ba_store(
    case: unittest.TestCase, *, branch: str = "feat-close-x", record: bool = True,
    merged: bool = False, q_in_passing: bool = False, x_changed: bool = True,
    x_status: str = "todo", docs_only: bool = False,
) -> Store:
    """The BA background of BO-400e-3-ii: M0, a recorded single-ticket branch, main gains M1.

    Y and Z are 'closable-looking' (todo, every phase signed off) so a wrong set would close them.
    """
    s = Store(case)
    s.write_ticket(X, status=x_status, phases=SIGNED if (x_status == "done" or not x_changed) else NEEDED)
    s.write_ticket(Y, source_ac="BO-9200a-1")
    s.write_ticket(Z, source_ac="BO-9300a-1")
    s.write_ticket(Q, source_ac="BO-9400a-1")
    for ac_id in ("BO-9100a-1", "BO-9200a-1", "BO-9300a-1", "BO-9400a-1"):
        s.write_ac(ac_id)
    s.write("docs/README.md", "docs\n")
    s.commit("M0")
    s.push_main()
    s.new_branch(branch)
    if record:
        s.record_built_for(branch, X)
    if docs_only:
        s.write("docs/note.md", "a docs-only change\n")
        s.commit("docs only")
    else:
        if x_changed:
            body = "reworded" if x_status == "done" else "original wording"
            s.write_ticket(X, status=x_status, phases=SIGNED, source_ac="BO-9100a-1", body=body)
            s.commit("sign off X")
        if q_in_passing:
            s.write_ticket(Q, source_ac="BO-9400a-1", body="a typo fix in passing")
            s.commit("typo fix in Q")
    s.advance_main_elsewhere(
        {Y: s.ticket_text("TICKET-Y", "todo", SIGNED, "BO-9200a-1", "edited on main only"),
         ac_rel("BO-9200a-1"): yaml.safe_dump(
             {"id": "BO-9200a-1", "title": "fixture BO-9200a-1", "status": "active", "level": "L3",
              "work_status": "todo", "notes": "edited on main only"}, sort_keys=False)},
        "M1",
    )
    if merged:
        s.merge_origin_main()
    return s


ALPHA = f"{EPICS}/EPIC-Alpha"
BETA = f"{EPICS}/EPIC-Beta"
A01, A02, A03, A04 = (f"{ALPHA}/alpha-0{n}.md" for n in (1, 2, 3, 4))
B01 = f"{BETA}/beta-01.md"
KEEP = f"{ALPHA}/alpha-keep.md"


def epic_store(
    case: unittest.TestCase, *, branch: str = "EPIC-Alpha", alpha01: str | None = None,
    parent: bool = True, dirty: bool = False, touch_beta: bool = False,
    touch_other_ac: bool = False, keep_ticket: bool = False, alpha03: bool = False,
) -> Store:
    """EPIC-Alpha: the branch signs off alpha-02 (source BO-9100a-2) and nothing else by default.

    alpha01: None = untouched, 'closable' = branch re-words it (every phase signed), 'refused'
    = branch re-words it while 'pull-request' is still needed (the real checker refuses it).
    dirty: someone else's uncommitted edits to beta-01 and BO-9200a-1 sit in the working tree.
    alpha03: the branch also re-words alpha-03 (todo, every phase signed, source BO-9100a-3).
    """
    s = Store(case)
    s.write_ticket(A01, status="todo", phases=SIGNED, source_ac="BO-9100a-1")
    s.write_ticket(A02, status="todo", phases=NEEDED, source_ac="BO-9100a-2")
    s.write_ticket(A03, status="in_progress", phases=SIGNED, source_ac="BO-9100a-3")
    s.write_ticket(A04, status="done", phases=SIGNED)
    s.write_ticket(B01, status="todo", phases=SIGNED, source_ac="BO-9200a-1")
    if keep_ticket:
        s.write_ticket(KEEP, status="todo", phases=SIGNED)
    s.write_ac("BO-9100a-1")
    s.write_ac("BO-9100a-2")
    s.write_ac("BO-9100a-3", work_status="in_progress")
    s.write_ac("BO-9200a-1")
    s.write_ac("BO-9500a-1")
    if parent:
        s.write_ac("BO-9100a", covered_by=["BO-9100a-1", "BO-9100a-2", "BO-9100a-3"])
    s.write("docs/README.md", "docs\n")
    s.commit("M0")
    s.push_main()
    s.new_branch(branch)
    s.write_ticket(A02, status="todo", phases=SIGNED, source_ac="BO-9100a-2")
    if alpha01 == "closable":
        s.write_ticket(A01, status="todo", phases=SIGNED, source_ac="BO-9100a-1", body="reworded")
    elif alpha01 == "refused":
        s.write_ticket(A01, status="todo", phases=PR_NEEDED, source_ac="BO-9100a-1", body="reworded")
    if alpha03:
        s.write_ticket(A03, status="todo", phases=SIGNED, source_ac="BO-9100a-3", body="reworded")
    if touch_beta:
        s.write_ticket(B01, status="todo", phases=SIGNED, source_ac="BO-9200a-1", body="reworded")
    if touch_other_ac:
        s.write_ac("BO-9500a-1", note="reworded on the branch")
    s.commit("branch work")
    if dirty:
        for rel in (B01, ac_rel("BO-9200a-1")):
            path = s.repo / rel
            path.write_text(path.read_text(encoding="utf-8") + "\n# someone else's half-finished edit\n",
                            encoding="utf-8")
    return s
