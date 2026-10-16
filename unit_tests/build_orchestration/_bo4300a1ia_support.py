"""Shared support for test_bo_4300a_1_ia.py: enumerate the DEPLOYED workflows,
run them under the E2 harness with recording stand-ins, and classify the
recorded dispatches.

Nothing here reads workflow source text to decide behaviour; the only static
reader is the repo-wide shell-dispatch lint, which lives in
``unit_tests/_workflow_engine_harness.py`` (``lint_shell_dispatches``) -- the
one place the "what counts as a prompt that runs a shell command" rule is held.

DECLARED RULES (one place each, reviewed here):
    * WORKSPACE_PATTERNS -- what makes a recorded dispatch "a workspace request".
    * FORBIDDEN_OWN_STEPS -- verbs that mean "make a workspace by your own steps".
    * RUNTIME_SHELL_RE -- a recorded prompt that asks an agent to run a command.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

_UNIT_TESTS = Path(__file__).resolve().parents[1]
REPO_ROOT = _UNIT_TESTS.parent
for _p in (str(_UNIT_TESTS), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _workflow_engine_harness as harness  # noqa: E402
from scripts.suite_performance._shared_layout_producer import (  # noqa: E402
    get_or_produce_shared_layout,
)

from ._bo4300a1_helpers import build_world, run_maker  # noqa: E402

GENERIC_ARGS: dict[str, Any] = {
    "target": "/tmp/bo4300a1ia/tickets/00_inbox/epics/EPIC-Demo",
    "epic_path": "/tmp/bo4300a1ia/tickets/00_inbox/epics/EPIC-Demo",
    "ticket_path": "/tmp/bo4300a1ia/tickets/00_inbox/01_TICKET-demo.md",
    "target_branch": "EPIC-Demo",
    "userInput": "plan a small demo feature",
    "run_id": "bo4300a1ia",
    # plan-feature.js stops at its permission gate unless the entry skill's
    # pre-flight verdict is handed in. The harness can supply one from the repo's
    # own config/ and scripts/, but not from a DEPLOYED layout (there both live
    # under the output root), where plan-feature would then never reach its
    # workspace step. The verdict is passed explicitly so the run reaches it in
    # either layout.
    "workspace_setup_permission": {"permits": True, "outcome": "granted", "agent_id": "worktree-agent"},
}

WORKSPACE_PATTERNS = (
    r"git\s+worktree\s+(add|remove|prune|move)\b",
    r"worktree\.py",
    r"\bsetup_ticket_worktree\b",
    r"\b(open|create|make|set\s*up|setup|bootstrap|repair|clone)\b[^.\n]{0,60}\b(worktree|workspace)\b",
    r"\.leafcutter\b[^.\n]{0,40}\b(symlink|copy)\b|\b(symlink|copy)\b[^.\n]{0,40}\.leafcutter",
)

FORBIDDEN_OWN_STEPS = (
    r"git\s+(clone|checkout)\b", r"git\s+worktree\s+(add|remove|prune|move)\b", r"\bsymlink", r"\bln\s+-s\b", r"\bcp\s",
    r"\bmkdir\b", r"\bbootstrap", r"\bcopy\b",
)

RUNTIME_SHELL_RE = re.compile(
    r"(?:^|[\s`\"'(:])(git|gh|python3?|node|npm|pytest|rm|mv|cp|bash|sh|pwsh)\s+[-\w./\"'{$<]")

MAKER_COMMAND_RE = re.compile(
    r"(?:/|[A-Za-z]:[\\/])\S*worktree\.py[\"'`]?\s+ensure\b[^\n`]*")


_NEGATION_RE = re.compile(r"(?i)\b(do not|don't|never|nothing)\b")


def affirmative(prompt: str) -> str:
    """The prompt without lines that only FORBID something ("Do NOT run git worktree add")."""
    return "\n".join(ln for ln in prompt.splitlines() if not _NEGATION_RE.search(ln))


def is_workspace_request(prompt: Any) -> bool:
    return isinstance(prompt, str) and any(
        re.search(p, affirmative(prompt), re.I) for p in WORKSPACE_PATTERNS)


def runs_shell(prompt: Any) -> bool:
    return isinstance(prompt, str) and bool(RUNTIME_SHELL_RE.search(prompt))


def deployed_workflow_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".claude" / "workflows"


def workflow_paths(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.js"))


def registry() -> dict:
    return json.loads((REPO_ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))


def shell_permitted_agents() -> set[str]:
    return {a["id"] for a in registry()["agents"] if a.get("permits_shell") is True}


def run_workflow(path: Path, label_responses: dict | None = None,
                 args: dict | None = None) -> harness.HarnessResult:
    # workspace_default="label": these tests observe the ONE maker dispatch (which
    # workflows make it, what it carries), so a run that scripts nothing for it is
    # answered ready on that dispatch instead of being handed args.workspace.
    return harness.run_workflow_under_e2(
        path, timeout=90, label_responses=label_responses,
        args={**GENERIC_ARGS, **(args or {})}, workspace_default="label")


def collect_runs(directory: Path, args: dict | None = None) -> dict[str, harness.HarnessResult]:
    """Run EVERY workflow found in ``directory`` (enumerated, never listed)."""
    return {p.name: run_workflow(p, args=args) for p in workflow_paths(directory)}


def workspace_requests(run: harness.HarnessResult) -> list:
    return [c for c in run.agent_calls if is_workspace_request(c.prompt)]


def needing_workspace(runs: dict[str, harness.HarnessResult]) -> dict[str, list]:
    return {n: workspace_requests(r) for n, r in runs.items() if workspace_requests(r)}


def strip_maker_command(prompt: str) -> str:
    return MAKER_COMMAND_RE.sub("<MAKER-COMMAND>", affirmative(prompt))


def copy_with_extra_workflow(source_dir: Path, name: str, body: str) -> tempfile.TemporaryDirectory:
    holder = tempfile.TemporaryDirectory(prefix="bo4300a1ia_wf_")
    shutil.copytree(source_dir, Path(holder.name) / "workflows")
    (Path(holder.name) / "workflows" / name).write_text(body, encoding="utf-8")
    return holder


_WORLD = None
_ANSWER: dict | None = None


def real_maker_answer() -> dict:
    """The REAL deployed maker's ``ensure`` answer (cached for the module)."""
    global _WORLD, _ANSWER
    if _ANSWER is None:
        scripts = Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"
        _WORLD = build_world(scripts)
        done, payload = run_maker(
            _WORLD, ["ensure", "--kind", "epic", "--slug", "bo4300a1ia-epic",
                     "--repo-root", str(_WORLD.project)])
        assert payload.get("status") == "ok", (done.stderr[-800:], payload)
        _ANSWER = payload
    return _ANSWER


def cleanup_world() -> None:
    global _WORLD, _ANSWER
    if _WORLD is not None:
        _WORLD.holder.cleanup()
    _WORLD, _ANSWER = None, None
