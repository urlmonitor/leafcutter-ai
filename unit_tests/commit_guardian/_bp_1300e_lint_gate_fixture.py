"""
MODULE: unit_tests/commit_guardian/_bp_1300e_lint_gate_fixture.py
COVERS: BP-1300e-1 and children -i, -ii, -iii, -iv, -v (shared fixture -- no tests)

GOAL: Build a REAL, isolated git repository wired so an ORDINARY `git commit`
    -- installed by a real `pre-commit install`, no extra command or flag --
    routes through the DEPLOYED `check_lint_gate.py` of the session's shared
    reference layout via its real `run_hook.py`, with `.pre-commit-config.yaml`
    carrying `check-lint-gate` ALONE so no unrelated hook can fail the commit.
    Modelled on `_ge_127a_1_ordinary_commit_fixture.py`.

REAL ARTIFACTS, NOT LOOKALIKES: the repository's real `ruff.toml` and real
    `leafcutter-lint.json` are copied byte for byte; the hook stanza is copied
    from the `.pre-commit-config.yaml` build.py GENERATED into the shared layout
    (only the script path tokens are pointed at the layout by absolute path);
    JSON is written with `json.dumps`, never typed.

PRE-COMMIT STASHES UNSTAGED CHANGES before it runs hooks, so a plain `git commit`
    cannot tell the staged blob from the working copy. Tests that must tell them
    apart ALSO run the deployed gate directly (``gate_json``) in the same state.

DECISION HISTORY
- 2026-10-12 [test-writer/BP-1300e-1]: Created. Every failure here is an
    AssertionError inside the test body (never a pytest fixture error), so a
    missing gate reads as an assertion red, not as an absence red.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bp_1300e_lint_gate_env as envmod  # noqa: E402
from _bp_1300e_lint_gate_env import PYTHON, hook_env  # noqa: E402,F401

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_GUARDIAN = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
HOOK_ID = "check-lint-gate"
HOOK_TIMEOUT = 180
GIT_TIMEOUT = 60
REAL = "real"
TREES = ("scripts", "tests", "unit_tests", "kernel")


@dataclass
class Repo:
    root: Path
    layout: Path
    stanza: dict


# ── source builders (line numbers are exact) ──────────────────────────────────
def _filler(n: int) -> list[str]:
    return [f"v{i:03d} = {i}" for i in range(1, n + 1)]


def e741_source(line: int = 12) -> str:
    """Module whose only violation is variable `l` (E741) at *line*."""
    return "\n".join([*_filler(line - 1), "l = 1"]) + "\n"


def ble001_source(line: int = 30) -> str:
    """Module whose only violation is `except Exception:` (BLE001) at *line*."""
    body = [*_filler(line - 3), "try:", "    pass", "except Exception:", "    pass"]
    return "\n".join(body) + "\n"


def try_only_source() -> str:
    """Module whose only finding is TRY300 (line 4) -- not E/F/E722/BLE001."""
    return "def f(x):\n    try:\n        x = int(x)\n        return x\n    except ValueError:\n        return 0\n"


def f841_source(edit_value: int = 0) -> str:
    """F841 (unused local) at line 40; line 90 is the edit target `edit_target = <v>`."""
    lines = _filler(38) + ["def holder():", "    unused = 1"]
    lines += [f"w{i:03d} = {i}" for i in range(41, 90)] + [f"edit_target = {edit_value}"]
    return "\n".join(lines) + "\n"


def used_variable_source(use: str) -> str:
    """`value` is used by the return; with use='0' it is NOT -> F841 at line 6."""
    return "\n".join([*_filler(4), "def g():", "    value = 1", f"    return {use}"]) + "\n"


CLEAN = "VALUE = 1\n"


# ── process plumbing ─────────────────────────────────────────────────────────
def sh(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = GIT_TIMEOUT,
       stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
                          check=False, env=env if env is not None else envmod.base_env(), input=stdin)


def git(args: list[str], cwd: Path, env: dict | None = None, timeout: int = GIT_TIMEOUT):
    return sh(["git", *args], cwd, env=env, timeout=timeout)


def out(proc: subprocess.CompletedProcess) -> str:
    return (proc.stdout or "") + (proc.stderr or "")


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def stage(repo: Repo, *rels: str) -> None:
    done = git(["add", "--", *rels], repo.root)
    assert done.returncode == 0, f"git add failed: {out(done)}"


def stage_files(repo: Repo, files: dict[str, str]) -> None:
    for rel, text in files.items():
        write(repo.root, rel, text)
    stage(repo, *files)


def baseline_commit(repo: Repo, files: dict[str, str], message: str = "baseline") -> None:
    """Commit *files* with hooks switched off -- test setup, not the subject."""
    for rel, text in files.items():
        write(repo.root, rel, text)
    stage(repo, *files)
    done = git(["-c", "core.hooksPath=/nonexistent", "commit", "-q", "-m", message], repo.root)
    assert done.returncode == 0, f"baseline commit failed: {out(done)}"


def commit(repo: Repo, work: Path, message: str = "change", *, args: tuple = (), ruff: str = f"stub:{envmod.PIN}",
           path: str = "inherit", git_wrapper: Path | None = None) -> subprocess.CompletedProcess:
    """A REAL ordinary `git commit -m` -- the hook chain runs, nothing is invoked by hand."""
    env = hook_env(work, ruff=ruff, path=path, git_wrapper=git_wrapper)
    return git(["commit", "-m", message, *args], repo.root, env=env, timeout=HOOK_TIMEOUT)


def subjects(repo: Repo) -> list[str]:
    done = git(["log", "--format=%s"], repo.root)
    return done.stdout.split("\n") if done.returncode == 0 else []


def commit_count(repo: Repo) -> int:
    done = git(["rev-list", "--count", "HEAD"], repo.root)
    return int(done.stdout.strip()) if done.returncode == 0 else 0


def hook_status(text: str, name: str) -> str | None:
    """pre-commit's own per-hook status word: Passed / Failed / Skipped, or None."""
    match = re.search(re.escape(name) + r"[.\s]*(Passed|Failed|Skipped)", text)
    return match.group(1) if match else None


