"""
MODULE: unit_tests/workflows/_bo4500a5v_support.py
GOAL: Shared readers for the BO-4500a-5-v tests: the commit agent template's text and
      the commands it instructs. Template-text tests are the strongest unit-level proof
      for an LLM surface (the AC's own test_rationale; BO-2400a-1-i precedent), so the
      checks here target COMMANDS and literal patterns, never incidental prose.

The template is read from templates/agents/commit.md, the source the build deploys to
.claude/agents/commit.md unchanged for this file (no config token in it), exactly as the
sibling agent-template text tests read it; no test here spawns its own build.py.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "templates" / "agents" / "commit.md"

#: A literal model name such as "Claude Opus 4.7" or "Claude Sonnet 5".
MODEL_NAME = re.compile(r"Claude\s+(?:Opus|Sonnet|Haiku|Fable)\s+\d", re.I)
#: A Co-Authored-By trailer that credits a Claude model (the hardcoded footer).
CLAUDE_TRAILER = re.compile(r"Co-Authored-By:\s*Claude", re.I)

_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)

#: Commands that must not be instructed inside any fenced command block.
FORBIDDEN_IN_BLOCKS = {
    "git add": re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?add\b"),
    "git commit": re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?commit\b"),
    "git stash": re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?stash\b"),
    "pkill": re.compile(r"\bpkill\b"),
    "kill": re.compile(r"(?:^|[\s;&|])kill\s+(?:-\w+\s+)?[<\d$]", re.M),
    "taskkill": re.compile(r"\btaskkill\b", re.I),
    "Stop-Process": re.compile(r"\bStop-Process\b", re.I),
}
#: Strings that must not appear anywhere in the template, prose or block.
FORBIDDEN_ANYWHERE = {
    "COMMIT_AGENT_MODE=1 git commit": re.compile(r"COMMIT_AGENT_MODE=1\s+git\s+commit"),
    "process enumeration (pgrep)": re.compile(r"\bpgrep\b"),
    "literal model name": MODEL_NAME,
    "Claude co-author trailer": CLAUDE_TRAILER,
}


def template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def fenced_blocks(text: str) -> list[str]:
    return _FENCE.findall(text)


def forbidden_hits(text: str) -> list[str]:
    """Names of every forbidden command / literal found in *text* (empty when clean)."""
    hits: list[str] = []
    blocks = "\n".join(fenced_blocks(text))
    for name, pattern in FORBIDDEN_IN_BLOCKS.items():
        if pattern.search(blocks):
            hits.append(name)
    for name, pattern in FORBIDDEN_ANYWHERE.items():
        if pattern.search(text):
            hits.append(name)
    return hits


def step_invocations(text: str) -> list[str]:
    """Every fenced command block that runs the shared step with a message file."""
    return [b for b in fenced_blocks(text) if "commit_changes.py" in b and "--message-file" in b]
