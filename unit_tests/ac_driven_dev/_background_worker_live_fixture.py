"""Disposable fixture and local-only publication adapter for opt-in live tests."""

import json
from pathlib import Path
import subprocess
import sys

import yaml

from scripts.background_worker.git_ops import GitOps
from scripts.background_worker.local_outcome import event_diagnostics, parse_events
from scripts.background_worker.execution_boundary import ExecutorError, safe_output


def traced_invocation(invoke, destination):
    """Test-only opt-in trace; no reasoning, command arguments or successful output."""
    def traced(argv, **kwargs):
        try:
            result = invoke(argv, **kwargs)
        except ExecutorError as exc:
            if "--json" in argv:
                evidence = getattr(exc, "evidence", {}) or {}
                entry = (dict(evidence) if evidence.get("kind") == "local_harness"
                         else event_diagnostics(parse_events(evidence.get("stdout", ""))))
                entry["transport_error"] = safe_output(str(exc))[-500:]
                with destination.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(entry) + "\n")
            raise
        if "--json" in argv:
            entry = event_diagnostics(parse_events(result.stdout))
            entry["returncode"] = result.returncode
            with destination.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry) + "\n")
        return result
    return traced


def command(argv, cwd, *, input_text=None):
    try:
        return subprocess.run(argv, cwd=cwd, input=input_text, text=True,
                              capture_output=True, check=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        raise


def git(repo, *args):
    return command(["git", *args], repo).stdout.strip()


def first_ac_commit(repo, base_sha, ac_id):
    """Find initial coordinator commit, independent of overwritten repair evidence."""
    expected = "feat: implement " + ac_id + " in background worker"
    history = git(repo, "log", "--reverse", "--first-parent", "--format=%H%x00%s",
                  base_sha + "..HEAD")
    for line in history.splitlines():
        sha, subject = line.split("\0", 1)
        if subject == expected:
            return sha
    raise AssertionError("Missing initial coordinator commit for " + ac_id)


def fixture(root, *, needs_input=False):
    """Write only inside a fresh pytest temporary root; never use the real backlog."""
    repo, remote = root / "consumer", root / "origin.git"
    repo.mkdir()
    remote.mkdir()
    git(remote, "init", "--bare")
    git(repo, "init")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "config", "user.name", "Leafcutter Live Acceptance")
    git(repo, "config", "user.email", "live-acceptance@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    files = {
        ".gitignore": ".leafcutter/\n__pycache__/\n.pytest_cache/\n*.pyc\n",
        "labels.py": "def normalize_label(value):\n    raise NotImplementedError('Implement the approved AC')\n",
        "tests/test_labels.py": (
            "from labels import normalize_label\n\n"
            "def test_collapse_whitespace():\n"
            "    assert normalize_label('  blue\\t  sky \\n') == 'blue sky'\n\n"
            "def test_preserve_case_and_punctuation():\n"
            "    assert normalize_label('  Hello, WORLD! ') == 'Hello, WORLD!'\n"
        ),
        "README.md": "# Disposable label normalizer acceptance fixture\n",
    }
    files["tools/format_labels.py"] = (
        "import json, pathlib, subprocess, sys\n"
        "root = pathlib.Path(__file__).resolve().parents[1]\n"
        "target = root / 'labels.py'\n"
        "if not target.is_file() or target.is_symlink():\n"
        "    raise SystemExit('Expected one regular labels.py file')\n"
        "before = target.read_bytes()\n"
        "if not before.strip():\n"
        "    raise SystemExit('Refusing empty formatting target')\n"
        "result = subprocess.run([sys.executable, '-m', 'ruff', 'format', '--isolated', '--no-cache', str(target)], cwd=root)\n"
        "if result.returncode:\n"
        "    raise SystemExit(result.returncode)\n"
        "after = target.read_bytes()\n"
        "compile(after, str(target), 'exec')\n"
        "print(json.dumps({'leafcutter_check': {'passed': True, 'inspected': 1}}))\n"
    )
    files["worker-checks.json"] = json.dumps({"checks": [
        [sys.executable, "tools/format_labels.py"],
        [sys.executable, "-m", "pytest", "-q"],
    ]}, indent=2) + "\n"
    common = {"status": "active", "readiness": "approved", "req_status": "approved",
              "work_status": "todo", "priority": "low", "depends_on": []}
    records = [
        {"id": "LIVE-100", "level": "L0", "criteria": "Deliver a documented, tested label normalizer."},
        {"id": "LIVE-100a", "level": "L1", "parent": "LIVE-100", "depends_on": ["LIVE-100"],
         "criteria": "Implement normalize_label(value: str) in labels.py. Keep existing tests intact. Document usage in README.md."},
        {"id": "LIVE-100a-1", "level": "L2", "parent": "LIVE-100a", "depends_on": ["LIVE-100a"],
         "estimated_complexity": "S",
         "criteria": "Trim surrounding whitespace and collapse all internal whitespace to one ASCII space, preserving case and punctuation. Make both existing pytest cases pass without deleting or weakening them. Do not implement the blank-input rejection until LIVE-100a-2."},
        {"id": "LIVE-100a-2", "level": "L2", "parent": "LIVE-100a", "depends_on": ["LIVE-100a", "LIVE-100a-1"],
         "estimated_complexity": "S",
         "criteria": "Retain normalized nonempty labels. For empty or whitespace-only input raise ValueError with message 'label must not be blank'. Add tests/test_blank_labels.py with tests for empty string, spaces, tabs and newlines. Preserve every prior test. Document the exception in README.md."},
    ]
    if needs_input:
        records[2]["required_inputs"] = [{
            "id": "internal-whitespace-policy",
            "question": "Choose internal whitespace behavior for normalize_label (collapse or preserve).",
            "choices": ["collapse", "preserve"],
        }]
        files["label-policy.json"] = json.dumps({
            "internal_whitespace": None,
            "allowed_choices": {
                "collapse": "Replace each internal whitespace run with one ASCII space.",
                "preserve": "Keep internal whitespace exactly as supplied.",
            },
        }, indent=2) + "\n"
        files["tests/test_labels.py"] = (
            "from labels import normalize_label\n\n"
            "def test_trim_surrounding_whitespace():\n"
            "    assert normalize_label('  blue sky \t') == 'blue sky'\n\n"
            "def test_preserve_case_and_punctuation():\n"
            "    assert normalize_label('  Hello, WORLD! ') == 'Hello, WORLD!'\n"
        )
        records[2]["criteria"] = (
            "Trim surrounding whitespace, preserving case and punctuation. Read label-policy.json "
            "to determine the required internal-whitespace behavior. Both allowed choices are valid; "
            "there is no default. If the policy choice is null and no saved user answer resolves it, "
            "return needs_input asking the user to choose collapse or preserve before changing files. "
            "Initial tests cover behavior shared by both choices and cannot resolve the missing choice. "
            "Once an explicit saved answer resolves the choice, implement that choice without asking again. "
            "Preserve existing tests, add tests for the selected behavior, and document it. "
            "Do not implement blank-input rejection until LIVE-100a-2."
        )
    for record in records:
        record = {**common, **record}
        files["docs/acceptance-criteria/live/" + record["id"] + ".yaml"] = yaml.safe_dump(record)
    for relative, body in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    git(repo, "add", "--all")
    tree = git(repo, "write-tree")
    # Fixture-only plumbing avoids invoking project commit hooks during setup.
    sha = git(repo, "commit-tree", tree, "-m", "Seed disposable live acceptance fixture")
    git(repo, "update-ref", "refs/heads/main", sha)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nset -eu\ngit diff --cached --check\n"
                    "mkdir -p .leafcutter\nprintf 'checked\\n' >> .leafcutter/live-hook.log\n",
                    encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return repo, remote, files["tests/test_labels.py"]


