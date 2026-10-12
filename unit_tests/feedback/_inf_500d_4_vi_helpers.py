"""
MODULE: _inf_500d_4_vi_helpers
GOAL: Lift the shell commands out of the DEPLOYED agent/skill prompts and run them
    against a temp declared install, for test_inf_500d_4_vi.py.
BUSINESS CONTEXT: INF-500d-4-vi is about what a prompt makes an agent DO, so the
    tests execute the commands the prompts prescribe instead of grepping for strings.
ARCHITECTURE: Prompt text comes from the shared reference layout's ``.leafcutter``
    (deployed copies). Commands are lifted by line (fences are NOT tracked: some
    prompts nest a bash fence inside another fenced pseudo-code block), their
    ``<placeholders>`` are filled, their ``scripts/<dir>/`` prefix is pointed at a
    temp install from ``_inf_500d_4_helpers.deploy_install`` (the declaration is
    written by the REAL build helper), and ``/tmp/`` redirects are confined to a
    temp dir. No build.py is spawned.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h

# surface name -> deployed path under <layout>/.leafcutter  (the eleven declared prompts)
_DECLARED = {
    "ticket-supervisor": "agents/ticket-supervisor.md",
    "epic-supervisor": "agents/epic-supervisor.md",
    "building-epics": "skills/building-epics/SKILL.md",
    "agent-telemetry": "skills/agent-telemetry/SKILL.md",
    "retrospective-agent": "agents/retrospective-agent.md",
    "signoff": "skills/signoff/SKILL.md",
    "user-surface-smoker": "agents/user-surface-smoker.md",
    "feedback-analyst": "agents/feedback-analyst.md",
    "feedback-review": "skills/feedback-review/SKILL.md",
    "feedback-analysis": "skills/feedback-analysis/SKILL.md",
    "feedback-report": "commands/feedback-report.md",  # templates/workflows/feedback-report.md, deployed
}
_SCAN_DIRS = ("agents", "skills", "commands", "workflows", "gemini")

_ARG_FLAGS = r"(?:--jsonl|--log|--feedback|--telemetry|--sink|--log-path|--output|--out)"
# Every workspace-relative ``debugging/logs/<file>`` counts -- knowledge_emissions.jsonl included. It was once
# exempted ("it belongs to the knowledge surfaces"), and that exemption is exactly what let the harvester prompt
# keep checking ``ls debugging/logs/knowledge_emissions.jsonl`` and passing ``--sink debugging/logs/...`` in an
# inherited-root worktree, where the file is not there and the agent reports "nothing to harvest" (review H-5).
_REL = r"(?:\./)?debugging[/\\]logs[/\\][^\s\"'`)\]]+"
_Q = r"[\"'`]?"
_DESTINATION_PATTERNS = {
    "flag argument": re.compile(rf"{_ARG_FLAGS}(?:\s+|=)\s*{_Q}{_REL}"),
    "redirect": re.compile(rf">>?\s*{_Q}{_REL}"),
    "assignment": re.compile(rf"\b\w+\s*=\s*{_Q}{_REL}"),
    "append instruction": re.compile(rf"\bappend\w*\b[^\n]{{0,60}}?{_Q}{_REL}", re.IGNORECASE),
}
_ANY_MENTION = re.compile(r"debugging[/\\]+logs")

_WRITER_TOOLS = ("submit_feedback", "emit_event")
_READER_TOOLS = ("aggregate", "list_tags", "trend_report", "generate_health_report", "resolve_feedback")
_TOOL_RE = re.compile(r"\b(" + "|".join((*_WRITER_TOOLS, *_READER_TOOLS)) + r")\.py\b")
_PLACEHOLDER_RE = re.compile(r"<([A-Za-z_]+)>")
_OPTIONAL_RE = re.compile(r"\[[^\]]*\]")
_SCRIPT_PREFIX_RE = re.compile(r"(?:[\w.\-]+/)*(scripts/(?:feedback|agent-health)/)")

_PLACEHOLDERS = {
    "ticket_path": "tickets/00_inbox/TICKET-inf-500d-4-probe.md",
    "new_ticket_path": "tickets/00_inbox/TICKET-inf-500d-4-probe.md",
    "ticket_basename": "TICKET-inf-500d-4-probe.md",
    "agent_name": "python-coder",
    "category": "complete",
    "tags_or_omit_flag": "probe-tag",
    "failing_agent": "python-coder",
    "reviewer_agent": "pr-reviewer",
    "count": "1",
    "cap_kind": "retry-cap",
}

# Floors on how many commands each surface must still carry. They are today's counts: deleting a
# command to make a destination disappear is a wrong version of this change, not a fix.
_MIN_WRITERS = {
    ("ticket-supervisor", "submit_feedback"): 4,
    ("building-epics", "emit_event"): 8,
    ("agent-telemetry", "emit_event"): 1,
    ("signoff", "submit_feedback"): 1,
}


@dataclass(frozen=True)
class Cmd:
    surface: str
    line: int
    tool: str
    raw: str

    @property
    def where(self) -> str:
        return f"{self.surface}:{self.line}"


# ---------------------------------------------------------------------------
# reading the deployed prompts
# ---------------------------------------------------------------------------

def _deployed_root(layout: Path) -> Path:
    root = Path(layout) / ".leafcutter"
    assert root.is_dir(), f"the shared layout has no deployed .leafcutter at {root}"
    return root


def _declared_prompts(layout: Path) -> dict[str, str]:
    root = _deployed_root(layout)
    prompts: dict[str, str] = {}
    for surface, rel in _DECLARED.items():
        path = root / rel
        assert path.is_file(), f"declared surface {surface} is not deployed at {path}"
        prompts[surface] = path.read_text(encoding="utf-8")
    return prompts


def _all_deployed_surfaces(layout: Path) -> dict[str, str]:
    root = _deployed_root(layout)
    found: dict[str, str] = {}
    for sub in _SCAN_DIRS:
        base = root / sub
        if not base.is_dir():
            continue
        for dirpath, _dirs, files in os.walk(base, followlinks=True):
            for name in files:
                if name.endswith(".md"):
                    path = Path(dirpath) / name
                    found[str(path.relative_to(root))] = path.read_text(encoding="utf-8", errors="replace")
    return found


def _destination_hits(text: str) -> list[tuple[int, str, str]]:
    """(line number, kind, line) for every line that names a workspace-relative log destination."""
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in _DESTINATION_PATTERNS.items():
            if pattern.search(line):
                hits.append((number, kind, line.strip()))
                break
    return hits


def _inspect(surfaces: dict[str, str]) -> tuple[int, list[str]]:
    """Scan ``surfaces``; return (how many were inspected, one message per offending line).

    Fails (raises AssertionError) when nothing was inspected: a scan with no input reports perfect
    agreement, which is exactly the failure mode this guards.
    """
    assert surfaces, "the scan inspected ZERO surfaces; a scan that looks at nothing proves nothing"
    offences = []
    for name, text in sorted(surfaces.items()):
        for number, kind, line in _destination_hits(text):
            offences.append(f"{name}:{number} [{kind}] {line[:160]}")
    return len(surfaces), offences


# ---------------------------------------------------------------------------
# lifting the shell commands out of a prompt
# ---------------------------------------------------------------------------

def _commands(surface: str, text: str) -> list[Cmd]:
    """Every line that IS a ``python ... <tool>.py ...`` command, backslash continuations joined."""
    found: list[Cmd] = []
    pending, start = "", 0
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            pending, start = "", 0
            continue
        if not pending:
            start = number
        if line.rstrip().endswith("\\"):
            pending += line.rstrip()[:-1] + " "
            continue
        logical = (pending + line).strip()
        pending = ""
        if not logical.startswith(("python ", "python3 ")):
            continue
        match = _TOOL_RE.search(logical)
        if match:
            found.append(Cmd(surface, start, match.group(1), logical))
    return found


def _lifted(prompts: dict[str, str], tools: tuple[str, ...]) -> list[Cmd]:
    return [c for name, text in prompts.items() for c in _commands(name, text) if c.tool in tools]


def _prepare(cmd: Cmd, out_root: Path, tmpdir: Path, feedback_id: str = "fb_2026-01-01_00000000") -> str:
    """The command as an agent would run it, pointed at the temp install and a confined /tmp."""
    text = _OPTIONAL_RE.sub("", cmd.raw)
    text = _PLACEHOLDER_RE.sub(
        lambda m: feedback_id if m.group(1) == "feedback_id" else _PLACEHOLDERS.get(m.group(1), "probe"), text)
    # Confine the prompt's own ``/tmp/`` redirects FIRST, then point the script prefix at the temp install:
    # substituting out_root first would also rewrite the ``/tmp/`` inside out_root itself whenever pytest's
    # basetemp lives under /tmp (CI's default), sending every command at a path that does not exist.
    text = text.replace("/tmp/", f"{tmpdir}/")
    return _SCRIPT_PREFIX_RE.sub(lambda m: f"{out_root}/{m.group(1)}", text)


def _shell(command: str, cwd: Path, tmpdir: Path, *, path: str | None = None) -> subprocess.CompletedProcess[str]:
    env = h.make_env(tmpdir, None, path)
    if path is None:
        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    return subprocess.run(["/bin/bash", "-c", command], capture_output=True, text=True, cwd=str(cwd),
                          timeout=h.RUN_TIMEOUT, check=False, env=env)


# ---------------------------------------------------------------------------
# layouts
# ---------------------------------------------------------------------------

def _worktree(base: Path, name: str, log_root: Path | None) -> tuple[Path, Path]:
    project = base / name
    project.mkdir(parents=True)
    out_root = h.deploy_install(project)
    if log_root is not None:
        h.declare(out_root, log_root)
    return project, out_root


def _enduring(base: Path) -> Path:
    root = base / "enduring" / "logs"
    root.mkdir(parents=True)
    return root


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _workspace_logs(project: Path) -> list[str]:
    """Every log file, and any ``debugging`` directory, that exists beneath the disposable worktree."""
    found = [str(p) for p in project.rglob("*.jsonl")]
    found += [str(p) for p in project.rglob("debugging")]
    return sorted(found)


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0


def _run_writers(commands: list[Cmd], project: Path, out_root: Path, root: Path, tmpdir: Path) -> list[str]:
    """Run each writer command from the worktree root; return one message per contract breach."""
    sinks = {"submit_feedback": root / "feedback.jsonl", "emit_event": root / "agent_telemetry.jsonl"}
    breaches = []
    for cmd in commands:
        sink = sinks[cmd.tool]
        before = _line_count(sink)
        proc = _shell(_prepare(cmd, out_root, tmpdir), project, tmpdir)
        if proc.returncode != 0:
            breaches.append(f"{cmd.where}: exited {proc.returncode}: {proc.stderr.strip()[:200]!r}")
            continue
        gained = _line_count(sink) - before
        if gained != 1:
            leaked = [Path(p).relative_to(project).as_posix() for p in _workspace_logs(project) if p.endswith(".jsonl")]
            breaches.append(
                f"{cmd.where}: expected exactly 1 record at the declared sink {sink}, found {gained}; "
                f"worktree logs now: {leaked}")
    return breaches
