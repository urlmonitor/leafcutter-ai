"""
MODULE: _inf_500d_3_ii_check
GOAL: The check of INF-500d-3-ii: every deployed instruction that sends a feedback
    submission's error stream to a file must name a file of that run's own.
BUSINESS CONTEXT: Two agents finishing in the same second must not share an error-stream
    file, or one agent's id-recovery search reads the other's line. The check FILLS IN each
    prescribed name for concrete runs (ticket + phase) and compares the results; it never
    only greps for a suffix.
ARCHITECTURE: Pure text functions (no build, no I/O except ``discover_surfaces``). A
    redirecting instruction is DISCOVERED at check time: any logical command line (backslash
    continuations joined) that runs ``submit_feedback.py`` and redirects its error stream to
    a file other than /dev/null. There is no list of file names. Placeholders are filled by
    their SPELLING, so an instruction author may choose any ticket / phase placeholder:
    a placeholder whose name contains ``ticket`` is the run's ticket (``*path*`` -> a
    tickets/ path with separators, ``*base*|*name*|*stem*|*file*`` -> ``<ticket>.md``,
    otherwise the bare ticket); ``agent_name`` / ``phase`` / ``phase_name`` / ``agent`` is the
    run's phase. Everything else keeps the value the sibling helpers use.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from unit_tests.feedback._inf_500d_4_vi_helpers import _PLACEHOLDER_RE, _PLACEHOLDERS

TICKET_A, TICKET_B = "03-add-parser", "05-wire-cli"
PHASE_A, PHASE_B = "python-coder", "pr-reviewer"
EVENT_KINDS = ("mechanical-retry", "cross-agent-rework", "brainstorm-escalation", "halt")
PHASE_PLACEHOLDERS = frozenset({"agent_name", "phase", "phase_name", "agent", "agent_phase", "phase_agent"})
SCAN_DIRS = ("agents", "skills", "commands", "workflows", "gemini")


@dataclass(frozen=True)
class Run:
    phase: str
    ticket: str


RUN_A = Run(PHASE_A, TICKET_A)  # python-coder signing off on 03-add-parser
RUN_B = Run(PHASE_B, TICKET_B)  # pr-reviewer signing off on 05-wire-cli
COMBOS = tuple(Run(p, t) for t in (TICKET_A, TICKET_B) for p in (PHASE_A, PHASE_B))


@dataclass(frozen=True)
class Redirect:
    surface: str
    line: int
    command: str
    target: str  # raw, placeholders unfilled


@dataclass(frozen=True)
class Search:
    surface: str
    line: int
    command: str  # the grep ... <file> part only
    target: str


@dataclass
class CheckResult:
    inspected: int
    surfaces: int
    problems: list[str]

    @property
    def ok(self) -> bool:
        return self.inspected > 0 and not self.problems

    @property
    def message(self) -> str:
        head = f"inspected {self.inspected} redirecting instruction(s) across {self.surfaces} surface(s)"
        if self.inspected == 0:
            return f"FAIL: {head}; a check that inspects zero instructions proves nothing"
        if self.problems:
            return f"FAIL: {head}; {len(self.problems)} problem(s):\n  " + "\n  ".join(self.problems)
        return f"OK: {head}"


# ---------------------------------------------------------------------------
# filling placeholders
# ---------------------------------------------------------------------------

def fill(text: str, run: Run) -> str:
    """``text`` with every ``<placeholder>`` filled for ``run``."""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        low = name.lower()
        if "ticket" in low:
            if "path" in low:
                return f"tickets/01_todo/{run.ticket}.md"
            if any(key in low for key in ("base", "name", "stem", "file")):
                return f"{run.ticket}.md"
            return run.ticket
        if low in PHASE_PLACEHOLDERS:
            return run.phase
        return _PLACEHOLDERS.get(name, "probe")

    return _PLACEHOLDER_RE.sub(repl, text)


def phase_of(command: str, run: Run) -> str:
    """The phase the filled-in command submits as (its ``--phase`` value)."""
    match = re.search(r"--phase\s+(\S+)", fill(command, run))
    return match.group(1) if match else run.phase


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def logical_lines(text: str) -> list[tuple[int, str]]:
    """(first line number, command text) with backslash continuations joined."""
    out: list[tuple[int, str]] = []
    pending, start = "", 0
    for number, line in enumerate(text.splitlines(), start=1):
        if not pending:
            start = number
        if line.rstrip().endswith("\\"):
            pending += line.rstrip()[:-1] + " "
            continue
        out.append((start, (pending + line).strip()))
        pending = ""
    return out


_REDIRECT_RE = re.compile(r"(?<![\w&>])2>\s*([^\s)&;|`'\"]+)")
_SEARCH_RE = re.compile(r"grep\s+(?:-\w+\s+)*'[^']*sidecar:[^']*'\s+([^\s|`)\\]+)")


def redirects(surface: str, text: str) -> list[Redirect]:
    found = []
    for number, logical in logical_lines(text):
        if "submit_feedback.py" not in logical:
            continue
        match = _REDIRECT_RE.search(logical)
        if match and match.group(1) != "/dev/null":
            found.append(Redirect(surface, number, logical, match.group(1)))
    return found


def searches(surface: str, text: str) -> list[Search]:
    found = []
    for number, logical in logical_lines(text):
        match = _SEARCH_RE.search(logical)
        if match:
            found.append(Search(surface, number, logical[match.start():match.end()], match.group(1)))
    return found


def discover_surfaces(root: Path) -> dict[str, str]:
    """Every instruction ``.md`` under ``root`` (a deployed ``.leafcutter``); {} when it is absent."""
    found: dict[str, str] = {}
    for sub in SCAN_DIRS:
        base = Path(root) / sub
        if not base.is_dir():
            continue
        for dirpath, _dirs, files in os.walk(base, followlinks=True):
            for name in files:
                if name.endswith(".md"):
                    path = Path(dirpath) / name
                    found[str(path.relative_to(root))] = path.read_text(encoding="utf-8", errors="replace")
    return found


# ---------------------------------------------------------------------------
# judging
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"[A-Za-z0-9._-]+")


def name_problems(resolved: str, ticket: str, phase: str) -> list[str]:
    """Why ``resolved`` is not a single-component name carrying both ``ticket`` and ``phase``."""
    problems = []
    directory, _, name = resolved.rpartition("/")
    if directory not in ("", "/tmp"):
        problems.append(f"{resolved!r} is not one path component (directory part {directory!r})")
    if not _NAME_RE.fullmatch(name):
        problems.append(f"{name!r} holds a separator, space or shell metacharacter")
    if ticket not in name:
        problems.append(f"{name!r} lacks the ticket {ticket!r}")
    if phase not in name:
        problems.append(f"{name!r} lacks the phase {phase!r}")
    return problems


def resolve_all(target: str, command: str) -> dict[tuple[str, str], str]:
    """Resolved name per distinct (ticket, effective phase) caller combination."""
    names: dict[tuple[str, str], str] = {}
    for run in COMBOS:
        names.setdefault((run.ticket, phase_of(command, run)), fill(target, run))
    return names


def collisions(target: str, command: str) -> list[str]:
    """Distinct callers (different ticket or phase) that resolve to the same name."""
    seen: dict[str, tuple[str, str]] = {}
    out = []
    for key, name in resolve_all(target, command).items():
        if name in seen:
            out.append(f"{seen[name]} and {key} both resolve to {name!r}")
        seen.setdefault(name, key)
    return out


def judge_redirect(red: Redirect) -> list[str]:
    problems = [f"{red.surface}:{red.line} {c}" for c in collisions(red.target, red.command)]
    for (ticket, phase), name in resolve_all(red.target, red.command).items():
        problems += [f"{red.surface}:{red.line} {p}" for p in name_problems(name, ticket, phase)]
    return problems


def judge_search(search: Search, reds: list[Redirect]) -> list[str]:
    """The search must read the file one of the same surface's submit steps wrote, for every caller."""
    for red in reds:
        if all(fill(search.target, r) == fill(red.target, r) for r in COMBOS):
            return []
    wrote = sorted({r.target for r in reds})
    return [f"{search.surface}:{search.line} the search reads {search.target!r} but the submit step writes {wrote}"]


def check(surfaces: dict[str, str]) -> CheckResult:
    """Judge every discovered redirecting instruction; fail when none was inspected."""
    inspected, problems, used = 0, [], set()
    for surface, text in sorted(surfaces.items()):
        reds = redirects(surface, text)
        if reds:
            used.add(surface)
        inspected += len(reds)
        for red in reds:
            problems += judge_redirect(red)
        for search in searches(surface, text):
            problems += judge_search(search, reds)
    return CheckResult(inspected, len(used), problems)