def mentions_finding(text: str, path: str, line: int, code: str) -> bool:
    return re.search(rf"{re.escape(path)}:{line}:\d+:?\s+{code}\b", text) is not None


# ── artifacts ────────────────────────────────────────────────────────────────
def real_declaration() -> dict:
    path = REPO_ROOT / "leafcutter-lint.json"
    assert path.is_file(), f"{path} does not exist: BP-1300e-1-i must create the one declaration"
    return json.loads(path.read_text(encoding="utf-8"))


def widened(decl: dict, tree: str) -> dict:
    """The declaration with one more tree on the first step and nothing else changed."""
    copy = json.loads(json.dumps(decl))
    copy["steps"][0]["paths"] = [*copy["steps"][0]["paths"], tree]
    return copy


def lint_gate_stanza(layout: Path, root: Path, via_symlink: bool) -> dict:
    """The check-lint-gate stanza build.py generated, script tokens pointed at the layout."""
    config = yaml.safe_load((layout / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {h["id"]: h for r in config["repos"] for h in r["hooks"]}
    assert HOOK_ID in hooks, f"generated .pre-commit-config.yaml registers no {HOOK_ID}"
    stanza = dict(hooks[HOOK_ID])
    assert re.search(r"run_hook\.py .*check_lint_gate\.py", stanza["entry"]), stanza["entry"]
    tokens = []
    for token in stanza["entry"].split():
        if token == "python":
            token = PYTHON
        elif "scripts/commit_guardian/" in token and not via_symlink:
            # Keep the spelling build.py GENERATED (`.leafcutter/scripts/...` for a real consumer);
            # only root it at the layout. Re-spelling it via the `scripts/` symlink would test a
            # path no generated hook entry uses.
            assert (layout / token).exists(), f"generated hook token {token!r} is not in the layout"
            token = str(layout / token)
        tokens.append(token)
    stanza["entry"] = " ".join(tokens)
    return stanza


def make_repo(root: Path, layout: Path, *, declaration: object = REAL, ruff_toml: object = REAL,
              requirements: str | None = f"ruff=={envmod.PIN}\n", trees: bool = True,
              files: dict[str, str] | None = None, via_symlink: bool = False,
              link_template_source: bool = False, install: bool = True) -> Repo:
    """A real repo with a baseline commit, then (optionally) the hook installed."""
    root.mkdir(parents=True, exist_ok=True)
    git(["init", "-q", "-b", "main"], root)
    git(["config", "user.email", "test-writer@example.com"], root)
    git(["config", "user.name", "BP-1300e lint-gate fixture"], root)
    git(["config", "core.autocrlf", "false"], root)
    base: dict[str, str] = {"README.md": "# fixture\n"}
    if ruff_toml == REAL:
        base["ruff.toml"] = (REPO_ROOT / "ruff.toml").read_text(encoding="utf-8")
    elif isinstance(ruff_toml, str):
        base["ruff.toml"] = ruff_toml
    if declaration == REAL:
        base["leafcutter-lint.json"] = json.dumps(real_declaration(), indent=2) + "\n"
    elif isinstance(declaration, dict):
        base["leafcutter-lint.json"] = json.dumps(declaration, indent=2) + "\n"
    if requirements is not None:
        base["requirements-dev.txt"] = requirements
    if trees:
        base.update({f"{t}/__init__.py": "" for t in TREES})
    base.update(files or {})
    repo = Repo(root, layout, {})
    baseline_commit(repo, base)
    if via_symlink:
        (root / ".leafcutter").symlink_to(layout / ".leafcutter")
    if link_template_source:
        (root / "templates" / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "templates" / "scripts" / "commit_guardian").symlink_to(TEMPLATE_GUARDIAN)
    if install:
        install_hook(repo, via_symlink)
    return repo


def setup(tmp_path: Path, layout: Path, name: str = "repo", **kwargs) -> tuple[Repo, Path]:
    """(repo, work) -- *work* holds the stub ruff / PATH helper directories."""
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    return make_repo(tmp_path / name, layout, **kwargs), work


def install_hook(repo: Repo, via_symlink: bool = False) -> None:
    repo.stanza = lint_gate_stanza(repo.layout, repo.root, via_symlink)
    config = {"repos": [{"repo": "local", "hooks": [repo.stanza]}]}
    (repo.root / ".pre-commit-config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    done = sh(["pre-commit", "install"], repo.root)
    assert done.returncode == 0, f"pre-commit install failed: {out(done)}"


# ── the deployed gate, run directly ──────────────────────────────────────────
def deployed_dir(layout: Path) -> Path:
    return layout / ".leafcutter" / "scripts" / "commit_guardian"


def run_gate(layout: Path, cwd: Path, *args: str, env: dict | None = None,
             script: Path | None = None) -> subprocess.CompletedProcess:
    target = script or deployed_dir(layout) / "check_lint_gate.py"
    return sh([PYTHON, str(target), *args], cwd, env=env, timeout=HOOK_TIMEOUT)


def parse_payload(text: str) -> dict | None:
    candidates = [text, *[ln for ln in text.splitlines() if ln.lstrip().startswith("{")]]
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def gate_json(layout: Path, cwd: Path, *args: str, env: dict | None = None,
              script: Path | None = None) -> tuple[subprocess.CompletedProcess, dict]:
    """Run the gate with --json; the payload MUST parse (else an AssertionError)."""
    proc = run_gate(layout, cwd, *args, "--json", env=env, script=script)
    payload = parse_payload(proc.stdout)
    assert payload is not None, f"no JSON payload from check_lint_gate.py {args}: {out(proc)!r}"
    return proc, payload


def finding_keys(payload: dict) -> list[tuple]:
    return sorted((f["path"], f["line"], f["code"]) for f in payload["findings"])


# ── CI's own lint command, read from the real workflow ───────────────────────
def ci_lint_gate_tokens() -> list[str]:
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    steps = [s for s in workflow["jobs"]["lint"]["steps"] if "check_lint_gate.py" in str(s.get("run", ""))]
    assert len(steps) == 1, f"ci.yml lint job must have exactly one check_lint_gate.py step, has {len(steps)}"
    tokens = []
    for token in shlex.split(steps[0]["run"]):
        if token == "python":
            token = PYTHON
        elif (REPO_ROOT / token).exists():
            token = str(REPO_ROOT / token)
        tokens.append(token)
    return tokens


def run_ci_lint(repo: Repo, work: Path) -> subprocess.CompletedProcess:
    """EXECUTE the lint job's gate step (as read from ci.yml) inside the fixture."""
    return sh(ci_lint_gate_tokens(), repo.root, env=hook_env(work), timeout=HOOK_TIMEOUT)
