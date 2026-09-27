"""Census: no shipped commit recipe is newly blocked by the argv-parsing delegation hook.

Covers BP-1100d-3-i. BP-1100d-3 replaced the commit-delegation hook's
``"git commit" in command`` substring test with an argv parser, so
``git -C <path> commit`` is now recognised as a commit. Any recipe that the
package itself ships -- a fenced command in a skill, agent or workflow
markdown file, or a command string inside a JS workflow prompt -- and that
passed the OLD rule but is caught by the NEW one would start failing the
moment the hook is deployed. This test runs the real hook's own detector over
every such recipe in ``templates/`` and fails on any recipe the new hook
blocks that the old rule allowed and that does not carry the
``COMMIT_AGENT_MODE=1`` exemption.

It deliberately does not flag recipes the OLD rule already blocked (bare
``git commit`` lines): those were broken before this change and are tracked
separately; this test guards the migration, not the whole backlog.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_TEMPLATES = _REPO / "templates"
_HOOK_PATH = _TEMPLATES / "hooks" / "enforce_commit_delegation.py"
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _load_hook():
    """Import the real hook module from its template path."""
    spec = importlib.util.spec_from_file_location("_ecd_census_hook", _HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalise(line: str) -> str:
    """Strip JS string-literal and prompt decoration from one recipe line."""
    text = line.strip()
    text = re.sub(r"\\n[\"'`]?\s*\+?$", "", text)
    text = text.strip().strip("+").strip().strip("\"'`").strip()
    text = re.sub(r"^(Run|Command|\$)\s*:?\s+", "", text)
    return text.replace("\\\"", "\"")


def _markdown_recipes(path: Path) -> list[tuple[int, str]]:
    """Return (line number, text) for every line inside a fenced block."""
    recipes: list[tuple[int, str]] = []
    inside = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE_RE.match(line):
            inside = not inside
            continue
        if inside:
            recipes.append((number, _normalise(line)))
    return recipes


def _js_recipes(path: Path) -> list[tuple[int, str]]:
    """Return (line number, text) for every JS line that mentions git."""
    return [
        (number, _normalise(line))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "git" in line
    ]


def _newly_blocked(hook) -> list[str]:
    """List recipes blocked by the new detector but allowed by the old rule."""
    found: list[str] = []
    sources = [(p, _markdown_recipes) for p in _TEMPLATES.rglob("*.md")]
    sources += [(p, _js_recipes) for p in (_TEMPLATES / "workflows-js").glob("*.js")]
    for path, extract in sources:
        for number, text in extract(path):
            if "commit" not in text or "git" not in text:
                continue
            payload = {"tool_input": {"command": text}}
            new_blocks = hook._is_git_commit_call(payload) and not hook._is_commit_agent_mode(payload)
            old_blocks = "git commit" in text
            if new_blocks and not old_blocks:
                found.append(f"{path.relative_to(_REPO).as_posix()}:{number}: {text}")
    return found


def test_no_shipped_recipe_is_newly_blocked_by_the_argv_parser() -> None:
    # covers: BP-1100d-3-i
    """Every recipe the new hook blocks was already blocked, or carries the exemption."""
    hook = _load_hook()
    offenders = _newly_blocked(hook)
    assert offenders == [], (
        "These shipped recipes passed the old substring rule but the argv-parsing "
        "hook blocks them; route them through the commit agent or the exemption:\n  "
        + "\n  ".join(offenders)
    )


def test_census_actually_sees_recipes() -> None:
    # covers: BP-1100d-3-i
    """Guard against a census that silently scans nothing."""
    hook = _load_hook()
    fast_lane = _TEMPLATES / "workflows-js" / "fast-lane-ship.js"
    exempt = [t for _, t in _js_recipes(fast_lane) if "COMMIT_AGENT_MODE=1" in t and "commit" in t]
    assert exempt, "census found no exempt fast-lane commit recipe; extraction is broken"
    payload = {"tool_input": {"command": exempt[0]}}
    assert hook._is_git_commit_call(payload), "detector no longer recognises the fast-lane commit"
