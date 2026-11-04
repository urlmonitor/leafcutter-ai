"""
MODULE: unit_tests/workflows/_acd_2100d_5_support.py
GOAL: The one reader of the INSTALLED /plan-feature entry texts (command and
    skill) and the one runner that starts the INSTALLED plan-feature.js with
    exactly the arguments those texts show (ACD-2100d-5-i; reused by
    ACD-2100d-5, -ii, -iii and -iv).
BUSINESS CONTEXT: KI-ACD-20261022 -- the command and the skill said "pass the
    maker's answer", the workflow still wanted a startup verdict, and every
    done record stayed green because its test wrote the args object by hand.
    So here the arguments are READ, when the check runs, from the installed
    copies a real build writes; no list of arguments is kept in any test, any
    fixture or the plan-feature harness defaults. The workflow is driven through
    the E2 harness (run_workflow_under_e2) with `workspace_setup_permission`
    passed as None explicitly, so the harness default verdict cannot hide the
    defect.
ARCHITECTURE: Test-side helper, not deployed. No tests here. `installed_route()`
    builds once per process via the real installer (scripts/build.py
    --target-dir). `check_start_agreement()` is the check ACD-2100d-5-i
    specifies; it takes the three texts as parameters so a test can hand it
    temporary mutated copies, never the repository's own files.
"""

from __future__ import annotations

import atexit
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _installed_route_probe import install_route_into_temp_target  # noqa: E402
from _plan_feature_harness_defaults import workspace_answer_at  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REQUEST = "Add a CSV export to the parts list"
TRIAGE_LABEL = "stage-0-triage"
TRIAGE_REPLY = {"route": "technical", "existing_acs": []}
TIMEOUT = 40


class NoStartReadable(AssertionError):
    """The entry text shows no workflow start the check could read."""


@dataclass(frozen=True)
class InstalledRoute:
    root: Path
    command_path: Path
    skill_path: Path
    workflow_path: Path

    @property
    def command_text(self) -> str:
        return self.command_path.read_text(encoding="utf-8")

    @property
    def skill_text(self) -> str:
        return self.skill_path.read_text(encoding="utf-8")


_INSTALLED: InstalledRoute | None = None


def installed_route() -> InstalledRoute:
    """The route as the REAL installer writes it into a fresh git project (built once per process)."""
    global _INSTALLED
    if _INSTALLED is None:
        target = Path(tempfile.mkdtemp(prefix="acd2100d5_install_"))
        atexit.register(shutil.rmtree, str(target), True)
        subprocess.run(["git", "init", "-q", str(target)], check=True, capture_output=True)
        done = install_route_into_temp_target(REPO_ROOT, target)
        assert done.returncode == 0, f"installer failed: {done.stderr[-500:]}"
        _INSTALLED = InstalledRoute(
            root=target,
            command_path=target / ".claude" / "commands" / "plan-feature.md",
            skill_path=target / ".claude" / "skills" / "plan-feature" / "SKILL.md",
            workflow_path=target / ".leafcutter" / "workflows" / "plan-feature.js",
        )
        for path in (_INSTALLED.command_path, _INSTALLED.skill_path, _INSTALLED.workflow_path):
            assert path.exists(), f"the installer did not write {path}"
    return _INSTALLED


# ---------------------------------------------------------------- readers

_START_RE = re.compile(r"Workflow\(\s*[\"']plan-feature[\"']\s*,\s*\{(?P<body>[^}]*)\}\s*\)", re.S)


def read_command_start(command_text: str) -> dict[str, str]:
    """{argument name: value text} of the Workflow("plan-feature", {...}) start the command shows."""
    match = _START_RE.search(command_text)
    if not match:
        raise NoStartReadable(  # noqa: TRY003
            "no start could be read from the command text: it shows no Workflow(\"plan-feature\", {...}) start")
    pairs: dict[str, str] = {}
    for part in match.group("body").split(","):
        name, _, value = part.partition(":")
        if name.strip():
            pairs[name.strip()] = value.strip()
    return pairs


def _section(text: str, marker: str, what: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"#{2,4}\s", line) and marker in line:
            body = []
            for nxt in lines[i + 1:]:
                if re.match(r"#{1,4}\s", nxt):
                    break
                body.append(nxt)
            return "\n".join(body)
    raise NoStartReadable(f"no start could be read from the skill: it has no {what} section ({marker})")  # noqa: TRY003


