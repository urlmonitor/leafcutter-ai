"""
MODULE: unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
AC: BO-4300a-1-ia -- "No workflow body asks an agent to make a workspace in
    its own words."
GOAL: Static helpers for the repo-wide shell-dispatch-permission lint
    (test_bo_4300a_1_ia_lint.py) and the free-form-workspace-instruction
    scan: directory enumeration, registry read (permits_shell), the ONE
    declared "prompt runs a shell command" rule, agent() call parsing, and
    WORKSPACE-ANSWER block extraction. The harness-driven scenario helpers
    live in _bo_4300c_3_fixtures.py.

NOT a test file itself (leading underscore) -- not collected by pytest.

DECISION HISTORY: 2026-10-12 [test-writer/EPIC-EveryPieceOfSeparateWork
GetsItsWorkspace/10]: restored from refs/wip/bo4300-attempt1 and trimmed:
the three-workflow runtime scenario table moved to _bo_4300c_3_fixtures.py
where the consuming set is DERIVED from the deployed workflows.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._bo_4300f_2_fixtures import OLD_WAY_ADD_TEXT, OLD_WAY_REMOVE_TEXT

REPO_ROOT = Path(__file__).resolve().parents[2]

# The repo-wide static lint's own it_requirement names its scan target
# literally: "any agent dispatch in any templates/workflows-js/*.js" -- a
# DIFFERENT (source) directory from the harness-driven tests above, per the
# AC's own wording for that test_spec entry.
TEMPLATE_WORKFLOWS_DIR = REPO_ROOT / "templates" / "workflows-js"

AGENT_REGISTRY_PATH = REPO_ROOT / "config" / "agent_registry.json"
_WORKSPACE_ANSWER_START = "// WORKSPACE-ANSWER-START"
_WORKSPACE_ANSWER_END = "// WORKSPACE-ANSWER-END"


# Directory enumeration (test #4's seam, and the lint's own file source)


def list_deployed_workflow_files(directory: Path | None = None) -> list[Path]:
    """Enumerate every workflow script from `directory` (default:
    TEMPLATE_WORKFLOWS_DIR) via a plain directory glob -- never a
    hard-coded name list, so a workflow added later is picked up
    automatically (this AC's own text: "a workflow added later ... is
    covered by the same check without anyone editing a list")."""
    target = directory if directory is not None else TEMPLATE_WORKFLOWS_DIR
    if not target.is_dir():
        return []
    return sorted(target.glob("*.js"))


# Registry (permits_shell)


def load_agent_registry() -> dict[str, Any]:
    with AGENT_REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def shell_permitted_agent_ids(registry: dict[str, Any] | None = None) -> set[str]:
    """Every agent id whose registry entry declares `permits_shell: true`.
    An absent field counts as NOT permitted (the AC's own literal text)."""
    reg = registry if registry is not None else load_agent_registry()
    permitted: set[str] = set()
    for entry in reg.get("agents", []):
        if entry.get("permits_shell") is True and entry.get("id"):
            permitted.add(entry["id"])
    return permitted


# Shell-command-prompt / free-form-workspace-instruction detection

# ONE declared, reviewed rule (per this AC's own it_requirements wording): a
# prompt counts as instructing an agent to run a shell command when it names
# a command LINE starting with one of these tokens, at the start of a
# physical source line or right after a template-literal/backtick boundary.
_SHELL_COMMAND_PATTERN = re.compile(
    r"(?:^|[\n`]|\\n)[ \t]*[\"']?[ \t]*"
    r"(git|gh|python3?|node|npm|pytest|rm|mv|cp|bash|sh|pwsh)\b",
    re.MULTILINE,
)

# Free-form workspace-instruction phrases (create/copy/set up/link/repair a
# workspace "by the agent's own choosing") -- the exact multi-step prompts
# this ticket's own Implementation Notes name for removal.
_FREE_FORM_WORKSPACE_PHRASES = (
    "open a new git worktree",
    OLD_WAY_ADD_TEXT,
    OLD_WAY_REMOVE_TEXT,
    "bootstrap",  # matches both "Bootstrap it" and "bootstraps it"
    "symlink .leafcutter",
    "copy/symlink",
    "rm -rf",
)


def prompt_runs_shell_command(text: str) -> bool:
    """True when `text` names a command line starting with one of
    git/gh/python(3)/node/npm/pytest/rm/mv/cp/bash/sh/pwsh."""
    if not isinstance(text, str):
        return False
    return bool(_SHELL_COMMAND_PATTERN.search(text))


def free_form_workspace_phrase(text: str) -> str | None:
    """Returns the offending phrase if `text` asks an agent to create, copy,
    set up, link or repair a workspace by steps of its own choosing; None
    otherwise."""
    if not isinstance(text, str):
        return None
    lowered = text.lower()
    for phrase in _FREE_FORM_WORKSPACE_PHRASES:
        if phrase in lowered:
            return phrase
    return None


# Repo-wide shell-dispatch lint: agent() call parsing (bracket-scanning, not a full JS parser -- sufficient for this repo's own workflow-authoring style; see parse_agent_dispatches()'s own docstring).

_AGENT_CALL_START = re.compile(r"\bagent\s*\(")


def _find_matching_close_paren(text: str, open_idx: int) -> int:
    """Scan forward from '(' at `open_idx`, respecting nested parens and
    string/template literals (backslash-escaped), returning the matching ')'."""
    depth = 0
    i = open_idx
    in_string: str | None = None
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    msg = f"no matching ')' found for '(' at offset {open_idx}"
    raise ValueError(msg)


def _resolve_identifier(source: str, identifier: str) -> str | None:
    """Best-effort resolution of a bare `agentType: IDENT` identifier via a
    top-level `const/let/var IDENT = "value";` literal assignment. Returns
    None when unresolvable (e.g. runtime-resolved from the registry, like
    plan-feature.js's `workspaceSetupAgentId`) -- reported as a violation by
    shell_dispatch_violations() below (fail-closed)."""
    pattern = re.compile(r"(?:const|let|var)\s+" + re.escape(identifier) + r"\s*=\s*[\"']([^\"']+)[\"']")
    match = pattern.search(source)
    return match.group(1) if match else None


@dataclass
class ParsedDispatch:
    workflow: str
    label: str | None
    agent_type_raw: str
    agent_type_resolved: str | None
    prompt_text: str
    line_no: int


def parse_agent_dispatches(source: str, workflow_name: str) -> list[ParsedDispatch]:
    """Parse every `agent(...)` call in `source` via bracket scanning (never
    a full JS parser). Skips calls with no `agentType:` key."""
    dispatches: list[ParsedDispatch] = []
    for m in _AGENT_CALL_START.finditer(source):
        open_idx = m.end() - 1
        try:
            close_idx = _find_matching_close_paren(source, open_idx)
        except ValueError:
            continue
        call_text = source[open_idx : close_idx + 1]
        agent_type_match = re.search(r"agentType\s*:\s*([\"']?[A-Za-z0-9_.-]+[\"']?)", call_text)
        if not agent_type_match:
            continue
        raw = agent_type_match.group(1)
        label_match = re.search(r"\blabel\s*:\s*[\"']([^\"']+)[\"']", call_text)
        if raw[:1] in ("'", '"'):
            literal = raw.strip("'\"")
            resolved: str | None = literal
        else:
            literal = raw
            resolved = _resolve_identifier(source, raw)
        dispatches.append(
            ParsedDispatch(
                workflow=workflow_name,
                label=label_match.group(1) if label_match else None,
                agent_type_raw=literal,
                agent_type_resolved=resolved,
                prompt_text=call_text,
                line_no=source.count("\n", 0, open_idx) + 1,
            )
        )
    return dispatches


def shell_dispatch_violations(
    source: str, workflow_name: str, permitted_ids: set[str]
) -> list[dict[str, str]]:
    """Every agent() dispatch in `source` whose prompt runs a shell command
    but whose agentType is not a resolved permits_shell:true id (an
    unresolved identifier is reported too -- fail-closed)."""
    violations: list[dict[str, str]] = []
    for dispatch in parse_agent_dispatches(source, workflow_name):
        if not prompt_runs_shell_command(dispatch.prompt_text):
            continue
        if dispatch.agent_type_resolved is not None and dispatch.agent_type_resolved in permitted_ids:
            continue
        command_match = _SHELL_COMMAND_PATTERN.search(dispatch.prompt_text)
        violations.append(
            {
                "workflow": workflow_name,
                "step": dispatch.label or f"line {dispatch.line_no}",
                "agent_type": dispatch.agent_type_resolved or f"<unresolved:{dispatch.agent_type_raw}>",
                "command": command_match.group(0).strip(" \t\n`\"'") if command_match else "<unknown>",
            }
        )
    return violations


def all_shell_dispatch_violations(
    directory: Path | None = None, registry: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    """shell_dispatch_violations() applied across every workflow file
    list_deployed_workflow_files() enumerates from `directory` (default:
    TEMPLATE_WORKFLOWS_DIR, matching the lint's own declared scan target)."""
    target = directory if directory is not None else TEMPLATE_WORKFLOWS_DIR
    permitted = shell_permitted_agent_ids(registry)
    violations: list[dict[str, str]] = []
    for wf_path in list_deployed_workflow_files(target):
        source = wf_path.read_text(encoding="utf-8")
        violations.extend(shell_dispatch_violations(source, wf_path.name, permitted))
    return violations


# WORKSPACE-ANSWER build-inlined-block discovery (BO-4300c-3)


def extract_workspace_answer_block(source: str) -> str | None:
    """Returns the marker-delimited WORKSPACE-ANSWER block's own text
    (markers included) from `source`, or None if absent."""
    start = source.find(_WORKSPACE_ANSWER_START)
    end = source.find(_WORKSPACE_ANSWER_END)
    if start == -1 or end == -1 or end < start:
        return None
    return source[start : end + len(_WORKSPACE_ANSWER_END)]


# ---------------------------------------------------------------------------
# Ticket 02 (EPIC-WorkspaceMakerHardening, M13/M16/M5): maker-command shape.
# ---------------------------------------------------------------------------

FIXTURE_PROJECT = "/fixture/proj"
# The scripted reply of the maker-path probe (git common dir of the fixture project).
FIXTURE_COMMON_DIR_STDOUT = FIXTURE_PROJECT + "/.git\n"
RESOLVE_LABEL = "resolve-maker-path"
# A handed-in workspace names its project in its marker; one probe step reads it (the reply: the file's text).
MARKER_LABEL = "read-workspace-marker"


def marker_reply(project_root: str = FIXTURE_PROJECT) -> dict[str, Any]:
    """The shell-runner reply of the marker read: the marker's JSON text (built by json.dumps), exit 0."""
    return {"command": "cat workspace.json", "exit_status": 0,
            "stdout": json.dumps({"project_root": project_root}), "stderr": ""}

# `python(3) "<absolute>/scripts/worktree.py" <verb>`: the one exact absolute, quoted form.
ABSOLUTE_QUOTED_MAKER = re.compile(
    r"^python3?\s+\"(?:/|[A-Za-z]:[\/])[^\"]*scripts[\/]worktree\.py\"\s+(?:ensure|verify|remove|locate)\b"
)
# A value flag whose value is not opened by a double quote.
UNQUOTED_VALUE_FLAG = re.compile(r"--(?:slug|path|ticket)\s+(?!\")\S")
# A maker command spelled with a relative or bare script path.
RELATIVE_MAKER_SPELLING = re.compile(
    r"python3?\s+(?!\?[\"'$]|\$\{)(?:\./)?(?:\{\{config\.output_root\}\}/|\.leafcutter/)?(?:scripts/)?worktree\.py"
)
# A maker command spelled with the rendered (relative) output root.
OUTPUT_ROOT_MAKER = re.compile(r"\{\{config\.output_root\}\}/scripts/worktree\.py")
# A maker command whose script path is not one double-quoted word: relative, bare, or an absolute / placeholder
# path (`<absolute-install-root>/scripts/worktree.py`, `/abs/...`) left unquoted. The AC requires the quoting.
UNQUOTED_MAKER_PATH = re.compile(r"""python3?\s+(?!["'])(?:<[^>]*>|[^\s"'`<])*worktree\.py""")
def cwd_relative_maker_hits(rel_path: str, text: str) -> list[str]:
    """Lines of `text` (a template file at `rel_path`, relative to templates/) that run the maker by a cwd-relative path.

    Nothing is exempt: no file, line or constant is allowed to spell the maker relative to the cwd.
    """
    return [
        f"{rel_path}:{no}: {line.strip()[:100]}"
        for no, line in enumerate(text.splitlines(), 1)
        if RELATIVE_MAKER_SPELLING.search(line) or OUTPUT_ROOT_MAKER.search(line) or UNQUOTED_MAKER_PATH.search(line)
    ]


# A dispatched current-branch command that names no location (the exact command string only).
UNANCHORED_BRANCH_COMMAND = re.compile(r"[`\"']git branch --show-current[`\"']")


def maker_command_line(prompt: Any) -> str | None:
    """The command line of a shell-step prompt that runs the maker, or None."""
    for line in str(prompt).splitlines():
        if "worktree.py" in line and re.match(r"\s*python3?\s", line):
            return line.strip()
    return None


def maker_command_defects(command: str) -> list[str]:
    """Why `command` is not the one exact absolute, quoted maker command ([] when it is)."""
    defects = []
    if not ABSOLUTE_QUOTED_MAKER.match(command):
        defects.append("does not start with an absolute, quoted path to scripts/worktree.py")
    if UNQUOTED_VALUE_FLAG.search(command):
        defects.append("an interpolated --slug/--path/--ticket value is not double-quoted")
    return defects


_BRANCH_NODE_RUNNER = """
const fs = require('fs'), vm = require('vm');
const [src, answers] = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ctx = { agent: async () => null, args: {}, log() {}, console };
vm.createContext(ctx);
vm.runInContext(src + '\\n;globalThis.__f = workspaceBranch;', ctx);
process.stdout.write(JSON.stringify(answers.map(a => ctx.__f(a))));
"""


def workspace_branch_results(block: str, answers: list[dict[str, Any]]) -> list[str]:
    """Run the deployed block's own `workspaceBranch` over each answer in Node."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory(prefix="bo4300a1ia-branch-") as tmp:
        Path(tmp, "in.json").write_text(json.dumps([block, answers]), encoding="utf-8")
        Path(tmp, "run.js").write_text(_BRANCH_NODE_RUNNER, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(Path(tmp, "run.js")), str(Path(tmp, "in.json"))],
            capture_output=True, text=True, timeout=30,
        )
    return json.loads(proc.stdout)