class LocalPublication(GitOps):
    """Exercise real commit/push, replacing only GitHub PR creation with a receipt."""

    def __init__(self, repo, settings, remote, receipt):
        super().__init__(repo, settings)
        self.remote = Path(remote).resolve()
        self.receipt = receipt

    def publish(self, run, expected_sha):
        workspace = self.assert_workspace(run)
        assert Path(self.git(workspace, "remote", "get-url", "origin")).resolve() == self.remote
        assert self.head(workspace) == expected_sha
        assert not self.git(workspace, "status", "--porcelain")
        assert run["payload"]["validated_sha"] == run["payload"]["reviewed_sha"] == expected_sha
        assert self.target_head() == run["payload"]["base_sha"]
        branch = run["payload"]["branch"]
        self.hooked_git(workspace, workspace, "push", "--set-upstream", "origin", branch)
        remote_sha = git(self.remote, "rev-parse", "refs/heads/" + branch)
        assert remote_sha == expected_sha
        self.receipt.write_text(json.dumps({
            "boundary": "local-bare-origin-only-no-GitHub-PR",
            "remote": str(self.remote), "branch": branch, "sha": remote_sha,
        }), encoding="utf-8")
        return "https://example.invalid/local-acceptance/" + run["id"]

    def publication_destination(self, workspace):
        assert Path(self.git(workspace, "remote", "get-url", "origin")).resolve() == self.remote
        return {"remote": "origin", "base": "main", "repository": self.remote.as_uri()}