def read_skill_start_args(skill_text: str) -> list[str]:
    """The `args.<name>` names the skill's workspace section (sec. WS.2) passes."""
    names = re.findall(r"args\.(\w+)", _section(skill_text, "WS.2", "workspace"))
    if not names:
        raise NoStartReadable("no start could be read from the skill's workspace section: it passes no args.<name>")  # noqa: TRY003
    return list(dict.fromkeys(names))


def read_skill_resume_args(skill_text: str) -> list[str]:
    """The names sec. RS.2 of the skill passes on a resume: args.<name> and resumeFromRunId."""
    body = _section(skill_text, "RS.2", "resume")
    names = re.findall(r"args\.(\w+)", body) + re.findall(r"\b(resumeFromRunId)\b", body)
    return list(dict.fromkeys(names))


def rename_arg(text: str, old: str, new: str) -> str:
    """Rename `args.<old>` to `args.<new>` (not args.<old>_something) in a text."""
    return re.sub(rf"args\.{old}\b", f"args.{new}", text)


# ---------------------------------------------------------------- running

def build_args(names, *, workspace: dict, request: str = REQUEST, resume_answer=None, run_id="acd2100d5-run") -> dict:
    """Harness args for exactly the argument `names` an entry text shows (nothing added)."""
    out: dict = {}
    for name in names:
        if name == "userInput":
            out[name] = request
        elif name == "resume_answer":
            out[name] = dict(resume_answer)
        elif name in ("run_id", "resumeFromRunId"):
            out["run_id"] = run_id
        elif name == "workspace_setup_permission":
            out[name] = None  # a hand-run verdict is exactly what is not supplied
        else:
            out[name] = workspace  # the maker's answer, under whatever name the text gives it
    return out


def drive(workflow_path: Path, args: dict, *, verdict=None, labels=None):
    """Run the workflow under the E2 harness; the verdict is None unless the caller supplies one."""
    result = run_workflow_under_e2(
        workflow_path, timeout=TIMEOUT,
        label_responses={TRIAGE_LABEL: TRIAGE_REPLY, **(labels or {})},
        args={**args, "workspace_setup_permission": verdict},
    )
    assert result.error == "", f"harness error: {result.error}"
    return result


def labels_of(result) -> list:
    return [c.label for c in result.agent_calls]


def reached_triage(result, request: str = REQUEST) -> bool:
    return any(c.label == TRIAGE_LABEL and request in str(c.prompt) for c in result.agent_calls)


def halt_message(result) -> str:
    terminal = result.result if isinstance(result.result, dict) else {}
    return str(terminal.get("message", "")) if terminal.get("status") == "error" else ""


def workspace_answer(directory) -> dict:
    return workspace_answer_at(directory)


# ---------------------------------------------------------------- the check

@dataclass
class CheckReport:
    problems: list[str] = field(default_factory=list)
    runs: dict = field(default_factory=dict)
    command_args: list[str] | None = None
    skill_args: list[str] | None = None


def check_start_agreement(command_text: str, skill_text: str, workflow_path: Path) -> CheckReport:
    """Read the start from each entry text and run the workflow with it; report each side that falls short."""
    report = CheckReport()
    sides: dict[str, list[str]] = {}
    try:
        pairs = read_command_start(command_text)
        report.command_args = list(pairs)
        sides["command"] = list(pairs)
    except NoStartReadable as exc:
        report.problems.append(f"the installed command: {exc}")
    try:
        report.skill_args = ["userInput", *read_skill_start_args(skill_text)]
        sides["skill"] = report.skill_args
    except NoStartReadable as exc:
        report.problems.append(f"the installed skill: {exc}")
    with tempfile.TemporaryDirectory(prefix="acd2100d5_ws_") as tmp:
        workspace = workspace_answer(tmp)
        for side, names in sides.items():
            result = drive(workflow_path, build_args(names, workspace=workspace))
            report.runs[side] = result
            if reached_triage(result):
                continue
            message = halt_message(result)
            lacking = [n for n in dict.fromkeys(re.findall(r"args\.(\w+)", message)) if n not in names]
            for name in lacking:
                report.problems.append(
                    f"the workflow needs args.{name} but the installed {side} does not supply it")
            if not lacking:
                report.problems.append(
                    f"the run started as the installed {side} shows did not reach triage and its halt names "
                    f"no missing argument: {message or result.result!r}")
    return report
