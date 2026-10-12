"""
MODULE: _inf_500d_4_helpers
GOAL: Shared layout/run/snapshot helpers for the INF-500d-4-i / -iv / -v test
    files (one durable operational log root for every workspace).
BUSINESS CONTEXT: Those three files all need the same thing: a temp
    "deployed install" (the shape ``.leafcutter/`` has in a worktree), a
    declaration written the way the build writes it, and subprocess runs of the
    deployed writers and readers from a chosen current directory.
ARCHITECTURE: No build.py is spawned (a build is ~60s). A deployed install is
    assembled by copying whole source directories to the paths the build puts
    them at, so a new sibling module added next to a writer or reader is carried
    into the layout automatically instead of failing the tests for an unrelated
    reason. The declaration comes from the REAL build helper
    (``build_phases_knowledge.build_knowledge_sink_declaration`` with the REAL
    ``build_log_root`` input), never a hand-typed literal. Whether a NEW module
    is in the real deploy manifest is a different question and is proved against
    the real shared layout (``test_emit_event_finds_the_declaration_in_the_real_
    deployed_layout``).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_log_root import CONFIG_KEY  # noqa: E402
from build_phases_knowledge import build_knowledge_sink_declaration  # noqa: E402

# deployed relative path -> source directory it is copied from (whole directory).
_TREES: dict[str, Path] = {
    "scripts/feedback": REPO_ROOT / "templates" / "scripts" / "feedback",
    "scripts/knowledge": REPO_ROOT / "scripts" / "knowledge",
    "scripts/agent-health": REPO_ROOT / "scripts" / "agent-health",
    "skills/agent-telemetry": REPO_ROOT / "templates" / "skills" / "agent-telemetry",
    "skills/feedback-analysis": REPO_ROOT / "templates" / "skills" / "feedback-analysis",
    "hooks": REPO_ROOT / "templates" / "hooks",
}
_CATEGORIES_SRC = REPO_ROOT / "templates" / "config" / "feedback_categories.yaml"

RUN_TIMEOUT = 60
FEEDBACK_ID_RE = r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$"


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------

def deploy_install(project: Path, *, git: bool = True) -> Path:
    """Create ``project`` as a worktree-shaped project with a deployed ``.leafcutter``.

    Returns the output root (``project/.leafcutter``). No declaration is
    written; call :func:`declare`. ``.claude/skills`` and ``.claude/hooks`` are
    the same relative symlinks the build creates, because the telemetry skill
    and the guard hook are invoked through them. ``git=True`` adds a ``.git``
    file (a worktree's shape) so the guard hook can find its repository root.
    """
    out = project / ".leafcutter"
    for rel, src in _TREES.items():
        shutil.copytree(src, out / rel, ignore=shutil.ignore_patterns("__pycache__"))
    (out / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(_CATEGORIES_SRC, out / "config" / "feedback_categories.yaml")
    claude = project / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    os.symlink("../.leafcutter/skills", claude / "skills")
    os.symlink("../.leafcutter/hooks", claude / "hooks")
    if git:
        (project / ".git").write_text("gitdir: /nonexistent/worktree-gitdir\n", encoding="utf-8")
    return out


def declare(out_root: Path, log_root: Path | None = None) -> Path:
    """Write ``config/knowledge_sink.json`` with the REAL build helper.

    ``log_root=None`` is an ordinary (plain-checkout) build, which declares
    ``<project>/debugging/logs``. A path is the inherited root a worktree
    bootstrap passes to the build as ``--log-root``.
    """
    config = {CONFIG_KEY: str(log_root)} if log_root is not None else {}
    build_knowledge_sink_declaration(out_root, config, False, True)
    return out_root / "config" / "knowledge_sink.json"


def read_declaration(out_root: Path) -> dict:
    return json.loads((out_root / "config" / "knowledge_sink.json").read_text(encoding="utf-8"))


def rewrite_declaration(out_root: Path, **changes: object) -> Path:
    """Round-trip the real declaration, replacing (or, for ``None``, dropping) keys."""
    data = read_declaration(out_root)
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    path = out_root / "config" / "knowledge_sink.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def declaration_path(out_root: Path) -> Path:
    return out_root / "config" / "knowledge_sink.json"


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------

def _env(tmpdir: Path, extra: dict[str, str] | None = None, path: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["TMPDIR"] = str(tmpdir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in ("INLINE_WORK_GUARD_MODE", "CLAUDE_SESSION_ID"):
        env.pop(key, None)
    if path is not None:
        env["PATH"] = path
    env.update(extra or {})
    return env


make_env = _env  # public alias for tests that must run a shell command themselves


def run_py(
    script: Path,
    args: list[str],
    cwd: Path,
    tmpdir: Path,
    *,
    stdin: str | None = None,
    env_extra: dict[str, str] | None = None,
    path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``python -B script args`` from ``cwd`` with TMPDIR confined to ``tmpdir``."""
    return subprocess.run(
        [sys.executable, "-B", str(script), *args],
        capture_output=True, text=True, cwd=str(cwd), timeout=RUN_TIMEOUT, check=False,
        input=stdin, env=_env(tmpdir, env_extra, path),
    )


def run_code(
    code: str, args: list[str], cwd: Path, tmpdir: Path, *, env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``python -B -c code args`` in a FRESH process (never importlib.reload)."""
    return subprocess.run(
        [sys.executable, "-B", "-c", code, *args],
        capture_output=True, text=True, cwd=str(cwd), timeout=RUN_TIMEOUT, check=False,
        env=_env(tmpdir, env_extra),
    )


def popen_py(script: Path, args: list[str], cwd: Path, tmpdir: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-B", str(script), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(cwd),
        env=_env(tmpdir),
    )


def submit_script(out_root: Path) -> Path:
    return out_root / "scripts" / "feedback" / "submit_feedback.py"


def submit_args(
    *, note: str = "probe", tags: str | None = None, category: str = "complete",
    phase: str = "python-coder", jsonl: Path | None = None,
) -> list[str]:
    args = ["--ticket", "tickets/00_inbox/TICKET-inf-500d-4-probe.md", "--phase", phase,
            "--category", category, "--note", note]
    if tags:
        args += ["--tags", tags]
    if jsonl is not None:
        args += ["--jsonl", str(jsonl)]
    return args


def submit(
    out_root: Path, cwd: Path, tmpdir: Path, *, env_extra: dict[str, str] | None = None,
    path: str | None = None, **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """File one report through the deployed ``submit_feedback.py`` CLI."""
    return run_py(submit_script(out_root), submit_args(**kwargs), cwd, tmpdir,  # type: ignore[arg-type]
                  env_extra=env_extra, path=path)


def seed_reports(
    out_root: Path, cwd: Path, tmpdir: Path, jsonl: Path, count: int, *, tag: str,
    category: str = "complete", phase: str = "python-coder",
) -> list[str]:
    """File ``count`` reports through the REAL producer into an explicit ``jsonl``; return the ids."""
    ids: list[str] = []
    for index in range(count):
        proc = submit(out_root, cwd, tmpdir, jsonl=jsonl, note=f"{tag} {index}", tags=tag,
                      category=category, phase=phase)
        assert proc.returncode == 0, f"seeding failed: {proc.stderr}"
        ids.append(proc.stdout.strip())
    return ids


def read_records(path: Path) -> list[dict]:
    """Parse every line of a JSONL file; a line that does not parse fails the caller."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# observation
# ---------------------------------------------------------------------------

def snapshot(*roots: Path) -> set[str]:
    """Every file and directory under the roots (minus ``__pycache__``), as strings."""
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        seen.add(str(root))
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in (*dirnames, *filenames):
                seen.add(os.path.join(dirpath, name))
    return seen


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stderr_lines(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in proc.stderr.splitlines() if line.strip()]


def empty_bin_path(base: Path) -> str:
    """A PATH holding no tools at all (git cannot be found on it)."""
    empty = base / "empty-bin"
    empty.mkdir(parents=True, exist_ok=True)
    return str(empty)
